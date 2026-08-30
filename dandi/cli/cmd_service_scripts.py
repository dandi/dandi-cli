from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from difflib import unified_diff
import json
import os
from pathlib import PurePosixPath
import re
from textwrap import indent
from typing import Any, TypeVar
import urllib.parse
from uuid import uuid4

import click
from dandischema.consts import DANDI_SCHEMA_VERSION
from packaging.version import Version
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError, RequestException

from dandi.consts import known_instances

from .base import ChoiceList, instance_option, map_to_click_exceptions
from .. import __version__, lgr
from ..dandiapi import DandiAPIClient, RemoteBlobAsset, RESTFullAPIClient
from ..dandiarchive import parse_dandi_url
from ..exceptions import HTTP404Error, NotFoundError
from ..utils import yaml_dump

T = TypeVar("T")


DOI_HUMAN_URLS = {
    "https://api.test.datacite.org/dois": "https://doi.test.datacite.org/dois",
    "https://api.datacite.org/dois": "https://doi.datacite.org/dois",
}

#: Base URL of the DOI resolver used to look up citation metadata
DOI_RESOLVER_URL = "https://doi.org/"

#: Content type requested from the DOI resolver for citation metadata
DOI_CSL_ACCEPT = "application/vnd.citationstyles.csl+json; charset=utf-8"

#: Matches a bare DOI, e.g. ``10.48324/dandi.001827/0.260505.1322``
DOI_REGEX = re.compile(r"10\.\d{4,9}/\S+")

#: Prefixes a DOI may be spelled with, in the order they are stripped
DOI_PREFIX_REGEXES = (r"doi:", r"(?:https?://)?(?:dx\.)?doi\.org/")


def normalize_doi(doi: str) -> str:
    """Reduce a DOI given in any of its usual spellings to the bare DOI.

    A bare DOI (``10.48324/dandi.001827/0.260505.1322``), a ``doi:`` URI, and a
    resolver URL (``https://doi.org/...``, ``http://dx.doi.org/...``) are all
    accepted and reduced to the bare form.

    Parameters
    ----------
    doi : str
        The DOI as given by the user

    Returns
    -------
    str
        The bare DOI

    Raises
    ------
    ValueError
        If `doi` is not a syntactically valid DOI in any accepted spelling
    """
    value = doi.strip()
    for prefix_regex in DOI_PREFIX_REGEXES:
        if m := re.match(prefix_regex, value, flags=re.I):
            value = value[m.end() :].strip()
            break
    if not DOI_REGEX.fullmatch(value):
        raise ValueError(
            f"{doi!r} does not look like a DOI.  Expected something like "
            "'10.48324/dandi.001827/0.260505.1322', optionally prefixed with "
            "'doi:' or 'https://doi.org/'."
        )
    return value


def fetch_doi_citation_metadata(doi: str) -> dict[str, Any]:
    """Fetch the CSL JSON citation metadata for a bare `doi` from doi.org.

    Parameters
    ----------
    doi : str
        A bare DOI, as returned by `normalize_doi()`

    Returns
    -------
    dict
        The parsed CSL JSON record

    Raises
    ------
    click.ClickException
        If the DOI cannot be resolved, or if the resolver answers with
        something other than a CSL JSON object.  The exception message
        describes what went wrong, so that the user is not left with a bare
        `json.JSONDecodeError` traceback.
    """
    url = f"{DOI_RESOLVER_URL}{doi}"
    with RESTFullAPIClient(
        DOI_RESOLVER_URL, headers={"Accept": DOI_CSL_ACCEPT}
    ) as doiclient:
        try:
            r = doiclient.get(doi, json_resp=False)
        except HTTP404Error:
            raise click.ClickException(
                f"DOI {doi} is not registered: {url} returned 404.  Check the "
                "DOI for typos and make sure it has already been published."
            )
        except HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            raise click.ClickException(
                f"Failed to look up DOI {doi}: {url} returned HTTP {status}."
            )
        except RequestException as e:
            raise click.ClickException(f"Failed to look up DOI {doi} at {url}: {e}")
        content_type = r.headers.get("Content-Type", "<unset>")
        try:
            doidata = r.json()
        except ValueError:
            raise click.ClickException(
                f"DOI {doi} did not resolve to citation metadata: {url} answered "
                f"with {content_type!r} instead of CSL JSON (final URL: {r.url}).  "
                "This usually means the DOI's registration agency does not serve "
                "citation metadata for it, and doi.org fell back to redirecting "
                "to the landing page."
            )
    if not isinstance(doidata, dict):
        raise click.ClickException(
            f"DOI {doi} resolved to a JSON {type(doidata).__name__} rather than "
            f"the expected CSL JSON object (final URL: {r.url})."
        )
    return doidata


