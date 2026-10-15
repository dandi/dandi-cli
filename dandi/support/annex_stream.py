"""
Reading the content of annexed files of git-annex_ repositories (such as
DataLad_ datasets) that is not present locally, by streaming it.

In a git-annex repository, a (locked) annexed file is a symbolic link into
:file:`.git/annex/objects/`, which is broken until the content is fetched.  Its
target names the git-annex key of the content, which records the size of the
content, and git-annex knows URLs for the key (``git annex whereis``).  The
content is read from those URLs with remfile_, which fetches only the parts of
a file that are read, in requests sized for the access pattern of HDF5-based
files (such as NWB), so that the files of a DataLad Dandiset can be read (e.g.,
for their metadata, or to be validated) without downloading the (possibly
terabytes of) data.

The URLs are tried in the order git-annex lists them; for a DataLad Dandiset,
that is the DANDI Archive's API download URL (which redirects to S3) before the
direct S3 URL.

This requires git-annex and remfile (``pip install "dandi[streaming]"``).  No
``git annex`` command is run in a repository in which git-annex is not
initialized (e.g., a fresh ``git clone``), as it would initialize git-annex
there, modifying the repository.

.. _git-annex: https://git-annex.branchable.com
.. _DataLad: https://www.datalad.org
.. _remfile: https://github.com/flatironinstitute/remfile
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
import io
import json
import logging
import os
from pathlib import Path
import re
import subprocess
from typing import IO, Any, cast

from ..misctypes import Readable

lgr = logging.getLogger("dandi.support.annex_stream")

#: Seconds to wait for a server to start answering a request
REQUEST_TIMEOUT = 60


@cache
def annex_initialized(directory: Path) -> bool:
    """
    Whether ``directory`` is in a Git repository in which git-annex is
    initialized.  (Any ``git annex`` command would otherwise initialize it,
    modifying the repository.)
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


def annex_key_size(key: str) -> int | None:
    """
    The size of the content of a git-annex key, as recorded in the key (e.g.,
    ``SHA256E-s1234--<checksum>.nwb``), or `None` if it is not
    """
    fields = key.split("--", 1)[0].split("-")
    for f in fields[1:]:
        if m := re.fullmatch(r"s(\d+)", f):
            return int(m[1])
    return None


def annex_urls(directory: Path, key: str) -> list[str]:
    """
    The http(s) URLs git-annex knows for ``key`` (in the order ``git annex
    whereis`` lists them), in the repository at ``directory``, in which
    git-annex must be initialized
    """
    r = subprocess.run(
        ["git", "-C", str(directory), "annex", "whereis", "--json", "--key", key],
        capture_output=True,
        text=True,
    )
    try:
        info = json.loads(r.stdout)
    except ValueError:
        lgr.debug("git annex whereis --key %s failed: %s", key, r.stderr.strip())
        return []
    urls: list[str] = []
    for location in info.get("whereis", []) + info.get("untrusted", []):
        for url in location.get("urls", []):
            if url.lower().startswith(("http://", "https://")) and url not in urls:
                urls.append(url)
    return urls


class RemoteFile(io.RawIOBase):
    """
    A seekable, read-only binary file object reading the content at ``url``
    (of ``size`` bytes) with remfile, which fetches it in the reading thread
    """

    def __init__(self, url: str, size: int) -> None:
        super().__init__()
        # Optional dependency:
        import remfile

        self.url = url
        self.size = size
        # Passing the size spares a request for it
        self._fp = remfile.File(url, _size=size)

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        view = memoryview(buffer).cast("B")
        n = min(len(view), max(self.size - self._fp.tell(), 0))
        if n == 0:
            return 0
        data = self._fp.read(n)
        view[: len(data)] = data
        return len(data)

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        self._fp.seek(offset, whence)
        return int(self._fp.tell())

    def tell(self) -> int:
        return int(self._fp.tell())

    def close(self) -> None:
        if not self.closed:
            self._fp.close()
        super().close()


def _responds(url: str) -> bool:
    """Whether a range request for the first byte at ``url`` succeeds"""
    # Avoid importing requests when this module is imported:
    import requests

    try:
        with requests.get(
            url,
            headers={"Range": "bytes=0-0"},
            stream=True,
            timeout=REQUEST_TIMEOUT,
        ) as r:
            return r.status_code in (200, 206)
    except requests.RequestException as e:
        lgr.debug("%s: Request failed: %s", url, e)
        return False


@dataclass
class AnnexedReadableFile(Readable):
    """
    A `Readable` for a (locked) annexed file at ``filepath`` (a broken symbolic
    link) whose content is not present locally, which is streamed from the
    first of ``urls`` (the http(s) URLs git-annex knows for the content) that
    can be read (see the module docstring).

    Instances are obtained by calling `get_annexed_readable()`.
    """

    filepath: Path
    key: str
    size: int
    urls: list[str]
    _url: str | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def url(self) -> str:
        """The URL the content is read from (once it was opened), else the first"""
        return self._url if self._url is not None else self.urls[0]

    def open(self) -> IO[bytes]:
        if self._url is None:
            for url in self.urls:
                if _responds(url):
                    self._url = url
                    break
                lgr.debug("%s: Cannot read %s", self.filepath, url)
            else:
                raise OSError(
                    f"{self.filepath}: None of the URLs of its content can be read:"
                    f" {', '.join(self.urls)}"
                )
        return cast("IO[bytes]", RemoteFile(self._url, self.size))

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
    """Whether the requirements for streaming (remfile) are installed"""
    try:
        import remfile  # noqa: F401
    except ImportError:
        return False
    return True


def get_annexed_readable(path: str | Path) -> AnnexedReadableFile | None:
    """
    Return an `AnnexedReadableFile` for streaming the content of the annexed
    file at ``path``, or `None` if remfile is not installed, ``path`` is not a
    (locked) annexed file whose content is missing in a repository in which
    git-annex is initialized, its key does not record the size of the content,
    or git-annex knows no http(s) URL to stream it from
    """
    filepath = Path(os.path.abspath(path))
    if not filepath.is_symlink() or filepath.exists():
        # Not a broken symbolic link
        return None
    if not can_stream():
        return None
    target = Path(os.readlink(filepath))
    if ".git/annex/objects" not in target.as_posix():
        return None
    key = target.name
    size = annex_key_size(key)
    if size is None:
        lgr.debug("%s: The key %s does not record the size", filepath, key)
        return None
    if not annex_initialized(filepath.parent):
        return None
    urls = annex_urls(filepath.parent, key)
    if not urls:
        lgr.debug("%s: git-annex knows no URL for key %s", filepath, key)
        return None
    return AnnexedReadableFile(filepath=filepath, key=key, size=size, urls=urls)
