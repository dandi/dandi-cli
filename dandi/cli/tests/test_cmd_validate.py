import os

from click.testing import CliRunner


def test_validate_bids_error(bids_examples):
    from ..cmd_validate import validate_bids

    expected_error = (
        "Summary: 1 filename pattern required by BIDS could not be found "
        "and 1 filename did not match any pattern known to BIDS.\n"
    )
    broken_dataset = os.path.join(bids_examples, "invalid_pet001")
    r = CliRunner().invoke(validate_bids, [broken_dataset])
    # Does it break?
    assert r.exit_code == 1

    # Does it report the issue correctly?
    assert r.output == expected_error
