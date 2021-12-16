from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Union

from . import get_logger
from .consts import ASSET_FILE_EXTENSIONS, ZARR_DIR_EXTENSIONS, dandiset_metadata_file

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


class LocalZarrAsset(LocalAsset):
    pass


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
            path = p.relative_to(dandiset_path).as_posix()
            if p.is_dir():
                if p.is_symlink():
                    lgr.warning(
                        "%s: Ignoring unsupported symbolic link to directory", p
                    )
                    continue
                if p.suffix in ZARR_DIR_EXTENSIONS:
                    yield LocalZarrAsset(filepath=p, path=path)
                else:
                    dirs.append(p)
            elif p == dandiset_path / dandiset_metadata_file:
                if allow_all or include_metadata:
                    yield DandisetMetadataFile(filepath=p)
            elif allow_all or p.suffix in ASSET_FILE_EXTENSIONS:
                yield LocalFileAsset(filepath=p, path=path)
