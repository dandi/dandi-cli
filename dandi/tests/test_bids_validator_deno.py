from subprocess import CompletedProcess, TimeoutExpired
from typing import Optional
from unittest.mock import patch

import pytest

# Adjust the import as needed for your package structure
from dandi.bids_validator_deno import (
    CMD,
    TIMEOUT,
    BidsValidationResult,
    _invoke_validator,
    bids_validate,
    get_version,
    strip_sgr,
)


@pytest.mark.parametrize(
    "text, expected_output",
    [
        (
            "\x1b[1mbids-validator\x1b[22m \x1b[94m2.0.4-dev\x1b[39m\n",
            "bids-validator 2.0.4-dev\n",
        ),
        (
            "\x1b[31mRed text\x1b[0m",
            "Red text",
        ),
        (
            "\x1b[1;32mBold, green text\x1b[0m",
            "Bold, green text",
        ),
        (
            "\x1b[1;4;35mBold, underlined, magenta text\x1b[0m",
            "Bold, underlined, magenta text",
        ),
        (
            "\x1b[93mBright yellow text\x1b[0m",
            "Bright yellow text",
        ),
    ],
)
def test_strip_sgr(text, expected_output: str):
    """
    Test the strip_sgr function to ensure it removes ANSI SGR sequences.
    """
    assert strip_sgr(text) == expected_output


class TestInvokeValidator:
    @pytest.mark.parametrize(
        # `None` as the value for `expected_in_stdout` or `expected_in_stderr` means
        # stdout or stderr are empty strings, respectively.
        "args, expected_returncode, expected_in_stdout, expected_in_stderr",
        [
            pytest.param(
                [],
                2,
                "--help",
                "Missing argument(s)",
                id="no option or argument",
            ),
            pytest.param(["--help"], 0, "--help", None, id="--help option"),
            pytest.param(
                ["--version"], 0, "bids-validator", None, id="--version option"
            ),
        ],
    )
    def test_real(
        self,
        args: list[str],
        expected_returncode: int,
        expected_in_stdout: Optional[str],
        expected_in_stderr: Optional[str],
    ):
        """
        Call the real bids-validator-deno command for given args.
        These tests validate the return code and partial output.
        """
        result = _invoke_validator(args)

        expected_args = [CMD, *args]
        assert result.args == expected_args

        assert result.returncode == expected_returncode

        if expected_in_stdout is not None:
            assert expected_in_stdout in result.stdout
        else:
            assert result.stdout == ""

        if expected_in_stderr is not None:
            assert expected_in_stderr in result.stderr
        else:
            assert result.stderr == ""

    def test_timeout(self):
        """
        Test that a TimeoutExpired from `subprocess.run` raises a RuntimeError.
        """
        with patch("dandi.bids_validator_deno.run") as mock_run:
            mock_run.side_effect = TimeoutExpired(cmd=[CMD], timeout=TIMEOUT)
            with pytest.raises(RuntimeError, match="timed out after"):
                _invoke_validator([])


class TestBidsValidate:
    def test_validate_empty_dir(self, tmp_path):
        """
        Test the case where an empty directory is validated
        """
        result = bids_validate(tmp_path)
        assert isinstance(result, BidsValidationResult)

    @pytest.mark.parametrize(
        "exit_code, stderr",
        [
            (-42, ""),
            (-1, ""),
            (2, ""),
            (2, "Some error"),
            (100, ""),
            (0, "Some other error"),
            (1, "Errr!"),
        ],
    )
    @pytest.mark.parametrize("stdout", ["", "Some output", "Some other output"])
    def test_execution_error(self, exit_code, stdout, stderr, tmp_path):
        """
        Test the cases where the deno-compiled BIDS validator fails not due to
        the input directory being invalid BIDS dataset but due to some other error
        in the execution of the validator.
        """
        with patch("dandi.bids_validator_deno._invoke_validator") as mock_invoke:
            # Simulate a CompletedProcess
            mock_invoke.return_value = CompletedProcess(
                args=[CMD, "--json", str(tmp_path)],
                returncode=exit_code,
                stdout=stdout,
                stderr=stderr,
            )
            # We expect a RuntimeError with a message about "exit code <exit_code>"
            with pytest.raises(
                RuntimeError,
                match=f"Execution of `{f'{CMD} --json {tmp_path}'}` failed.",
            ):
                bids_validate(tmp_path)


@pytest.fixture
def clear_get_version_cache():
    # Ensure the cache is cleared before each test run
    get_version.cache_clear()
    yield


@pytest.mark.usefixtures("clear_get_version_cache")
class TestGetVersion:
    def test_real(self):
        """
        Test fetching the version number from the real bids-validator-deno command
        """
        result = get_version()
        assert isinstance(result, str)
        assert result != ""

    @pytest.mark.parametrize("returncode", [1, -2, 127])
    def test_fail_exit_code(self, returncode):
        """
        Test the case where `bids-validator-deno --version` has a non-zero exit code
        """
        with patch("dandi.bids_validator_deno._invoke_validator") as mock_invoke:
            # Simulate a CompletedProcess with a non-zero return code
            mock_invoke.return_value = CompletedProcess(
                args=[CMD, "--version"],
                returncode=returncode,
                stdout="Some error",
                stderr="Some other error",
            )

            # We expect a RuntimeError with a message about "exit code <returncode>"
            with pytest.raises(RuntimeError, match=f"exit code {returncode}"):
                get_version()

    @pytest.mark.parametrize(
        "stdout_text, expected_version",
        [
            ("\x1b[1mbids-validator\x1b[22m \x1b[94m2.0.4-dev\x1b[39m\n", "2.0.4-dev"),
            (
                "\x1b[1m\t  bids-validator\x1b[22m \x1b[94m2.0.4-dev\x1b[39m\nhello",
                "2.0.4-dev",
            ),
            (
                "\x1b[1mbids-validator\x1b[22m \x1b[94m2.0.4-dev.g123\x1b[39m\n",
                "2.0.4-dev.g123",
            ),
        ],
    )
    def test_version_extraction(self, stdout_text, expected_version):
        """
        Test the case where a version number is extracted from the output
        of `bids-validator-deno --version` using an expected regex pattern.
        """
        with patch("dandi.bids_validator_deno._invoke_validator") as mock_invoke:
            mock_invoke.return_value = CompletedProcess(
                args=[CMD, "--version"],
                returncode=0,
                stdout=stdout_text,
                stderr="",
            )
            # The regex should match and extract the version
            version = get_version()
            assert version == expected_version

    @pytest.mark.parametrize(
        "stdout_text",
        [
            "",  # empty output
            "unknown 1.2.3",  # missing "bids-validator" prefix
            "bidsvalidator 1.2.3",  # missing dash in "bids-validator"
        ],
    )
    def test_failed_version_extraction(self, stdout_text):
        """
        Test the case where a version number can't be extracted from the output of
        `bids-validator-deno --version` using an expected regex pattern.
        """
        with patch("dandi.bids_validator_deno._invoke_validator") as mock_invoke:
            mock_invoke.return_value = CompletedProcess(
                args=[CMD, "--version"],
                returncode=0,
                stdout=stdout_text,
                stderr="",
            )
            # Because the regex doesn't match any of these stdout_text variants,
            # we expect a RuntimeError about failing to extract the version.
            with pytest.raises(RuntimeError, match="Failed to extract a version"):
                get_version()
