from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import ExitStack
from dataclasses import dataclass, field
from itertools import zip_longest
import os.path
from pathlib import Path, PurePosixPath
import posixpath
import re
from typing import NewType, Optional

from . import get_logger
from .dandiapi import DandiAPIClient, RemoteAsset, RemoteDandiset
from .dandiarchive import DandisetURL, parse_dandi_url
from .dandiset import Dandiset
from .exceptions import NotFoundError
from .files import DandisetMetadataFile, LocalAsset, find_dandi_files

lgr = get_logger()

#: A /-separated path to an asset, relative to the root of the Dandiset
AssetPath = NewType("AssetPath", str)


@dataclass
class File:
    path: AssetPath


@dataclass
class Folder:
    #: A /-separated path to an asset folder, relative to the root of the
    #: Dandiset
    path: str
    #: All file paths under the folder recursively, as /-separated paths
    #: relative to the folder path
    relcontents: list[str]


@dataclass
class Movement:
    """A movement/renaming of an asset"""

    #: The asset's original path
    src: AssetPath
    #: The asset's destination path
    dest: AssetPath
    #: Whether to skip this operation because an asset already exists at the
    #: destination
    skip: bool = False
    #: Whether to delete the asset at the destination before moving
    delete: bool = False

    @property
    def dest_exists(self) -> bool:
        """True iff an asset already exists at the destination"""
        return self.skip or self.delete


class Mover(ABC):
    """
    An abstract base class for calculating and performing asset moves/renames
    """

    @property
    def columns(self) -> tuple[str, ...]:
        """Names of the columns in the pyout display"""
        return ("source", "target") + self.updating_fields

    @property
    def updating_fields(self) -> tuple[str, ...]:
        """Names of the pyout fields that are updated as things progress"""
        return (self.status_field, "message")

    @property
    @abstractmethod
    def status_field(self) -> str:
        """
        Name of the pyout status column (either ``"local"`` or ``"remote"``)
        """
        ...

    @abstractmethod
    def calculate_moves(self, *srcs: str, dest: str, existing: str) -> list[Movement]:
        """
        Given a sequence of input source paths and a destination path, return a
        sorted list of all assets that will be moved/renamed
        """
        ...

    @abstractmethod
    def calculate_moves_by_regex(
        self, find: str, replace: str, existing: str
    ) -> list[Movement]:
        """
        Given a regular expression and a replacement string, return a sorted
        list of all assets that will be moved/renamed
        """
        ...

    def process_moves_pyout(
        self, plan: list[Movement], dry_run: bool = False
    ) -> Iterator[dict]:
        """Yield a `dict` to pass to pyout for each `Movement` in ``plan``"""
        for m in plan:
            yield {
                "source": m.src,
                "target": m.dest,
                self.updating_fields: self.process_movement(m, dry_run),
            }

    def process_moves_debug(
        self, plan: list[Movement], dry_run: bool = False
    ) -> Iterator[Iterator[dict]]:
        """
        For each `Movement` in ``plan``, yield an iterator of `dict`\\s to
        print for each step of the movement operation.
        """
        for m in plan:
            yield (
                {"source": m.src, "target": m.dest, **d}
                for d in self.process_movement(m, dry_run)
            )

    @abstractmethod
    def process_movement(
        self, m: Movement, dry_run: bool = False
    ) -> Iterator[dict[str, str]]:
        """Perform the `Movement` and yield a `dict` for each step"""
        ...


