# This file provides definitions to do BIDS validation through the deno-compiled BIDS
# validator, https://pypi.org/project/bids-validator-deno/.

from importlib.metadata import version
import json
from pathlib import Path
import re
from subprocess import CompletedProcess, TimeoutExpired, run
from tempfile import TemporaryDirectory
from typing import Optional

from packaging.version import parse as parse_ver_str
from pydantic import DirectoryPath, validate_call

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

from ._models import BidsValidationResult, Issue
from ._models import Severity as BidsSeverity

DISTRIBUTION_NAME = CMD = "bids-validator-deno"
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

    def __init__(
        self,
        cmd: list[str],
        returncode: int,
        stdout: str,
        stderr: str,
        outfile_content: Optional[str] = None,
    ):
        """
        Parameters
        ----------
        cmd : list[str]
            The command that was executed as the execution of BIDS validator
        returncode : int
            The return code of the execution
        stdout : str
            The standard output of the execution
        stderr : str
            The standard error of the execution
        outfile_content : Optional[str]
            The content of the output file produced by the execution
            (if any). This is `None` if the output file was not produced.
        """
        # Pass a human-readable message up to the base Exception
        super().__init__("Execution of the deno-compiled BIDS validator failed")
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.outfile_content = outfile_content

    def __str__(self):
        base_msg = super().__str__()  # the message passed in __init__
        return (
            f"{base_msg}\n"
            f"Command: `{' '.join(self.cmd)}`\n"
            f"Return code: {self.returncode}\n"
            f"Stdout:\n{self.stdout}\n"
            f"Stderr:\n{self.stderr}"
            + (
                f"\nOutfile content:\n{self.outfile_content}"
                if self.outfile_content is not None
                else ""
            )
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


def bids_validate(
    dir_: DirectoryPath,
    config: Optional[dict] = None,
    ignore_nifti_headers: bool = False,
    recursive: bool = False,
) -> list[ValidationResult]:
    """
    Validate a file directory as a BIDS dataset with the deno-compiled BIDS validator

    Parameters
    ----------
    dir_ : DirectoryPath
        The path to the directory to validate
    config : Optional[dict]
        The configuration to use in the validation. This specifies a JSON configuration
        file to be provided through the `--config` option when invoking the underlying
        deno-compiled BIDS validator. If `None`, the deno-compiled BIDS validator will
        be invoked without the `--config` option.
    ignore_nifti_headers : bool
        If `True`, disregard NIfTI header content during validation
    recursive : bool
        If `True`, validate datasets found in derivatives directories in addition to
        root dataset

    Returns
    -------
    list[ValidationResult]
        A list of `ValidationResult` objects in which each object represents an issue
        in the validation result produced by the deno-compiled BIDS validator
    """

    try:
        bv_result = _bids_validate(dir_, config, ignore_nifti_headers, recursive)
    except ValidatorError as e:
        return [
            ValidationResult(
                id="BIDS.VALIDATOR_ERROR",
                origin=(
                    Origin(
                        type=OriginType.INTERNAL,
                        validator=Validator.bids_validator_deno,
                        validator_version=get_version(),
                    )
                ),
                scope=Scope.DATASET,
                origin_result=e,
                dandiset_path=find_parent_directory_containing("dandiset.yaml", dir_),
                dataset_path=dir_,
                message="Deno-compiled BIDS validator failed in execution",
                path=dir_,
            )
        ]

    return _harmonize(bv_result, dir_)


@validate_call
def _bids_validate(
    dir_: DirectoryPath,
    config: Optional[dict] = None,
    ignore_nifti_headers: bool = False,
    recursive: bool = False,
) -> BidsValidationResult:
    """
    Validate a file directory as a BIDS dataset with the deno-compiled BIDS validator

    Parameters
    ----------
    dir_ : DirectoryPath
        The path to the directory to validate
    config : Optional[dict]
        The configuration to use in the validation. This specifies a JSON configuration
        file to be provided through the `--config` option when invoking the underlying
        deno-compiled BIDS validator. If `None`, the deno-compiled BIDS validator will
        be invoked without the `--config` option.
    ignore_nifti_headers : bool
        If `True`, disregard NIfTI header content during validation
    recursive : bool
        If `True`, validate datasets found in derivatives directories in addition to
        root dataset

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
    pydantic.ValidationError
        If any of the parameters can't be validated by Pydantic according to their type
        annotation. E.g., If `dir_` is not pointing to a valid directory or not provided
        at all
    """
    config_fname = "config.json"
    out_fname = "out.json"

    # Conditional options
    conditional_ops = []

    if ignore_nifti_headers:
        conditional_ops.append("--ignoreNiftiHeaders")
    if recursive:
        conditional_ops.append("--recursive")

    with TemporaryDirectory() as tmp_dir:
        if config is not None:
            # Write the config to a file in the temporary directory
            configfile_path = Path(tmp_dir) / config_fname
            configfile_path.write_text(json.dumps(config))

            # Add the `--config` option
            conditional_ops.extend(["--config", str(configfile_path)])

        outfile_path = Path(tmp_dir) / out_fname
        result = _invoke_validator(
            ["--json", "--outfile", str(outfile_path), *conditional_ops, str(dir_)]
        )
        # Read the validation result from the outfile if it exists
        outfile_content = outfile_path.read_text() if outfile_path.exists() else None

    if parse_ver_str(get_version()) <= parse_ver_str("2.0.5"):
        validator_error_occurred = (
            result.returncode not in range(0, 2) or result.stderr != ""
        )
    else:
        # Since version 2.0.6, the BIDS validator uses exit code 16 to indicate failures
        # due to validation errors. The second part of the `or` expression is retained
        # mostly as a defensive measure. For more details about the use of the 16
        # exit code, see https://github.com/bids-standard/bids-validator/pull/196.
        validator_error_occurred = (
            result.returncode not in [0, 16] or result.stderr != ""
        )

    if validator_error_occurred:
        raise ValidatorError(
            result.args,
            result.returncode,
            result.stdout,
            result.stderr,
            outfile_content,
        )

    assert (
        outfile_content is not None
    ), "`outfile_content` should not be None when validation is successful"

    # Parse the content, in JSON format, of the outfile
    return BidsValidationResult.model_validate_json(outfile_content, strict=True)


def get_version() -> str:
    """
    Return the version of the deno-compiled BIDS validator

    Returns
    -------
    str
        The version of the deno-compiled BIDS validator
    """
    return version(DISTRIBUTION_NAME)


def _harmonize(
    bv_result: BidsValidationResult, ds_path: Path
) -> list[ValidationResult]:
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
        # `BIDSVersion` is unavailable through the BIDS validator; see
        #   https://github.com/bids-standard/bids-validator/issues/10#issuecomment-2848121538
        #   for details
        # standard_version=<BIDS Version>,
        standard_schema_version=schema_version,
    )

    results: list[ValidationResult] = []
    for issue in issues:
        severity = issue.severity
        if severity is BidsSeverity.ignore:
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
                # Store only the issue, not entire bv_result with more context
                origin_result=issue,
                severity=_SEVERITY_MAP[severity] if severity else None,
                dandiset_path=dandiset_path,
                dataset_path=ds_path,
                message=_get_msg(issue, code_messages),
                path=issue_path,
            )
        )

    return results


def _get_scope(issue_path: Optional[Path]) -> Scope:
    """
    Return the scope of the issue

    Parameters
    ----------
    issue_path : Optional[Path]
        The path to the file or directory that the issue is related to. `None` if there
        is no a file or directory is related to the issue.

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


def _get_msg(issue: Issue, code_messages: dict[str, str]) -> Optional[str]:
    """
    Produce a human-readable message from an issue in a validation result produced by
    the deno-compiled BIDS validator.

    Parameters
    ----------
    issue : Issue
        The issue to produce a message from
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


def _get_path(issue: Issue, ds_path: Path) -> Optional[Path]:
    """
    Given an issue from the validation result of the deno-compiled BIDS validator,
    produce the absolute path to the file or directory that the issue is related to.

    Parameters
    ----------
    issue : Issue
        The issue to produce a path for
    ds_path : Path
        The path to the dataset that has been validated to produce the validation result

    Returns
    -------
    Optional[Path]
        The absolute path to the file or directory that the issue is related to
        or `None` there is no file or directory that the issue is related to
    """
    if issue.location is None:
        return None

    # Ensure the path is absolute and in canonical form
    ds_path = ds_path.resolve()

    return ds_path.joinpath(issue.location.lstrip("/"))
