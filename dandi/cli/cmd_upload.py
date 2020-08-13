import click

from .base import (
    devel_debug_option,
    devel_option,
    instance_option,
    map_to_click_exceptions,
)
from ..consts import collection_drafts


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
# TODO: should always go into 'drafts' (consts.collection_drafts)
@devel_option(
    "-c", "--girder-collection", help="For development: Girder collection to upload to"
)
# TODO: figure out folder for the dandiset
@devel_option("--girder-top-folder", help="For development: Girder top folder")
#
@devel_option(
    "--fake-data",
    help="For development: fake file content (filename will be stored instead of actual load)",
    default=False,
    is_flag=True,
)
@devel_option(
    "--allow-any-path",
    help="For development: allow DANDI 'unsupported' file types/paths",
    default=False,
    is_flag=True,
)
@devel_debug_option()
@map_to_click_exceptions
def upload(
    paths,
    existing="refresh",
    validation="require",
    dandiset_path=None,
    # Development options should come as kwargs
    girder_collection=collection_drafts,
    girder_top_folder=None,
    dandi_instance="dandi",
    fake_data=False,  # TODO: not implemented, prune?
    allow_any_path=False,
    devel_debug=False,
):
    """Upload dandiset (files) to DANDI archive.

    Target dandiset to upload to must already be registered in the archive and
    locally "dandiset.yaml" should exist in `--dandiset-path`.  If you have not
    yet created a dandiset in the archive, use 'dandi register' command first.

    Local dandiset should pass validation.  For that it should be first organized
    using 'dandiset organize' command.

    By default all files in the dandiset (not following directories starting with a period)
    will be considered for the upload.  You can point to specific files you would like to
    validate and have uploaded.
    """
    from ..upload import upload

    upload(
        paths,
        existing=existing,
        validation=validation,
        dandiset_path=dandiset_path,
        girder_collection=girder_collection,
        girder_top_folder=girder_top_folder,
        dandi_instance=dandi_instance,
        fake_data=fake_data,
        allow_any_path=allow_any_path,
        devel_debug=devel_debug,
    )
