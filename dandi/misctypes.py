"""
.. versionadded:: 0.36.0

Miscellaneous public classes
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Dict, Iterator, List, Tuple, TypeVar

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

    def asdict(self) -> Dict[DigestType, str]:
        """
        Convert the instance to a single-item `dict` mapping the digest
        algorithm to the digest value
        """
        return {self.algorithm: self.value}


#: Placeholder digest used in some situations where a digest is required but
#: not actually relevant and would be too expensive to calculate
DUMMY_DIGEST = Digest(algorithm=DigestType.dandi_etag, value=32 * "d" + "-1")

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
    parts: Tuple[str, ...]

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
    def _split_path(path: str) -> Tuple[str, ...]:
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
    def parents(self: P) -> Tuple[P, ...]:
        """
        A tuple of the path's ancestors, starting at the parent and going up to
        (and including) the root of the hierarchy
        """
        ps: List[P] = []
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
    def suffixes(self) -> List[str]:
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
