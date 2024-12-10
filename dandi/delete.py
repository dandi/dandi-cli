from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from operator import attrgetter
from pathlib import Path

import click
from yarl import URL

from .consts import DRAFT, ZARR_EXTENSIONS, DandiInstance, dandiset_metadata_file
from .dandiapi import DandiAPIClient, RemoteAsset, RemoteDandiset
from .dandiarchive import BaseAssetIDURL, DandisetURL, ParsedDandiURL, parse_dandi_url
from .dandiset import Dandiset
from .exceptions import NotFoundError
from .support import pyout as pyouts
from .utils import get_instance, is_url


@dataclass
class Deleter:
    """
    Class for registering assets & Dandisets to delete and then deleting them
    """

    client: DandiAPIClient | None = None
    dandiset: RemoteDandiset | None = None
    #: Whether we are deleting an entire Dandiset (true) or just assets (false)
    deleting_dandiset: bool = False
    skip_missing: bool = False
    remote_assets: list[RemoteAsset] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.deleting_dandiset or bool(self.remote_assets)

    def set_dandiset(self, instance: DandiInstance, dandiset_id: str) -> bool:
        """
        Returns `False` if no action should be taken due to the Dandiset not
        existing
        """
        if self.client is None:
            self.client = DandiAPIClient.for_dandi_instance(instance, authenticate=True)
            try:
                self.dandiset = self.client.get_dandiset(dandiset_id, DRAFT, lazy=False)
            except NotFoundError:
                if self.skip_missing:
                    return False
                else:
                    raise
        elif not is_same_url(self.client.api_url, instance.api):
            raise ValueError("Cannot delete assets from multiple API instances at once")
        else:
            assert self.dandiset is not None
            if self.dandiset.identifier != dandiset_id:
                raise ValueError("Cannot delete assets from multiple Dandisets at once")
        return True

    def add_asset(self, asset: RemoteAsset) -> None:
        # Ensure the list is free of duplicates so that we don't try to delete
        # the same asset twice
        if not any(a.identifier == asset.identifier for a in self.remote_assets):
            self.remote_assets.append(asset)

    def register_dandiset(self, instance: DandiInstance, dandiset_id: str) -> None:
        if not self.set_dandiset(instance, dandiset_id):
            return
        self.deleting_dandiset = True

    def register_asset(
        self,
        instance: DandiInstance,
        dandiset_id: str,
        version_id: str,
        asset_path: str,
    ) -> None:
        if not self.set_dandiset(instance, dandiset_id):
            return
        assert self.dandiset is not None
        try:
            asset = self.dandiset.get_asset_by_path(asset_path)
        except NotFoundError:
            if self.skip_missing:
                return
            else:
                raise NotFoundError(
                    f"Asset at path {asset_path!r} not found in Dandiset {dandiset_id}"
                )
        self.add_asset(asset)

    def register_asset_folder(
        self,
        instance: DandiInstance,
        dandiset_id: str,
        version_id: str,
        folder_path: str,
    ) -> None:
        if not self.set_dandiset(instance, dandiset_id):
            return
        any_assets = False
        assert self.dandiset is not None
        for asset in self.dandiset.get_assets_with_path_prefix(folder_path):
            self.add_asset(asset)
            any_assets = True
        if not any_assets and not self.skip_missing:
            raise NotFoundError(
                f"No assets under path {folder_path!r} found in Dandiset {dandiset_id}"
            )

    def register_assets_url(self, url: str, parsed_url: ParsedDandiURL) -> None:
        if isinstance(parsed_url, BaseAssetIDURL):
            raise ValueError("Cannot delete an asset identified by just an ID")
        assert parsed_url.dandiset_id is not None
        if not self.set_dandiset(parsed_url.instance, parsed_url.dandiset_id):
            return
        any_assets = False
        assert self.client is not None
        for a in parsed_url.get_assets(self.client):
            assert isinstance(a, RemoteAsset)
            self.add_asset(a)
            any_assets = True
        if not any_assets and not self.skip_missing:
            raise NotFoundError(f"No assets found for {url}")

    def register_url(self, url: str) -> None:
        parsed_url = parse_dandi_url(url)
        if isinstance(parsed_url, DandisetURL):
            if parsed_url.version_id is not None:
                raise NotImplementedError(
                    "DANDI API server does not support deletion of individual"
                    " versions of a dandiset"
                )
            assert parsed_url.dandiset_id is not None
            self.register_dandiset(parsed_url.instance, parsed_url.dandiset_id)
        else:
            if parsed_url.version_id is None:
                parsed_url.version_id = DRAFT
            self.register_assets_url(url, parsed_url)

    def register_local_path_equivalent(
        self, instance_name: str | DandiInstance, filepath: str
    ) -> None:
        instance = get_instance(instance_name)
        dandiset_id, asset_path = find_local_asset(filepath)
        if not self.set_dandiset(instance, dandiset_id):
            return
        if asset_path.endswith("/"):
            self.register_asset_folder(instance, dandiset_id, DRAFT, asset_path)
        else:
            self.register_asset(instance, dandiset_id, DRAFT, asset_path)

    def confirm(self) -> bool:
        if self.dandiset is None:
            raise ValueError("confirm() called before registering anything to delete")
        if self.deleting_dandiset:
            msg = f"Delete Dandiset {self.dandiset.identifier}?"
        else:
            msg = (
                f"Delete {len(self.remote_assets)} assets on server from"
                f" Dandiset {self.dandiset.identifier}?"
            )
        return click.confirm(msg)

    def delete_dandiset(self) -> None:
        if self.deleting_dandiset:
            assert self.dandiset is not None
            self.dandiset.delete()
        else:
            raise RuntimeError(
                "delete_dandiset() called when Dandiset not registered for deletion"
            )

    def _process_asset(self, asset: RemoteAsset) -> Iterator[dict]:
        yield {"status": "Deleting"}
        try:
            asset.delete()
        except Exception as e:
            yield {"status": "Error", "message": f"{type(e).__name__}: {e}"}
        else:
            yield {"status": "Deleted"}

    def process_assets_pyout(self) -> Iterator[dict]:
        for asset in sorted(self.remote_assets, key=attrgetter("path")):
            yield {
                "path": asset.path,
                ("status", "message"): self._process_asset(asset),
            }

    def process_assets_debug(self) -> Iterator[Iterator[dict]]:
        for asset in sorted(self.remote_assets, key=attrgetter("path")):
            yield ({"path": asset.path, **d} for d in self._process_asset(asset))


