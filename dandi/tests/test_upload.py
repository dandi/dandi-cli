import os
from pathlib import Path

import pytest

from ..consts import DRAFT, dandiset_metadata_file
from ..dandiapi import RemoteDandiset
from ..download import download
from ..exceptions import NotFoundError
from ..upload import upload
from ..utils import find_files


def test_new_upload_download(local_dandi_api, monkeypatch, organized_nwb_dir, tmp_path):
    d = local_dandi_api["client"].create_dandiset("Test Dandiset", {})
    dandiset_id = d.identifier
    (nwb_file,) = organized_nwb_dir.glob(f"*{os.sep}*.nwb")
    (organized_nwb_dir / dandiset_metadata_file).write_text(
        f"identifier: '{dandiset_id}'\n"
    )
    monkeypatch.chdir(organized_nwb_dir)
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    upload(paths=[], dandi_instance=local_dandi_api["instance_id"], devel_debug=True)
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/draft",
        tmp_path,
    )
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
        dandi_instance=local_dandi_api["instance_id"],
        devel_debug=True,
        upload_dandiset_metadata=True,
    )

    d = local_dandi_api["client"].get_dandiset(dandiset_id, DRAFT)
    assert d.version.name == "shorty"


def test_new_upload_extant_existing(mocker, text_dandiset):
    iter_upload_spy = mocker.spy(RemoteDandiset, "iter_upload_raw_asset")
    with pytest.raises(FileExistsError):
        text_dandiset["reupload"](existing="error")
    iter_upload_spy.assert_not_called()


def test_new_upload_extant_skip(mocker, text_dandiset):
    iter_upload_spy = mocker.spy(RemoteDandiset, "iter_upload_raw_asset")
    text_dandiset["reupload"](existing="skip")
    iter_upload_spy.assert_not_called()


@pytest.mark.parametrize("existing", ["overwrite", "refresh"])
def test_new_upload_extant_eq_overwrite(existing, mocker, text_dandiset):
    iter_upload_spy = mocker.spy(RemoteDandiset, "iter_upload_raw_asset")
    text_dandiset["reupload"](existing=existing)
    iter_upload_spy.assert_not_called()


@pytest.mark.parametrize("existing", ["overwrite", "refresh"])
def test_new_upload_extant_neq_overwrite(
    existing, local_dandi_api, mocker, text_dandiset, tmp_path
):
    dandiset_id = text_dandiset["dandiset_id"]
    (text_dandiset["dspath"] / "file.txt").write_text("This is different text.\n")
    iter_upload_spy = mocker.spy(RemoteDandiset, "iter_upload_raw_asset")
    text_dandiset["reupload"](existing=existing)
    iter_upload_spy.assert_called()
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/draft",
        tmp_path,
    )
    assert (
        tmp_path / dandiset_id / "file.txt"
    ).read_text() == "This is different text.\n"


def test_new_upload_extant_old_refresh(mocker, text_dandiset):
    (text_dandiset["dspath"] / "file.txt").write_text("This is different text.\n")
    os.utime(text_dandiset["dspath"] / "file.txt", times=(0, 0))
    iter_upload_spy = mocker.spy(RemoteDandiset, "iter_upload_raw_asset")
    text_dandiset["reupload"](existing="refresh")
    iter_upload_spy.assert_not_called()


def test_new_upload_extant_force(mocker, text_dandiset):
    iter_upload_spy = mocker.spy(RemoteDandiset, "iter_upload_raw_asset")
    text_dandiset["reupload"](existing="force")
    iter_upload_spy.assert_called()


def test_new_upload_extant_bad_existing(mocker, text_dandiset):
    iter_upload_spy = mocker.spy(RemoteDandiset, "iter_upload_raw_asset")
    text_dandiset["reupload"](existing="foobar")
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
    client = local_dandi_api["client"]
    dandiset_id = client.create_dandiset("Small Dandiset", {}).identifier
    dspath = tmp_path / "upload"
    dspath.mkdir()
    (dspath / dandiset_metadata_file).write_text(f"identifier: '{dandiset_id}'\n")
    (dspath / "file.txt").write_bytes(contents)
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    upload(
        paths=[],
        dandiset_path=dspath,
        dandi_instance=local_dandi_api["instance_id"],
        devel_debug=True,
        allow_any_path=True,
        validation="skip",
    )
    download_dir = tmp_path / "download"
    download_dir.mkdir()
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/draft",
        download_dir,
    )
    files = sorted(map(Path, find_files(r".*", paths=[download_dir])))
    assert files == [
        download_dir / dandiset_id / dandiset_metadata_file,
        download_dir / dandiset_id / "file.txt",
    ]
    assert files[1].read_bytes() == contents


@pytest.mark.parametrize("confirm", [True, False])
def test_upload_sync(confirm, mocker, text_dandiset):
    (text_dandiset["dspath"] / "file.txt").unlink()
    confirm_mock = mocker.patch("click.confirm", return_value=confirm)
    text_dandiset["reupload"](sync=True)
    confirm_mock.assert_called_with("Delete 1 asset on server?")
    if confirm:
        with pytest.raises(NotFoundError):
            text_dandiset["dandiset"].get_asset_by_path("file.txt")
    else:
        text_dandiset["dandiset"].get_asset_by_path("file.txt")


def test_upload_sync_folder(mocker, text_dandiset):
    (text_dandiset["dspath"] / "file.txt").unlink()
    (text_dandiset["dspath"] / "subdir2" / "banana.txt").unlink()
    confirm_mock = mocker.patch("click.confirm", return_value=True)
    text_dandiset["reupload"](paths=[text_dandiset["dspath"] / "subdir2"], sync=True)
    confirm_mock.assert_called_with("Delete 1 asset on server?")
    text_dandiset["dandiset"].get_asset_by_path("file.txt")
    with pytest.raises(NotFoundError):
        text_dandiset["dandiset"].get_asset_by_path("subdir2/banana.txt")
