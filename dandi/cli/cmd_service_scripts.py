from difflib import unified_diff
from pathlib import PurePosixPath

import click
from dandischema.consts import DANDI_SCHEMA_VERSION
from packaging.version import Version

from .base import map_to_click_exceptions
from .. import lgr
from ..dandiapi import RemoteBlobAsset
from ..dandiarchive import parse_dandi_url
from ..exceptions import NotFoundError
from ..utils import yaml_dump


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
