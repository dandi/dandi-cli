import click

from .base import (
    IntColonInt,
    devel_debug_option,
    devel_option,
    instance_option,
    map_to_click_exceptions,
)


@click.command()
@click.option(
    "-e",
    "--existing",
    type=click.Choice(["error", "skip", "force", "overwrite", "refresh"]),
    help="What to do if a file found existing on the server. 'skip' would skip"
    "the file, 'force' - force reupload, 'overwrite' - force upload if "
    "either size or modification time differs; 'refresh' - upload only if "
    "local modification time is ahead of the remote.",
    default="refresh",
    show_default=True,
)
@click.option(
    "-J",
    "--jobs",
    type=IntColonInt(),
    help=(
        "Number of assets to upload in parallel and, optionally, number of"
        " upload threads per asset  [default: 5:5]"
    ),
)
@click.option(
    "--sync", is_flag=True, help="Delete assets on the server that do not exist locally"
)
@click.option(
    "--validation",
    help="Data must pass validation before the upload.  Use of this option is highly discouraged.",
    type=click.Choice(["require", "skip", "ignore"]),
    default="require",
    show_default=True,
)
@click.argument("paths", nargs=-1)  # , type=click.Path(exists=True, dir_okay=False))
# &
# Development options:  Set DANDI_DEVEL for them to become available
#
# TODO: should always go to dandi for now
@instance_option()
@devel_option(
    "--allow-any-path",
    help="For development: allow DANDI 'unsupported' file types/paths",
    default=False,
    is_flag=True,
)
@devel_option(
    "--upload-dandiset-metadata",
    help="For development: do upload dandiset metadata",
    default=False,
    is_flag=True,
)
@devel_debug_option()
@map_to_click_exceptions
def upload(
    paths,
    jobs,
    sync,
    dandi_instance,
    existing="refresh",
    validation="require",
    # Development options should come as kwargs
    allow_any_path=False,
    upload_dandiset_metadata=False,
    devel_debug=False,
):
    """
    Upload Dandiset files to DANDI Archive.

    The target Dandiset to upload to must already be registered in the archive,
    and a `dandiset.yaml` file must exist in the common ancestor of the given
    paths (or the current directory, if no paths are specified) or a parent
    directory thereof.

    Local Dandiset should pass validation.  For that, the assets should first
    be organized using the `dandi organize` command.

    By default all .nwb, .zarr, and .ngff assets in the Dandiset (ignoring
    directories starting with a period) will be considered for the upload.  You
    can point to specific files you would like to validate and have uploaded.
    """
    from ..upload import upload

    if jobs is None:
        jobs = None
        jobs_per_file = None
    else:
        jobs, jobs_per_file = jobs

    upload(
        paths,
        existing=existing,
        validation=validation,
        dandi_instance=dandi_instance,
        allow_any_path=allow_any_path,
        upload_dandiset_metadata=upload_dandiset_metadata,
        devel_debug=devel_debug,
        jobs=jobs,
        jobs_per_file=jobs_per_file,
        sync=sync,
    )
