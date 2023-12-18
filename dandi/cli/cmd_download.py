from __future__ import annotations

from collections.abc import Sequence
import os

import click

from .base import ChoiceList, IntColonInt, instance_option, map_to_click_exceptions
from ..dandiarchive import _dandi_url_parser, parse_dandi_url
from ..dandiset import Dandiset
from ..download import DownloadExisting, DownloadFormat, PathType
from ..utils import get_instance, joinurl


# The use of f-strings apparently makes this not a proper docstring, and so
# click doesn't use it unless we explicitly assign it to `help`:
@click.command(
    help=f"""\
Download files or entire folders from DANDI.

\b
{_dandi_url_parser.known_patterns}
    """
)
@click.option(
    "-o",
    "--output-dir",
    help="Directory where to download to (directory must exist). "
    "Files will be downloaded with paths relative to that directory. ",
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
    default=os.curdir,
)
@click.option(
    "-e",
    "--existing",
    type=click.Choice(list(DownloadExisting)),
    # TODO: verify-reupload (to become default)
    help="What to do if a file found existing locally. 'refresh': verify "
    "that according to the size and mtime, it is the same file, if not - "
    "download and overwrite.",
    default="error",
    show_default=True,
)
@click.option(
    "-f",
    "--format",
    help="Choose the format/frontend for output. TODO: support all of the ls",
    type=click.Choice(list(DownloadFormat)),
    default="pyout",
)
@click.option(
    "--path-type",
    type=click.Choice(list(PathType)),
    default="exact",
    help="Whether to interpret asset paths in URLs as exact matches or glob patterns",
    show_default=True,
)
@click.option(
    "-J",
    "--jobs",
    type=IntColonInt(),
    help="Number of parallel download jobs and, optionally number of subjobs per Zarr asset",
    default="6",  # TODO: come up with smart auto-scaling etc
    show_default=True,
)
@click.option(
    "--download",
    "download_types",
    type=ChoiceList(["dandiset.yaml", "assets"]),
    help="Comma-separated list of elements to download",
    default="all",
    show_default=True,
)
@click.option(
    "--sync", is_flag=True, help="Delete local assets that do not exist on the server"
)
@instance_option(
    default=None,
    help=(
        "DANDI Archive instance to download from. If any URLs are provided,"
        " they must point to the given instance. If no URL is provided, and"
        " there is a local dandiset.yaml file, the Dandiset with the identifier"
        " given in the file will be downloaded from the given instance."
    ),
)
# Might be a cool feature, not unlike verifying a checksum, we verify that
# downloaded file passes the validator, and if not -- alert
# @click.option(
#     "--validation",
#     "validation",
#     type=click.Choice(["require", "skip", "ignore"]),
#     default="require",
# )
# @devel_option(
#     "--develop-debug",
#     help="For development: do not use pyout callbacks, do not swallow exception",
#     default=False,
#     is_flag=True,
# )
@click.argument("url", nargs=-1)
@map_to_click_exceptions
def download(
    url: Sequence[str],
    output_dir: str,
    existing: DownloadExisting,
    jobs: tuple[int, int],
    format: DownloadFormat,
    download_types: set[str],
    sync: bool,
    dandi_instance: str,
    path_type: PathType,
) -> None:
    # We need to import the download module rather than the download function
    # so that the tests can properly patch the function with a mock.
    from .. import download

    if dandi_instance is not None:
        instance = get_instance(dandi_instance)
        if url:
            for u in url:
                parsed_url = parse_dandi_url(u)
                if parsed_url.instance != instance:
                    raise click.UsageError(
                        f"{u} does not point to {dandi_instance!r} instance"
                    )
        else:
            try:
                dandiset_id = Dandiset(os.curdir).identifier
            except ValueError:
                # No Dandiset here; leave `url` alone
                pass
            else:
                if instance.gui is not None:
                    url = [joinurl(instance.gui, f"/#/dandiset/{dandiset_id}/draft")]
                else:
                    url = [joinurl(instance.api, f"/dandisets/{dandiset_id}/")]

    return download.download(
        url,
        output_dir,
        existing=existing,
        format=format,
        jobs=jobs[0],
        jobs_per_zarr=jobs[1],
        get_metadata="dandiset.yaml" in download_types,
        get_assets="assets" in download_types,
        sync=sync,
        path_type=path_type,
        # develop_debug=develop_debug
    )
