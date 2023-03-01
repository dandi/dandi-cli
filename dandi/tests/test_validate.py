import json
from pathlib import Path

import pytest

from .fixtures import BIDS_ERROR_TESTDATA_SELECTION, BIDS_TESTDATA_SELECTION
from ..validate import validate


def test_validate_nwb_error(simple3_nwb: Path) -> None:
    """Do we fail on critical NWB validation errors?"""
    validation_result = validate(simple3_nwb)
    assert len([i for i in validation_result if i.severity]) > 0


@pytest.mark.parametrize("dataset", BIDS_TESTDATA_SELECTION)
def test_validate_bids(bids_examples: Path, tmp_path: Path, dataset: str) -> None:
    selected_dataset = bids_examples / dataset
    validation_result = validate(selected_dataset)
    for i in validation_result:
        assert i.severity is None


def test_validate_bids_onefile(bids_error_examples: Path, tmp_path: Path) -> None:
    """
    Dedicated test using single-file validation.

    Notes
    -----
    * Due to the dataset-wide scope of BIDS, issues with single-file handling have arisen and can
    potentially arise again. Best to keep this in to always make sure.
    * This can be further automated thanks to the upstream `.ERRORS.json` convention to be
    performed on all error datasets, but that might be overkill since we test the datasets as
    a whole anyway.
    """

    selected_dataset = "invalid_asl003"
    error_file = Path("sub-Sub1/perf/sub-Sub1_headshape.jpg")

    bids_file_path = bids_error_examples / selected_dataset / error_file
    error_reference = bids_error_examples / selected_dataset / ".ERRORS.json"
    with error_reference.open() as f:
        expected_errors = json.load(f)
    validation_result = validate(bids_file_path)
    for i in validation_result:
        error_id = i.id
        assert i.path is not None
        assert i.dataset_path is not None
        relative_error_path = i.path.relative_to(i.dataset_path).as_posix()
        assert relative_error_path in expected_errors[error_id.lstrip("BIDS.")]["scope"]


@pytest.mark.parametrize("dataset", BIDS_ERROR_TESTDATA_SELECTION)
def test_validate_bids_errors(bids_error_examples: Path, dataset: str) -> None:
    # This only checks that the error we found is correct, not that we found
    # all errors.  ideally make a list and erode etc.
    selected_dataset = bids_error_examples / dataset
    validation_result = list(validate(selected_dataset))
    with (selected_dataset / ".ERRORS.json").open() as f:
        expected_errors = json.load(f)

    # We know that these datasets contain errors.
    assert len(validation_result) > 0

    # But are they the right errors?
    for i in validation_result:
        if i.id == "BIDS.MATCH":
            continue
        error_id = i.id
        if i.path is not None:
            assert i.dataset_path is not None
            relative_error_path = i.path.relative_to(i.dataset_path).as_posix()
            assert (
                relative_error_path
                in expected_errors[error_id.lstrip("BIDS.")]["scope"]
            )
        else:
            assert i.id.lstrip("BIDS.") in expected_errors.keys()