class LocalizedMover(Mover):
    """
    A `Mover` for moving only the assets in one location (i.e., either local or
    remote)
    """

    #: A relative path denoting the subdirectory of the Dandiset in which we
    #: are operating
    subpath: Path

    @property
    @abstractmethod
    def placename(self) -> str:
        """
        A description of the mover to show in messages (either ``"local"`` or
        ``"remote"``)
        """
        ...

    @abstractmethod
    def get_assets(self, subpath_only: bool = False) -> Iterator[tuple[AssetPath, str]]:
        """
        Yield all available assets as ``(asset_path, relpath)`` pairs, where
        ``asset_path`` is a ``/``-separated path relative to the root of the
        Dandiset and ``relpath`` is a ``/``-separated path to that asset,
        relative to `subpath` (For assets outside of `subpath`, ``relpath``
        starts with ``"../"``).  If ``subpath_only`` is true, only assets
        underneath `subpath` are returned.
        """
        ...

    @abstractmethod
    def get_path(self, path: str, is_src: bool = True) -> File | Folder:
        """
        Return the asset or folder of assets at ``path`` (relative to
        `subpath`) as a `File` or `Folder` instance.  If there is nothing at
        the given path, raises `NotFoundError`.

        If the path points to a folder, its `~Folder.relcontents` attribute
        will be populated iff ``is_src`` is given.
        """
        ...

    @abstractmethod
    def is_dir(self, path: AssetPath) -> bool:
        """Returns true if the given path points to a directory"""
        ...

    @abstractmethod
    def is_file(self, path: AssetPath) -> bool:
        """Returns true if the given path points to an asset"""
        ...

    @abstractmethod
    def move(self, src: AssetPath, dest: AssetPath) -> None:
        """
        Move the asset at path ``src`` to path ``dest`` (which can be assumed
        to not exist)
        """
        ...

    @abstractmethod
    def delete(self, path: AssetPath) -> None:
        """Delete the asset at ``path``"""
        ...

    def resolve(self, path: str) -> tuple[AssetPath, bool]:
        """
        Convert an input path (relative to `subpath`, possibly starting with
        ``../``) to a /-separated path relative to the root of the Dandiset,
        plus a boolean that is true iff ``path`` ended with a slash
        """
        p = PurePosixPath(
            posixpath.normpath(posixpath.join(self.subpath.as_posix(), path))
        )
        if p.parts and p.parts[0] == os.pardir:
            raise ValueError(f"{path!r} is outside of Dandiset")
        return (AssetPath(str(p)), path.endswith("/"))

    def calculate_moves(self, *srcs: str, dest: str, existing: str) -> list[Movement]:
        """
        Given a sequence of input source paths and a destination path, return a
        sorted list of all assets that will be moved/renamed
        """
        destpath, dest_is_dir = self.resolve(dest)
        destobj: File | Folder | None
        try:
            destobj = self.get_path(dest, is_src=False)
        except NotFoundError:
            if dest_is_dir or len(srcs) > 1:
                destobj = Folder(destpath, [])
            elif len(srcs) == 1:
                destobj = None
            else:
                destobj = File(destpath)
        if isinstance(destobj, File) and len(srcs) > 1:
            raise ValueError(
                "Cannot take multiple source paths when destination is a file"
            )
        moves: dict[AssetPath, AssetPath] = {}
        for s in map(self.get_path, srcs):
            if destobj is None:
                if isinstance(s, File):
                    destobj = File(destpath)
                else:
                    destobj = Folder(destpath, [])
            if isinstance(s, File):
                if isinstance(destobj, File):
                    pdest = AssetPath(destobj.path)
                else:
                    pdest = AssetPath(
                        posixpath.normpath(
                            posixpath.join(destobj.path, posixpath.basename(s.path))
                        )
                    )
                if s.path == pdest:
                    lgr.debug(
                        "Would move %s asset %r to itself; ignoring",
                        self.placename,
                        s.path,
                    )
                else:
                    moves[s.path] = pdest
                    lgr.debug(
                        "Calculated %s move: %r -> %r",
                        self.placename,
                        s.path,
                        pdest,
                    )
            else:
                if isinstance(destobj, File):
                    raise ValueError(f"Cannot move folder {s.path!r} to a file path")
                else:
                    for p in s.relcontents:
                        p1 = posixpath.normpath(posixpath.join(s.path, p))
                        p2 = posixpath.normpath(
                            posixpath.join(destobj.path, posixpath.basename(s.path), p)
                        )
                        if p1 == p2:
                            lgr.debug(
                                "Would move %s asset %r to itself; ignoring",
                                self.placename,
                                p1,
                            )
                            continue
                        moves[AssetPath(p1)] = AssetPath(p2)
                        lgr.debug(
                            "Calculated %s move: %r -> %r", self.placename, p1, p2
                        )
        return self.compile_moves(moves, existing)

    def calculate_moves_by_regex(
        self, find: str, replace: str, existing: str
    ) -> list[Movement]:
        """
        Given a regular expression and a replacement string, return a sorted
        list of all assets that will be moved/renamed
        """
        rgx = re.compile(find)
        moves: dict[AssetPath, AssetPath] = {}
        rev: dict[AssetPath, AssetPath] = {}
        any_matched = False
        for asset_path, relpath in self.get_assets(subpath_only=True):
            m = rgx.search(relpath)
            if m:
                any_matched = True
                dest, _ = self.resolve(
                    relpath[: m.start()] + m.expand(replace) + relpath[m.end() :]
                )
                if asset_path == dest:
                    lgr.debug(
                        "Would move %s asset %r to itself; ignoring",
                        self.placename,
                        asset_path,
                    )
                    continue
                lgr.debug(
                    "Calculated %s move: %r -> %r", self.placename, asset_path, dest
                )
                if dest in rev:
                    p1, p2 = sorted([rev[dest], asset_path])
                    raise ValueError(
                        f"{self.placename.title()} assets {p1!r} and {p2!r}"
                        f" would both be moved to {dest!r}"
                    )
                moves[asset_path] = dest
                rev[dest] = asset_path
        if not any_matched:
            raise ValueError(
                f"Regular expression {find!r} did not match any {self.placename} paths"
            )
        return self.compile_moves(moves, existing)

    def compile_moves(
        self, moves: dict[AssetPath, AssetPath], existing: str
    ) -> list[Movement]:
        """
        Given a `dict` mapping source paths to destination paths, produce a
        sorted list of `Movement` instances.
        """
        motions: list[Movement] = []
        for src, dest in sorted(moves.items()):
            if self.is_dir(dest):
                raise ValueError(
                    f"Cannot move {src!r} to {dest!r}, as {self.placename}"
                    " destination is a directory"
                )
            elif self.is_file(dest):
                if existing == "overwrite":
                    motions.append(Movement(src, dest, delete=True))
                elif existing == "skip":
                    motions.append(Movement(src, dest, skip=True))
                else:
                    raise ValueError(
                        f"Cannot move {src!r} to {dest!r}, as {self.placename}"
                        " destination already exists"
                    )
            else:
                motions.append(Movement(src, dest))
        return motions

    def process_movement(
        self, m: Movement, dry_run: bool = False
    ) -> Iterator[dict[str, str]]:
        """Perform the `Movement` and yield a `dict` for each step"""
        if m.skip:
            lgr.debug(
                "Would move %r to %r, but destination exists; skipping", m.src, m.dest
            )
            yield {self.status_field: "skipped", "message": "Destination exists"}
            return
        if m.delete:
            yield {self.status_field: "Deleting"}
            lgr.debug("Moving %r to %r: destination exists, so deleting", m.src, m.dest)
            if not dry_run:
                try:
                    self.delete(m.dest)
                except Exception as e:
                    yield {
                        self.status_field: "Error",
                        "message": f"Error unlinking destination: {type(e).__name__}: {e}",
                    }
                    return
        yield {self.status_field: "Moving"}
        lgr.debug("Moving %r to %r", m.src, m.dest)
        if not dry_run:
            try:
                self.move(m.src, m.dest)
            except Exception as e:
                yield {
                    self.status_field: "Error",
                    "message": f"Error moving: {type(e).__name__}: {e}",
                }
                return
        yield {self.status_field: "Moved"}


