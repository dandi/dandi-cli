from __future__ import annotations

from collections import Counter, deque
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import InitVar, dataclass, field
from datetime import datetime
from enum import Enum
from functools import partial
import hashlib
import inspect
import json
import os
import os.path as op
from pathlib import Path
import random
from shutil import rmtree
import sys
from threading import Lock
import time
from types import TracebackType
from typing import IO, Any, Literal

from dandischema.digests.dandietag import ETagHashlike
from dandischema.models import DigestType
from fasteners import InterProcessLock
import humanize
from interleave import FINISH_CURRENT, lazy_interleave
import requests

from . import get_logger
from .consts import RETRY_STATUSES, dandiset_metadata_file
from .dandiapi import AssetType, BaseRemoteZarrAsset, RemoteDandiset
from .dandiarchive import (
    AssetItemURL,
    DandisetURL,
    ParsedDandiURL,
    SingleAssetURL,
    parse_dandi_url,
)
from .dandiset import Dandiset
from .exceptions import NotFoundError
from .files import LocalAsset, find_dandi_files
from .support import pyout as pyouts
from .support.iterators import IteratorWithAggregation
from .support.pyout import naturalsize
from .utils import (
    Hasher,
    abbrev_prompt,
    ensure_datetime,
    exclude_from_zarr,
    flattened,
    is_same_time,
    path_is_subpath,
    pluralize,
    yaml_load,
)

lgr = get_logger()


class DownloadExisting(str, Enum):
    ERROR = "error"
    SKIP = "skip"
    OVERWRITE = "overwrite"
    OVERWRITE_DIFFERENT = "overwrite-different"
    REFRESH = "refresh"

    def __str__(self) -> str:
        return self.value


class DownloadFormat(str, Enum):
    PYOUT = "pyout"
    DEBUG = "debug"

    def __str__(self) -> str:
        return self.value


class PathType(str, Enum):
    EXACT = "exact"
    GLOB = "glob"

    def __str__(self) -> str:
        return self.value


def download(
    urls: str | Sequence[str],
    output_dir: str | Path,
    *,
    format: DownloadFormat = DownloadFormat.PYOUT,
    existing: DownloadExisting = DownloadExisting.ERROR,
    jobs: int = 1,
    jobs_per_zarr: int | None = None,
    get_metadata: bool = True,
    get_assets: bool = True,
    preserve_tree: bool = False,
    sync: bool = False,
    path_type: PathType = PathType.EXACT,
) -> None:
    # TODO: unduplicate with upload. For now stole from that one
    # We will again use pyout to provide a neat table summarizing our progress
    # with upload etc
    urls = flattened([urls])
    if not urls:
        # if no paths provided etc, we will download dandiset path
        # we are at, BUT since we are not git -- we do not even know
        # on which instance it exists!  Thus ATM we would do nothing but crash
        raise NotImplementedError("No URLs were provided.  Cannot download anything")

    parsed_urls = [parse_dandi_url(u, glob=path_type is PathType.GLOB) for u in urls]

    # dandi.cli.formatters are used in cmd_ls to provide switchable
    pyout_style = pyouts.get_style(hide_if_missing=False)

    rec_fields = ("path", "size", "done", "done%", "checksum", "status", "message")
    out = pyouts.LogSafeTabular(style=pyout_style, columns=rec_fields, max_workers=jobs)

    out_helper = PYOUTHelper()
    pyout_style["done"] = pyout_style["size"].copy()
    pyout_style["size"]["aggregate"] = out_helper.agg_size
    pyout_style["done"]["aggregate"] = out_helper.agg_done

    # I thought I was making a beautiful flower but ended up with cacti
    # which never blooms... All because assets are looped through inside download_generator
    # TODO: redo
    kw = dict(assets_it=out_helper.it)
    if jobs > 1:
        if format is DownloadFormat.PYOUT:
            # It could handle delegated to generator downloads
            kw["yield_generator_for_fields"] = rec_fields[1:]  # all but path
        else:
            lgr.warning(
                "Parallel downloads are not yet implemented for non-pyout format=%r. "
                "Download will proceed serially.",
                str(format),
            )

    downloaders = [
        Downloader(
            url=purl,
            output_dir=output_dir,
            existing=existing,
            get_metadata=get_metadata,
            get_assets=get_assets,
            preserve_tree=preserve_tree,
            jobs_per_zarr=jobs_per_zarr,
            on_error="yield" if format is DownloadFormat.PYOUT else "raise",
            **kw,
        )
        for purl in parsed_urls
    ]

    gen_ = (r for dl in downloaders for r in dl.download_generator())

    # Constructs to capture errors and handle them at the end
    errors = []

    def p4e_gen(callback):
        for v in callback:
            yield p4e(v)

    def p4e(out):
        if out.get("status") == "error":
            if out not in errors:
                errors.append(out)
        else:
            # If generator was yielded, we need to wrap it also with
            # our handling
            for k, v in out.items():
                if inspect.isgenerator(v):
                    rec[k] = p4e_gen(v)

        return out

    # TODOs:
    #  - redo frontends similarly to how command_ls did it
    #  - have a single loop with analysis of `rec` to either any file
    #    has failed to download.  If any was: exception should probably be
    #    raised.  API discussion for Python side of API:
    #
    if format is DownloadFormat.DEBUG:
        for rec in gen_:
            print(p4e(rec), flush=True)
    elif format is DownloadFormat.PYOUT:
        with out:
            for rec in gen_:
                out(p4e(rec))
    else:
        raise AssertionError(f"Unhandled DownloadFormat member: {format!r}")

    if sync:
        to_delete = [p for dl in downloaders for p in dl.delete_for_sync()]
        if to_delete:
            while True:
                opt = abbrev_prompt(
                    f"Delete {pluralize(len(to_delete), 'local asset')}?",
                    "yes",
                    "no",
                    "list",
                )
                if opt == "list":
                    for p in to_delete:
                        print(p)
                elif opt == "yes":
                    for p in to_delete:
                        if p.is_dir():
                            rmtree(p)
                        else:
                            p.unlink()
                    break
                else:
                    break
    if errors:
        raise RuntimeError(
            f"Encountered {pluralize(len(errors), 'error')} while downloading."
        )


