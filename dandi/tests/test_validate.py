from glob import glob
import os

import appdirs


def test_validate_bids(bids_examples):
    from ..validate import validate_bids

    selected_dataset = os.path.join(bids_examples, os.listdir(bids_examples)[0])
    _ = validate_bids(selected_dataset, report=True)

    # Check if a report is being produced.
    pid = os.getpid()
    log_dir = appdirs.user_log_dir("dandi-cli", "dandi")
    assert len(glob(f"{log_dir}/bids-validator-report_*-{pid}.log")) == 1
