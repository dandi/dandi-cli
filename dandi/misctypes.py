"""
.. versionadded:: 0.36.0

Miscellaneous public classes
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from fnmatch import fnmatchcase
import gc
import os.path
from pathlib import Path
import threading
from typing import IO, Any, TypeVar, cast

from dandischema.models import DigestType


@dataclass
class Digest:
    """A computed digest for a file or directory"""

    #: The digest algorithm used
    algorithm: DigestType

    #: The digest itself
    value: str

    @classmethod
    def dandi_etag(cls, value: str) -> Digest:
        """
        Construct a `Digest` with the given value and a ``algorithm`` of
        ``DigestType.dandi_etag``
        """
        return cls(algorithm=DigestType.dandi_etag, value=value)

    @classmethod
    def dandi_zarr(cls, value: str) -> Digest:
        """
        Construct a `Digest` with the given value and a ``algorithm`` of
        ``DigestType.dandi_zarr_checksum``
        """
        return cls(algorithm=DigestType.dandi_zarr_checksum, value=value)

    def asdict(self) -> dict[DigestType, str]:
        """
        Convert the instance to a single-item `dict` mapping the digest
        algorithm to the digest value
        """
        return {self.algorithm: self.value}


#: Placeholder digest used in some situations where a digest is required but
#: not actually relevant and would be too expensive to calculate
DUMMY_DANDI_ETAG = Digest(algorithm=DigestType.dandi_etag, value=32 * "d" + "-1")
DUMMY_DANDI_ZARR_CHECKSUM = Digest(
    algorithm=DigestType.dandi_zarr_checksum,
    value=32 * "d" + "-1--1",
)

P = TypeVar("P", bound="BasePath")


@dataclass  # type: ignore[misc]  # <https://github.com/python/mypy/issues/5374>
class BasePath(ABC):
    """
    An abstract base class for path-like objects that can be traversed with the
    ``/`` operator *à la* `pathlib.Path` (though, unlike `pathlib.Path`
    instances, "dividing" by another non-string path is not allowed).  All
    paths are treated as forward-slash-separated relative paths under an
    empty-name "root" path.
    """

    #: The path components of the object
    parts: tuple[str, ...]

    def __str__(self) -> str:
        return "/".join(self.parts)

    @property
    def name(self) -> str:
        """
        The basename of the path object.  When the object represents the root
        of a path hierarchy, this is the empty string.
        """
        if self.is_root():
            return ""
        else:
            assert self.parts
            return self.parts[-1]

    @abstractmethod
    def _get_subpath(self: P, name: str) -> P:
        """
        Return the path immediately under the instance with the given name.  A
        name of ``"."`` should cause ``self`` to be returned, and a name of
        ``".."`` should cause ``self.parent`` to be returned.  An empty name or
        a name containing a forward slash should result in a `ValueError`.
        """
        ...

    def __truediv__(self: P, path: str) -> P:
        p = self
        for q in self._split_path(path):
            p = p._get_subpath(q)
        return p

    def joinpath(self: P, *paths: str) -> P:
        """
        Combine the path with each name or relative path in ``paths`` using the
        ``/`` operator
        """
        p = self
        for q in paths:
            p /= q
        return p

    @staticmethod
    def _split_path(path: str) -> tuple[str, ...]:
        """Split a path into its path components"""
        if path.startswith("/"):
            raise ValueError(f"Absolute paths not allowed: {path!r}")
        return tuple(q for q in path.split("/") if q)

    def is_root(self) -> bool:
        """
        Returns true if this path object represents the root of its hierarchy
        """
        return self.parts == ()

    @property
    def root_path(self: P) -> P:
        """The root of the path object's hierarchy"""
        p = self
        while not p.is_root():
            p = p.parent
        return p

    @property
    @abstractmethod
    def parent(self: P) -> P:
        """
        The parent path of the object.  The parent of the root of a path
        hierarchy is itself.
        """
        ...

    @property
    def parents(self: P) -> tuple[P, ...]:
        """
        A tuple of the path's ancestors, starting at the parent and going up to
        (and including) the root of the hierarchy
        """
        ps: list[P] = []
        p = self
        while not p.is_root():
            q = p.parent
            ps.append(q)
            p = q
        return tuple(ps)

    def with_name(self: P, name: str) -> P:
        """Equivalent to ``p.parent / name``"""
        return self.parent / name

    @property
    def suffix(self) -> str:
        """The final file extension of the basename, if any"""
        i = self.name.rfind(".")
        if 0 < i < len(self.name) - 1:
            return self.name[i:]
        else:
            return ""

    @property
    def suffixes(self) -> list[str]:
        """A list of the basename's file extensions"""
        if self.name.endswith("."):
            return []
        name = self.name.lstrip(".")
        return ["." + suffix for suffix in name.split(".")[1:]]

    @property
    def stem(self) -> str:
        """The basename without its final file extension, if any"""
        i = self.name.rfind(".")
        if 0 < i < len(self.name) - 1:
            return self.name[:i]
        else:
            return self.name

    def with_stem(self: P, stem: str) -> P:
        """Returns a new path with the stem changed"""
        return self.with_name(stem + self.suffix)

    def with_suffix(self: P, suffix: str) -> P:
        """Returns a new path with the final file extension changed"""
        if "/" in suffix or (suffix and not suffix.startswith(".")) or suffix == ".":
            raise ValueError(f"Invalid suffix: {suffix!r}")
        if not self.name:
            raise ValueError("Path has an empty name")
        if not self.suffix:
            name = self.name + suffix
        else:
            name = self.name[: -len(self.suffix)] + suffix
        return self.with_name(name)

    def match(self, pattern: str) -> bool:
        """Tests whether the path matches the given glob pattern"""
        patparts = self._split_path(pattern)
        if not patparts:
            raise ValueError("Empty pattern")
        if len(patparts) > len(self.parts):
            return False
        for part, pat in zip(reversed(self.parts), reversed(patparts)):
            if not fnmatchcase(part, pat):
                return False
        return True

    @abstractmethod
    def exists(self) -> bool:
        """True iff the resource at the given path exists"""
        ...

    @abstractmethod
    def is_file(self) -> bool:
        """True if the resource at the given path exists and is a file"""
        ...

    @abstractmethod
    def is_dir(self) -> bool:
        """True if the resource at the given path exists and is a directory"""
        ...

    @abstractmethod
    def iterdir(self: P) -> Iterator[P]:
        """
        Returns a generator of the paths under the instance, which must be a
        directory
        """
        ...

    @property
    @abstractmethod
    def size(self) -> int:
        """The size of the resource at the path"""
        ...


