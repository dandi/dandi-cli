import os

import click
from .command import devel_option, main, map_to_click_exceptions


@main.command()
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
    type=click.Choice(
        ["error", "skip", "overwrite", "refresh"]
    ),  # TODO: verify-reupload (to become default)
    help="What to do if a file found existing locally. 'refresh': verify "
    "that according to the size and mtime, it is the same file, if not - "
    "download and overwrite.",
    default="refresh",
    show_default=True,
)
@click.option(
    "-f",
    "--format",
    help="Choose the format/frontend for output. TODO: support all of the ls",
    type=click.Choice(["pyout", "debug"]),
    default="pyout",
)
@click.option(
    "-J",
    "--jobs",
    help="Number of parallel download jobs.",
    default=6,  # TODO: come up with smart auto-scaling etc
    show_default=True,
)
# Might be a cool feature, not unlike verifying a checksum, we verify that
# downloaded file passes the validator, and if not -- alert
# @click.option(
#     "--validation",
#     "validation",
#     type=click.Choice(["require", "skip", "ignore"]),
#     default="require",
# )
@devel_option(
    "--develop-debug",
    help="For development: do not use pyout callbacks, do not swallow exception",
    default=False,
    is_flag=True,
)
@click.argument("url", nargs=-1)
@map_to_click_exceptions
def download(url, output_dir, existing, jobs=6, format="pytout"):
    """Download a file or entire folder from DANDI"""
    # First boring attempt at click commands being merely an interface to
    # Python function
    from ..download import download

    return download(
        url,
        output_dir,
        existing=existing,
        format=format,
        jobs=jobs,  # develop_debug=develop_debug
    )
