import logging
import os

import click

from .base import devel_debug_option, devel_option, lgr, map_to_click_exceptions
from ..utils import pluralize


@click.command()
@devel_option(
    "--schema", help="Validate against new BIDS schema version", metavar="VERSION"
)
@click.option("--report", help="Specify path to write a report under.")
@click.option(
    "--report-flag",
    "-r",
    is_flag=True,
    help="Whether to write a report under a unique path in the current directory. "
    "Only usable if `--report` is not already used.",
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=True))
@devel_debug_option()
@map_to_click_exceptions
def validate_bids(
    paths, schema=None, devel_debug=False, report=False, report_flag=False
):
    """Validate BIDS paths."""
    from ..validate import validate_bids as validate_bids_

    if report_flag and not report:
        report = report_flag

    validation_result = validate_bids_(
        *paths,
        report=report,
        schema_version=schema,
        devel_debug=devel_debug,
    )
    missing_files = [
        pattern["regex"]
        for pattern in validation_result["schema_tracking"]
        if pattern["mandatory"]
    ]
    error_list = []
    if missing_files:
        error_substring = (
            f"{pluralize(len(missing_files), 'filename pattern')} required "
            "by BIDS could not be found"
        )
        error_list.append(error_substring)
    if validation_result["path_tracking"]:
        error_substring = (
            f"{pluralize(len(validation_result['path_tracking']), 'filename')} "
            "did not match any pattern known to BIDS"
        )
        error_list.append(error_substring)
    if error_list:
        error_string = " and ".join(error_list)
        error_string = f"Summary: {error_string}."
        click.secho(
            error_string,
            bold=True,
            fg="red",
        )
        raise SystemExit(1)


@click.command()
@devel_option("--schema", help="Validate against new schema version", metavar="VERSION")
@devel_option(
    "--allow-any-path",
    help="For development: allow DANDI 'unsupported' file types/paths",
    default=False,
    is_flag=True,
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=True))
@devel_debug_option()
@map_to_click_exceptions
def validate(paths, schema=None, devel_debug=False, allow_any_path=False):
    """Validate files for NWB and DANDI compliance.

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
        *paths,
        schema_version=schema,
        devel_debug=devel_debug,
        allow_any_path=allow_any_path,
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
