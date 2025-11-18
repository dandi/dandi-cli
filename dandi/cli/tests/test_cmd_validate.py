from pathlib import Path

from click.testing import CliRunner
import pytest
import pytest_mock

from ..cmd_validate import _process_issues, validate
from ...tests.xfail import mark_xfail_windows_python313_posixsubprocess
from ...validate_types import (
    Origin,
    OriginType,
    Scope,
    Severity,
    ValidationResult,
    Validator,
)


@pytest.mark.parametrize(
    "ds_name, expected_err_location",
    [
        ("invalid_asl003", "sub-Sub1/perf/sub-Sub1_headshape.jpg"),
        ("invalid_pet001", "sub-01/ses-01/anat/sub-02_ses-01_T1w.json"),
    ],
)
def test_validate_bids_error(
    ds_name: str,
    expected_err_location: str,
    bids_error_examples: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test validating a selection of datasets at
        https://github.com/bids-standard/bids-error-examples
    """
    from dandi.files import bids
    from dandi.tests.test_bids_validator_deno.test_validator import mock_bids_validate

    monkeypatch.setattr(bids, "bids_validate", mock_bids_validate)

    broken_dataset = bids_error_examples / ds_name

    r = CliRunner().invoke(validate, ["--min-severity", "ERROR", str(broken_dataset)])

    # Assert there are errors
    assert r.exit_code == 1

    # Assert that there is at least one error from the expected location
    assert str(Path(expected_err_location)) in r.output


def test_validate_severity(organized_nwb_dir3: Path) -> None:
    """
    Can we specify a severity floor?
    """
    r = CliRunner().invoke(
        validate, ["--grouping=path", "--min-severity=ERROR", str(organized_nwb_dir3)]
    )
    # Is the usage correct?
    assert r.exit_code == 0
    # Is the WARNING-level issue reporting suppressed?
    assert "NWBI.check_data_orientation" not in r.output


def test_validate_nwb_error(simple3_nwb: Path) -> None:
    """Do we fail on critical NWB validation errors?"""
    r = CliRunner().invoke(validate, [str(simple3_nwb)])
    # does it fail? as per:
    # https://github.com/dandi/dandi-cli/pull/1157#issuecomment-1312546812
    assert r.exit_code != 0


def test_validate_ignore(simple2_nwb: Path) -> None:
    r = CliRunner().invoke(validate, [str(simple2_nwb)])
    assert r.exit_code != 0
    assert "DANDI.NO_DANDISET_FOUND" in r.output
    r = CliRunner().invoke(validate, ["--ignore=NO_DANDISET_FOUND", str(simple2_nwb)])
    assert r.exit_code == 0, r.output
    assert "DANDI.NO_DANDISET_FOUND" not in r.output


@mark_xfail_windows_python313_posixsubprocess
def test_validate_nwb_path_grouping(organized_nwb_dir4: Path) -> None:
    """
    Does grouping of issues by path work?
    """
    r = CliRunner().invoke(validate, ["--grouping=path", str(organized_nwb_dir4)])
    assert r.exit_code == 0

    # Do paths with issues appear only once?
    assert r.output.count("sub-mouse004.nwb") == 1
    assert r.output.count("sub-mouse001.nwb") == 1

    # Do issues affecting multiple paths get listed multiple times?
    assert r.output.count("NWBI.check_data_orientation") >= 2


def test_process_issues(capsys):
    origin_validation_nwbinspector = Origin(
        type=OriginType.VALIDATION,
        validator=Validator.nwbinspector,
        validator_version="",
    )

    issues = [
        ValidationResult(
            id="NWBI.check_data_orientation",
            origin=origin_validation_nwbinspector,
            scope=Scope.FILE,
            message="Data may be in the wrong orientation.",
            path=Path("dir0/sub-mouse004/sub-mouse004.nwb"),
            severity=Severity.WARNING,
        ),
        ValidationResult(
            id="NWBI.check_data_orientation",
            origin=origin_validation_nwbinspector,
            scope=Scope.FILE,
            message="Data may be in the wrong orientation.",
            path=Path("dir1/sub-mouse001/sub-mouse001.nwb"),
            severity=Severity.WARNING,
        ),
        ValidationResult(
            id="NWBI.check_missing_unit",
            origin=origin_validation_nwbinspector,
            scope=Scope.FILE,
            message="Missing text for attribute 'unit'.",
            path=Path("dir1/sub-mouse001/sub-mouse001.nwb"),
            severity=Severity.WARNING,
        ),
    ]
    _process_issues(issues, grouping="path")
    captured = capsys.readouterr().out

    # Do paths with issues appear only once?
    assert captured.count("sub-mouse004.nwb") == 1
    assert captured.count("sub-mouse001.nwb") == 1

    # Do issues affecting multiple paths get listed multiple times?
    assert captured.count("NWBI.check_data_orientation") >= 2


def test_validate_bids_error_grouping_notification(
    bids_error_examples: Path, dataset: str = "invalid_asl003"
) -> None:
    """Test user notification for unimplemented parameter value."""
    broken_dataset = bids_error_examples / dataset
    r = CliRunner().invoke(validate, ["--grouping=error", str(broken_dataset)])
    # Does it break?
    assert r.exit_code == 2
    # Does it notify the user correctly?
    notification_substring = "Invalid value for '--grouping'"
    assert notification_substring in r.output


class TestValidateMatchOption:
    """Test the --match option for filtering validation results."""

    @staticmethod
    def _mock_validate(*paths, **kwargs):
        """Mock validation function that returns controlled ValidationResult objects."""
        origin = Origin(
            type=OriginType.VALIDATION,
            validator=Validator.dandi,
            validator_version="test",
        )

        # Return a set of validation results with different IDs
        results = [
            ValidationResult(
                id="BIDS.DATATYPE_MISMATCH",
                origin=origin,
                severity=Severity.ERROR,
                scope=Scope.FILE,
                message="Datatype mismatch error",
                path=Path(paths[0]) / "file1.nii",
            ),
            ValidationResult(
                id="BIDS.EXTENSION_MISMATCH",
                origin=origin,
                severity=Severity.ERROR,
                scope=Scope.FILE,
                message="Extension mismatch error",
                path=Path(paths[0]) / "file2.jpg",
            ),
            ValidationResult(
                id="DANDI.NO_DANDISET_FOUND",
                origin=origin,
                severity=Severity.ERROR,
                scope=Scope.DANDISET,
                message="No dandiset found",
                path=Path(paths[0]),
            ),
            ValidationResult(
                id="NWBI.check_data_orientation",
                origin=origin,
                severity=Severity.WARNING,
                scope=Scope.FILE,
                message="Data orientation warning",
                path=Path(paths[0]) / "file3.nwb",
            ),
        ]
        return iter(results)

    @pytest.mark.parametrize(
        "match_patterns,parsed_patterns,should_contain,should_not_contain",
        [
            # Single pattern matching specific validation ID
            (
                r"BIDS\.DATATYPE_MISMATCH",
                [r"BIDS\.DATATYPE_MISMATCH"],
                ["BIDS.DATATYPE_MISMATCH"],
                [
                    "BIDS.EXTENSION_MISMATCH",
                    "DANDI.NO_DANDISET_FOUND",
                    "NWBI.check_data_orientation",
                ],
            ),
            # Single pattern matching by prefix
            (
                r"^BIDS\.",
                [r"^BIDS\."],
                ["BIDS.DATATYPE_MISMATCH", "BIDS.EXTENSION_MISMATCH"],
                ["DANDI.NO_DANDISET_FOUND", "NWBI.check_data_orientation"],
            ),
            # Single pattern that matches nothing (should show "No errors found")
            (
                r"NONEXISTENT_ID",
                [r"NONEXISTENT_ID"],
                ["No errors found"],
                ["BIDS", "DANDI", "NWBI"],
            ),
            # Multiple patterns separated by comma
            (
                r"BIDS\.DATATYPE_MISMATCH,BIDS\.EXTENSION_MISMATCH",
                [r"BIDS\.DATATYPE_MISMATCH", r"BIDS\.EXTENSION_MISMATCH"],
                ["BIDS.DATATYPE_MISMATCH", "BIDS.EXTENSION_MISMATCH"],
                ["DANDI.NO_DANDISET_FOUND", "NWBI.check_data_orientation"],
            ),
            # Multiple patterns with wildcard
            (
                r"BIDS\.\S+,DANDI\.\S+",
                [r"BIDS\.\S+", r"DANDI\.\S+"],
                [
                    "BIDS.DATATYPE_MISMATCH",
                    "BIDS.EXTENSION_MISMATCH",
                    "DANDI.NO_DANDISET_FOUND",
                ],
                ["NWBI"],
            ),
        ],
    )
    def test_match_patterns(
        self,
        tmp_path: Path,
        match_patterns: str,
        parsed_patterns: list[str],
        should_contain: list[str],
        should_not_contain: list[str],
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """Test --match option with single or multiple comma-separated patterns."""
        from .. import cmd_validate

        # Use to monitor what compiled patterns are passed by the CLI
        process_issues_spy = mocker.spy(cmd_validate, "_process_issues")

        monkeypatch.setattr(cmd_validate, "validate_", self._mock_validate)

        r = CliRunner().invoke(validate, [f"--match={match_patterns}", str(tmp_path)])

        process_issues_spy.assert_called_once()
        call_args = process_issues_spy.call_args

        # Ensure the patterns are parsed and passed correctly
        passed_patterns = call_args.kwargs.get(
            "match", call_args.args[3] if len(call_args.args) > 3 else None
        )
        assert (
            passed_patterns is not None
        ), "No match patterns were passed to _process_issues"
        # We don't really care about the order of the patterns
        assert {p.pattern for p in passed_patterns} == set(parsed_patterns)

        for text in should_contain:
            assert text in r.output, f"Expected '{text}' in output but not found"

        for text in should_not_contain:
            assert text not in r.output, f"Expected '{text}' NOT in output but found"

    def test_match_invalid_regex(self, tmp_path: Path) -> None:
        """Test --match option with invalid regex pattern."""
        # Invalid regex pattern with unmatched parenthesis
        r = CliRunner(mix_stderr=False).invoke(
            validate, [r"--match=(INVALID", str(tmp_path)], catch_exceptions=False
        )

        # Should fail with an error about invalid regex
        assert r.exit_code != 0
        assert "error" in r.stderr.lower() and "--match" in r.stderr

    def test_match_with_ignore_combination(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test --match and --ignore options used together."""
        from .. import cmd_validate

        monkeypatch.setattr(cmd_validate, "validate_", self._mock_validate)

        # Then use both match and ignore
        r = CliRunner().invoke(
            validate,
            [
                r"--match=BIDS\.DATATYPE_MISMATCH",
                r"--ignore=DATATYPE_MISMATCH",
                str(tmp_path),
            ],
        )

        assert "BIDS.DATATYPE_MISMATCH" not in r.output
        assert "No errors found" in r.output
