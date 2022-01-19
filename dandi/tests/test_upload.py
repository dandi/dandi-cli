import os
from pathlib import Path
from shutil import rmtree

import numpy as np
import pynwb
import pytest
import zarr

from ..consts import DRAFT, ZARR_MIME_TYPE, dandiset_metadata_file
from ..dandiapi import RemoteBlobAsset, RemoteZarrAsset
from ..download import download
from ..exceptions import NotFoundError
from ..files import LocalFileAsset
from ..pynwb_utils import make_nwb_file
from ..upload import upload
from ..utils import assert_dirtrees_eq, list_paths


def test_new_upload_download(local_dandi_api, monkeypatch, organized_nwb_dir, tmp_path):
    d = local_dandi_api.client.create_dandiset("Test Dandiset", {})
    dandiset_id = d.identifier
    (nwb_file,) = organized_nwb_dir.glob(f"*{os.sep}*.nwb")
    (organized_nwb_dir / dandiset_metadata_file).write_text(
        f"identifier: '{dandiset_id}'\n"
    )
    monkeypatch.chdir(organized_nwb_dir)
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api.api_key)
    upload(paths=[], dandi_instance=local_dandi_api.instance_id, devel_debug=True)
    download(d.version_api_url, tmp_path)
    (nwb_file2,) = tmp_path.glob(f"{dandiset_id}{os.sep}*{os.sep}*.nwb")
    assert nwb_file.name == nwb_file2.name
    assert nwb_file.parent.name == nwb_file2.parent.name

    #
    # test updating dandiset metadata record while at it
    # For now let's "manually" populate dandiset.yaml in that downloaded location
    # which is missing due to https://github.com/dandi/dandi-api/issues/63
    from ..dandiset import APIDandiset
    from ..utils import yaml_dump

    ds_orig = APIDandiset(organized_nwb_dir)
    ds_metadata = ds_orig.metadata
    ds_metadata["description"] = "very long"
    ds_metadata["name"] = "shorty"

    monkeypatch.chdir(tmp_path / dandiset_id)
    Path(dandiset_metadata_file).write_text(yaml_dump(ds_metadata))
    upload(
        paths=[dandiset_metadata_file],
        dandi_instance=local_dandi_api.instance_id,
        devel_debug=True,
        upload_dandiset_metadata=True,
    )

    d = local_dandi_api.client.get_dandiset(dandiset_id, DRAFT)
    assert d.version.name == "shorty"


def test_new_upload_extant_existing(mocker, text_dandiset):
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    with pytest.raises(FileExistsError):
        text_dandiset.upload(existing="error")
    iter_upload_spy.assert_not_called()


def test_new_upload_extant_skip(mocker, text_dandiset):
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing="skip")
    iter_upload_spy.assert_not_called()


@pytest.mark.parametrize("existing", ["overwrite", "refresh"])
def test_new_upload_extant_eq_overwrite(existing, mocker, text_dandiset):
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing=existing)
    iter_upload_spy.assert_not_called()


@pytest.mark.parametrize("existing", ["overwrite", "refresh"])
def test_new_upload_extant_neq_overwrite(existing, mocker, text_dandiset, tmp_path):
    dandiset_id = text_dandiset.dandiset_id
    (text_dandiset.dspath / "file.txt").write_text("This is different text.\n")
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing=existing)
    iter_upload_spy.assert_called()
    download(text_dandiset.dandiset.version_api_url, tmp_path)
    assert (
        tmp_path / dandiset_id / "file.txt"
    ).read_text() == "This is different text.\n"


def test_new_upload_extant_old_refresh(mocker, text_dandiset):
    (text_dandiset.dspath / "file.txt").write_text("This is different text.\n")
    os.utime(text_dandiset.dspath / "file.txt", times=(0, 0))
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing="refresh")
    iter_upload_spy.assert_not_called()


def test_new_upload_extant_force(mocker, text_dandiset):
    iter_upload_spy = mocker.spy(LocalFileAsset, "iter_upload")
    text_dandiset.upload(existing="force")
    iter_upload_spy.assert_called()


