from glob import glob
import os

import appdirs
import pytest


def test_validate_bids(bids_examples, tmp_path):
    from ..validate import validate_bids

    # TEST DEFAULT REPORT PATH:
    # Replace explicit dataset with `os.listdir(bids_examples)[1]` whenever we
    # implement light data cloning analogous to (`[1]` because `[0]` is .git):
    # https://github.com/bids-standard/bids-specification/pull/1143
    selected_dataset = os.path.join(bids_examples, "asl003")
    _ = validate_bids(selected_dataset, report=True)

    # Check if a report is being produced.
    pid = os.getpid()
    log_dir = appdirs.user_log_dir("dandi")
    report_expression = os.path.join(log_dir, f"bids-validator-report_*-{pid}.log")
    assert len(glob(report_expression)) == 1

    # TEST CISTOM REPORT PATH:
    # Replace explicit dataset with `os.listdir(bids_examples)[1]` whenever we
    # implement light data cloning analogous to (`[1]` because `[0]` is .git):
    # https://github.com/bids-standard/bids-specification/pull/1143
    report_path = os.path.join(tmp_path, "inplace_bids-validator-report.log")
    selected_dataset = os.path.join(bids_examples, "asl003")
    _ = validate_bids(
        selected_dataset,
        report_path=report_path,
    )

    # Check if a report is being produced.
    assert len(glob(report_path)) == 1


@pytest.mark.parametrize(
    "dataset", ["invalid_asl003", "invalid_eeg_cbm", "invalid_pet001"]
)
def test_validate_bids_errors(bids_error_examples, dataset):
    # This only checks that the error we found is correct, not that we found all errors.
    # ideally make a list and erode etc.
    import json

    from ..validate import validate_bids

    selected_dataset = os.path.join(bids_error_examples, dataset)
    validation_result = validate_bids(selected_dataset, report=True)
    with open(os.path.join(selected_dataset, ".ERRORS.json")) as f:
        expected_errors = json.load(f)
    for i in validation_result:
        error_id = i.id
        if i.path:
            error_path = i.path
            relative_error_path = os.path.relpath(error_path, i.dataset_path)
            assert (
                relative_error_path
                in expected_errors[error_id.lstrip("BIDS.")]["scope"]
            )
        else:
            assert i.id.lstrip("BIDS.") in expected_errors.keys()
