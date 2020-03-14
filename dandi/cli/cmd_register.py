import click
from datetime import datetime
import os
import os.path as op
import re
import sys
import time

from ..consts import dandiset_metadata_file, known_instances, routes

from .command import (
    dandiset_path_option,
    instance_option,
    main,
    map_to_click_exceptions,
)
from ..utils import ensure_datetime, ensure_strtime, find_parent_directory_containing

from .. import get_logger

lgr = get_logger()


@main.command()
@dandiset_path_option(
    help="Top directory (local) for the dandiset, where dandi will download "
    "(or update existing) dandiset.yaml upon successful registration.  If not "
    "specified, content for the file will be printed to the screen."
)
@click.option(
    "-n",
    "--name",
    help="Short name or title for the dandiset.",
    prompt="Name",
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
    """Register a new dandiset in the DANDI archive"""
    from .. import girder
    from ..dandiset import Dandiset

    if not dandiset_path and op.exists(dandiset_metadata_file):
        dandiset = Dandiset.find(os.getcwd())
        if dandiset:
            if "identifier" in dandiset.metadata:
                lgr.warning(
                    "Running 'register' while in a dandiset at %s.  We will "
                    "not generate %s",
                    dandiset,
                    dandiset_metadata_file,
                )
            else:
                dandiset_path = dandiset.path
                lgr.info(
                    "We will populate %s of the %s dandiset",
                    dandiset_metadata_file,
                    dandiset.path,
                )

    dandi_instance = known_instances[dandi_instance]
    client = girder.get_client(dandi_instance.girder)
    dandiset = client.register_dandiset(name, description)

    url = routes.dandiset_draft.format(**locals())

    lgr.info(f"Registered dandiset at {url}. Please visit and adjust metadata.")
    if dandiset_path:
        ds = Dandiset(dandiset_path, allow_empty=True)
        ds.update_metadata(dandiset)
    else:
        lgr.info(
            "No dandiset path was provided and no dandiset detected in the path."
            " Here is a record for %s",
            dandiset_metadata_file,
        )
        print(Dandiset.get_dandiset_record(dandiset))
