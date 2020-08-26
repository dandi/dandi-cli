"""
Commands definition for DANDI command line interface
"""

import logging

import click
from click_didyoumean import DYMGroup

from .base import get_logger, lgr, map_to_click_exceptions, set_logger_level

from .. import __version__


# Delay imports leading to import of heavy modules such as pynwb and h5py
# Import at the point of use
# from ..pynwb_utils import ...


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
from .cmd_ls import ls  # noqa: E402
from .cmd_organize import organize  # noqa: E402
from .cmd_upload import upload  # noqa: E402
from .cmd_download import download  # noqa: E402
from .cmd_validate import validate  # noqa: E402
from .cmd_register import register  # noqa: E402

__all_commands__ = (ls, organize, upload, download, validate, register)

for cmd in __all_commands__:
    main.add_command(cmd)