@click.group()
def service_scripts() -> None:
    """Various utility operations"""
    pass


@service_scripts.command()
@click.option("--diff", is_flag=True, help="Show diffs of old & new metadata")
@click.option(
    "--when",
    type=click.Choice(["newer-schema-version", "always"]),
    default="newer-schema-version",
    help="When to re-extract an asset's metadata",
    show_default=True,
)
@click.argument("url")
@map_to_click_exceptions
def reextract_metadata(url: str, diff: bool, when: str) -> None:
    """
    Recompute & update the metadata for NWB assets on a remote server.

    Running this command requires the fsspec library to be installed with the
    `http` extra (e.g., `pip install "fsspec[http]"`).
    """
    from ..metadata.nwb import nwb2asset  # Avoid heavy import at top level

    parsed_url = parse_dandi_url(url)
    if parsed_url.dandiset_id is None:
        raise click.UsageError("URL must point to an asset within a Dandiset.")
    if parsed_url.version_id != "draft":
        raise click.UsageError(
            "URL must explicitly point to a draft version of a Dandiset"
        )
    current_schema_version = Version(DANDI_SCHEMA_VERSION)
    with parsed_url.navigate(authenticate=True, strict=True) as (_, _, assets):
        for asset in assets:
            if PurePosixPath(asset.path).suffix.lower() != ".nwb":
                lgr.info(
                    "Asset %s (%s) is not NWB; skipping", asset.identifier, asset.path
                )
            assert isinstance(asset, RemoteBlobAsset)
            lgr.info("Processing asset %s (%s)", asset.identifier, asset.path)
            if when == "always":
                do_reextract = True
            else:
                try:
                    sv = asset.get_raw_metadata()["schemaVersion"]
                except KeyError:
                    do_reextract = True
                else:
                    schemaVersion = Version(sv)
                    if schemaVersion < current_schema_version:
                        lgr.info(
                            "Asset's schemaVersion %r is out of date; will reextract",
                            sv,
                        )
                        do_reextract = True
                    elif schemaVersion == current_schema_version:
                        lgr.info(
                            "Asset's schemaVersion %r is up to date; not reextracting",
                            sv,
                        )
                        do_reextract = False
                    else:
                        lgr.warning(
                            "schemaVersion of asset %s (%s) is %r, higher than"
                            " current schema version %r",
                            asset.identifier,
                            asset.path,
                            sv,
                            DANDI_SCHEMA_VERSION,
                        )
                        do_reextract = False
            if do_reextract:
                try:
                    digest = asset.get_digest()
                except NotFoundError:
                    digest = None
                lgr.info("Extracting new metadata for asset")
                metadata = nwb2asset(asset.as_readable(), digest=digest)
                metadata.path = asset.path
                mddict = metadata.model_dump(mode="json", exclude_none=True)
                if diff:
                    oldmd = asset.get_raw_metadata()
                    oldmd_str = yaml_dump(oldmd)
                    mddict_str = yaml_dump(mddict)
                    print(
                        "".join(
                            unified_diff(
                                oldmd_str.splitlines(True),
                                mddict_str.splitlines(True),
                                fromfile=f"{asset.path}:old",
                                tofile=f"{asset.path}:new",
                            )
                        )
                    )
                lgr.info("Saving new asset metadata")
                asset.set_raw_metadata(mddict)