@dataclass
class Downloader:
    """:meta private:"""

    url: ParsedDandiURL
    output_dir: InitVar[str | Path]
    output_prefix: Path = field(init=False)
    output_path: Path = field(init=False)
    existing: DownloadExisting
    get_metadata: bool
    get_assets: bool
    preserve_tree: bool
    jobs_per_zarr: int | None
    on_error: Literal["raise", "yield"]
    #: which will be set .gen to assets.  Purpose is to make it possible to get
    #: summary statistics while already downloading.  TODO: reimplement
    #: properly!
    assets_it: IteratorWithAggregation | None = None
    yield_generator_for_fields: tuple[str, ...] | None = None
    asset_download_paths: set[str] = field(init=False, default_factory=set)

    def __post_init__(self, output_dir: str | Path) -> None:
        # TODO: if we are ALREADY in a dandiset - we can validate that it is
        # the same dandiset and use that dandiset path as the one to download
        # under
        if isinstance(self.url, DandisetURL) or (
            self.preserve_tree and self.url.dandiset_id is not None
        ):
            assert self.url.dandiset_id is not None
            self.output_prefix = Path(self.url.dandiset_id)
        else:
            self.output_prefix = Path()
        self.output_path = Path(output_dir, self.output_prefix)

    def is_dandiset_yaml(self) -> bool:
        return isinstance(self.url, AssetItemURL) and self.url.path == "dandiset.yaml"

    def download_generator(self) -> Iterator[dict]:
        """
        A generator for downloads of files, folders, or entire dandiset from
        DANDI (as identified by URL)

        This function is a generator which yields records on ongoing
        activities.  Activities include traversal of the remote resource (DANDI
        Archive), download of individual assets while yielding records (TODO:
        schema) while validating their checksums "on the fly", etc.
        """

        with self.url.navigate(strict=True) as (client, dandiset, assets):
            if (
                (
                    isinstance(self.url, DandisetURL)
                    or self.is_dandiset_yaml()
                    or self.preserve_tree
                )
                and self.get_metadata
                and dandiset is not None
            ):
                for resp in _populate_dandiset_yaml(
                    self.output_path, dandiset, self.existing
                ):
                    yield {
                        "path": str(self.output_prefix / dandiset_metadata_file),
                        **resp,
                    }
                if self.is_dandiset_yaml():
                    return

            # TODO: do analysis of assets for early detection of needed renames
            # etc to avoid any need for late treatment of existing and also for
            # more efficient download if files are just renamed etc

            if not self.get_assets:
                return

            if self.assets_it:
                assets = self.assets_it.feed(assets)
            lock = Lock()
            for asset in assets:
                path = self.url.get_asset_download_path(
                    asset, preserve_tree=self.preserve_tree
                )
                self.asset_download_paths.add(path)
                download_path = Path(self.output_path, path)
                path = str(self.output_prefix / path)

                try:
                    metadata = asset.get_raw_metadata()
                except NotFoundError as e:
                    yield {"path": path, "status": "error", "message": str(e)}
                    continue
                d = metadata.get("digest", {})

                if asset.asset_type is AssetType.BLOB:
                    if "dandi:dandi-etag" in d:
                        digests = {"dandi-etag": d["dandi:dandi-etag"]}
                    else:
                        raise RuntimeError(
                            f"dandi-etag not available for asset. Known digests: {d}"
                        )
                    try:
                        digests["sha256"] = d["dandi:sha2-256"]
                    except KeyError:
                        pass
                    try:
                        mtime = ensure_datetime(metadata["blobDateModified"])
                    except KeyError:
                        mtime = None
                    if mtime is None:
                        lgr.warning(
                            "Asset %s is missing blobDateModified metadata field",
                            asset.path,
                        )
                        mtime = asset.modified
                    _download_generator = _download_file(
                        asset.get_download_file_iter(),
                        download_path,
                        toplevel_path=self.output_path,
                        # size and modified generally should be there but
                        # better to redownload than to crash
                        size=asset.size,
                        mtime=mtime,
                        existing=self.existing,
                        digests=digests,
                        lock=lock,
                    )

                else:
                    assert isinstance(
                        asset, BaseRemoteZarrAsset
                    ), f"Asset {asset.path} is neither blob nor Zarr"
                    _download_generator = _download_zarr(
                        asset,
                        download_path,
                        toplevel_path=self.output_path,
                        existing=self.existing,
                        jobs=self.jobs_per_zarr,
                        lock=lock,
                    )

                def _progress_filter(gen):
                    """To reduce load on pyout etc, make progress reports only if enough time
                    from prior report has passed (over 2 seconds) or we are done (got 100%).

                    Note that it requires "awareness" from the code below to issue other messages
                    with bundling with done% reporting if reporting on progress of some kind (e.g.,
                    adjusting "message").
                    """
                    prior_time = 0
                    warned = False
                    for rec in gen:
                        current_time = time.time()
                        if done_perc := rec.get("done%", 0):
                            if isinstance(done_perc, (int, float)):
                                if current_time - prior_time < 2 and done_perc != 100:
                                    continue
                            elif not warned:
                                warned = True
                                lgr.warning(
                                    "Received non numeric done%%: %r", done_perc
                                )
                        prior_time = current_time
                        yield rec

                # If exception is raised we might just raise it, or yield
                # an error record
                gen = {
                    "raise": _download_generator,
                    "yield": _download_generator_guard(path, _download_generator),
                }[self.on_error]
                gen = _progress_filter(gen)
                if self.yield_generator_for_fields:
                    yield {"path": path, self.yield_generator_for_fields: gen}
                else:
                    for resp in gen:
                        yield {**resp, "path": path}

    def delete_for_sync(self) -> list[Path]:
        """
        Returns the paths of local files that need to be deleted in order to
        sync the contents of `output_path` with the remote URL
        """
        if isinstance(self.url, SingleAssetURL):
            return []
        to_delete = []
        for df in find_dandi_files(
            self.output_path, dandiset_path=self.output_path, allow_all=True
        ):
            if not isinstance(df, LocalAsset):
                continue
            if (
                self.url.is_under_download_path(df.path)
                and df.path not in self.asset_download_paths
            ):
                to_delete.append(df.filepath)
        return to_delete


