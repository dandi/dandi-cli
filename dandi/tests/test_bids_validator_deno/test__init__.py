from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from typing import Optional
from unittest.mock import ANY, patch

import pytest

# Adjust the import as needed for your package structure
# noinspection PyProtectedMember
from dandi.bids_validator_deno import (
    CMD,
    TIMEOUT,
    ValidatorError,
    _bids_validate,
    _get_msg,
    _get_path,
    _get_scope,
    _invoke_validator,
    bids_validate,
    get_version,
    strip_sgr,
)
from dandi.bids_validator_deno.models import (
    BidsValidationResult,
    DatasetIssues,
    Issue,
    SummaryOutput,
)
from dandi.tests.fixtures import BIDS_ERROR_TESTDATA_SELECTION, BIDS_TESTDATA_SELECTION
from dandi.validate_types import OriginType, Scope, ValidationResult, Validator


@pytest.mark.parametrize(
    "outfile_content, expected_outfile_content_rep",
    [
        (None, ""),
        ("", "\nOutfile content:\n"),
        ("Some content", "\nOutfile content:\nSome content"),
    ],
)
def test_validator_error(
    outfile_content: Optional[str], expected_outfile_content_rep: str
) -> None:
    """
    Test the ValidatorError exception class.
    """
    cmd = ["bids-validator-deno", "--json"]
    returncode = 1
    stdout = "Some output"
    stderr = "Some error"

    error = ValidatorError(cmd, returncode, stdout, stderr, outfile_content)

    assert error.cmd == cmd
    assert error.returncode == returncode
    assert error.stdout == stdout
    assert error.stderr == stderr
    assert error.outfile_content == outfile_content

    # Check the string representation
    expected_str = (
        "Execution of the deno-compiled BIDS validator failed\n"
        f"Command: `bids-validator-deno --json`\n"
        f"Return code: {returncode}\n"
        f"Stdout:\n{stdout}\n"
        f"Stderr:\n{stderr}"
    ) + expected_outfile_content_rep
    assert str(error) == expected_str


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
def test_strip_sgr(text: str, expected_output: str) -> None:
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
    ) -> None:
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
    def test_empty_dir(self, tmp_path):
        """
        Test validating an empty directory. The validator should return validation
        results representing validation errors.
        """
        results = bids_validate(tmp_path)
        assert type(results) is list
        assert len(results) > 0
        assert all(isinstance(result, ValidationResult) for result in results)

    def test_validator_success(self, tmp_path):
        """
        Test the case where the deno-compiled BIDS validator succeeds in execution
        """
        with patch("dandi.bids_validator_deno._bids_validate") as mock_validate:
            mock_validate.return_value = BidsValidationResult(
                issues=DatasetIssues(
                    issues=[Issue(code="code1")], codeMessages={"code1": "message1"}
                ),
                summary=SummaryOutput(
                    sessions=[],
                    subjects=[],
                    subjectMetadata=[],
                    tasks=[],
                    modalities=[],
                    secondaryModalities=[],
                    totalFiles=0,
                    size=0,
                    dataProcessed=False,
                    pet={},
                    dataTypes=[],
                    schemaVersion="1.0.0",
                ),
            )
            results = bids_validate(tmp_path)

        assert len(results) == 1  # Corresponding only one issue

        result = results[0]
        assert result.id == "BIDS.code1"
        assert result.origin.type == OriginType.VALIDATION
        assert result.origin.validator == Validator.bids_validator_deno

    def test_validator_failure(self, tmp_path):
        """
        Test the case where the deno-compiled BIDS validator fails in execution, and
        the failure is not an indication of the presence of validation errors.
        """
        validator_error = ValidatorError(
            cmd=[CMD, "--json", str(tmp_path)],
            returncode=2,
            stdout="Some output",
            stderr="Some error",
            outfile_content="Some content",
        )
        with patch(
            "dandi.bids_validator_deno._bids_validate",
            side_effect=validator_error,
        ):
            results = bids_validate(tmp_path)

        assert len(results) == 1
        result = results[0]

        assert result.id == "BIDS.VALIDATOR_ERROR"
        assert result.origin.type == OriginType.INTERNAL
        assert result.origin.validator == Validator.bids_validator_deno
        assert result.scope == Scope.DATASET
        assert result.origin_result is validator_error
        assert result.dandiset_path is None
        assert result.dataset_path == tmp_path
        assert result.message == "Deno-compiled BIDS validator failed in execution"
        assert result.path == tmp_path


