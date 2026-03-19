import json
from pathlib import Path

from click.testing import CliRunner
import pytest
import ruamel.yaml

from ..cmd_validate import _process_issues, validate
from ...tests.xfail import mark_xfail_windows_python313_posixsubprocess
from ...validate.types import (
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


@pytest.mark.ai_generated
def test_validate_format_json(simple2_nwb: Path) -> None:
    """Test --format json outputs a valid JSON array."""
    r = CliRunner().invoke(validate, ["-f", "json", str(simple2_nwb)])
    assert r.exit_code == 1  # NO_DANDISET_FOUND is an error
    data = json.loads(r.output)
    assert isinstance(data, list)
    assert len(data) >= 1
    # Check structure of first result
    rec = data[0]
    assert "id" in rec
    assert "origin" in rec
    assert "severity" in rec
    assert "record_version" in rec


@pytest.mark.ai_generated
def test_validate_format_json_lines(simple2_nwb: Path) -> None:
    """Test --format json_lines outputs one JSON object per line."""
    r = CliRunner().invoke(validate, ["-f", "json_lines", str(simple2_nwb)])
    assert r.exit_code == 1
    lines = [line for line in r.output.strip().split("\n") if line.strip()]
    assert len(lines) >= 1
    for line in lines:
        rec = json.loads(line)
        assert "id" in rec
        assert "severity" in rec
        assert "record_version" in rec


@pytest.mark.ai_generated
def test_validate_format_yaml(simple2_nwb: Path) -> None:
    """Test --format yaml outputs valid YAML."""
    r = CliRunner().invoke(validate, ["-f", "yaml", str(simple2_nwb)])
    assert r.exit_code == 1
    yaml = ruamel.yaml.YAML(typ="safe")
    data = yaml.load(r.output)
    assert isinstance(data, list)
    assert len(data) >= 1
    rec = data[0]
    assert "id" in rec
    assert "severity" in rec
    assert "record_version" in rec


@pytest.mark.ai_generated
def test_validate_format_no_errors_no_message(tmp_path: Path) -> None:
    """Structured formats should not emit 'No errors found.' text."""
    (tmp_path / "dandiset.yaml").write_text(
        "identifier: 12346\nname: Foo\ndescription: Dandiset Foo\n"
    )
    r = CliRunner().invoke(validate, ["-f", "json", str(tmp_path)])
    assert r.exit_code == 0
    assert "No errors found" not in r.output
    data = json.loads(r.output)
    assert data == []


@pytest.mark.ai_generated
def test_validate_output_file(simple2_nwb: Path, tmp_path: Path) -> None:
    """Test --output writes to file instead of stdout."""
    outfile = tmp_path / "results.jsonl"
    r = CliRunner().invoke(
        validate,
        ["-f", "json_lines", "-o", str(outfile), str(simple2_nwb)],
    )
    assert r.exit_code == 1
    assert outfile.exists()
    lines = outfile.read_text().strip().split("\n")
    assert len(lines) >= 1
    rec = json.loads(lines[0])
    assert "id" in rec
    # stdout should be empty (output went to file)
    assert r.output.strip() == ""


@pytest.mark.ai_generated
def test_validate_output_requires_format(simple2_nwb: Path, tmp_path: Path) -> None:
    """Test --output with unrecognized extension and no --format gives error."""
    outfile = tmp_path / "results.txt"
    r = CliRunner().invoke(
        validate,
        ["-o", str(outfile), str(simple2_nwb)],
    )
    assert r.exit_code != 0
    assert "--output requires --format" in r.output


@pytest.mark.ai_generated
def test_validate_output_auto_format(simple2_nwb: Path, tmp_path: Path) -> None:
    """Test --output auto-detects format from file extension."""
    outfile = tmp_path / "results.jsonl"
    r = CliRunner().invoke(
        validate,
        ["-o", str(outfile), str(simple2_nwb)],
    )
    assert r.exit_code == 1  # NO_DANDISET_FOUND
    assert outfile.exists()
    lines = outfile.read_text().strip().split("\n")
    # Should be json_lines format (one JSON per line)
    rec = json.loads(lines[0])
    assert "id" in rec

    # .json → json_pp (indented)
    outjson = tmp_path / "results.json"
    r = CliRunner().invoke(
        validate,
        ["-o", str(outjson), str(simple2_nwb)],
    )
    assert r.exit_code == 1
    content = outjson.read_text()
    data = json.loads(content)
    assert isinstance(data, list)
    # json_pp produces indented output
    assert "\n " in content


@pytest.mark.ai_generated
def test_validate_summary_human(simple2_nwb: Path) -> None:
    """Test --summary in human format shows statistics."""
    r = CliRunner().invoke(validate, ["--summary", str(simple2_nwb)])
    assert r.exit_code != 0
    assert "Validation Summary" in r.output
    assert "Total issues:" in r.output
    assert "By severity:" in r.output


@pytest.mark.ai_generated
def test_validate_load(simple2_nwb: Path, tmp_path: Path) -> None:
    """Test --load reads results from a JSONL file."""
    # First, produce a JSONL file
    outfile = tmp_path / "results.jsonl"
    r = CliRunner().invoke(
        validate,
        ["-f", "json_lines", "-o", str(outfile), str(simple2_nwb)],
    )
    assert r.exit_code == 1
    assert outfile.exists()

    # Now load it
    r = CliRunner().invoke(validate, ["--load", str(outfile)])
    assert r.exit_code == 1  # loaded errors still produce exit 1
    assert "DANDI.NO_DANDISET_FOUND" in r.output


@pytest.mark.ai_generated
def test_validate_load_with_format(simple2_nwb: Path, tmp_path: Path) -> None:
    """Test --load combined with --format."""
    outfile = tmp_path / "results.jsonl"
    r = CliRunner().invoke(
        validate,
        ["-f", "json_lines", "-o", str(outfile), str(simple2_nwb)],
    )
    assert outfile.exists()

    r = CliRunner().invoke(validate, ["--load", str(outfile), "-f", "json"])
    assert r.exit_code == 1
    data = json.loads(r.output)
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.ai_generated
def test_validate_load_mutual_exclusivity(simple2_nwb: Path, tmp_path: Path) -> None:
    """Test --load and paths are mutually exclusive."""
    outfile = tmp_path / "dummy.jsonl"
    outfile.write_text("")
    r = CliRunner().invoke(validate, ["--load", str(outfile), str(simple2_nwb)])
    assert r.exit_code != 0
    assert "mutually exclusive" in r.output