@service_scripts.command()
@instance_option()
@click.option(
    "--version-ref",
    metavar="DANDISET_VERSION_ID",
    required=True,
    help="ID of Dandiset/Version to operate on, ie DANDI:000005/0.250416.1418",
)
def publish_dandiset_version_doi(dandi_instance: str, version_ref: str) -> None:
    from dandischema.datacite import to_datacite

    if version_ref.startswith("DANDI:"):
        version_ref = version_ref[len("DANDI:") :]
    dandiset_id, dandiset_version_id = version_ref.split("/")

    with DandiAPIClient.for_dandi_instance(dandi_instance, authenticate=True) as client:
        ds = client.get_dandiset(dandiset_id, dandiset_version_id, lazy=False)
        version_metadata = ds.get_raw_metadata()

    username = os.environ["DJANGO_DANDI_DOI_API_USER"]
    password = os.environ["DJANGO_DANDI_DOI_API_PASSWORD"]
    base_url = os.environ["DJANGO_DANDI_DOI_API_URL"]

    if not (doi := version_metadata.get("doi")):
        print(json.dumps(version_metadata, indent=2))
        raise NotImplementedError("Need to mint DOI")
    if "10.80507" in doi and base_url == "https://api.datacite.org/dois":
        if "dandi.123456" in doi:
            raise ValueError(f"Hopeless case with fake DOI {doi}")
        # we used to try to mint using wrong DOI prefix, fix was in
        # https://github.com/dandi/dandi-schema/pull/65
        print("Round-tripping through JSON, fixing DOI")
        # round-trip through JSON to replace all such DOIs
        version_metadata = json.loads(
            json.dumps(version_metadata).replace("10.80507/", "10.48324/")
        )
        doi = version_metadata["doi"]
        # TODO: fix up in dandi-archive DB!?
    publish_str = os.environ.get("DJANGO_DANDI_DOI_PUBLISH", "False")
    publish = {"true": True, "false": False}.get(publish_str.lower(), False)
    doi_auth = HTTPBasicAuth(username, password)

    headers = {"accept": "application/vnd.api+json", "content-type": "application/json"}
    datacite_body = to_datacite(
        version_metadata,
        # validate=False,
        publish=publish,
    )
    with RESTFullAPIClient(base_url) as doiclient:
        try:
            doidata = doiclient.post(
                "", auth=doi_auth, headers=headers, json=datacite_body
            )
        except HTTPError as e:
            print("Failed to create DOI %s", doi)
            print("Datcite payload:")
            print(datacite_body)
            if e.response:
                print(e.response.text)
            raise

    encoded_doi = urllib.parse.quote(
        doidata["data"]["id"], safe=""
    )  # encode special chars
    verify_url = f"{DOI_HUMAN_URLS[base_url]}/{encoded_doi}"
    print(f"DOI successefully created, verify at {verify_url}")


