import os
import os.path as op

from .consts import dandiset_metadata_file
from .metadata import get_metadata
from .pynwb_utils import validate as pynwb_validate
from .pynwb_utils import validate_cache
from .utils import find_dandi_files, yaml_load

# TODO -- should come from schema.  This is just a simplistic example for now
_required_dandiset_metadata_fields = ["identifier", "name", "description"]
_required_nwb_metadata_fields = ["subject_id"]


# TODO: provide our own "errors" records, which would also include warnings etc
def validate(paths, schema_version=None):
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
        errors = validate_file(path, schema_version=schema_version)
        yield path, errors


@validate_cache.memoize_path
def validate_file(filepath, schema_version=None):
    if op.basename(filepath) == dandiset_metadata_file:
        return validate_dandiset_yaml(filepath)
    else:
        return pynwb_validate(filepath) + validate_dandi_nwb(
            filepath, schema_version=schema_version
        )


def validate_dandiset_yaml(filepath):
    """Validate dandiset.yaml"""
    with open(filepath) as f:
        meta = yaml_load(f, typ="safe")
    return _check_required_fields(meta, _required_dandiset_metadata_fields)


def validate_dandi_nwb(filepath, schema_version=None):
    """Provide validation of .nwb file regarding requirements we impose
    """
    use_new_schema = False
    if schema_version is not None:
        from .models import CommonModel

        current_version = CommonModel.__fields__["schemaVersion"].default
        if schema_version != current_version:
            raise ValueError(
                f"Unsupported schema version: {schema_version}; expected {current_version}"
            )
        use_new_schema = True
    elif os.environ.get("DANDI_SCHEMA"):
        use_new_schema = True
    if use_new_schema:
        from pydantic import ValidationError

        from .metadata import nwb2asset
        from .models import AssetMeta

        try:
            asset = nwb2asset(filepath, digest="dummy_value", digest_type="sha1")
            AssetMeta(**asset.dict())
        except ValidationError as e:
            return [str(e)]
        except Exception as e:
            return [f"Failed to read metadata: {e}"]
        return []
    else:
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
