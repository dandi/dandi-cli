import datetime
import os
import sys
import time

import click
from .command import devel_option, main, map_to_click_exceptions


@main.command()
@click.option(
    "-b",
    "--base-dir",
    help="Base Directory where Dandiset will be published (directory must exist).",
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
@click.option("--no_files", help="Do not retrieve files", default=False, is_flag=True)
@click.argument("url", nargs=-1)
@map_to_click_exceptions
def publish(url, base_dir, existing, jobs=6, no_files=False, develop_debug=False):
    """Download a file or entire folder from DANDI"""
    # First boring attempt at click commands being merely an interface to
    # Python function
    from ..publish import publish

    return publish(
        url,
        base_dir,
        existing=existing,
        jobs=jobs,
        develop_debug=develop_debug,
        get_files=(not no_files),
    )
