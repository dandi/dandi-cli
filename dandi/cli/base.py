from functools import wraps
import os
from os import path as op

import click

from ..consts import dandiset_metadata_file, known_instances
from .. import get_logger, set_logger_level  # noqa: F401

lgr = get_logger()

# Aux common functionality


def get_files(paths, recursive=True, recursion_limit=None):
    """Given a list of paths, return a list of paths"""
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
        import girder_client as gcl

        from ..girder import get_HttpError_response

        try:
            return f(*args, **kwargs)
        # Prints global Usage: useless in majority of cases.
        # It seems we better use it with some ctx, so it would hint in some
        # cases to the help of a specific command
        # except ValueError as e:
        #     raise click.UsageError(str(e))
        except Exception as e:
            if isinstance(e, gcl.HttpError):
                resp = get_HttpError_response(e)
                if resp is None:
                    e_str = str(e)
                else:
                    e_str = resp.get("message", str(e))
            else:
                e_str = str(e)
            lgr.debug("Caught exception %s", e_str)
            if not map_to_click_exceptions._do_map:
                raise
            raise click.ClickException(e_str)
        finally:
            if obj is not None:
                # obj is None when invoking a subcommand directly (as is done
                # during testing) instead of via the `main` command.
                lgr.info("Logs saved in %s", obj.logfile)

    return wrapper


map_to_click_exceptions._do_map = not bool(os.environ.get("DANDI_DEVEL", None))
