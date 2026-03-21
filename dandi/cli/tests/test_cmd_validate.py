import json
from pathlib import Path
from typing import cast

from click.testing import CliRunner
import pytest
import ruamel.yaml

from ..cmd_validate import (
    GroupedResults,
    TruncationNotice,
    _group_results,
    _process_issues,
    _render_human,
    _truncate_leaves,
    validate,
)
from ..command import main
from ...tests.xfail import mark_xfail_windows_python313_posixsubprocess
from ...validate.io import load_validation_jsonl
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


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "grouping",
    ["severity", "id", "validator", "standard", "dandiset"],
)
def test_render_human_grouping(grouping: str, capsys: pytest.CaptureFixture) -> None:
    """Test extended grouping renders section headers with counts."""
    origin = Origin(
        type=OriginType.VALIDATION,
        validator=Validator.nwbinspector,
        validator_version="",
    )
    issues = [
        ValidationResult(
            id="NWBI.check_data_orientation",
            origin=origin,
            scope=Scope.FILE,
            message="Data may be in the wrong orientation.",
            path=Path("sub-01/sub-01.nwb"),
            severity=Severity.WARNING,
            dandiset_path=Path("/data/ds001"),
        ),
        ValidationResult(
            id="NWBI.check_missing_unit",
            origin=origin,
            scope=Scope.FILE,
            message="Missing text for attribute 'unit'.",
            path=Path("sub-02/sub-02.nwb"),
            severity=Severity.WARNING,
            dandiset_path=Path("/data/ds001"),
        ),
    ]
    _render_human(issues, grouping=(grouping,))
    captured = capsys.readouterr().out

    # Section headers with "===" must appear
    assert "===" in captured
    # Both issues should be rendered
    assert "NWBI.check_data_orientation" in captured
    assert "NWBI.check_missing_unit" in captured
    # Issue counts in headers
    assert "issue" in captured


@pytest.mark.ai_generated
def test_validate_grouping_severity_cli(simple2_nwb: Path) -> None:
    """Test --grouping=severity via CLI."""
    r = CliRunner().invoke(validate, ["--grouping=severity", str(simple2_nwb)])
    assert r.exit_code != 0
    assert "===" in r.output
    assert "ERROR" in r.output


@pytest.mark.ai_generated
def test_render_human_multilevel_grouping(capsys: pytest.CaptureFixture) -> None:
    """Test multi-level grouping renders nested section headers."""
    origin = Origin(
        type=OriginType.VALIDATION,
        validator=Validator.nwbinspector,
        validator_version="",
    )
    issues = [
        ValidationResult(
            id="NWBI.check_data_orientation",
            origin=origin,
            scope=Scope.FILE,
            message="Data may be in the wrong orientation.",
            path=Path("sub-01/sub-01.nwb"),
            severity=Severity.WARNING,
            dandiset_path=Path("/data/ds001"),
        ),
        ValidationResult(
            id="NWBI.check_missing_unit",
            origin=origin,
            scope=Scope.FILE,
            message="Missing text for attribute 'unit'.",
            path=Path("sub-02/sub-02.nwb"),
            severity=Severity.WARNING,
            dandiset_path=Path("/data/ds001"),
        ),
        ValidationResult(
            id="NWBI.check_data_orientation",
            origin=origin,
            scope=Scope.FILE,
            message="Data may be in the wrong orientation.",
            path=Path("sub-03/sub-03.nwb"),
            severity=Severity.ERROR,
            dandiset_path=Path("/data/ds001"),
        ),
    ]
    _render_human(issues, grouping=("severity", "id"))
    captured = capsys.readouterr().out

    # Should have nested headers: severity then id
    assert "=== WARNING" in captured
    assert "=== ERROR" in captured
    assert "=== NWBI.check_data_orientation" in captured
    assert "=== NWBI.check_missing_unit" in captured
    # Nested headers should be indented
    lines = captured.split("\n")
    # Find inner headers — they should have leading spaces
    inner_headers = [ln for ln in lines if "===" in ln and ln.startswith("  ")]
    assert len(inner_headers) >= 2  # at least 2 inner group headers


@pytest.mark.ai_generated
def test_validate_multilevel_grouping_human_cli(simple2_nwb: Path) -> None:
    """Test -g severity -g id via CLI produces nested headers."""
    r = CliRunner().invoke(validate, ["-g", "severity", "-g", "id", str(simple2_nwb)])
    assert r.exit_code != 0
    assert "===" in r.output
    # Should have nested structure
    lines = r.output.split("\n")
    inner_headers = [ln for ln in lines if "===" in ln and ln.startswith("  ")]
    assert len(inner_headers) >= 1


