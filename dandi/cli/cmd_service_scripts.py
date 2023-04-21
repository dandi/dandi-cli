from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from difflib import unified_diff
from pathlib import PurePosixPath
from typing import Any, TypeVar
from uuid import uuid4

import click
from dandischema.consts import DANDI_SCHEMA_VERSION
from packaging.version import Version

from .base import ChoiceList, map_to_click_exceptions
from .. import __version__, lgr
from ..dandiapi import DandiAPIClient, RemoteBlobAsset, RESTFullAPIClient
from ..dandiarchive import parse_dandi_url
from ..exceptions import NotFoundError
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
    from ..metadata import nwb2asset  # Avoid heavy import at top level

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
                mddict = metadata.json_dict()
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
@click.option("-d", "--dandiset", metavar="DANDISET_ID", required=True)
@click.option(
    "--existing",
    type=click.Choice(["ask", "overwrite", "skip"]),
    default="ask",
    show_default=True,
)
@click.option(
    "--fields",
    type=ChoiceList(["contributor", "name", "description", "relatedResource"]),
    default="all",
    show_default=True,
)
def update_dandiset_from_doi(dandiset: str, existing: str, fields: set[str]) -> None:
    if dandiset.startswith("DANDI:"):
        dandiset = dandiset[6:]
    start_time = datetime.now().astimezone()
    with DandiAPIClient.for_dandi_instance("dandi", authenticate=True) as client:
        dpublished = client.get_dandiset(dandiset, lazy=False)
        if dpublished.version_id == "draft":
            raise click.UsageError(f"Dandiset {dandiset} has no published versions.")
        published_metadata = dpublished.get_raw_metadata()
        doi = published_metadata.get("doi")
        if not isinstance(doi, str):
            raise click.UsageError(f"{dpublished} does not have a DOI.")

        with RESTFullAPIClient(
            "https://doi.org/",
            headers={
                "Accept": "application/vnd.citationstyles.csl+json; charset=utf-8"
            },
        ) as doiclient:
            doidata = doiclient.get(doi)

        ddraft = dpublished.for_version("draft")
        original_metadata = ddraft.get_raw_metadata()
        new_metadata = deepcopy(original_metadata)
        changed_fields = []

        if "contributor" in fields:
            changed = False
            for author in doidata["author"]:
                contrib = {
                    "name": f"{author['family']}, {author['given']}",
                    "roleName": ["dcite:Author"],
                    ### TODO: If corresponding author of the paper, add
                    ### dcite:ContactPerson
                    "schemaKey": "Person",
                    "includeInCitation": True,
                }
                if "ORCID" in author:
                    contrib["identifier"] = author["ORCID"].split(r"\/")[-1]
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

        if changed:
            if new_metadata.get("wasGeneratedBy") is None:
                new_metadata["wasGeneratedBy"] = []
            assert isinstance(new_metadata["wasGeneratedBy"], list)
            new_metadata["wasGeneratedBy"].append(
                {
                    "id": str(uuid4().urn),
                    "name": "Metadata extraction from DOI",
                    "description": (
                        f"Metadata ({', '.join(changed_fields)}) was enhanced"
                        " with data from DOI {doi} by DANDI cli"
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
            if click.confirm(
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
            if click.confirm(
                "Save modified Dandiset metadata?", default=True, prompt_suffix=" "
            ):
                lgr.info("Saving ...")
                ddraft.set_raw_metadata(new_metadata)
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
    if metadata.get(key) is None:
        metadata[key] = []
    assert isinstance(metadata[key], list)

    matches = [item for item in metadata[key] if eqtest(newvalue, item)]  # type: ignore[arg-type]
    if matches:
        item = matches[0]
        if item == newvalue:
            lgr.info("Dandiset %s already up to date", key)
            return False

        ### TODO: Improve the log messages in this section:
        elif existing == "overwrite":
            item.clear()
            item.update(newvalue)
            lgr.info("Adding %r to Dandiset %s", newvalue, key)
            return True
        elif existing == "skip":
            lgr.info("Item %r missing from Dandiset %s; not updating", newvalue, key)
            return False
        elif click.confirm(
            f"Add {newvalue!r} to Dandiset {key}?", default=True, prompt_suffix=" "
        ):
            item.clear()
            item.update(newvalue)
            lgr.info("Adding value to Dandiset %s", key)
            return True
        else:
            return False

    elif existing == "overwrite":
        metadata[key].append(newvalue)
        lgr.info("Adding %r to Dandiset %s", newvalue, key)
        return True
    elif existing == "skip":
        lgr.info("Item %r missing from Dandiset %s; not updating", newvalue, key)
        return False
    elif click.confirm(
        f"Add {newvalue!r} to Dandiset {key}?", default=True, prompt_suffix=" "
    ):
        metadata[key].append(newvalue)
        lgr.info("Adding value to Dandiset %s", key)
        return True
    else:
        return False


def eq_rel_resource(r1: dict[str, Any], r2: dict[str, Any]) -> bool:
    return bool(r1["identifier"] == r2["identifier"])


def eq_authors(author1: dict[str, Any], author2: dict[str, Any]) -> bool:
    orcid = author1.get("identifier")
    if orcid is not None:
        return bool(orcid == author2.get("identifier"))
    else:
        return bool(author1["name"] == author2["name"])
