from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import os
from pathlib import Path
from shutil import copyfile, rmtree
from typing import Any
from unittest.mock import Mock
from urllib.parse import urlparse

import numpy as np
import pynwb
import pytest
from pytest_mock import MockerFixture
import requests
import zarr

from dandi.tests.test_bids_validator_deno.test_validator import mock_bids_validate

from .fixtures import SampleDandiset, sweep_embargo
from .test_helpers import assert_dirtrees_eq
from ..consts import (
    DOWNLOAD_SUFFIX,
    ZARR_MIME_TYPE,
    EmbargoStatus,
    dandiset_metadata_file,
)
from ..dandiapi import AssetType, RemoteBlobAsset, RemoteZarrAsset, RESTFullAPIClient
from ..dandiset import Dandiset
from ..download import download
from ..exceptions import NotFoundError, UploadError
from ..files import LocalFileAsset
from ..pynwb_utils import make_nwb_file
from ..upload import UploadExisting, UploadValidation
from ..utils import list_paths, yaml_dump


def test_upload_download(
    new_dandiset: SampleDandiset, organized_nwb_dir: Path, tmp_path: Path
) -> None:
    d = new_dandiset.dandiset
    dspath = new_dandiset.dspath
    (nwb_file,) = (
        p for p in list_paths(organized_nwb_dir) if p.name != dandiset_metadata_file
    )
    assert nwb_file.suffix == ".nwb"
    parent, name = nwb_file.relative_to(organized_nwb_dir).parts
    (dspath / parent).mkdir()
    copyfile(nwb_file, dspath / parent / name)
    new_dandiset.upload()
    download(d.version_api_url, tmp_path)
    assert list_paths(tmp_path) == [
        tmp_path / d.identifier / dandiset_metadata_file,
        tmp_path / d.identifier / parent / name,
    ]


def test_upload_dandiset_metadata(new_dandiset: SampleDandiset) -> None:
    # For now let's "manually" populate dandiset.yaml in that downloaded location
    # which is missing due to https://github.com/dandi/dandi-api/issues/63
    d = new_dandiset.dandiset
    dspath = new_dandiset.dspath
    ds_orig = Dandiset(dspath)
    ds_metadata = ds_orig.metadata
    assert ds_metadata is not None
    ds_metadata["description"] = "very long"
    ds_metadata["name"] = "shorty"
    (dspath / dandiset_metadata_file).write_text(yaml_dump(ds_metadata))
    new_dandiset.upload(
        paths=[dspath / dandiset_metadata_file], upload_dandiset_metadata=True
    )
    d.refresh()
    assert d.version.name == "shorty"


def test_upload_extant_existing(
    mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    with pytest.raises(FileExistsError):
        text_dandiset.upload(existing=UploadExisting.ERROR)
    iter_upload_spy.assert_not_called()


def test_upload_extant_skip(
    mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing=UploadExisting.SKIP)
    iter_upload_spy.assert_not_called()


@pytest.mark.parametrize("existing", [UploadExisting.OVERWRITE, UploadExisting.REFRESH])
def test_upload_extant_eq_overwrite(
    existing: UploadExisting, mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing=existing)
    iter_upload_spy.assert_not_called()


@pytest.mark.parametrize("existing", [UploadExisting.OVERWRITE, UploadExisting.REFRESH])
def test_upload_extant_neq_overwrite(
    existing: UploadExisting,
    mocker: MockerFixture,
    text_dandiset: SampleDandiset,
    tmp_path: Path,
) -> None:
    (text_dandiset.dspath / "file.txt").write_text("This is different text.\n")
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing=existing)
    iter_upload_spy.assert_called()
    download(text_dandiset.dandiset.version_api_url, tmp_path)
    assert (
        tmp_path / text_dandiset.dandiset_id / "file.txt"
    ).read_text() == "This is different text.\n"


