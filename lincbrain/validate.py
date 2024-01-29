from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path

from . import __version__
from .consts import dandiset_metadata_file
from .files import find_dandi_files
from .utils import find_parent_directory_containing
from .validate_types import Scope, Severity, ValidationOrigin, ValidationResult

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
    origin = ValidationOrigin(
        name="bidsschematools",
        version=bidsschematools.__version__,
        bids_version=validation_result["bids_version"],
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
                path=Path(file_path),
                metadata=meta,
                dataset_path=dataset_path,
                dandiset_path=dandiset_path,
            )
        )

    return our_validation_result


def validate(
    *paths: str | Path,
    schema_version: str | None = None,
    devel_debug: bool = False,
    allow_any_path: bool = False,
) -> Iterator[ValidationResult]:
    """Validate content

    Parameters
    ----------
    paths: list(str)
      Could be individual (.nwb) files or a single dandiset path.

    Yields
    ------
    path, errors
      errors for a path
    """
    for p in paths:
        p = os.path.abspath(p)
        dandiset_path = find_parent_directory_containing(dandiset_metadata_file, p)
        if dandiset_path is None:
            yield ValidationResult(
                id="DANDI.NO_DANDISET_FOUND",
                origin=ValidationOrigin(name="dandi", version=__version__),
                severity=Severity.ERROR,
                scope=Scope.DANDISET,
                path=Path(p),
                message="Path is not inside a Dandiset",
            )
        for df in find_dandi_files(
            p, dandiset_path=dandiset_path, allow_all=allow_any_path
        ):
            yield from df.get_validation_errors(
                schema_version=schema_version, devel_debug=devel_debug
            )