def test_new_upload_extant_bad_existing(mocker, text_dandiset):
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
def test_upload_download_small_file(contents, local_dandi_api, monkeypatch, tmp_path):
    client = local_dandi_api.client
    d = client.create_dandiset("Small Dandiset", {})
    dandiset_id = d.identifier
    dspath = tmp_path / "upload"
    dspath.mkdir()
    (dspath / dandiset_metadata_file).write_text(f"identifier: '{dandiset_id}'\n")
    (dspath / "file.txt").write_bytes(contents)
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api.api_key)
    upload(
        paths=[],
        dandiset_path=dspath,
        dandi_instance=local_dandi_api.instance_id,
        devel_debug=True,
        allow_any_path=True,
    )
    download_dir = tmp_path / "download"
    download_dir.mkdir()
    download(d.version_api_url, download_dir)
    assert list_paths(download_dir) == [
        download_dir / dandiset_id / dandiset_metadata_file,
        download_dir / dandiset_id / "file.txt",
    ]
    assert (download_dir / dandiset_id / "file.txt").read_bytes() == contents


@pytest.mark.parametrize("confirm", [True, False])
def test_upload_sync(confirm, mocker, text_dandiset):
    (text_dandiset.dspath / "file.txt").unlink()
    confirm_mock = mocker.patch("click.confirm", return_value=confirm)
    text_dandiset.upload(sync=True)
    confirm_mock.assert_called_with("Delete 1 asset on server?")
    if confirm:
        with pytest.raises(NotFoundError):
            text_dandiset.dandiset.get_asset_by_path("file.txt")
    else:
        text_dandiset.dandiset.get_asset_by_path("file.txt")


def test_upload_sync_folder(mocker, text_dandiset):
    (text_dandiset.dspath / "file.txt").unlink()
    (text_dandiset.dspath / "subdir2" / "banana.txt").unlink()
    confirm_mock = mocker.patch("click.confirm", return_value=True)
    text_dandiset.upload(paths=[text_dandiset.dspath / "subdir2"], sync=True)
    confirm_mock.assert_called_with("Delete 1 asset on server?")
    text_dandiset.dandiset.get_asset_by_path("file.txt")
    with pytest.raises(NotFoundError):
        text_dandiset.dandiset.get_asset_by_path("subdir2/banana.txt")


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
    local_dandi_api, monkeypatch, simple1_nwb_metadata, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api.api_key)
    d = local_dandi_api.client.create_dandiset("Broken Dandiset", {})
    nwb_file = "broken.nwb"
    make_nwb_file(
        nwb_file,
        subject=pynwb.file.Subject(
            subject_id="mouse001",
            age="XLII anni",
            sex="yes",
            species="unicorn",
        ),
        **simple1_nwb_metadata,
    )
    Path(dandiset_metadata_file).write_text(f"identifier: '{d.identifier}'\n")
    upload(paths=[], dandi_instance=local_dandi_api.instance_id, devel_debug=True)
    with pytest.raises(NotFoundError):
        d.get_asset_by_path(nwb_file)


def test_upload_zarr(local_dandi_api, monkeypatch, tmp_path):
    d = local_dandi_api.client.create_dandiset("Test Dandiset", {})
    dandiset_id = d.identifier
    (tmp_path / dandiset_metadata_file).write_text(f"identifier: '{dandiset_id}'\n")
    zarr.save(tmp_path / "sample.zarr", np.arange(1000), np.arange(1000, 0, -1))
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api.api_key)
    upload(
        paths=[],
        dandiset_path=tmp_path,
        dandi_instance=local_dandi_api.instance_id,
        devel_debug=True,
    )
    (asset,) = d.get_assets()
    assert isinstance(asset, RemoteZarrAsset)
    assert asset.is_zarr()
    assert not asset.is_blob()
    assert asset.path == "sample.zarr"