class Readable(ABC):
    """
    .. versionadded:: 0.50.0

    An abstract base class representing a local or remote resource that can be
    opened & read like a file
    """

    @abstractmethod
    def open(self) -> IO[bytes]:
        """
        Returns a readable binary filehandle for accessing the resource's bytes
        """
        ...

    @abstractmethod
    def get_size(self) -> int:
        """Returns the size in bytes of the resource"""
        ...

    @abstractmethod
    def get_mtime(self) -> datetime | None:
        """
        Returns the time at which the resource's contents were last modified,
        if it can be determined
        """
        ...

    @abstractmethod
    def get_filename(self) -> str:
        """
        Returns the base name of the resource, suitable for use as a file name
        """
        ...


class LocalReadableFile(Readable):
    """
    A concrete implementation of `Readable` for local files.

    Instances of this class are obtained by calling
    `LocalFileAsset.as_readable()` or `DandisetMetadataFile.as_readable()`.
    """

    def __init__(self, filepath: str | Path) -> None:
        #: The path to a local file to read
        self.filepath = Path(filepath)

    def __fspath__(self) -> str:
        return str(self.filepath)

    def __str__(self) -> str:
        return str(self.filepath)

    def open(self) -> IO[bytes]:
        return self.filepath.open("rb")

    def get_size(self) -> int:
        return os.path.getsize(self.filepath)

    def get_mtime(self) -> datetime:
        return datetime.fromtimestamp(self.filepath.stat().st_mtime).astimezone()

    def get_filename(self) -> str:
        return self.filepath.name