# noinspection PyPep8Naming
class Test_BidsValidate:
    @pytest.mark.parametrize(
        "config, ignore_nifti_headers, recursive, expected_conditional_ops",
        [
            (None, False, False, []),
            (None, True, False, ["--ignoreNiftiHeaders"]),
            (None, False, True, ["--recursive"]),
            (None, True, True, ["--ignoreNiftiHeaders", "--recursive"]),
            (
                {
                    "ignore": [
                        {"code": "JSON_KEY_RECOMMENDED", "location": "/T1w.json"}
                    ],
                    "warning": [],
                    "error": [{"code": "NO_AUTHORS"}],
                },
                True,
                True,
                ["--ignoreNiftiHeaders", "--recursive", "--config", ANY],
            ),
        ],
    )
    def test_invoke_validator_args(
        self,
        config: Optional[dict],
        ignore_nifti_headers: bool,
        recursive: bool,
        expected_conditional_ops: list[str],
        tmp_path: Path,
    ) -> None:
        """
        Spy on the `_invoke_validator()` call inside `_bids_validate()` and verify
        the arguments passed
        """

        # `ANY` is used as the third argument because we only know that the argument
        # ends with "out.json" but not the full path.
        expected_args = (
            ["--json", "--outfile", ANY] + expected_conditional_ops + [str(tmp_path)]
        )

        with patch(
            "dandi.bids_validator_deno._invoke_validator",
            wraps=_invoke_validator,  # <--- "Spy" on the original function
        ) as mock_invoke:

            _bids_validate(
                dir_=tmp_path,
                config=config,
                ignore_nifti_headers=ignore_nifti_headers,
                recursive=recursive,
            )

        # Ensure _invoke_validator was called at exactly once
        mock_invoke.assert_called_once()

        # The real call arguments are in mock_invoke.call_args
        # e.g., ( (args,), {} )
        actual_args = mock_invoke.call_args.args[0]

        assert actual_args == expected_args

        # Check that the third argument ends with "out.json"
        assert actual_args[2].endswith("out.json")

        if config is not None:
            # Ensure the second to the last argument is the path to the config file
            assert actual_args[-2].endswith("config.json")

    def test_validate_empty_dir(self, tmp_path):
        """
        Test the case where an empty directory is validated
        """
        result = _bids_validate(tmp_path)
        assert isinstance(result, BidsValidationResult)

    @pytest.mark.parametrize("ds_name", BIDS_TESTDATA_SELECTION)
    def test_validate_bids_examples(self, ds_name: str, bids_examples: Path) -> None:
        """
        Test validating a selection of datasets at
            https://github.com/bids-standard/bids-examples
        """
        ds_path = bids_examples / ds_name
        result = _bids_validate(ds_path)
        assert isinstance(result, BidsValidationResult)

    @pytest.mark.parametrize("ds_name", BIDS_ERROR_TESTDATA_SELECTION)
    def test_validate_bids_error_examples(
        self, ds_name: str, bids_error_examples: Path
    ) -> None:
        ds_path = bids_error_examples / ds_name
        result = _bids_validate(ds_path)
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
        the input directory being an invalid BIDS dataset but due to some other error
        in the execution of the validator.
        """
        cmd = [CMD, "--json", str(tmp_path)]
        with patch("dandi.bids_validator_deno._invoke_validator") as mock_invoke:
            # Simulate a CompletedProcess
            mock_invoke.return_value = CompletedProcess(
                args=cmd,
                returncode=exit_code,
                stdout=stdout,
                stderr=stderr,
            )
            # We expect a `ValidatorError`
            with pytest.raises(ValidatorError) as excinfo:
                _bids_validate(tmp_path)

            e = excinfo.value

            assert e.cmd == cmd
            assert e.returncode == exit_code
            assert e.stdout == stdout
            assert e.stderr == stderr


def test_get_version():
    """
    Test the `get_version()` function
    """
    version = get_version()
    assert "." in version


@pytest.fixture
def folder_path(tmp_path: Path) -> Path:
    folder = tmp_path / "test_folder"
    folder.mkdir()
    return folder


@pytest.fixture
def file_path(tmp_path: Path) -> Path:
    file = tmp_path / "test_file.txt"
    file.touch()
    return file


@pytest.fixture
def symlink_path(tmp_path: Path, file_path: Path) -> Path:
    symlink = tmp_path / "test_symlink"
    symlink.symlink_to(file_path)
    return symlink


@pytest.fixture
def non_existent_path(tmp_path: Path) -> Path:
    non_existent = tmp_path / "non_existent_file.txt"
    return non_existent


@pytest.mark.parametrize(
    "path_fixture, expected_scope",
    [
        (None, Scope.DATASET),  # Passing None => `_get_scope(None)` => DATASET
        ("file_path", Scope.FILE),  # File => FILE
        ("symlink_path", Scope.FILE),  # Symlink => FILE
        ("folder_path", Scope.FOLDER),  # Folder => FOLDER
        ("non_existent_path", Scope.DATASET),  # Non-existent path => DATASET
    ],
)
def test_get_scope(path_fixture, expected_scope, request):
    """
    Test the `_get_scope()` function
    """
    if path_fixture is None:
        issue_path = None
    else:
        issue_path = request.getfixturevalue(path_fixture)

    result = _get_scope(issue_path)
    assert result == expected_scope


@pytest.mark.parametrize(
    "issue_code, issue_sub_code, issue_issue_message, code_messages, expected_result",
    [
        ("code1", None, None, {}, None),
        ("code1", None, None, {"code1": "message1"}, "message1"),
        (
            "code1",
            "sub code 1",
            None,
            {"code1": "message1"},
            "message1\nsubCode: sub code 1",
        ),
        (
            "code1",
            "sub code 1",
            "issue msg 1",
            {"code1": "message1"},
            "message1\nsubCode: sub code 1\nissueMessage: issue msg 1",
        ),
        (
            "code1",
            None,
            "issue msg 1",
            {"code1": "message1"},
            "message1\nissueMessage: issue msg 1",
        ),
        (
            "code1",
            "sub code 1",
            "issue msg 1",
            {"code2": "message2"},
            "subCode: sub code 1\nissueMessage: issue msg 1",
        ),
        (
            "code1",
            None,
            "issue msg 1",
            {"code2": "message2"},
            "issueMessage: issue msg 1",
        ),
    ],
)
def test_get_msg(
    issue_code: str,
    issue_sub_code: Optional[str],
    issue_issue_message: Optional[str],
    code_messages: dict[str, str],
    expected_result: Optional[str],
) -> None:
    """
    Test the `_get_msg()` function
    """
    issue = Issue(
        code=issue_code,
        subCode=issue_sub_code,
        issueMessage=issue_issue_message,
    )

    result = _get_msg(issue, code_messages)

    assert result == expected_result


@pytest.mark.parametrize(
    "issue_location, expected_tail",
    [
        (None, None),
        ("a/b/c", "a/b/c"),
        ("/a/b/c", "a/b/c"),
        ("///a/b/c", "a/b/c"),
        ("/a/b/c.json", "a/b/c.json"),
    ],
)
def test_get_path(
    issue_location: Optional[str], expected_tail: Optional[str], tmp_path: Path
) -> None:
    """
    Test the `_get_path()` function

    Parameters:
    issue_location: str or None
        The value of the `location` attribute of the `Issue` object.
    expected_tail: str or None
        The expected tail of the resulting path, the portion of the path that extends
        after the dataset path. `None` means `None` is expected to be the result.
    """
    ds_path = tmp_path

    issue = Issue(code="DUMMY", location=issue_location)

    result = _get_path(issue, ds_path)

    if expected_tail is not None:
        assert result == ds_path.resolve().joinpath(expected_tail)
    else:
        assert result is None
