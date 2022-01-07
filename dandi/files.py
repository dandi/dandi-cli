from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterator, List, Optional, Union

from dandischema.models import BareAsset, CommonModel
from dandischema.models import Dandiset as DandisetMeta
from dandischema.models import get_schema_version
from pydantic import ValidationError
import zarr

from . import get_logger
from .consts import MAX_ZARR_DEPTH, dandiset_metadata_file
from .exceptions import UnknownSuffixError
from .metadata import get_default_metadata, get_metadata, nwb2asset
from .misctypes import DUMMY_DIGEST, Digest
from .pynwb_utils import validate as pynwb_validate
from .utils import yaml_load
from .validate import _check_required_fields

lgr = get_logger()

# TODO -- should come from schema.  This is just a simplistic example for now
_required_dandiset_metadata_fields = ["identifier", "name", "description"]
_required_nwb_metadata_fields = ["subject_id"]


@dataclass
class DandiFile(ABC):
    #: Path to node on disk
    filepath: Path

    @abstractmethod
    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        allow_any_path: bool = True,
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
        allow_any_path: bool = True,
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
    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        allow_any_path: bool = True,
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


class LocalFileAsset(LocalAsset):
    pass


class NWBAsset(LocalFileAsset):
    EXTENSIONS = [".nwb"]

    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        allow_any_path: bool = True,
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
            if allow_any_path:
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
        allow_any_path: bool = True,
    ) -> BareAsset:
        metadata = get_default_metadata(self.filepath, digest=digest)
        metadata.path = self.path
        return metadata


class LocalDirectoryAsset(LocalAsset):
    pass


class ZarrAsset(LocalDirectoryAsset):
    EXTENSIONS = [".ngff", ".zarr"]

    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        allow_any_path: bool = True,
    ) -> BareAsset:
        raise NotImplementedError

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
