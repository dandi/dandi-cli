from __future__ import annotations

import logging
import os
import re
import sys
from typing import cast
import warnings

import click

from .base import devel_debug_option, devel_option, map_to_click_exceptions
from .formatter import JSONFormatter, JSONLinesFormatter, YAMLFormatter
from ..utils import pluralize
from ..validate.core import validate as validate_
from ..validate.io import validation_sidecar_path, write_validation_jsonl
from ..validate.types import Severity, ValidationResult

lgr = logging.getLogger(__name__)

STRUCTURED_FORMATS = ("json", "json_pp", "json_lines", "yaml")


def _collect_results(
    paths: tuple[str, ...],
    schema: str | None,
    devel_debug: bool,
    allow_any_path: bool,
) -> list[ValidationResult]:
    """Run validation and collect all results into a list."""
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

    return list(
        validate_(
            *paths,
            schema_version=schema,
            devel_debug=devel_debug,
            allow_any_path=allow_any_path,
        )
    )


def _filter_results(
    results: list[ValidationResult],
    min_severity: str,
    ignore: str | None,
) -> list[ValidationResult]:
    """Filter results by minimum severity and ignore pattern."""
    min_severity_value = Severity[min_severity].value
    filtered = [
        r
        for r in results
        if r.severity is not None and r.severity.value >= min_severity_value
    ]
    if ignore is not None:
        filtered = [r for r in filtered if not re.search(ignore, r.id)]
    return filtered


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
@click.option(
    "--format",
    "-f",
    "output_format",
    help="Output format.",
    type=click.Choice(["human", "json", "json_pp", "json_lines", "yaml"]),
    default="human",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    help="Write output to file instead of stdout. "
    "Requires --format to be set to a structured format.",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
)
@click.option(
    "--summary/--no-summary",
    help="Show summary statistics.",
    default=False,
)
@click.option(
    "--load",
    help="Load validation results from JSONL file(s) instead of running validation.",
    type=click.Path(exists=True, dir_okay=False),
    multiple=True,
    default=(),
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=True))
@click.pass_context
@devel_debug_option()
@map_to_click_exceptions
def validate(
    ctx: click.Context,
    paths: tuple[str, ...],
    ignore: str | None,
    grouping: str,
    min_severity: str,
    output_format: str = "human",
    output_file: str | None = None,
    summary: bool = False,
    load: tuple[str, ...] = (),
    schema: str | None = None,
    devel_debug: bool = False,
    allow_any_path: bool = False,
) -> None:
    """Validate files for data standards compliance.

    Exits with non-0 exit code if any file is not compliant.
    """
    if output_file is not None and output_format not in STRUCTURED_FORMATS:
        raise click.UsageError(
            "--output requires --format to be set to a structured format "
            "(json, json_pp, json_lines, yaml)."
        )

    if load and paths:
        raise click.UsageError("--load and positional paths are mutually exclusive.")

    if load:
        from ..validate.io import load_validation_jsonl

        results = load_validation_jsonl(*load)
    else:
        results = _collect_results(paths, schema, devel_debug, allow_any_path)

    filtered = _filter_results(results, min_severity, ignore)

    if output_format == "human":
        _render_human(filtered, grouping)
        if summary:
            _print_summary(filtered, sys.stdout)
        _exit_if_errors(filtered)
    elif output_file is not None:
        with open(output_file, "w") as fh:
            _render_structured(filtered, output_format, fh)
        lgr.info("Validation output written to %s", output_file)
        if summary:
            _print_summary(filtered, sys.stderr)
        _exit_if_errors(filtered)
    else:
        _render_structured(filtered, output_format, sys.stdout)
        if summary:
            _print_summary(filtered, sys.stderr)
        # Auto-save sidecar next to logfile (skip when loading)
        if not load and filtered and hasattr(ctx, "obj") and ctx.obj is not None:
            _auto_save_sidecar(filtered, ctx.obj.logfile)
        _exit_if_errors(filtered)


def _auto_save_sidecar(results: list[ValidationResult], logfile: str) -> None:
    """Write validation sidecar JSONL next to the logfile."""
    sidecar = validation_sidecar_path(logfile)
    write_validation_jsonl(results, sidecar)
    lgr.info("Validation sidecar saved to %s", sidecar)


def _print_summary(results: list[ValidationResult], out: object) -> None:
    """Print summary statistics about validation results."""
    from collections import Counter

    total = len(results)
    print("\n--- Validation Summary ---", file=out)
    print(f"Total issues: {total}", file=out)
    if not total:
        return

    severity_counts = Counter(
        r.severity.name if r.severity is not None else "NONE" for r in results
    )
    print("By severity:", file=out)
    for sev in ("CRITICAL", "ERROR", "WARNING", "HINT", "INFO"):
        if sev in severity_counts:
            print(f"  {sev}: {severity_counts[sev]}", file=out)

    validator_counts = Counter(r.origin.validator.value for r in results)
    if validator_counts:
        print("By validator:", file=out)
        for validator, count in validator_counts.most_common():
            print(f"  {validator}: {count}", file=out)

    standard_counts = Counter(
        r.origin.standard.value if r.origin.standard is not None else "N/A"
        for r in results
    )
    if standard_counts:
        print("By standard:", file=out)
        for standard, count in standard_counts.most_common():
            print(f"  {standard}: {count}", file=out)


def _get_formatter(output_format: str, out: object = None):
    """Create a formatter for the given output format."""
    if output_format == "json":
        return JSONFormatter(out=out)
    elif output_format == "json_pp":
        return JSONFormatter(indent=2, out=out)
    elif output_format == "json_lines":
        return JSONLinesFormatter(out=out)
    elif output_format == "yaml":
        return YAMLFormatter(out=out)
    else:
        raise ValueError(f"Unknown format: {output_format}")


def _render_structured(
    results: list[ValidationResult],
    output_format: str,
    out: object,
) -> None:
    """Render validation results in a structured format."""
    formatter = _get_formatter(output_format, out=out)
    with formatter:
        for r in results:
            formatter(r.model_dump(mode="json"))


def _exit_if_errors(results: list[ValidationResult]) -> None:
    """Raise SystemExit(1) if any result has severity >= ERROR."""
    if any(r.severity is not None and r.severity >= Severity.ERROR for r in results):
        raise SystemExit(1)


def _render_human(
    issues: list[ValidationResult],
    grouping: str,
) -> None:
    """Render validation results in human-readable colored format."""
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

    if not any(r.severity is not None and r.severity >= Severity.ERROR for r in issues):
        click.secho("No errors found.", fg="green")


def _process_issues(
    issues: list[ValidationResult],
    grouping: str,
) -> None:
    """Legacy wrapper: render human output and exit if errors."""
    _render_human(issues, grouping)
    _exit_if_errors(issues)


def _get_severity_color(severities: list[Severity]) -> str:
    max_severity = max(severities, default=Severity.INFO)
    if max_severity >= Severity.ERROR:
        return "red"
    if max_severity >= Severity.WARNING:
        return "yellow"

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
