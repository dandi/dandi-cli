import os
import os.path as op
from .consts import dandiset_metadata_file
import yaml

from .pynwb_utils import validate as pynwb_validate, validate_cache
from .utils import find_dandi_files


# TODO -- should come from schema.  This is just a simplistic example for now
_required_metadata_fields = ["identifier", "name", "description"]


# TODO: provide our own "errors" records, which would also include warnings etc
def validate(paths):
    """Validate content

    Parameters
    ----------
    paths: str or list of paths
      Could be individual (.nwb) files or a single dandiset path.

    Yields
    ------
    path, errors
      errors for a path
    """
    for path in find_dandi_files(paths):
        errors = validate_file(path)
        yield path, errors


@validate_cache.memoize_path
def validate_file(filepath):
    if op.basename(filepath) == dandiset_metadata_file:
        return validate_dandiset_yaml(filepath)
    else:
        return pynwb_validate(filepath)


def validate_dandiset_yaml(filepath):
    """Validate dandiset.yaml"""
    with open(filepath) as f:
        meta = yaml.safe_load(f)

    errors = []
    for f in _required_metadata_fields:
        v = meta.get(f, None)
        if v in (None, "REQUIRED", "PLACEHOLDER"):
            errors.append(f"Required field {f!r} has value {v!r}")
    return errors
