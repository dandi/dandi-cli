from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from difflib import unified_diff
import os
from pathlib import PurePosixPath
from textwrap import indent
from typing import Any, TypeVar
import urllib.parse
from uuid import uuid4

import click
from dandischema.consts import DANDI_SCHEMA_VERSION
from packaging.version import Version
from requests.auth import HTTPBasicAuth

from .base import ChoiceList, instance_option, map_to_click_exceptions
from .. import __version__, lgr
from ..dandiapi import DandiAPIClient, RemoteBlobAsset, RESTFullAPIClient
from ..dandiarchive import parse_dandi_url
from ..exceptions import HTTP404Error, NotFoundError
from ..utils import yaml_dump

T = TypeVar("T")


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


# TODO REMOVE JUST REFERENCE
# -------------------DANDI-ARCHIVE ---------------------------------
# def _generate_doi_data(version: Version):
#     from dandischema.datacite import to_datacite
#
#     publish = settings.DANDI_DOI_PUBLISH
#     # Use the DANDI test datacite instance as a placeholder if PREFIX isn't set
#     prefix = settings.DANDI_DOI_API_PREFIX or "10.80507"
#     dandiset_id = version.dandiset.identifier
#     version_id = version.version
#     doi = f"{prefix}/dandi.{dandiset_id}/{version_id}"
#     metadata = version.metadata
#     metadata["doi"] = doi
#     return (doi, to_datacite(metadata, publish=publish))
#
#
# def create_doi(version: Version) -> str:
#     doi, request_body = _generate_doi_data(version)
#     # If DOI isn't configured, skip the API call
#     if doi_configured():
#         try:
#             requests.post(
#                 settings.DANDI_DOI_API_URL,
#                 json=request_body,
#                 auth=requests.auth.HTTPBasicAuth(
#                     settings.DANDI_DOI_API_USER,
#                     settings.DANDI_DOI_API_PASSWORD,
#                 ),
#                 timeout=30,
#             ).raise_for_status()
#         except requests.exceptions.HTTPError as e:
#             logger.exception("Failed to create DOI %s", doi)
#             logger.exception(request_body)
#             if e.response:
#                 logger.exception(e.response.text)
#             raise
#     return doi
#
#
# -------------------DANDI-ARCHIVE ---------------------------------


@service_scripts.command()
@instance_option()
@click.option(
    "-d",
    "--dandiset",
    metavar="DANDISET_ID",
    required=True,
    help="ID of Dandiset to operate on",
)
@click.option(
    "--dandiset-version",
    metavar="DANDISET_VERSION_ID",
    required=True,
    help="ID of Dandiset Version to operate on",
)
def publish_dandiset_version_doi(dandi_instance, dandiset, dandiset_version) -> None:
    with DandiAPIClient.for_dandi_instance(dandi_instance, authenticate=True) as client:
        ds = client.get_dandiset(dandiset, dandiset_version, lazy=False)
        version_metadata = ds.get_raw_metadata()

    # TODO(asmacdo) verify actually published, and doi exists
    doi = version_metadata["doi"]
    username = os.environ["DJANGO_DANDI_DOI_API_USER"]
    password = os.environ["DJANGO_DANDI_DOI_API_PASSWORD"]
    base_url = os.environ["DJANGO_DANDI_DOI_API_URL"]
    doi_auth = HTTPBasicAuth(username, password)
    # TODO(asmacdo) as-is works, but lets make sure the headers are correct
    # Expected: `Content-Type: application/vnd.api+json`
    with RESTFullAPIClient(base_url) as doiclient:
        try:
            doidata = doiclient.get(doi, auth=doi_auth)
        except HTTP404Error as e:
            print(f"DOI does not exist {e}")
            doidata = None

        if doidata is None:
            print("Creating DOI...")
            from dandischema.datacite import to_datacite

            datacite_body = to_datacite(version_metadata, publish=False)
            try:
                doidata = doiclient.post("", auth=doi_auth, json=datacite_body)
                encoded_doi = urllib.parse.quote(
                    doidata["data"]["id"], safe=""
                )  # encode special chars
                # TODO(asmacdo) Dont hardcode base of verify url
                #  - this is not included in the API response
                #  - but its either doi.test.datacite.org or doi.datacite.org
                #     - could be determined which one from DJANGO_DANDI_API_URL and some constants
                verify_url = f"https://doi.test.datacite.org/dois/{encoded_doi}"
                print(f"DOI successefully created, verify at {verify_url}")
            except Exception as e:
                import ipdb

                ipdb.set_trace()
                print(e)

                ipdb.set_trace()
                # TODO(asmacdo)
                print("TODO CATCH ME")
                # What exceptions? (possible responses not listed on API Reference)
                # Maybe just all ie, except requests.exceptions.HTTPError as e:
                # Exceptions seen:
                #  - 404 (when using invalid creds or invalid url)
                #  - 403 (at least caused by a DOI prefix we dont have access to)
                #  - 422
                #    - "title": "param is missing or the value is empty: attributes"
                #    - Response JSON: {'errors': [{'source': 'doi', 'title': 'This DOI has already been taken', 'uid': '10.80507/asmacdo-draft-doi-test'}]}  # noqa
                #    - For Draft, less stringent. For event=publish Response JSON: {'errors': [{'source': 'url', 'title': "Can't be blank", 'uid': '10.80507/asmacdo-draft-doi-test3'}, {'source': 'xml', 'title': "Can't be blank", 'uid': '10.80507/asmacdo-draft-doi-test3'}]}  # noqa
                print("TODO Output errors")

        # TODO(asmacdo) does "state" always exist when draft?
        doi_state = doidata["data"]["attributes"]["state"]
        if doi_state == "findable":
            print("NOOP, DOI already Findable")
        elif doi_state == "registered":
            print("TODO? Republish DOI?")
        elif doi_state == "draft":
            # TODO(asmacdo) DJANGO_DANDI_DOI_PUBLISH env var could be used to disable publishing
            print("DOI is draft, publishing to 'findable'...")
            # TODO(asmacdo) re-enable, avoiding unnecessary proliferation so disabled for now
            # Tested once, produced
            #    https://doi.test.datacite.org/dois/10.80507%2Fdandi.000004%2F0.250416.1347
            # publish_update_body = {
            #   "data": {
            #     "type": "dois",
            #     "attributes": {
            #       "event": "publish"
            #     }
            #   }
            # }
            # TODO(asmacdo) catch and output errors
            # doidata = doiclient.put(doi, auth=doi_auth, json=publish_update_body)
            # print(doidata)
            print("SKIPPING PUBLISH FOR DEVELOPMENT")


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
    """
    if dandiset.startswith("DANDI:"):
        dandiset = dandiset[6:]
    start_time = datetime.now().astimezone()
    with DandiAPIClient.for_dandi_instance(dandi_instance, authenticate=True) as client:
        with RESTFullAPIClient(
            "https://doi.org/",
            headers={
                "Accept": "application/vnd.citationstyles.csl+json; charset=utf-8"
            },
        ) as doiclient:
            doidata = doiclient.get(doi)

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
