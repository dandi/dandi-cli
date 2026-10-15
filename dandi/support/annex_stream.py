"""
Reading the content of annexed files of git-annex_ repositories (such as
DataLad_ datasets) that is not present locally, by streaming it with
datalad-fuse_.

In a git-annex repository, a (locked) annexed file is a symbolic link into
:file:`.git/annex/objects/`, which is broken until the content is fetched.
datalad-fuse can mount such a repository with FUSE so that the content is
streamed on demand, but its adapter, which the mount is built on, also opens
the files directly, with no mount: it asks git-annex where the content is
(``git annex whereis``) and reads it over HTTP(S), from the first of its URLs
that can be read, with remfile_ for HDF5-based files (such as NWB).  remfile
fetches only the parts of a file that are read, in requests sized for the
access pattern of HDF5, so that the files of a DataLad Dandiset can be read
(e.g., for their metadata, or to be validated) without downloading the
(possibly terabytes of) data.

For a DataLad Dandiset, git-annex lists the DANDI Archive's API download URL
(which redirects to S3) before the direct S3 URL.

This requires datalad-fuse with its remfile backend (``pip install
"dandi[datalad]"``), which requires DataLad and git-annex.  No ``git annex``
command is run in a repository in which git-annex is not initialized (e.g., a
fresh ``git clone``), as it would initialize git-annex there, modifying the
repository.

.. _git-annex: https://git-annex.branchable.com
.. _DataLad: https://www.datalad.org
.. _datalad-fuse: https://github.com/datalad/datalad-fuse
.. _remfile: https://github.com/flatironinstitute/remfile
"""

from __future__ import annotations

import atexit
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
import io
import logging
import os
from pathlib import Path
import subprocess
from typing import IO, Any, cast

from ..misctypes import Readable

lgr = logging.getLogger("dandi.support.annex_stream")


@cache
def get_adapter() -> Any:
    """
    The datalad-fuse adapter shared by all files, rooted at the filesystem
    root so that it serves files of any dataset, and closed at exit
    """
    # Optional dependency:
    from datalad_fuse.adapter import RemoteFilesystemAdapter

    # caching=False: do not keep the streamed content on disk, in the dataset.
    # backends: always read HDF5-based files (such as NWB) with remfile,
    # whatever a dataset configures (datalad.fusefs.backends), as it reads in
    # the calling thread: h5py holds a global lock while it reads, and fsspec,
    # which reads in another thread, could deadlock with h5py finalizers run by
    # a garbage collection there.
    # The root and all paths passed to the adapter must be absolute.  (Files
    # are only handed to the adapter in repositories in which git-annex is
    # initialized: see `annex_initialized()`.)
    adapter = RemoteFilesystemAdapter(
        Path(os.path.abspath(os.sep)),
        caching=False,
        backends="remfile,fsspec",
    )
    atexit.register(adapter.__exit__, None, None, None)
    return adapter


@cache
def annex_initialized(directory: Path) -> bool:
    """
    Whether ``directory`` is in a Git repository in which git-annex is
    initialized.  (This is checked before handing a file to datalad-fuse,
    which would otherwise load the dataset with DataLad only to find out.)
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


class StreamedFile(io.RawIOBase):
    """
    A seekable, read-only binary file object around a file object returned by
    datalad-fuse's adapter, for consumers (such as h5py) that read with
    ``readinto()``
    """

    def __init__(self, fp: Any) -> None:
        super().__init__()
        self._fp = fp

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        view = memoryview(buffer).cast("B")
        data = self._fp.read(len(view))
        view[: len(data)] = data
        return len(data)

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        return int(self._fp.seek(offset, whence))

    def tell(self) -> int:
        return int(self._fp.tell())

    def close(self) -> None:
        if not self.closed:
            self._fp.close()
        super().close()


@dataclass
class AnnexedReadableFile(Readable):
    """
    A `Readable` for a (locked) annexed file at ``filepath`` (a broken symbolic
    link) whose content is not present locally, which is streamed with
    datalad-fuse (see the module docstring).  ``url`` is only the first URL
    known for the content, for reporting: if it cannot be read, datalad-fuse
    tries the others.

    Instances are obtained by calling `get_annexed_readable()`.
    """

    filepath: Path
    key: str
    size: int
    url: str
    adapter: Any = field(repr=False, compare=False)

    def open(self) -> IO[bytes]:
        return cast("IO[bytes]", StreamedFile(self.adapter.open(self.filepath, "rb")))

    def get_size(self) -> int:
        return self.size

    def get_mtime(self) -> datetime | None:
        return None

    def get_filename(self) -> str:
        return self.filepath.name

    def __str__(self) -> str:
        return str(self.filepath)


def annex_fingerprint(source: Any) -> tuple[str, str] | None:
    """
    Fingerprint of ``source`` for ``PersistentCache.memoize_path``

    Pass it as ``custom_fingerprint`` to cache the results of a function of a
    local path or a `Readable` under the git-annex key of a locked annexed
    file, paired with its path (see `fscacher.annex_key_fingerprint`), rather
    than under ``stat()``: the content of an `AnnexedReadableFile`, which is
    not present locally, cannot be ``stat()``-ed.  Anything else is handled as
    without this.
    """
    # Avoid heavy import (fscacher imports joblib, which imports numpy) when
    # this module is imported, e.g., by the CLI:
    from fscacher import annex_key_fingerprint

    if isinstance(source, AnnexedReadableFile):
        source = source.filepath
    return cast("tuple[str, str] | None", annex_key_fingerprint(source))


def can_stream() -> bool:
    """
    Whether the requirements for streaming are installed: datalad-fuse with
    its adapter, and remfile
    """
    try:
        import datalad_fuse.adapter  # noqa: F401
        import remfile  # noqa: F401
    except ImportError:
        return False
    return True


def get_annexed_readable(path: str | Path) -> AnnexedReadableFile | None:
    """
    Return an `AnnexedReadableFile` for streaming the content of the annexed
    file at ``path``, or `None` if datalad-fuse (with remfile) is not
    installed, ``path`` is not a (locked) annexed file whose content is missing
    in a repository in which git-annex is initialized, its key does not record
    the size of the content, or git-annex knows no URL to stream it from
    """
    filepath = Path(os.path.abspath(path))
    if not filepath.is_symlink() or filepath.exists():
        # Not a broken symbolic link
        return None
    if not can_stream():
        return None
    if not annex_initialized(filepath.parent):
        return None
    from datalad_fuse.adapter import FileState

    try:
        dsap, relpath = get_adapter().resolve_dataset(filepath)
        state, key = dsap.get_file_state(relpath)
    except Exception as e:
        # E.g., a repository without any commit
        lgr.debug("%s: Cannot be read with datalad-fuse: %s", filepath, e)
        return None
    if state is not FileState.NO_CONTENT or key is None:
        return None
    if key.size is None:
        lgr.debug("%s: The key %s does not record the size", filepath, key)
        return None
    url = next(dsap.get_urls(str(key)), None)
    if url is None:
        lgr.debug("%s: git-annex knows no URL for key %s", filepath, key)
        return None
    return AnnexedReadableFile(
        filepath=filepath, key=str(key), size=key.size, url=url, adapter=get_adapter()
    )
