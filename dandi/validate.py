from pathlib import Path
from typing import Iterator, List, Optional, Tuple, Union

import appdirs

from .files import find_dandi_files

# TODO: provide our own "errors" records, which would also include warnings etc


def validate_bids(
    *paths: Union[str, Path],
    schema_version: Optional[str] = None,
    report: bool = False,
    report_path: str = "",
) -> dict:
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
    return dict(validation_result)


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
