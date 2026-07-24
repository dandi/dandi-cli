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

# Importing this module imports fscacher, which imports joblib, which imports
# numpy, which is a "heavy" import, so avoid importing this module at the top
# level of a module.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import hashlib
import logging
import os
import os.path
from pathlib import Path
import re

from dandischema.digests.dandietag import DandiETag
from fscacher import PersistentCache
from zarr_checksum.checksum import ZarrChecksum, ZarrChecksumManifest
from zarr_checksum.tree import ZarrChecksumTree

from .threaded_walk import threaded_walk
from ..consts import S3_MAX_SINGLE_PART_UPLOAD
from ..utils import Hasher, exclude_from_zarr

lgr = logging.getLogger("dandi.support.digests")


@dataclass
class Digester:
    """Helper to compute multiple digests in one pass for a file"""

    # Loosely based on snippet by PM 2Ring 2014.10.23
    # http://unix.stackexchange.com/a/163769/55543

    # Ideally we should find an efficient way to parallelize this but
    # atm this one is sufficiently speedy

    #: List of any supported algorithm labels, such as md5, sha1, etc.
    digests: list[str] = field(
        default_factory=lambda: ["md5", "sha1", "sha256", "sha512"]
    )

    #: Chunk size (in bytes) by which to consume a file.
    blocksize: int = 1 << 16

    digest_funcs: list[Callable[[], Hasher]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.digest_funcs = [getattr(hashlib, digest) for digest in self.digests]

    def __call__(self, fpath: str | Path) -> dict[str, str]:
        """
        fpath : str
          File path for which a checksum shall be computed.

        Return
        ------
        dict
          Keys are algorithm labels, and values are checksum strings
        """
        lgr.debug("Estimating digests for %s" % fpath)
        digests = [x() for x in self.digest_funcs]
        with open(fpath, "rb") as f:
            while True:
                block = f.read(self.blocksize)
                if not block:
                    break
                for d in digests:
                    d.update(block)
        return {n: d.hexdigest() for n, d in zip(self.digests, digests)}


checksums = PersistentCache(name="dandi-checksums", envvar="DANDI_CACHE")


@checksums.memoize_path
def get_digest(filepath: str | Path, digest: str = "sha256") -> str:
    if digest == "dandi-etag":
        s = get_dandietag(filepath).as_str()
        assert isinstance(s, str)
        return s
    elif digest == "zarr-checksum":
        return get_zarr_checksum(Path(filepath))
    else:
        return Digester([digest])(filepath)[digest]


@checksums.memoize_path
def get_dandietag(filepath: str | Path) -> DandiETag:
    return DandiETag.from_file(filepath)


#: Pattern of an S3 multipart ETag: an MD5 hex digest, a hyphen, and the number
#: of parts (e.g. ``d41d8cd98f00b204e9800998ecf8427e-3``).
_MULTIPART_ETAG_RE = re.compile(r"[0-9a-f]{32}-[1-9][0-9]*\Z")


def is_multipart_etag(digest: str) -> bool:
    """
    Return whether ``digest`` is an S3 multipart ETag (``<md5>-<parts>``) rather
    than a plain MD5 digest.
    """
    return bool(_MULTIPART_ETAG_RE.match(digest))


def zarr_has_oversized_entry(path: Path) -> bool:
    """
    Return whether the Zarr at ``path`` contains any entry larger than
    `S3_MAX_SINGLE_PART_UPLOAD`.  Such a Zarr must be uploaded via S3 multipart
    upload, since S3 rejects single-part PUTs above that size.
    """
    for dirpath, dirnames, filenames in os.walk(path):
        dp = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not exclude_from_zarr(dp / d)]
        for fn in filenames:
            fp = dp / fn
            if exclude_from_zarr(fp):
                continue
            if os.path.getsize(fp) > S3_MAX_SINGLE_PART_UPLOAD:
                return True
    return False


def get_zarr_checksum(
    path: Path,
    known: dict[str, str] | None = None,
    multipart: bool | None = None,
) -> str:
    """
    Compute the Zarr checksum for a file or directory tree.

    If the digests for any files in the Zarr are already known, they can be
    passed in the ``known`` argument, which must be a `dict` mapping
    slash-separated paths relative to the root of the Zarr to hex digests.

    ``multipart`` indicates whether the Zarr is uploaded via S3 multipart
    upload (see `md5file_nocache`), which determines how its entries are
    digested.  If `None`, it is inferred: from ``known`` if given (any multipart
    ETag among the known digests implies a multipart Zarr), otherwise from
    whether any entry on disk exceeds `S3_MAX_SINGLE_PART_UPLOAD`.
    """
    if path.is_file():
        s = get_digest(path, "md5")
        assert isinstance(s, str)
        return s
    if known is None:
        known = {}
    if multipart is None:
        multipart = (
            any(is_multipart_etag(d) for d in known.values())
            if known
            else zarr_has_oversized_entry(path)
        )

    def digest_file(f: Path) -> tuple[Path, str, int]:
        assert known is not None
        relpath = f.relative_to(path).as_posix()
        try:
            dgst = known[relpath]
        except KeyError:
            dgst = md5file_nocache(f, multipart)
        return (f, dgst, os.path.getsize(f))

    zcc = ZarrChecksumTree()
    for p, digest, size in threaded_walk(path, digest_file, exclude=exclude_from_zarr):
        zcc.add_leaf(p.relative_to(path), size, digest)
    return str(zcc.process())


def md5file_nocache(filepath: str | Path, multipart: bool = False) -> str:
    """
    Compute the digest of a Zarr entry without caching with fscacher, which has
    been shown to slow things down for the large numbers of files typically
    present in Zarrs.

    The entries of a *multipart* Zarr — one that contains an entry too large
    for a single-part S3 PUT, and whose entries are therefore all uploaded via
    S3 multipart upload — are digested with their multipart ETag rather than
    their plain MD5, since that is what S3 stores as the object's ETag and thus
    what the server's Zarr checksum is computed from.  A single-part Zarr's
    entries are digested with plain MD5.
    """
    if multipart:
        s = get_dandietag(filepath).as_str()
        assert isinstance(s, str)
        return s
    return Digester(["md5"])(filepath)["md5"]


def checksum_zarr_dir(
    files: dict[str, tuple[str, int]], directories: dict[str, tuple[str, int]]
) -> str:
    """
    Calculate the Zarr checksum of a directory only from information about the
    files and subdirectories immediately within it.

    :param files:
        A mapping from names of files in the directory to pairs of their MD5
        digests and sizes
    :param directories:
        A mapping from names of subdirectories in the directory to pairs of
        their Zarr checksums and the sum of the sizes of all files recursively
        within them
    """
    manifest = ZarrChecksumManifest(
        files=[
            ZarrChecksum(digest=digest, name=name, size=size)
            for name, (digest, size) in files.items()
        ],
        directories=[
            ZarrChecksum(digest=digest, name=name, size=size)
            for name, (digest, size) in directories.items()
        ],
    )
    return manifest.generate_digest().digest
