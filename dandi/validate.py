from typing import Any, Iterator, List, Optional, Tuple

from .files import find_dandi_files

# TODO: provide our own "errors" records, which would also include warnings etc


def validate_bids(
    *paths: str,
    schema_version: Optional[str] = None,
    devel_debug: bool = False,
    report: Optional[str] = None,
) -> Any:
    """Validate BIDS paths.

    Parameters
    ----------
    paths : *str
        Paths to validate.
    schema_version : str, optional
        BIDS schema version to use, this setting will override the version specified in the dataset.
    devel_debug : bool, optional
        Whether to trigger debugging in the BIDS validator.
    report_path : bool or str, optional
        If `True` a log will be written using the standard output path of `.write_report()`.
        If string, the string will be used as the output path.
        If the variable evaluates as False, no log will be written.

    Notes
    -----
    Can be used from bash, as:
        DANDI_DEVEL=1 dandi validate-bids --schema="1.7.0+012+dandi001" --report="my.log" /my/path
    """
    from .bids_validator_xs import validate_bids as validate_bids_

    return validate_bids_(
        paths, schema_version=schema_version, debug=devel_debug, report_path=report
    )


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
