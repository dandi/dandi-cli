"""
Support for reading the content of annexed files in git-annex_ repositories
(such as DataLad_ datasets) when that content is not present locally.

In a git-annex repository, an annexed file is a symbolic link into
:file:`.git/annex/objects/`.  Until the content is fetched (e.g., with ``git
annex get`` or ``datalad get``), the link is broken.  The name of the link's
target is the file's *key*, which for the ``SHA256E`` and ``MD5E`` backends used
for DANDI Dandisets records the size of the content.  The URLs from which the
content can be retrieved are recorded in the ``git-annex`` branch of the
repository (the "URL log" of the key).

This module reads that information using only ``git`` (git-annex itself is not
required) and exposes the content of such files as a `Readable` that streams it
over HTTP(S) with fsspec_, so that, e.g., ``dandi validate`` can validate a
DataLad Dandiset without downloading the (possibly terabytes of) data.

.. _git-annex: https://git-annex.branchable.com
.. _DataLad: https://www.datalad.org
.. _fsspec: https://github.com/fsspec/filesystem_spec
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import logging
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import IO, ClassVar, cast

from ..misctypes import Readable

lgr = logging.getLogger("dandi.support.annex")

#: Regular expression matching DANDI Archive API "download" URLs, which
#: redirect to the actual storage location on every request and are thus less
#: efficient for streaming than the direct URLs also registered in git-annex
DANDI_API_DOWNLOAD_URL_RE = re.compile(
    r"/api/(?:dandisets/[^/]+/versions/[^/]+/)?assets/[^/]+/download/?(?:[?#].*)?$"
)

#: Block size (in bytes) for streaming reads of remote content
STREAM_BLOCK_SIZE = 4 * 1024 * 1024

#: Maximum number of blocks of remote content kept in memory per open file
STREAM_MAX_BLOCKS = 64


@dataclass(frozen=True)
class AnnexKey:
    """
    A parsed git-annex key, e.g., ``SHA256E-s1234--<hash>.nwb`` (see
    https://git-annex.branchable.com/internals/key_format/)
    """

    #: The key as a whole
    key: str

    #: The key backend, e.g., ``SHA256E`` or ``MD5E``
    backend: str

    #: The size of the content in bytes, if recorded in the key
    size: int | None

    #: The backend-specific part of the key following ``--``; for the checksum
    #: backends, this is the checksum followed (for the ``*E`` variants) by the
    #: file extension
    name: str

    @classmethod
    def parse(cls, key: str) -> AnnexKey:
        """Parse a git-annex key string"""
        fields, sep, name = key.partition("--")
        backend, *extra = fields.split("-")
        if not sep or not name or not backend:
            raise ValueError(f"Not a git-annex key: {key!r}")
        size = None
        for f in extra:
            if f[:1] == "s" and f[1:].isdigit():
                size = int(f[1:])
        return cls(key=key, backend=backend, size=size, name=name)

    def __str__(self) -> str:
        return self.key

    @property
    def hashdir_lower(self) -> str:
        """
        The two-level hash directory under which git-annex stores the key's
        log files in the ``git-annex`` branch
        """
        h = hashlib.md5(self.key.encode("utf-8"), usedforsecurity=False).hexdigest()
        return f"{h[:3]}/{h[3:6]}"


def get_annex_key(path: str | Path) -> AnnexKey | None:
    """
    Return the git-annex key of the annexed file at ``path``, or `None` if
    ``path`` is not a symbolic link into a git-annex object store
    """
    try:
        target = os.readlink(path)
    except OSError:
        # Not a symlink (or does not exist at all)
        return None
    parts = PurePosixPath(target.replace(os.sep, "/")).parts
    if not any(a == "annex" and b == "objects" for a, b in zip(parts, parts[1:])):
        return None
    try:
        return AnnexKey.parse(parts[-1])
    except ValueError:
        return None


def parse_url_log(text: str) -> list[str]:
    """
    Parse the content of a git-annex URL log (a ``<key>.log.web`` file in the
    ``git-annex`` branch), whose lines are of the form ``<timestamp>s <status>
    <url>``, and return the URLs whose most recent status is ``1`` (present).

    Direct URLs are sorted before DANDI Archive API download URLs; otherwise,
    the order is that of first appearance in the log.
    """
    latest: dict[str, tuple[float, str]] = {}
    for line in text.splitlines():
        try:
            ts, status, url = line.split(" ", 2)
            t = float(ts.rstrip("s"))
        except ValueError:
            lgr.debug("Ignoring unparsable git-annex URL log line: %r", line)
            continue
        if url not in latest or t > latest[url][0]:
            latest[url] = (t, status)
    urls = [url for url, (_, status) in latest.items() if status == "1"]
    return sorted(urls, key=lambda u: DANDI_API_DOWNLOAD_URL_RE.search(u) is not None)


class AnnexRepo:
    """
    Read-only access to the git-annex metadata (the ``git-annex`` branch) of a
    Git repository, using only ``git``.  Instances are obtained with `find()`
    and are cached per repository root.
    """

    _instances: ClassVar[dict[Path, AnnexRepo]] = {}

    def __init__(self, root: Path) -> None:
        #: The root (top-level directory) of the repository
        self.root = root
        self._annex_ref: str | None = None
        self._annex_ref_resolved = False
        self._urls: dict[str, list[str]] = {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}({str(self.root)!r})"

    @classmethod
    def find(cls, path: str | Path) -> AnnexRepo | None:
        """
        Return the `AnnexRepo` for the repository containing ``path`` (the
        closest parent directory containing a ``.git`` directory or file), or
        `None` if ``path`` is not inside a Git repository
        """
        p = Path(os.path.abspath(path))
        for d in (p, *p.parents):
            if os.path.lexists(d / ".git"):
                return cls._instances.setdefault(d, cls(d))
        return None

    def _git(self, *args: str) -> str | None:
        """
        Run a ``git`` command in the repository and return its standard output,
        or `None` if it failed
        """
        try:
            r = subprocess.run(
                ["git", "-C", str(self.root), *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            lgr.warning(
                "git is not installed; cannot read git-annex metadata of %s", self.root
            )
            return None
        if r.returncode != 0:
            lgr.debug(
                "git %s failed in %s: %s", " ".join(args), self.root, r.stderr.strip()
            )
            return None
        return r.stdout

    @property
    def annex_ref(self) -> str | None:
        """
        The ref of the ``git-annex`` branch: the local branch if there is one,
        otherwise a remote-tracking branch (preferring that of ``origin``); or
        `None` if the repository has no git-annex metadata
        """
        if not self._annex_ref_resolved:
            self._annex_ref_resolved = True
            out = self._git(
                "for-each-ref",
                "--format=%(refname)",
                "refs/heads/git-annex",
                "refs/remotes/*/git-annex",
            )
            if out is not None and (refs := out.split()):
                for preferred in (
                    "refs/heads/git-annex",
                    "refs/remotes/origin/git-annex",
                ):
                    if preferred in refs:
                        self._annex_ref = preferred
                        break
                else:
                    self._annex_ref = sorted(refs)[0]
        return self._annex_ref

    def get_urls(self, key: AnnexKey | str) -> list[str]:
        """
        Return the URLs registered in git-annex for the given key (see
        `parse_url_log()` for their order), or an empty list if there are none
        or the git-annex metadata cannot be read
        """
        if isinstance(key, str):
            key = AnnexKey.parse(key)
        if (urls := self._urls.get(key.key)) is None:
            urls = []
            if (ref := self.annex_ref) is not None:
                out = self._git(
                    "cat-file", "-p", f"{ref}:{key.hashdir_lower}/{key.key}.log.web"
                )
                if out is not None:
                    urls = parse_url_log(out)
            self._urls[key.key] = urls
        return urls


@dataclass
class AnnexReadableFile(Readable):
    """
    A `Readable` for an annexed file whose content is not present locally and
    is instead streamed from the URL(s) registered for it in git-annex.  The
    fsspec_ library must be installed with the ``http`` extra (e.g., ``pip
    install "dandi[extras]"``) in order for `.open()` to be usable.

    Instances are obtained by calling `get_annex_readable()`.

    .. _fsspec: http://github.com/fsspec/filesystem_spec
    """

    #: The path of the (broken) symbolic link to the file's content
    filepath: Path

    #: The git-annex key of the file
    key: AnnexKey

    #: The URLs from which the content can be retrieved, in order of preference
    urls: list[str]

    def open(self) -> IO[bytes]:
        """
        Open the content for random-access reading from the first URL that can
        be opened, streaming it in blocks on demand
        """
        # Optional dependency:
        from aiohttp import ClientTimeout
        import fsspec
        from fsspec.caching import caches as fsspec_caches

        if not self.urls:
            raise RuntimeError(f"{self.filepath}: No URLs registered in git-annex")
        # fsspec's LRU block cache (which suits h5py's random access) was
        # registered as "block" before it was renamed to "blockcache" in 2023
        cache_type = "blockcache" if "blockcache" in fsspec_caches else "block"
        # fsspec logs every block it fetches at INFO level, which is too noisy
        # for the (INFO-level by default) dandi CLI output; quiet that unless
        # the user configured that logger themselves
        if (fsspec_lgr := logging.getLogger("fsspec.caching")).level == logging.NOTSET:
            fsspec_lgr.setLevel(logging.WARNING)
        error: Exception | None = None
        for url in self.urls:
            lgr.debug("%s: Opening %s for streaming", self.filepath, url)
            try:
                # We need to call open() on the return value of fsspec.open()
                # because otherwise the filehandle will only be opened when
                # used to enter a context manager.
                return cast(
                    IO[bytes],
                    fsspec.open(
                        url,
                        mode="rb",
                        block_size=STREAM_BLOCK_SIZE,
                        cache_type=cache_type,
                        cache_options={"maxblocks": STREAM_MAX_BLOCKS},
                        client_kwargs={
                            # Explicit timeouts prevent indefinite hangs in
                            # fsspec's sync() wrapper on a stalled connection;
                            # see the same in `RemoteReadableAsset.open()`.
                            "timeout": ClientTimeout(
                                total=120, sock_read=60, sock_connect=30
                            ),
                            # Honor HTTP(S)_PROXY etc. environment variables
                            "trust_env": True,
                        },
                    ).open(),
                )
            except Exception as e:
                lgr.warning(
                    "%s: Could not open %s for streaming: %s: %s",
                    self.filepath,
                    url,
                    type(e).__name__,
                    e,
                )
                error = e
        assert error is not None
        raise error

    def get_size(self) -> int:
        if self.key.size is None:
            raise ValueError(f"git-annex key {self.key} does not record a size")
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


def get_annex_readable(path: str | Path) -> AnnexReadableFile | None:
    """
    Return an `AnnexReadableFile` for streaming the content of the annexed file
    at ``path``, or `None` if ``path`` is not a symbolic link into a git-annex
    object store or its key does not record the size of the content.  The
    returned object's ``urls`` list is empty if no URLs are registered for the
    file (or the repository's git-annex metadata cannot be read).
    """
    filepath = Path(path)
    key = get_annex_key(filepath)
    if key is None or key.size is None:
        return None
    repo = AnnexRepo.find(filepath.parent)
    urls = repo.get_urls(key) if repo is not None else []
    return AnnexReadableFile(filepath=filepath, key=key, urls=urls)