def _download_generator_guard(path: str, generator: Iterator[dict]) -> Iterator[dict]:
    try:
        yield from generator
    except Exception as exc:
        lgr.exception("Caught while downloading %s:", path)
        yield {
            "status": "error",
            "message": str(exc.__class__.__name__),
        }


class ItemsSummary:
    """A helper "structure" to accumulate information about assets to be downloaded

    To be used as a callback to IteratorWithAggregation
    """

    def __init__(self) -> None:
        self.files = 0
        # TODO: get rid of needing it
        self.t0: float | None = None  # when first record is seen
        self.size = 0
        self.has_unknown_sizes = False

    def as_dict(self) -> dict:
        return {
            "files": self.files,
            "size": self.size,
            "has_unknown_sizes": self.has_unknown_sizes,
        }

    # TODO: Determine the proper annotation for `rec`
    def __call__(self, rec: Any, prior: ItemsSummary | None = None) -> ItemsSummary:
        assert prior in (None, self)
        if not self.files:
            self.t0 = time.time()
        self.files += 1
        self.size += rec.size
        return self


class PYOUTHelper:
    """Helper for PYOUT styling

    Provides aggregation callbacks for PyOUT and also an iterator to be wrapped around
    iterating over assets, so it would get "totals" as soon as they are available.
    """

    def __init__(self):
        # Establish "fancy" download while still possibly traversing the dandiset
        # functionality.
        self.items_summary = ItemsSummary()
        self.it = IteratorWithAggregation(
            # unfortunately Yarik missed the point that we need to wrap
            # "assets" generator within downloader_generator
            # so we do not have assets here!  Ad-hoc solution for now is to
            # pass this beast so it could get .gen set within downloader_generator
            None,  # download_generator(urls, output_dir, existing=existing),
            self.items_summary,
        )

    def agg_files(self, *ignored: Any) -> str:
        ret = str(self.items_summary.files)
        if not self.it.finished:
            ret += "+"
        return ret

    def agg_size(self, sizes: Iterable[int]) -> str | list[str]:
        """Formatter for "size" column where it would show

        how much is "active" (or done)
        +how much yet to be "shown".
        """
        active = sum(sizes)
        if (active, self.items_summary.size) == (0, 0):
            return ""
        v = [naturalsize(active)]
        if not self.it.finished or (
            active != self.items_summary.size or self.items_summary.has_unknown_sizes
        ):
            extra = self.items_summary.size - active
            if extra < 0:
                lgr.debug("Extra size %d < 0 -- must not happen", extra)
            else:
                extra_str = "+%s" % naturalsize(extra)
                if not self.it.finished:
                    extra_str = ">" + extra_str
                if self.items_summary.has_unknown_sizes:
                    extra_str += "+?"
                v.append(extra_str)
        return v

    def agg_done(self, done_sizes: Iterator[int]) -> list[str]:
        """Formatter for "DONE" column"""
        done = sum(done_sizes)
        if self.it.finished and done == 0 and self.items_summary.size == 0:
            # even with 0s everywhere consider it 100%
            r = 1.0
        elif self.items_summary.size:
            r = done / self.items_summary.size
        else:
            r = 0
        pref = ""
        if not self.it.finished:
            pref += "<"
        if self.items_summary.has_unknown_sizes:
            pref += "?"
        v = [naturalsize(done), f"{pref}{100 * r:.2f}%"]
        if (
            done
            and self.items_summary.t0 is not None
            and r
            and self.items_summary.size != 0
        ):
            dt = time.time() - self.items_summary.t0
            more_time = (dt / r) - dt if r != 1 else 0
            more_time_str = humanize.naturaldelta(more_time)
            if not self.it.finished:
                more_time_str += "<"
            if self.items_summary.has_unknown_sizes:
                more_time_str += "+?"
            if more_time:
                v.append("ETA: %s" % more_time_str)
        return v


