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


DUMMY_DIGEST = Digest(algorithm=DigestType.dandi_etag, value=32 * "d" + "-1")

P = TypeVar("P", bound="BasePath")


@dataclass
class BasePath(ABC):
    parts: Tuple[str, ...]

    def __str__(self) -> str:
        return "/".join(self.parts)

    @property
    def name(self) -> str:
        if self.is_root():
            return ""
        else:
            assert self.parts
            return self.parts[-1]

    @abstractmethod
    def _get_subpath(self: P, name: str) -> P:
        ...

    def __truediv__(self: P, path: str) -> P:
        p = self
        for q in self._split_path(path):
            p = p._get_subpath(q)
        return p

    def joinpath(self: P, *paths: str) -> P:
        p = self
        for q in paths:
            p /= q
        return p

    @staticmethod
    def _split_path(path: str) -> Tuple[str, ...]:
        if path.startswith("/"):
            raise ValueError(f"Absolute paths not allowed: {path!r}")
        return tuple(q for q in path.split("/") if q)

    def is_root(self) -> bool:
        return self.parts == ()

    @property
    def root_path(self: P) -> P:
        p = self
        while not p.is_root():
            p = p.parent
        return p

    @property
    @abstractmethod
    def parent(self: P) -> P:
        # The parent of the root of a filetree is itself
        ...

    @property
    def parents(self: P) -> Tuple[P, ...]:
        ps: List[P] = []
        p = self
        while not p.is_root():
            q = p.parent
            ps.append(q)
            p = q
        return tuple(ps)

    def with_name(self: P, name: str) -> P:
        return self.parent / name

    @property
    def suffix(self) -> str:
        i = self.name.rfind(".")
        if 0 < i < len(self.name) - 1:
            return self.name[i:]
        else:
            return ""

    @property
    def suffixes(self) -> List[str]:
        if self.name.endswith("."):
            return []
        name = self.name.lstrip(".")
        return ["." + suffix for suffix in name.split(".")[1:]]

    @property
    def stem(self) -> str:
        i = self.name.rfind(".")
        if 0 < i < len(self.name) - 1:
            return self.name[:i]
        else:
            return self.name

    def with_stem(self: P, stem: str) -> P:
        return self.with_name(stem + self.suffix)

    def with_suffix(self: P, suffix: str) -> P:
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
        ...

    @abstractmethod
    def is_file(self) -> bool:
        ...

    @abstractmethod
    def is_dir(self) -> bool:
        ...

    @abstractmethod
    def iterdir(self: P) -> Iterator[P]:
        ...

    @property
    @abstractmethod
    def size(self) -> int:
        ...
