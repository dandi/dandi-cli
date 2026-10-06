import json
import os
from pathlib import Path
import shutil
from typing import Any

import pytest

from .._core import validate
from .._types import (
    MissingFileContent,
    Origin,
    OriginType,
    Scope,
    Severity,
    Standard,
    ValidationResult,
    Validator,
)
from ... import __version__
from ...consts import dandiset_metadata_file
from ...pynwb_utils import validate as pynwb_validate
from ...support.datalad_fuse import get_annexed_readable
from ...tests.fixtures import (
    BIDS_TESTDATA_SELECTION,
    RangeHTTPServer,
    make_git_annex_dandiset,
)
from ...tests.skip import skipif


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

    # === Assert that there is the dandiset.yaml hint ===
    i = None
    for i, r in enumerate(validation_results):
        if r is err:
            break

    assert i is not None
    # There must be at least one more result after the error
    assert len(validation_results) > i + 1
    # The next result must be the hint re: dandiset.yaml
    assert validation_results[i + 1].id == "DANDI.BIDSIGNORE_DANDISET_YAML"
    assert validation_results[i + 1].severity == Severity.HINT


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


def _make_dandiset_with_broken_symlink(
    tmp_path: Path, *, include_real_nwb: bool = False
) -> Path:
    """Create a minimal dandiset with a broken NWB symlink (simulating datalad).

    When *include_real_nwb* is True a second subject directory contains a real
    (though minimal) NWB file so tests can verify that normal validation still
    runs on files with content present alongside broken symlinks.
    """
    (tmp_path / dandiset_metadata_file).write_text(
        "identifier: '000027'\nname: Test\ndescription: Test dandiset\n"
    )
    sub_dir = tmp_path / "sub-001"
    sub_dir.mkdir()
    nwb_link = sub_dir / "sub-001.nwb"
    # Symlink to a non-existent target (simulating datalad annex)
    nwb_link.symlink_to(
        ".git/annex/objects/XX/YY/SHA256E-s123--abc.nwb/SHA256E-s123--abc.nwb"
    )

    if include_real_nwb:
        from datetime import datetime, timezone

        from ...pynwb_utils import make_nwb_file

        sub2 = tmp_path / "sub-002"
        sub2.mkdir()
        make_nwb_file(
            sub2 / "sub-002.nwb",
            session_description="test session",
            identifier="test-nwb-001",
            session_start_time=datetime(2017, 4, 3, 11, tzinfo=timezone.utc),
        )
    return tmp_path


@pytest.mark.ai_generated
def test_validate_broken_symlink_error_default(tmp_path: Path) -> None:
    """Default (error) policy emits a concise error for broken symlinks."""
    ds = _make_dandiset_with_broken_symlink(tmp_path)
    results = list(validate(ds))
    errs = [r for r in results if r.id == "DANDI.FILE_CONTENT_MISSING"]
    assert len(errs) == 1
    assert errs[0].severity == Severity.ERROR
    assert errs[0].message is not None
    assert "broken symlink" in errs[0].message.lower()
    # No traceback should appear in the message
    assert "Traceback" not in errs[0].message


@pytest.mark.ai_generated
def test_validate_broken_symlink_skip(tmp_path: Path) -> None:
    """skip policy emits a WARNING and skips the file entirely."""
    ds = _make_dandiset_with_broken_symlink(tmp_path)
    results = list(validate(ds, missing_file_content=MissingFileContent.skip))
    skipped = [r for r in results if r.id == "DANDI.FILE_CONTENT_MISSING_SKIPPED"]
    assert len(skipped) == 1
    assert skipped[0].severity == Severity.WARNING
    assert skipped[0].message is not None
    assert "skipped" in skipped[0].message.lower()
    # No pynwb/nwbinspector errors should appear
    pynwb_errs = [r for r in results if r.origin.validator in (Validator.pynwb,)]
    assert len(pynwb_errs) == 0


