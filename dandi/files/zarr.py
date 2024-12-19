from __future__ import annotations

from base64 import b64encode
from collections.abc import Generator, Iterator
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import closing
from dataclasses import dataclass, field, replace
from datetime import datetime
import os
import os.path
from pathlib import Path
from time import sleep
from typing import Any

from dandischema.models import BareAsset, DigestType
import requests
from zarr_checksum.tree import ZarrChecksumTree

from dandi import get_logger
from dandi.consts import (
    MAX_ZARR_DEPTH,
    ZARR_DELETE_BATCH_SIZE,
    ZARR_MIME_TYPE,
    ZARR_UPLOAD_BATCH_SIZE,
)
from dandi.dandiapi import (
    RemoteAsset,
    RemoteDandiset,
    RemoteZarrAsset,
    RemoteZarrEntry,
    RESTFullAPIClient,
)
from dandi.metadata.core import get_default_metadata
from dandi.misctypes import DUMMY_DANDI_ZARR_CHECKSUM, BasePath, Digest
from dandi.utils import (
    chunked,
    exclude_from_zarr,
    pluralize,
    post_upload_size_check,
    pre_upload_size_check,
)

from .bases import LocalDirectoryAsset
from ..validate_types import Scope, Severity, ValidationOrigin, ValidationResult

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
        return os.path.lexists(self.filepath)

    def is_file(self) -> bool:
        return self.filepath.is_file()

    def is_dir(self) -> bool:
        return self.filepath.is_dir()

    def iterdir(self) -> Iterator[LocalZarrEntry]:
        for p in self.filepath.iterdir():
            if exclude_from_zarr(p):
                continue
            if p.is_dir() and not any(p.iterdir()):
                # Ignore empty directories
                continue
            yield self._get_subpath(p.name)

    def get_digest(self) -> Digest:
        """
        Calculate the DANDI etag digest for the entry.  If the entry is a
        directory, the algorithm will be the DANDI Zarr checksum algorithm; if
        it is a file, it will be MD5.
        """
        # Avoid heavy import by importing within function:
        from dandi.support.digests import get_digest, get_zarr_checksum

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
    #: The DANDI Zarr checksum of the asset
    digest: Digest
    #: A list of all files in the asset in unspecified order
    files: list[LocalZarrEntry]


