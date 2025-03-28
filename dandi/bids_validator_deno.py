# This file provides definitions to do BIDS validation through the deno-compiled BIDS
# validator, https://pypi.org/project/bids-validator-deno/.

from functools import cache
import re
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired, run
from typing import Optional

from pydantic import DirectoryPath

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
            f"The deno-compiled BIDS validator, {e.cmd} timed out after {e.timeout} "
            f"seconds"
        ) from e

    return result


def bids_validate(dataset_dir: DirectoryPath) -> Optional[dict]:
    """"""
    # TODO: use the `--no-color` option to disable color output


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
            f"Execution of the deno-compiled BIDS validator with the --version option "
            f"failed: exit code {e.returncode}"
        ) from e

    # Get the version from the stdout
    pattern = r"bids-validator\s+(\S+)"
    match = re.search(pattern, strip_sgr(result.stdout))
    if match:
        version = match.group(1)
    else:
        raise RuntimeError(
            "Failed to extract the version of the deno-compiled BIDS validator from "
            f"stdout, {result.stdout!r}, using the expected regex pattern, {pattern!r},"
        )

    return version
