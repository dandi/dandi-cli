import builtins
from datetime import datetime, timezone
import os.path
from pathlib import Path
import random
import re
from shutil import rmtree

import anys
import click
from dandischema.models import UUID_PATTERN, DigestType, get_schema_version
import pytest
import responses

from .. import dandiapi
from ..consts import (
    DRAFT,
    VERSION_REGEX,
    dandiset_identifier_regex,
    dandiset_metadata_file,
)
from ..dandiapi import DandiAPIClient, Version
from ..download import download
from ..exceptions import NotFoundError, SchemaVersionError
from ..upload import upload
from ..utils import find_files


def test_upload(local_dandi_api, simple1_nwb, tmp_path):
    client = local_dandi_api["client"]
    d = client.create_dandiset(name="Upload Test", metadata={})
    assert d.version_id == DRAFT
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

    d.wait_until_valid()
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


def test_get_content_url(tmp_path):
    with DandiAPIClient.for_dandi_instance("dandi") as client:
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


def test_get_content_url_regex(tmp_path):
    with DandiAPIClient.for_dandi_instance("dandi") as client:
        asset = client.get_dandiset("000027", "draft").get_asset_by_path(
            "sub-RAT123/sub-RAT123.nwb"
        )
        url = asset.get_content_url(r"amazonaws.com/.*blobs/")
        r = client.get(url, stream=True, json_resp=False)
        with open(tmp_path / "asset.nwb", "wb") as fp:
            for chunk in r.iter_content(chunk_size=8192):
                fp.write(chunk)


def test_get_content_url_follow_one_redirects_strip_query():
    with DandiAPIClient.for_dandi_instance("dandi") as client:
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
    assert asset.json_dict() == {
        "asset_id": anys.ANY_STR,
        "modified": anys.ANY_AWARE_DATETIME_STR,
        "path": anys.ANY_STR,
        "size": anys.ANY_INT,
    }


@responses.activate
def test_check_schema_version_matches_default():
    responses.add(
        responses.GET,
        "https://test.nil/api/info/",
        json={"schema_version": get_schema_version()},
    )
    client = DandiAPIClient("https://test.nil/api")
    client.check_schema_version()


@responses.activate
def test_check_schema_version_mismatch():
    responses.add(
        responses.GET, "https://test.nil/api/info/", json={"schema_version": "4.5.6"}
    )
    client = DandiAPIClient("https://test.nil/api")
    with pytest.raises(SchemaVersionError) as excinfo:
        client.check_schema_version("1.2.3")
    assert (
        str(excinfo.value)
        == "Server requires schema version 4.5.6; client only supports 1.2.3.  "
        "You may need to upgrade dandi and/or dandischema."
    )


def test_get_dandisets(text_dandiset):
    dandisets = list(text_dandiset["client"].get_dandisets())
    assert (
        sum(1 for d in dandisets if d.identifier == text_dandiset["dandiset_id"]) == 1
    )


def test_get_dandiset_lazy(mocker, text_dandiset):
    client = text_dandiset["client"]
    get_spy = mocker.spy(client, "get")
    dandiset = client.get_dandiset(text_dandiset["dandiset_id"], DRAFT, lazy=True)
    get_spy.assert_not_called()
    assert dandiset.version_id == DRAFT
    get_spy.assert_not_called()
    assert isinstance(dandiset.created, datetime)
    get_spy.assert_called_once()
    get_spy.reset_mock()
    assert isinstance(dandiset.created, datetime)
    assert isinstance(dandiset.modified, datetime)
    assert isinstance(dandiset.version, Version)
    assert dandiset.version.identifier == DRAFT
    assert dandiset.most_recent_published_version is None
    assert isinstance(dandiset.draft_version, Version)
    assert isinstance(dandiset.contact_person, str)
    get_spy.assert_not_called()


def test_get_dandiset_non_lazy(mocker, text_dandiset):
    client = text_dandiset["client"]
    get_spy = mocker.spy(client, "get")
    dandiset = client.get_dandiset(text_dandiset["dandiset_id"], DRAFT, lazy=False)
    get_spy.assert_called_once()
    get_spy.reset_mock()
    assert dandiset.version_id == DRAFT
    get_spy.assert_not_called()
    assert isinstance(dandiset.created, datetime)
    get_spy.assert_not_called()
    assert isinstance(dandiset.created, datetime)
    assert isinstance(dandiset.modified, datetime)
    assert isinstance(dandiset.version, Version)
    assert dandiset.version.identifier == DRAFT
    assert dandiset.most_recent_published_version is None
    assert isinstance(dandiset.draft_version, Version)
    assert isinstance(dandiset.contact_person, str)
    get_spy.assert_not_called()