@dataclass
class LocalMover(LocalizedMover):
    """A `Mover` for moving only the assets in a local Dandiset"""

    #: The path to the root of the Dandiset
    dandiset_path: Path

    #: A relative path denoting the subdirectory of the Dandiset in which we
    #: are operating
    subpath: Path

    @property
    def status_field(self) -> str:
        """Name of the pyout status column"""
        return "local"

    @property
    def placename(self) -> str:
        """A description of the mover to show in messages"""
        return "local"

    def get_assets(self, subpath_only: bool = False) -> Iterator[tuple[AssetPath, str]]:
        """
        Yield all available assets as ``(asset_path, relpath)`` pairs, where
        ``asset_path`` is a ``/``-separated path relative to the root of the
        Dandiset and ``relpath`` is a ``/``-separated path to that asset,
        relative to `subpath` (For assets outside of `subpath`, ``relpath``
        starts with ``"../"``).  If ``subpath_only`` is true, only assets
        underneath `subpath` are returned.
        """
        root = self.dandiset_path
        if subpath_only:
            root /= self.subpath
        for df in find_dandi_files(
            root,
            dandiset_path=self.dandiset_path,
            allow_all=True,
        ):
            if isinstance(df, DandisetMetadataFile):
                continue
            assert isinstance(df, LocalAsset)
            relpath = posixpath.relpath(df.path, self.subpath.as_posix())
            yield (AssetPath(df.path), relpath)

    def get_path(self, path: str, is_src: bool = True) -> File | Folder:
        """
        Return the asset or folder of assets at ``path`` (relative to
        `subpath`) as a `File` or `Folder` instance.  If there is nothing at
        the given path, raises `NotFoundError`.

        If the path points to a folder, its `~Folder.relcontents` attribute
        will be populated iff ``is_src`` is given.
        """
        rpath, needs_dir = self.resolve(path)
        p = self.dandiset_path / rpath
        if not p.exists():
            raise NotFoundError(f"No asset at local path {path!r}")
        if p.is_dir():
            if is_src:
                if p == self.dandiset_path / self.subpath:
                    raise ValueError("Cannot move current working directory")
                files = [
                    df.filepath.relative_to(p).as_posix()
                    for df in find_dandi_files(
                        p, dandiset_path=self.dandiset_path, allow_all=True
                    )
                    if isinstance(df, LocalAsset)
                ]
            else:
                files = []
            return Folder(rpath, files)
        elif needs_dir:
            raise ValueError(f"Local path {path!r} is a file")
        else:
            return File(rpath)

    def is_dir(self, path: AssetPath) -> bool:
        """Returns true if the given path points to a directory"""
        p = self.dandiset_path / path
        return p.is_dir() and p.suffix not in (".ngff", ".zarr")

    def is_file(self, path: AssetPath) -> bool:
        """Returns true if the given path points to an asset"""
        p = self.dandiset_path / path
        return (
            p.is_file()
            or p.is_symlink()
            or (p.is_dir() and p.suffix in (".ngff", ".zarr"))
        )

    def move(self, src: AssetPath, dest: AssetPath) -> None:
        """
        Move the asset at path ``src`` to path ``dest`` (which can be assumed
        to not exist)
        """
        lgr.debug("Moving local file %r to %r", src, dest)
        target = self.dandiset_path / dest
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            (self.dandiset_path / src).rename(target)
        except Exception as e:
            lgr.error(
                "Failed to move local file %r to %r: %s: %s",
                src,
                dest,
                type(e).__name__,
                e,
            )
            raise
        # Remove residual empty directories up to subpath
        d = (self.dandiset_path / src).parent
        while d != (self.dandiset_path / self.subpath) and not any(d.iterdir()):
            try:
                d.rmdir()
            except OSError:
                break
            d = d.parent

    def delete(self, path: AssetPath) -> None:
        """Delete the asset at ``path``"""
        lgr.debug("Deleting local file %r", path)
        try:
            (self.dandiset_path / path).unlink()
        except Exception as e:
            lgr.error(
                "Failed to delete local file %r: %s: %s", path, type(e).__name__, e
            )
            raise


