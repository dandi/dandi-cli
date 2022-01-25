from .files import find_dandi_files


# TODO: provide our own "errors" records, which would also include warnings etc
def validate(*paths, schema_version=None, devel_debug=False, allow_any_path=False):
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
            df.filepath,
            df.get_validation_errors(
                schema_version=schema_version, devel_debug=devel_debug
            ),
        )