@service_scripts.command()
@click.option(
    "-d",
    "--dandiset",
    metavar="DANDISET_ID",
    required=True,
    help="ID of Dandiset to operate on",
)
@click.option(
    "-e",
    "--existing",
    type=click.Choice(["ask", "overwrite", "skip"]),
    default="ask",
    help="Specify behavior when a value would be set on or added to the metadata",
    show_default=True,
)
@click.option(
    "-F",
    "--fields",
    type=ChoiceList(["contributor", "name", "description", "relatedResource"]),
    default="all",
    help="Comma-separated list of Dandiset metadata fields to update",
    show_default=True,
)
@instance_option()
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="Show final diff and save changes without prompting",
)
@click.argument("doi")
def update_dandiset_from_doi(
    dandiset: str,
    doi: str,
    dandi_instance: str,
    existing: str,
    fields: set[str],
    yes: bool,
) -> None:
    """
    Update the metadata for the draft version of a Dandiset with information
    from a given DOI record.

    DOI may be given bare (``10.48324/dandi.001827/0.260505.1322``), as a
    ``doi:`` URI, or as a resolver URL (``https://doi.org/...``).
    """
    try:
        doi = normalize_doi(doi)
    except ValueError as e:
        raise click.UsageError(str(e))

    known_instance_names = [k.upper() for k in known_instances.keys()]

    # Strip instance name prefix from dandiset ID, if present
    for name in known_instance_names:
        dandiset_id_prefix = f"{name}:"
        if dandiset.startswith(dandiset_id_prefix):
            dandiset = dandiset[len(dandiset_id_prefix) :]
            break

    start_time = datetime.now().astimezone()
    # Resolve the DOI before talking to the archive, so that a bad DOI fails
    # fast and without requiring credentials
    doidata = fetch_doi_citation_metadata(doi)
    with DandiAPIClient.for_dandi_instance(dandi_instance, authenticate=True) as client:
        d = client.get_dandiset(dandiset, "draft", lazy=False)
        original_metadata = d.get_raw_metadata()
        new_metadata = deepcopy(original_metadata)
        changed_fields = []

        if "contributor" in fields:
            changed = False
            for author in doidata["author"]:
                author_mut = author.copy()
                try:
                    given = author_mut.pop("given")
                except KeyError:
                    lgr.warning("Author %r in DOI lacks 'given' field", author)
                    continue
                try:
                    family = author_mut.pop("family")
                except KeyError:
                    lgr.warning("Author %r in DOI lacks 'family' field", author)
                    continue
                name = f"{family}, {given}"
                contrib = {
                    "name": name,
                    "roleName": ["dcite:Author"],
                    "schemaKey": "Person",
                    "includeInCitation": True,
                    "affiliation": [
                        {"name": affil} for affil in author_mut.pop("affiliation", [])
                    ],
                }
                if "ORCID" in author_mut:
                    contrib["identifier"] = author_mut.pop("ORCID").split("/")[-1]
                author_mut.pop("authenticated-orcid", None)
                author_mut.pop("sequence", None)
                for key, value in author_mut.items():
                    if value:
                        lgr.warning(
                            "DOI entry for author %r contained non-empty %r field: %r",
                            name,
                            key,
                            value,
                        )
                if add_dict_to_list_field(
                    new_metadata, "contributor", contrib, eq_authors, existing
                ):
                    changed = True

            if changed:
                changed_fields.append("contributor")

        if "name" in fields and copy_str_from_doi_to_metadata(
            doidata, new_metadata, "title", "name", existing
        ):
            changed_fields.append("name")

        if "description" in fields and copy_str_from_doi_to_metadata(
            doidata, new_metadata, "abstract", "description", existing
        ):
            changed_fields.append("description")

        if "relatedResource" in fields:
            new_record = {
                "identifier": doi,
                "name": doidata["title"],
                "relation": "dcite:IsDescribedBy",
                "schemaKey": "Resource",
                "url": f"https://doi.org/{doi}",
            }
            if add_dict_to_list_field(
                new_metadata,
                "relatedResource",
                new_record,
                eq_rel_resource,
                existing,
            ):
                changed_fields.append("relatedResource")

        if changed_fields:
            if new_metadata.get("wasGeneratedBy") is None:
                new_metadata["wasGeneratedBy"] = []
            assert isinstance(new_metadata["wasGeneratedBy"], list)
            new_metadata["wasGeneratedBy"].append(
                {
                    "id": str(uuid4().urn),
                    "name": "Metadata extraction from DOI",
                    "description": (
                        f"Metadata ({', '.join(changed_fields)}) was enhanced"
                        f" with data from DOI {doi} by DANDI cli"
                    ),
                    "schemaKey": "Activity",
                    "startDate": str(start_time),
                    "endDate": str(datetime.now().astimezone()),
                    "wasAssociatedWith": [
                        {
                            "identifier": "RRID:SCR_019009",
                            "name": "DANDI Command Line Interface",
                            "schemaKey": "Software",
                            "url": "https://github.com/dandi/dandi-cli",
                            "version": __version__,
                        }
                    ],
                }
            )
            if yes or click.confirm(
                "Show diff from old metadata to new?", default=True, prompt_suffix=" "
            ):
                oldmd = yaml_dump(original_metadata)
                newmd = yaml_dump(new_metadata)
                print(
                    "".join(
                        unified_diff(
                            oldmd.splitlines(True),
                            newmd.splitlines(True),
                            fromfile="dandiset.yaml:old",
                            tofile="dandiset.yaml:new",
                        )
                    )
                )
            if yes or click.confirm(
                "Save modified Dandiset metadata?", default=True, prompt_suffix=" "
            ):
                lgr.info("Saving ...")
                d.set_raw_metadata(new_metadata)
        else:
            lgr.info("No changes to Dandiset metadata")


