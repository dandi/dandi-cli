"""
Commands definition for DANDI command line interface
"""

from datetime import datetime
import logging
import os
import os.path
import sys
from types import SimpleNamespace

import appdirs
import click
from click_didyoumean import DYMGroup

from .base import lgr, map_to_click_exceptions
from .. import __version__, set_logger_level
from ..utils import get_module_version

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
@click.pass_context
def main(ctx, log_level, pdb=False):
    """A client to support interactions with DANDI archive (http://dandiarchive.org).

    To see help for a specific command, run

        dandi COMMAND --help

    e.g. dandi upload --help
    """
    logging.basicConfig(format="%(asctime)-15s [%(levelname)8s] %(message)s")

    # The excessive manipulation of logging levels in this function is done so
    # that (a) the log messages printed to the screen are of the level the user
    # chose with `--log-level` AND (b) all log messages from all libraries at
    # level min(DEBUG, --log-level) or higher are recorded in the logfile.

    lgr.setLevel(logging.NOTSET)
    for h in lgr.handlers:
        set_logger_level(h, log_level)

    # Ensure that certain log messages are only sent to the log file, not the
    # console:
    root = logging.getLogger()
    root.setLevel(logging.NOTSET)
    for h in root.handlers:
        h.addFilter(lambda r: not getattr(r, "file_only", False))
        set_logger_level(h, log_level)

    logdir = appdirs.user_log_dir("dandi-cli", "dandi")
    logfile = os.path.join(
        logdir, "{:%Y%m%d%H%M%SZ}-{}.log".format(datetime.utcnow(), os.getpid())
    )
    os.makedirs(logdir, exist_ok=True)
    handler = logging.FileHandler(logfile, encoding="utf-8")
    handler.setLevel(min(log_level, logging.DEBUG))
    fmter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s %(process)d:%(thread)d %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler.setFormatter(fmter)
    root.addHandler(handler)

    lgr.info(
        "dandi v%s, hdmf v%s, pynwb v%s, h5py v%s",
        __version__,
        get_module_version("hdmf"),
        get_module_version("pynwb"),
        get_module_version("h5py"),
        extra={"file_only": True},
    )
    lgr.info("sys.argv = %r", sys.argv, extra={"file_only": True})
    lgr.info("os.getcwd() = %s", os.getcwd(), extra={"file_only": True})

    ctx.obj = SimpleNamespace(logfile=logfile)

    if pdb:
        map_to_click_exceptions._do_map = False
        from ..utils import setup_exceptionhook

        setup_exceptionhook()

    from ..utils import check_dandi_version

    check_dandi_version()


#
# Commands in the main group
#
from .cmd_delete import delete  # noqa: E402
from .cmd_digest import digest  # noqa: E402
from .cmd_download import download  # noqa: E402
from .cmd_instances import instances  # noqa: E402
from .cmd_ls import ls  # noqa: E402
from .cmd_move import move  # noqa: E402
from .cmd_organize import organize  # noqa: E402
from .cmd_service_scripts import service_scripts  # noqa: E402
from .cmd_shell_completion import shell_completion  # noqa: E402
from .cmd_upload import upload  # noqa: E402
from .cmd_validate import validate, validate_bids  # noqa: E402

__all_commands__ = (
    delete,
    digest,
    download,
    instances,
    ls,
    move,
    organize,
    service_scripts,
    shell_completion,
    upload,
    validate,
    validate_bids,
)

for cmd in __all_commands__:
    main.add_command(cmd)
