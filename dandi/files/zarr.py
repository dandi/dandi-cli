from __future__ import annotations

import atexit
from collections.abc import Generator, Iterator
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import closing
from dataclasses import dataclass, field, replace
from datetime import datetime
import os
from pathlib import Path
from time import sleep
from typing import Any, Optional, cast

from dandischema.digests.zarr import get_checksum
from dandischema.models import BareAsset, DigestType
import requests
import zarr

from dandi import get_logger
from dandi.consts import (
    MAX_ZARR_DEPTH,
    ZARR_MIME_TYPE,
    ZARR_UPLOAD_BATCH_SIZE,
    EmbargoStatus,
)
from dandi.dandiapi import (
    RemoteAsset,
    RemoteDandiset,
    RemoteZarrAsset,
    RemoteZarrEntry,
    RESTFullAPIClient,
)
from dandi.metadata import get_default_metadata
from dandi.misctypes import BasePath, Digest
from dandi.support.digests import get_digest, get_zarr_checksum, md5file_nocache
from dandi.utils import chunked, pluralize

from .bases import LocalDirectoryAsset

lgr = get_logger()


@dataclass
class LocalZarrEntry(BasePath):
    """A file or directory within a `ZarrAsset`"""

    #: The path to the actual file or directory on disk
    filepath: Path
    #: The path to the root of the Zarr file tree
    zarr_basepath: Path

    def _get_subpath(self, name: str) -> LocalZarrEntry:
        if not name or "/" in name:
            raise ValueError(f"Invalid path component: {name!r}")
        elif name == ".":
            return self
        elif name == "..":
            return self.parent
        else:
            return replace(
                self, filepath=self.filepath / name, parts=self.parts + (name,)
            )

    @property
    def parent(self) -> LocalZarrEntry:
        if self.is_root():
            return self
        else:
            return replace(self, filepath=self.filepath.parent, parts=self.parts[:-1])

    def exists(self) -> bool:
        return self.filepath.exists()

    def is_file(self) -> bool:
        return self.filepath.is_file()

    def is_dir(self) -> bool:
        return self.filepath.is_dir()

    def iterdir(self) -> Iterator[LocalZarrEntry]:
        for p in self.filepath.iterdir():
            if p.is_dir() and not any(p.iterdir()):
                # Ignore empty directories
                continue
            yield self._get_subpath(p.name)

    def get_digest(self) -> Digest:
        """
        Calculate the DANDI etag digest for the entry.  If the entry is a
        directory, the algorithm will be the Dandi Zarr checksum algorithm; if
        it is a file, it will be MD5.
        """
        if self.is_dir():
            return Digest.dandi_zarr(get_zarr_checksum(self.filepath))
        else:
            return Digest(
                algorithm=DigestType.md5, value=get_digest(self.filepath, "md5")
            )

    @property
    def size(self) -> int:
        """
        The size of the entry.  For a directory, this is the total size of all
        entries within it.
        """
        if self.is_dir():
            return sum(p.size for p in self.iterdir())
        else:
            return os.path.getsize(self.filepath)

    @property
    def modified(self) -> datetime:
        """The time at which the entry was last modified"""
        # TODO: Should this be overridden for directories?
        return datetime.fromtimestamp(self.filepath.stat().st_mtime).astimezone()


@dataclass
class ZarrStat:
    """Details about a Zarr asset"""

    #: The total size of the asset
    size: int
    #: The Dandi Zarr checksum of the asset
    digest: Digest
    #: A list of all files in the asset in unspecified order
    files: list[LocalZarrEntry]


