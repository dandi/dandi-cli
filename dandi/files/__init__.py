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

from collections import deque
from collections.abc import Iterator
from pathlib import Path
from typing import Optional

from dandi import get_logger
from dandi.consts import dandiset_metadata_file
from dandi.exceptions import UnknownAssetError

from .bases import (
    DandiFile,
    DandisetMetadataFile,
    GenericAsset,
    LocalAsset,
    LocalDirectoryAsset,
    LocalFileAsset,
    NWBAsset,
    VideoAsset,
)
from .zarr import LocalZarrEntry, ZarrAsset, ZarrStat

__all__ = [
    "DandiFile",
    "DandisetMetadataFile",
    "LocalAsset",
    "LocalFileAsset",
    "NWBAsset",
    "VideoAsset",
    "GenericAsset",
    "LocalDirectoryAsset",
    "LocalZarrEntry",
    "ZarrStat",
    "ZarrAsset",
    "find_dandi_files",
    "dandi_file",
]

lgr = get_logger()


def find_dandi_files(
    *paths: str | Path,
    dandiset_path: Optional[str | Path] = None,
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
    filepath: str | Path, dandiset_path: Optional[str | Path] = None
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