@dataclass
class RemoteMover(LocalizedMover):
    """
    A `Mover` for moving only the assets in a remote Dandiset.  It cannot be
    reused after performing a set of moves.
    """

    #: The client object for the remote Dandiset being operated on
    dandiset: RemoteDandiset

    #: A relative path denoting the subdirectory of the Dandiset in which we
    #: are operating
    subpath: Path

    #: The `~LocalMover.dandiset_path` of the corresponding `LocalMover` when
    #: inside a `LocalRemoteMover`
    local_dandiset_path: Optional[Path] = None

    #: A collection of all assets in the Dandiset, keyed by their paths
    assets: dict[AssetPath, RemoteAsset] = field(init=False)

    def __post_init__(self) -> None:
        lgr.info("Fetching list of assets for Dandiset %s", self.dandiset.identifier)
        self.assets = {}
        for asset in self.dandiset.get_assets():
            self.assets[AssetPath(asset.path.strip("/"))] = asset

    @property
    def status_field(self) -> str:
        """Name of the pyout status column"""
        return "remote"

    @property
    def placename(self) -> str:
        """A description of the mover to show in messages"""
        return "remote"

    def get_assets(self, subpath_only: bool = False) -> Iterator[tuple[AssetPath, str]]:
        """
        Yield all available assets as ``(asset_path, relpath)`` pairs, where
        ``asset_path`` is a ``/``-separated path relative to the root of the
        Dandiset and ``relpath`` is a ``/``-separated path to that asset,
        relative to `subpath` (For assets outside of `subpath`, ``relpath``
        starts with ``"../"``).  If ``subpath_only`` is true, only assets
        underneath `subpath` are returned.
        """
        for path in self.assets.keys():
            relpath = posixpath.relpath(path, self.subpath.as_posix())
            if subpath_only and relpath.startswith("../"):
                continue
            yield (path, relpath)

    def get_path(self, path: str, is_src: bool = True) -> File | Folder:
        """
        Return the asset or folder of assets at ``path`` (relative to
        `subpath`) as a `File` or `Folder` instance.  If there is nothing at
        the given path, raises `NotFoundError`.

        If the path points to a folder, its `~Folder.relcontents` attribute
        will be populated iff ``is_src`` is given.
        """
        rpath, needs_dir = self.resolve(path)
        relcontents: list[str] = []
        file_found = False
        if rpath == self.subpath.as_posix():
            if is_src:
                raise ValueError("Cannot move current working directory")
            else:
                return Folder(rpath, [])
        for p in self.assets.keys():
            if p == rpath:
                if needs_dir:
                    file_found = True
                else:
                    return File(rpath)
            elif p.startswith(f"{rpath}/"):
                if is_src:
                    relcontents.append(posixpath.relpath(p, rpath))
                else:
                    return Folder(rpath, [])
        if relcontents:
            return Folder(rpath, relcontents)
        if needs_dir and file_found:
            raise ValueError(f"Remote path {path!r} is a file")
        elif (
            not needs_dir
            and not is_src
            and self.local_dandiset_path is not None
            and (self.local_dandiset_path / rpath).is_dir()
        ):
            # If the user does `move --work-on=both somepath somedir`, where
            # `somedir` exists locally but not remotely, treat `somedir` as a
            # remote directory.
            return Folder(rpath, [])
        else:
            raise NotFoundError(f"No asset at remote path {path!r}")

    def is_dir(self, path: AssetPath) -> bool:
        """Returns true if the given path points to a directory"""
        return any(p.startswith(f"{path}/") for p in self.assets.keys())

    def is_file(self, path: AssetPath) -> bool:
        """Returns true if the given path points to an asset"""
        return path in self.assets

    def move(self, src: AssetPath, dest: AssetPath) -> None:
        """
        Move the asset at path ``src`` to path ``dest`` (which can be assumed
        to not exist)
        """
        lgr.debug("Moving remote asset %r to %r", src, dest)
        assert src in self.assets
        try:
            self.assets[src].rename(dest)
        except Exception as e:
            lgr.error(
                "Failed to move remote asset %r to %r: %s: %s",
                src,
                dest,
                type(e).__name__,
                e,
            )
            raise

    def delete(self, path: AssetPath) -> None:
        """Delete the asset at ``path``"""
        lgr.debug("Deleting remote asset %r", path)
        assert path in self.assets
        try:
            self.assets[path].delete()
        except Exception as e:
            lgr.error(
                "Failed to delete remote asset %r: %s: %s", path, type(e).__name__, e
            )
            raise


