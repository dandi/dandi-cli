from __future__ import annotations

from typing import Optional

import click

from .base import devel_debug_option, instance_option, map_to_click_exceptions


@click.command()
@click.option(
    "-d", "--dandiset", metavar="URL", help="The remote Dandiset to operate on"
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be moved but do not move anything"
)
@click.option(
    "-e",
    "--existing",
    type=click.Choice(["error", "skip", "overwrite"]),
    default="error",
    help="How to handle assets that would be moved to a destination that already exists",
    show_default=True,
)
@click.option("-J", "--jobs", type=int, help="Number of assets to move in parallel")
@click.option(
    "--regex",
    is_flag=True,
    help="Perform a regex substitution on all asset paths in the directory",
)
@click.option(
    "-w",
    "--work-on",
    type=click.Choice(["auto", "both", "local", "remote"]),
    default="auto",
    help=(
        "Whether to operate on the local Dandiset, remote Dandiset, or both;"
        " 'auto' means 'remote' when `--dandiset` is given and 'both' otherwise"
    ),
    show_default=True,
)
@click.argument(
    "paths", nargs=-1, required=True, type=click.Path(exists=False, dir_okay=True)
)
@instance_option()
@devel_debug_option()
@map_to_click_exceptions
def move(
    paths: tuple[str],
    dandiset: Optional[str],
    dry_run: bool,
    existing: str,
    jobs: Optional[int],
    regex: bool,
    work_on: str,
    dandi_instance: str,
    devel_debug: bool = False,
) -> None:
    """
    Move or rename assets in a local Dandiset and/or on the server.  The `dandi
    move` command takes one of more source paths of the assets to move,
    followed by a destination path indicating where to move them to.  Paths
    given on the command line must use forward slashes (/) as path separators,
    even on Windows.  In addition, when running the command inside a
    subdirectory of a Dandiset, all paths must be relative to the subdirectory,
    even if only operating on the remote Dandiset.  (The exception is when the
    `--dandiset` option is given in order to operate on an arbitrary remote
    Dandiset, in which case any local Dandiset is ignored.)

    If there is more than one source path, or if the destination path either
    names an existing directory or ends in a trailing forward slash (/), then
    the source assets are placed within the destination directory.  Otherwise,
    the single source path is renamed to the given destination path.

    Alternatively, if the `--regex` option is given, then there must be exactly
    two arguments on the command line: a Python regular expression and a
    replacement string, possibly containing regex backreferences.
    :program:`dandi move`: will then apply the regular expression to the path
    of every asset in the current directory recursively (using paths relative
    to the current directory, if in a subdirectory of a Dandiset); if a path
    matches, the matching portion is replaced with the replacement string,
    after expanding any backreferences.

    For more information, including examples, see
    <https://dandi.rtfd.io/en/latest/cmdline/move.html>.
    """

    from .. import move as move_mod

    if len(paths) < 2:
        raise ValueError("At least two paths are required")
    move_mod.move(
        *paths[:-1],
        dest=paths[-1],
        regex=regex,
        existing=existing,
        dandi_instance=dandi_instance,
        dandiset=dandiset,
        work_on=work_on,
        devel_debug=devel_debug,
        jobs=jobs,
        dry_run=dry_run,
    )
