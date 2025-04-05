# This file provides definitions to do BIDS validation through the deno-compiled BIDS
# validator, https://pypi.org/project/bids-validator-deno/.

from functools import cache
from pathlib import Path
import re
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired, run
from typing import Optional

from pydantic import DirectoryPath, validate_call

from dandi.bids_validator_deno.models import BidsValidationResult, Issue
from dandi.bids_validator_deno.models import Severity as BidsSeverity
from dandi.utils import find_parent_directory_containing
from dandi.validate_types import (
    Origin,
    OriginType,
    Scope,
    Severity,
    Standard,
    ValidationResult,
    Validator,
)

CMD = "bids-validator-deno"
TIMEOUT = 600.0  # 10 minutes, in seconds

# ANSI SGR (Select Graphic Rendition) pattern
_ANSI_SGR_PATTERN = re.compile(r"\x1b\[[0-9;]*m")

# Map from BIDS validator severity levels to Dandi severity levels
# Note: BidsSeverity.ignore level is not mapped. Issues with this severity level will
#   be ignored in the harmonization process.
_SEVERITY_MAP = {
    BidsSeverity.warning: Severity.HINT,
    BidsSeverity.error: Severity.ERROR,
}


class ValidatorError(Exception):
    """
    Exception raised when the deno-compiled BIDS validator fails in execution,
    and the failure is not an indication of the presence of validation errors.
    """

    def __init__(self, cmd: list[str], returncode: int, stdout: str, stderr: str):
        # Pass a human-readable message up to the base Exception
        super().__init__("Execution of the deno-compiled BIDS validator failed")
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        base_msg = super().__str__()  # the message passed in __init__
        return (
            f"{base_msg}\n"
            f"Command: `{' '.join(self.cmd)}`\n"
            f"Return code: {self.returncode}\n"
            f"Stdout:\n{self.stdout}\n"
            f"Stderr:\n{self.stderr}"
        )


def strip_sgr(text: str) -> str:
    """
    Strip ANSI SGR (Select Graphic Rendition) sequences from a string.

    For example, this can be used to remove color encoding sequences from terminal
    outputs.
    """
    return _ANSI_SGR_PATTERN.sub("", text)


def _invoke_validator(args: list[str]) -> CompletedProcess:
    """
    Invoke the deno compiled BIDS validator

    Parameters
    ----------
    args : list[str]
        An ordered list of options and arguments to pass to the validator

    Returns
    -------
    CompletedProcess
        An object representing the result of invoking the deno-compiled BIDS validator

    Raises
    ------
    RuntimeError
        If the deno-compiled BIDS validator times out in `TIMEOUT` seconds

    Notes
    -----
    - The text captured in `stdout` and `stderr` can be color encoded
    """
    try:
        result = run(
            args=[CMD, *args],
            capture_output=True,
            timeout=TIMEOUT,
            text=True,
        )
    except TimeoutExpired as e:
        raise RuntimeError(
            f"The `{' '.join(e.cmd)}` command timed out after {e.timeout} " f"seconds"
        ) from e

    return result


@validate_call
def bids_validate(dir_: DirectoryPath) -> BidsValidationResult:
    """
    Validate a file directory as a BIDS dataset with the deno-compiled BIDS validator

    Parameters
    ----------
    dir_ : DirectoryPath
        The path to the directory to validate

    Returns
    -------
    BidsValidationResult
        The result of the validation using the deno-compiled BIDS validator with
        the `--json` option.

    Raises
    ------
    ValidatorError
        If the deno-compiled BIDS validator fails in execution, and the failure is
        not an indication of the presence of validation errors.
    """
    result = _invoke_validator(["--json", str(dir_)])

    # The condition of this statement may need to change in the future.
    # See https://github.com/bids-standard/bids-validator/issues/191 for details
    if result.returncode not in range(0, 2) or result.stderr != "":
        raise ValidatorError(
            result.args, result.returncode, result.stdout, result.stderr
        )

    # Parse the JSON output at stdout
    return BidsValidationResult.model_validate_json(result.stdout, strict=True)


@cache
def get_version() -> str:
    """
    Return the version of the deno-compiled BIDS validator

    Returns
    -------
    str
        The version of the deno-compiled BIDS validator

    Raises
    ------
    ValidatorError
        If the deno-compiled BIDS validator fails in execution, and the failure is
        not an indication of the presence of validation errors.
    RuntimeError
        If the version number cannot be extracted from the output of the
        `bids-validator-deno --version` command using the expected regex pattern
    """
    result = _invoke_validator(["--version"])

    try:
        result.check_returncode()
    except CalledProcessError as e:
        raise ValidatorError(e.cmd, e.returncode, e.stdout, e.stderr)

    # Get the version from the stdout
    pattern = r"bids-validator\s+(\S+)"
    match = re.search(pattern, strip_sgr(result.stdout))
    if match:
        version = match.group(1)
    else:
        raise RuntimeError(
            f"Failed to extract a version number from the stdout output of the "
            f"`{' '.join(result.args)}` command, {result.stdout!r}, using the expected "
            f"regex pattern, {pattern!r}"
        )

    return version