def _skip_file(msg: Any, **kwargs: Any) -> dict:
    return {"status": "skipped", "message": str(msg), **kwargs}


def _populate_dandiset_yaml(
    dandiset_path: str | Path, dandiset: RemoteDandiset, existing: DownloadExisting
) -> Iterator[dict]:
    metadata = dandiset.get_raw_metadata()
    if not metadata:
        lgr.warning(
            "Got completely empty metadata record for dandiset, not producing dandiset.yaml"
        )
        return
    dandiset_yaml = op.join(dandiset_path, dandiset_metadata_file)
    yield {"message": "updating"}
    lgr.debug("Updating %s from obtained dandiset metadata", dandiset_metadata_file)
    mtime = dandiset.modified
    if op.lexists(dandiset_yaml):
        with open(dandiset_yaml) as fp:
            if yaml_load(fp, typ="safe") == metadata:
                yield _skip_file("no change")
                return
        if existing is DownloadExisting.ERROR:
            yield {"status": "error", "message": "already exists"}
            return
        elif existing is DownloadExisting.REFRESH and op.lexists(
            op.join(dandiset_path, ".git", "annex")
        ):
            raise RuntimeError("Not refreshing path in git annex repository")
        elif existing is DownloadExisting.SKIP or (
            existing is DownloadExisting.REFRESH
            and os.lstat(dandiset_yaml).st_mtime >= mtime.timestamp()
        ):
            yield _skip_file("already exists", size=os.lstat(dandiset_yaml).st_mtime)
            return
    ds = Dandiset(dandiset_path, allow_empty=True)
    ds.path_obj.mkdir(exist_ok=True)  # exist_ok in case of parallel race
    old_metadata = ds.metadata
    ds.update_metadata(metadata)
    os.utime(dandiset_yaml, (time.time(), mtime.timestamp()))
    yield {
        "status": "done",
        "message": "updated" if metadata != old_metadata else "same",
    }


