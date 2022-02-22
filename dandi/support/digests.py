# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the dandi package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Provides helper to compute digests (md5 etc) on files
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, cast

from dandischema.digests.dandietag import DandiETag
from dandischema.digests.zarr import get_checksum
from fscacher import PersistentCache

from .threaded_walk import threaded_walk
from ..utils import auto_repr

lgr = logging.getLogger("dandi.support.digests")


@auto_repr
class Digester:
    """Helper to compute multiple digests in one pass for a file"""

    # Loosely based on snippet by PM 2Ring 2014.10.23
    # http://unix.stackexchange.com/a/163769/55543

    # Ideally we should find an efficient way to parallelize this but
    # atm this one is sufficiently speedy

    DEFAULT_DIGESTS = ["md5", "sha1", "sha256", "sha512"]

    def __init__(
        self, digests: Optional[List[str]] = None, blocksize: int = 1 << 16
    ) -> None:
        """
        Parameters
        ----------
        digests : list or None
          List of any supported algorithm labels, such as md5, sha1, etc.
          If None, a default set of hashes will be computed (md5, sha1,
          sha256, sha512).
        blocksize : int
          Chunk size (in bytes) by which to consume a file.
        """
        self._digests = digests or self.DEFAULT_DIGESTS
        self._digest_funcs = [getattr(hashlib, digest) for digest in self._digests]
        self.blocksize = blocksize

    @property
    def digests(self) -> List[str]:
        return self._digests

    def __call__(self, fpath: Union[str, Path]) -> Dict[str, str]:
        """
        fpath : str
          File path for which a checksum shall be computed.

        Return
        ------
        dict
          Keys are algorithm labels, and values are checksum strings
        """
        lgr.debug("Estimating digests for %s" % fpath)
        digests = [x() for x in self._digest_funcs]
        with open(fpath, "rb") as f:
            while True:
                block = f.read(self.blocksize)
                if not block:
                    break
                [d.update(block) for d in digests]

        return {n: d.hexdigest() for n, d in zip(self.digests, digests)}


checksums = PersistentCache(name="dandi-checksums", envvar="DANDI_CACHE")


@checksums.memoize_path
def get_digest(filepath: Union[str, Path], digest: str = "sha256") -> str:
    if digest == "dandi-etag":
        return cast(str, get_dandietag(filepath).as_str())
    elif digest == "zarr-checksum":
        return get_zarr_checksum(Path(filepath))
    else:
        return Digester([digest])(filepath)[digest]


@checksums.memoize_path
def get_dandietag(filepath: Union[str, Path]) -> DandiETag:
    return DandiETag.from_file(filepath)


def get_zarr_checksum(
    path: Path,
    basepath: Optional[Path] = None,
    known: Optional[Dict[str, str]] = None,
) -> str:
    if path.is_file():
        return cast(str, get_digest(path, "md5"))
    root: Tuple[str, ...]
    if basepath is None:
        basepath = path
        root = ()
    else:
        root = path.relative_to(basepath).parts
    zcc = ZCDirectory(path="")
    for p, digest in threaded_walk(path, lambda f: (f, md5file_nocache(f))):
        zcc.add(p.relative_to(basepath), digest)
    for d in root:
        try:
            sub = zcc.children[d]
        except KeyError:
            raise ValueError("Cannot compute a Zarr checksum for an empty directory")
        else:
            assert isinstance(sub, ZCDirectory)
            zcc = sub
    return zcc.get_digest()


@dataclass
class ZCFile:
    """
    File node used for building an in-memory tree of Zarr entries and their
    digests when calculating a complete Zarr checksum

    :meta private:
    """

    path: str
    digest: str


@dataclass
class ZCDirectory:
    """
    Directory node used for building an in-memory tree of Zarr entries and
    their digests when calculating a complete Zarr checksum

    :meta private:
    """

    path: str
    children: Dict[str, Union[ZCDirectory, ZCFile]] = field(default_factory=dict)

    def get_digest(self) -> str:
        files = {}
        dirs = {}
        for n in self.children.values():
            if isinstance(n, ZCDirectory):
                dirs[n.path] = n.get_digest()
            else:
                files[n.path] = n.digest
        return cast(str, get_checksum(files, dirs))

    def add(self, path: Path, digest: str) -> None:
        *dirs, name = path.parts
        parts = []
        d = self
        for dirname in dirs:
            parts.append(dirname)
            e = d.children.setdefault(dirname, ZCDirectory(path="/".join(parts)))
            assert isinstance(e, ZCDirectory), f"Path type conflict for {d.path}"
            d = e
        parts.append(name)
        pstr = "/".join(parts)
        assert name not in d.children, f"File {pstr} encountered twice"
        d.children[name] = ZCFile(path=pstr, digest=digest)


def md5file_nocache(filepath: Union[str, Path]) -> str:
    """
    Compute the MD5 digest of a file without caching with fscacher, which has
    been shown to slow things down for the large numbers of files typically
    present in Zarrs
    """
    return Digester(["md5"])(filepath)["md5"]
