from dataclasses import dataclass, field
from operator import attrgetter
from pathlib import Path, PurePosixPath
from typing import Iterable, Iterator, NamedTuple, Optional, Set, Tuple

import click
import requests

from .consts import dandiset_metadata_file
from .dandiapi import DandiAPIClient
from .dandiarchive import parse_dandi_url
from .exceptions import NotFoundError
from .utils import get_instance, is_url


class RemoteAsset(NamedTuple):
    dandiset_id: str
    version_id: str
    asset_id: str
    path: str


@dataclass
class Deleter:
    """
    Class for registering assets & Dandisets to delete and then deleting them
    """

    client: Optional[DandiAPIClient] = None
    dandiset_id: Optional[str] = None
    #: Whether we are deleting an entire Dandiset (true) or just assets (false)
    deleting_dandiset: bool = False
    remote_assets: Set[RemoteAsset] = field(default_factory=set)

    def __bool__(self) -> bool:
        return self.deleting_dandiset or bool(self.remote_assets)

    def set_dandiset(self, api_url: str, dandiset_id: str) -> None:
        if self.client is None:
            # Strip the trailing slash so that dandi_authenticate can find the
            # URL in known_instances_rev:
            self.client = DandiAPIClient(api_url.rstrip("/"))
            self.client.dandi_authenticate()
            self.dandiset_id = dandiset_id
            try:
                self.client.get_dandiset(dandiset_id, "draft")
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    raise NotFoundError(f"Dandiset {dandiset_id} not found on server")
                else:
                    raise
        elif not is_same_url(self.client.api_url, api_url):
            raise ValueError("Cannot delete assets from multiple API instances at once")
        elif self.dandiset_id != dandiset_id:
            raise ValueError("Cannot delete assets from multiple Dandisets at once")

    def register_dandiset(self, api_url: str, dandiset_id: str) -> None:
        self.set_dandiset(api_url, dandiset_id)
        self.deleting_dandiset = True

    def register_asset(
        self, api_url: str, dandiset_id: str, version_id: str, asset_path: str
    ) -> None:
        self.set_dandiset(api_url, dandiset_id)
        asset = self.client.get_asset_bypath(dandiset_id, version_id, asset_path)
        if asset is None:
            raise NotFoundError(
                f"Asset at path {asset_path!r} not found in Dandiset {dandiset_id}"
            )
        self.remote_assets.add(
            RemoteAsset(dandiset_id, version_id, asset["asset_id"], asset["path"])
        )

    def register_asset_folder(
        self, api_url: str, dandiset_id: str, version_id: str, folder_path: str
    ) -> None:
        self.set_dandiset(api_url, dandiset_id)
        any_assets = False
        for asset in self.client.get_dandiset_assets(
            dandiset_id, version_id, path=folder_path
        ):
            self.remote_assets.add(
                RemoteAsset(dandiset_id, version_id, asset["asset_id"], asset["path"])
            )
            any_assets = True
        if not any_assets:
            raise NotFoundError(
                f"No assets under path {folder_path!r} found in Dandiset {dandiset_id}"
            )

    def register_url(self, url: str) -> None:
        server_type, server_url, asset_type, asset_id = parse_dandi_url(url)
        if asset_type == "dandiset":
            if asset_id.get("version") is not None:
                raise NotImplementedError(
                    "Dandi API server does not support deletion of individual"
                    " versions of a dandiset"
                )
            self.register_dandiset(server_url, asset_id["dandiset_id"])
        elif asset_type == "item":
            self.register_asset(
                server_url,
                asset_id["dandiset_id"],
                asset_id.get("version") or "draft",
                asset_id["location"],
            )
        elif asset_type == "folder":
            self.register_asset_folder(
                server_url,
                asset_id["dandiset_id"],
                asset_id.get("version") or "draft",
                asset_id["location"],
            )
        else:
            raise RuntimeError(f"Unexpected asset type for {url}: {asset_type}")

    def register_local_path_equivalent(self, instance_name: str, filepath: str) -> None:
        instance = get_instance(instance_name)
        if instance.girder is not None:
            raise NotImplementedError("Cannot delete assets from Girder instances")
        api_url = instance.api
        dandiset_id, asset_path = find_local_asset(filepath)
        self.set_dandiset(api_url, dandiset_id)
        if asset_path.endswith("/"):
            self.register_asset_folder(api_url, dandiset_id, "draft", asset_path)
        else:
            self.register_asset(api_url, dandiset_id, "draft", asset_path)

    def confirm(self) -> bool:
        if self.deleting_dandiset:
            msg = f"Delete Dandiset {self.dandiset_id}?"
        else:
            msg = (
                f"Delete {len(self.remote_assets)} assets on server from"
                f" Dandiset {self.dandiset_id}?"
            )
        return click.confirm(msg)

    def delete_dandiset(self) -> None:
        if self.deleting_dandiset:
            self.client.delete_dandiset(self.dandiset_id)
        else:
            raise RuntimeError(
                "delete_dandiset() called when Dandiset not registered for deletion"
            )

    def _process_asset(self, asset: RemoteAsset) -> Iterator[dict]:
        yield {"status": "Deleting"}
        try:
            self.client.delete_asset(
                asset.dandiset_id, asset.version_id, asset.asset_id
            )
        except Exception as e:
            yield {"status": "Error", "message": f"{type(e).__name__}: {e}"}
        else:
            yield {"status": "Deleted"}

    def process_assets_pyout(self) -> Iterator[dict]:
        with self.client.session():
            for asset in sorted(self.remote_assets, key=attrgetter("path")):
                yield {
                    "path": asset.path,
                    ("status", "message"): self._process_asset(asset),
                }

    def process_assets_debug(self) -> Iterator[Iterator[dict]]:
        with self.client.session():
            for asset in sorted(self.remote_assets, key=attrgetter("path")):
                yield ({"path": asset.path, **d} for d in self._process_asset(asset))


def delete(
    paths: Iterable[str],
    dandi_instance: str = "dandi",
    devel_debug: bool = False,
    jobs: Optional[int] = None,
    force: bool = False,
) -> None:
    deleter = Deleter()
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
                for gen in deleter.process_assets_pyout():
                    out(gen)


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
            "Use 'dandi register', 'download', or 'organize' first"
        )
    relpath = str(PurePosixPath(path.relative_to(dandiset.path)))
    if path.is_dir():
        relpath += "/"
    return (dandiset.identifier, relpath)


def is_same_url(url1: str, url2: str) -> bool:
    # TODO: Use a real URL library like furl, purl, or yarl
    return url1.rstrip("/") == url2.rstrip("/")