def _download_file(
    downloader: Callable[[int], Iterator[bytes]],
    path: Path,
    toplevel_path: str | Path,
    lock: Lock,
    size: int | None = None,
    mtime: datetime | None = None,
    existing: DownloadExisting = DownloadExisting.ERROR,
    digests: dict[str, str] | None = None,
    digest_callback: Callable[[str, str], Any] | None = None,
) -> Iterator[dict]:
    """
    Common logic for downloading a single file.

    Yields progress records that take the following forms::

        {"status": "skipped", "message": "<MESSAGE>"}
        {"size": <int>}
        {"status": "downloading"}
        {"done": <bytes downloaded>[, "done%": <percentage done, from 0 to 100>]}
        {"status": "error", "message": "<MESSAGE>"}
        {"checksum": "differs", "status": "error", "message": "<MESSAGE>"}
        {"checksum": "ok"}
        {"checksum": "-"}  #  No digests were provided
        {"status": "setting mtime"}
        {"status": "done"}

    Parameters
    ----------
    downloader: callable returning a generator
      A backend-specific fixture for downloading some file into path. It should
      be a generator yielding downloaded blocks.
    size: int, optional
      Target size if known
    digests: dict, optional
      possible checksums or other digests provided for the file. Only one
      will be used to verify download
    """
    # Avoid heavy import by importing within function:
    from .support.digests import get_digest

    if op.lexists(path):
        annex_path = op.join(toplevel_path, ".git", "annex")
        if existing is DownloadExisting.ERROR:
            raise FileExistsError(f"File {path!r} already exists")
        elif existing is DownloadExisting.SKIP:
            yield _skip_file("already exists")
            return
        elif existing is DownloadExisting.OVERWRITE:
            pass
        elif existing is DownloadExisting.OVERWRITE_DIFFERENT:
            realpath = op.realpath(path)
            key_parts = op.basename(realpath).split("-")
            if size is not None and os.stat(realpath).st_size != size:
                lgr.debug(
                    "Size of %s does not match size on server; redownloading", path
                )
            elif (
                op.lexists(annex_path)
                and op.islink(path)
                and path_is_subpath(realpath, op.abspath(annex_path))
                and key_parts[0] == "SHA256E"
                and digests
                and "sha256" in digests
            ):
                if key_parts[-1].partition(".")[0] == digests["sha256"]:
                    yield _skip_file("already exists")
                    return
                else:
                    lgr.debug(
                        "%s is in git-annex, and hash does not match hash on server; redownloading",
                        path,
                    )
            elif (
                digests is not None
                and "dandi-etag" in digests
                and get_digest(path, "dandi-etag") == digests["dandi-etag"]
            ):
                yield _skip_file("already exists")
                return
            elif (
                digests is not None
                and "dandi-etag" not in digests
                and "md5" in digests
                and get_digest(path, "md5") == digests["md5"]
            ):
                yield _skip_file("already exists")
                return
            else:
                lgr.debug(
                    "Etag of %s does not match etag on server; redownloading", path
                )
        elif existing is DownloadExisting.REFRESH:
            if op.lexists(annex_path):
                raise RuntimeError("Not refreshing path in git annex repository")
            if mtime is None:
                lgr.warning(
                    f"{path!r} - no mtime or ctime in the record, redownloading"
                )
            else:
                stat = os.stat(op.realpath(path))
                same = []
                if is_same_time(stat.st_mtime, mtime):
                    same.append("mtime")
                if size is not None and stat.st_size == size:
                    same.append("size")
                # TODO: use digests if available? or if e.g. size is identical
                # but mtime is different
                if same == ["mtime", "size"]:
                    # TODO: add recording and handling of .nwb object_id
                    yield _skip_file("same time and size", size=size)
                    return
                lgr.debug(f"{path!r} - same attributes: {same}.  Redownloading")

    if size is not None:
        yield {"size": size}

    destdir = Path(op.dirname(path))
    with lock:
        for p in (destdir, *destdir.parents):
            if p.is_file():
                p.unlink()
                break
            elif p.is_dir():
                break
        destdir.mkdir(parents=True, exist_ok=True)

    yield {"status": "downloading"}

    algo: str | None = None
    digester: Callable[[], Hasher] | None = None
    digest: str | None = None
    downloaded_digest: Hasher | None = None
    if digests:
        # choose first available for now.
        # TODO: reuse that sorting based on speed
        for algo, digest in digests.items():
            if algo == "dandi-etag" and size is not None:
                # Instantiate outside the lambda so that mypy is assured that
                # `size` is not None:
                hasher = ETagHashlike(size)
                digester = lambda: hasher  # noqa: E731
            else:
                digester = getattr(hashlib, algo, None)
            if digester is not None:
                break
        if digester is None:
            lgr.warning(
                "%s - found no digests in hashlib for any of %s", path, str(digests)
            )

    resuming = False
    attempt = 0
    attempts_allowed: int = (
        3  # number to do, could be incremented if we downloaded a little
    )
    while attempt <= attempts_allowed:
        attempt += 1
        try:
            if digester:
                downloaded_digest = digester()  # start empty
            warned = False
            # I wonder if we could make writing async with downloader
            with DownloadDirectory(path, digests or {}) as dldir:
                assert dldir.offset is not None
                downloaded_in_attempt = 0
                downloaded = dldir.offset
                resuming = downloaded > 0
                if size is not None and downloaded == size:
                    lgr.debug(
                        "%s - downloaded size matches target size of %d, exiting the loop",
                        path,
                        size,
                    )
                    # Exit early when downloaded == size, as making a Range
                    # request in such a case results in a 416 error from S3.
                    # Problems will result if `size` is None but we've already
                    # downloaded everything.
                    break
                for block in downloader(dldir.offset):
                    if digester:
                        assert downloaded_digest is not None
                        downloaded_digest.update(block)
                    downloaded += len(block)
                    downloaded_in_attempt += len(block)
                    out: dict[str, Any] = {"done": downloaded}
                    if size:
                        if downloaded > size and not warned:
                            warned = True
                            # Yield ERROR?
                            lgr.warning(
                                "%s - downloaded %d bytes although size was told to be just %d",
                                path,
                                downloaded,
                                size,
                            )
                        out["done%"] = 100 * downloaded / size
                    yield out
                    dldir.append(block)
            break
        except ValueError:
            # When `requests` raises a ValueError, it's because the caller
            # provided invalid parameters (e.g., an invalid URL), and so
            # retrying won't change anything.
            raise
        # Catching RequestException lets us retry on timeout & connection
        # errors (among others) in addition to HTTP status errors.
        except requests.RequestException as exc:
            attempts_allowed_or_not = _check_if_more_attempts_allowed(
                path=path,
                exc=exc,
                attempt=attempt,
                attempts_allowed=attempts_allowed,
                downloaded_in_attempt=downloaded_in_attempt,
            )
            if not isinstance(attempts_allowed_or_not, int) or not attempts_allowed:
                yield {"status": "error", "message": str(exc)}
                return
            attempts_allowed = attempts_allowed_or_not
    else:
        lgr.warning("downloader logic: We should not be here!")

    final_digest = None
    if downloaded_digest and not resuming:
        assert downloaded_digest is not None
        final_digest = downloaded_digest.hexdigest()  # we care only about hex
    elif digests:
        if resuming:
            lgr.debug("%s - resumed download. Need to check full checksum.", path)
        else:
            assert not downloaded_digest
            lgr.debug(
                "%s - no digest was checked online. Need to check full checksum", path
            )
        final_digest = get_digest(path, algo)
    if final_digest:
        if digest_callback is not None:
            assert isinstance(algo, str)
            digest_callback(algo, final_digest)
        if digest != final_digest:
            msg = f"{algo}: downloaded {final_digest} != {digest}"
            yield {"checksum": "differs", "status": "error", "message": msg}
            lgr.debug("%s - is different: %s.", path, msg)
            return
        else:
            yield {"checksum": "ok"}
            lgr.debug("%s - verified that has correct %s %s", path, algo, digest)
    else:
        lgr.debug("%s - no digests were provided", path)
        # shouldn't happen with more recent metadata etc
        yield {
            "checksum": "-",
            # "message": "no digests were provided"
        }

    # TODO: dissolve attrs and pass specific mtime?
    if mtime is not None:
        yield {"status": "setting mtime"}
        os.utime(path, (time.time(), mtime.timestamp()))

    yield {"status": "done"}