def test_upload_extant_old_refresh(
    mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    (text_dandiset.dspath / "file.txt").write_text("This is different text.\n")
    os.utime(text_dandiset.dspath / "file.txt", times=(0, 0))
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing=UploadExisting.REFRESH)
    iter_upload_spy.assert_not_called()


def test_upload_extant_force(
    mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing=UploadExisting.FORCE)
    iter_upload_spy.assert_called()


@pytest.mark.parametrize(
    "contents",
    [
        pytest.param(
            b"",
            marks=pytest.mark.xfail(
                reason="https://github.com/dandi/dandi-api/issues/168"
            ),
        ),
        b"x",
    ],
)
def test_upload_download_small_file(
    contents: bytes, new_dandiset: SampleDandiset, tmp_path: Path
) -> None:
    d = new_dandiset.dandiset
    dandiset_id = d.identifier
    dspath = new_dandiset.dspath
    (dspath / "file.txt").write_bytes(contents)
    new_dandiset.upload(allow_any_path=True)
    download(d.version_api_url, tmp_path)
    assert list_paths(tmp_path) == [
        tmp_path / dandiset_id / dandiset_metadata_file,
        tmp_path / dandiset_id / "file.txt",
    ]
    assert (tmp_path / dandiset_id / "file.txt").read_bytes() == contents


@sweep_embargo
@pytest.mark.parametrize("confirm", [True, False])
def test_upload_sync(
    confirm: bool, mocker: MockerFixture, text_dandiset: SampleDandiset, embargo: bool
) -> None:
    (text_dandiset.dspath / "file.txt").unlink()
    confirm_mock = mocker.patch("click.confirm", return_value=confirm)
    text_dandiset.upload(sync=True)
    confirm_mock.assert_called_with("Delete 1 asset on server?")
    if confirm:
        with pytest.raises(NotFoundError):
            text_dandiset.dandiset.get_asset_by_path("file.txt")
    else:
        text_dandiset.dandiset.get_asset_by_path("file.txt")