class ZarrAsset(LocalDirectoryAsset[LocalZarrEntry]):
    """Representation of a local Zarr directory"""

    @property
    def filetree(self) -> LocalZarrEntry:
        """
        The `LocalZarrEntry` for the root of the hierarchy of files within the
        Zarr asset
        """
        return LocalZarrEntry(
            filepath=self.filepath, zarr_basepath=self.filepath, parts=()
        )

    def stat(self) -> ZarrStat:
        """Return various details about the Zarr asset"""

        def dirstat(dirpath: LocalZarrEntry) -> ZarrStat:
            size = 0
            dir_md5s = {}
            file_md5s = {}
            files = []
            for p in dirpath.iterdir():
                if p.is_dir():
                    st = dirstat(p)
                    size += st.size
                    dir_md5s[p.name] = (st.digest.value, st.size)
                    files.extend(st.files)
                else:
                    size += p.size
                    file_md5s[p.name] = (md5file_nocache(p.filepath), p.size)
                    files.append(p)
            return ZarrStat(
                size=size,
                digest=Digest.dandi_zarr(get_checksum(file_md5s, dir_md5s)),
                files=files,
            )

        return dirstat(self.filetree)

    def get_digest(self) -> Digest:
        """Calculate a dandi-zarr-checksum digest for the asset"""
        return Digest.dandi_zarr(get_zarr_checksum(self.filepath))

    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        metadata = get_default_metadata(self.filepath, digest=digest)
        metadata.encodingFormat = ZARR_MIME_TYPE
        metadata.path = self.path
        return metadata

    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> list[str]:
        try:
            data = zarr.open(self.filepath)
        except Exception as e:
            if devel_debug:
                raise
            lgr.warning(
                "Error opening %s: %s: %s",
                self.filepath,
                type(e).__name__,
                e,
                extra={"validating": True},
            )
            return [str(e)]
        if isinstance(data, zarr.Group) and not data:
            msg = "Zarr group is empty"
            if devel_debug:
                raise ValueError(msg)
            lgr.warning("%s: %s", self.filepath, msg, extra={"validating": True})
            return [msg]
        try:
            next(self.filepath.glob(f"*{os.sep}" + os.sep.join(["*"] * MAX_ZARR_DEPTH)))
        except StopIteration:
            pass
        else:
            msg = f"Zarr directory tree more than {MAX_ZARR_DEPTH} directories deep"
            if devel_debug:
                raise ValueError(msg)
            lgr.warning("%s: %s", self.filepath, msg, extra={"validating": True})
            return [msg]
        # TODO: Should this be appended to the above errors?
        return super().get_validation_errors(
            schema_version=schema_version, devel_debug=devel_debug
        )

    def iter_upload(
        self,
        dandiset: RemoteDandiset,
        metadata: dict[str, Any],
        jobs: Optional[int] = None,
        replacing: Optional[RemoteAsset] = None,
    ) -> Iterator[dict]:
        """
        Upload the Zarr directory as an asset with the given metadata to the
        given Dandiset, returning a generator of status `dict`\\s.

        :param RemoteDandiset dandiset:
            the Dandiset to which the Zarr will be uploaded
        :param dict metadata:
            Metadata for the uploaded asset.  The "path" field will be set to
            the value of the instance's ``path`` attribute if no such field is
            already present.
        :param int jobs: Number of threads to use for uploading; defaults to 5
        :param RemoteAsset replacing:
            If set, replace the given asset, which must have the same path as
            the new asset; if the old asset is a Zarr, the Zarr will be updated
            & reused for the new asset
        :returns:
            A generator of `dict`\\s containing at least a ``"status"`` key.
            Upon successful upload, the last `dict` will have a status of
            ``"done"`` and an ``"asset"`` key containing the resulting
            `RemoteAsset`.
        """
        # So that older clients don't get away with doing the wrong thing once
        # Zarr upload to embargoed Dandisets is implemented in the API:
        if dandiset.embargo_status is EmbargoStatus.EMBARGOED:
            raise NotImplementedError(
                "Uploading Zarr assets to embargoed Dandisets is currently not implemented"
            )
        asset_path = metadata.setdefault("path", self.path)
        client = dandiset.client
        lgr.debug("%s: Producing asset", asset_path)
        yield {"status": "producing asset"}
        old_zarr_entries: dict[str, RemoteZarrEntry] = {}

        def mkzarr() -> str:
            nonlocal old_zarr_entries
            try:
                r = client.post(
                    "/zarr/",
                    json={"name": asset_path, "dandiset": dandiset.identifier},
                )
            except requests.HTTPError as e:
                if "Zarr already exists" in e.response.text:
                    lgr.warning(
                        "%s: Found pre-existing Zarr at same path not"
                        " associated with any asset; reusing",
                        asset_path,
                    )
                    (old_zarr,) = client.paginate(
                        "/zarr/",
                        params={
                            "dandiset": dandiset.identifier,
                            "name": asset_path,
                        },
                    )
                    zarr_id = old_zarr["zarr_id"]
                    filetree = RemoteZarrEntry(
                        client=client,
                        zarr_id=zarr_id,
                        parts=(),
                        _known_dir=True,
                    )
                    old_zarr_entries = {
                        str(e): e for e in filetree.iterfiles(include_dirs=True)
                    }
                else:
                    raise
            else:
                zarr_id = r["zarr_id"]
            assert isinstance(zarr_id, str)
            return zarr_id

        if replacing is not None:
            lgr.debug("%s: Replacing pre-existing asset", asset_path)
            if isinstance(replacing, RemoteZarrAsset):
                lgr.debug(
                    "%s: Pre-existing asset is a Zarr; reusing & updating", asset_path
                )
                zarr_id = replacing.zarr
                old_zarr_entries = {
                    str(e): e for e in replacing.iterfiles(include_dirs=True)
                }
            else:
                lgr.debug(
                    "%s: Pre-existing asset is not a Zarr; minting new Zarr", asset_path
                )
                zarr_id = mkzarr()
            r = client.put(
                replacing.api_path,
                json={"metadata": metadata, "zarr_id": zarr_id},
            )
        else:
            lgr.debug("%s: Minting new Zarr", asset_path)
            zarr_id = mkzarr()
            r = client.post(
                f"{dandiset.version_api_path}assets/",
                json={"metadata": metadata, "zarr_id": zarr_id},
            )
        a = RemoteAsset.from_data(dandiset, r)
        assert isinstance(a, RemoteZarrAsset)

        total_size = 0
        to_upload = EntryUploadTracker()
        if old_zarr_entries:
            to_delete: list[RemoteZarrEntry] = []
            digesting: list[Future[Optional[tuple[LocalZarrEntry, str]]]] = []
            yield {"status": "comparing against remote Zarr"}
            with ThreadPoolExecutor(max_workers=jobs or 5) as executor:
                for local_entry in self.iterfiles():
                    total_size += local_entry.size
                    try:
                        remote_entry = old_zarr_entries.pop(str(local_entry))
                    except KeyError:
                        for pp in local_entry.parents:
                            pps = str(pp)
                            if pps in old_zarr_entries:
                                if old_zarr_entries[pps].is_file():
                                    lgr.debug(
                                        "%s: Parent path %s of file %s"
                                        " corresponds to a remote file;"
                                        " deleting remote",
                                        asset_path,
                                        pps,
                                        local_entry,
                                    )
                                    to_delete.append(old_zarr_entries.pop(pps))
                                break
                        lgr.debug(
                            "%s: Path %s not present in remote Zarr; uploading",
                            asset_path,
                            local_entry,
                        )
                        to_upload.register(local_entry)
                    else:
                        if remote_entry.is_dir():
                            lgr.debug(
                                "%s: Path %s of local file is a directory in"
                                " remote Zarr; deleting remote & re-uploading",
                                asset_path,
                                local_entry,
                            )
                            eprefix = str(remote_entry) + "/"
                            sub_e = [
                                (k, v)
                                for k, v in old_zarr_entries.items()
                                if k.startswith(eprefix)
                            ]
                            for k, v in sub_e:
                                old_zarr_entries.pop(k)
                                to_delete.append(v)
                            to_upload.register(local_entry)
                        else:
                            digesting.append(
                                executor.submit(
                                    _cmp_digests,
                                    asset_path,
                                    local_entry,
                                    remote_entry.get_digest().value,
                                )
                            )
                for dgstfut in as_completed(digesting):
                    try:
                        item = dgstfut.result()
                    except Exception:
                        for d in digesting:
                            d.cancel()
                        raise
                    else:
                        if item is not None:
                            local_entry, local_digest = item
                            to_upload.register(local_entry, local_digest)
            if to_delete:
                a.rmfiles(to_delete, reingest=False)
        else:
            yield {"status": "traversing local Zarr"}
            for local_entry in self.iterfiles():
                total_size += local_entry.size
                to_upload.register(local_entry)
        yield {"status": "initiating upload", "size": total_size}
        lgr.debug("%s: Beginning upload", asset_path)
        bytes_uploaded = 0
        need_ingest = False
        upload_data = (
            zarr_id,
            client.get_url(f"/zarr/{zarr_id}/upload"),
            cast(Optional[str], client.session.headers.get("Authorization")),
        )
        with RESTFullAPIClient(
            "http://nil.nil",
            headers={"X-Amz-ACL": "bucket-owner-full-control"},
        ) as storage, closing(to_upload.get_items()) as upload_items:
            for i, upload_body in enumerate(
                chunked(upload_items, ZARR_UPLOAD_BATCH_SIZE), start=1
            ):
                lgr.debug(
                    "%s: Uploading Zarr file batch #%d (%s)",
                    asset_path,
                    i,
                    pluralize(len(upload_body), "file"),
                )
                r = client.post(f"/zarr/{zarr_id}/upload/", json=upload_body)
                ZARR_UPLOADS_IN_PROGRESS.add(upload_data)
                with ThreadPoolExecutor(max_workers=jobs or 5) as executor:
                    futures = [
                        executor.submit(
                            _upload_zarr_file,
                            storage_session=storage,
                            path=self.filepath / upspec["path"],
                            upload_url=upspec["upload_url"],
                        )
                        for upspec in r
                    ]
                    need_ingest = True
                    for fut in as_completed(futures):
                        try:
                            size = fut.result()
                        except Exception as e:
                            lgr.debug(
                                "Error uploading zarr: %s: %s", type(e).__name__, e
                            )
                            lgr.debug("Cancelling upload")
                            for f in futures:
                                f.cancel()
                            executor.shutdown()
                            client.delete(f"/zarr/{zarr_id}/upload/")
                            raise
                        else:
                            bytes_uploaded += size
                            yield {
                                "status": "uploading",
                                "upload": 100 * bytes_uploaded / to_upload.total_size,
                                "current": bytes_uploaded,
                            }
                lgr.debug("%s: Completing upload of batch #%d", asset_path, i)
                client.post(f"/zarr/{zarr_id}/upload/complete/")
                ZARR_UPLOADS_IN_PROGRESS.discard(upload_data)
        lgr.debug("%s: All files uploaded", asset_path)
        old_zarr_files = [e for e in old_zarr_entries.values() if e.is_file()]
        if old_zarr_files:
            yield {"status": "deleting extra remote files"}
            lgr.debug(
                "%s: Deleting %s in remote Zarr not present locally",
                asset_path,
                pluralize(len(old_zarr_files), "file"),
            )
            a.rmfiles(old_zarr_files, reingest=False)
            need_ingest = True
        if need_ingest:
            lgr.debug("%s: Waiting for server to calculate Zarr checksum", asset_path)
            yield {"status": "server calculating checksum"}
            client.post(f"/zarr/{zarr_id}/ingest/")
            while True:
                sleep(2)
                r = client.get(f"/zarr/{zarr_id}/")
                if r["status"] == "Complete":
                    break
            lgr.info("%s: Asset successfully uploaded", asset_path)
        else:
            lgr.info("%s: No changes made to Zarr", asset_path)
        yield {"status": "done", "asset": a}


