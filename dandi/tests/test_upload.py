import os
from pathlib import Path
from shutil import copyfile, rmtree
from typing import Any, Dict

import numpy as np
import pynwb
import pytest
from pytest_mock import MockerFixture
import zarr

from .fixtures import SampleDandiset
from .test_helpers import assert_dirtrees_eq
from ..consts import ZARR_MIME_TYPE, dandiset_metadata_file
from ..dandiapi import AssetType, RemoteBlobAsset, RemoteZarrAsset
from ..dandiset import APIDandiset
from ..download import download
from ..exceptions import NotFoundError
from ..files import LocalFileAsset
from ..pynwb_utils import make_nwb_file
from ..utils import list_paths, yaml_dump


def test_upload_download(
    new_dandiset: SampleDandiset, organized_nwb_dir: str, tmp_path: Path
) -> None:
    d = new_dandiset.dandiset
    dspath = new_dandiset.dspath
    (nwb_file,) = [
        p for p in list_paths(organized_nwb_dir) if p.name != dandiset_metadata_file
    ]
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
    ds_orig = APIDandiset(dspath)
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
        text_dandiset.upload(existing="error")
    iter_upload_spy.assert_not_called()


def test_upload_extant_skip(
    mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing="skip")
    iter_upload_spy.assert_not_called()


@pytest.mark.parametrize("existing", ["overwrite", "refresh"])
def test_upload_extant_eq_overwrite(
    existing: str, mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing=existing)
    iter_upload_spy.assert_not_called()


@pytest.mark.parametrize("existing", ["overwrite", "refresh"])
def test_upload_extant_neq_overwrite(
    existing: str, mocker: MockerFixture, text_dandiset: SampleDandiset, tmp_path: Path
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
    text_dandiset.upload(existing="refresh")
    iter_upload_spy.assert_not_called()


def test_upload_extant_force(
    mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing="force")
    iter_upload_spy.assert_called()


def test_upload_extant_bad_existing(
    mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing="foobar")
    iter_upload_spy.assert_not_called()


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


@pytest.mark.parametrize("confirm", [True, False])
def test_upload_sync(
    confirm: bool, mocker: MockerFixture, text_dandiset: SampleDandiset
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
    bids_dandiset_invalid.upload(existing="force")
    iter_upload_spy.assert_not_called()
    # Does validation ignoring work?
    bids_dandiset_invalid.upload(existing="force", validation="ignore")
    iter_upload_spy.assert_called()
    # Check existence of assets:
    dandiset = bids_dandiset_invalid.dandiset
    dandiset.get_asset_by_path("dataset_description.json")


def test_upload_bids_validation_ignore(
    mocker: MockerFixture, bids_dandiset: SampleDandiset
) -> None:
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    bids_dandiset.upload(existing="force", validation="ignore")
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


def test_upload_bids(mocker: MockerFixture, bids_dandiset: SampleDandiset) -> None:
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    bids_dandiset.upload(existing="force")
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


def test_upload_sync_zarr(mocker, zarr_dandiset):
    rmtree(zarr_dandiset.dspath / "sample.zarr")
    zarr.save(zarr_dandiset.dspath / "identity.zarr", np.eye(5))
    confirm_mock = mocker.patch("click.confirm", return_value=True)
    zarr_dandiset.upload(sync=True)
    confirm_mock.assert_called_with("Delete 1 asset on server?")
    zarr_dandiset.dandiset.get_asset_by_path("identity.zarr")
    with pytest.raises(NotFoundError):
        zarr_dandiset.dandiset.get_asset_by_path("sample.zarr")


def test_upload_invalid_metadata(
    new_dandiset: SampleDandiset, simple1_nwb_metadata: Dict[str, Any]
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
    new_dandiset.upload(validation="skip")
    rmtree(zf)
    zf.mkdir()
    (zf / "unchanged.txt").write_text("This is will not change.\n")
    (zf / "changed-contents.txt").write_text("This is text version #2.\n")
    (zf / "changed-size.txt").write_text("This is a test of the upload code.\n")
    (zf / "changed-type").write_text("This is now a file.\n")
    new_dandiset.upload(validation="skip")
    download(new_dandiset.dandiset.version_api_url, tmp_path)
    assert_dirtrees_eq(zf, tmp_path / new_dandiset.dandiset_id / "sample.zarr")


def test_upload_different_zarr_file_to_parent_dir(
    tmp_path: Path, new_dandiset: SampleDandiset
) -> None:
    zf = new_dandiset.dspath / "sample.zarr"
    zf.mkdir()
    (zf / "foo").write_text("This is a file.\n")
    new_dandiset.upload(validation="skip")
    rmtree(zf)
    zf.mkdir()
    (zf / "foo").mkdir()
    (zf / "foo" / "bar").write_text("This is under what used to be a file.\n")
    new_dandiset.upload(validation="skip")
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
    assert not (asset.filetree / "empty").exists()
