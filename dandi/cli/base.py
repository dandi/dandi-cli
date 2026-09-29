from enum import Enum
from functools import wraps
from gettext import gettext as _
import os
from typing import Any

import click
from click.utils import format_filename

from .. import get_logger

lgr = get_logger()

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

    def get_metavar(self, param, ctx=None):
        return "N[:M]"


class EnumChoice(click.Choice):
    """A ``click.Choice`` over an ``Enum``, matched on member values.

    ``click >= 8.2`` matches ``Enum`` members on ``.name`` by default; this
    subclass overrides :meth:`click.Choice.normalize_choice` to match on
    ``.value`` instead, so command-line tokens stay the lowercase enum values
    (``error``, ``skip``, ...). ``click.Choice.convert`` then returns the
    matched enum member.
    """

    def normalize_choice(self, choice, ctx=None):
        return choice.value if isinstance(choice, Enum) else str(choice)


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

    def get_metavar(self, param, ctx=None):
        return "[" + ",".join(self.values) + ",all]"


class LinkAwarePath(click.Path):
    """
    A ``click.Path`` that knows a symlink can be there even if its target is not

    ``click.Path(exists=True)`` follows symlinks, so it turns away a broken one
    as "does not exist" before the command ever sees it.  In a git-annex or
    DataLad dataset, that is common: a file whose content has not been fetched
    is exactly such a link.  Commands like ``dandi validate`` should still take
    these paths, to report on them (or skip them) rather than refuse them.

    With ``lexists=True``, the link itself only has to be there, whether or not
    its target is.  It cannot be combined with ``resolve_path=True``, which
    would swap the link for its missing target.
    """

    def __init__(self, *, lexists: bool = False, **kwargs: Any) -> None:
        if lexists and kwargs.get("resolve_path"):
            raise ValueError("lexists=True cannot be combined with resolve_path=True")
        super().__init__(**kwargs)
        self.lexists = lexists

    def convert(
        self, value: Any, param: click.Parameter | None, ctx: click.Context | None
    ) -> Any:
        is_dash = self.file_okay and self.allow_dash and value in ("-", b"-")
        if self.lexists and not is_dash and not os.path.lexists(value):
            self.fail(
                _("{name} {filename!r} does not exist.").format(
                    name=self.name.title(), filename=format_filename(value)
                ),
                param,
                ctx,
            )
        return super().convert(value, param, ctx)


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