@pytest.mark.ai_generated
def test_validate_broken_symlink_only_non_data(tmp_path: Path) -> None:
    """only-non-data policy skips content validators, runs path validation."""
    ds = _make_dandiset_with_broken_symlink(tmp_path)
    results = list(validate(ds, missing_file_content=MissingFileContent.only_non_data))
    # Should have a partial-skip warning
    partial = [r for r in results if r.id == "DANDI.FILE_CONTENT_MISSING_PARTIAL"]
    assert len(partial) == 1
    assert partial[0].severity == Severity.WARNING
    # No pynwb/nwbinspector errors
    pynwb_errs = [r for r in results if r.origin.validator in (Validator.pynwb,)]
    assert len(pynwb_errs) == 0


@pytest.mark.ai_generated
def test_validate_broken_symlink_real_file_still_validated(tmp_path: Path) -> None:
    """When a real NWB file coexists with broken symlinks, normal validation
    still runs on the real file under all policies."""
    ds = _make_dandiset_with_broken_symlink(tmp_path, include_real_nwb=True)

    for policy in (MissingFileContent.skip, MissingFileContent.only_non_data):
        results = list(validate(ds, missing_file_content=policy))

        # The real file (sub-002.nwb) must have been validated by pynwb or
        # nwbinspector — look for any result referencing it.
        real_file = tmp_path / "sub-002" / "sub-002.nwb"
        real_results = [
            r for r in results if r.path is not None and r.path == real_file
        ]
        assert len(real_results) > 0, (
            f"policy={policy.value}: expected validation results for the real "
            f"NWB file at {real_file}"
        )

        # The broken symlink file must NOT have pynwb/nwbinspector results.
        broken_file = tmp_path / "sub-001" / "sub-001.nwb"
        broken_pynwb = [
            r
            for r in results
            if r.path == broken_file and r.origin.validator == Validator.pynwb
        ]
        assert (
            len(broken_pynwb) == 0
        ), f"policy={policy.value}: pynwb should not run on the broken symlink"


# ---- Tests for streaming the content of annexed files (missing_file_content=stream) ----


@pytest.fixture
def streamable_dandiset(
    range_http_server: tuple[RangeHTTPServer, str], simple3_nwb: Path, tmp_path: Path
) -> tuple[Path, RangeHTTPServer]:
    """A git-annex dandiset looking like a DataLad clone without fetched content.

    ``sub-001/sub-001.nwb`` is an annexed copy of *simple3_nwb* whose content
    is served by the HTTP server, and ``sub-001/sub-001_video.mp4`` an annexed
    video registered at a URL that is never read (only the size recorded in
    its key is needed).
    """
    skipif.no_git_annex()
    pytest.importorskip("datalad_fuse.fsspec")
    server, base_url = range_http_server
    shutil.copy(simple3_nwb, tmp_path / "served" / "content.nwb")
    video = tmp_path / "video.mp4"
    video.write_bytes(b"not really a video")
    ds = tmp_path / "ds"
    make_git_annex_dandiset(
        ds,
        {
            "sub-001/sub-001.nwb": (simple3_nwb, f"{base_url}/content.nwb"),
            "sub-001/sub-001_video.mp4": (video, f"{base_url}/never-read.mp4"),
        },
    )
    return ds, server


def _content_results(results: list[ValidationResult], name: str) -> list[tuple]:
    """Path-independent summary of the results for the file called *name*."""
    return sorted(
        (r.id, r.severity, r.origin.validator, r.message)
        for r in results
        if r.path is not None
        and r.path.name == name
        and r.id != "DANDI.FILE_CONTENT_STREAMED"
    )


