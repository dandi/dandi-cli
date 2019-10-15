"""
Commands definition for DANDI command line interface
"""

import os
import os.path as op
import sys

import click
from click_didyoumean import DYMGroup

import logging
from .. import get_logger, set_logger_level

from collections import OrderedDict

from .. import __version__

# Delay imports leading to import of heavy modules such as pynwb and h5py
# Import at the point of use
# from ..pynwb_utils import ...

lgr = get_logger()

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
    help="Log level (TODO non-numeric values)",
    type=click.IntRange(1, 40),
    default=logging.INFO,
)
@click.option("--pdb", help="Fall into pdb if errors out", is_flag=True)
def main(log_level, pdb=False):
    set_logger_level(get_logger(), log_level)  # common one
    if pdb:
        from ..utils import setup_exceptionhook

        setup_exceptionhook()


#
# ls
#

# TODO: all the recursion options etc
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


def get_metadata_pyout(path, keys=None):
    from ..pynwb_utils import get_metadata, get_nwb_version

    def fn():
        rec = {}
        # No need for calling get_metadata if no keys are needed from it
        if keys is None or list(keys) != ["nwb_version"]:
            try:
                meta = get_metadata(path)
                # normalize some fields and remove completely empty
                for f, v in meta.items():
                    if keys is not None and f not in keys:
                        continue
                    if isinstance(v, (tuple, list)):
                        v = ", ".join(v)
                    if v:
                        rec[f] = v
            except Exception as exc:
                lgr.debug("Failed to get metadata from %s: %s", path, exc)

        if "nwb_version" not in rec:
            # Let's at least get that one
            try:
                rec["nwb_version"] = get_nwb_version(path) or ""
            except Exception as exc:
                rec["nwb_version"] = "ERROR"
                lgr.debug("Failed to get even nwb_version from %s: %s", path, exc)
        return rec

    return fn


@main.command()
@click.option(
    "-F",
    "--fields",
    help="Comma-separated list of fields to display. "
    "An empty value to trigger a list of "
    "available fields to be printed out",
)
@click.option(
    "-f",
    "--format",
    help="Choose the format/frontend for output. If 'auto', 'pyout' will be "
    "used in case of multiple files, and 'yaml' for a single file.",
    type=click.Choice(["auto", "pyout", "json", "json_pp", "yaml"]),
    default="auto",
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=False))
def ls(paths, fields=None, format="auto"):
    """List file size and selected set of metadata fields
    """
    from ..consts import metadata_all_fields

    all_fields = sorted(["path", "size"] + list(metadata_all_fields))

    # TODO: more logical ordering in case of fields = None
    from .formatter import JSONFormatter, YAMLFormatter, PYOUTFormatter

    # TODO: avoid
    from .formatter import PYOUT_SHORT_NAMES, PYOUT_SHORT_NAMES_rev

    if fields is not None:
        if fields.strip() == "":
            for field in all_fields:
                s = field
                if field in PYOUT_SHORT_NAMES:
                    s += " or %s" % PYOUT_SHORT_NAMES[field]
                click.secho(s)
            raise SystemExit(0)
        fields = fields.split(",")
        # Map possibly present short names back to full names
        fields = [PYOUT_SHORT_NAMES_rev.get(f.lower(), f) for f in fields]
        unknown_fields = set(fields).difference(all_fields)
        if unknown_fields:
            raise ValueError(
                "Following fields are not known: %s" % ", ".join(unknown_fields)
            )

    # For now we support only individual files
    files = get_files(paths)

    if not files:
        return

    if format == "auto":
        format = "yaml" if len(files) == 1 else "pyout"

    if format == "pyout":
        out = PYOUTFormatter(files=files, fields=fields)
    elif format == "json":
        out = JSONFormatter()
    elif format == "json_pp":
        out = JSONFormatter(indent=2)
    elif format == "yaml":
        out = YAMLFormatter()
    else:
        raise NotImplementedError("Unknown format %s" % format)

    if fields is not None:
        async_keys = tuple(set(metadata_all_fields).intersection(fields))
    else:
        async_keys = metadata_all_fields

    with out:
        for path in files:
            rec = {}
            rec["path"] = path

            try:
                if not fields or "size" in fields:
                    rec["size"] = os.stat(path).st_size

                if async_keys:
                    cb = get_metadata_pyout(path, async_keys)
                    if format == "pyout":
                        rec[async_keys] = cb
                    else:
                        # TODO: parallel execution
                        # For now just call callback and get all the fields
                        for k, v in cb().items():
                            rec[k] = v
            except FileNotFoundError as exc:
                lgr.debug("File is not available: %s", exc)
            except Exception as exc:
                lgr.debug("Problem obtaining metadata for %s: %s", path, exc)
            if not rec:
                lgr.debug("Skipping a record for %s since emtpy", path)
                continue
            out(rec)


#
# Validate
#


@main.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=False))
def validate(paths):
    """Validate files for NWB (and DANDI) compliance

    Exits with non-0 exit code if any file is not compliant.
    """
    files = get_files(paths)
    import pynwb
    import warnings

    # below we are using load_namespaces but it causes HDMF to whine if there
    # is no cached name spaces in the file.  It is benign but not really useful
    # at this point, so we ignore it although ideally there should be a formal
    # way to get relevant warnings (not errors) from PyNWB
    #   See https://github.com/dandi/dandi-cli/issues/14 for more info
    for s in (
        "No cached namespaces found .*",
        "ignoring namespace 'core' because it already exists",
    ):
        warnings.filterwarnings("ignore", s, UserWarning)

    view = "one-at-a-time"  # TODO: rename, add groupped
    all_files_errors = {}
    for path in files:
        try:
            with pynwb.NWBHDF5IO(path, "r", load_namespaces=True) as reader:
                errors = pynwb.validate(reader)
        except Exception as exc:
            errors = ["Failed to validate: %s" % str(exc)]
        if view == "one-at-a-time":
            display_errors(path, errors)
        all_files_errors[path] = errors

    if view == "groupped":
        # TODO: Most likely we want to summarize errors across files since they
        # are likely to be similar
        # TODO: add our own criteria for validation (i.e. having needed metadata)

        # # can't be done since fails to compare different types of errors
        # all_errors = sum(errors.values(), [])
        # all_error_types = []
        # errors_unique = sorted(set(all_errors))
        # from collections import Counter
        # # Let's make it
        # print(
        #     "{} unique errors in {} files".format(
        #     len(errors_unique), len(errors))
        # )
        raise NotImplementedError("TODO")

    files_with_errors = [f for f, errors in all_files_errors.items() if errors]

    if files_with_errors:
        click.secho(
            "Summary: Validation errors in {} out of {} files".format(
                len(files_with_errors), len(files)
            ),
            bold=True,
            fg="red",
        )
        raise SystemExit(1)
    else:
        click.secho(
            "Summary: No validation errors among {} file(s)".format(len(files)),
            bold=True,
            fg="green",
        )


def display_errors(path, errors):
    click.echo(
        "{}: {}".format(
            click.style(path, bold=True),
            click.style("ok", fg="green")
            if not errors
            else click.style("{} error(s)".format(len(errors)), fg="red"),
        )
    )
    for error in errors:
        click.secho("  {}".format(error), fg="red")
