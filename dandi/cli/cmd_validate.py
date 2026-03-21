from __future__ import annotations

from collections import OrderedDict
import dataclasses
import json as json_mod
import logging
import os
import re
import sys
from typing import IO, Union, cast
import warnings

import click

from .base import devel_debug_option, devel_option, map_to_click_exceptions
from .formatter import JSONFormatter, JSONLinesFormatter, YAMLFormatter
from ..utils import pluralize
from ..validate.core import validate as validate_
from ..validate.io import validation_sidecar_path, write_validation_jsonl
from ..validate.types import Severity, ValidationResult

lgr = logging.getLogger(__name__)


@dataclasses.dataclass
class TruncationNotice:
    """Placeholder indicating omitted results in truncated output."""

    omitted_count: int


STRUCTURED_FORMATS = ("json", "json_pp", "json_lines", "yaml")

_EXT_TO_FORMAT = {
    ".json": "json_pp",
    ".jsonl": "json_lines",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def _format_from_ext(path: str) -> str | None:
    """Infer output format from file extension, or None if unrecognized."""
    ext = os.path.splitext(path)[1].lower()
    return _EXT_TO_FORMAT.get(ext)


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
    ctx.invoke(
        validate, paths=paths, grouping=(grouping,) if grouping != "none" else ()
    )


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
    help="How to group output. Repeat for hierarchical nesting, e.g. -g severity -g id.",
    type=click.Choice(
        ["none", "path", "severity", "id", "validator", "standard", "dandiset"],
        case_sensitive=False,
    ),
    multiple=True,
    default=(),
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
    "--max-per-group",
    type=int,
    default=None,
    help="Limit results per group (or total if ungrouped). "
    "Excess results are replaced by a count of omitted items.",
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
    grouping: tuple[str, ...],
    min_severity: str,
    output_format: str = "human",
    output_file: str | None = None,
    summary: bool = False,
    max_per_group: int | None = None,
    load: tuple[str, ...] = (),
    schema: str | None = None,
    devel_debug: bool = False,
    allow_any_path: bool = False,
) -> None:
    """Validate files for data standards compliance.

    Exits with non-0 exit code if any file is not compliant.

    Validation results are automatically saved as a JSONL sidecar next to the
    dandi-cli log file (unless --output is used or --load is active).  Use
    ``dandi validate --load <path>`` to re-render saved results later with
    different grouping, filtering, or format options.
    """
    # Normalize grouping: strip "none" values
    grouping = tuple(g for g in grouping if g != "none")

    # Auto-detect format from output file extension when --format not given
    if output_file is not None and output_format == "human":
        detected = _format_from_ext(output_file)
        if detected is None:
            raise click.UsageError(
                "--output requires --format to be set to a structured format "
                "(json, json_pp, json_lines, yaml), or use a recognized "
                "extension (.json, .jsonl, .yaml, .yml)."
            )
        output_format = detected

    # JSONL is incompatible with grouping (flat format, no nesting)
    if grouping and output_format == "json_lines":
        raise click.UsageError(
            "--grouping is incompatible with json_lines format "
            "(JSONL is a flat format that cannot represent nested groups)."
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
        _render_human(filtered, grouping, max_per_group=max_per_group)
        if summary:
            _print_summary(filtered, sys.stdout)
    elif output_file is not None:
        with open(output_file, "w") as fh:
            _render_structured(
                filtered,
                output_format,
                fh,
                grouping,
                max_per_group=max_per_group,
            )
        lgr.info("Validation output written to %s", output_file)
        if summary:
            _print_summary(filtered, sys.stderr)
    else:
        _render_structured(
            filtered,
            output_format,
            sys.stdout,
            grouping,
            max_per_group=max_per_group,
        )
        if summary:
            _print_summary(filtered, sys.stderr)

    # Auto-save sidecar next to logfile (skip when loading or writing to --output file)
    if (
        not load
        and not output_file
        and filtered
        and hasattr(ctx, "obj")
        and ctx.obj is not None
    ):
        _auto_save_sidecar(filtered, ctx.obj.logfile)

    _exit_if_errors(filtered)


def _auto_save_sidecar(results: list[ValidationResult], logfile: str) -> None:
    """Write validation sidecar JSONL next to the logfile."""
    sidecar = validation_sidecar_path(logfile)
    write_validation_jsonl(results, sidecar)
    lgr.info("Validation sidecar saved to %s", sidecar)


def _print_summary(results: list[ValidationResult], out: IO[str]) -> None:
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


def _get_formatter(
    output_format: str, out: IO[str] | None = None
) -> JSONFormatter | JSONLinesFormatter | YAMLFormatter:
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
    out: IO[str],
    grouping: tuple[str, ...] = (),
    max_per_group: int | None = None,
) -> None:
    """Render validation results in a structured format."""
    if grouping:
        # Grouped output: build nested dict, serialize directly
        grouped: GroupedResults | TruncatedResults = _group_results(results, grouping)
        if max_per_group is not None:
            grouped = _truncate_leaves(grouped, max_per_group)
        data = _serialize_grouped(grouped)
        if output_format in ("json", "json_pp"):
            indent = 2 if output_format == "json_pp" else None
            json_mod.dump(data, out, indent=indent, sort_keys=True, default=str)
            out.write("\n")
        elif output_format == "yaml":
            import ruamel.yaml

            yaml = ruamel.yaml.YAML(typ="safe")
            yaml.default_flow_style = False
            yaml.dump(data, out)
        else:
            raise ValueError(f"Unsupported format for grouped output: {output_format}")
    else:
        items: list[dict] = [r.model_dump(mode="json") for r in results]
        if max_per_group is not None and len(items) > max_per_group:
            items = items[:max_per_group]
            items.append(
                {"_truncated": True, "omitted_count": len(results) - max_per_group}
            )
        formatter = _get_formatter(output_format, out=out)
        with formatter:
            for item in items:
                formatter(item)