@pytest.mark.ai_generated
def test_validate_stream(
    streamable_dandiset: tuple[Path, RangeHTTPServer],
    simple3_nwb: Path,
    tmp_path: Path,
) -> None:
    """stream policy validates the content of annexed files with datalad-fuse."""
    ds, server = streamable_dandiset
    results = list(validate(ds, missing_file_content=MissingFileContent.stream))

    streamed = [r for r in results if r.id == "DANDI.FILE_CONTENT_STREAMED"]
    assert sorted(r.path.name for r in streamed if r.path is not None) == [
        "sub-001.nwb",
        "sub-001_video.mp4",
    ]
    assert all(r.severity == Severity.INFO for r in streamed)
    assert not [r for r in results if r.id.startswith("DANDI.FILE_CONTENT_MISSING")]
    assert server.ranged_requests > 0

    # Validating the video only needs the size recorded in its key
    assert _content_results(results, "sub-001_video.mp4") == []

    # Content-dependent validation of the NWB file gives the same results as
    # for a regular dandiset containing the file itself
    local = tmp_path / "local"
    (local / "sub-001").mkdir(parents=True)
    shutil.copy(ds / dandiset_metadata_file, local / dandiset_metadata_file)
    shutil.copy(simple3_nwb, local / "sub-001" / "sub-001.nwb")
    expected = list(validate(local))
    # simple3_nwb lacks a subject_id, which only content-based checks notice
    assert any(r.origin.validator == Validator.nwbinspector for r in expected)
    assert _content_results(results, "sub-001.nwb") == _content_results(
        expected, "sub-001.nwb"
    )


@pytest.mark.ai_generated
@pytest.mark.skipif(
    os.environ.get("DANDI_CACHE") == "ignore", reason="the validation cache is disabled"
)
def test_validate_stream_cached_by_key(
    streamable_dandiset: tuple[Path, RangeHTTPServer],
) -> None:
    """pynwb validation results of a streamed file are cached under its annex key."""
    ds, server = streamable_dandiset
    nwb = ds / "sub-001" / "sub-001.nwb"
    readable = get_annexed_readable(nwb)
    assert readable is not None
    results = pynwb_validate(nwb, readable=readable)
    assert not [r for r in results if r.id == "pynwb.GENERIC"]
    requests = server.ranged_requests
    assert requests > 0
    # Served from the cache, without the content being read again
    assert pynwb_validate(nwb, readable=get_annexed_readable(nwb)) == results
    assert server.ranged_requests == requests


@pytest.mark.ai_generated
def test_validate_stream_not_streamable(tmp_path: Path) -> None:
    """stream policy emits an error for a broken symlink that cannot be streamed."""
    pytest.importorskip("datalad_fuse.fsspec")
    skipif.no_git_annex()
    ds = _make_dandiset_with_broken_symlink(tmp_path)
    results = list(validate(ds, missing_file_content=MissingFileContent.stream))
    errs = [r for r in results if r.id == "DANDI.FILE_CONTENT_MISSING"]
    assert len(errs) == 1
    assert errs[0].severity == Severity.ERROR
    assert errs[0].message is not None
    assert "cannot be streamed" in errs[0].message
    assert not [r for r in results if r.id == "DANDI.FILE_CONTENT_STREAMED"]
    assert not [
        r
        for r in results
        if r.origin.validator in (Validator.pynwb, Validator.nwbinspector)
    ]


@pytest.mark.ai_generated
def test_validate_stream_unreadable_url(
    streamable_dandiset: tuple[Path, RangeHTTPServer], tmp_path: Path
) -> None:
    """A registered URL that cannot be read yields errors, not an exception."""
    ds, _ = streamable_dandiset
    (tmp_path / "served" / "content.nwb").unlink()
    results = list(validate(ds, missing_file_content=MissingFileContent.stream))
    nwb = ds / "sub-001" / "sub-001.nwb"
    assert [
        r for r in results if r.path == nwb and r.id == "DANDI.FILE_CONTENT_STREAMED"
    ]
    errs = [r for r in results if r.path == nwb and r.severity == Severity.ERROR]
    assert {r.origin.validator for r in errs} == {
        Validator.pynwb,
        Validator.nwbinspector,
    }


@pytest.mark.ai_generated
def test_validate_stream_requires_datalad_fuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("dandi.validate._core.find_spec", lambda name: None)
    with pytest.raises(RuntimeError, match=r"dandi\[datalad\]"):
        list(validate(tmp_path, missing_file_content=MissingFileContent.stream))
