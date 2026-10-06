"""
Reading the content of annexed files of git-annex_ repositories (such as
DataLad_ datasets) that is not present locally, with datalad-fuse_.

In a git-annex repository, a (locked) annexed file is a symbolic link into
:file:`.git/annex/objects/`, which is broken until the content is fetched.
datalad-fuse can mount such a repository with FUSE so that the content is
streamed on demand, but its adapter, which the mount is built on, also opens
the files directly with no mount.  It asks git-annex where the content is
(``git annex whereis``) and streams it over HTTP(S) with fsspec_.  That adapter
is used here, so that the files of a DataLad Dandiset can be read (e.g., for
their metadata, or to be validated) without downloading the (possibly
terabytes of) data.

This requires datalad-fuse (``pip install "dandi[datalad]"``), which requires
DataLad and git-annex.

.. _git-annex: https://git-annex.branchable.com
.. _DataLad: https://www.datalad.org
.. _datalad-fuse: https://github.com/datalad/datalad-fuse
.. _fsspec: https://github.com/fsspec/filesystem_spec
"""

from __future__ import annotations

import atexit
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
import logging
import os
from pathlib import Path
import subprocess
from typing import IO, Any, cast

from ..misctypes import Readable

lgr = logging.getLogger("dandi.support.datalad_fuse")


@cache
def get_adapter() -> Any:
    """
    The datalad-fuse adapter shared by all files, rooted at the filesystem
    root so that it serves files of any dataset, and closed at exit
    """
    # Optional dependency:
    from datalad_fuse.fsspec import FsspecAdapter

    # caching=False: do not keep the streamed blocks on disk, in the dataset
    adapter = FsspecAdapter(Path(os.path.abspath(os.sep)), caching=False)
    atexit.register(adapter.__exit__, None, None, None)
    return adapter


@cache
def annex_initialized(directory: Path) -> bool:
    """
    Whether ``directory`` is in a Git repository in which git-annex is
    initialized.  (DataLad would otherwise initialize it, modifying the
    repository.)
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
class AnnexedReadableFile(Readable):
    """
    A `Readable` for a (locked) annexed file whose content is not present
    locally, which is streamed with datalad-fuse (see the module docstring).

    Instances are obtained by calling `get_annexed_readable()`.
    """

    #: The absolute path of the (broken) symbolic link to the file's content
    filepath: Path

    #: The git-annex key of the file
    key: str

    #: The size of the content, as recorded in the key
    size: int

    #: The first URL that the content may be streamed from (for reporting;
    #: the adapter tries the others if it cannot be read from that one)
    url: str

    adapter: Any = field(repr=False, compare=False)

    def open(self) -> IO[bytes]:
        return cast("IO[bytes]", self.adapter.open(self.filepath, "rb"))

    def get_size(self) -> int:
        return self.size

    def get_mtime(self) -> datetime | None:
        return None

    def get_filename(self) -> str:
        return self.filepath.name

    def __str__(self) -> str:
        return str(self.filepath)


def get_annexed_readable(path: str | Path) -> AnnexedReadableFile | None:
    """
    Return an `AnnexedReadableFile` for streaming the content of the annexed
    file at ``path``, or `None` if datalad-fuse is not installed, ``path`` is
    not a (locked) annexed file whose content is missing in a repository in
    which git-annex is initialized, its key does not record the size of the
    content, or git-annex knows no URL to stream it from
    """
    filepath = Path(os.path.abspath(path))
    if not filepath.is_symlink() or filepath.exists():
        # Not a broken symbolic link
        return None
    try:
        from datalad_fuse.fsspec import FileState
    except ImportError:
        return None
    if not annex_initialized(filepath.parent):
        return None
    try:
        dsap, relpath = get_adapter().resolve_dataset(filepath)
        state, key = dsap.get_file_state(relpath)
    except Exception as e:
        # E.g., a repository without any commit
        lgr.debug("%s: Cannot be read with datalad-fuse: %s", filepath, e)
        return None
    if state is not FileState.NO_CONTENT or key is None or key.size is None:
        return None
    url = next(dsap.get_urls(str(key)), None)
    if url is None:
        lgr.debug("%s: git-annex knows no URL for key %s", filepath, key)
        return None
    return AnnexedReadableFile(
        filepath=filepath, key=str(key), size=key.size, url=url, adapter=get_adapter()
    )