class ZarrAsset(LocalDirectoryAsset[LocalZarrEntry]):
    """Representation of a local Zarr directory"""

    _DUMMY_DIGEST = DUMMY_DANDI_ZARR_CHECKSUM

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
            # Avoid heavy import by importing within function:
            from dandi.support.digests import checksum_zarr_dir, md5file_nocache

            size = 0
            dir_info = {}
            file_info = {}
            files = []
            for p in dirpath.iterdir():
                if p.is_dir():
                    st = dirstat(p)
                    size += st.size
                    dir_info[p.name] = (st.digest.value, st.size)
                    files.extend(st.files)
                else:
                    size += p.size
                    file_info[p.name] = (md5file_nocache(p.filepath), p.size)
                    files.append(p)
            return ZarrStat(
                size=size,
                digest=Digest.dandi_zarr(checksum_zarr_dir(file_info, dir_info)),
                files=files,
            )

        return dirstat(self.filetree)

    def get_digest(self) -> Digest:
        """Calculate a dandi-zarr-checksum digest for the asset"""
        # Avoid heavy import by importing within function:
        from dandi.support.digests import get_zarr_checksum

        return Digest.dandi_zarr(get_zarr_checksum(self.filepath))

    def get_metadata(
        self,
        digest: Digest | None = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        metadata = get_default_metadata(self.filepath, digest=digest)
        metadata.encodingFormat = ZARR_MIME_TYPE
        metadata.path = self.path
        return metadata

    def get_validation_errors(
        self,
        schema_version: str | None = None,
        devel_debug: bool = False,
    ) -> list[ValidationResult]:
        # Avoid heavy import by importing within function:
        import zarr

        errors: list[ValidationResult] = []
        try:
            data = zarr.open(str(self.filepath))
        except Exception:
            if devel_debug:
                raise
            errors.append(
                ValidationResult(
                    origin=ValidationOrigin(
                        name="zarr",
                        version=zarr.version.version,
                    ),
                    severity=Severity.ERROR,
                    id="zarr.cannot_open",
                    scope=Scope.FILE,
                    path=self.filepath,
                    message="Error opening file.",
                )
            )
            data = None
        if isinstance(data, zarr.Group) and not data:
            errors.append(
                ValidationResult(
                    origin=ValidationOrigin(
                        name="zarr",
                        version=zarr.version.version,
                    ),
                    severity=Severity.ERROR,
                    id="zarr.empty_group",
                    scope=Scope.FILE,
                    path=self.filepath,
                    message="Zarr group is empty.",
                )
            )
        if self._is_too_deep():
            msg = f"Zarr directory tree more than {MAX_ZARR_DEPTH} directories deep"
            if devel_debug:
                raise ValueError(msg)
            errors.append(
                ValidationResult(
                    origin=ValidationOrigin(
                        name="zarr",
                        version=zarr.version.version,
                    ),
                    severity=Severity.ERROR,
                    id="zarr.tree_depth_exceeded",
                    scope=Scope.FILE,
                    path=self.filepath,
                    message=msg,
                )
            )
        return errors + super().get_validation_errors(
            schema_version=schema_version, devel_debug=devel_debug
        )

    def _is_too_deep(self) -> bool:
        for e in self.iterfiles():
            if len(e.parts) >= MAX_ZARR_DEPTH + 1:
                return True
        return False

    def iter_upload(
        self,
        dandiset: RemoteDandiset,
        metadata: dict[str, Any],
        jobs: int | None = None,
        replacing: RemoteAsset | None = None,
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
        asset_path = metadata.setdefault("path", self.path)
        client = dandiset.client
        lgr.debug("%s: Producing asset", asset_path)
        yield {"status": "producing asset"}

        def mkzarr() -> str:
            try:
                r = client.post(
                    "/zarr/",
                    json={"name": asset_path, "dandiset": dandiset.identifier},
                )
            except requests.HTTPError as e:
                if e.response is not None and "Zarr already exists" in e.response.text:
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
        mismatched = True
        first_run = True
        while mismatched:
            zcc = ZarrChecksumTree()
            old_zarr_entries: dict[str, RemoteZarrEntry] = {
                str(e): e for e in a.iterfiles()
            }
            total_size = 0
            to_upload = EntryUploadTracker()
            if old_zarr_entries:
                to_delete: list[RemoteZarrEntry] = []
                digesting: list[Future[tuple[LocalZarrEntry, str, bool]]] = []
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
                            else:
                                eprefix = str(local_entry) + "/"
                                sub_e = [
                                    (k, v)
                                    for k, v in old_zarr_entries.items()
                                    if k.startswith(eprefix)
                                ]
                                if sub_e:
                                    lgr.debug(
                                        "%s: Path %s of local file is a directory"
                                        " in remote Zarr; deleting remote",
                                        asset_path,
                                        local_entry,
                                    )
                                    for k, v in sub_e:
                                        old_zarr_entries.pop(k)
                                        to_delete.append(v)
                            lgr.debug(
                                "%s: Path %s not present in remote Zarr; uploading",
                                asset_path,
                                local_entry,
                            )
                            to_upload.register(local_entry)
                        else:
                            digesting.append(
                                executor.submit(
                                    _cmp_digests,
                                    asset_path,
                                    local_entry,
                                    remote_entry.digest.value,
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
                            local_entry, local_digest, differs = item
                            if differs:
                                to_upload.register(local_entry, local_digest)
                            else:
                                zcc.add_leaf(
                                    Path(str(local_entry)),
                                    local_entry.size,
                                    local_digest,
                                )
                if to_delete:
                    yield from _rmfiles(
                        asset=a,
                        entries=to_delete,
                        status="deleting conflicting remote files",
                    )
            else:
                yield {"status": "traversing local Zarr"}
                for local_entry in self.iterfiles():
                    total_size += local_entry.size
                    to_upload.register(local_entry)
            yield {"status": "initiating upload", "size": total_size}
            lgr.debug("%s: Beginning upload", asset_path)
            bytes_uploaded = 0
            changed = False
            with RESTFullAPIClient(
                "http://nil.nil",
                headers={"X-Amz-ACL": "bucket-owner-full-control"},
            ) as storage, closing(to_upload.get_items()) as upload_items:
                for i, items in enumerate(
                    chunked(upload_items, ZARR_UPLOAD_BATCH_SIZE), start=1
                ):
                    uploading = []
                    for it in items:
                        zcc.add_leaf(Path(it.entry_path), it.size, it.digest)
                        uploading.append(it.upload_request())
                    lgr.debug(
                        "%s: Uploading Zarr file batch #%d (%s)",
                        asset_path,
                        i,
                        pluralize(len(uploading), "file"),
                    )
                    r = client.post(f"/zarr/{zarr_id}/files/", json=uploading)
                    with ThreadPoolExecutor(max_workers=jobs or 5) as executor:
                        futures = [
                            executor.submit(
                                _upload_zarr_file,
                                storage_session=storage,
                                upload_url=signed_url,
                                item=it,
                            )
                            for (signed_url, it) in zip(r, items)
                        ]
                        changed = True
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
                                raise
                            else:
                                bytes_uploaded += size
                                yield {
                                    "status": "uploading",
                                    "progress": 100
                                    * bytes_uploaded
                                    / to_upload.total_size,
                                    "current": bytes_uploaded,
                                }
                    lgr.debug("%s: Completing upload of batch #%d", asset_path, i)
            lgr.debug("%s: All files uploaded", asset_path)
            old_zarr_files = list(old_zarr_entries.values())
            if old_zarr_files:
                lgr.debug(
                    "%s: Deleting %s in remote Zarr not present locally",
                    asset_path,
                    pluralize(len(old_zarr_files), "file"),
                )
                yield from _rmfiles(
                    asset=a,
                    entries=old_zarr_files,
                    status="deleting extra remote files",
                )
                changed = True
            if changed:
                lgr.debug(
                    "%s: Waiting for server to calculate Zarr checksum", asset_path
                )
                yield {"status": "server calculating checksum"}
                client.post(f"/zarr/{zarr_id}/finalize/")
                while True:
                    sleep(2)
                    r = client.get(f"/zarr/{zarr_id}/")
                    if r["status"] == "Complete":
                        our_checksum = str(zcc.process())
                        server_checksum = r["checksum"]
                        if our_checksum == server_checksum:
                            mismatched = False
                        else:
                            mismatched = True
                            lgr.info(
                                "%s: Asset checksum mismatch (local: %s;"
                                " server: %s); redoing upload",
                                asset_path,
                                our_checksum,
                                server_checksum,
                            )
                            yield {"status": "Checksum mismatch"}
                        break
            elif mismatched and not first_run:
                lgr.error(
                    "%s: Previous upload loop resulted in checksum mismatch,"
                    " and no discrepancies between local and remote Zarr were found"
                )
                raise RuntimeError("Unresolvable Zarr checksum mismatch")
            else:
                mismatched = False
                lgr.info("%s: No changes made to Zarr", asset_path)
            first_run = False
        lgr.info("%s: Asset successfully uploaded", asset_path)
        yield {"status": "done", "asset": a}


def _upload_zarr_file(
    storage_session: RESTFullAPIClient, upload_url: str, item: UploadItem
) -> int:
    try:
        with item.filepath.open("rb") as fp:
            storage_session.put(
                upload_url,
                data=fp,
                json_resp=False,
                retry_if=_retry_zarr_file,
                headers={"Content-MD5": item.base64_digest},
            )
    except Exception:
        post_upload_size_check(item.filepath, item.size, True)
        raise
    else:
        post_upload_size_check(item.filepath, item.size, False)
        return item.size


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
    digested_entries: list[UploadItem] = field(default_factory=list)
    fresh_entries: list[LocalZarrEntry] = field(default_factory=list)

    def register(self, e: LocalZarrEntry, digest: str | None = None) -> None:
        if digest is not None:
            self.digested_entries.append(UploadItem.from_entry(e, digest))
        else:
            self.fresh_entries.append(e)
        self.total_size += e.size

    @staticmethod
    def _mkitem(e: LocalZarrEntry) -> UploadItem:
        # Avoid heavy import by importing within function:
        from dandi.support.digests import md5file_nocache

        digest = md5file_nocache(e.filepath)
        return UploadItem.from_entry(e, digest)

    def get_items(self, jobs: int = 5) -> Generator[UploadItem, None, None]:
        # Note: In order for the ThreadPoolExecutor to be closed if an error
        # occurs during upload, the method must be used like this:
        #
        #     with contextlib.closing(to_upload.get_items()) as upload_items:
        #         for item in upload_items:
        #             ...
        yield from self.digested_entries
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


@dataclass
class UploadItem:
    """:meta private:"""

    entry_path: str
    filepath: Path
    digest: str
    size: int

    @classmethod
    def from_entry(cls, e: LocalZarrEntry, digest: str) -> UploadItem:
        return cls(
            entry_path=str(e),
            filepath=e.filepath,
            digest=digest,
            size=pre_upload_size_check(e.filepath),
        )

    @property
    def base64_digest(self) -> str:
        return b64encode(bytes.fromhex(self.digest)).decode("us-ascii")

    def upload_request(self) -> dict[str, str]:
        return {"path": self.entry_path, "base64md5": self.base64_digest}


def _cmp_digests(
    asset_path: str, local_entry: LocalZarrEntry, remote_digest: str
) -> tuple[LocalZarrEntry, str, bool]:
    # Avoid heavy import by importing within function:
    from dandi.support.digests import md5file_nocache

    local_digest = md5file_nocache(local_entry.filepath)
    if local_digest != remote_digest:
        lgr.debug(
            "%s: Path %s in Zarr differs from local file; re-uploading",
            asset_path,
            local_entry,
        )
        return (local_entry, local_digest, True)
    else:
        lgr.debug("%s: File %s already on server; skipping", asset_path, local_entry)
        return (local_entry, local_digest, False)


def _rmfiles(
    asset: RemoteZarrAsset, entries: list[RemoteZarrEntry], status: str
) -> Iterator[dict]:
    # Do the batching outside of the rmfiles() method so that we can report
    # progress on the completion of each batch
    yield {
        "status": status,
        "progress": 0,
        "current": 0,
    }
    deleted = 0
    for ents in chunked(entries, ZARR_DELETE_BATCH_SIZE):
        asset.rmfiles(ents, reingest=False)
        deleted += len(ents)
        yield {
            "status": status,
            "progress": deleted / len(entries) * 100,
            "current": deleted,
        }
