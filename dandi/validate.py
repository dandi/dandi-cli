import os
from typing import Iterator, List, Optional, Tuple

from .files import find_dandi_files


# TODO: provide our own "errors" records, which would also include warnings etc

def validate_bids(
    *paths: str,
    schema_version: Optional[str]=None,
    devel_debug: bool = False,
) -> Iterator[Tuple[str, List[str]]]:
    """Validate BIDS paths.

    Parameters
    ----------
    paths : *str
        Paths to validate.
    schema_version : str, optional
        BIDS schema version to use, this setting will override the version specified in the dataset.
    debug : bool, optional
        Whether to trigger debugging in the BIDS validator.
    """
    from .bids_validator_xs import load_all, validate_all, write_report

    module_path = os.path.abspath(os.path.dirname(__file__))
    bids_schema_path = os.path.join(module_path,'support/bids/schemadata/',schema_version)
    regex_schema = load_all(bids_schema_path)
    validation_result = validate_all(*paths, regex_schema,
        debug=devel_debug,
        )
    write_report(validation_result)
    print("klajfkjsf")

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
