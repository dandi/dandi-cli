"""
Reading the content of annexed files of git-annex_ repositories (such as
DataLad_ datasets) that is not present locally, with datalad-fuse_.

In a git-annex repository, a (locked) annexed file is a symbolic link into
:file:`.git/annex/objects/`, which is broken until the content is fetched.
datalad-fuse can mount such a repository with FUSE so that the content is
streamed on demand, but its adapter, which the mount is built on, also opens
the files directly with no mount.  It asks git-annex where the content is
(``git annex whereis``) and streams it over HTTP(S): HDF5-based files (such as
NWB) with remfile_, which is optimized for HDF5's access pattern and reads in
the calling thread, and other files with fsspec_.  That adapter is used here,
so that the files of a DataLad Dandiset can be read (e.g., for their metadata,
or to be validated) without downloading the (possibly terabytes of) data.

The URLs are tried in the order git-annex lists them; for a DataLad Dandiset,
that is the DANDI Archive's API download URL (which redirects to S3) before the
direct S3 URL.  datalad-fuse does not use HTTP proxy environment variables.

This requires datalad-fuse (``pip install "dandi[datalad]"``), which requires
DataLad and git-annex, in a version with pluggable backends
(datalad/datalad-fuse#131) and ``init_annex`` (for now, the ``remfile-dev``
branch of https://github.com/CodyCBakerPhD/datalad-fuse), and remfile.

.. _git-annex: https://git-annex.branchable.com
.. _DataLad: https://www.datalad.org
.. _datalad-fuse: https://github.com/datalad/datalad-fuse
.. _fsspec: https://github.com/fsspec/filesystem_spec
.. _remfile: https://github.com/flatironinstitute/remfile
"""

from __future__ import annotations

import atexit
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
import gc
from itertools import chain
import logging
import os
from pathlib import Path
import threading
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
    from datalad_fuse.adapter import RemoteFilesystemAdapter

    adapter = RemoteFilesystemAdapter(
        # The root and all paths passed to the adapter must be absolute
        Path(os.path.abspath(os.sep)),
        # Do not keep the streamed blocks on disk, in the dataset
        caching=False,
        # remfile for HDF5-based files (such as NWB), fsspec for the others,
        # and for HDF5-based files that remfile fails to open
        backends="remfile,fsspec",
        # Do not initialize git-annex (modifying the repository) where it is
        # not
        init_annex=False,
    )
    atexit.register(adapter.__exit__, None, None, None)
    return adapter


_gc_lock = threading.Lock()
_gc_pauses = 0
_gc_was_enabled = False


class _GCPausedFile:
    """
    A file object streamed by datalad-fuse with fsspec, during whose lifetime
    automatic garbage collection is disabled

    h5py holds a global lock while it reads from a Python file object, and a
    read of an fsspec file waits for fsspec's I/O thread to fetch the data.  If
    a garbage collection ran in that thread meanwhile, finalizers calling h5py
    (e.g., those of h5py objects, or ``HDMFIO.__del__``, which checks whether
    the file is open) would wait for the same lock, deadlocking the process.
    Files read with remfile need no pause: remfile fetches the data in the
    reading thread.
    """

    def __init__(self, fp: Any) -> None:
        global _gc_pauses, _gc_was_enabled
        with _gc_lock:
            if _gc_pauses == 0:
                # Collect pending garbage now, in this thread, which does not
                # hold h5py's lock yet
                gc.collect()
                _gc_was_enabled = gc.isenabled()
                gc.disable()
            _gc_pauses += 1
        self._fp = fp
        self._paused = True

    def __getattr__(self, name: str) -> Any:
        return getattr(self._fp, name)

    def __enter__(self) -> _GCPausedFile:
        return self

    def __exit__(self, *_exc: Any) -> None:
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


@dataclass
class AnnexedReadableFile(Readable):
    """
    A `Readable` for a (locked) annexed file at ``filepath`` (a broken symbolic
    link) whose content is not present locally, which is streamed with
    datalad-fuse (see the module docstring).  ``url`` is only the first URL
    known for the content, for reporting: if it cannot be read, the adapter
    tries the others.

    Instances are obtained by calling `get_annexed_readable()`.
    """

    filepath: Path
    key: str
    size: int
    url: str
    adapter: Any = field(repr=False, compare=False)

    def open(self) -> IO[bytes]:
        fp = self.adapter.open(self.filepath, "rb")
        if type(fp).__name__ != "RemfileWrapper":
            fp = _GCPausedFile(fp)
        return cast("IO[bytes]", fp)

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
        from datalad_fuse.adapter import FileState
    except ImportError:
        # Not installed, or a version without pluggable backends
        return None
    try:
        dsap, relpath = get_adapter().resolve_dataset(filepath)
        if not dsap.annex_initialized:
            return None
        state, key = dsap.get_file_state(relpath)
    except Exception as e:
        # E.g., a repository without any commit
        lgr.debug("%s: Cannot be read with datalad-fuse: %s", filepath, e)
        return None
    if state is not FileState.NO_CONTENT or key is None or key.size is None:
        return None
    # Including the S3 exports git-annex knows no URLs on
    urls: Iterator[str] = chain(
        dsap.get_urls(str(key)), dsap.get_exporttree_urls(relpath, key)
    )
    url = next(urls, None)
    if url is None:
        lgr.debug("%s: git-annex knows no URL for key %s", filepath, key)
        return None
    return AnnexedReadableFile(
        filepath=filepath, key=str(key), size=key.size, url=url, adapter=get_adapter()
    )
