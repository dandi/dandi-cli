"""Validation of DANDI datasets against schemas and standards.

This module provides validation functionality for dandisets, including:
- DANDI schema validation
- BIDS standard validation
- File layout and organization validation
- Metadata completeness checking
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from concurrent.futures import Future, ProcessPoolExecutor
from copy import copy
from functools import partial
from importlib.util import find_spec
import logging
from logging.handlers import QueueHandler, QueueListener
from multiprocessing import get_context
import os
from pathlib import Path
import shutil
from threading import Lock
from typing import Any

from ._types import (
    ORIGIN_VALIDATION_DANDI_LAYOUT,
    MissingFileContent,
    Origin,
    OriginType,
    Scope,
    Severity,
    Standard,
    ValidationResult,
    Validator,
)
from .. import get_logger
from ..consts import dandiset_metadata_file
from ..files import (
    BIDSAsset,
    DandiFile,
    LocalAsset,
    LocalFileAsset,
    NWBAsset,
    find_dandi_files,
)
from ..support.datalad_fuse import AnnexedReadableFile, get_annexed_readable
from ..utils import find_parent_directory_containing

lgr = get_logger()

BIDS_TO_DANDI = {
    "subject": "subject_id",
    "session": "session_id",
}


def validate_bids(
    *paths: str | Path,
    schema_version: str | None = None,
) -> list[ValidationResult]:
    """Validate BIDS paths.

    Parameters
    ----------
    paths : list(str)
        Paths to validate.
    devel_debug : bool, optional
        Whether to trigger debugging in the BIDS validator.

    Returns
    -------
    dict
        Dictionary reporting required patterns not found and existing filenames not matching any
        patterns.

    Notes
    -----
    - Eventually this should be migrated to BIDS schema specified errors, see discussion here:
        https://github.com/bids-standard/bids-specification/issues/1262
    """

    import bidsschematools
    from bidsschematools.validator import validate_bids as validate_bids_

    validation_result = validate_bids_(paths, exclude_files=["dandiset.yaml"])
    our_validation_result = []
    origin = Origin(
        type=OriginType.VALIDATION,
        validator=Validator.bidsschematools,
        validator_version=bidsschematools.__version__,
        standard=Standard.BIDS,
        standard_version=validation_result["bids_version"],
    )

    # Storing variable to not re-compute set paths for each individual file.
    parent_path = None
    for path in validation_result["path_tracking"]:
        # Hard-coding exclusion here pending feature + release in:
        # https://github.com/bids-standard/bids-specification/issues/1272
        if path.endswith((".ERRORS", ".ERRORS.json")):
            continue
        if parent_path != os.path.dirname(path):
            parent_path = os.path.dirname(path)
            dataset_path = find_parent_directory_containing(
                "dataset_description.json", parent_path
            )
            dandiset_path = find_parent_directory_containing(
                "dandiset.yaml", parent_path
            )
        our_validation_result.append(
            ValidationResult(
                origin=origin,
                severity=Severity.ERROR,
                id="BIDS.NON_BIDS_PATH_PLACEHOLDER",
                scope=Scope.FILE,
                origin_result=validation_result,
                path=Path(path),
                message="File does not match any pattern known to BIDS.",
                dataset_path=dataset_path,
                dandiset_path=dandiset_path,
            )
        )

    for pattern in validation_result["schema_tracking"]:
        # Future proofing for standard-compliant name.
        if pattern.get("mandatory") or pattern.get("required"):
            # We don't have a path for this so we'll need some external logic to make sure
            # that the dataset path is populated.
            # dataset_path = find_parent_directory_containing(paths, path)
            our_validation_result.append(
                ValidationResult(
                    origin=origin,
                    severity=Severity.ERROR,
                    id="BIDS.MANDATORY_FILE_MISSING_PLACEHOLDER",
                    scope=Scope.DATASET,
                    origin_result=validation_result,
                    path_regex=pattern["regex"],
                    message="BIDS-required file is not present.",
                )
            )

    # Storing variable to not re-compute set paths for each individual file.
    parent_path = None
    for meta in validation_result["match_listing"]:
        file_path = meta.pop("path")
        meta = {BIDS_TO_DANDI[k]: v for k, v in meta.items() if k in BIDS_TO_DANDI}
        if parent_path != os.path.dirname(file_path):
            parent_path = os.path.dirname(file_path)
            dataset_path = find_parent_directory_containing(
                "dataset_description.json", parent_path
            )
            dandiset_path = find_parent_directory_containing(
                "dandiset.yaml", parent_path
            )
        our_validation_result.append(
            ValidationResult(
                origin=origin,
                id="BIDS.MATCH",
                scope=Scope.FILE,
                origin_result=validation_result,
                path=Path(file_path),
                metadata=meta,
                dataset_path=dataset_path,
                dandiset_path=dandiset_path,
            )
        )

    return our_validation_result


def _is_broken_symlink(filepath: Path) -> bool:
    """Return True if *filepath* is a symlink whose target does not exist."""
    return filepath.is_symlink() and not filepath.exists()


# BIDS error codes that require reading file content (headers, pixel data).
# When ``only-non-data`` or ``stream`` is active these are suppressed for
# broken-symlink files (the BIDS validator cannot stream content).
_BIDS_CONTENT_DEPENDENT_CODES = frozenset(
    {
        "BIDS.NIFTI_HEADER_UNREADABLE",
        "BIDS.EMPTY_FILE",
    }
)


def validate(
    *paths: str | Path,
    schema_version: str | None = None,
    devel_debug: bool = False,
    allow_any_path: bool = False,
    missing_file_content: MissingFileContent = MissingFileContent.error,
    jobs: int = 1,
) -> Iterator[ValidationResult]:
    """Validate content

    Parameters
    ----------
    paths : list(str)
      Could be individual (.nwb) files or a single dandiset path.
    missing_file_content : MissingFileContent
      Policy for files whose content is unavailable (e.g. broken symlinks in a
      datalad dataset without fetched data).  ``error`` emits a concise error,
      ``skip`` skips the file with a warning, ``only-non-data`` skips
      content-dependent validators but still validates path layout, and
      ``stream`` streams the content of annexed files with datalad-fuse (see
      `dandi.support.datalad_fuse`) so that
      content-dependent validators run without the content being present
      locally.
    jobs : int
      Number of processes in which to validate NWB files (other than those of
      BIDS datasets) in parallel; the results are yielded in the same order
      as with 1 (the default), with which everything is validated in this
      process.

    Yields
    ------
    path, errors
      errors for a path
    """
    if missing_file_content == MissingFileContent.stream:
        _check_streaming_requirements()

    # Archive of unique `ValidationResult` objects obtained through
    # `DandiFile.get_validation_errors()`
    # Note: This is needed to hold on to the unique `ValidationResult` objects
    #   so that they don't get garbage collected, ensuring that the same ID in
    #   `df_result_ids` is always associated with the same object.
    df_results: list[ValidationResult] = []

    # The ids of the objects in `df_results` obtain through the `id()` built-in function
    df_result_ids: set[int] = set()

    def unique(results: list[ValidationResult]) -> Iterator[ValidationResult]:
        for r in results:
            r_id = id(r)
            if r_id not in df_result_ids:
                df_results.append(r)
                df_result_ids.add(r_id)
                yield r

    # The results of the files, in order, either computed or being computed
    # in `pool`
    pending: deque[list[ValidationResult] | Future[list[ValidationResult]]]
    pending = deque()
    # The files to validate (and the results for paths not in a Dandiset), all
    # found first so that the progress can be reported as a count
    items: list[DandiFile | ValidationResult] = []
    # The `dataset_description.json` files of BIDS datasets, which the
    # `BIDSAsset` files found refer to only weakly
    bids_descriptions = []
    for p in paths:
        p = os.path.abspath(p)
        dandiset_path = find_parent_directory_containing(dandiset_metadata_file, p)
        if dandiset_path is None:
            items.append(
                ValidationResult(
                    id="DANDI.NO_DANDISET_FOUND",
                    origin=ORIGIN_VALIDATION_DANDI_LAYOUT,
                    severity=Severity.ERROR,
                    scope=Scope.DANDISET,
                    path=Path(p),
                    message="Path is not inside a Dandiset",
                )
            )
        for df in find_dandi_files(
            p, dandiset_path=dandiset_path, allow_all=allow_any_path
        ):
            if isinstance(df, BIDSAsset):
                bids_descriptions.append(df.bids_dataset_description)
            items.append(df)
    progress = _Progress(sum(isinstance(i, DandiFile) for i in items))

    pool = _ValidationPool(jobs) if jobs > 1 else None
    try:
        for item in items:
            if isinstance(item, ValidationResult):
                pending.append([item])
                continue
            df = item
            # Handle broken symlinks (missing file content)
            is_broken = _is_broken_symlink(df.filepath)
            if is_broken:
                if missing_file_content == MissingFileContent.stream:
                    readable = _prepare_streaming(df)
                    # A file whose content cannot be streamed gets an error
                    # and is otherwise skipped
                    skip_file = readable is None
                else:
                    readable = None
                    skip_file = missing_file_content in (
                        MissingFileContent.skip,
                        MissingFileContent.error,
                    )
                pending.append(
                    [_handle_missing_content(df, missing_file_content, readable)]
                )
                if skip_file:
                    progress.done(df, None)
                    continue
                # only-non-data & stream: fall through but pass the policy
                # to the validators

            file_policy = missing_file_content if is_broken else None
            if pool is not None and type(df) is NWBAsset:
                future = pool.submit(df, schema_version, devel_debug, file_policy)
                future.add_done_callback(partial(progress.future_done, df))
                pending.append(future)
            else:
                results = _validate_file(df, schema_version, devel_debug, file_policy)
                progress.done(df, results)
                pending.append(results)
            # Yield what is ready, or wait (for the oldest file) if enough
            # files are being validated
            while pending and (
                isinstance(pending[0], list)
                or pending[0].done()
                or (pool is not None and len(pending) > 2 * jobs)
            ):
                head = pending.popleft()
                yield from unique(head if isinstance(head, list) else head.result())
        while pending:
            head = pending.popleft()
            yield from unique(head if isinstance(head, list) else head.result())
    finally:
        if pool is not None:
            pool.shutdown()


class _Progress:
    """Report the progress of validating ``total`` files with log messages"""

    def __init__(self, total: int) -> None:
        self.total = total
        self.count = 0
        # Files may be done in the threads of a `_ValidationPool`
        self.lock = Lock()
        if total:
            lgr.info("Validating %d file%s", total, "" if total == 1 else "s")

    def done(
        self,
        df: DandiFile,
        results: list[ValidationResult] | None,
        outcome: str = "skipped",
    ) -> None:
        """
        Report that validating ``df`` is done, with the given results, or
        `None` if it was not validated, for the reason ``outcome``
        """
        with self.lock:
            self.count += 1
            if results is None:
                pass
            elif results:
                outcome = f"{len(results)} issue{'' if len(results) == 1 else 's'}"
            else:
                outcome = "OK"
            path = df.path if isinstance(df, LocalAsset) else df.filepath
            lgr.info("[%d/%d] %s: %s", self.count, self.total, path, outcome)

    def future_done(
        self, df: DandiFile, future: Future[list[ValidationResult]]
    ) -> None:
        """Report that validating ``df`` in a `_ValidationPool` is done"""
        if future.cancelled() or future.exception() is not None:
            self.done(df, None, outcome="failed")
        else:
            self.done(df, future.result())


def _validate_file(
    df: DandiFile,
    schema_version: str | None,
    devel_debug: bool,
    missing_file_content: MissingFileContent | None,
) -> list[ValidationResult]:
    """
    Return the results of validating ``df``; ``missing_file_content`` is the
    policy for its missing content, if it is missing
    """
    results = []
    for r in df.get_validation_errors(
        schema_version=schema_version,
        devel_debug=devel_debug,
        missing_file_content=missing_file_content,
    ):
        # For broken-symlink files under only-non-data and stream, suppress
        # BIDS errors that require reading file content (e.g.
        # NIFTI_HEADER_UNREADABLE).  The validator ran in full so real files
        # still get those checks.
        if (
            missing_file_content
            in (MissingFileContent.only_non_data, MissingFileContent.stream)
            and r.id in _BIDS_CONTENT_DEPENDENT_CODES
        ):
            continue
        results.append(r)
    return results


def _validate_file_in_worker(
    df: LocalFileAsset,
    schema_version: str | None,
    devel_debug: bool,
    missing_file_content: MissingFileContent | None,
) -> list[ValidationResult]:
    """`_validate_file()` in a worker process of a `_ValidationPool`"""
    if missing_file_content == MissingFileContent.stream:
        # The streamed content is opened in this process
        _prepare_streaming(df)
    return _validate_file(df, schema_version, devel_debug, missing_file_content)


def _init_worker(log_queue: Any, levels: dict[str, int]) -> None:
    """
    Set up a worker process of a `_ValidationPool`: send the log records to
    the parent process, and ignore the warnings that it ignores
    """
    # Avoid heavy import by importing within function:
    from ..pynwb_utils import ignore_benign_pynwb_warnings

    root = logging.getLogger()
    root.handlers = [QueueHandler(log_queue)]
    for name, level in levels.items():
        logging.getLogger(name).setLevel(level)
    ignore_benign_pynwb_warnings()


class _ValidationPool:
    """
    Processes in which files are validated in parallel (h5py serializes all
    reading of HDF5 files in a process), whose log records are handled by the
    handlers of this process
    """

    def __init__(self, jobs: int) -> None:
        # Not "fork": this process may have started threads (e.g., fsspec's
        # for streaming content)
        context = get_context("spawn")
        self.log_queue = context.Queue()
        self.listener = QueueListener(
            self.log_queue, *logging.getLogger().handlers, respect_handler_level=True
        )
        self.listener.start()
        levels = {name: logging.getLogger(name or None).level for name in ("", "dandi")}
        self.executor = ProcessPoolExecutor(
            max_workers=jobs,
            mp_context=context,
            initializer=_init_worker,
            initargs=(self.log_queue, levels),
        )

    def submit(
        self,
        df: LocalFileAsset,
        schema_version: str | None,
        devel_debug: bool,
        missing_file_content: MissingFileContent | None,
    ) -> Future[list[ValidationResult]]:
        # The source of streamed content cannot be sent to another process;
        # it is set up again there
        df = copy(df)
        df.content_source = None
        return self.executor.submit(
            _validate_file_in_worker,
            df,
            schema_version,
            devel_debug,
            missing_file_content,
        )

    def shutdown(self) -> None:
        self.executor.shutdown(cancel_futures=True)
        self.listener.stop()
        self.log_queue.close()


def _check_streaming_requirements() -> None:
    """Raise an informative error if what is needed for streaming file content
    is not installed"""
    if find_spec("datalad_fuse") is None:
        raise RuntimeError(
            "Streaming file content requires datalad-fuse; install it with "
            "`pip install 'dandi[datalad]'`"
        )
    if shutil.which("git-annex") is None:
        raise RuntimeError("Streaming file content requires git-annex")


def _prepare_streaming(df: DandiFile) -> AnnexedReadableFile | None:
    """
    Set up streaming of the content of the annexed file represented by ``df``,
    and return the `Readable` that will be used for it, or `None` if the
    content cannot be streamed (see `get_annexed_readable()`)
    """
    if not isinstance(df, LocalFileAsset):
        return None
    readable = get_annexed_readable(df.filepath)
    if readable is not None:
        df.content_source = readable
    return readable


def _handle_missing_content(
    df: DandiFile,
    policy: MissingFileContent,
    readable: AnnexedReadableFile | None = None,
) -> ValidationResult:
    """Produce a single :class:`ValidationResult` for a file with missing content.

    For the ``stream`` policy, ``readable`` is the `Readable` streaming the
    file's content, or `None` if the content cannot be streamed.
    """
    filepath = df.filepath

    if policy == MissingFileContent.stream:
        if readable is not None:
            return ValidationResult(
                id="DANDI.FILE_CONTENT_STREAMED",
                origin=ORIGIN_VALIDATION_DANDI_LAYOUT,
                severity=Severity.INFO,
                scope=Scope.FILE,
                path=filepath,
                dandiset_path=df.dandiset_path,
                message=(
                    f"File content is not present locally (git-annex key "
                    f"{readable.key}); content-dependent validation streams "
                    f"it from {readable.url}"
                ),
            )
        return ValidationResult(
            id="DANDI.FILE_CONTENT_MISSING",
            origin=ORIGIN_VALIDATION_DANDI_LAYOUT,
            severity=Severity.ERROR,
            scope=Scope.FILE,
            path=filepath,
            dandiset_path=df.dandiset_path,
            message=(
                f"File content is not available (broken symlink: "
                f"{filepath} -> {os.readlink(filepath)}) and cannot be "
                f"streamed: not an annexed file in a git-annex repository "
                f"with a URL known to git-annex."
            ),
        )
    elif policy == MissingFileContent.error:
        return ValidationResult(
            id="DANDI.FILE_CONTENT_MISSING",
            origin=ORIGIN_VALIDATION_DANDI_LAYOUT,
            severity=Severity.ERROR,
            scope=Scope.FILE,
            path=filepath,
            dandiset_path=df.dandiset_path,
            message=(
                f"File content is not available (broken symlink: "
                f"{filepath} -> {os.readlink(filepath)}). "
                f"Use --missing-file-content=skip, "
                f"--missing-file-content=only-non-data, or "
                f"--missing-file-content=stream to handle gracefully."
            ),
        )
    elif policy == MissingFileContent.skip:
        return ValidationResult(
            id="DANDI.FILE_CONTENT_MISSING_SKIPPED",
            origin=ORIGIN_VALIDATION_DANDI_LAYOUT,
            severity=Severity.WARNING,
            scope=Scope.FILE,
            path=filepath,
            dandiset_path=df.dandiset_path,
            message=(
                f"Validation skipped: file content is not available "
                f"(broken symlink: {filepath} -> {os.readlink(filepath)})."
            ),
        )
    else:
        # only-non-data: emit a warning per file so the user knows that
        # content-dependent checks were skipped for this file.
        return ValidationResult(
            id="DANDI.FILE_CONTENT_MISSING_PARTIAL",
            origin=ORIGIN_VALIDATION_DANDI_LAYOUT,
            severity=Severity.WARNING,
            scope=Scope.FILE,
            path=filepath,
            dandiset_path=df.dandiset_path,
            message=(
                f"File content is not available (broken symlink: "
                f"{filepath} -> {os.readlink(filepath)}); "
                f"content-dependent checks skipped, "
                f"path layout still validated."
            ),
        )
