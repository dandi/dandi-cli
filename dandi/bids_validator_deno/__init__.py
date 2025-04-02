# This file provides definitions to do BIDS validation through the deno-compiled BIDS
# validator, https://pypi.org/project/bids-validator-deno/.

from functools import cache
import re
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired, run

from pydantic import DirectoryPath, validate_call

from dandi.bids_validator_deno.models import BidsValidationResult

CMD = "bids-validator-deno"
TIMEOUT = 600.0  # 10 minutes, in seconds

# ANSI SGR (Select Graphic Rendition) pattern
_ANSI_SGR_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


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
    return BidsValidationResult.model_validate_json(result.stdout)


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
