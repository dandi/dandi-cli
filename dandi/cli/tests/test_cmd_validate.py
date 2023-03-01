import json
from pathlib import Path

from click.testing import CliRunner
import pytest

from ..cmd_validate import validate
from ...tests.fixtures import BIDS_ERROR_TESTDATA_SELECTION


@pytest.mark.parametrize("dataset", BIDS_ERROR_TESTDATA_SELECTION)
def test_validate_bids_error(bids_error_examples: Path, dataset: str) -> None:
    broken_dataset = bids_error_examples / dataset
    with (broken_dataset / ".ERRORS.json").open() as f:
        expected_errors = json.load(f)
    r = CliRunner().invoke(validate, [str(broken_dataset)])
    # Does it break?
    assert r.exit_code == 1
    # Does it detect all errors?
    for key in expected_errors:
        assert key in r.output


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


def test_validate_bids_grouping_error(
    bids_error_examples: Path, dataset: str = "invalid_asl003"
) -> None:
    """
    This is currently a placeholder test, and should be updated once we have
    paths with multiple errors for which grouping functionality can actually be
    tested.
    """
    bids_dataset = bids_error_examples / dataset
    r = CliRunner().invoke(validate, ["--grouping=path", str(bids_dataset)])
    # Does it break?
    assert r.exit_code == 1
    # Does it detect all errors?
    assert str(bids_dataset) in r.output


def test_validate_nwb_path_grouping(organized_nwb_dir3: Path) -> None:
    """
    This is currently a placeholder test and should be updated once we have
    paths with multiple errors for which grouping functionality can actually be
    tested.
    """
    r = CliRunner().invoke(validate, ["--grouping=path", str(organized_nwb_dir3)])
    assert r.exit_code == 0
    # Does it give required warnings for required path?
    assert str(organized_nwb_dir3 / "sub-mouse001" / "sub-mouse001.nwb") in r.output
    assert "NWBI.check_data_orientation" in r.output


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
