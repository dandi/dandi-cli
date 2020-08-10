import os.path as op
from .consts import dandiset_metadata_file

from .pynwb_utils import validate as pynwb_validate, validate_cache
from .utils import find_dandi_files, yaml_load
from .metadata import get_metadata


# TODO -- should come from schema.  This is just a simplistic example for now
_required_dandiset_metadata_fields = ["identifier", "name", "description"]
_required_nwb_metadata_fields = ["subject_id"]


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
        return pynwb_validate(filepath) + validate_dandi_nwb(filepath)


def validate_dandiset_yaml(filepath):
    """Validate dandiset.yaml"""
    with open(filepath) as f:
        meta = yaml_load(f, typ="safe")
    return _check_required_fields(meta, _required_dandiset_metadata_fields)


def validate_dandi_nwb(filepath):
    """Provide validation of .nwb file regarding requirements we impose
    """
    # make sure that we have some basic metadata fields we require
    try:
        meta = get_metadata(filepath)
    except BaseException as e:
        return [f"Failed to read metadata: {e}"]
    return _check_required_fields(meta, _required_nwb_metadata_fields)


def _check_required_fields(d, required):
    errors = []
    for f in required:
        v = d.get(f, None)
        if not v or (isinstance(v, str) and not (v.strip())):
            errors += [f"Required field {f!r} has no value"]
        if v in ("REQUIRED", "PLACEHOLDER"):
            errors += [f"Required field {f!r} has value {v!r}"]
    return errors
