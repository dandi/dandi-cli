from __future__ import annotations

from pathlib import Path
from time import sleep

import click

from .base import instance_option, lgr, map_to_click_exceptions
from ..consts import dandiset_metadata_file
from ..dandiapi import DandiAPIClient, RemoteZarrAsset
from ..dandiset import Dandiset
from ..exceptions import NotFoundError


@click.group()
def service_scripts() -> None:
    """Various utility operations"""
    pass


@service_scripts.command()
@instance_option()
@click.argument("paths", nargs=-1)
@map_to_click_exceptions
def cancel_zarr_upload(paths: tuple[str, ...], dandi_instance: str) -> None:
    """
    Cancel an in-progress Zarr upload operation on the server.

    If a process uploading a Zarr is suddenly interrupted or killed, the server
    might not be properly notified.  If a later attempt is made to upload the
    same Zarr, the server will then report back that there is already an upload
    operation in progress and prohibit the new upload.  Use this command in
    such a case to tell the server to cancel the old upload operations for the
    Zarrs at the given path(s).
    """

    cwd = Path.cwd()
    dandiset = Dandiset.find(cwd)
    if dandiset is None:
        raise RuntimeError(
            f"Found no {dandiset_metadata_file} anywhere."
            "  Use 'dandi download' or 'organize' first"
        )
    pathbase = cwd.relative_to(dandiset.path)

    with DandiAPIClient.for_dandi_instance(dandi_instance, authenticate=True) as client:
        d = client.get_dandiset(dandiset.identifier)
        for p in paths:
            asset_path = (pathbase / p).as_posix()
            try:
                asset = d.get_asset_by_path(asset_path)
            except NotFoundError:
                lgr.warning("No such asset: %s", asset_path)
                continue
            if not isinstance(asset, RemoteZarrAsset):
                lgr.warning("Not a Zarr: %s", asset_path)
                continue
            r = client.get(f"/zarr/{asset.zarr}/")
            if not r["upload_in_progress"]:
                lgr.info("No upload in progress for Zarr at %s", asset_path)
                continue
            lgr.info("Cancelling in-progress upload for Zarr at %s ...", asset_path)
            client.delete(f"/zarr/{asset.zarr}/upload/")
            while True:
                sleep(0.5)
                r = client.get(f"/zarr/{asset.zarr}/")
                if not r["upload_in_progress"]:
                    lgr.info("Upload cancelled")
                    break
