from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Union

from . import get_logger
from .consts import dandiset_metadata_file
from .exceptions import UnknownSuffixError

lgr = get_logger()


@dataclass
class DandiFile:
    #: Path to node on disk
    filepath: Path


class DandisetMetadataFile(DandiFile):
    pass


@dataclass
class LocalAsset(DandiFile):
    #: Forward-slash-separated path relative to root of Dandiset
    path: str


class LocalFileAsset(LocalAsset):
    pass


class NWBAsset(LocalFileAsset):
    EXTENSIONS = [".nwb"]


class GenericAsset(LocalFileAsset):
    EXTENSIONS = []


class LocalDirectoryAsset(LocalAsset):
    pass


class ZarrAsset(LocalDirectoryAsset):
    EXTENSIONS = [".ngff", ".zarr"]


def find_dandi_files(
    dirpath: Union[str, Path],
    *,
    dandiset_path: Optional[Union[str, Path]] = None,
    allow_all: bool = False,
    include_metadata: bool = False,
) -> Iterator[DandiFile]:
    if dandiset_path is None:
        dandiset_path = dirpath
    else:
        try:
            Path(dandiset_path).relative_to(dirpath)
        except ValueError:
            raise ValueError("dirpath must be within dandiset_path")
    dirs = deque([Path(dirpath)])
    while dirs:
        for p in dirs.popleft().iterdir():
            if p.name.startswith("."):
                continue
            if p.is_dir():
                if p.is_symlink():
                    lgr.warning(
                        "%s: Ignoring unsupported symbolic link to directory", p
                    )
                    continue
                try:
                    df = dandi_file(p, dandiset_path)
                except UnknownSuffixError:
                    dirs.append(p)
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