def copy_str_from_doi_to_metadata(
    doidata: dict[str, Any],
    metadata: dict[str, Any],
    doi_key: str,
    metadata_key: str,
    existing: str,
) -> bool:
    newvalue = doidata.get(doi_key)
    if isinstance(newvalue, str):
        if metadata_key not in metadata:
            metadata[metadata_key] = newvalue
            lgr.info("Setting Dandiset %s to %r", metadata_key, newvalue)
            return True
        elif metadata[metadata_key] == newvalue:
            lgr.info("Dandiset %s already up to date", metadata_key)
            return False
        elif existing == "overwrite":
            metadata[metadata_key] = newvalue
            lgr.info("Setting Dandiset %s to %r", metadata_key, newvalue)
            return True
        elif existing == "skip":
            lgr.info("Dandiset %s differs from DOI; not updating", metadata_key)
            return False
        elif click.confirm(
            f"Set Dandiset {metadata_key} to {newvalue!r}?",
            default=True,
            prompt_suffix=" ",
        ):
            metadata[metadata_key] = newvalue
            lgr.info("Setting Dandiset %s", metadata_key)
            return True
        else:
            return False
    elif newvalue is not None:
        lgr.warning("Expected DOI %s to be string; got %r", doi_key, newvalue)
        return False
    else:
        lgr.warning(
            "DOI object does not have %s; cannot set Dandiset %s", doi_key, metadata_key
        )
        return False


def add_dict_to_list_field(
    metadata: dict[str, Any],
    key: str,
    newvalue: dict,
    eqtest: Callable[[T, T], bool],
    existing: str,
) -> bool:
    newvalue_yaml = indent(yaml_dump(newvalue), " " * 4)
    if metadata.get(key) is None:
        metadata[key] = []
    assert isinstance(metadata[key], list)
    matches = [item for item in metadata[key] if eqtest(newvalue, item)]  # type: ignore[arg-type]
    if matches:
        item = matches[0]
        item_yaml = indent(yaml_dump(item), " " * 4)
        if item == newvalue:
            lgr.info("Dandiset %s field already up to date", key)
            return False
        elif existing == "overwrite":
            lgr.info(
                "Adding new value to Dandiset %s field:\n\n%s\n", key, newvalue_yaml
            )
            lgr.info("Replacing:\n\n%s\n", item_yaml)
            item.clear()
            item.update(newvalue)
            return True
        elif existing == "skip":
            lgr.info(
                "Item in Dandiset %s not up to date; expected value:\n\n%s\n",
                key,
                newvalue_yaml,
            )
            lgr.info("Current value:\n\n%s\n", item_yaml)
            lgr.info("Not updating")
            return False
        else:
            lgr.info(
                "New value to add to Dandiset %s field:\n\n%s\n", key, newvalue_yaml
            )
            lgr.info("Replacing:\n\n%s\n", item_yaml)
            if click.confirm(
                f"Add value to Dandiset {key} field?", default=True, prompt_suffix=" "
            ):
                lgr.info("Adding value to Dandiset %s field", key)
                item.clear()
                item.update(newvalue)
                return True
            else:
                return False
    elif existing == "overwrite":
        lgr.info("Adding new value to Dandiset %s field:\n\n%s\n", key, newvalue_yaml)
        metadata[key].append(newvalue)
        return True
    elif existing == "skip":
        lgr.info("Item missing from Dandiset %s field:\n\n%s\n", key, newvalue_yaml)
        lgr.info("Not updating")
        return False
    else:
        lgr.info("New value to add to Dandiset %s field:\n\n%s\n", key, newvalue_yaml)
        if click.confirm(
            f"Add value to Dandiset {key} field?", default=True, prompt_suffix=" "
        ):
            lgr.info("Adding value to Dandiset %s field", key)
            metadata[key].append(newvalue)
            return True
        else:
            return False


def eq_rel_resource(r1: dict[str, Any], r2: dict[str, Any]) -> bool:
    return bool(r1["identifier"] == r2.get("identifier"))


def eq_authors(author1: dict[str, Any], author2: dict[str, Any]) -> bool:
    orcid = author1.get("identifier")
    if orcid is not None:
        return bool(orcid == author2.get("identifier"))
    else:
        return bool(author1["name"] == author2.get("name"))
