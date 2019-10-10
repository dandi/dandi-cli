"""
Commands definition for DANDI command line interface
"""

import os
import os.path as op
import sys

import click
from click_didyoumean import DYMGroup

import pyout

import logging
from .. import get_logger

from collections import OrderedDict

from .. import __version__

# Delay imports leading to import of heavy modules such as pynwb and h5py
# Import at the point of use
# from ..pynwb_utils import ...
from ..support import pyout as pyouts

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
    get_logger().setLevel(log_level)  # common one
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


def get_metadata_pyout(path, keys):
    from ..pynwb_utils import get_metadata, get_nwb_version

    def fn():
        rec = {}
        try:
            meta = get_metadata(path)
            # normalize some fields and remove completely empty
            for f, v in meta.items():
                if f not in keys:
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
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=False))
def ls(paths):
    """List file size and selected set of metadata fields
    """
    # For now we support only individual files
    files = get_files(paths)

    if not files:
        return

    max_filename_len = max(map(lambda x: len(op.basename(x)), files))
    # Needs to stay here due to use of  counds/mapped_counts
    PYOUT_STYLE = OrderedDict(
        [
            ("summary_", {"bold": True}),
            (
                "header_",
                dict(
                    bold=True,
                    transform=lambda x: {
                        # shortening for some fields
                        "nwb_version": "NWB",
                        #'annex_local_size': 'annex(present)',
                        #'annex_worktree_size': 'annex(worktree)',
                    }
                    .get(x, x)
                    .upper(),
                ),
            ),
            # ('default_', dict(align="center")),
            ("default_", dict(missing="")),
            (
                "path",
                dict(
                    bold=True,
                    align="left",
                    underline=True,
                    width=dict(
                        truncate="left",
                        # min=max_filename_len + 4 #  .../
                        # min=0.3  # not supported yet by pyout, https://github.com/pyout/pyout/issues/85
                    ),
                    aggregate=lambda _: "Summary:"
                    # TODO: seems to be wrong
                    # width='auto'
                    # summary=lambda x: "TOTAL: %d" % len(x)
                ),
            ),
            # ('type', dict(
            #     transform=lambda s: "%s" % s,
            #     aggregate=counts,
            #     missing='-',
            #     # summary=summary_counts
            # )),
            # ('describe', dict(
            #     transform=empty_for_none)),
            # ('clean', dict(
            #     color='green',
            #     transform=fancy_bool,
            #     aggregate=mapped_counts({False: fancy_bool(False),
            #                              True: fancy_bool(True)}),
            #     delayed="group-git"
            # )),
            ("size", pyouts.size_style),
            (
                "session_start_time",
                dict(
                    transform=pyouts.datefmt,
                    aggregate=pyouts.summary_dates,
                    # summary=summary_dates
                ),
            ),
        ]
    )
    if not sys.stdout.isatty():
        # TODO: ATM width in the final mode is hardcoded
        #  https://github.com/pyout/pyout/issues/70
        # and depending on how it would be resolved, there might be a
        # need to specify it here as "max" or smth like that.
        # For now hardcoding to hopefully wide enough 200 if stdout is not
        # a tty
        PYOUT_STYLE["width_"] = 200

    out = pyout.Tabular(
        columns=[
            "path",
            "nwb_version",
            "size",
            #'experiment_description',
            "lab",
            "experimenter",
            "session_id",
            "subject_id",
            "session_start_time",
            #'identifier',  # note: required arg2 of NWBFile
            #'institution',
            "keywords",
            #'related_publications',
            #'session_description',  # note: required arg1 of NWBFile
        ],
        style=PYOUT_STYLE
        # , stream=...
    )
    with out:
        async_keys = (
            "NWB",
            "lab",
            "experimenter",
            "session_id",
            "subject_id",
            "session_start_time",
            "keywords",
        )
        for path in files:
            rec = {"path": path}
            try:
                rec["size"] = os.stat(path).st_size
                rec[async_keys] = get_metadata_pyout(path, async_keys)
            except FileNotFoundError as exc:
                # lgr.error("File is not available: %s", exc)
                pass
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
