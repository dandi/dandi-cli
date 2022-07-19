from dataclasses import dataclass, field
from operator import attrgetter
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Tuple

import click

from .consts import DRAFT, ZARR_EXTENSIONS, dandiset_metadata_file
from .dandiapi import DandiAPIClient, RemoteAsset, RemoteDandiset
from .dandiarchive import BaseAssetIDURL, DandisetURL, ParsedDandiURL, parse_dandi_url
from .exceptions import NotFoundError
from .utils import get_instance, is_url


@dataclass
class Deleter:
    """
    Class for registering assets & Dandisets to delete and then deleting them
    """

    client: Optional[DandiAPIClient] = None
    dandiset: Optional[RemoteDandiset] = None
    #: Whether we are deleting an entire Dandiset (true) or just assets (false)
    deleting_dandiset: bool = False
    skip_missing: bool = False
    remote_assets: List[RemoteAsset] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.deleting_dandiset or bool(self.remote_assets)

    def set_dandiset(self, api_url: str, dandiset_id: str) -> bool:
        """
        Returns `False` if no action should be taken due to the Dandiset not
        existing
        """
        if self.client is None:
            # Strip the trailing slash so that dandi_authenticate can find the
            # URL in known_instances_rev:
            self.client = DandiAPIClient(api_url.rstrip("/"))
            self.client.dandi_authenticate()
            try:
                self.dandiset = self.client.get_dandiset(dandiset_id, DRAFT, lazy=False)
            except NotFoundError:
                if self.skip_missing:
                    return False
                else:
                    raise
        elif not is_same_url(self.client.api_url, api_url):
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

    def register_dandiset(self, api_url: str, dandiset_id: str) -> None:
        if not self.set_dandiset(api_url, dandiset_id):
            return
        self.deleting_dandiset = True

    def register_asset(
        self, api_url: str, dandiset_id: str, version_id: str, asset_path: str
    ) -> None:
        if not self.set_dandiset(api_url, dandiset_id):
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
        self, api_url: str, dandiset_id: str, version_id: str, folder_path: str
    ) -> None:
        if not self.set_dandiset(api_url, dandiset_id):
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
        if not self.set_dandiset(parsed_url.api_url, parsed_url.dandiset_id):
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
                    "Dandi API server does not support deletion of individual"
                    " versions of a dandiset"
                )
            assert parsed_url.dandiset_id is not None
            self.register_dandiset(parsed_url.api_url, parsed_url.dandiset_id)
        else:
            if parsed_url.version_id is None:
                parsed_url.version_id = DRAFT
            self.register_assets_url(url, parsed_url)

    def register_local_path_equivalent(self, instance_name: str, filepath: str) -> None:
        instance = get_instance(instance_name)
        api_url = instance.api
        assert api_url is not None
        dandiset_id, asset_path = find_local_asset(filepath)
        if not self.set_dandiset(api_url, dandiset_id):
            return
        if asset_path.endswith("/"):
            self.register_asset_folder(api_url, dandiset_id, DRAFT, asset_path)
        else:
            self.register_asset(api_url, dandiset_id, DRAFT, asset_path)

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
    dandi_instance: str = "dandi",
    devel_debug: bool = False,
    jobs: Optional[int] = None,
    force: bool = False,
    skip_missing: bool = False,
) -> None:
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
            from .support import pyout as pyouts

            pyout_style = pyouts.get_style(hide_if_missing=False)
            rec_fields = ("path", "status", "message")
            out = pyouts.LogSafeTabular(
                style=pyout_style, columns=rec_fields, max_workers=jobs
            )
            with out:
                for r in deleter.process_assets_pyout():
                    out(r)


def find_local_asset(filepath: str) -> Tuple[str, str]:
    """
    Given a path to a local file, return the ID of the Dandiset in which it is
    located and the path to the file relative to the root of said Dandiset.  If
    the file is a directory, the path will end with a trailing slash.
    """
    from .dandiset import Dandiset

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
    # TODO: Use a real URL library like furl, purl, or yarl
    return url1.rstrip("/") == url2.rstrip("/")
