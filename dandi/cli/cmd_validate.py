import logging
import os
from typing import List, cast

import click

from .base import devel_debug_option, devel_option, map_to_click_exceptions
from ..utils import pluralize
from ..validate_types import Severity


@click.command()
@click.option(
    "--schema", help="Validate against new BIDS schema version.", metavar="VERSION"
)
@click.option(
    "--report-path",
    help="Write report under path, this option implies `--report/-r`.",
)
@click.option(
    "--report",
    "-r",
    is_flag=True,
    help="Whether to write a report under a unique path in the DANDI log directory.",
)
@click.option(
    "--grouping",
    "-g",
    help="How to group error/warning reporting.",
    type=click.Choice(["none", "path"], case_sensitive=False),
    default="none",
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=True))
@map_to_click_exceptions
def validate_bids(
    paths,
    schema,
    report,
    report_path,
    grouping="none",
):
    """Validate BIDS paths.

    Notes
    -----
    Used from bash, eg:
        dandi validate-bids /my/path
    """

    from ..validate import validate_bids as validate_bids_

    validator_result = validate_bids_(  # Controller
        *paths,
        report=report,
        report_path=report_path,
        schema_version=schema,
    )

    _process_issues(validator_result, grouping)


@click.command()
@devel_option("--schema", help="Validate against new schema version", metavar="VERSION")
@devel_option(
    "--allow-any-path",
    help="For development: allow DANDI 'unsupported' file types/paths",
    default=False,
    is_flag=True,
)
@click.option(
    "--grouping",
    "-g",
    help="How to group error/warning reporting.",
    type=click.Choice(["none", "path"], case_sensitive=False),
    default="none",
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=True))
@devel_debug_option()
@map_to_click_exceptions
def validate(
    paths,
    schema=None,
    devel_debug=False,
    allow_any_path=False,
    grouping="none",
):
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

    validator_result = validate_(
        *paths,
        schema_version=schema,
        devel_debug=devel_debug,
        allow_any_path=allow_any_path,
    )

    _process_issues(validator_result, grouping)


def _process_issues(validator_result, grouping):

    issues = [i for i in validator_result if i.severity]

    purviews = [
        list(filter(bool, [i.path, i.path_regex, i.dataset_path]))[0] for i in issues
    ]
    if grouping == "none":
        display_errors(
            purviews,
            [i.id for i in issues],
            [i.severity for i in issues],
            [i.message for i in issues],
        )
    elif grouping == "path":
        for purview in purviews:
            applies_to = [
                i for i in issues if purview in [i.path, i.path_regex, i.dataset_path]
            ]
            display_errors(
                [purview],
                [i.id for i in applies_to],
                [i.severity for i in applies_to],
                [i.message for i in applies_to],
            )
    else:
        raise NotImplementedError(
            "The `grouping` parameter values currently supported are " "path or None."
        )

    validation_errors = [i for i in issues if i.severity == Severity.ERROR]

    if validation_errors:
        raise SystemExit(1)
    else:
        click.secho("No errors found.", fg="green")


def _get_severity_color(severities):

    if Severity.ERROR in severities:
        return "red"
    elif Severity.WARNING in severities:
        return "yellow"
    else:
        return "blue"


def display_errors(
    purviews: List[str],
    errors: List[str],
    severities: List[Severity],
    messages: List[str],
) -> None:
    """
    Unified error display for validation CLI, which auto-resolves grouping logic based on
    the length of input lists.


    Notes
    -----
    * There is a bit of roundabout and currently untestable logic to deal with potential cases
    where the same error has multiple error message, could be removed in the future and removed
    by assert if this won't ever be the case.
    """

    if all(len(cast(list, i)) == 1 for i in [purviews, errors, severities, messages]):
        fg = _get_severity_color(severities)
        error_message = f"[{errors[0]}] {purviews[0]} — {messages[0]}"
        click.secho(error_message, fg=fg)
    elif len(purviews) == 1:
        group_message = f"{purviews[0]}: {pluralize(len(errors), 'issue')} detected."
        fg = _get_severity_color(severities)
        click.secho(group_message, fg=fg)
        for error, severity, message in zip(errors, severities, messages):
            error_message = f"  [{error}] {message}"
            fg = _get_severity_color([severity])
            click.secho(error_message, fg=fg)
    elif len(errors) == 1:
        fg = _get_severity_color(severities)
        group_message = (
            f"{errors[0]}: detected in {pluralize(len(purviews), 'purviews')}"
        )
        if len(set(messages)) == 1:
            group_message += f" — {messages[0]}."
            click.secho(group_message, fg=fg)
            for purview, severity in zip(purviews, severities):
                error_message = f"  {purview}"
                fg = _get_severity_color([severity])
                click.secho(error_message, fg=fg)
        else:
            group_message += "."
            click.secho(group_message, fg=fg)
            for purview, severity, message in zip(purviews, severities, messages):
                error_message = f"  {purview} — {message}"
                fg = _get_severity_color([severity])
                click.secho(error_message, fg=fg)
    else:
        for purview, error, severity, message in zip(
            purviews, errors, severities, messages
        ):
            fg = _get_severity_color([severity])
            error_message = f"[{error}] {purview} — {message}"
            click.secho(error_message, fg=fg)
