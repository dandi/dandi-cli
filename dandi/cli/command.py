"""
Commands definition for DANDI command line interface
"""

from functools import wraps
import logging
import os
from os import path as op

import click
from click_didyoumean import DYMGroup

from .. import get_logger, set_logger_level

from .. import __version__
from ..consts import dandiset_metadata_file, known_instances


# Delay imports leading to import of heavy modules such as pynwb and h5py
# Import at the point of use
# from ..pynwb_utils import ...

lgr = get_logger()


class LogLevel(click.ParamType):
    name = "log-level"
    levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def convert(self, value, param, ctx):
        if value is None:
            return value
        try:
            return int(value)
        except ValueError:
            vupper = value.upper()
            if vupper in self.levels:
                return getattr(logging, vupper)
            else:
                self.fail(f"{value!r}: invalid log level", param, ctx)

    def get_metavar(self, param):
        return "[" + "|".join(self.levels) + "]"


# Aux common functionality


def get_files(paths, recursive=True, recursion_limit=None):
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
# Common options to reuse
#
# Functions to provide customizations where needed
def _updated_option(*args, **kwargs):
    args, d = args[:-1], args[-1]
    kwargs.update(d)
    return click.option(*args, **kwargs)


def dandiset_id_option(**kwargs):
    return _updated_option(
        "--dandiset-id",
        kwargs,
        help=f"ID of the dandiset on DANDI archive.  Necessary to populate "
        f"{dandiset_metadata_file}. Please use 'register' command to first "
        f"register a new dandiset.",
        # TODO: could add a check for correct regexp
    )


def dandiset_path_option(**kwargs):
    return _updated_option(
        "-d",
        "--dandiset-path",
        kwargs,
        help="Top directory (local) of the dandiset.",
        type=click.Path(exists=True, dir_okay=True, file_okay=False),
    )


def instance_option():
    return devel_option(
        "-i",
        "--dandi-instance",
        help="For development: DANDI instance to use",
        type=click.Choice(sorted(known_instances)),
        default="dandi",
        show_default=True,
    )


def devel_debug_option():
    return devel_option(
        "--devel-debug",
        help="For development: do not use pyout callbacks, do not swallow"
        " exception, do not parallize",
        default=False,
        is_flag=True,
    )


def map_to_click_exceptions(f):
    """Catch all exceptions and re-raise as click exceptions.

    Will be active only if DANDI_DEVEL is not set and --pdb is not given
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        # Prints global Usage: useless in majority of cases.
        # It seems we better use it with some ctx, so it would hint in some
        # cases to the help of a specific command
        # except ValueError as e:
        #     raise click.UsageError(str(e))
        except Exception as e:
            e_str = str(e)
            lgr.debug("Caught exception %s", e_str)
            if not map_to_click_exceptions._do_map:
                raise
            raise click.ClickException(e_str)

    return wrapper


map_to_click_exceptions._do_map = not bool(os.environ.get("DANDI_DEVEL", None))

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
    help="Log level (case insensitive).  May be specified as an integer.",
    type=LogLevel(),
    default="INFO",
    show_default=True,
)
@click.option("--pdb", help="Fall into pdb if errors out", is_flag=True)
def main(log_level, pdb=False):
    """A client to support interactions with DANDI archive (http://dandiarchive.org).

    To see help for a specific command, run

        dandi COMMAND --help

    e.g. dandi upload --help
    """
    set_logger_level(get_logger(), log_level)
    if pdb:
        map_to_click_exceptions._do_map = False
        from ..utils import setup_exceptionhook

        setup_exceptionhook()
    try:
        import etelemetry

        etelemetry.check_available_version("dandi/dandi-cli", __version__, lgr=lgr)
    except Exception as exc:
        lgr.warning(
            "Failed to check for a more recent version available with etelemetry: %s",
            exc,
        )


#
# Commands in the main group
#
from .cmd_ls import ls  # noqa: E402, F401
from .cmd_organize import organize  # noqa: E402, F401
from .cmd_upload import upload  # noqa: E402, F401
from .cmd_download import download  # noqa: E402, F401
from .cmd_validate import validate  # noqa: E402, F401
from .cmd_register import register  # noqa: E402, F401
