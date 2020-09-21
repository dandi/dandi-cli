import click

from .base import dandiset_path_option, instance_option, map_to_click_exceptions


@click.command()
@dandiset_path_option(
    help="Top directory (local) for the dandiset, where dandi will download "
    "(or update existing) dandiset.yaml upon successful registration."
)
@click.option(
    "-n", "--name", help="Short name or title for the dandiset.", prompt="Name"
)
@click.option(
    "-D",
    "--description",
    help="Description of the dandiset - high level summary of the experiment "
    "and type(s) of data.",
    prompt="Description",
)
# &
# Development options:  Set DANDI_DEVEL for them to become available
#
# TODO: should always go to dandi for now
@instance_option()
@map_to_click_exceptions
def register(name, description, dandiset_path=None, dandi_instance="dandi"):
    """Register a new dandiset in the DANDI archive.

    This command provides only a minimal set of metadata. It is
    recommended to use Web UI to fill out other metadata fields for the
    dandiset
    """
    from ..register import register

    dandiset = register(name, description, dandiset_path, dandi_instance)
    print("identifier:", dandiset.identifier)
