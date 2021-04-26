import os.path as op

from .consts import dandiset_metadata_file
from . import get_logger
from .metadata import get_metadata
from .pynwb_utils import validate as pynwb_validate
from .pynwb_utils import validate_cache
from .utils import find_dandi_files, yaml_load

lgr = get_logger()

# TODO -- should come from schema.  This is just a simplistic example for now
_required_dandiset_metadata_fields = ["identifier", "name", "description"]
_required_nwb_metadata_fields = ["subject_id"]


# TODO: provide our own "errors" records, which would also include warnings etc
def validate(paths, schema_version=None, devel_debug=False):
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
        errors = validate_file(
            path, schema_version=schema_version, devel_debug=devel_debug
        )
        yield path, errors


def validate_file(filepath, schema_version=None, devel_debug=False):
    if op.basename(filepath) == dandiset_metadata_file:
        return validate_dandiset_yaml(
            filepath, schema_version=None, devel_debug=devel_debug
        )
    else:
        return pynwb_validate(filepath, devel_debug=devel_debug) + validate_dandi_nwb(
            filepath, schema_version=schema_version, devel_debug=devel_debug
        )


@validate_cache.memoize_path
def validate_dandiset_yaml(filepath, schema_version=None, devel_debug=False):
    """Validate dandiset.yaml"""
    with open(filepath) as f:
        meta = yaml_load(f, typ="safe")
    if schema_version is None:
        schema_version = meta.get("schemaVersion")
    if schema_version is None:
        return _check_required_fields(meta, _required_dandiset_metadata_fields)
    else:
        from pydantic import ValidationError

        from .metadata import migrate2newschema
        from .models import DandisetMeta, get_schema_version

        current_version = get_schema_version()
        if schema_version != current_version:
            raise ValueError(
                f"Unsupported schema version: {schema_version}; expected {current_version}"
            )
        try:
            new_meta = migrate2newschema(meta)
            DandisetMeta(**new_meta.dict())
        except ValidationError as e:
            if devel_debug:
                raise
            lgr.warning(
                "Validation error for %s: %s", filepath, e, extra={"validating": True}
            )
            return [str(e)]
        except Exception as e:
            if devel_debug:
                raise
            lgr.warning(
                "Unexpected validation error for %s: %s",
                filepath,
                e,
                extra={"validating": True},
            )
            return [f"Failed to convert metadata: {e}"]
        return []


@validate_cache.memoize_path
def validate_dandi_nwb(filepath, schema_version=None, devel_debug=False):
    """Provide validation of .nwb file regarding requirements we impose"""
    if schema_version is not None:
        from pydantic import ValidationError

        from .metadata import nwb2asset
        from .models import BareAssetMeta, get_schema_version

        current_version = get_schema_version()
        if schema_version != current_version:
            raise ValueError(
                f"Unsupported schema version: {schema_version}; expected {current_version}"
            )
        try:
            asset = nwb2asset(filepath, digest="dummy_value", digest_type="sha1")
            BareAssetMeta(**asset.dict())
        except ValidationError as e:
            if devel_debug:
                raise
            lgr.warning(
                "Validation error for %s: %s", filepath, e, extra={"validating": True}
            )
            return [str(e)]
        except Exception as e:
            if devel_debug:
                raise
            lgr.warning(
                "Unexpected validation error for %s: %s",
                filepath,
                e,
                extra={"validating": True},
            )
            return [f"Failed to read metadata: {e}"]
        return []
    else:
        # make sure that we have some basic metadata fields we require
        try:
            meta = get_metadata(filepath)
        except Exception as e:
            if devel_debug:
                raise
            lgr.warning(
                "Failed to read metadata in %s: %s",
                filepath,
                e,
                extra={"validating": True},
            )
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
