import os

from click.testing import CliRunner
import pytest


@pytest.mark.parametrize(
    "dataset", ["invalid_asl003", "invalid_eeg_cbm", "invalid_pet001"]
)
def test_validate_bids_error(bids_error_examples, dataset):
    import json

    from ..cmd_validate import validate_bids

    # expected_error = "File does not match any pattern known to BIDS.\n"

    broken_dataset = os.path.join(bids_error_examples, dataset)
    with open(os.path.join(broken_dataset, ".ERRORS.json")) as f:
        expected_errors = json.load(f)
    r = CliRunner().invoke(validate_bids, [broken_dataset])
    # Does it break?
    assert r.exit_code == 1

    # Does it detect all errors?
    for key in expected_errors:
        assert key in r.output