class DownloadDirectory:
    def __init__(self, filepath: str | Path, digests: dict[str, str]) -> None:
        #: The path to which to save the file after downloading
        self.filepath = Path(filepath)
        #: Expected hashes of the downloaded data, as a mapping from algorithm
        #: names to digests
        self.digests = digests
        #: The working directory in which downloaded data will be temporarily
        #: stored
        self.dirpath = self.filepath.with_name(self.filepath.name + ".dandidownload")
        #: The file in `dirpath` to which data will be written as it is
        #: received
        self.writefile = self.dirpath / "file"
        #: A `fasteners.InterProcessLock` on `dirpath`
        self.lock: InterProcessLock | None = None
        #: An open filehandle to `writefile`
        self.fp: IO[bytes] | None = None
        #: How much of the data has been downloaded so far
        self.offset: int | None = None

    def __enter__(self) -> DownloadDirectory:
        self.dirpath.mkdir(parents=True, exist_ok=True)
        self.lock = InterProcessLock(str(self.dirpath / "lock"))
        if not self.lock.acquire(blocking=False):
            raise RuntimeError(f"Could not acquire download lock for {self.filepath}")
        chkpath = self.dirpath / "checksum"
        try:
            with chkpath.open() as fp:
                digests = json.load(fp)
        except (FileNotFoundError, ValueError):
            digests = {}
        matching_algs = self.digests.keys() & digests.keys()
        if matching_algs and all(
            self.digests[alg] == digests[alg] for alg in matching_algs
        ):
            # Pick up where we left off, writing to the end of the file
            lgr.debug(
                "%s - download directory exists and has matching checksum(s) %s; resuming download",
                self.dirpath,
                matching_algs,
            )
            self.fp = self.writefile.open("ab")
        else:
            # Delete the file (if it even exists) and start anew
            if not chkpath.exists():
                lgr.debug(
                    "%s - no prior digests found; starting new download", self.dirpath
                )
            else:
                lgr.debug(
                    "%s - download directory found, but digests do not match;"
                    " starting new download",
                    self.dirpath,
                )
            try:
                self.writefile.unlink()
            except FileNotFoundError:
                pass
            self.fp = self.writefile.open("wb")
        with chkpath.open("w") as fp:
            json.dump(self.digests, fp)
        self.offset = self.fp.tell()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        assert self.fp is not None
        if exc_type is not None or exc_val is not None or exc_tb is not None:
            lgr.debug(
                "%s - entered __exit__ with position %d with exception: %s, %s",
                self.dirpath,
                self.fp.tell(),
                exc_type,
                exc_val,
            )
        else:
            lgr.debug(
                "%s - entered __exit__ with position %d without any exception",
                self.dirpath,
                self.fp.tell(),
            )
        self.fp.close()
        try:
            if exc_type is None:
                try:
                    self.writefile.replace(self.filepath)
                except (IsADirectoryError, PermissionError) as exc:
                    if isinstance(exc, PermissionError):
                        if not (
                            sys.platform.startswith("win") and self.filepath.is_dir()
                        ):
                            raise
                    lgr.debug(
                        "Destination path %s is a directory; removing it and retrying",
                        self.filepath,
                    )
                    rmtree(self.filepath)
                    self.writefile.replace(self.filepath)
        finally:
            assert self.lock is not None
            self.lock.release()
            if exc_type is None:
                rmtree(self.dirpath, ignore_errors=True)
            self.lock = None
            self.fp = None
            self.offset = None

    def append(self, blob: bytes) -> None:
        if self.fp is None:
            raise ValueError(
                "DownloadDirectory.append() called outside of context manager"
            )
        self.fp.write(blob)


