"""
Streaming the content of annexed files with datalad-fuse_, as an alternative
to the git-only reader of `dandi.support.annex`.

datalad-fuse can mount a DataLad dataset with FUSE, but its remote filesystem
adapter, which the mount is built on, also opens files directly, with no mount.
That adapter is what is used here.  Unlike `dandi.support.annex`, it asks
git-annex itself where the content is (``git annex whereis``), so it also finds
content available from remotes (e.g., a Forgejo-aneksajo instance or an S3
export) that has no URL registered.  It needs git-annex and DataLad installed,
and is used only in a git-annex repository, i.e., one with git-annex
initialized.

.. _datalad-fuse: https://github.com/datalad/datalad-fuse
"""

from __future__ import annotations

import atexit
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from itertools import chain
import logging
import os
from pathlib import Path
import subprocess
from typing import IO, TYPE_CHECKING, cast

from .annex import AnnexKey
from ..misctypes import Readable

if TYPE_CHECKING:
    from datalad_fuse.adapter import RemoteFilesystemAdapter

lgr = logging.getLogger("dandi.support.datalad_fuse")


@cache
def get_adapter() -> RemoteFilesystemAdapter:
    """
    The datalad-fuse adapter shared by all files, rooted at the filesystem root
    so that it serves files of any dataset, and closed at exit
    """
    # Optional dependency:
    from datalad_fuse.adapter import RemoteFilesystemAdapter

    # caching=False: do not keep the streamed blocks on disk, in the dataset
    adapter = RemoteFilesystemAdapter(Path(os.path.abspath(os.sep)), caching=False)
    atexit.register(adapter.__exit__, None, None, None)
    return adapter


@cache
def annex_initialized(directory: Path) -> bool:
    """
    Whether ``directory`` is in a Git repository in which git-annex is
    initialized.  (DataLad would otherwise initialize it, modifying the
    repository, e.g., in a repository with only a ``git-annex`` branch.)
    """
    try:
        r = subprocess.run(
            ["git", "-C", str(directory), "config", "--get", "annex.uuid"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


@dataclass
class DataladFuseReadableFile(Readable):
    """
    A `Readable` for an annexed file whose content is not present locally and
    is instead streamed with datalad-fuse's adapter (see the module
    docstring).

    Instances are obtained by calling `get_datalad_fuse_readable()`.
    """

    #: The absolute path of the (broken) symbolic link to the file's content
    filepath: Path

    #: The git-annex key of the file
    key: AnnexKey

    #: The first URL that the content may be streamed from (for reporting;
    #: the adapter tries the others if it cannot be read from that one)
    url: str

    adapter: RemoteFilesystemAdapter = field(repr=False, compare=False)

    def open(self) -> IO[bytes]:
        return cast("IO[bytes]", self.adapter.open(self.filepath, "rb"))

    def get_size(self) -> int:
        assert self.key.size is not None
        return self.key.size

    def get_mtime(self) -> datetime | None:
        return None

    def get_filename(self) -> str:
        return self.filepath.name

    def get_fingerprint(self) -> str:
        # The key is a digest of the content (plus its size), so results
        # computed from it (validation, metadata) can be cached under it
        return self.key.key

    def __str__(self) -> str:
        return str(self.filepath)


def get_datalad_fuse_readable(path: str | Path) -> DataladFuseReadableFile | None:
    """
    Return a `DataladFuseReadableFile` for streaming the content of the
    annexed file at ``path``, or `None` if datalad-fuse is not installed,
    ``path`` is not in a git-annex repository, is not an annexed file whose
    content is missing, its key does not record the size of the content, or
    git-annex knows no URL to stream it from.  Only locked annexed files
    (symbolic links) are handled.
    """
    try:
        from datalad_fuse.adapter import FileState
    except ImportError:
        return None
    filepath = Path(os.path.abspath(path))
    if not filepath.is_symlink() or filepath.exists():
        # Not a broken symbolic link, i.e., not a locked annexed file whose
        # content is missing
        return None
    if not annex_initialized(filepath.parent):
        return None
    adapter = get_adapter()
    try:
        dsap, relpath = adapter.resolve_dataset(filepath)
    except Exception as e:
        # Not in a Git repository, or one datalad-fuse cannot handle (e.g.,
        # without any commit)
        lgr.debug("%s: Not streamable with datalad-fuse: %s", filepath, e)
        return None
    if dsap.annex is None:
        # git-annex not initialized
        return None
    state, fkey = dsap.get_file_state(relpath)
    if state is not FileState.NO_CONTENT or fkey is None:
        return None
    key = AnnexKey.parse(str(fkey))
    if key.size is None:
        return None
    # The URLs tried by the adapter, in its order
    url = next(
        chain(dsap.get_urls(key.key), dsap.get_exporttree_urls(relpath, fkey)), None
    )
    if url is None:
        lgr.debug("%s: git-annex knows no URL for key %s", filepath, key)
        return None
    return DataladFuseReadableFile(filepath=filepath, key=key, url=url, adapter=adapter)