@pytest.mark.parametrize("lazy", [True, False])
def test_get_dandiset_no_version_id(lazy, text_dandiset):
    dandiset = text_dandiset["client"].get_dandiset(
        text_dandiset["dandiset_id"], lazy=lazy
    )
    assert dandiset.version_id == DRAFT
    assert isinstance(dandiset.created, datetime)
    assert isinstance(dandiset.created, datetime)
    assert isinstance(dandiset.modified, datetime)
    assert isinstance(dandiset.version, Version)
    assert dandiset.version.identifier == DRAFT
    assert dandiset.most_recent_published_version is None
    assert isinstance(dandiset.draft_version, Version)
    assert isinstance(dandiset.contact_person, str)
    versions = list(dandiset.get_versions())
    assert len(versions) == 1
    assert versions[0].identifier == DRAFT


@pytest.mark.parametrize("lazy", [True, False])
def test_get_dandiset_published(lazy, text_dandiset):
    d = text_dandiset["dandiset"]
    d.wait_until_valid()
    v = d.publish().version.identifier
    dandiset = text_dandiset["client"].get_dandiset(d.identifier, v, lazy=lazy)
    assert dandiset.version_id == v
    assert isinstance(dandiset.created, datetime)
    assert isinstance(dandiset.created, datetime)
    assert isinstance(dandiset.modified, datetime)
    assert isinstance(dandiset.version, Version)
    assert dandiset.version.identifier == v
    assert isinstance(dandiset.most_recent_published_version, Version)
    assert dandiset.most_recent_published_version.identifier == v
    assert isinstance(dandiset.draft_version, Version)
    assert isinstance(dandiset.contact_person, str)
    versions = list(dandiset.get_versions())
    assert len(versions) == 2
    assert sorted(vobj.identifier for vobj in versions) == [v, DRAFT]


@pytest.mark.parametrize("lazy", [True, False])
def test_get_dandiset_published_no_version_id(lazy, text_dandiset):
    d = text_dandiset["dandiset"]
    d.wait_until_valid()
    v = d.publish().version.identifier
    dandiset = text_dandiset["client"].get_dandiset(d.identifier, lazy=lazy)
    assert dandiset.version_id == v
    assert isinstance(dandiset.created, datetime)
    assert isinstance(dandiset.created, datetime)
    assert isinstance(dandiset.modified, datetime)
    assert isinstance(dandiset.version, Version)
    assert dandiset.version.identifier == v
    assert isinstance(dandiset.most_recent_published_version, Version)
    assert dandiset.most_recent_published_version.identifier == v
    assert isinstance(dandiset.draft_version, Version)
    assert isinstance(dandiset.contact_person, str)
    versions = list(dandiset.get_versions())
    assert len(versions) == 2
    assert sorted(vobj.identifier for vobj in versions) == [v, DRAFT]


@pytest.mark.parametrize("lazy", [True, False])
def test_get_dandiset_published_draft(lazy, text_dandiset):
    d = text_dandiset["dandiset"]
    d.wait_until_valid()
    v = d.publish().version.identifier
    dandiset = text_dandiset["client"].get_dandiset(d.identifier, DRAFT, lazy=lazy)
    assert dandiset.version_id == DRAFT
    assert isinstance(dandiset.created, datetime)
    assert isinstance(dandiset.created, datetime)
    assert isinstance(dandiset.modified, datetime)
    assert isinstance(dandiset.version, Version)
    assert dandiset.version.identifier == DRAFT
    assert isinstance(dandiset.most_recent_published_version, Version)
    assert dandiset.most_recent_published_version.identifier == v
    assert isinstance(dandiset.draft_version, Version)
    assert isinstance(dandiset.contact_person, str)
    versions = list(dandiset.get_versions())
    assert len(versions) == 2
    assert sorted(vobj.identifier for vobj in versions) == [v, DRAFT]


