# This file provides definitions to do BIDS validation through the deno-compiled BIDS
# validator, https://pypi.org/project/bids-validator-deno/.

from functools import cache
import re
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired, run
from typing import Any

from pydantic import DirectoryPath, RootModel, validate_call

CMD = "bids-validator-deno"
TIMEOUT = 600.0  # 10 minutes, in seconds

# ANSI SGR (Select Graphic Rendition) pattern
_ANSI_SGR_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


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


class BidsValidationResult(RootModel):
    root: dict[str, Any]


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
    """
    result = _invoke_validator(["--json", str(dir_)])

    # The condition of this statement may need to change in the future.
    # See https://github.com/bids-standard/bids-validator/issues/191 for details
    if result.returncode not in range(0, 2) or result.stderr != "":
        raise RuntimeError(
            f"Execution of `{' '.join(result.args)}` failed.\n"
            f"Exit code: {result.returncode}\n"
            f"stdout:\n {result.stdout}\n"
            f"stderr:\n {result.stderr}\n"
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
    """
    result = _invoke_validator(["--version"])

    try:
        result.check_returncode()
    except CalledProcessError as e:
        raise RuntimeError(
            f"Execution of the `{' '.join(e.cmd)}` command failed: "
            f"exit code {e.returncode}"
        ) from e

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
