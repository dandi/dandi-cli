import builtins
import os.path
from pathlib import Path
import random
import re
from shutil import rmtree

import click
from dandischema.models import UUID_PATTERN

from .. import dandiapi
from ..consts import dandiset_metadata_file
from ..dandiapi import DandiAPIClient
from ..download import download
from ..upload import upload
from ..utils import find_files


def test_upload(local_dandi_api, simple1_nwb, tmp_path):
    client = local_dandi_api["client"]
    d = client.create_dandiset(name="Upload Test", metadata={})
    assert d.version_id == "draft"
    d.upload_raw_asset(simple1_nwb, {"path": "testing/simple1.nwb"})
    (asset,) = d.get_assets()
    assert asset.path == "testing/simple1.nwb"
    d.download_directory("", tmp_path)
    (p,) = [p for p in tmp_path.glob("**/*") if p.is_file()]
    assert p == tmp_path / "testing" / "simple1.nwb"
    assert p.stat().st_size == os.path.getsize(simple1_nwb)


def test_publish_and_manipulate(local_dandi_api, monkeypatch, tmp_path):
    client = local_dandi_api["client"]
    d = client.create_dandiset(
        "Test Dandiset",
        {
            "schemaKey": "Dandiset",
            "name": "Text Dandiset",
            "description": "A test text Dandiset",
            "contributor": [
                {
                    "schemaKey": "Person",
                    "name": "Wodder, John",
                    "roleName": ["dcite:Author", "dcite:ContactPerson"],
                }
            ],
            "license": ["spdx:CC0-1.0"],
            "manifestLocation": ["https://github.com/dandi/dandi-cli"],
        },
    )
    dandiset_id = d.identifier
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

    version_id = d.publish().version.identifier

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

    d.get_asset_by_path("subdir/file.txt").delete()

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


def test_get_asset_metadata(local_dandi_api, simple1_nwb):
    client = local_dandi_api["client"]
    d = client.create_dandiset(name="Include Metadata Test", metadata={})
    d.upload_raw_asset(simple1_nwb, {"path": "testing/simple1.nwb", "foo": "bar"})
    (asset,) = d.get_assets()
    metadata = asset.get_raw_metadata()
    assert metadata["path"] == "testing/simple1.nwb"
    assert metadata["foo"] == "bar"


def test_large_upload(local_dandi_api, tmp_path):
    client = local_dandi_api["client"]
    asset_file = tmp_path / "asset.dat"
    meg = bytes(random.choices(range(256), k=1 << 20))
    with asset_file.open("wb") as fp:
        for _ in range(100):
            fp.write(meg)
    d = client.create_dandiset(name="Large Upload Test", metadata={})
    d.upload_raw_asset(asset_file, {"path": "testing/asset.dat"})


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
    assert "Authorization" not in client.session.headers
    client.dandi_authenticate()
    assert client.session.headers["Authorization"] == f"token {good_key}"

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
    assert "Authorization" not in client.session.headers
    client.dandi_authenticate()
    assert client.session.headers["Authorization"] == f"token {good_key}"

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
    assert "Authorization" not in client.session.headers
    client.dandi_authenticate()
    assert client.session.headers["Authorization"] == f"token {good_key}"

    backend_mock.set_password.assert_called_once_with(app_id, "key", good_key)
    keyring_lookup_mock.assert_called_once_with(app_id, "key")
    input_mock.assert_called_once_with(f"Please provide API Key for {client_name}: ")
    is_interactive_mock.assert_called_once()
    confirm_mock.assert_called_once_with("API key is invalid; enter another?")


def test_get_content_url(monkeypatch, tmp_path):
    monkeypatch.setenv("DANDI_INSTANCE", "dandi")
    with DandiAPIClient() as client:
        asset = client.get_dandiset("000027", "draft").get_asset_by_path(
            "sub-RAT123/sub-RAT123.nwb"
        )
        url = asset.get_content_url()
        assert re.match(
            "https://api.dandiarchive.org/api/assets/"
            # note: Yarik doesn't care if there is a trailing /
            + UUID_PATTERN.rstrip("$") + "/download/?$",
            url,
        )
        r = client.get(url, stream=True, json_resp=False)
        with open(tmp_path / "asset.nwb", "wb") as fp:
            for chunk in r.iter_content(chunk_size=8192):
                fp.write(chunk)


def test_get_content_url_regex(monkeypatch, tmp_path):
    monkeypatch.setenv("DANDI_INSTANCE", "dandi")
    with DandiAPIClient() as client:
        asset = client.get_dandiset("000027", "draft").get_asset_by_path(
            "sub-RAT123/sub-RAT123.nwb"
        )
        url = asset.get_content_url(r"amazonaws.com/.*blobs/")
        r = client.get(url, stream=True, json_resp=False)
        with open(tmp_path / "asset.nwb", "wb") as fp:
            for chunk in r.iter_content(chunk_size=8192):
                fp.write(chunk)


def test_get_content_url_follow_one_redirects_strip_query(monkeypatch):
    monkeypatch.setenv("DANDI_INSTANCE", "dandi")
    with DandiAPIClient() as client:
        asset = client.get_dandiset("000027", "draft").get_asset_by_path(
            "sub-RAT123/sub-RAT123.nwb"
        )
        url = asset.get_content_url(follow_redirects=1, strip_query=True)
        assert url == (
            "https://dandiarchive.s3.amazonaws.com/blobs/2db/af0/2dbaf0fd-5003"
            "-4a0a-b4c0-bc8cdbdb3826"
        )


def test_remote_asset_json_dict(text_dandiset):
    asset = text_dandiset["dandiset"].get_asset_by_path("file.txt")
    data = asset.json_dict()
    assert sorted(data.keys()) == ["asset_id", "modified", "path", "size"]
    for v in data.values():
        assert isinstance(v, (str, int))