def test_upload_different_zarr(tmp_path, zarr_dandiset):
    rmtree(zarr_dandiset.dspath / "sample.zarr")
    zarr.save(zarr_dandiset.dspath / "sample.zarr", np.eye(5))
    zarr_dandiset.upload()
    download(zarr_dandiset.dandiset.version_api_url, tmp_path)
    assert_dirtrees_eq(
        zarr_dandiset.dspath / "sample.zarr",
        tmp_path / zarr_dandiset.dandiset_id / "sample.zarr",
    )


def test_upload_nonzarr_to_zarr_path(tmp_path, zarr_dandiset):
    rmtree(zarr_dandiset.dspath / "sample.zarr")
    (zarr_dandiset.dspath / "sample.zarr").write_text("This is not a Zarr.\n")
    zarr_dandiset.upload(allow_any_path=True)
    (asset,) = zarr_dandiset.dandiset.get_assets()
    assert isinstance(asset, RemoteBlobAsset)
    assert asset.is_blob()
    assert not asset.is_zarr()
    assert asset.path == "sample.zarr"
    assert asset.get_raw_metadata()["encodingFormat"] == "application/octet-stream"
    download(zarr_dandiset.dandiset.version_api_url, tmp_path)
    assert (
        tmp_path / zarr_dandiset.dandiset_id / "sample.zarr"
    ).read_text() == "This is not a Zarr.\n"


def test_upload_zarr_to_nonzarr_path(local_dandi_api, monkeypatch, tmp_path):
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api.api_key)
    d = local_dandi_api.client.create_dandiset("Test Dandiset", {})
    dandiset_id = d.identifier
    dspath = tmp_path / "dandiset"
    dspath.mkdir()
    (dspath / dandiset_metadata_file).write_text(f"identifier: '{dandiset_id}'\n")
    (dspath / "sample.zarr").write_text("This is not a Zarr.\n")
    upload(
        paths=[],
        dandiset_path=dspath,
        dandi_instance=local_dandi_api.instance_id,
        devel_debug=True,
        allow_any_path=True,
    )

    (asset,) = d.get_assets()
    assert isinstance(asset, RemoteBlobAsset)
    assert asset.is_blob()
    assert not asset.is_zarr()
    assert asset.path == "sample.zarr"
    assert asset.get_raw_metadata()["encodingFormat"] == "application/octet-stream"

    (dspath / "sample.zarr").unlink()
    zarr.save(dspath / "sample.zarr", np.arange(1000), np.arange(1000, 0, -1))
    upload(
        paths=[],
        dandiset_path=dspath,
        dandi_instance=local_dandi_api.instance_id,
        devel_debug=True,
        allow_any_path=True,
    )

    (asset,) = d.get_assets()
    assert isinstance(asset, RemoteZarrAsset)
    assert asset.is_zarr()
    assert not asset.is_blob()
    assert asset.path == "sample.zarr"
    assert asset.get_raw_metadata()["encodingFormat"] == ZARR_MIME_TYPE

    (tmp_path / "download").mkdir()
    download(d.version_api_url, tmp_path / "download")
    assert_dirtrees_eq(
        dspath / "sample.zarr",
        tmp_path / "download" / dandiset_id / "sample.zarr",
    )


def test_upload_zarr_with_empty_dir(local_dandi_api, monkeypatch, tmp_path):
    d = local_dandi_api.client.create_dandiset("Test Dandiset", {})
    dandiset_id = d.identifier
    (tmp_path / dandiset_metadata_file).write_text(f"identifier: '{dandiset_id}'\n")
    zarr.save(tmp_path / "sample.zarr", np.arange(1000), np.arange(1000, 0, -1))
    (tmp_path / "sample.zarr" / "empty").mkdir()
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api.api_key)
    upload(
        paths=[],
        dandiset_path=tmp_path,
        dandi_instance=local_dandi_api.instance_id,
        devel_debug=True,
    )
    (asset,) = d.get_assets()
    assert isinstance(asset, RemoteZarrAsset)
    assert asset.is_zarr()
    assert not asset.is_blob()
    assert asset.path == "sample.zarr"
    assert not (asset.filetree / "empty").exists()
