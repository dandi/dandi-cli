from functools import wraps
import os

import click
from dandischema.conf import set_instance_config
import requests
from yarl import URL

from dandi.consts import known_instances
from dandi.utils import ServerInfo

from .. import get_logger

lgr = get_logger()


def get_server_info(dandi_id: str) -> ServerInfo:
    """
    Get server info from a particular DANDI instance

    Parameters
    ----------
    dandi_id : str
        The ID specifying the particular known DANDI instance to query for server info.
        This is a key in the `dandi.consts.known_instances` dictionary.

    Returns
    -------
    ServerInfo
        An object representing the server information responded by the DANDI instance.

    Raises
    ------
    valueError
        If the provided `dandi_id` is not a valid key in the
        `dandi.consts.known_instances` dictionary.
    """
    if dandi_id not in known_instances:
        raise ValueError(f"Unknown DANDI instance: {dandi_id}")

    info_url = str(URL(known_instances[dandi_id].api) / "info/")
    resp = requests.get(info_url)
    resp.raise_for_status()
    return ServerInfo.model_validate(resp.json())


def bind_client(server_info: ServerInfo) -> None:
    """
    Bind the DANDI client to a specific DANDI server instance. I.e., to set the DANDI
    server instance as the context of subsequent command executions by the DANDI client

    Parameters
    ----------
    server_info : ServerInfo
        An object containing the information of the DANDI server instance to bind to.
        This is typically obtained by calling `get_server_info()`.
    """
    set_instance_config(server_info.instance_config)


# Aux common functionality


class IntColonInt(click.ParamType):
    name = "int:int"

    def convert(self, value, param, ctx):
        if isinstance(value, str):
            v1, colon, v2 = value.partition(":")
            try:
                v1 = int(v1)
                v2 = int(v2) if colon else None
            except ValueError:
                self.fail("Value must be of the form `N[:M]`", param, ctx)
            return (v1, v2)
        else:
            return value

    def get_metavar(self, param):
        return "N[:M]"


class ChoiceList(click.ParamType):
    name = "choice-list"

    def __init__(self, values):
        self.values = set(values)

    def convert(self, value, param, ctx):
        if value is None or isinstance(value, set):
            return value
        selected = set()
        for v in value.split(","):
            if v == "all":
                selected = self.values.copy()
            elif v in self.values:
                selected.add(v)
            else:
                must_be = ", ".join(sorted(self.values)) + ", all"
                self.fail(
                    f"{v!r}: invalid value; must be one of: {must_be}", param, ctx
                )
        return selected

    def get_metavar(self, param):
        return "[" + ",".join(self.values) + ",all]"


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


def dandiset_path_option(**kwargs):
    return _updated_option(
        "-d",
        "--dandiset-path",
        kwargs,
        help="Top directory (local) of the dandiset.",
        type=click.Path(exists=True, dir_okay=True, file_okay=False),
    )


def instance_option(**kwargs):
    params = {
        "help": "DANDI instance to use",
        "default": "dandi",
        "show_default": True,
        "envvar": "DANDI_INSTANCE",
        "show_envvar": True,
    }
    params.update(kwargs)
    return click.option("-i", "--dandi-instance", **params)


def devel_debug_option():
    return devel_option(
        "--devel-debug",
        help="For development: do not use pyout callbacks, do not swallow"
        " exception, do not parallelize",
        default=False,
        is_flag=True,
    )


def map_to_click_exceptions(f):
    """Catch all exceptions and re-raise as click exceptions.

    Will be active only if DANDI_DEVEL is not set and --pdb is not given
    """

    @click.pass_obj
    @wraps(f)
    def wrapper(obj, *args, **kwargs):
        try:
            return f(*args, **kwargs)
        # Prints global Usage: useless in majority of cases.
        # It seems we better use it with some ctx, so it would hint in some
        # cases to the help of a specific command
        # except ValueError as e:
        #     raise click.UsageError(str(e))
        except Exception as e:
            e_str = str(e)
            lgr.debug("Caught exception %s", e_str, exc_info=True)
            if not map_to_click_exceptions._do_map:
                raise
            raise click.ClickException(e_str)
        finally:
            if obj is not None:
                # obj is None when invoking a subcommand directly (as is done
                # during testing) instead of via the `main` command.
                lgr.info("Logs saved in %s", obj.logfile)

    return wrapper


map_to_click_exceptions._do_map = not bool(  # type: ignore[attr-defined]
    os.environ.get("DANDI_DEVEL", None)
)