def _exit_if_errors(results: list[ValidationResult]) -> None:
    """Raise SystemExit(1) if any result has severity >= ERROR."""
    if any(r.severity is not None and r.severity >= Severity.ERROR for r in results):
        raise SystemExit(1)


def _group_key(issue: ValidationResult, grouping: str) -> str:
    """Extract the grouping key from a ValidationResult."""
    if grouping == "path":
        return issue.purview or "(no path)"
    elif grouping == "severity":
        return issue.severity.name if issue.severity is not None else "NONE"
    elif grouping == "id":
        return issue.id
    elif grouping == "validator":
        return issue.origin.validator.value
    elif grouping == "standard":
        return issue.origin.standard.value if issue.origin.standard else "N/A"
    elif grouping == "dandiset":
        return str(issue.dandiset_path) if issue.dandiset_path else "(no dandiset)"
    else:
        raise NotImplementedError(f"Unsupported grouping: {grouping}")


# Recursive grouped type: either a nested OrderedDict or leaf list
GroupedResults = Union["OrderedDict[str, GroupedResults]", list[ValidationResult]]

# Leaf items after possible truncation
LeafItem = Union[ValidationResult, TruncationNotice]
TruncatedResults = Union["OrderedDict[str, TruncatedResults]", list[LeafItem]]


def _group_results(
    results: list[ValidationResult],
    levels: tuple[str, ...],
) -> GroupedResults:
    """Group results recursively by the given hierarchy of grouping levels.

    Returns a nested OrderedDict with leaf values as lists of ValidationResult.
    With zero levels, returns the flat list unchanged.
    """
    if not levels:
        return results
    key_fn = levels[0]
    remaining = levels[1:]
    groups: OrderedDict[str, list[ValidationResult]] = OrderedDict()
    for r in results:
        k = _group_key(r, key_fn)
        groups.setdefault(k, []).append(r)
    if remaining:
        return OrderedDict((k, _group_results(v, remaining)) for k, v in groups.items())
    # mypy can't resolve the recursive type alias, but this is correct:
    # OrderedDict[str, list[VR]] is a valid GroupedResults
    return cast("GroupedResults", groups)


def _truncate_leaves(
    grouped: GroupedResults | TruncatedResults, max_per_group: int
) -> TruncatedResults:
    """Truncate leaf lists to *max_per_group* items, appending a TruncationNotice."""
    if isinstance(grouped, list):
        if len(grouped) > max_per_group:
            kept: list[LeafItem] = list(grouped[:max_per_group])
            kept.append(TruncationNotice(len(grouped) - max_per_group))
            return kept
        return cast("TruncatedResults", grouped)
    return OrderedDict(
        (k, _truncate_leaves(v, max_per_group)) for k, v in grouped.items()
    )


