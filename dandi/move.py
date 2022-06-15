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
from .files import LocalAsset, find_dandi_files

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
    src: AssetPath
    dest: AssetPath
    skip: bool = False
    delete: bool = False

    @property
    def dest_exists(self) -> bool:
        return self.skip or self.delete


class Mover(ABC):
    # Only good for one set of moves

    @property
    def columns(self) -> tuple[str, ...]:
        return ("source", "target") + self.updating_fields

    @property
    def updating_fields(self) -> tuple[str, ...]:
        return (self.status_field, "message")

    @property
    @abstractmethod
    def status_field(self) -> str:
        ...

    @abstractmethod
    def calculate_moves(self, *srcs: str, dest: str, existing: str) -> list[Movement]:
        ...

    @abstractmethod
    def calculate_moves_by_regex(
        self, find: str, replace: str, existing: str
    ) -> list[Movement]:
        ...

    def process_moves_pyout(
        self, plan: list[Movement], dry_run: bool = False
    ) -> Iterator[dict]:
        for m in plan:
            yield {
                "source": m.src,
                "target": m.dest,
                self.updating_fields: self.process_movement(m, dry_run),
            }

    def process_moves_debug(
        self, plan: list[Movement], dry_run: bool = False
    ) -> Iterator[Iterator[dict]]:
        for m in plan:
            yield (
                {"source": m.src, "target": m.dest, **d}
                for d in self.process_movement(m, dry_run)
            )

    @abstractmethod
    def process_movement(
        self, m: Movement, dry_run: bool = False
    ) -> Iterator[dict[str, str]]:
        ...


