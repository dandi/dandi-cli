import json
from pathlib import Path
from typing import Any

import pytest

from .fixtures import BIDS_TESTDATA_SELECTION
from .. import __version__
from ..consts import dandiset_metadata_file
from ..validate import validate
from ..validate_types import (
    Origin,
    OriginType,
    Scope,
    Severity,
    Standard,
    ValidationResult,
    Validator,
)


def test_validate_nwb_error(simple3_nwb: Path) -> None:
    """Do we fail on critical NWB validation errors?"""
    validation_result = validate(simple3_nwb)
    assert len([i for i in validation_result if i.severity]) > 0


def test_validate_relative_path(
    bids_examples: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_dataset_path = bids_examples / "asl003"
    monkeypatch.chdir(selected_dataset_path)
    # improper relative path handling would fail with:
    # ValueError: Path '.' is not inside Dandiset path '/tmp/.../asl003'
    list(validate("."))


def test_validate_empty(tmp_path: Path) -> None:
    assert list(validate(tmp_path)) == [
        ValidationResult(
            id="DANDI.NO_DANDISET_FOUND",
            origin=Origin(
                type=OriginType.VALIDATION,
                validator=Validator.dandi,
                validator_version=__version__,
                standard=Standard.DANDI_LAYOUT,
            ),
            severity=Severity.ERROR,
            scope=Scope.DANDISET,
            path=tmp_path,
            message="Path is not inside a Dandiset",
        )
    ]


def test_validate_just_dandiset_yaml(tmp_path: Path) -> None:
    (tmp_path / dandiset_metadata_file).write_text(
        "identifier: 12346\nname: Foo\ndescription: Dandiset Foo\n"
    )
    assert list(validate(tmp_path)) == []


@pytest.mark.parametrize("dataset", BIDS_TESTDATA_SELECTION)
def test_validate_bids(
    bids_examples: Path, tmp_path: Path, dataset: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test validating a selection of datasets at
        https://github.com/bids-standard/bids-examples
    """
    from dandi.files import bids

    def mock_bids_validate(*args: Any, **kwargs: Any) -> list[ValidationResult]:
        """
        Mock `bids_validate` to validate the examples in
        # https://github.com/bids-standard/bids-examples. These example datasets
        contains empty NIFTI files

        Note
        -----
            Unlike other mock function for `bids_validate`, this one doesn't
            configure the validator to ignore the dandiset metadata file. Thus,
            an error regarding the `dandiset.yaml` file is to be expected.
        """
        from dandi.bids_validator_deno import bids_validate

        kwargs["config"] = {
            "ignore": [
                # Raw Data Files in the examples are empty
                {"code": "EMPTY_FILE"}
            ]
        }
        kwargs["ignore_nifti_headers"] = True
        return bids_validate(*args, **kwargs)

    monkeypatch.setattr(bids, "bids_validate", mock_bids_validate)

    selected_dataset = bids_examples / dataset
    validation_results = list(validate(selected_dataset))

    validation_errs = [
        r
        for r in validation_results
        if r.severity is not None and r.severity >= Severity.ERROR
    ]

    # Assert that there is one error
    assert len(validation_errs) == 1

    err = validation_errs[0]

    assert err.path is not None
    assert err.dataset_path is not None
    assert err.path.relative_to(err.dataset_path).as_posix() == dandiset_metadata_file

    assert err.message is not None
    assert err.message.startswith(
        f"The dandiset metadata file, `{dandiset_metadata_file}`, is not a part of "
        f"BIDS specification."
    )


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


@pytest.mark.parametrize(
    "ds_name, expected_err_location",
    [
        ("invalid_asl003", "sub-Sub1/perf/sub-Sub1_headshape.jpg"),
        ("invalid_pet001", "sub-01/ses-01/anat/sub-02_ses-01_T1w.json"),
    ],
)
def test_validate_bids_errors(
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

    ds_path = bids_error_examples / ds_name

    results = list(validate(ds_path))

    # All results with severity `ERROR` or above
    err_results = list(
        r for r in results if r.severity is not None and r.severity >= Severity.ERROR
    )

    assert len(err_results) >= 1  # Assert there must be an error

    # Assert all the errors are from the expected location
    # as documented in the `.ERRORS.json` of respective datasets
    for r in err_results:
        assert r.path is not None
        assert r.dataset_path is not None

        err_location = r.path.relative_to(r.dataset_path).as_posix()
        assert err_location == expected_err_location
