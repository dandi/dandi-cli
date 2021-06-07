import builtins
import os.path
from pathlib import Path
import random
from shutil import rmtree

import click

from ..consts import dandiset_metadata_file
from ..dandiapi import DandiAPIClient
from ..download import download
from .. import dandiapi
from ..upload import upload
from ..utils import find_files


def test_upload(local_dandi_api, simple1_nwb, tmp_path):
    client = local_dandi_api["client"]
    r = client.create_dandiset(name="Upload Test", metadata={})
    dandiset_id = r["identifier"]
    client.upload(dandiset_id, "draft", {"path": "testing/simple1.nwb"}, simple1_nwb)
    (asset,) = client.get_dandiset_assets(dandiset_id, "draft")
    assert asset["path"] == "testing/simple1.nwb"
    client.download_assets_directory(dandiset_id, "draft", "", tmp_path)
    (p,) = [p for p in tmp_path.glob("**/*") if p.is_file()]
    assert p == tmp_path / "testing" / "simple1.nwb"
    assert p.stat().st_size == os.path.getsize(simple1_nwb)


def test_publish_and_manipulate(local_dandi_api, monkeypatch, tmp_path):
    client = local_dandi_api["client"]
    dandiset_id = client.create_dandiset("Test Dandiset", {})["identifier"]
    upload_dir = tmp_path / "upload"
    upload_dir.mkdir()
    (upload_dir / dandiset_metadata_file).write_text(f"identifier: '{dandiset_id}'\n")
    (upload_dir / "subdir").mkdir()
    (upload_dir / "subdir" / "file.txt").write_text("This is test text.\n")
    monkeypatch.chdir(upload_dir)
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    upload(
        paths=[],
        dandi_instance=local_dandi_api["instance_id"],
        devel_debug=True,
        allow_any_path=True,
        validation="skip",
    )

    version_id = client.publish_version(dandiset_id, "draft")["version"]

    download_dir = tmp_path / "download"
    download_dir.mkdir()

    def downloaded_files():
        return list(map(Path, find_files(r".*", paths=[download_dir])))

    dandiset_yaml = download_dir / dandiset_id / dandiset_metadata_file
    file_in_version = download_dir / dandiset_id / "subdir" / "file.txt"

    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/{version_id}",
        download_dir,
    )
    assert downloaded_files() == [dandiset_yaml, file_in_version]
    assert file_in_version.read_text() == "This is test text.\n"

    (upload_dir / "subdir" / "file.txt").write_text("This is different text.\n")
    upload(
        paths=[],
        dandi_instance=local_dandi_api["instance_id"],
        devel_debug=True,
        allow_any_path=True,
        validation="skip",
    )
    rmtree(download_dir / dandiset_id)
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/{version_id}",
        download_dir,
    )
    assert downloaded_files() == [dandiset_yaml, file_in_version]
    assert file_in_version.read_text() == "This is test text.\n"

    (upload_dir / "subdir" / "file2.txt").write_text("This is more text.\n")
    upload(
        paths=[],
        dandi_instance=local_dandi_api["instance_id"],
        devel_debug=True,
        allow_any_path=True,
        validation="skip",
    )

    rmtree(download_dir / dandiset_id)
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/draft",
        download_dir,
    )
    assert sorted(downloaded_files()) == [
        dandiset_yaml,
        file_in_version,
        file_in_version.with_name("file2.txt"),
    ]
    assert file_in_version.read_text() == "This is different text.\n"
    assert file_in_version.with_name("file2.txt").read_text() == "This is more text.\n"

    rmtree(download_dir / dandiset_id)
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/{version_id}",
        download_dir,
    )
    assert downloaded_files() == [dandiset_yaml, file_in_version]
    assert file_in_version.read_text() == "This is test text.\n"

    client.delete_asset_bypath(dandiset_id, "draft", "subdir/file.txt")

    rmtree(download_dir / dandiset_id)
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/draft",
        download_dir,
    )
    assert downloaded_files() == [dandiset_yaml, file_in_version.with_name("file2.txt")]
    assert file_in_version.with_name("file2.txt").read_text() == "This is more text.\n"

    rmtree(download_dir / dandiset_id)
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/{version_id}",
        download_dir,
    )
    assert downloaded_files() == [dandiset_yaml, file_in_version]
    assert file_in_version.read_text() == "This is test text.\n"


def test_get_asset_include_metadata(local_dandi_api, simple1_nwb, tmp_path):
    client = local_dandi_api["client"]
    r = client.create_dandiset(name="Include Metadata Test", metadata={})
    dandiset_id = r["identifier"]
    client.upload(
        dandiset_id,
        "draft",
        {"path": "testing/simple1.nwb", "foo": "bar"},
        simple1_nwb,
    )

    (asset,) = client.get_dandiset_assets(dandiset_id, "draft")
    assert "metadata" not in asset
    (asset,) = client.get_dandiset_assets(dandiset_id, "draft", include_metadata=True)
    assert asset["metadata"]["path"] == "testing/simple1.nwb"
    assert asset["metadata"]["foo"] == "bar"

    _, (asset,) = client.get_dandiset_and_assets(dandiset_id, "draft")
    assert "metadata" not in asset
    _, (asset,) = client.get_dandiset_and_assets(
        dandiset_id, "draft", include_metadata=True
    )
    assert asset["metadata"]["path"] == "testing/simple1.nwb"
    assert asset["metadata"]["foo"] == "bar"

    asset = client.get_asset_bypath(dandiset_id, "draft", "testing/simple1.nwb")
    assert asset is not None
    assert "metadata" not in asset
    asset = client.get_asset_bypath(
        dandiset_id, "draft", "testing/simple1.nwb", include_metadata=True
    )
    assert asset is not None
    assert asset["metadata"]["path"] == "testing/simple1.nwb"
    assert asset["metadata"]["foo"] == "bar"


