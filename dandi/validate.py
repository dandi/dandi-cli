from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterator, List, Optional, Tuple, Union

import appdirs

from .files import find_dandi_files


@dataclass
class ValidationResult:
    origin: ValidationOrigin
    severity: Severity
    id: str
    scope: Scope
    path: Path
    message: str
    dataset_path: Optional[Path]
    asset_paths: Optional[list[str]] = None


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
        our_validation_result.append(
            ValidationResult(
                origin=origin,
                severity=Severity.ERROR,
                id="BIDS.WRONG_PATH_TODO",
                scope=Scope.FILE,
                path=path,
                message="TODO",
                # TODO - discover dandiset or actually BIDS dataset
                # might want separate the two
                # dandiset_path="TODO",  # might contain multiple datasets
                # dataset_path="TODO",  # BIDS dataset in this case
                # asset_paths: Optional[list[str]] = None
            )
        )

    for pattern in validation_result["schema_tracking"]:
        if pattern["mandatory"]:  # TODO: future proof if gets renamed to required
            our_validation_result.append(
                ValidationResult(
                    origin=origin,
                    severity=Severity.ERROR,
                    id="BIDS.MANDATORY_FILE_MISSING",  # we decided to generalize, and not have
                    scope=Scope.FILE,
                    message="TODO",
                    # TODO - discover dandiset or actually BIDS dataset
                    # might want separate the two
                    # dandiset_path="TODO",  # might contain multiple datasets
                    # dataset_path="TODO",  # BIDS dataset in this case
                    # asset_paths: Optional[list[str]] = None
                )
            )
    return our_validation_result


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
