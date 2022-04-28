"""
.. versionadded:: 0.36.0

This module defines functionality for working with local files & directories
(as opposed to remote resources on a DANDI Archive server) that are of interest
to DANDI.  The classes for such files & directories all inherit from
`DandiFile`, which has two immediate subclasses: `DandisetMetadataFile`, for
representing :file:`dandiset.yaml` files, and `LocalAsset`, for representing
files that can be uploaded as assets to DANDI Archive.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import closing
from dataclasses import dataclass, field, replace
from datetime import datetime
import os
from pathlib import Path
import re
from threading import Lock
from time import sleep
from typing import (
    Any,
    BinaryIO,
    ClassVar,
    Dict,
    Generator,
    Generic,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
)
from xml.etree.ElementTree import fromstring

from dandischema.digests.dandietag import DandiETag
from dandischema.digests.zarr import get_checksum
from dandischema.models import BareAsset, CommonModel
from dandischema.models import Dandiset as DandisetMeta
from dandischema.models import DigestType, get_schema_version
from nwbinspector import Importance, inspect_nwb, load_config
from pydantic import ValidationError
import requests
import zarr

from . import get_logger
from .consts import (
    MAX_ZARR_DEPTH,
    VIDEO_FILE_EXTENSIONS,
    ZARR_MIME_TYPE,
    ZARR_UPLOAD_BATCH_SIZE,
    EmbargoStatus,
    dandiset_metadata_file,
)
from .dandiapi import (
    RemoteAsset,
    RemoteDandiset,
    RemoteZarrAsset,
    RemoteZarrEntry,
    RESTFullAPIClient,
)
from .exceptions import UnknownAssetError
from .metadata import get_default_metadata, nwb2asset
from .misctypes import DUMMY_DIGEST, BasePath, Digest, P
from .pynwb_utils import validate as pynwb_validate
from .support.digests import (
    get_dandietag,
    get_digest,
    get_zarr_checksum,
    md5file_nocache,
)
from .utils import chunked, pluralize, yaml_load

lgr = get_logger()

# TODO -- should come from schema.  This is just a simplistic example for now
_required_dandiset_metadata_fields = ["identifier", "name", "description"]


@dataclass  # type: ignore[misc]  # <https://github.com/python/mypy/issues/5374>
class DandiFile(ABC):
    """Abstract base class for local files & directories of interest to DANDI"""

    #: The path to the actual file or directory on disk
    filepath: Path

    @property
    def size(self) -> int:
        """The size of the file"""
        return os.path.getsize(self.filepath)

    @property
    def modified(self) -> datetime:
        """The time at which the file was last modified"""
        # TODO: Should this be overridden for LocalDirectoryAsset?
        return datetime.fromtimestamp(self.filepath.stat().st_mtime).astimezone()

    @abstractmethod
    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        ignore_errors: bool = True,
    ) -> CommonModel:
        """Return the Dandi metadata for the file"""
        ...

    @abstractmethod
    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> List[str]:
        """
        Attempt to validate the file and return a list of errors encountered
        """
        ...


class DandisetMetadataFile(DandiFile):
    """Representation of a :file:`dandiset.yaml` file"""

    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        ignore_errors: bool = True,
    ) -> DandisetMeta:
        """Return the Dandiset metadata inside the file"""
        with open(self.filepath) as f:
            meta = yaml_load(f, typ="safe")
        return DandisetMeta.unvalidated(**meta)

    # TODO: @validate_cache.memoize_path
    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> List[str]:
        with open(self.filepath) as f:
            meta = yaml_load(f, typ="safe")
        if schema_version is None:
            schema_version = meta.get("schemaVersion")
        if schema_version is None:
            return _check_required_fields(meta, _required_dandiset_metadata_fields)
        else:
            current_version = get_schema_version()
            if schema_version != current_version:
                raise ValueError(
                    f"Unsupported schema version: {schema_version}; expected {current_version}"
                )
            try:
                DandisetMeta(**meta)
            except ValidationError as e:
                if devel_debug:
                    raise
                lgr.warning(
                    "Validation error for %s: %s",
                    self.filepath,
                    e,
                    extra={"validating": True},
                )
                return [str(e)]
            except Exception as e:
                if devel_debug:
                    raise
                lgr.warning(
                    "Unexpected validation error for %s: %s",
                    self.filepath,
                    e,
                    extra={"validating": True},
                )
                return [f"Failed to initialize Dandiset meta: {e}"]
            return []


@dataclass  # type: ignore[misc]  # <https://github.com/python/mypy/issues/5374>
class LocalAsset(DandiFile):
    """
    Representation of a file or directory that can be uploaded to a DANDI
    Archive as an asset of a Dandiset
    """

    #: The forward-slash-separated path to the asset within its local Dandiset
    #: (i.e., relative to the Dandiset's root)
    path: str

    @abstractmethod
    def get_digest(self) -> Digest:
        """
        Calculate a DANDI etag digest for the asset using the appropriate
        algorithm for its type
        """
        ...

    @abstractmethod
    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        """Return the Dandi metadata for the asset"""
        ...

    # TODO: @validate_cache.memoize_path
    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> List[str]:
        if schema_version is not None:
            current_version = get_schema_version()
            if schema_version != current_version:
                raise ValueError(
                    f"Unsupported schema version: {schema_version}; expected {current_version}"
                )
            try:
                asset = self.get_metadata(digest=DUMMY_DIGEST)
                BareAsset(**asset.dict())
            except ValidationError as e:
                if devel_debug:
                    raise
                lgr.warning(
                    "Validation error for %s: %s",
                    self.filepath,
                    e,
                    extra={"validating": True},
                )
                return [str(e)]
            except Exception as e:
                if devel_debug:
                    raise
                lgr.warning(
                    "Unexpected validation error for %s: %s",
                    self.filepath,
                    e,
                    extra={"validating": True},
                )
                return [f"Failed to read metadata: {e}"]
            return []
        else:
            # TODO: Do something else?
            return []

    def upload(
        self,
        dandiset: RemoteDandiset,
        metadata: Dict[str, Any],
        jobs: Optional[int] = None,
        replacing: Optional[RemoteAsset] = None,
    ) -> RemoteAsset:
        """
        Upload the file as an asset with the given metadata to the given
        Dandiset and return the resulting asset.  Blocks until the upload is
        complete.

        :param RemoteDandiset dandiset:
            the Dandiset to which the file will be uploaded
        :param dict metadata:
            Metadata for the uploaded asset.  The "path" field will be set to
            the value of the instance's ``path`` attribute if no such field is
            already present.
        :param int jobs: Number of threads to use for uploading; defaults to 5
        :param RemoteAsset replacing:
            If set, replace the given asset, which must have the same path as
            the new asset
        :rtype: RemoteAsset
        """
        for status in self.iter_upload(
            dandiset, metadata, jobs=jobs, replacing=replacing
        ):
            if status["status"] == "done":
                a = status["asset"]
                assert isinstance(a, RemoteAsset)
                return a
        raise AssertionError("iter_upload() finished without returning 'done'")

    @abstractmethod
    def iter_upload(
        self,
        dandiset: RemoteDandiset,
        metadata: Dict[str, Any],
        jobs: Optional[int] = None,
        replacing: Optional[RemoteAsset] = None,
    ) -> Iterator[dict]:
        """
        Upload the asset with the given metadata to the given Dandiset,
        returning a generator of status `dict`\\s.

        :param RemoteDandiset dandiset:
            the Dandiset to which the asset will be uploaded
        :param dict metadata:
            Metadata for the uploaded asset.  The "path" field will be set to
            the value of the instance's ``path`` attribute if no such field is
            already present.
        :param int jobs: Number of threads to use for uploading; defaults to 5
        :param RemoteAsset replacing:
            If set, replace the given asset, which must have the same path as
            the new asset
        :returns:
            A generator of `dict`\\s containing at least a ``"status"`` key.
            Upon successful upload, the last `dict` will have a status of
            ``"done"`` and an ``"asset"`` key containing the resulting
            `RemoteAsset`.
        """
        ...


class LocalFileAsset(LocalAsset):
    """
    Representation of a regular file that can be uploaded to a DANDI Archive as
    an asset of a Dandiset
    """

    EXTENSIONS: ClassVar[List[str]] = []

    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        metadata = get_default_metadata(self.filepath, digest=digest)
        metadata.path = self.path
        return metadata

    def get_digest(self) -> Digest:
        """Calculate a dandi-etag digest for the asset"""
        value = get_digest(self.filepath, digest="dandi-etag")
        return Digest.dandi_etag(value)

    def iter_upload(
        self,
        dandiset: RemoteDandiset,
        metadata: Dict[str, Any],
        jobs: Optional[int] = None,
        replacing: Optional[RemoteAsset] = None,
    ) -> Iterator[dict]:
        """
        Upload the file as an asset with the given metadata to the given
        Dandiset, returning a generator of status `dict`\\s.

        :param RemoteDandiset dandiset:
            the Dandiset to which the file will be uploaded
        :param dict metadata:
            Metadata for the uploaded asset.  The "path" field will be set to
            the value of the instance's ``path`` attribute if no such field is
            already present.
        :param int jobs: Number of threads to use for uploading; defaults to 5
        :param RemoteAsset replacing:
            If set, replace the given asset, which must have the same path as
            the new asset
        :returns:
            A generator of `dict`\\s containing at least a ``"status"`` key.
            Upon successful upload, the last `dict` will have a status of
            ``"done"`` and an ``"asset"`` key containing the resulting
            `RemoteAsset`.
        """
        asset_path = metadata.setdefault("path", self.path)
        client = dandiset.client
        yield {"status": "calculating etag"}
        etagger = get_dandietag(self.filepath)
        filetag = etagger.as_str()
        lgr.debug("Calculated dandi-etag of %s for %s", filetag, self.filepath)
        digest = metadata.get("digest", {})
        if "dandi:dandi-etag" in digest:
            if digest["dandi:dandi-etag"] != filetag:
                raise RuntimeError(
                    f"{self.filepath}: File etag changed; was originally"
                    f" {digest['dandi:dandi-etag']} but is now {filetag}"
                )
        yield {"status": "initiating upload"}
        lgr.debug("%s: Beginning upload", asset_path)
        total_size = self.size
        try:
            resp = client.post(
                "/uploads/initialize/",
                json={
                    "contentSize": total_size,
                    "digest": {
                        "algorithm": "dandi:dandi-etag",
                        "value": filetag,
                    },
                    "dandiset": dandiset.identifier,
                },
            )
        except requests.HTTPError as e:
            if e.response.status_code == 409:
                lgr.debug("%s: Blob already exists on server", asset_path)
                blob_id = e.response.headers["Location"]
            else:
                raise
        else:
            upload_id = resp["upload_id"]
            parts = resp["parts"]
            if len(parts) != etagger.part_qty:
                raise RuntimeError(
                    f"Server and client disagree on number of parts for upload;"
                    f" server says {len(parts)}, client says {etagger.part_qty}"
                )
            parts_out = []
            bytes_uploaded = 0
            lgr.debug("Uploading %s in %d parts", self.filepath, len(parts))
            with RESTFullAPIClient("http://nil.nil") as storage:
                with self.filepath.open("rb") as fp:
                    with ThreadPoolExecutor(max_workers=jobs or 5) as executor:
                        lock = Lock()
                        futures = [
                            executor.submit(
                                _upload_blob_part,
                                storage_session=storage,
                                fp=fp,
                                lock=lock,
                                etagger=etagger,
                                asset_path=asset_path,
                                part=part,
                            )
                            for part in parts
                        ]
                        for fut in as_completed(futures):
                            out_part = fut.result()
                            bytes_uploaded += out_part["size"]
                            yield {
                                "status": "uploading",
                                "upload": 100 * bytes_uploaded / total_size,
                                "current": bytes_uploaded,
                            }
                            parts_out.append(out_part)
                lgr.debug("%s: Completing upload", asset_path)
                resp = client.post(
                    f"/uploads/{upload_id}/complete/",
                    json={"parts": parts_out},
                )
                lgr.debug(
                    "%s: Announcing completion to %s",
                    asset_path,
                    resp["complete_url"],
                )
                r = storage.post(
                    resp["complete_url"], data=resp["body"], json_resp=False
                )
                lgr.debug(
                    "%s: Upload completed. Response content: %s",
                    asset_path,
                    r.content,
                )
                rxml = fromstring(r.text)
                m = re.match(r"\{.+?\}", rxml.tag)
                ns = m.group(0) if m else ""
                final_etag = rxml.findtext(f"{ns}ETag")
                if final_etag is not None:
                    final_etag = final_etag.strip('"')
                    if final_etag != filetag:
                        raise RuntimeError(
                            "Server and client disagree on final ETag of uploaded file;"
                            f" server says {final_etag}, client says {filetag}"
                        )
                # else: Error? Warning?
                resp = client.post(f"/uploads/{upload_id}/validate/")
                blob_id = resp["blob_id"]
        lgr.debug("%s: Assigning asset blob to dandiset & version", asset_path)
        yield {"status": "producing asset"}
        if replacing is not None:
            lgr.debug("%s: Replacing pre-existing asset", asset_path)
            r = client.put(
                replacing.api_path,
                json={"metadata": metadata, "blob_id": blob_id},
            )
        else:
            r = client.post(
                f"{dandiset.version_api_path}assets/",
                json={"metadata": metadata, "blob_id": blob_id},
            )
        a = RemoteAsset.from_data(dandiset, r)
        lgr.info("%s: Asset successfully uploaded", asset_path)
        yield {"status": "done", "asset": a}


class NWBAsset(LocalFileAsset):
    """Representation of a local NWB file"""

    EXTENSIONS: ClassVar[List[str]] = [".nwb"]

    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        try:
            metadata = nwb2asset(self.filepath, digest=digest)
        except Exception as e:
            lgr.warning(
                "Failed to extract NWB metadata from %s: %s: %s",
                self.filepath,
                type(e).__name__,
                str(e),
            )
            if ignore_errors:
                metadata = get_default_metadata(self.filepath, digest=digest)
            else:
                raise
        metadata.path = self.path
        return metadata

    # TODO: @validate_cache.memoize_path
    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> List[str]:
        errors: List[str] = pynwb_validate(self.filepath, devel_debug=devel_debug)
        if schema_version is not None:
            errors.extend(
                super().get_validation_errors(
                    schema_version=schema_version, devel_debug=devel_debug
                )
            )
        else:
            # make sure that we have some basic metadata fields we require
            try:
                errors.extend(
                    [
                        error.message
                        for error in inspect_nwb(
                            nwbfile_path=self.filepath,
                            skip_validate=True,
                            config=load_config(filepath_or_keyword="dandi"),
                            importance_threshold=Importance.CRITICAL,
                        )
                    ]
                )
            except Exception as e:
                if devel_debug:
                    raise
                lgr.warning(
                    "Failed to inspect NWBFile in %s: %s",
                    self.filepath,
                    e,
                    extra={"validating": True},
                )
                errors.append(f"Failed to inspect NWBFile: {e}")
        return errors


class VideoAsset(LocalFileAsset):
    EXTENSIONS: ClassVar[List[str]] = VIDEO_FILE_EXTENSIONS


class GenericAsset(LocalFileAsset):
    """
    Representation of a generic regular file, one that is not of any known type
    """

    EXTENSIONS: ClassVar[List[str]] = []


class LocalDirectoryAsset(LocalAsset, Generic[P]):
    """
    Representation of a directory that can be uploaded to a DANDI Archive as
    a single asset of a Dandiset.  It is generic in ``P``, bound to
    `dandi.misctypes.BasePath`.
    """

    EXTENSIONS: ClassVar[List[str]] = []

    @property
    @abstractmethod
    def filetree(self) -> P:
        """
        The path object for the root of the hierarchy of files within the
        directory
        """
        ...

    def iterfiles(self, include_dirs: bool = False) -> Iterator[P]:
        """Yield all files within the directory"""
        dirs = deque([self.filetree])
        while dirs:
            for p in dirs.popleft().iterdir():
                if p.is_dir():
                    dirs.append(p)
                    if include_dirs:
                        yield p
                else:
                    yield p

    @property
    def size(self) -> int:
        """The total size of the files in the directory"""
        return sum(p.size for p in self.iterfiles())


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
    files: List[LocalZarrEntry]


class ZarrAsset(LocalDirectoryAsset[LocalZarrEntry]):
    """Representation of a local Zarr directory"""

    EXTENSIONS: ClassVar[List[str]] = [".ngff", ".zarr"]

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
                    dir_md5s[str(p)] = (st.digest.value, st.size)
                    files.extend(st.files)
                else:
                    size += p.size
                    file_md5s[str(p)] = (md5file_nocache(p.filepath), p.size)
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
    ) -> List[str]:
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
        metadata: Dict[str, Any],
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
        old_zarr_entries: Dict[str, RemoteZarrEntry] = {}
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
                r = client.post(
                    "/zarr/", json={"name": asset_path, "dandiset": dandiset.identifier}
                )
                zarr_id = r["zarr_id"]
            r = client.put(
                replacing.api_path,
                json={"metadata": metadata, "zarr_id": zarr_id},
            )
        else:
            lgr.debug("%s: Minting new Zarr", asset_path)
            r = client.post(
                "/zarr/", json={"name": asset_path, "dandiset": dandiset.identifier}
            )
            zarr_id = r["zarr_id"]
            r = client.post(
                f"{dandiset.version_api_path}assets/",
                json={"metadata": metadata, "zarr_id": zarr_id},
            )
        a = RemoteAsset.from_data(dandiset, r)
        assert isinstance(a, RemoteZarrAsset)

        total_size = 0
        to_upload = EntryUploadTracker()
        if old_zarr_entries:
            to_delete: List[RemoteZarrEntry] = []
            digesting: List[Future[Optional[Tuple[LocalZarrEntry, str]]]] = []
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
        lgr.debug("%s: Waiting for server to calculate Zarr checksum", asset_path)
        yield {"status": "server calculating checksum"}
        client.post(f"/zarr/{zarr_id}/ingest/")
        while True:
            sleep(2)
            r = client.get(f"/zarr/{zarr_id}/")
            if r["status"] == "Complete":
                break
        lgr.info("%s: Asset successfully uploaded", asset_path)
        yield {"status": "done", "asset": a}


def find_dandi_files(
    *paths: Union[str, Path],
    dandiset_path: Optional[Union[str, Path]] = None,
    allow_all: bool = False,
    include_metadata: bool = False,
) -> Iterator[DandiFile]:
    """
    Yield all DANDI files at or under the paths in ``paths`` (which may be
    either files or directories).  Files & directories whose names start with a
    period are ignored.  Directories are only included in the return value if
    they are of a type represented by a `LocalDirectoryAsset` subclass, in
    which case they are not recursed into.

    :param dandiset_path:
        The path to the root of the Dandiset in which the paths are located.
        All paths in ``paths`` must be equal to or subpaths of
        ``dandiset_path``.  If `None`, then the Dandiset path for each asset
        found is implicitly set to the parent directory.
    :param allow_all:
        If true, unrecognized assets and the Dandiset's :file:`dandiset.yaml`
        file are returned as `GenericAsset` and `DandisetMetadataFile`
        instances, respectively.  If false, they are not returned at all.
    :param include_metadata:
        If true, the Dandiset's :file:`dandiset.yaml` file is returned as a
        `DandisetMetadataFile` instance.  If false, it is not returned at all
        (unless ``allow_all`` is true).
    """

    path_queue: deque[Path] = deque()
    for p in map(Path, paths):
        if dandiset_path is not None:
            try:
                p.relative_to(dandiset_path)
            except ValueError:
                raise ValueError(
                    "Path {str(p)!r} is not inside Dandiset path {str(dandiset_path)!r}"
                )
        path_queue.append(p)
    while path_queue:
        p = path_queue.popleft()
        if p.name.startswith("."):
            continue
        if p.is_dir():
            if p.is_symlink():
                lgr.warning("%s: Ignoring unsupported symbolic link to directory", p)
            elif dandiset_path is not None and p == Path(dandiset_path):
                path_queue.extend(p.iterdir())
            elif any(p.iterdir()):
                try:
                    df = dandi_file(p, dandiset_path)
                except UnknownAssetError:
                    path_queue.extend(p.iterdir())
                else:
                    yield df
        else:
            df = dandi_file(p, dandiset_path)
            if isinstance(df, GenericAsset) and not allow_all:
                pass
            elif isinstance(df, DandisetMetadataFile) and not (
                allow_all or include_metadata
            ):
                pass
            else:
                yield df


def dandi_file(
    filepath: Union[str, Path], dandiset_path: Optional[Union[str, Path]] = None
) -> DandiFile:
    """
    Return a `DandiFile` instance of the appropriate type for the file at
    ``filepath`` inside the Dandiset rooted at ``dandiset_path``.  If
    ``dandiset_path`` is not set, it will default to ``filepath``'s parent
    directory.

    If ``filepath`` is a directory, it must be of a type represented by a
    `LocalDirectoryAsset` subclass; otherwise, an `UnknownAssetError` exception
    will be raised.

    A regular file named :file:`dandiset.yaml` will only be represented by a
    `DandisetMetadataFile` instance if it is at the root of the Dandiset.

    A regular file that is not of a known type will be represented by a
    `GenericAsset` instance.
    """
    filepath = Path(filepath)
    if dandiset_path is not None:
        path = filepath.relative_to(dandiset_path).as_posix()
        if path == ".":
            raise ValueError("Dandi file path cannot equal Dandiset path")
    else:
        path = filepath.name
    if filepath.is_dir():
        if not any(filepath.iterdir()):
            raise UnknownAssetError("Empty directories cannot be assets")
        for dirclass in LocalDirectoryAsset.__subclasses__():
            if filepath.suffix in dirclass.EXTENSIONS:
                return dirclass(filepath=filepath, path=path)  # type: ignore[abstract]
        raise UnknownAssetError(
            f"Directory has unrecognized suffix {filepath.suffix!r}"
        )
    elif path == dandiset_metadata_file:
        return DandisetMetadataFile(filepath=filepath)
    else:
        for fileclass in LocalFileAsset.__subclasses__():
            if filepath.suffix in fileclass.EXTENSIONS:
                return fileclass(filepath=filepath, path=path)  # type: ignore[abstract]
        return GenericAsset(filepath=filepath, path=path)


def _upload_blob_part(
    storage_session: RESTFullAPIClient,
    fp: BinaryIO,
    lock: Lock,
    etagger: DandiETag,
    asset_path: str,
    part: dict,
) -> dict:
    etag_part = etagger.get_part(part["part_number"])
    if part["size"] != etag_part.size:
        raise RuntimeError(
            f"Server and client disagree on size of upload part"
            f" {part['part_number']}; server says {part['size']},"
            f" client says {etag_part.size}"
        )
    with lock:
        fp.seek(etag_part.offset)
        chunk = fp.read(part["size"])
    if len(chunk) != part["size"]:
        raise RuntimeError(
            f"End of file {fp.name} reached unexpectedly early:"
            f" read {len(chunk)} bytes of out of an expected {part['size']}"
        )
    lgr.debug(
        "%s: Uploading part %d/%d (%d bytes)",
        asset_path,
        part["part_number"],
        etagger.part_qty,
        part["size"],
    )
    r = storage_session.put(
        part["upload_url"],
        data=chunk,
        json_resp=False,
        retry_statuses=[500],
    )
    server_etag = r.headers["ETag"].strip('"')
    lgr.debug(
        "%s: Part upload finished ETag=%s Content-Length=%s",
        asset_path,
        server_etag,
        r.headers.get("Content-Length"),
    )
    client_etag = etagger.get_part_etag(etag_part)
    if server_etag != client_etag:
        raise RuntimeError(
            f"Server and client disagree on ETag of upload part"
            f" {part['part_number']}; server says"
            f" {server_etag}, client says {client_etag}"
        )
    return {
        "part_number": part["part_number"],
        "size": part["size"],
        "etag": server_etag,
    }


def _upload_zarr_file(
    storage_session: RESTFullAPIClient, path: Path, upload_url: str
) -> int:
    with path.open("rb") as fp:
        storage_session.put(upload_url, data=fp, json_resp=False)
    return path.stat().st_size


def _check_required_fields(d: dict, required: List[str]) -> List[str]:
    errors: List[str] = []
    for f in required:
        v = d.get(f, None)
        if not v or (isinstance(v, str) and not v.strip()):
            errors += [f"Required field {f!r} has no value"]
        if v in ("REQUIRED", "PLACEHOLDER"):
            errors += [f"Required field {f!r} has value {v!r}"]
    return errors


@dataclass
class EntryUploadTracker:
    """
    Class for keeping track of `LocalZarrEntry` instances to upload

    :meta private:
    """

    total_size: int = 0
    digested_entries: List[Tuple[LocalZarrEntry, str]] = field(default_factory=list)
    fresh_entries: List[LocalZarrEntry] = field(default_factory=list)

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
) -> Optional[Tuple[LocalZarrEntry, str]]:
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
