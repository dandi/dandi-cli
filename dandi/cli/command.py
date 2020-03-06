"""
Commands definition for DANDI command line interface
"""

import os
from os import path as op

import click
from click_didyoumean import DYMGroup

from .. import get_logger, set_logger_level

from .. import __version__

# Delay imports leading to import of heavy modules such as pynwb and h5py
# Import at the point of use
# from ..pynwb_utils import ...

lgr = get_logger()


# Aux common functionality


def get_files(paths, recursive=True, recurion_limit=None):
    """Given a list of paths, return a list of paths
    """
    # For now we support only individual files
    dirs = list(filter(op.isdir, paths))
    if dirs:
        raise NotImplementedError(
            "ATM supporting only listing of individual files, no recursive "
            "operation. Was provided following directories: {}".format(", ".join(dirs))
        )
    return paths


# ???: could make them always available but hidden
#  via  hidden=True.
def devel_option(*args, **kwargs):
    """A helper to make command line options useful for development (only)

    They will become available..."""

    def wrapper(f):
        if not os.environ.get("DANDI_DEVEL", None):
            return f
        else:
            return click.option(*args, **kwargs)(f)

    return wrapper


#
# Main group
#


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo(__version__)
    ctx.exit()


def upper(ctx, param, value):
    import pdb

    pdb.set_trace()
    return value.upper()


# group to provide commands
@click.group(cls=DYMGroup)
@click.option(
    "--version", is_flag=True, callback=print_version, expose_value=False, is_eager=True
)
@click.option(
    "-l",
    "--log-level",
    help="Log level name",
    # TODO: may be bring also handling of  int  values.  For now -- no need
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    # callback=upper,  # TODO: not in effect! seems to come to play only after type validation
    show_default=True,
)
@click.option("--pdb", help="Fall into pdb if errors out", is_flag=True)
def main(log_level, pdb=False):
    """A client to support interactions with DANDI archive (http://dandiarchive.org).
    """
    set_logger_level(get_logger(), log_level)
    if pdb:
        from ..utils import setup_exceptionhook

        setup_exceptionhook()


#
# Commands in the main group
#
from .cmd_ls import ls
from .cmd_organize import organize
from .cmd_upload import upload
from .cmd_download import download
from .cmd_validate import validate
