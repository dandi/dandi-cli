from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterator, List, Optional, Tuple, Union

import appdirs

from .files import find_dandi_files


BIDS_TO_DANDI = {
    "subject": "subject_id",
    "session": "session_id",
}


@dataclass
class ValidationResult:
    id: str
    origin: ValidationOrigin
    scope: Scope
    asset_paths: Optional[list[str]] = None
    dandiset_path: Optional[Path] = None
    dataset_path: Optional[Path] = None
    message: Optional[str] = ""
    metadata: Optional[dict] = None
    path: Optional[Path] = None
    path_regex: Optional[str] = ""
    severity: Optional[Severity] = None


@dataclass
class ValidationOrigin:
    name: str
    version: str


class Severity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    HINT = "HINT"


class Scope(Enum):
    FILE = "file"
    DANDISET = "dandiset"
    DATASET = "dataset"


def validate_bids(
    *paths: Union[str, Path],
    schema_version: Optional[str] = None,
    report: bool = False,
    report_path: str = "",
) -> list[ValidationResult]:
    """Validate BIDS paths.

    Parameters
    ----------
    paths : *str
        Paths to validate.
    schema_version : str, optional
        BIDS schema version to use, this setting will override the version specified in the dataset.
    devel_debug : bool, optional
        Whether to trigger debugging in the BIDS validator.
    report : bool, optional
        Whether to write a BIDS validator report inside the DANDI log directory.
    report_path : str, optional
        Path underneath which to write a validation report, this option implies `report`.

    Returns
    -------
    dict
        Dictionary reporting required patterns not found and existing filenames not matching any
        patterns.

    Notes
    -----
    * Eventually this should be migrated to BIDS schema specified errors, see discussion here:
        https://github.com/bids-standard/bids-specification/issues/1262
    """

    import bidsschematools
    from bidsschematools.validator import validate_bids as validate_bids_

    if report and not report_path:
        log_dir = appdirs.user_log_dir("dandi-cli", "dandi")
        report_path = "{log_dir}/bids-validator-report_{{datetime}}-{{pid}}.log"
        report_path = report_path.format(
            log_dir=log_dir,
        )
    validation_result = validate_bids_(
        paths,
        schema_version=schema_version,
        report_path=report_path,
    )
    our_validation_result = []
    origin = ValidationOrigin(
        name="bidsschematools",
        version=bidsschematools.__version__,
    )

    for path in validation_result["path_tracking"]:
        # Hard-coding exclusion here pending feature + release in:
        # https://github.com/bids-standard/bids-specification/issues/1272
        if path.endswith((".ERRORS", ".ERRORS.json")):
            continue
        dataset_path = _get_set_path(path, "dataset_description.json")
        dandiset_path = _get_set_path(path, "dandiset.yaml")
        our_validation_result.append(
            ValidationResult(
                origin=origin,
                severity=Severity.ERROR,
                id="BIDS.NON_BIDS_PATH_PLACEHOLDER",
                scope=Scope.FILE,
                path=path,
                message="File does not match any pattern known to BIDS.",
                dataset_path=dataset_path,
                dandiset_path=dandiset_path,
            )
        )

    for pattern in validation_result["schema_tracking"]:
        # Future proofing for standard-compliant name.
        if ("mandatory" in pattern and pattern["mandatory"]) or (
            "required" in pattern and pattern["required"]
        ):
            # We don't have a path for this so we'll need some external logic to make sure
            # that the dataset path is populated.
            # dataset_path = _get_dataset_path(path, paths)
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
    for meta in validation_result["match_listing"]:
        file_path = meta.pop("path")
        meta = {
            BIDS_TO_DANDI[k]: v
            for k, v in meta.items()
            if k in BIDS_TO_DANDI
        }
        our_validation_result.append(
            ValidationResult(
                origin=origin,
                id="BIDS.MATCH",
                scope=Scope.FILE,
                path=file_path,
                metadata=meta,
            )
        )

    return our_validation_result


def _get_set_path(in_path, marker):
    """Get the path to the root of a file set (e.g. BIDS dataset or DANDIset).

    Parameters
    ----------
    in_path : str, optional
        File for which to determine set path.
    marker : str, optional
        Filename marker which identifies the set root.
    """
    import os

    candidate = os.path.join(in_path, marker)
    # Windows support... otherwise we could do `if in_path == "/"`.
    if in_path == "/" or not any(i in in_path for i in ["/", "\\"]):
        return None
    if os.path.isfile(candidate):
        return os.path.dirname(candidate)
    else:
        level_up = os.path.dirname(in_path.rstrip("/\\"))
        return _get_set_path(level_up, marker)


def validate(
    *paths: str,
    schema_version: Optional[str] = None,
    devel_debug: bool = False,
    allow_any_path: bool = False,
) -> Iterator[Tuple[str, List[str]]]:
    """Validate content

    Parameters
    ----------
    paths: *str
      Could be individual (.nwb) files or a single dandiset path.

    Yields
    ------
    path, errors
      errors for a path
    """
    for df in find_dandi_files(*paths, dandiset_path=None, allow_all=allow_any_path):
        yield (
            str(df.filepath),
            df.get_validation_errors(
                schema_version=schema_version, devel_debug=devel_debug
            ),
        )
