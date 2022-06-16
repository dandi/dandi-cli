from __future__ import annotations

from typing import Optional

import click

from .base import devel_debug_option, instance_option, map_to_click_exceptions


@click.command()
@click.option("-d", "--dandiset", metavar="URL")
@click.option("--dry-run", is_flag=True)
@click.option(
    "-e",
    "--existing",
    type=click.Choice(["error", "skip", "overwrite"]),
    default="error",
)
@click.option("-J", "--jobs", type=int)
@click.option("--regex", is_flag=True)
@click.option(
    "-w",
    "--work-on",
    type=click.Choice(["auto", "both", "local", "remote"]),
    default="auto",
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
