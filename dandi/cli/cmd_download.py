import datetime
import os
import sys
import time

import click
from .command import main, lgr


@main.command()
@click.option(
    "-t",
    "--local-top-path",
    help="Top directory (local) of the dataset.  Files will be uploaded with "
    "paths relative to that directory",
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
)
@click.option(
    "-e",
    "--existing",
    type=click.Choice(
        ["skip", "overwrite", "refresh"]
    ),  # TODO: verify-reupload (to become default)
    help="What to do if a file found existing locally. 'refresh': verify "
    "that according to the size and mtime, it is the same file, if not - "
    "download and overwrite.",
    default="skip",
)
# Might be a cool feature, not unlike verifying a checksum, we verify that
# downloaded file passes the validator, and if not -- alert
# @click.option(
#     "--validation",
#     "validation_",
#     type=click.Choice(["require", "skip", "ignore"]),
#     default="require",
# )
@click.option(
    "--develop-debug",
    help="For development: do not use pyout callbacks, do not swallow exception",
    default=False,
    is_flag=True,
)
@click.argument("url", nargs=-1)
def download(url, local_top_path, existing, develop_debug):
    """Download a file or entire folder from DANDI"""
    # First boring attempt at click commands being merely an interface to
    # Python function
    from ..download import download

    return download(url, local_top_path, existing, develop_debug)
