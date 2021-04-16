import logging
import os

import click

from .base import devel_debug_option, devel_option, lgr, map_to_click_exceptions


@click.command()
@devel_option("--schema", help="Validate against new schema version", metavar="VERSION")
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=True))
@devel_debug_option()
@map_to_click_exceptions
def validate(paths, schema=None, devel_debug=False):
    """Validate files for NWB (and DANDI) compliance.

    Exits with non-0 exit code if any file is not compliant.
    """
    from ..pynwb_utils import ignore_benign_pynwb_warnings
    from ..validate import validate as validate_

    # Don't log validation warnings, as this command reports them to the user
    # anyway:
    root = logging.getLogger()
    for h in root.handlers:
        h.addFilter(lambda r: not getattr(r, "validating", False))

    if not paths:
        paths = [os.curdir]
    # below we are using load_namespaces but it causes HDMF to whine if there
    # is no cached name spaces in the file.  It is benign but not really useful
    # at this point, so we ignore it although ideally there should be a formal
    # way to get relevant warnings (not errors) from PyNWB
    ignore_benign_pynwb_warnings()
    view = "one-at-a-time"  # TODO: rename, add groupped

    all_files_errors = {}
    nfiles = 0
    for path, errors in validate_(
        paths, schema_version=schema, devel_debug=devel_debug
    ):
        nfiles += 1
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
                len(files_with_errors), nfiles
            ),
            bold=True,
            fg="red",
        )
        raise SystemExit(1)
    else:
        click.secho(
            "Summary: No validation errors among {} file(s)".format(nfiles),
            bold=True,
            fg="green",
        )


def display_errors(path, errors):
    if not errors:
        lgr.info("%s: ok", path)
    else:
        lgr.error("%s: %d error(s)", path, len(errors))
        for error in errors:
            lgr.error("  %s", error)