@pytest.mark.ai_generated
def test_validate_multilevel_grouping_json_cli(simple2_nwb: Path) -> None:
    """Test -g severity -f json_pp via CLI produces nested JSON dict."""
    r = CliRunner().invoke(
        validate, ["-g", "severity", "-f", "json_pp", str(simple2_nwb)]
    )
    assert r.exit_code == 1
    data = json.loads(r.output)
    # With grouping, output should be a dict (not a list)
    assert isinstance(data, dict)
    # Keys should be severity names
    for key in data:
        assert key in ("CRITICAL", "ERROR", "WARNING", "HINT", "INFO", "NONE")
    # Values should be lists of validation result dicts
    for v in data.values():
        assert isinstance(v, list)
        for rec in v:
            assert "id" in rec


@pytest.mark.ai_generated
def test_validate_multilevel_grouping_json_two_levels(simple2_nwb: Path) -> None:
    """Test -g severity -g id -f json_pp produces two-level nested JSON."""
    r = CliRunner().invoke(
        validate, ["-g", "severity", "-g", "id", "-f", "json_pp", str(simple2_nwb)]
    )
    assert r.exit_code == 1
    data = json.loads(r.output)
    assert isinstance(data, dict)
    # Each value should be a dict (second grouping level)
    for severity_key, id_groups in data.items():
        assert isinstance(id_groups, dict)
        for id_key, results in id_groups.items():
            assert isinstance(results, list)
            for rec in results:
                assert "id" in rec


@pytest.mark.ai_generated
def test_validate_grouping_yaml_cli(simple2_nwb: Path) -> None:
    """Test -g severity -f yaml produces grouped YAML output."""
    r = CliRunner().invoke(validate, ["-g", "severity", "-f", "yaml", str(simple2_nwb)])
    assert r.exit_code == 1
    yaml = ruamel.yaml.YAML(typ="safe")
    data = yaml.load(r.output)
    assert isinstance(data, dict)
    for key in data:
        assert key in ("CRITICAL", "ERROR", "WARNING", "HINT", "INFO", "NONE")


@pytest.mark.ai_generated
def test_validate_grouping_jsonl_error(simple2_nwb: Path) -> None:
    """Test -g severity -f json_lines gives a UsageError."""
    r = CliRunner().invoke(
        validate, ["-g", "severity", "-f", "json_lines", str(simple2_nwb)]
    )
    assert r.exit_code != 0
    assert "incompatible" in r.output


@pytest.mark.ai_generated
def test_validate_grouping_none_explicit(simple2_nwb: Path) -> None:
    """Test -g none is treated as no grouping."""
    r = CliRunner().invoke(validate, ["-g", "none", str(simple2_nwb)])
    assert r.exit_code != 0
    # Should NOT have section headers
    assert "===" not in r.output


@pytest.mark.ai_generated
def test_group_results_unit() -> None:
    """Unit test for _group_results with multiple levels."""
    from collections import OrderedDict

    origin = Origin(
        type=OriginType.VALIDATION,
        validator=Validator.nwbinspector,
        validator_version="",
    )
    issues = [
        ValidationResult(
            id="A.one",
            origin=origin,
            scope=Scope.FILE,
            message="msg1",
            path=Path("f1.nwb"),
            severity=Severity.ERROR,
        ),
        ValidationResult(
            id="A.two",
            origin=origin,
            scope=Scope.FILE,
            message="msg2",
            path=Path("f2.nwb"),
            severity=Severity.WARNING,
        ),
        ValidationResult(
            id="A.one",
            origin=origin,
            scope=Scope.FILE,
            message="msg3",
            path=Path("f3.nwb"),
            severity=Severity.ERROR,
        ),
    ]

    # Zero levels: returns flat list
    result = _group_results(issues, ())
    assert result is issues

    # One level
    result = _group_results(issues, ("severity",))
    assert isinstance(result, OrderedDict)
    assert "ERROR" in result
    assert "WARNING" in result
    assert len(result["ERROR"]) == 2
    assert len(result["WARNING"]) == 1

    # Two levels
    result2 = _group_results(issues, ("severity", "id"))
    assert isinstance(result2, OrderedDict)
    error_group = result2["ERROR"]
    assert isinstance(error_group, OrderedDict)
    assert "A.one" in error_group
    assert len(error_group["A.one"]) == 2
    warning_group = result2["WARNING"]
    assert isinstance(warning_group, OrderedDict)
    assert "A.two" in warning_group
    assert len(warning_group["A.two"]) == 1