def test_large_upload(local_dandi_api, tmp_path):
    client = local_dandi_api["client"]
    asset_file = tmp_path / "asset.dat"
    meg = bytes(random.choices(range(256), k=1 << 20))
    with asset_file.open("wb") as fp:
        for _ in range(100):
            fp.write(meg)
    r = client.create_dandiset(name="Large Upload Test", metadata={})
    dandiset_id = r["identifier"]
    client.upload(dandiset_id, "draft", {"path": "testing/asset.dat"}, asset_file)


def test_authenticate_bad_key_good_key_input(local_dandi_api, mocker, monkeypatch):
    good_key = local_dandi_api["api_key"]
    bad_key = "1234567890"
    client_name = local_dandi_api["instance_id"]
    app_id = f"dandi-api-{client_name}"

    backend_mock = mocker.Mock(spec=["set_password"])
    keyring_lookup_mock = mocker.patch(
        "dandi.dandiapi.keyring_lookup", return_value=(backend_mock, None)
    )
    input_mock = mocker.patch("dandi.dandiapi.input", side_effect=[bad_key, good_key])
    is_interactive_mock = mocker.patch(
        "dandi.dandiapi.is_interactive", return_value=True
    )
    confirm_mock = mocker.patch("click.confirm", return_value=True)

    monkeypatch.delenv("DANDI_API_KEY", raising=False)

    client = DandiAPIClient(local_dandi_api["instance"].api)
    assert "Authorization" not in client._headers
    client.dandi_authenticate()
    assert client._headers["Authorization"] == f"token {good_key}"

    backend_mock.set_password.assert_called_once_with(app_id, "key", good_key)
    keyring_lookup_mock.assert_called_once_with(app_id, "key")
    assert input_mock.call_args_list == (
        [mocker.call(f"Please provide API Key for {client_name}: ")] * 2
    )
    is_interactive_mock.assert_called_once()
    confirm_mock.assert_called_once_with("API key is invalid; enter another?")


def test_authenticate_good_key_keyring(local_dandi_api, mocker, monkeypatch):
    good_key = local_dandi_api["api_key"]
    client_name = local_dandi_api["instance_id"]
    app_id = f"dandi-api-{client_name}"

    backend_mock = mocker.Mock(spec=["set_password"])
    keyring_lookup_mock = mocker.patch(
        "dandi.dandiapi.keyring_lookup", return_value=(backend_mock, good_key)
    )
    input_spy = mocker.spy(builtins, "input")
    is_interactive_spy = mocker.spy(dandiapi, "is_interactive")
    confirm_spy = mocker.spy(click, "confirm")

    monkeypatch.delenv("DANDI_API_KEY", raising=False)

    client = DandiAPIClient(local_dandi_api["instance"].api)
    assert "Authorization" not in client._headers
    client.dandi_authenticate()
    assert client._headers["Authorization"] == f"token {good_key}"

    backend_mock.set_password.assert_not_called()
    keyring_lookup_mock.assert_called_once_with(app_id, "key")
    input_spy.assert_not_called()
    is_interactive_spy.assert_not_called()
    confirm_spy.assert_not_called()


def test_authenticate_bad_key_keyring_good_key_input(
    local_dandi_api, mocker, monkeypatch
):
    good_key = local_dandi_api["api_key"]
    bad_key = "1234567890"
    client_name = local_dandi_api["instance_id"]
    app_id = f"dandi-api-{client_name}"

    backend_mock = mocker.Mock(spec=["set_password"])
    keyring_lookup_mock = mocker.patch(
        "dandi.dandiapi.keyring_lookup", return_value=(backend_mock, bad_key)
    )
    input_mock = mocker.patch("dandi.dandiapi.input", return_value=good_key)
    is_interactive_mock = mocker.patch(
        "dandi.dandiapi.is_interactive", return_value=True
    )
    confirm_mock = mocker.patch("click.confirm", return_value=True)

    monkeypatch.delenv("DANDI_API_KEY", raising=False)

    client = DandiAPIClient(local_dandi_api["instance"].api)
    assert "Authorization" not in client._headers
    client.dandi_authenticate()
    assert client._headers["Authorization"] == f"token {good_key}"

    backend_mock.set_password.assert_called_once_with(app_id, "key", good_key)
    keyring_lookup_mock.assert_called_once_with(app_id, "key")
    input_mock.assert_called_once_with(f"Please provide API Key for {client_name}: ")
    is_interactive_mock.assert_called_once()
    confirm_mock.assert_called_once_with("API key is invalid; enter another?")