class LocalizedMover(Mover):
    # A mover for moving only the files in one location (i.e., either local or
    # remote)

    #: A relative path denoting the subdirectory of the Dandiset in which we
    #: are operating
    subpath: Path

    @abstractmethod
    def get_assets(self) -> Iterator[tuple[AssetPath, str]]:
        # Yields all assets as (asset_path, relpath) pairs where asset_path is
        # a /-separated path relative to the root of the Dandiset and relpath
        # is a /-separated path relative to `subpath` (for assets outside of
        # `subpath`, relpath starts with ``../``)
        ...

    @abstractmethod
    def get_path(self, path: str, contents: bool = True) -> File | Folder:
        # Raises NotFoundError if the path does not exist
        ...

    @abstractmethod
    def is_dir(self, path: AssetPath) -> bool:
        ...

    @abstractmethod
    def is_file(self, path: AssetPath) -> bool:
        ...

    @abstractmethod
    def move(self, src: AssetPath, dest: AssetPath) -> None:
        # `dest` can be assumed to not exist
        ...

    @abstractmethod
    def delete(self, path: AssetPath) -> None:
        ...

    def resolve(self, path: str) -> tuple[AssetPath, bool]:
        """
        Convert an input path (relative to `subpath`, possibly starting with
        ``../``) to a /-separated path relative to the root of the Dandiset,
        plus a boolean that is true iff the input path ended with a slash
        """
        p = PurePosixPath(
            posixpath.normpath(posixpath.join(self.subpath.as_posix(), path))
        )
        if p.parts[0] == os.pardir:
            raise ValueError(f"{path!r} is outside of Dandiset")
        return (AssetPath(str(p)), path.endswith("/"))

    def calculate_moves(self, *srcs: str, dest: str, existing: str) -> list[Movement]:
        destobj: File | Folder | None
        try:
            destobj = self.get_path(dest, contents=False)
        except NotFoundError:
            if dest.endswith("/") or len(srcs) > 1:
                destobj = Folder(dest, [])
            elif len(srcs) == 1:
                destobj = None
            else:
                destobj = File(AssetPath(dest))
        if isinstance(dest, File) and len(srcs) > 1:
            raise ValueError(
                "Cannot take multiple source paths when destination is a file"
            )
        moves: dict[AssetPath, AssetPath] = {}
        for s in map(self.get_path, srcs):
            if destobj is None:
                if isinstance(s, File):
                    destobj = File(AssetPath(dest))
                else:
                    destobj = Folder(dest, [])
            if isinstance(s, File):
                if isinstance(destobj, File):
                    moves[s.path] = AssetPath(destobj.path)
                else:
                    moves[s.path] = AssetPath(
                        posixpath.join(destobj.path, posixpath.basename(s.path))
                    )
                lgr.debug("Calculated move: %r -> %r", s.path, moves[s.path])
            else:
                if isinstance(destobj, File):
                    raise ValueError("Cannot move a folder to a file path")
                else:
                    for p in s.relcontents:
                        p1 = posixpath.join(s.path, p)
                        p2 = posixpath.join(destobj.path, posixpath.basename(s.path), p)
                        moves[AssetPath(p1)] = AssetPath(p2)
                        lgr.debug("Calculated move: %r -> %r", p1, p2)
        return self.compile_moves(moves, existing)

    def calculate_moves_by_regex(
        self, find: str, replace: str, existing: str
    ) -> list[Movement]:
        rgx = re.compile(find)
        moves: dict[AssetPath, AssetPath] = {}
        rev: dict[AssetPath, AssetPath] = {}
        for asset_path, relpath in self.get_assets():
            m = rgx.search(relpath)
            if m:
                dest, _ = self.resolve(
                    relpath[: m.start()] + m.expand(replace) + relpath[m.end() :]
                )
                lgr.debug("Calculated move: %r -> %r", asset_path, dest)
                if dest in rev:
                    raise ValueError(
                        f"Both {rev[dest]!r} and {asset_path!r} would be moved to {dest!r}"
                    )
                moves[asset_path] = dest
                rev[dest] = asset_path
        return self.compile_moves(moves, existing)

    def compile_moves(
        self, moves: dict[AssetPath, AssetPath], existing: str
    ) -> list[Movement]:
        motions: list[Movement] = []
        for src, dest in sorted(moves.items()):
            if self.is_dir(dest):
                raise ValueError(
                    f"Cannot move {src!r} to {dest!r}, as destination is a directory"
                )
            elif self.is_file(dest):
                if existing == "overwrite":
                    motions.append(Movement(src, dest, delete=True))
                elif existing == "skip":
                    motions.append(Movement(src, dest, skip=True))
                else:
                    raise ValueError(
                        f"Cannot move {src!r} to {dest!r}, as destination already exists"
                    )
            else:
                motions.append(Movement(src, dest))
        return motions

    def process_moves_pyout(
        self, plan: list[Movement], dry_run: bool = False
    ) -> Iterator[dict]:
        for m in plan:
            yield {
                "source": m.src,
                "target": m.dest,
                self.updating_fields: self.process_movement(m, dry_run),
            }

    def process_moves_debug(
        self, plan: list[Movement], dry_run: bool = False
    ) -> Iterator[Iterator[dict]]:
        for m in plan:
            yield (
                {"source": m.src, "target": m.dest, **d}
                for d in self.process_movement(m, dry_run)
            )

    def process_movement(
        self, m: Movement, dry_run: bool = False
    ) -> Iterator[dict[str, str]]:
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
    dandiset_path: Path
    subpath: Path  # relative path

    @property
    def status_field(self) -> str:
        return "local"

    def get_assets(self) -> Iterator[tuple[AssetPath, str]]:
        for df in find_dandi_files(
            self.dandiset_path,
            dandiset_path=self.dandiset_path,
            allow_all=True,
            include_metadata=False,
        ):
            assert isinstance(df, LocalAsset)
            relpath = posixpath.relpath(df.path, self.subpath.as_posix())
            yield (AssetPath(df.path), relpath)

    def get_path(self, path: str, contents: bool = True) -> File | Folder:
        # TODO: Potential problem: Empty `src` dirs in local Dandisets
        path, _ = self.resolve(path)
        p = self.dandiset_path / path
        if not p.exists():
            raise NotFoundError(f"No asset at path {path!r}")
        if p.is_dir():
            if contents:
                files = [
                    df.filepath.relative_to(p).as_posix()
                    for df in find_dandi_files(
                        p,
                        dandiset_path=self.dandiset_path,
                        allow_all=True,
                        include_metadata=False,
                    )
                ]
            else:
                files = []
            return Folder(path, files)
        else:
            return File(path)

    def is_dir(self, path: AssetPath) -> bool:
        return (self.dandiset_path / path).is_dir()

    def is_file(self, path: AssetPath) -> bool:
        p = self.dandiset_path / path
        return p.is_file() or p.is_symlink()

    def move(self, src: AssetPath, dest: AssetPath) -> None:
        lgr.debug("Moving local file %r to %r", src, dest)
        try:
            (self.dandiset_path / src).rename(self.dandiset_path / dest)
        except Exception as e:
            lgr.error(
                "Failed to move local file %r to %r: %s: %s",
                src,
                dest,
                type(e).__name__,
                e,
            )
            raise

    def delete(self, path: AssetPath) -> None:
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
    dandiset: RemoteDandiset
    subpath: Path  # relative path
    assets: dict[AssetPath, RemoteAsset] = field(init=False)

    def __post_init__(self) -> None:
        lgr.info("Fetching list of assets for Dandiset %s", self.dandiset.identifier)
        self.assets = {}
        for asset in self.dandiset.get_assets():
            self.assets[AssetPath(asset.path)] = asset

    @property
    def status_field(self) -> str:
        return "remote"

    def get_assets(self) -> Iterator[tuple[AssetPath, str]]:
        for path in self.assets.keys():
            relpath = posixpath.relpath(path, self.subpath.as_posix())
            yield (path, relpath)

    def get_path(self, path: str, contents: bool = True) -> File | Folder:
        path, needs_dir = self.resolve(path)
        relcontents: list[str] = []
        for p in self.assets.keys():
            if p == path:
                if not needs_dir:
                    return File(path)
            elif p.startswith(f"{path}/"):
                relcontents.append(posixpath.relpath(p, path))
        if relcontents:
            return Folder(path, relcontents)
        raise NotFoundError(f"No asset at path {path!r}")

    def is_dir(self, path: AssetPath) -> bool:
        return any(p.startswith(f"{path}/") for p in self.assets.keys())

    def is_file(self, path: AssetPath) -> bool:
        return path in self.assets

    def move(self, src: AssetPath, dest: AssetPath) -> None:
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
    local: LocalMover
    remote: RemoteMover

    @property
    def subpath(self) -> Path:
        return self.local.subpath

    @property
    def updating_fields(self) -> tuple[str, ...]:
        return (self.local.status_field, self.remote.status_field, "message")

    @property
    def status_field(self) -> str:
        return "both"  # Should not be used

    def calculate_moves(self, *srcs: str, dest: str, existing: str) -> list[Movement]:
        local_moves = self.local.calculate_moves(*srcs, dest=dest, existing=existing)
        remote_moves = self.remote.calculate_moves(*srcs, dest=dest, existing=existing)
        self.compare_moves(local_moves, remote_moves)
        return local_moves

    def calculate_moves_by_regex(
        self, find: str, replace: str, existing: str
    ) -> list[Movement]:
        local_moves = self.local.calculate_moves_by_regex(find, replace, existing)
        remote_moves = self.remote.calculate_moves_by_regex(find, replace, existing)
        self.compare_moves(local_moves, remote_moves)
        return local_moves

    def compare_moves(
        self, local_moves: list[Movement], remote_moves: list[Movement]
    ) -> None:
        # Recall that the Movements are sorted by src path
        for lm, rm in zip_longest(local_moves, remote_moves):
            if rm is None:
                raise AssetMismatchError(f"asset {lm.src!r} only exists locally")
            elif lm is None:
                raise AssetMismatchError(f"asset {rm.src!r} only exists remotely")
            elif lm.src < rm.src:
                raise AssetMismatchError(f"asset {lm.src!r} only exists locally")
            elif lm.src > rm.src:
                raise AssetMismatchError(f"asset {rm.src!r} only exists remotely")
            elif lm.dest != rm.dest:
                raise AssetMismatchError(
                    f"asset {lm.src!r} would be moved to {lm.dest!r} locally"
                    f" but to {rm.dest!r} remotely"
                )
            elif lm.dest_exists and not rm.dest_exists:
                raise AssetMismatchError(
                    f"asset {lm.src!r} would be moved to {lm.dest!r}, which"
                    " exists locally but not remotely"
                )
            elif not lm.dest_exists and rm.dest_exists:
                raise AssetMismatchError(
                    f"asset {lm.src!r} would be moved to {lm.dest!r}, which"
                    " exists remotely but not locally"
                )

    def process_movement(
        self, m: Movement, dry_run: bool = False
    ) -> Iterator[dict[str, str]]:
        for state in self.local.process_movement(m, dry_run):
            yield state
            if state[self.local.status_field] == "Error":
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
                remote=RemoteMover(dandiset=remote_ds, subpath=subpath),
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
    path = path.absolute()
    ds = Dandiset.find(path)
    if ds is None:
        raise ValueError(f"{path}: not a Dandiset")
    return (ds, path.relative_to(ds.path))


class AssetMismatchError(ValueError):
    def __init__(self, msg: str) -> None:
        self.msg = msg

    def __str__(self) -> str:
        return "Mismatch between local and remote servers: {self.msg}"