def delete(
    paths: Iterable[str],
    dandi_instance: str | DandiInstance = "dandi",
    devel_debug: bool = False,
    jobs: int | None = None,
    force: bool = False,
    skip_missing: bool = False,
) -> None:
    """Delete dandisets and assets from the server.

    PATH could be a local path or a URL to an asset, directory, or an entire
    dandiset.
    """
    deleter = Deleter(skip_missing=skip_missing)
    for p in paths:
        if is_url(p):
            deleter.register_url(p)
        else:
            deleter.register_local_path_equivalent(dandi_instance, p)
    if deleter and (force or deleter.confirm()):
        if deleter.deleting_dandiset:
            deleter.delete_dandiset()
        elif devel_debug:
            for gen in deleter.process_assets_debug():
                for r in gen:
                    print(r, flush=True)
        else:
            pyout_style = pyouts.get_style(hide_if_missing=False)
            rec_fields = ("path", "status", "message")
            out = pyouts.LogSafeTabular(
                style=pyout_style, columns=rec_fields, max_workers=jobs
            )
            with out:
                for r in deleter.process_assets_pyout():
                    out(r)


def find_local_asset(filepath: str) -> tuple[str, str]:
    """
    Given a path to a local file, return the ID of the Dandiset in which it is
    located and the path to the file relative to the root of said Dandiset.  If
    the file is a directory, the path will end with a trailing slash.
    """
    path = Path(filepath).absolute()
    dandiset = Dandiset.find(path.parent)
    if dandiset is None:
        raise RuntimeError(
            f"Found no {dandiset_metadata_file} anywhere.  "
            "Use 'dandi download' or 'organize' first"
        )
    relpath = path.relative_to(dandiset.path).as_posix()
    if path.is_dir() and path.suffix not in ZARR_EXTENSIONS:
        relpath += "/"
    return (dandiset.identifier, relpath)


def is_same_url(url1: str, url2: str) -> bool:
    u1 = URL(url1)
    u1 = u1.with_path(u1.path.rstrip("/"))
    u2 = URL(url2)
    u2 = u2.with_path(u2.path.rstrip("/"))
    return u1 == u2