@pytest.mark.parametrize("lazy", [True, False])
def test_get_dandiset_published_other_version(lazy, text_dandiset):
    d = text_dandiset["dandiset"]
    d.wait_until_valid()
    v1 = d.publish().version.identifier

    (text_dandiset["dspath"] / "file2.txt").write_text("This is more text.\n")
    text_dandiset["reupload"]()
    d.wait_until_valid()
    v2 = d.publish().version.identifier
    assert v1 != v2

    dandiset = text_dandiset["client"].get_dandiset(d.identifier, v1, lazy=lazy)
    assert dandiset.version_id == v1
    assert isinstance(dandiset.created, datetime)
    assert isinstance(dandiset.created, datetime)
    assert isinstance(dandiset.modified, datetime)
    assert isinstance(dandiset.version, Version)
    assert dandiset.version.identifier == v1
    assert isinstance(dandiset.most_recent_published_version, Version)
    assert dandiset.most_recent_published_version.identifier == v2
    assert isinstance(dandiset.draft_version, Version)
    assert isinstance(dandiset.contact_person, str)

    versions = list(dandiset.get_versions())
    assert len(versions) == 3
    assert sorted(vobj.identifier for vobj in versions) == [v1, v2, DRAFT]


def test_set_asset_metadata(text_dandiset):
    asset = text_dandiset["dandiset"].get_asset_by_path("file.txt")
    md = asset.get_metadata()
    md.blobDateModified = datetime(2038, 1, 19, 3, 14, 7, tzinfo=timezone.utc)
    asset.set_metadata(md)
    assert asset.get_raw_metadata()["blobDateModified"] == "2038-01-19T03:14:07+00:00"


def test_remote_dandiset_json_dict(text_dandiset):
    data = text_dandiset["dandiset"].json_dict()
    assert data == {
        "identifier": anys.AnyFullmatch(dandiset_identifier_regex),
        "created": anys.ANY_AWARE_DATETIME_STR,
        "modified": anys.ANY_AWARE_DATETIME_STR,
        "contact_person": anys.ANY_STR,
        "most_recent_published_version": None,
        "draft_version": {
            "version": anys.AnyFullmatch(VERSION_REGEX),
            "name": anys.ANY_STR,
            "asset_count": anys.ANY_INT,
            "size": anys.ANY_INT,
            "created": anys.ANY_AWARE_DATETIME_STR,
            "modified": anys.ANY_AWARE_DATETIME_STR,
        },
        "version": anys.ANY_DICT,
    }
    assert data["draft_version"] == data["version"]


def test_set_dandiset_metadata(text_dandiset):
    dandiset = text_dandiset["dandiset"]
    md = dandiset.get_metadata()
    md.description = "A test Dandiset with altered metadata"
    dandiset.set_metadata(md)
    assert (
        dandiset.get_raw_metadata()["description"]
        == "A test Dandiset with altered metadata"
    )


@pytest.mark.parametrize(
    "digest_type,digest_regex",
    [
        (DigestType.dandi_etag, r"[0-9a-f]{32}-\d{1,5}"),
        ("dandi:dandi-etag", r"[0-9a-f]{32}-\d{1,5}"),
    ],
)
def test_get_digest(digest_type, digest_regex, text_dandiset):
    asset = text_dandiset["dandiset"].get_asset_by_path("file.txt")
    d = asset.get_digest(digest_type)
    assert re.fullmatch(digest_regex, d)


def test_get_digest_nonexistent(text_dandiset):
    asset = text_dandiset["dandiset"].get_asset_by_path("file.txt")
    with pytest.raises(NotFoundError):
        asset.get_digest("md5")


def test_refresh(text_dandiset):
    dandiset = text_dandiset["dandiset"]
    mtime = dandiset.version.modified
    md = dandiset.get_metadata()
    md.description = "A test Dandiset with altered metadata"
    dandiset.set_metadata(md)
    dandiset.wait_until_valid()
    dandiset.publish()
    assert dandiset.version.modified == mtime
    assert dandiset.most_recent_published_version is None
    dandiset.refresh()
    assert dandiset.version_id == DRAFT
    assert dandiset.version.modified > mtime
    assert dandiset.most_recent_published_version is not None