def _serialize_grouped(grouped: GroupedResults | TruncatedResults) -> dict | list:
    """Convert grouped results to a JSON-serializable nested dict/list."""
    if isinstance(grouped, list):
        result: list[dict] = []
        for item in grouped:
            if isinstance(item, TruncationNotice):
                result.append({"_truncated": True, "omitted_count": item.omitted_count})
            else:
                result.append(item.model_dump(mode="json"))
        return result
    return {k: _serialize_grouped(v) for k, v in grouped.items()}


def _render_human(
    issues: list[ValidationResult],
    grouping: tuple[str, ...],
    max_per_group: int | None = None,
) -> None:
    """Render validation results in human-readable colored format."""
    if not grouping:
        shown = issues
        omitted = 0
        if max_per_group is not None and len(issues) > max_per_group:
            shown = issues[:max_per_group]
            omitted = len(issues) - max_per_group
        purviews = [i.purview for i in shown]
        display_errors(
            purviews,
            [i.id for i in shown],
            cast("list[Severity]", [i.severity for i in shown]),
            [i.message for i in shown],
        )
        if omitted:
            click.secho(f"... and {pluralize(omitted, 'more issue')}", fg="cyan")
    elif grouping == ("path",):
        # Legacy path grouping: de-duplicate purviews, show per-path
        purviews = list(set(i.purview for i in issues))
        for purview in purviews:
            applies_to = [i for i in issues if purview == i.purview]
            display_errors(
                [purview],
                [i.id for i in applies_to],
                cast("list[Severity]", [i.severity for i in applies_to]),
                [i.message for i in applies_to],
            )
    else:
        grouped: GroupedResults | TruncatedResults = _group_results(issues, grouping)
        if max_per_group is not None:
            grouped = _truncate_leaves(grouped, max_per_group)
        _render_human_grouped(grouped, depth=0)

    if not any(r.severity is not None and r.severity >= Severity.ERROR for r in issues):
        click.secho("No errors found.", fg="green")


def _count_leaves(grouped: GroupedResults | TruncatedResults) -> int:
    """Count total items in a grouped structure (including omitted counts)."""
    if isinstance(grouped, list):
        return sum(
            item.omitted_count if isinstance(item, TruncationNotice) else 1
            for item in grouped
        )
    return sum(_count_leaves(v) for v in grouped.values())


def _render_human_grouped(
    grouped: GroupedResults | TruncatedResults,
    depth: int,
) -> None:
    """Recursively render grouped results with nested indented section headers."""
    indent = "  " * depth
    if isinstance(grouped, list):
        # Leaf level: render individual issues
        for issue in grouped:
            if isinstance(issue, TruncationNotice):
                click.secho(
                    f"{indent}... and {pluralize(issue.omitted_count, 'more issue')}",
                    fg="cyan",
                )
                continue
            msg = f"{indent}[{issue.id}] {issue.purview} — {issue.message}"
            fg = _get_severity_color(
                [issue.severity] if issue.severity is not None else []
            )
            click.secho(msg, fg=fg)
    else:
        for key, value in grouped.items():
            count = _count_leaves(value)
            header = f"{indent}=== {key} ({pluralize(count, 'issue')}) ==="
            # Determine color from all issues in this group
            all_issues = _collect_all_issues(value)
            fg = _get_severity_color(
                cast(
                    "list[Severity]",
                    [i.severity for i in all_issues if i.severity is not None],
                )
            )
            click.secho(header, fg=fg, bold=True)
            _render_human_grouped(value, depth + 1)


def _collect_all_issues(
    grouped: GroupedResults | TruncatedResults,
) -> list[ValidationResult]:
    """Flatten a grouped structure into a list of all ValidationResults."""
    if isinstance(grouped, list):
        return [item for item in grouped if isinstance(item, ValidationResult)]
    result: list[ValidationResult] = []
    for v in grouped.values():
        result.extend(_collect_all_issues(v))
    return result


def _process_issues(
    issues: list[ValidationResult],
    grouping: str | tuple[str, ...],
) -> None:
    """Legacy wrapper: render human output and exit if errors."""
    if isinstance(grouping, str):
        grouping = (grouping,) if grouping != "none" else ()
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
