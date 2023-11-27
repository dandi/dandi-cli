import click

from .base import devel_debug_option, instance_option, map_to_click_exceptions


@click.command()
@click.option("--skip-missing", is_flag=True)
@click.option(
    "--force",
    is_flag=True,
    help="Force deletion without requesting interactive confirmation",
)
@click.argument("paths", nargs=-1, type=click.Path(exists=False, dir_okay=True))
@instance_option()
@devel_debug_option()
@map_to_click_exceptions
def delete(paths, skip_missing, dandi_instance, force, devel_debug=False):
    """Delete dandisets and assets from the server.

    PATH could be a local path or a URL to an asset, directory, or an entire
    dandiset.
    """
    from ..delete import delete

    delete(
        paths,
        dandi_instance=dandi_instance,
        devel_debug=devel_debug,
        force=force,
        skip_missing=skip_missing,
    )