def test_upload_sync_folder(
    mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    (text_dandiset.dspath / "file.txt").unlink()
    (text_dandiset.dspath / "subdir2" / "banana.txt").unlink()
    confirm_mock = mocker.patch("click.confirm", return_value=True)
    text_dandiset.upload(paths=[text_dandiset.dspath / "subdir2"], sync=True)
    confirm_mock.assert_called_with("Delete 1 asset on server?")
    text_dandiset.dandiset.get_asset_by_path("file.txt")
    with pytest.raises(NotFoundError):
        text_dandiset.dandiset.get_asset_by_path("subdir2/banana.txt")


def test_upload_bids_invalid(
    mocker: MockerFixture, bids_dandiset_invalid: SampleDandiset
) -> None:
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    with pytest.raises(UploadError):
        bids_dandiset_invalid.upload(existing=UploadExisting.FORCE)
    iter_upload_spy.assert_not_called()
    # Does validation ignoring work?
    bids_dandiset_invalid.upload(
        existing=UploadExisting.FORCE, validation=UploadValidation.IGNORE
    )
    iter_upload_spy.assert_called()
    # Check existence of assets:
    dandiset = bids_dandiset_invalid.dandiset
    dandiset.get_asset_by_path("dataset_description.json")


def test_upload_bids_validation_ignore(
    mocker: MockerFixture, bids_dandiset: SampleDandiset
) -> None:
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    bids_dandiset.upload(
        existing=UploadExisting.FORCE, validation=UploadValidation.IGNORE
    )
    # Check whether upload was run
    iter_upload_spy.assert_called()
    # Check existence of assets:
    dandiset = bids_dandiset.dandiset
    # file we created?
    dandiset.get_asset_by_path("CHANGES")
    # BIDS descriptor file?
    dandiset.get_asset_by_path("dataset_description.json")
    # actual data file?
    dandiset.get_asset_by_path("sub-Sub1/anat/sub-Sub1_T1w.nii.gz")


def test_upload_bids_metadata(
    bids_dandiset: SampleDandiset, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test the uploading of metadata of a dataset at
        https://github.com/bids-standard/bids-examples
    """
    from dandi.files import bids

    monkeypatch.setattr(bids, "bids_validate", mock_bids_validate)

    bids_dandiset.upload(existing=UploadExisting.FORCE)
    dandiset = bids_dandiset.dandiset
    # Automatically check all files, heuristic should remain very BIDS-stable
    for asset in dandiset.get_assets(order="path"):
        apath = asset.path
        if "sub-" in apath:
            metadata = dandiset.get_asset_by_path(apath).get_metadata()
            # Hard-coded check for the subject identifier set in the fixture:
            assert metadata.wasAttributedTo is not None
            assert metadata.wasAttributedTo[0].identifier == "Sub1"


def test_upload_bids(
    mocker: MockerFixture,
    bids_dandiset: SampleDandiset,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test the uploading of a dataset at
        https://github.com/bids-standard/bids-examples
    """
    from dandi.files import bids

    monkeypatch.setattr(bids, "bids_validate", mock_bids_validate)

    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    bids_dandiset.upload(existing=UploadExisting.FORCE)
    # Check whether upload was run
    iter_upload_spy.assert_called()
    # Check existence of assets:
    dandiset = bids_dandiset.dandiset
    # file we created?
    dandiset.get_asset_by_path("README")
    # BIDS descriptor file?
    dandiset.get_asset_by_path("dataset_description.json")
    # actual data file?
    dandiset.get_asset_by_path("sub-Sub1/anat/sub-Sub1_T1w.nii.gz")


def test_upload_bids_non_nwb_file(bids_dandiset: SampleDandiset) -> None:
    bids_dandiset.upload([bids_dandiset.dspath / "README"])
    assert [asset.path for asset in bids_dandiset.dandiset.get_assets()] == ["README"]


@sweep_embargo
def test_upload_sync_zarr(
    mocker: MockerFixture, zarr_dandiset: SampleDandiset, embargo: bool
) -> None:
    assert zarr_dandiset.dandiset.embargo_status == (
        EmbargoStatus.EMBARGOED if embargo else EmbargoStatus.OPEN
    )
    rmtree(zarr_dandiset.dspath / "sample.zarr")
    zarr.save(zarr_dandiset.dspath / "identity.zarr", np.eye(5))
    confirm_mock = mocker.patch("click.confirm", return_value=True)
    zarr_dandiset.upload(sync=True)
    confirm_mock.assert_called_with("Delete 1 asset on server?")
    zarr_dandiset.dandiset.get_asset_by_path("identity.zarr")
    with pytest.raises(NotFoundError):
        zarr_dandiset.dandiset.get_asset_by_path("sample.zarr")


def test_upload_invalid_metadata(
    new_dandiset: SampleDandiset, simple1_nwb_metadata: dict[str, Any]
) -> None:
    make_nwb_file(
        new_dandiset.dspath / "broken.nwb",
        subject=pynwb.file.Subject(
            subject_id="mouse001",
            age="XLII anni",
            sex="yes",
            species="unicorn",
        ),
        **simple1_nwb_metadata,
    )
    with pytest.raises(UploadError):
        new_dandiset.upload()
    with pytest.raises(NotFoundError):
        new_dandiset.dandiset.get_asset_by_path("broken.nwb")


def test_upload_zarr(new_dandiset: SampleDandiset) -> None:
    zarr.save(
        new_dandiset.dspath / "sample.zarr", np.arange(1000), np.arange(1000, 0, -1)
    )
    new_dandiset.upload()
    (asset,) = new_dandiset.dandiset.get_assets()
    assert isinstance(asset, RemoteZarrAsset)
    assert asset.asset_type is AssetType.ZARR
    assert asset.path == "sample.zarr"
    # Test that uploading again without any changes works:
    new_dandiset.upload()


# identical to above, but different scenaior/fixture and path. TODO: avoid duplication
def test_upload_bids_zarr(
    bids_zarr_dandiset: SampleDandiset, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test the uploading of a dataset based on one of the datasets at
        https://github.com/bids-standard/bids-examples
    """
    from dandi.files import bids

    monkeypatch.setattr(bids, "bids_validate", mock_bids_validate)

    bids_zarr_dandiset.upload()
    assets = list(bids_zarr_dandiset.dandiset.get_assets())
    assert len(assets) > 10  # it is a bigish dataset
    (asset,) = (a for a in assets if a.path.endswith(".zarr"))
    assert isinstance(asset, RemoteZarrAsset)
    assert asset.asset_type is AssetType.ZARR
    assert asset.path.endswith(".zarr")
    # Test that uploading again without any changes works:
    bids_zarr_dandiset.upload()


def test_upload_different_zarr(tmp_path: Path, zarr_dandiset: SampleDandiset) -> None:
    asset = zarr_dandiset.dandiset.get_asset_by_path("sample.zarr")
    assert isinstance(asset, RemoteZarrAsset)
    zarr_id = asset.zarr
    rmtree(zarr_dandiset.dspath / "sample.zarr")
    zarr.save(zarr_dandiset.dspath / "sample.zarr", np.eye(5))
    zarr_dandiset.upload()
    asset = zarr_dandiset.dandiset.get_asset_by_path("sample.zarr")
    assert isinstance(asset, RemoteZarrAsset)
    assert asset.zarr == zarr_id
    download(zarr_dandiset.dandiset.version_api_url, tmp_path)
    assert_dirtrees_eq(
        zarr_dandiset.dspath / "sample.zarr",
        tmp_path / zarr_dandiset.dandiset_id / "sample.zarr",
    )


def test_upload_loose_zarr(tmp_path: Path, zarr_dandiset: SampleDandiset) -> None:
    asset = zarr_dandiset.dandiset.get_asset_by_path("sample.zarr")
    assert isinstance(asset, RemoteZarrAsset)
    zarr_id = asset.zarr
    asset.delete()
    rmtree(zarr_dandiset.dspath / "sample.zarr")
    zarr.save(zarr_dandiset.dspath / "sample.zarr", np.eye(5))
    zarr_dandiset.upload()
    asset = zarr_dandiset.dandiset.get_asset_by_path("sample.zarr")
    assert isinstance(asset, RemoteZarrAsset)
    assert asset.zarr == zarr_id
    download(zarr_dandiset.dandiset.version_api_url, tmp_path)
    assert_dirtrees_eq(
        zarr_dandiset.dspath / "sample.zarr",
        tmp_path / zarr_dandiset.dandiset_id / "sample.zarr",
    )


def test_upload_different_zarr_entry_conflicts(
    tmp_path: Path, new_dandiset: SampleDandiset
) -> None:
    zf = new_dandiset.dspath / "sample.zarr"
    zf.mkdir()
    (zf / "unchanged.txt").write_text("This is will not change.\n")
    (zf / "changed-contents.txt").write_text("This is text version #1.\n")
    (zf / "changed-size.txt").write_text("This is a test.\n")
    (zf / "changed-type").mkdir()
    (zf / "changed-type" / "file.txt").write_text("This is test text.\n")
    new_dandiset.upload(validation=UploadValidation.SKIP)
    rmtree(zf)
    zf.mkdir()
    (zf / "unchanged.txt").write_text("This is will not change.\n")
    (zf / "changed-contents.txt").write_text("This is text version #2.\n")
    (zf / "changed-size.txt").write_text("This is a test of the upload code.\n")
    (zf / "changed-type").write_text("This is now a file.\n")
    new_dandiset.upload(validation=UploadValidation.SKIP)
    download(new_dandiset.dandiset.version_api_url, tmp_path)
    assert_dirtrees_eq(zf, tmp_path / new_dandiset.dandiset_id / "sample.zarr")


def test_upload_different_zarr_file_to_parent_dir(
    tmp_path: Path, new_dandiset: SampleDandiset
) -> None:
    zf = new_dandiset.dspath / "sample.zarr"
    zf.mkdir()
    (zf / "foo").write_text("This is a file.\n")
    new_dandiset.upload(validation=UploadValidation.SKIP)
    rmtree(zf)
    zf.mkdir()
    (zf / "foo").mkdir()
    (zf / "foo" / "bar").write_text("This is under what used to be a file.\n")
    new_dandiset.upload(validation=UploadValidation.SKIP)
    download(new_dandiset.dandiset.version_api_url, tmp_path)
    assert_dirtrees_eq(zf, tmp_path / new_dandiset.dandiset_id / "sample.zarr")


def test_upload_nonzarr_to_zarr_path(
    tmp_path: Path, zarr_dandiset: SampleDandiset
) -> None:
    rmtree(zarr_dandiset.dspath / "sample.zarr")
    (zarr_dandiset.dspath / "sample.zarr").write_text("This is not a Zarr.\n")
    zarr_dandiset.upload(allow_any_path=True)
    (asset,) = zarr_dandiset.dandiset.get_assets()
    assert isinstance(asset, RemoteBlobAsset)
    assert asset.asset_type is AssetType.BLOB
    assert asset.path == "sample.zarr"
    assert asset.get_raw_metadata()["encodingFormat"] == "application/octet-stream"
    download(zarr_dandiset.dandiset.version_api_url, tmp_path)
    assert (
        tmp_path / zarr_dandiset.dandiset_id / "sample.zarr"
    ).read_text() == "This is not a Zarr.\n"


def test_upload_zarr_to_nonzarr_path(
    new_dandiset: SampleDandiset, tmp_path: Path
) -> None:
    d = new_dandiset.dandiset
    dspath = new_dandiset.dspath
    (dspath / "sample.zarr").write_text("This is not a Zarr.\n")
    new_dandiset.upload(allow_any_path=True)

    (asset,) = d.get_assets()
    assert isinstance(asset, RemoteBlobAsset)
    assert asset.asset_type is AssetType.BLOB
    assert asset.path == "sample.zarr"
    assert asset.get_raw_metadata()["encodingFormat"] == "application/octet-stream"

    (dspath / "sample.zarr").unlink()
    zarr.save(dspath / "sample.zarr", np.arange(1000), np.arange(1000, 0, -1))
    new_dandiset.upload(allow_any_path=True)

    (asset,) = d.get_assets()
    assert isinstance(asset, RemoteZarrAsset)
    assert asset.asset_type is AssetType.ZARR
    assert asset.path == "sample.zarr"
    assert asset.get_raw_metadata()["encodingFormat"] == ZARR_MIME_TYPE

    download(d.version_api_url, tmp_path)
    assert_dirtrees_eq(dspath / "sample.zarr", tmp_path / d.identifier / "sample.zarr")


def test_upload_zarr_with_empty_dir(new_dandiset: SampleDandiset) -> None:
    zarr.save(
        new_dandiset.dspath / "sample.zarr", np.arange(1000), np.arange(1000, 0, -1)
    )
    (new_dandiset.dspath / "sample.zarr" / "empty").mkdir()
    new_dandiset.upload()
    (asset,) = new_dandiset.dandiset.get_assets()
    assert isinstance(asset, RemoteZarrAsset)
    assert asset.asset_type is AssetType.ZARR
    assert asset.path == "sample.zarr"
    with pytest.raises(NotFoundError):
        asset.get_entry_by_path("empty")


def test_zarr_upload_403_retry(
    new_dandiset: SampleDandiset, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 403 errors during Zarr upload trigger retry with new URLs"""
    # Create test Zarr
    zarr_path = new_dandiset.dspath / "test.zarr"
    zarr.save(zarr_path, np.arange(100), np.arange(100, 0, -1))

    # Track upload attempts per URL
    upload_attempts: defaultdict[str, int] = defaultdict(int)
    original_put = RESTFullAPIClient.put

    def mock_put(self, url, **kwargs):
        # Track attempts for each URL
        urlpath = urlparse(url).path
        upload_attempts[urlpath] += 1

        # Simulate 403 error on first attempt for some files
        # Use a deterministic pattern - fail paths containing "arr_1"
        if upload_attempts[urlpath] == 1 and "arr_1" in url:
            # Create a mock 403 response
            resp = Mock(spec=requests.Response)
            resp.status_code = 403
            resp.text = "Forbidden"
            error = requests.HTTPError("403 Forbidden", response=resp)
            error.response = resp
            raise error
        # Otherwise, call the original method
        return original_put(self, url, **kwargs)

    # Apply the mock
    monkeypatch.setattr(RESTFullAPIClient, "put", mock_put)

    # Upload the Zarr
    new_dandiset.upload()

    # Verify the upload succeeded
    (asset,) = new_dandiset.dandiset.get_assets()
    assert isinstance(asset, RemoteZarrAsset)
    assert asset.asset_type is AssetType.ZARR
    assert asset.path == "test.zarr"

    # Verify that some URLs were retried (those with arr_1)
    retry_urls = [url for url, count in upload_attempts.items() if count > 1]
    assert len(retry_urls) > 0, "Expected at least one URL to be retried"

    # Verify all retried URLs contained "arr_1" (our trigger pattern)
    for url in retry_urls:
        assert "arr_1" in url, f"URL {url} was retried but shouldn't have been"

    # Verify non-arr_1 URLs were not retried
    single_attempt_urls = [url for url, count in upload_attempts.items() if count == 1]
    for url in single_attempt_urls:
        assert "arr_1" not in url, f"URL {url} should have been retried but wasn't"


@pytest.mark.ai_generated
def test_zarr_upload_400_timeout_retry(
    new_dandiset: SampleDandiset,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that 400 RequestTimeout errors trigger automatic retry via tenacity"""
    # Create test Zarr
    zarr_path = new_dandiset.dspath / "test.zarr"
    zarr.save(zarr_path, np.arange(100), np.arange(100, 0, -1))

    # Track request attempts
    request_attempts: defaultdict[str, int] = defaultdict(int)
    original_request = RESTFullAPIClient.request

    def mock_request(self, method, path, **kwargs):
        # Track attempts for each request
        urlpath = urlparse(path).path if path.startswith("http") else path
        request_attempts[urlpath] += 1

        # Simulate 400 timeout on first attempt for files containing "arr_0"
        if method == "PUT" and "arr_0" in path and request_attempts[urlpath] == 1:
            # Return a mock response that will trigger the retry_if condition
            resp = Mock(spec=requests.Response)
            resp.status_code = 400
            resp.text = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<Error><Code>RequestTimeout</Code>"
                "<Message>Your socket connection to the server "
                "was not read from or written to within the timeout period. "
                "Idle connections will be closed.</Message>"
                "<RequestId>1111111111111111</RequestId>"
                "<HostId>AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA</HostId>"
                "</Error>"
            )
            resp.headers = {}
            resp.content = resp.text.encode()
            resp.json = Mock(side_effect=ValueError("No JSON"))
            return resp

        # Otherwise, call the original method
        return original_request(self, method, path, **kwargs)

    # Apply the mock
    monkeypatch.setattr(RESTFullAPIClient, "request", mock_request)

    # Upload the Zarr
    new_dandiset.upload()

    # Verify the upload succeeded
    (asset,) = new_dandiset.dandiset.get_assets()
    assert isinstance(asset, RemoteZarrAsset)
    assert asset.asset_type is AssetType.ZARR
    assert asset.path == "test.zarr"

    # Verify that arr_0 files were retried automatically by tenacity
    # Filter for PUT requests to S3/minio (not API endpoints)
    arr_0_urls = [
        url for url in request_attempts if "arr_0" in url and "dandi-dandisets" in url
    ]
    assert len(arr_0_urls) > 0, "Expected to find arr_0 files"

    for url in arr_0_urls:
        # Each arr_0 file should have been attempted twice (initial + 1 retry)
        assert (
            request_attempts[url] == 2
        ), f"Expected {url} to be retried once, got {request_attempts[url]} attempts"

    # Verify non-arr_0 S3/minio URLs were not retried
    non_arr_0_urls = [
        url
        for url in request_attempts
        if "arr_0" not in url and "dandi-dandisets" in url and request_attempts[url] > 0
    ]
    for url in non_arr_0_urls:
        assert (
            request_attempts[url] == 1
        ), f"URL {url} should not have been retried but had {request_attempts[url]} attempts"


@pytest.mark.ai_generated
def test_upload_rejects_dandidownload_paths(
    new_dandiset: SampleDandiset, tmp_path: Path
) -> None:
    """Test that upload rejects assets with .dandidownload paths"""
    dspath = new_dandiset.dspath

    # Test 1: Regular file with .dandidownload in path
    badfile_path = dspath / f"test{DOWNLOAD_SUFFIX}" / "file.nwb"
    badfile_path.parent.mkdir(parents=True)
    make_nwb_file(
        badfile_path,
        session_description="test session",
        identifier="test123",
        session_start_time=datetime(2017, 4, 15, 12, tzinfo=timezone.utc),
        subject=pynwb.file.Subject(subject_id="test"),
    )

    with pytest.raises(
        UploadError,
        match=f"contains {DOWNLOAD_SUFFIX} path which indicates incomplete download",
    ):
        new_dandiset.upload(allow_any_path=True)

    # Clean up for next test
    rmtree(badfile_path.parent)

    # Test 2: Zarr asset with .dandidownload in internal path
    zarr_path = dspath / "test.zarr"
    zarr.save(zarr_path, np.arange(100))

    # Create a .dandidownload directory inside the zarr
    bad_zarr_path = zarr_path / f"sub{DOWNLOAD_SUFFIX}"
    bad_zarr_path.mkdir()
    (bad_zarr_path / "badfile").write_text("bad data")

    with pytest.raises(
        UploadError,
        match=f"Zarr asset contains {DOWNLOAD_SUFFIX} path which indicates incomplete download",
    ):
        new_dandiset.upload()

    # Clean up
    rmtree(bad_zarr_path)

    # Test 3: Zarr asset with .dandidownload in filename
    bad_file_in_zarr = zarr_path / f"data{DOWNLOAD_SUFFIX}"
    bad_file_in_zarr.write_text("bad data")

    with pytest.raises(
        UploadError,
        match=f"Zarr asset contains {DOWNLOAD_SUFFIX} path which indicates incomplete download",
    ):
        new_dandiset.upload()

    # Clean up
    bad_file_in_zarr.unlink()

    # Test 4: Normal zarr should upload fine after removing bad paths
    new_dandiset.upload()
    (asset,) = new_dandiset.dandiset.get_assets()
    assert isinstance(asset, RemoteZarrAsset)
    assert asset.path == "test.zarr"


@pytest.mark.ai_generated
def test_upload_rejects_dandidownload_nwb_file(new_dandiset: SampleDandiset) -> None:
    """Test that upload rejects NWB files with .dandidownload in their path"""
    dspath = new_dandiset.dspath

    # Create an NWB file with .dandidownload in its name
    bad_nwb_path = dspath / f"test{DOWNLOAD_SUFFIX}.nwb"
    make_nwb_file(
        bad_nwb_path,
        session_description="test session",
        identifier="test456",
        session_start_time=datetime(2017, 4, 15, 12, tzinfo=timezone.utc),
        subject=pynwb.file.Subject(subject_id="test"),
    )

    with pytest.raises(
        UploadError,
        match=f"contains {DOWNLOAD_SUFFIX} path which indicates incomplete download",
    ):
        new_dandiset.upload(allow_any_path=True)
