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

The URLs are tried in the order git-annex lists them; for a DataLad Dandiset,
that is the DANDI Archive's API download URL (which redirects to S3) before the
direct S3 URL.  datalad-fuse does not use HTTP proxy environment variables.

This requires datalad-fuse (``pip install "dandi[datalad]"``), which requires
DataLad and git-annex.

.. _git-annex: https://git-annex.branchable.com
.. _DataLad: https://www.datalad.org
.. _datalad-fuse: https://github.com/datalad/datalad-fuse
.. _fsspec: https://github.com/fsspec/filesystem_spec
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
import subprocess
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
    try:
        # datalad-fuse with pluggable backends (datalad/datalad-fuse#131):
        # remfile for HDF5-based files (such as NWB) if installed, fsspec
        # otherwise, as configured with datalad.fusefs.backends
        from datalad_fuse.adapter import RemoteFilesystemAdapter as Adapter
    except ImportError:
        from datalad_fuse.fsspec import FsspecAdapter as Adapter

    # caching=False: do not keep the streamed blocks on disk, in the dataset.
    # The root and all paths passed to the adapter must be absolute.
    adapter = Adapter(Path(os.path.abspath(os.sep)), caching=False)
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


_gc_lock = threading.Lock()
_gc_pauses = 0
_gc_was_enabled = False


class _GCPausedFile:
    """
    A file object streamed by datalad-fuse, during whose lifetime automatic
    garbage collection is disabled

    h5py holds a global lock while it reads from a Python file object, and the
    read waits for another thread (fsspec's I/O thread, or an HTTP server in
    the same process) to fetch the data.  If a garbage collection ran in that
    thread meanwhile, finalizers of h5py objects (e.g., of an unreferenced
    ``NWBHDF5IO``) would wait for the same lock, deadlocking the process.
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
        return cast("IO[bytes]", _GCPausedFile(self.adapter.open(self.filepath, "rb")))

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
    urls: Iterator[str] = dsap.get_urls(str(key))
    if hasattr(dsap, "get_exporttree_urls"):
        # Fallback to S3 exports of datalad/datalad-fuse#131
        urls = chain(urls, dsap.get_exporttree_urls(relpath, key))
    url = next(urls, None)
    if url is None:
        lgr.debug("%s: git-annex knows no URL for key %s", filepath, key)
        return None
    return AnnexedReadableFile(
        filepath=filepath, key=str(key), size=key.size, url=url, adapter=get_adapter()
    )