def _make_jsonl(tmp_path: Path, n: int = 5) -> Path:
    """Write *n* synthetic validation results to a JSONL file and return its path."""
    outfile = tmp_path / "results.jsonl"
    lines = []
    for i in range(n):
        sev = "ERROR" if i % 2 == 0 else "WARNING"
        rec = {
            "id": f"TEST.issue_{i}",
            "origin": {
                "type": "VALIDATION",
                "validator": "nwbinspector",
                "validator_version": "",
            },
            "scope": "file",
            "severity": sev,
            "path": f"sub-{i:02d}/sub-{i:02d}.nwb",
            "message": f"Synthetic issue number {i}",
            "record_version": "1",
        }
        lines.append(json.dumps(rec))
    outfile.write_text("\n".join(lines) + "\n")
    return outfile


@pytest.mark.ai_generated
def test_max_per_group_flat(tmp_path: Path) -> None:
    """--max-per-group without grouping truncates the flat list."""
    jsonl = _make_jsonl(tmp_path, n=5)
    r = CliRunner().invoke(validate, ["--load", str(jsonl), "--max-per-group", "2"])
    assert r.exit_code == 1
    assert "3 more issues" in r.output
    # Only 2 real issues should be listed
    assert "TEST.issue_0" in r.output
    assert "TEST.issue_1" in r.output
    assert "TEST.issue_4" not in r.output


@pytest.mark.ai_generated
def test_max_per_group_with_grouping(tmp_path: Path) -> None:
    """-g severity --max-per-group 1 truncates each severity group independently."""
    jsonl = _make_jsonl(tmp_path, n=6)
    r = CliRunner().invoke(
        validate,
        ["--load", str(jsonl), "-g", "severity", "--max-per-group", "1"],
    )
    assert r.exit_code == 1
    # Each group should show "more issue(s)"
    assert "more issue" in r.output
    # Headers should reflect original counts (including omitted)
    assert "=== ERROR" in r.output
    assert "=== WARNING" in r.output


@pytest.mark.ai_generated
def test_max_per_group_json(tmp_path: Path) -> None:
    """-f json_pp --max-per-group 2 emits _truncated placeholder in JSON."""
    jsonl = _make_jsonl(tmp_path, n=5)
    r = CliRunner().invoke(
        validate,
        ["--load", str(jsonl), "-f", "json_pp", "--max-per-group", "2"],
    )
    assert r.exit_code == 1  # ERRORs in test data
    data = json.loads(r.output)
    assert isinstance(data, list)
    # Last item should be a truncation notice
    assert data[-1]["_truncated"] is True
    assert data[-1]["omitted_count"] == 3
    # Only 2 real results before the notice
    real = [d for d in data if "_truncated" not in d]
    assert len(real) == 2


@pytest.mark.ai_generated
def test_max_per_group_multilevel(tmp_path: Path) -> None:
    """-g severity -g id --max-per-group 1 truncates only at leaf level."""
    jsonl = _make_jsonl(tmp_path, n=6)
    r = CliRunner().invoke(
        validate,
        [
            "--load",
            str(jsonl),
            "-g",
            "severity",
            "-g",
            "id",
            "--max-per-group",
            "1",
        ],
    )
    assert r.exit_code == 1
    # All severity groups should appear
    assert "=== ERROR" in r.output
    assert "=== WARNING" in r.output
    # Each id within a severity gets at most 1 result — but since each
    # synthetic issue has a unique id, each leaf has exactly 1 item,
    # so no truncation notice is expected for unique-id leaves.
    # Verify structure is intact.
    assert "TEST.issue_0" in r.output


@pytest.mark.ai_generated
def test_max_per_group_no_truncation(tmp_path: Path) -> None:
    """--max-per-group larger than result count produces no placeholder."""
    jsonl = _make_jsonl(tmp_path, n=3)
    r = CliRunner().invoke(validate, ["--load", str(jsonl), "--max-per-group", "100"])
    assert r.exit_code == 1
    assert "more issue" not in r.output
    # All issues present
    assert "TEST.issue_0" in r.output
    assert "TEST.issue_1" in r.output
    assert "TEST.issue_2" in r.output


@pytest.mark.ai_generated
def test_max_per_group_json_grouped(tmp_path: Path) -> None:
    """-g severity -f json_pp --max-per-group 1 emits _truncated in grouped JSON."""
    jsonl = _make_jsonl(tmp_path, n=6)
    r = CliRunner().invoke(
        validate,
        [
            "--load",
            str(jsonl),
            "-g",
            "severity",
            "-f",
            "json_pp",
            "--max-per-group",
            "1",
        ],
    )
    data = json.loads(r.output)
    assert isinstance(data, dict)
    # Each severity group should have a truncation notice if it has > 1 item
    for sev_key, items in data.items():
        assert isinstance(items, list)
        truncated = [i for i in items if isinstance(i, dict) and i.get("_truncated")]
        if len(items) > 1:
            # At least one truncation notice
            assert len(truncated) >= 1


