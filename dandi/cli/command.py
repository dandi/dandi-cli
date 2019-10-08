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

from ..pynwb_utils import (
    get_metadata,
    get_nwb_version,
)
from ..support import pyout as pyouts

lgr = get_logger()

#
# Main group
#

# group to provide commands
@click.group(cls=DYMGroup)
@click.option('-l', '--log-level', help="Log level (TODO non-numeric values)",
              type=click.IntRange(1, 40), default=logging.INFO)
@click.option('--pdb', help='Fall into pdb if errors out', is_flag=True)
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
            "operation. Was provided following directories: {}".format(', '.join(dirs))
        )
    return paths


# TODO: RF to use as a callback. For some reason just hanged
def get_metadata_pyout(path):
    rec = {}
    try:
        meta = get_metadata(path)
        # normalize some fields and remove completely empty
        for f, v in meta.items():
            if isinstance(v, (tuple, list)):
                v = ', '.join(v)
            if v:
                rec[f] = v
    except Exception as exc:
        lgr.debug('Failed to get metadata from %s: %s', path, exc)

    if 'nwb_version' not in rec:
        # Let's at least get that one
        try:
            rec['NWB'] = get_nwb_version(path) or ''
        except Exception as exc:
            rec['NWB'] = 'ERROR'
            lgr.debug('Failed to get even nwb_version from %s: %s', path, exc)
    else:
        # renames for more concise ls
        rec['NWB'] = rec.pop('nwb_version', '')
    return rec


@main.command()
@click.argument('paths', nargs=-1, type=click.Path(exists=True, dir_okay=False))
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
            ('summary_', {"bold": True}),
            ('header_', dict(
                bold=True,
                transform=lambda x: {
                    # shortening for some fields
                    #'annex_local_size': 'annex(present)',
                    #'annex_worktree_size': 'annex(worktree)',
                }.get(x, x).upper()
            )),
            # ('default_', dict(align="center")),
            ('default_', dict(missing="")),
            ('path', dict(
                bold=True,
                align="left",
                underline=True,
                width=dict(
                    truncate='left',
                    max=max_filename_len + 1
                ),
                aggregate=lambda _: "Summary:"
                # TODO: seems to be wrong
                # width='auto'
                # summary=lambda x: "TOTAL: %d" % len(x)
            )),
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
            ('size', pyouts.size_style),
            ('session_start_time', dict(
                transform=pyouts.datefmt,
                aggregate=pyouts.summary_dates,
                # summary=summary_dates
            ))
        ]
    )
    if not sys.stdout.isatty():
        # TODO: ATM width in the final mode is hardcoded
        #  https://github.com/pyout/pyout/issues/70
        # and depending on how it would be resolved, there might be a
        # need to specify it here as "max" or smth like that.
        # For now hardcoding to hopefully wide enough 200 if stdout is not
        # a tty
        PYOUT_STYLE['width_'] = 200

    out = pyout.Tabular(
        columns=[
            'path',
            'NWB',
            'size',
            #'experiment_description',
            'lab',
            'experimenter',
            'session_id',
            'subject_id',
            'session_start_time',
            #'identifier',  # note: required arg2 of NWBFile
            #'institution',
            'keywords',
            #'related_publications',
            #'session_description',  # note: required arg1 of NWBFile
        ],
        style=PYOUT_STYLE
        # , stream=...
    )
    with out:
        for path in files:
            rec = {'path': path}
            try:
                rec['size'] = os.stat(path).st_size
                rec.update(get_metadata_pyout(path))
            except FileNotFoundError as exc:
                #lgr.error("File is not available: %s", exc)
                pass
            out(rec)

#
# Validate
#

@main.command()
@click.argument('paths', nargs=-1, type=click.Path(exists=True, dir_okay=False))
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
            "ignoring namespace 'core' because it already exists"
    ):
        warnings.filterwarnings('ignore', s, UserWarning)

    errors = {}
    for path in files:
        try:
            with pynwb.NWBHDF5IO(path, 'r', load_namespaces=True) as reader:
                validation = pynwb.validate(reader)
                if validation:
                    errors[path] = validation
        except Exception as exc:
            errors[path] = ["Failed to validate: %s" % str(exc)]

    # TODO: Most likely we want to summarize errors across files since they
    # are likely to be similar
    # TODO: add our own criteria for validation (i.e. having needed metadata)
    if errors:
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
        for path, errors in errors.items():
            click.secho(path, bold=True)
            for error in errors:
                click.secho("  {}".format(error), fg='red')
        raise SystemExit(1)
    else:
        click.secho(
            "No validation errors among {} files".format(len(files)),
            bold=True, fg='green'
        )
