from glob import glob
import os

import appdirs


def test_validate_bids(bids_examples):
    from ..validate import validate_bids

    # TEST DEFAULT REPORT PATH:
    # Replace explicit dataset with `os.listdir(bids_examples)[1]` whenever we
    # implement light data cloning analogous to (`[1]` because `[0]` is .git):
    # https://github.com/bids-standard/bids-specification/pull/1143
    selected_dataset = os.path.join(bids_examples, "asl003")
    _ = validate_bids(selected_dataset, report=True)

    # Check if a report is being produced.
    pid = os.getpid()
    log_dir = appdirs.user_log_dir("dandi-cli", "dandi")
    report_expression = os.path.join(log_dir, f"bids-validator-report_*-{pid}.log")
    assert len(glob(report_expression)) == 1

    # TEST CISTOM REPORT PATH:
    # Replace explicit dataset with `os.listdir(bids_examples)[1]` whenever we
    # implement light data cloning analogous to (`[1]` because `[0]` is .git):
    # https://github.com/bids-standard/bids-specification/pull/1143
    selected_dataset = os.path.join(bids_examples, "asl003")
    _ = validate_bids(
        selected_dataset, report_path="/tmp/inplace_bids-validator-report.log"
    )

    # Check if a report is being produced.
    assert len(glob("/tmp/inplace_bids-validator-report.log")) == 1