@pytest.mark.ai_generated
def test_truncate_leaves_unit() -> None:
    """Unit test for _truncate_leaves helper."""
    from collections import OrderedDict

    origin = Origin(
        type=OriginType.VALIDATION,
        validator=Validator.nwbinspector,
        validator_version="",
    )
    issues = [
        ValidationResult(
            id=f"T.{i}",
            origin=origin,
            scope=Scope.FILE,
            message=f"msg{i}",
            path=Path(f"f{i}.nwb"),
            severity=Severity.ERROR,
        )
        for i in range(5)
    ]

    # Flat list truncation
    truncated = _truncate_leaves(issues, 2)
    assert isinstance(truncated, list)
    assert len(truncated) == 3  # 2 results + 1 notice
    assert isinstance(truncated[-1], TruncationNotice)
    assert truncated[-1].omitted_count == 3

    # Nested dict truncation
    grouped: GroupedResults = cast(
        "GroupedResults", OrderedDict([("A", issues[:3]), ("B", issues[3:])])
    )
    truncated_grouped = _truncate_leaves(grouped, 1)
    assert isinstance(truncated_grouped, OrderedDict)
    a_items = truncated_grouped["A"]
    assert isinstance(a_items, list)
    assert len(a_items) == 2  # 1 result + 1 notice
    assert isinstance(a_items[-1], TruncationNotice)
    assert a_items[-1].omitted_count == 2
    # B has 2 items → truncated to 1 + notice
    b_items = truncated_grouped["B"]
    assert isinstance(b_items, list)
    assert len(b_items) == 2
    assert isinstance(b_items[-1], TruncationNotice)

    # No truncation when under limit
    no_trunc = _truncate_leaves(issues, 100)
    assert no_trunc is issues


@pytest.mark.ai_generated
def test_validate_auto_sidecar_human(
    simple2_nwb: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default human-format validate auto-saves sidecar next to log file."""
    logdir = tmp_path / "logs"
    logdir.mkdir()
    monkeypatch.setattr("platformdirs.user_log_dir", lambda *a, **kw: str(logdir))

    r = CliRunner().invoke(main, ["validate", str(simple2_nwb)])
    assert r.exit_code == 1  # NO_DANDISET_FOUND

    # Find sidecar files
    sidecars = list(logdir.glob("*_validation.jsonl"))
    assert len(sidecars) == 1

    # Verify content is loadable
    results = load_validation_jsonl(sidecars[0])
    assert len(results) > 0


@pytest.mark.ai_generated
def test_validate_auto_sidecar_skipped_with_output(
    simple2_nwb: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--output suppresses auto-save sidecar."""
    logdir = tmp_path / "logs"
    logdir.mkdir()
    monkeypatch.setattr("platformdirs.user_log_dir", lambda *a, **kw: str(logdir))

    outfile = tmp_path / "results.jsonl"
    r = CliRunner().invoke(main, ["validate", "-o", str(outfile), str(simple2_nwb)])
    assert r.exit_code == 1
    assert outfile.exists()

    # No sidecar should exist
    sidecars = list(logdir.glob("*_validation.jsonl"))
    assert len(sidecars) == 0


@pytest.mark.ai_generated
def test_validate_auto_sidecar_skipped_with_load(
    simple2_nwb: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--load suppresses auto-save sidecar."""
    logdir = tmp_path / "logs"
    logdir.mkdir()
    monkeypatch.setattr("platformdirs.user_log_dir", lambda *a, **kw: str(logdir))

    # First produce a JSONL to load
    outfile = tmp_path / "input.jsonl"
    r = CliRunner().invoke(
        main, ["validate", "-f", "json_lines", "-o", str(outfile), str(simple2_nwb)]
    )
    assert outfile.exists()

    # Clear any sidecars from first run
    for s in logdir.glob("*_validation.jsonl"):
        s.unlink()

    # Now --load it
    r = CliRunner().invoke(main, ["validate", "--load", str(outfile)])
    assert r.exit_code == 1

    # No new sidecar should exist
    sidecars = list(logdir.glob("*_validation.jsonl"))
    assert len(sidecars) == 0


@pytest.mark.ai_generated
def test_validate_auto_sidecar_structured_stdout(
    simple2_nwb: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Structured format to stdout also auto-saves sidecar."""
    logdir = tmp_path / "logs"
    logdir.mkdir()
    monkeypatch.setattr("platformdirs.user_log_dir", lambda *a, **kw: str(logdir))

    r = CliRunner().invoke(main, ["validate", "-f", "json", str(simple2_nwb)])
    assert r.exit_code == 1

    sidecars = list(logdir.glob("*_validation.jsonl"))
    assert len(sidecars) == 1
