from __future__ import annotations

from collections.abc import Iterable
import logging
import os
import re
from typing import cast
import warnings

import click

from .base import devel_debug_option, devel_option, map_to_click_exceptions
from ..utils import pluralize
from ..validate import validate as validate_
from ..validate_types import Severity, ValidationResult


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
@click.pass_context
@map_to_click_exceptions
def validate_bids(
    ctx,
    paths,
    schema,
    report,
    report_path,
    grouping="none",
):
    """Validate BIDS paths.
    Notes
    -----
    * Used from bash, eg:
    dandi validate-bids /my/path
    * DEPRECATED: use  dandi validate /my/path
    """

    warnings.filterwarnings("default")
    warnings.warn(
        "The `dandi validate-bids` command line interface is deprecated, you can use "
        "`dandi validate` instead. Proceeding to parse the call to `dandi validate` now.",
        DeprecationWarning,
    )
    ctx.invoke(validate, paths=paths, grouping=grouping)


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
@click.option("--ignore", metavar="REGEX", help="Regex matching error IDs to ignore")
@click.option(
    "--min-severity",
    help="Only display issues with severities above this level.",
    type=click.Choice([i.name for i in Severity], case_sensitive=True),
    default="HINT",
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=True))
@devel_debug_option()
@map_to_click_exceptions
def validate(
    paths: tuple[str, ...],
    ignore: str | None,
    grouping: str,
    min_severity: str,
    schema: str | None = None,
    devel_debug: bool = False,
    allow_any_path: bool = False,
) -> None:
    """Validate files for data standards compliance.

    Exits with non-0 exit code if any file is not compliant.
    """
    # Avoid heavy import by importing within function:
    from ..pynwb_utils import ignore_benign_pynwb_warnings

    # Don't log validation warnings, as this command reports them to the user
    # anyway:
    root = logging.getLogger()
    for h in root.handlers:
        h.addFilter(lambda r: not getattr(r, "validating", False))

    if not paths:
        paths = (os.curdir,)
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

    min_severity_value = Severity[min_severity].value

    filtered_results = [
        i
        for i in validator_result
        if i.severity is not None and i.severity.value >= min_severity_value
    ]

    _process_issues(filtered_results, grouping, ignore)


def _process_issues(
    validator_result: Iterable[ValidationResult],
    grouping: str,
    ignore: str | None = None,
) -> None:
    issues = [i for i in validator_result if i.severity is not None]
    if ignore is not None:
        issues = [i for i in issues if not re.search(ignore, i.id)]
    purviews = [i.purview for i in issues]
    if grouping == "none":
        display_errors(
            purviews,
            [i.id for i in issues],
            cast("list[Severity]", [i.severity for i in issues]),
            [i.message for i in issues],
        )
    elif grouping == "path":
        # The purviews are the paths, if we group by path, we need to de-duplicate.
        # typing complains if we just take the set, though the code works otherwise.
        purviews = list(set(purviews))
        for purview in purviews:
            applies_to = [i for i in issues if purview == i.purview]
            display_errors(
                [purview],
                [i.id for i in applies_to],
                cast("list[Severity]", [i.severity for i in applies_to]),
                [i.message for i in applies_to],
            )
    else:
        raise NotImplementedError(
            "The `grouping` parameter values currently supported are 'path' and"
            " 'none'."
        )
    if any(i.severity is Severity.ERROR for i in issues):
        raise SystemExit(1)
    else:
        click.secho("No errors found.", fg="green")


def _get_severity_color(severities: list[Severity]) -> str:
    if Severity.ERROR in severities:
        return "red"
    elif Severity.WARNING in severities:
        return "yellow"
    else:
        return "blue"


def display_errors(
    purviews: list[str | None],
    errors: list[str],
    severities: list[Severity],
    messages: list[str | None],
) -> None:
    """
    Unified error display for validation CLI, which auto-resolves grouping
    logic based on the length of input lists.

    Notes
    -----
    * There is a bit of roundabout and currently untestable logic to deal with
      potential cases where the same error has multiple error message, could be
      removed in the future and removed by assert if this won't ever be the
      case.
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
