from abc import ABC, abstractmethod
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
from threading import Lock
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Union
from xml.etree.ElementTree import fromstring

from dandischema.digests.dandietag import DandiETag
from dandischema.models import BareAsset, CommonModel
from dandischema.models import Dandiset as DandisetMeta
from dandischema.models import get_schema_version
from pydantic import ValidationError
import requests
import zarr

from . import get_logger
from .consts import MAX_ZARR_DEPTH, ZARR_MIME_TYPE, dandiset_metadata_file
from .dandiapi import RemoteAsset, RemoteDandiset, RESTFullAPIClient
from .exceptions import UnknownSuffixError
from .metadata import get_default_metadata, get_metadata, nwb2asset
from .misctypes import DUMMY_DIGEST, Digest
from .pynwb_utils import validate as pynwb_validate
from .support.digests import get_dandietag, get_digest
from .utils import ensure_datetime, yaml_load
from .validate import _check_required_fields

lgr = get_logger()

# TODO -- should come from schema.  This is just a simplistic example for now
_required_dandiset_metadata_fields = ["identifier", "name", "description"]
_required_nwb_metadata_fields = ["subject_id"]


@dataclass
class DandiFile(ABC):
    #: Path to node on disk
    filepath: Path

    def get_size(self) -> int:
        return os.path.getsize(self.filepath)

    def get_mtime(self) -> datetime:
        # TODO: Should this be overridden for LocalDirectoryAsset?
        return ensure_datetime(self.filepath.stat().st_mtime)

    @abstractmethod
    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        ignore_errors: bool = True,
    ) -> CommonModel:
        ...

    @abstractmethod
    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> List[str]:
        ...


class DandisetMetadataFile(DandiFile):
    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        ignore_errors: bool = True,
    ) -> DandisetMeta:
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


@dataclass
class LocalAsset(DandiFile):
    #: Forward-slash-separated path relative to root of Dandiset
    path: str

    @abstractmethod
    def get_etag(self) -> Digest:
        ...

    @abstractmethod
    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
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
            # TODO: Only do this for NWB files
            # make sure that we have some basic metadata fields we require
            try:
                meta = get_metadata(self.filepath)
            except Exception as e:
                if devel_debug:
                    raise
                lgr.warning(
                    "Failed to read metadata in %s: %s",
                    self.filepath,
                    e,
                    extra={"validating": True},
                )
                return [f"Failed to read metadata: {e}"]
            return _check_required_fields(meta, _required_nwb_metadata_fields)

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

        :dandiset RemoteDandiset:
            the Dandiset to which the file will be uploaded
        :param dict metadata:
            Metadata for the uploaded asset.  The "path" field will be set to
            the value of the instance's ``path`` attribute if no such field is
            already present.
        :param int jobs: Number of threads to use for uploading; defaults to 5
        :param RemoteAsset replacing: If set, replace the given asset, which
            must have the same path as the new asset
        :rtype: RemoteAsset
        """
        for status in self.iter_upload(
            dandiset, metadata, jobs=jobs, replacing=replacing
        ):
            if status["status"] == "done":
                return status["asset"]
        raise AssertionError("iter_upload() finished without returning 'done'")

    @abstractmethod
    def iter_upload(
        self,
        dandiset: RemoteDandiset,
        metadata: Dict[str, Any],
        jobs: Optional[int] = None,
        replacing: Optional[RemoteAsset] = None,
    ) -> Iterator[dict]:
        ...


class LocalFileAsset(LocalAsset):
    def get_etag(self) -> Digest:
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

        :dandiset RemoteDandiset:
            the Dandiset to which the file will be uploaded
        :param dict metadata:
            Metadata for the uploaded asset.  The "path" field will be set to
            the value of the instance's ``path`` attribute if no such field is
            already present.
        :param int jobs:
            Number of threads to use for uploading; defaults to 5
        :param RemoteAsset replacing: If set, replace the given asset, which
            must have the same path as the new asset
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
        total_size = self.get_size()
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
                                _upload_part,
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
            lgr.debug("%s: Replacing pre-existing asset")
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
    EXTENSIONS = [".nwb"]

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
        return pynwb_validate(
            self.filepath, devel_debug=devel_debug
        ) + super().get_validation_errors(
            schema_version=schema_version, devel_debug=devel_debug
        )


class GenericAsset(LocalFileAsset):
    EXTENSIONS = []

    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        metadata = get_default_metadata(self.filepath, digest=digest)
        metadata.path = self.path
        return metadata


class LocalDirectoryAsset(LocalAsset):
    def iterfiles(self) -> Iterator[Path]:
        dirs = deque([self.filepath])
        while dirs:
            for p in dirs.popleft().iterdir():
                if p.is_dir():
                    dirs.append(p)
                else:
                    yield p

    def get_size(self) -> int:
        return sum(p.stat().st_size for p in self.iterfiles())


class ZarrAsset(LocalDirectoryAsset):
    EXTENSIONS = [".ngff", ".zarr"]

    def get_etag(self) -> Digest:
        raise NotImplementedError
        # return Digest.dandi_zarr(get_zarr_checksum(self.filepath))

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
        raise NotImplementedError


def find_dandi_files(
    *paths: Union[str, Path],
    dandiset_path: Optional[Union[str, Path]] = None,
    allow_all: bool = False,
    include_metadata: bool = False,
) -> Iterator[DandiFile]:
    if dandiset_path is None:
        if len(paths) == 1 and os.path.isdir(paths[0]):
            dandiset_path = paths[0]
        else:
            raise ValueError(
                "dandiset_path must be set when not traversing a single directory"
            )
    path_queue = deque()
    for p in paths:
        p = Path(p)
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
                continue
            try:
                df = dandi_file(p, dandiset_path)
            except UnknownSuffixError:
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
    filepath = Path(filepath)
    if dandiset_path is not None:
        path = filepath.relative_to(dandiset_path).as_posix()
    else:
        path = filepath.name
    if filepath.is_dir():
        for dirclass in LocalDirectoryAsset.__subclasses__():
            if filepath.suffix in dirclass.EXTENSIONS:
                return dirclass(filepath=filepath, path=path)
        raise UnknownSuffixError(
            f"Directory has unrecognized suffix {filepath.suffix!r}"
        )
    elif path == dandiset_metadata_file:
        return DandisetMetadataFile(filepath=filepath)
    else:
        for fileclass in LocalFileAsset.__subclasses__():
            if filepath.suffix in fileclass.EXTENSIONS:
                return fileclass(filepath=filepath, path=path)
            return GenericAsset(filepath=filepath, path=path)


def _upload_part(
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