def _upload_zarr_file(
    storage_session: RESTFullAPIClient, path: Path, upload_url: str
) -> int:
    with path.open("rb") as fp:
        storage_session.put(
            upload_url, data=fp, json_resp=False, retry_if=_retry_zarr_file
        )
    return path.stat().st_size


def _retry_zarr_file(r: requests.Response) -> bool:
    # Some sort of filesystem hiccup can cause requests to be unable to get the
    # filesize, leading to it falling back to "chunked" transfer encoding,
    # which S3 doesn't support.
    return (
        r.status_code == 501
        and "header you provided implies functionality that is not implemented"
        in r.text
    )


@dataclass
class EntryUploadTracker:
    """
    Class for keeping track of `LocalZarrEntry` instances to upload

    :meta private:
    """

    total_size: int = 0
    digested_entries: list[tuple[LocalZarrEntry, str]] = field(default_factory=list)
    fresh_entries: list[LocalZarrEntry] = field(default_factory=list)

    def register(self, e: LocalZarrEntry, digest: Optional[str] = None) -> None:
        if digest is not None:
            self.digested_entries.append((e, digest))
        else:
            self.fresh_entries.append(e)
        self.total_size += e.size

    @staticmethod
    def _mkitem(e: LocalZarrEntry) -> dict:
        digest = md5file_nocache(e.filepath)
        return {"path": str(e), "etag": digest}

    def get_items(self, jobs: int = 5) -> Generator[dict, None, None]:
        # Note: In order for the ThreadPoolExecutor to be closed if an error
        # occurs during upload, the method must be used like this:
        #
        #     with contextlib.closing(to_upload.get_items()) as upload_items:
        #         for item in upload_items:
        #             ...
        for e, digest in self.digested_entries:
            yield {"path": str(e), "etag": digest}
        if not self.fresh_entries:
            return
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            futures = [executor.submit(self._mkitem, e) for e in self.fresh_entries]
            for fut in as_completed(futures):
                try:
                    yield fut.result()
                # Use BaseException to also catch GeneratorExit thrown by
                # closing()
                except BaseException:
                    for f in futures:
                        f.cancel()
                    raise


def _cmp_digests(
    asset_path: str, local_entry: LocalZarrEntry, remote_digest: str
) -> Optional[tuple[LocalZarrEntry, str]]:
    local_digest = md5file_nocache(local_entry.filepath)
    if local_digest != remote_digest:
        lgr.debug(
            "%s: Path %s in Zarr differs from local file; re-uploading",
            asset_path,
            local_entry,
        )
        return (local_entry, local_digest)
    else:
        lgr.debug("%s: File %s already on server; skipping", asset_path, local_entry)
        return None


# Collection of (zarr ID, upload endpoint URL, auth header value) tuples
ZARR_UPLOADS_IN_PROGRESS: set[tuple[str, str, Optional[str]]] = set()


@atexit.register
def cancel_zarr_uploads() -> None:
    for zarr_id, url, auth in ZARR_UPLOADS_IN_PROGRESS:
        lgr.debug("Cancelling upload for Zarr %s", zarr_id)
        headers = {"Authorization": auth} if auth is not None else {}
        r = requests.delete(url, headers=headers)
        if not r.ok:
            lgr.warning(
                "Upload cancellation failed with %d: %s: %s",
                r.status_code,
                r.reason,
                r.text,
            )
