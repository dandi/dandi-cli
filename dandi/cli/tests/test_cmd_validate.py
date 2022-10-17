import json
import os

from click.testing import CliRunner
import pytest

from ..cmd_validate import validate, validate_bids


@pytest.mark.parametrize(
    "dataset", ["invalid_asl003", "invalid_eeg_cbm", "invalid_pet001"]
)
def test_validate_bids_error(bids_error_examples, dataset):

    broken_dataset = os.path.join(bids_error_examples, dataset)
    with open(os.path.join(broken_dataset, ".ERRORS.json")) as f:
        expected_errors = json.load(f)
    r = CliRunner().invoke(validate_bids, [broken_dataset])
    # Does it break?
    assert r.exit_code == 1

    # Does it detect all errors?
    for key in expected_errors:
        assert key in r.output


def test_validate_bids_grouping_error(bids_error_examples, dataset="invalid_asl003"):
    """
    This is currently a placeholder test, and should be updated once we have paths with
    multiple errors.
    """

    dataset = os.path.join(bids_error_examples, dataset)
    r = CliRunner().invoke(validate_bids, ["--grouping=path", dataset])
    # Does it break?
    assert r.exit_code == 1

    # Does it detect all errors?
    assert dataset in r.output


def test_validate_nwb_path_grouping(simple3_nwb):
    """
    This is currently a placeholder test, and should be updated once we have paths with
    multiple errors.
    """

    r = CliRunner().invoke(validate, ["--grouping=path", simple3_nwb])
    # Does it pass?
    print(r.output)
    assert r.exit_code == 0

    # Does it give required warnings for required path?
    assert simple3_nwb in r.output
    assert "NWBI.check_subject_id_exists" in r.output


def test_validate_bids_error_grouping_notification(
    bids_error_examples, dataset="invalid_asl003"
):
    """Test user notification for unimplemented parameter value."""

    broken_dataset = os.path.join(bids_error_examples, dataset)
    r = CliRunner().invoke(validate_bids, ["--grouping=error", broken_dataset])
    # Does it break?
    assert r.exit_code == 2

    # Does it notify the user correctly?
    notification_substring = "Invalid value for '--grouping'"
    assert notification_substring in r.output