@dataclass  # type: ignore[misc]
class LocalRemoteMover(Mover):
    """
    A `Mover` for moving the assets in a local Dandiset and the corresponding
    remote Dandiset simultaneously.  It cannot be reused after performing a set
    of moves.
    """

    #: The local `Mover`
    local: LocalMover

    #: The remote `Mover`
    remote: RemoteMover

    @property
    def updating_fields(self) -> tuple[str, ...]:
        """Names of the pyout fields that are updated as things progress"""
        return (self.local.status_field, self.remote.status_field, "message")

    @property
    def status_field(self) -> str:
        """
        Name of the pyout status column.

        This specific property should never be used.
        """
        return "both"

    def calculate_moves(self, *srcs: str, dest: str, existing: str) -> list[Movement]:
        """
        Given a sequence of input source paths and a destination path, return a
        sorted list of all assets that will be moved/renamed
        """
        local_moves = self.local.calculate_moves(*srcs, dest=dest, existing=existing)
        remote_moves = self.remote.calculate_moves(*srcs, dest=dest, existing=existing)
        self.compare_moves(local_moves, remote_moves)
        return local_moves

    def calculate_moves_by_regex(
        self, find: str, replace: str, existing: str
    ) -> list[Movement]:
        """
        Given a regular expression and a replacement string, return a sorted
        list of all assets that will be moved/renamed
        """
        local_moves = self.local.calculate_moves_by_regex(find, replace, existing)
        remote_moves = self.remote.calculate_moves_by_regex(find, replace, existing)
        self.compare_moves(local_moves, remote_moves)
        return local_moves

    def compare_moves(
        self, local_moves: list[Movement], remote_moves: list[Movement]
    ) -> None:
        """
        Given a list of `Movement` instances calculated by the local and remote
        `Mover`\\s, compare them and raise `AssetMismatchError` if there are
        any differences.
        """
        # Recall that the Movements are sorted by src path
        mismatches = []
        for lm, rm in zip_longest(local_moves, remote_moves):
            if rm is None:
                mismatches.append(f"Asset {lm.src!r} only exists locally")
            elif lm is None:
                mismatches.append(f"Asset {rm.src!r} only exists remotely")
            elif lm.src < rm.src:
                mismatches.append(f"Asset {lm.src!r} only exists locally")
            elif lm.src > rm.src:
                mismatches.append(f"Asset {rm.src!r} only exists remotely")
            elif lm.dest != rm.dest:
                mismatches.append(
                    f"Asset {lm.src!r} would be moved to {lm.dest!r} locally"
                    f" but to {rm.dest!r} remotely"
                )
            elif lm.dest_exists and not rm.dest_exists:
                mismatches.append(
                    f"Asset {lm.src!r} would be moved to {lm.dest!r}, which"
                    " exists locally but not remotely"
                )
            elif not lm.dest_exists and rm.dest_exists:
                mismatches.append(
                    f"Asset {lm.src!r} would be moved to {lm.dest!r}, which"
                    " exists remotely but not locally"
                )
        if mismatches:
            raise AssetMismatchError(mismatches)

    def process_movement(
        self, m: Movement, dry_run: bool = False
    ) -> Iterator[dict[str, str]]:
        """Perform the `Movement` and yield a `dict` for each step"""
        for state in self.local.process_movement(m, dry_run):
            yield state
            if state[self.local.status_field].lower() == "error":
                yield {self.remote.status_field: "skipped"}
                return
        yield from self.remote.process_movement(m, dry_run)


