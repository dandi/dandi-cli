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

import hashlib
import logging
import os
import os.path
import sys
from typing import Dict, Iterable, Optional, Tuple

import appdirs
from diskcache import FanoutCache

from ..utils import AnyPath, auto_repr

if sys.version_info < (3, 8):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict

lgr = logging.getLogger("dandi.support.digests")

# This is the default number of workers for
# concurrent.futures.ThreadPoolExecutor (as of Python 3.8) and pyout, which
# means it's also the number of concurrent uploads/downloads dandi performs at
# once.
SHARD_QTY = min(32, os.cpu_count() + 4)

CACHE_DIR = os.path.join(appdirs.user_cache_dir("dandi", "dandi"), "digests")

DEFAULT_DIGESTS = ["md5", "sha1", "sha256", "sha512"]

DEFAULT_BLOCKSIZE = 1 << 16


@auto_repr
class Digester(object):
    """Helper to compute multiple digests in one pass for a file"""

    # Loosely based on snippet by PM 2Ring 2014.10.23
    # http://unix.stackexchange.com/a/163769/55543

    # Ideally we should find an efficient way to parallelize this but
    # atm this one is sufficiently speedy

    def __init__(self, digests=None, blocksize=DEFAULT_BLOCKSIZE):
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
        self._digests = digests or DEFAULT_DIGESTS
        self._digest_funcs = [getattr(hashlib, digest) for digest in self._digests]
        self.blocksize = blocksize

    @property
    def digests(self):
        return self._digests

    def __call__(self, fpath):
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


class DigestProgress(TypedDict, total=False):
    status: str
    # size: int
    digests: Dict[str, str]


digest_cache = FanoutCache(
    directory=CACHE_DIR, shards=SHARD_QTY, eviction_policy="least-recently-used"
)


def get_progressive_digests(
    path: AnyPath,
    digests: Optional[Iterable[str]] = None,
    blocksize: int = DEFAULT_BLOCKSIZE,
) -> Iterable[DigestProgress]:
    if not os.path.isfile(path):
        raise ValueError(f"{os.fsdecode(path)}: Cannot hash a directory")
    if digests is None:
        digests = DEFAULT_DIGESTS
    digest_tuple = tuple(sorted(digests))
    if not digest_tuple:
        raise ValueError("No digests specified")

    def mkkey() -> Tuple[str, Tuple[str, ...], int, int, int, int]:
        pathstr = os.path.realpath(os.fsdecode(path))
        s = os.stat(pathstr)
        return (
            pathstr,
            digest_tuple,
            s.st_mtime_ns,
            s.st_ctime_ns,
            s.st_size,
            s.st_ino,
        )

    try:
        digested = digest_cache[mkkey()]
    except KeyError:
        lgr.debug("Digesting %s", path)
        digestions = [getattr(hashlib, d)() for d in digest_tuple]
        total_size = os.path.getsize(path)
        current = 0
        with open(path, "rb") as f:
            while True:
                block = f.read(blocksize)
                if not block:
                    break
                for d in digestions:
                    d.update(block)
                current += len(block)
                pct = 100 * current / total_size
                yield {
                    "status": f"digesting ({pct:.2f}%)",
                    # "size": current,
                }
        digested = {n: d.hexdigest() for n, d in zip(digest_tuple, digestions)}
        # Calculate the key again just in case:
        digest_cache[mkkey()] = digested
    else:
        lgr.debug("Digests for %s found in cache", path)
    yield {"status": "digested", "digests": digested}


def get_digests(
    path: AnyPath,
    digests: Optional[Iterable[str]] = None,
    blocksize: int = DEFAULT_BLOCKSIZE,
) -> Dict[str, str]:
    for status in get_progressive_digests(path, digests, blocksize):
        if status["status"] == "digested":
            return status["digests"]


def get_digest(path, digest="sha256"):
    return get_digests(path)[digest]
