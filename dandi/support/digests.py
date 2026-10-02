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
    """
    Compute the digest of ``filepath`` under the named algorithm.

    Besides the hashlib algorithms, ``digest`` may be ``"dandi-etag"`` or one
    of the two Zarr checksums.  A Zarr's checksum is an aggregate over its
    entries' S3 ETags, which differ by the scheme the Zarr was uploaded with,
    so the two schemes have to be named apart: ``"zarr-checksum"`` is the
    checksum of a single-part Zarr and ``"zarr-checksum-multipart"`` that of a
    multipart one, the scheme `dandi upload` uses for new Zarrs.
    """
    if digest == "dandi-etag":
        s = get_dandietag(filepath).as_str()
        assert isinstance(s, str)
        return s
    elif digest == "zarr-checksum":
        return get_zarr_checksum(Path(filepath))
    elif digest == "zarr-checksum-multipart":
        return get_zarr_multipart_checksum(Path(filepath))
    else:
        return Digester([digest])(filepath)[digest]


@checksums.memoize_path
def get_dandietag(filepath: str | Path) -> DandiETag:
    return DandiETag.from_file(filepath)


#: Pattern of an S3 multipart ETag: an MD5 hex digest, a hyphen, and the number
#: of parts (e.g. ``d41d8cd98f00b204e9800998ecf8427e-3``).  The part count is
#: never zero: S3 rejects a multipart upload with no parts, so an empty object
#: is always stored under its plain MD5 (see `dandietag_nocache`).
_MULTIPART_ETAG_RE = re.compile(r"[0-9a-f]{32}-[1-9][0-9]*\Z")


def is_multipart_etag(digest: str) -> bool:
    """
    Return whether ``digest`` is an S3 multipart ETag (``<md5>-<parts>``) rather
    than a plain MD5 digest.  An entry of a multipart Zarr is stored under such
    an ETag (see `dandietag_nocache`), so this distinguishes the digests of a
    multipart Zarr's entries from a single-part Zarr's.
    """
    return bool(_MULTIPART_ETAG_RE.match(digest))


def md5file_nocache(filepath: str | Path) -> str:
    """
    Compute the plain MD5 digest of a file, bypassing the fscacher cache (which
    has been shown to slow things down for the large numbers of files typically
    present in Zarrs).

    This is the digest of an entry of a **single-part** Zarr, which S3 stores
    under its plain MD5 ETag.  For the multipart counterpart, see
    `dandietag_nocache`.
    """
    return Digester(["md5"])(filepath)["md5"]


def dandietag_nocache(filepath: str | Path) -> str:
    """
    Compute the S3 multipart ETag (a.k.a. DANDI etag) of a file, bypassing the
    fscacher cache (cf. `md5file_nocache`).

    This is the digest of an entry of a **multipart** Zarr, which S3 stores
    under its multipart ETag; multipart is the scheme `dandi upload` uses for
    new Zarrs.  For the single-part counterpart, see `md5file_nocache`.

    An empty file is the one exception: `DandiETag` gives it zero parts and so
    an etag of ``<md5>-0``, but S3 rejects a multipart upload with no parts and
    stores an empty object under its plain MD5 under either scheme.  The plain
    MD5 is therefore what the archive will have digested the entry as.
    """
    if os.path.getsize(filepath) == 0:
        return md5file_nocache(filepath)
    s = DandiETag.from_file(filepath).as_str()
    assert isinstance(s, str)
    return s


def _zarr_checksum(
    path: Path, known: dict[str, str], digest_file: Callable[[Path], str]
) -> str:
    """
    Compute a Zarr checksum for the directory tree ``path``, digesting each
    entry not already present in ``known`` with ``digest_file``.  The two public
    entry points — `get_zarr_checksum` (single-part) and
    `get_zarr_multipart_checksum` (multipart) — differ only in that per-entry
    digest function.

    :meta private:
    """

    def digest_entry(f: Path) -> tuple[Path, str, int]:
        relpath = f.relative_to(path).as_posix()
        try:
            dgst = known[relpath]
        except KeyError:
            dgst = digest_file(f)
        return (f, dgst, os.path.getsize(f))

    zcc = ZarrChecksumTree()
    for p, digest, size in threaded_walk(path, digest_entry, exclude=exclude_from_zarr):
        zcc.add_leaf(p.relative_to(path), size, digest)
    return str(zcc.process())


def get_zarr_checksum(path: Path, known: dict[str, str] | None = None) -> str:
    """
    Compute the **single-part** Zarr checksum for a file or directory tree:
    every entry is digested with its plain MD5, as S3 stores it for a
    single-part upload.  This is the checksum of a single-part Zarr; for the
    multipart counterpart, see `get_zarr_multipart_checksum`.

    If the digests for any files in the Zarr are already known, they can be
    passed in the ``known`` argument, which must be a `dict` mapping
    slash-separated paths relative to the root of the Zarr to hex digests.
    """
    if path.is_file():
        s = get_digest(path, "md5")
        assert isinstance(s, str)
        return s
    return _zarr_checksum(path, known or {}, md5file_nocache)


def get_zarr_multipart_checksum(path: Path, known: dict[str, str] | None = None) -> str:
    """
    Compute the **multipart** Zarr checksum for a file or directory tree: every
    entry is digested with its S3 multipart ETag, as S3 stores it for a
    multipart upload (the scheme `dandi upload` uses for new Zarrs).  This is
    the checksum of a multipart Zarr; for the single-part counterpart, see
    `get_zarr_checksum`.

    If the digests for any files in the Zarr are already known, they can be
    passed in the ``known`` argument, which must be a `dict` mapping
    slash-separated paths relative to the root of the Zarr to hex digests.
    """
    if path.is_file():
        return dandietag_nocache(path)
    return _zarr_checksum(path, known or {}, dandietag_nocache)


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
