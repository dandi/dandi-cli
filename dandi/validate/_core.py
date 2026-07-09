"""Validation of DANDI datasets against schemas and standards.

This module provides validation functionality for dandisets, including:
- DANDI schema validation
- BIDS standard validation
- File layout and organization validation
- Metadata completeness checking
"""

from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path
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
from ..consts import dandiset_metadata_file
from ..files import find_dandi_files
from ..utils import find_parent_directory_containing

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
# When ``only-non-data`` is active these are suppressed for broken-symlink files.
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
      content-dependent validators but still validates path layout.

    Yields
    ------
    path, errors
      errors for a path
    """
    # Archive of unique `ValidationResult` objects obtained through
    # `DandiFile.get_validation_errors()`
    # Note: This is needed to hold on to the unique `ValidationResult` objects
    #   so that they don't get garbage collected, ensuring that the same ID in
    #   `df_result_ids` is always associated with the same object.
    df_results: list[ValidationResult] = []

    # The ids of the objects in `df_results` obtain through the `id()` built-in function
    df_result_ids: set[int] = set()

    for p in paths:
        p = os.path.abspath(p)
        dandiset_path = find_parent_directory_containing(dandiset_metadata_file, p)
        if dandiset_path is None:
            yield ValidationResult(
                id="DANDI.NO_DANDISET_FOUND",
                origin=ORIGIN_VALIDATION_DANDI_LAYOUT,
                severity=Severity.ERROR,
                scope=Scope.DANDISET,
                path=Path(p),
                message="Path is not inside a Dandiset",
            )
        for df in find_dandi_files(
            p, dandiset_path=dandiset_path, allow_all=allow_any_path
        ):
            # Handle broken symlinks (missing file content)
            if _is_broken_symlink(df.filepath):
                r = _handle_missing_content(df, missing_file_content)
                if r is not None:
                    r_id = id(r)
                    if r_id not in df_result_ids:
                        df_results.append(r)
                        df_result_ids.add(r_id)
                        yield r
                if missing_file_content in (
                    MissingFileContent.skip,
                    MissingFileContent.error,
                ):
                    continue
                # only-non-data: fall through but pass the flag to validators

            is_broken = _is_broken_symlink(df.filepath)
            for r in df.get_validation_errors(
                schema_version=schema_version,
                devel_debug=devel_debug,
                missing_file_content=(missing_file_content if is_broken else None),
            ):
                # For broken-symlink files under only-non-data, suppress
                # BIDS errors that require reading file content (e.g.
                # NIFTI_HEADER_UNREADABLE).  The validator ran in full so
                # real files still get those checks.
                if (
                    is_broken
                    and missing_file_content == MissingFileContent.only_non_data
                    and r.id in _BIDS_CONTENT_DEPENDENT_CODES
                ):
                    continue
                r_id = id(r)
                if r_id not in df_result_ids:
                    df_results.append(r)
                    df_result_ids.add(r_id)
                    yield r


def _handle_missing_content(
    df: Any,
    policy: MissingFileContent,
) -> ValidationResult | None:
    """Produce a single :class:`ValidationResult` for a file with missing content.

    Returns ``None`` when *policy* is ``only-non-data`` (a warning is not
    needed because validation still proceeds on the non-data aspects).
    """
    from ..files import DandiFile

    assert isinstance(df, DandiFile)
    filepath = df.filepath

    if policy == MissingFileContent.error:
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
                f"Use --missing-file-content=skip or "
                f"--missing-file-content=only-non-data to handle gracefully."
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
