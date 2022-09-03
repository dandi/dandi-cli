from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
from threading import Lock
from typing import Any, BinaryIO, Generic, Optional
from xml.etree.ElementTree import fromstring

from dandischema.digests.dandietag import DandiETag
from dandischema.models import BareAsset, CommonModel
from dandischema.models import Dandiset as DandisetMeta
from dandischema.models import get_schema_version
from etelemetry import get_project
from nwbinspector import Importance, inspect_nwb, load_config
from nwbinspector.utils import get_package_version
from packaging.version import Version
from pydantic import ValidationError
import requests

from dandi import get_logger
from dandi.dandiapi import RemoteAsset, RemoteDandiset, RESTFullAPIClient
from dandi.metadata import get_default_metadata, nwb2asset
from dandi.misctypes import DUMMY_DIGEST, Digest, P
from dandi.pynwb_utils import validate as pynwb_validate
from dandi.support.digests import get_dandietag, get_digest
from dandi.utils import yaml_load

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
    ) -> list[str]:
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
    ) -> list[str]:
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
    ) -> list[str]:
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
        metadata: dict[str, Any],
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
        metadata: dict[str, Any],
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
        metadata: dict[str, Any],
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
    ) -> list[str]:
        errors: list[str] = pynwb_validate(self.filepath, devel_debug=devel_debug)
        if schema_version is not None:
            errors.extend(
                super().get_validation_errors(
                    schema_version=schema_version, devel_debug=devel_debug
                )
            )
        else:
            # make sure that we have some basic metadata fields we require
            try:
                # Ensure latest version of NWB Inspector is installed and used client-side
                try:
                    max_version = Version(
                        get_project(repo="NeurodataWithoutBorders/nwbinspector")[
                            "version"
                        ]
                    )
                    current_version = get_package_version(name="nwbinspector")

                    if current_version < max_version:
                        errors.append(
                            f"NWB Inspector version {current_version} is installed - please "
                            f"use the latest release of the NWB Inspector ({max_version}) "
                            "when performing `dandi validate`. To update, run "
                            "`pip install -U nwbinspector` if you installed it with `pip`."
                        )
                        return errors

                except Exception as e:  # In case of no internet connection or other error
                    lgr.warning(
                        "Failed to retrieve NWB Inspector version due to %s: %s",
                        type(e).__name__,
                        str(e),
                    )

                # Run NWB Inspector with 'dandi' config
                # CRITICAL errors and above are equivalent to validation errors
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
    pass


class GenericAsset(LocalFileAsset):
    """
    Representation of a generic regular file, one that is not of any known type
    """

    pass


class LocalDirectoryAsset(LocalAsset, Generic[P]):
    """
    Representation of a directory that can be uploaded to a DANDI Archive as
    a single asset of a Dandiset.  It is generic in ``P``, bound to
    `dandi.misctypes.BasePath`.
    """

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


def _check_required_fields(d: dict, required: list[str]) -> list[str]:
    errors: list[str] = []
    for f in required:
        v = d.get(f, None)
        if not v or (isinstance(v, str) and not v.strip()):
            errors += [f"Required field {f!r} has no value"]
        if v in ("REQUIRED", "PLACEHOLDER"):
            errors += [f"Required field {f!r} has value {v!r}"]
    return errors
