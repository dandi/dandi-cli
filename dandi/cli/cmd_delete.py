import click

from .base import devel_debug_option, instance_option, map_to_click_exceptions


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=False, dir_okay=True))
@instance_option()
@devel_debug_option()
@map_to_click_exceptions
def delete(paths, dandi_instance="dandi", devel_debug=False):
    """ Delete Dandisets and assets from the server """
    from ..delete import delete

    delete(paths, dandi_instance=dandi_instance, devel_debug=devel_debug)