@dataclass
class RemoteReadableAsset(Readable):
    """
    A concrete implementation of `Readable` for DANDI blob assets on a remote
    server.  The fsspec_ library must be installed with the ``http`` extra
    (e.g., ``pip install "fsspec[http]"``) in order for `.open()` to be usable.

    Instances of this class are obtained by calling
    `BaseRemoteBlobAsset.as_readable()`.

    .. _fsspec: http://github.com/fsspec/filesystem_spec
    """

    #: The URL that data is read from
    url: str

    #: :meta private:
    size: int

    #: :meta private:
    mtime: datetime | None

    #: :meta private:
    name: str

    def open(self) -> IO[bytes]:
        # Optional dependency:
        from aiohttp import ClientTimeout
        import fsspec

        # We need to call open() on the return value of fsspec.open() because
        # otherwise the filehandle will only be opened when used to enter a
        # context manager.
        #
        # Pass explicit timeouts to aiohttp to prevent indefinite hangs in
        # fsspec's sync() wrapper.  Without these, a stalled connection to S3
        # (or minio in tests) causes fsspec's background IO thread to block
        # forever, which in turn blocks the calling thread in
        # threading.Event.wait() — see https://github.com/fsspec/filesystem_spec/issues/1666
        #
        # Automatic garbage collection is disabled while the file is open, as
        # it could otherwise deadlock fsspec's IO thread (see `_GCPausedFile`).
        return cast(
            IO[bytes],
            _GCPausedFile(
                fsspec.open(
                    self.url,
                    mode="rb",
                    client_kwargs={
                        "timeout": ClientTimeout(
                            total=120, sock_read=60, sock_connect=30
                        )
                    },
                ).open()
            ),
        )

    def get_size(self) -> int:
        return self.size

    def get_mtime(self) -> datetime | None:
        return self.mtime

    def get_filename(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.url


#: Protects `_gc_pauses` and `_gc_was_enabled`
_gc_lock = threading.Lock()
#: The number of open `_GCPausedFile` instances
_gc_pauses = 0
#: Whether automatic garbage collection was enabled before the first open
#: `_GCPausedFile` disabled it
_gc_was_enabled = False


class _GCPausedFile:
    """
    A file object during whose lifetime automatic garbage collection is
    disabled

    h5py holds a global lock while it reads from a Python file object, and the
    read of a `RemoteReadableAsset` waits for fsspec's IO thread to fetch the
    data.  If a garbage collection ran in that thread meanwhile, the finalizer
    of an unreferenced object closing an HDF5 file (e.g., hdmf's
    ``HDMFIO.__del__``) would wait for the same lock, and neither thread could
    proceed (<https://github.com/dandi/dandi-cli/issues/1450>).
    """

    def __init__(self, fp: IO[bytes]) -> None:
        global _gc_pauses, _gc_was_enabled
        self._fp = fp
        self._paused = False
        with _gc_lock:
            if _gc_pauses == 0:
                _gc_was_enabled = gc.isenabled()
                gc.disable()
            _gc_pauses += 1
            self._paused = True

    def __getattr__(self, name: str) -> Any:
        return getattr(self._fp, name)

    def __enter__(self) -> _GCPausedFile:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        if self._paused:
            self.close()

    def close(self) -> None:
        global _gc_pauses
        try:
            self._fp.close()
        finally:
            with _gc_lock:
                if self._paused:
                    self._paused = False
                    _gc_pauses -= 1
                    if _gc_pauses == 0 and _gc_was_enabled:
                        gc.enable()