def harmonize(bv_result: BidsValidationResult, ds_path: Path) -> list[ValidationResult]:
    """
    Harmonize a `BidsValidationResult` object into a list of `ValidationResult` objects

    Parameters
    ----------
    bv_result : BidsValidationResult
        The `BidsValidationResult` object representing the result of the validation
        using the deno-compiled BIDS validator
    ds_path : Path
        The path to the dataset that has been validated to produce the `bv_result`
        object

    Returns
    -------
    list[ValidationResult]
        A list of `ValidationResult` objects in which each object represents an issue
        in the validation result.
    """
    # Ensure the path is absolute and in canonical form
    ds_path = ds_path.resolve()

    issues = bv_result.issues.issues
    code_messages = bv_result.issues.codeMessages
    schema_version = bv_result.summary.schemaVersion
    dandiset_path = find_parent_directory_containing("dandiset.yaml", ds_path)

    origin = Origin(
        type=OriginType.VALIDATION,
        validator=Validator.bids_validator_deno,
        validator_version=get_version(),
        standard=Standard.BIDS,
        # todo: the BIDSVersion is unavailable through the validator;
        #   However, the schema version is actually more precise
        standard_version=schema_version,
    )

    results: list[ValidationResult] = []
    for issue in issues:
        if issue.severity is BidsSeverity.ignore:
            # Ignore issues with severity "ignore"
            # TODO: If we want to include these issues, we will have to add a new value
            #   to the Severity enum.
            continue

        # The absolute path to the file or directory that the issue is related to
        issue_path = _get_path(issue, ds_path)

        results.append(
            ValidationResult(
                id=f"BIDS.{issue.code}",
                origin=origin,
                scope=_get_scope(issue_path),
                origin_result=issue,  # TODO: it may be more useful if set to `bv_result`
                severity=_SEVERITY_MAP.get(issue.severity),
                dandiset_path=dandiset_path,
                dataset_path=ds_path,
                message=_get_msg(issue, code_messages),
                # metadata, not sure if this can be done it is there is SubjectMetadata in summary
                path=issue_path,
            )
        )

    return results


# TODO: to be tested
def _get_scope(issue_path: Optional[Path]) -> Scope:
    """
    Return the scope of the issue

    Parameters
    ----------
    issue_path : Optional[Path]
        The path to the file or directory that the issue is related to. `None` if there
        is no such a file or directory.
    Returns
    -------
    Scope
        The scope of the issue. If `issue_path` is `None`, the scope is set to
        `Scope.DATASET`.
    """
    if issue_path is None:
        return Scope.DATASET

    if issue_path.is_file() or issue_path.is_symlink():
        return Scope.FILE
    if issue_path.is_dir():
        return Scope.FOLDER

    return Scope.DATASET


# todo: to be tested
def _get_msg(issue: Issue, code_messages: dict[str, str]) -> Optional[str]:
    """
    Given an issue from the validation result of the deno-compiled BIDS validator,
    produce a human-readable message.

    Parameters
    ----------
    issue : Issue
        The issue to produce a message for
    code_messages : dict[str, str]
        A dictionary mapping issue codes to human-readable messages given as part of
        the validation result
    Returns
    -------
    Optional[str]
        The human-readable message (or `None` if such a message can't be produced)
    """
    coded_msg = code_messages.get(issue.code, "")
    sub_code_msg = f"subCode: {issue.subCode}" if issue.subCode else ""
    issue_msg = f"issueMessage: {issue.issueMessage}" if issue.issueMessage else ""

    msg = "\n".join(filter(None, [coded_msg, sub_code_msg, issue_msg]))

    # Return `None` if a non-empty message cannot be produced
    return msg if msg else None


# todo: to be tested
def _get_path(issue: Issue, ds_path: Path) -> Optional[Path]:
    """
    Given an issue from the validation result of the deno-compiled BIDS validator,
    produce the absolute path to the file or directory that the issue is related to.

    Parameters
    ----------
    issue : Issue
        The issue to produce a path for
    ds_path : Path
        The path to the dataset that has been validated to produce the `issue`
    Returns
    -------
    Optional[Path]
        The absolute path to the file or directory that the issue is related to
        (or `None` if such a path can't be produced. E.g., there is no file or
        directory that the issue is related to.)
    """
    if issue.location is None:
        return None

    # Ensure the path is absolute and in canonical form
    ds_path = ds_path.resolve()

    return ds_path.joinpath(issue.location.lstrip("/"))
