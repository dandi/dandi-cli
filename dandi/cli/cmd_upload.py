import click

from .base import (
    devel_debug_option,
    devel_option,
    instance_option,
    map_to_click_exceptions,
)


class IntColonInt(click.ParamType):
    name = "int:int"

    def convert(self, value, param, ctx):
        if isinstance(value, str):
            v1, colon, v2 = value.partition(":")
            try:
                v1 = int(v1)
                v2 = int(v2) if colon else None
            except ValueError:
                self.fail("Value must be of the form `N[:M]`", param, ctx)
            return (v1, v2)
        else:
            return value

    def get_metavar(self, param):
        return "N[:M]"


@click.command()
# @dandiset_path_option(
#     help="Top directory (local) of the dandiset.  Files will be uploaded with "
#     "paths relative to that directory. If not specified, current or a parent "
#     "directory containing dandiset.yaml file will be assumed "
# )
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
    help="Number of files to upload in parallel and, optionally, number of upload threads per file",
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
    existing="refresh",
    validation="require",
    dandiset_path=None,
    # Development options should come as kwargs
    dandi_instance="dandi",
    allow_any_path=False,
    upload_dandiset_metadata=False,
    devel_debug=False,
):
    """Upload dandiset (files) to DANDI archive.

    Target dandiset to upload to must already be registered in the archive and
    locally "dandiset.yaml" should exist in `--dandiset-path`.

    Local dandiset should pass validation.  For that it should be first organized
    using 'dandiset organize' command.

    By default all files in the dandiset (not following directories starting with a period)
    will be considered for the upload.  You can point to specific files you would like to
    validate and have uploaded.
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
        dandiset_path=dandiset_path,
        dandi_instance=dandi_instance,
        allow_any_path=allow_any_path,
        upload_dandiset_metadata=upload_dandiset_metadata,
        devel_debug=devel_debug,
        jobs=jobs,
        jobs_per_file=jobs_per_file,
        sync=sync,
    )