def move(
    *srcs: str,
    dest: str,
    regex: bool = False,
    existing: str = "error",
    dandi_instance: str = "dandi",
    dandiset: Path | str | None = None,
    work_on: str = "auto",
    devel_debug: bool = False,
    jobs: Optional[int] = None,
    dry_run: bool = False,
) -> None:
    if not srcs:
        raise ValueError("No source paths given")
    if dandiset is None:
        dandiset = Path()
    with ExitStack() as stack:
        mover: Mover
        client: Optional[DandiAPIClient] = None
        if work_on == "auto":
            work_on = "remote" if isinstance(dandiset, str) else "both"
        if work_on == "both":
            if isinstance(dandiset, str):
                raise TypeError("`dandiset` must be a Path when work_on='both'")
            local_ds, subpath = find_dandiset_and_subpath(dandiset)
            client = DandiAPIClient.for_dandi_instance(dandi_instance)
            stack.enter_context(client)
            remote_ds = client.get_dandiset(
                local_ds.identifier, version_id="draft", lazy=False
            )
            mover = LocalRemoteMover(
                local=LocalMover(
                    dandiset_path=Path(local_ds.path),
                    subpath=subpath,
                ),
                remote=RemoteMover(
                    dandiset=remote_ds,
                    subpath=subpath,
                    local_dandiset_path=Path(local_ds.path),
                ),
            )
        elif work_on == "remote":
            if isinstance(dandiset, str):
                url = parse_dandi_url(dandiset)
                if not isinstance(url, DandisetURL):
                    raise ValueError("URL does not point to a Dandiset")
                client = url.get_client()
                stack.enter_context(client)
                rds = url.get_dandiset(client, lazy=False)
                assert rds is not None
                remote_ds = rds
                subpath = Path()
            else:
                local_ds, subpath = find_dandiset_and_subpath(dandiset)
                client = DandiAPIClient.for_dandi_instance(dandi_instance)
                stack.enter_context(client)
                remote_ds = client.get_dandiset(
                    local_ds.identifier, version_id="draft", lazy=False
                )
            mover = RemoteMover(dandiset=remote_ds, subpath=subpath)
        elif work_on == "local":
            if isinstance(dandiset, str):
                raise TypeError("`dandiset` must be a Path when work_on='both'")
            local_ds, subpath = find_dandiset_and_subpath(dandiset)
            mover = LocalMover(dandiset_path=Path(local_ds.path), subpath=subpath)
        else:
            raise ValueError(f"Invalid work_on value: {work_on!r}")
        if regex:
            try:
                (find,) = srcs
            except ValueError:
                raise ValueError(
                    "Cannot take multiple source paths when `regex` is True"
                )
            plan = mover.calculate_moves_by_regex(find, dest, existing=existing)
        else:
            plan = mover.calculate_moves(*srcs, dest=dest, existing=existing)
        if not plan:
            lgr.info("Nothing to move")
            return
        if not dry_run and client is not None:
            client.dandi_authenticate()
        if devel_debug:
            for gen in mover.process_moves_debug(plan, dry_run):
                for r in gen:
                    print(r, flush=True)
        else:
            from .support import pyout as pyouts

            pyout_style = pyouts.get_style(hide_if_missing=False)
            out = pyouts.LogSafeTabular(
                style=pyout_style, columns=mover.columns, max_workers=jobs
            )
            with out:
                for r in mover.process_moves_pyout(plan, dry_run):
                    out(r)


def find_dandiset_and_subpath(path: Path) -> tuple[Dandiset, Path]:
    """
    Find the Dandiset rooted at ``path`` or one of its parents, and return the
    Dandiset along with ``path`` made relative to the Dandiset root
    """
    path = path.absolute()
    ds = Dandiset.find(path)
    if ds is None:
        raise ValueError(f"{path}: not a Dandiset")
    return (ds, path.relative_to(ds.path))


class AssetMismatchError(ValueError):
    def __init__(self, mismatches: list[str]) -> None:
        self.mismatches = mismatches

    def __str__(self) -> str:
        return "Mismatch between local and remote Dandisets:\n" + "\n".join(
            f"- {msg}" for msg in self.mismatches
        )