def _download_zarr(
    asset: BaseRemoteZarrAsset,
    download_path: Path,
    toplevel_path: str | Path,
    existing: DownloadExisting,
    lock: Lock,
    jobs: int | None = None,
) -> Iterator[dict]:
    # Avoid heavy import by importing within function:
    from .support.digests import get_zarr_checksum

    # we will collect them all while starting the download
    # with the first page of entries received from the server.
    entries = []
    digests = {}
    pc = ProgressCombiner(zarr_size=asset.size)

    def digest_callback(path: str, algoname: str, d: str) -> None:
        if algoname == "md5":
            digests[path] = d

    def downloads_gen():
        for entry in asset.iterfiles():
            entries.append(entry)
            etag = entry.digest
            assert etag.algorithm is DigestType.md5
            yield pairing(
                str(entry),
                _download_file(
                    entry.get_download_file_iter(),
                    download_path / str(entry),
                    toplevel_path=toplevel_path,
                    size=entry.size,
                    mtime=entry.modified,
                    existing=existing,
                    digests={"md5": etag.value},
                    lock=lock,
                    digest_callback=partial(digest_callback, str(entry)),
                ),
            )
        pc.file_qty = len(entries)

    final_out: dict | None = None
    with lazy_interleave(
        downloads_gen(),
        onerror=FINISH_CURRENT,
        max_workers=jobs or 4,
    ) as it:
        for path, status in it:
            for out in pc.feed(path, status):
                if out.get("status") == "done":
                    final_out = out
                else:
                    yield out
            if final_out is not None:
                break
        else:
            return

    yield {"status": "deleting extra files"}
    remote_paths = set(map(str, entries))
    zarr_basepath = Path(download_path)
    dirs = deque([zarr_basepath])
    empty_dirs: deque[Path] = deque()
    while dirs:
        d = dirs.popleft()
        is_empty = True
        for p in list(d.iterdir()):
            if exclude_from_zarr(p):
                is_empty = False
            elif (
                p.is_file()
                and p.relative_to(zarr_basepath).as_posix() not in remote_paths
            ):
                try:
                    p.unlink()
                except OSError:
                    is_empty = False
            elif p.is_dir():
                dirs.append(p)
                is_empty = False
            else:
                is_empty = False
        if is_empty and d != zarr_basepath:
            empty_dirs.append(d)
    while empty_dirs:
        d = empty_dirs.popleft()
        d.rmdir()
        if d.parent != zarr_basepath and not any(d.parent.iterdir()):
            empty_dirs.append(d.parent)

    if "skipped" not in final_out["message"]:
        zarr_checksum = asset.get_digest().value
        local_checksum = get_zarr_checksum(zarr_basepath, known=digests)
        if zarr_checksum != local_checksum:
            msg = f"Zarr checksum: downloaded {local_checksum} != {zarr_checksum}"
            yield {"checksum": "differs", "status": "error", "message": msg}
            lgr.debug("%s is different: %s.", zarr_basepath, msg)
            return
        else:
            yield {"checksum": "ok"}
            lgr.debug(
                "Verified that %s has correct Zarr checksum %s",
                zarr_basepath,
                zarr_checksum,
            )

    yield {"status": "done"}


def _check_if_more_attempts_allowed(
    path: Path,
    exc: requests.RequestException,
    attempt: int,
    attempts_allowed: int,
    downloaded_in_attempt: int,
) -> int | None:
    """Check if we should retry the download, return potentially adjusted 'attempts_allowed'"""
    sleep_amount = random.random() * 5 * attempt
    if os.environ.get("DANDI_DOWNLOAD_AGGRESSIVE_RETRY"):
        # in such a case if we downloaded a little more --
        # consider it a successful attempt
        if downloaded_in_attempt > 0:
            lgr.debug(
                "%s - download failed on attempt #%d: %s, "
                "but did download %d bytes, so considering "
                "it a success and incrementing number of allowed attempts.",
                path,
                attempt,
                exc,
                downloaded_in_attempt,
            )
            attempts_allowed += 1
    if attempt >= attempts_allowed:
        lgr.debug("%s - download failed after %d attempts: %s", path, attempt, exc)
        return None
    # TODO: actually we should probably retry only on selected codes,
    elif exc.response is not None:
        if exc.response.status_code not in (
            400,  # Bad Request, but happened with gider:
            # https://github.com/dandi/dandi-cli/issues/87
            *RETRY_STATUSES,
        ):
            lgr.debug(
                "%s - download failed due to response %d: %s",
                path,
                exc.response.status_code,
                exc,
            )
            return None
        elif retry_after := exc.response.headers.get("Retry-After"):
            # playing safe
            if not str(retry_after).isdigit():
                # our code is wrong, do not crash but issue warning so
                # we might get report/fix it up
                lgr.warning(
                    "%s - download failed due to response %d with non-integer"
                    " Retry-After=%r: %s",
                    path,
                    exc.response.status_code,
                    retry_after,
                    exc,
                )
                return None
            sleep_amount = int(retry_after)
            lgr.debug(
                "%s - download failed due to response %d with "
                "Retry-After=%d: %s, will sleep and retry",
                path,
                exc.response.status_code,
                sleep_amount,
                exc,
            )
        else:
            lgr.debug(
                "%s - download failed on attempt #%d: %s, will sleep a bit and retry",
                path,
                attempt,
                exc,
            )
    # if is_access_denied(exc) or attempt >= 2:
    #     raise
    # sleep a little and retry
    else:
        lgr.debug(
            "%s - download failed on attempt #%d: %s, will sleep a bit and retry",
            path,
            attempt,
            exc,
        )
    time.sleep(sleep_amount)
    return attempts_allowed


