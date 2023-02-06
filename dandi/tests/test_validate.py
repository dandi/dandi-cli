import json
import os
import pathlib

import pytest

from .fixtures import BIDS_TESTDATA_SELECTION
from ..validate import validate, validate_bids


def test_validate_nwb_error(simple3_nwb):
    """
    Do we fail on critical NWB validation errors?
    """

    validation_result = validate(simple3_nwb)
    assert len([i for i in validation_result if i.severity]) > 0


@pytest.mark.parametrize("dataset", BIDS_TESTDATA_SELECTION)
def test_validate_bids(bids_examples, tmp_path, dataset):

    selected_dataset = os.path.join(bids_examples, dataset)
    validation_result = validate(selected_dataset, report=True)
    for i in validation_result:
        assert i.severity is None


def test_validate_bids_onefile(bids_error_examples, tmp_path):
    """
    Dedicated test using to single-file validation.

    Notes
    -----
    * Due to the dataset-wide scope of BIDS, issues have arisen and can potentially arise again
    with single-file handling. Best to keep this in to always make sure.
    * This can be further automated thanks to the upstream `.ERRORS.json` convention to be
    performed on all error datasets, but that might be overkill since we test the datasets as
    a whole anyway.
    """

    selected_dataset, error_file = (
        "invalid_asl003",
        "sub-Sub1/perf/sub-Sub1_headshape.jpg",
    )

    bids_file_path = os.path.join(bids_error_examples, selected_dataset, error_file)
    bids_dataset_path = pathlib.Path(
        os.path.join(bids_error_examples, selected_dataset)
    )
    error_reference = os.path.join(bids_dataset_path, ".ERRORS.json")
    with open(error_reference) as f:
        expected_errors = json.load(f)
    validation_result = validate(bids_file_path)
    for i in validation_result:
        error_id = i.id
        error_path = i.path
        relative_error_path = os.path.relpath(error_path, i.dataset_path)
        relative_error_path = pathlib.Path(relative_error_path).as_posix()
        assert relative_error_path in expected_errors[error_id.lstrip("BIDS.")]["scope"]


def test_report_path(bids_examples, tmp_path):

    Notes
    -----
    * Due to the dataset-wide scope of BIDS, issues have arisen and can potentially arise again
    with single-file handling. Best to keep this in to always make sure.
    * This can be further automated thanks to the upstream `.ERRORS.json` convention to be
    performed on all error datasets, but that might be overkill since we test the datasets as
    a whole anyway.
    """

    selected_dataset, error_file = (
        "invalid_asl003",
        "sub-Sub1/perf/sub-Sub1_headshape.jpg",
    )

    bids_file_path = os.path.join(bids_error_examples, selected_dataset, error_file)
    bids_dataset_path = pathlib.Path(bids_error_examples, selected_dataset)
    error_reference = os.path.join(bids_dataset_path, ".ERRORS.json")
    with open(error_reference) as f:
        expected_errors = json.load(f)
    validation_result = validate(bids_file_path)
    for i in validation_result:
        error_id = i.id
        error_path = i.path
        relative_error_path = os.path.relpath(error_path, i.dataset_path)
        relative_error_path = pathlib.Path(relative_error_path).as_posix()
        assert relative_error_path in expected_errors[error_id.lstrip("BIDS.")]["scope"]


@pytest.mark.parametrize(
    "dataset", ["invalid_asl003", "invalid_eeg_cbm", "invalid_pet001"]
)
def test_validate_bids_errors(bids_error_examples, dataset):
    # This only checks that the error we found is correct, not that we found all errors.
    # ideally make a list and erode etc.

    selected_dataset = os.path.join(bids_error_examples, dataset)
    validation_result = validate(selected_dataset)
    validation_result = list(validation_result)
    with open(os.path.join(selected_dataset, ".ERRORS.json")) as f:
        expected_errors = json.load(f)

    # We know that these datasets contain errors.
    assert len(validation_result) > 0

    # But are they the right errors?
    for i in validation_result:
        if i.id == "BIDS.MATCH":
            continue
        error_id = i.id
        if i.path:
            error_path = i.path
            relative_error_path = os.path.relpath(error_path, i.dataset_path)
            relative_error_path = pathlib.Path(relative_error_path).as_posix()
            assert (
                relative_error_path
                in expected_errors[error_id.lstrip("BIDS.")]["scope"]
            )
        else:
            assert i.id.lstrip("BIDS.") in expected_errors.keys()