def pairing(p: str, gen: Iterator[dict]) -> Iterator[tuple[str, dict]]:
    for d in gen:
        yield (p, d)


DLState = Enum("DLState", "STARTING DOWNLOADING SKIPPED ERROR CHECKSUM_ERROR DONE")


@dataclass
class DownloadProgress:
    state: DLState = DLState.STARTING
    downloaded: int = 0
    size: int | None = None


@dataclass
class ProgressCombiner:
    zarr_size: int
    file_qty: int | None = (
        None  # set to specific known value whenever full sweep is complete
    )
    files: dict[str, DownloadProgress] = field(default_factory=dict)
    #: Total size of all files that were not skipped and did not error out
    #: during download
    maxsize: int = 0
    prev_status: str = ""
    yielded_size: bool = False

    def get_done(self) -> dict:
        total_downloaded = sum(
            s.downloaded
            for s in self.files.values()
            if s.state
            in (
                DLState.DOWNLOADING,
                DLState.CHECKSUM_ERROR,
                DLState.SKIPPED,
                DLState.DONE,
            )
        )
        return {
            "done": total_downloaded,
            "done%": total_downloaded / self.zarr_size * 100 if self.zarr_size else 0,
        }

    def get_status(self, report_done: bool = True) -> dict:
        state_qtys = Counter(s.state for s in self.files.values())
        total = len(self.files)
        if (
            self.file_qty is not None  # if already known
            and total == self.file_qty
            and state_qtys[DLState.STARTING] == state_qtys[DLState.DOWNLOADING] == 0
        ):
            # All files have finished
            if state_qtys[DLState.ERROR] or state_qtys[DLState.CHECKSUM_ERROR]:
                new_status = "error"
            elif state_qtys[DLState.DONE]:
                new_status = "done"
            else:
                new_status = "skipped"
        elif total - state_qtys[DLState.STARTING] - state_qtys[DLState.SKIPPED] > 0:
            new_status = "downloading"
        else:
            new_status = ""

        statusdict = {}

        if report_done:
            msg_comps = []
            for msg_label, states in {
                "done": (DLState.DONE,),
                "errored": (DLState.ERROR, DLState.CHECKSUM_ERROR),
                "skipped": (DLState.SKIPPED,),
            }.items():
                if count := sum(state_qtys.get(state, 0) for state in states):
                    msg_comps.append(f"{count} {msg_label}")
            if msg_comps:
                statusdict["message"] = ", ".join(msg_comps)

        if new_status != self.prev_status:
            self.prev_status = statusdict["status"] = new_status

        if report_done and self.zarr_size:
            statusdict.update(self.get_done())

        return statusdict

    def feed(self, path: str, status: dict) -> Iterator[dict]:
        keys = list(status.keys())
        self.files.setdefault(path, DownloadProgress())
        size = status.get("size")
        if size is not None:
            if not self.yielded_size:
                # this thread will yield
                self.yielded_size = True
                yield {"size": self.zarr_size}
        if status.get("status") == "skipped":
            self.files[path].state = DLState.SKIPPED
            # Treat skipped as "downloaded" for the matter of accounting
            if size is not None:
                self.files[path].downloaded = size
                self.maxsize += size
            yield self.get_status()
        elif keys == ["size"]:
            self.files[path].size = size
            self.maxsize += status["size"]
            if any(s.state is DLState.DOWNLOADING for s in self.files.values()):
                yield self.get_done()
        elif status == {"status": "downloading"}:
            self.files[path].state = DLState.DOWNLOADING
            if out := self.get_status(report_done=False):
                yield out
        elif "done" in status:
            self.files[path].downloaded = status["done"]
            yield self.get_done()
        elif status.get("status") == "error":
            if "checksum" in status:
                self.files[path].state = DLState.CHECKSUM_ERROR
            else:
                self.files[path].state = DLState.ERROR
                sz = self.files[path].size
                if sz is not None:
                    self.maxsize -= sz
            yield self.get_status()
        elif keys == ["checksum"]:
            pass
        elif status == {"status": "setting mtime"}:
            pass
        elif status == {"status": "done"}:
            self.files[path].state = DLState.DONE
            yield self.get_status()
        else:
            lgr.warning(
                "Unexpected download status dict for %r received: %r", path, status
            )
