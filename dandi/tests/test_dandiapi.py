import builtins
from datetime import datetime, timezone
import logging
import os.path
from pathlib import Path
import random
import re
from shutil import rmtree
from typing import List, Union

import anys
import click
from dandischema.models import UUID_PATTERN, DigestType, get_schema_version
import pytest
from pytest_mock import MockerFixture
import requests
import responses

from .fixtures import DandiAPI, SampleDandiset
from .skip import mark
from .. import dandiapi
from ..consts import (
    DRAFT,
    VERSION_REGEX,
    dandiset_identifier_regex,
    dandiset_metadata_file,
)
from ..dandiapi import DandiAPIClient, RemoteAsset, RemoteZarrAsset, Version
from ..download import download
from ..exceptions import NotFoundError, SchemaVersionError
from ..files import GenericAsset, dandi_file
from ..utils import list_paths


def test_upload(new_dandiset: SampleDandiset, simple1_nwb: str, tmp_path: Path) -> None:
    d = new_dandiset.dandiset
    assert d.version_id == DRAFT
    d.upload_raw_asset(simple1_nwb, {"path": "testing/simple1.nwb"})
    (asset,) = d.get_assets()
    assert asset.path == "testing/simple1.nwb"
    d.download_directory("", tmp_path)
    paths = list_paths(tmp_path)
    assert paths == [tmp_path / "testing" / "simple1.nwb"]
    assert paths[0].stat().st_size == os.path.getsize(simple1_nwb)


def test_publish_and_manipulate(new_dandiset: SampleDandiset, tmp_path: Path) -> None:
    d = new_dandiset.dandiset
    dandiset_id = d.identifier
    dspath = new_dandiset.dspath
    assert str(d) == f"DANDI-API-LOCAL-DOCKER-TESTS:{dandiset_id}/draft"
    (dspath / "subdir").mkdir()
    (dspath / "subdir" / "file.txt").write_text("This is test text.\n")
    (dspath / "subdir" / "doomed.txt").write_text("This will be deleted.\n")
    new_dandiset.upload(allow_any_path=True)

    d.wait_until_valid()
    v = d.publish().version
    version_id = v.identifier
    assert version_id != "draft"
    assert str(v) == version_id
    dv = d.for_version(v)
    assert str(dv) == f"DANDI-API-LOCAL-DOCKER-TESTS:{dandiset_id}/{version_id}"

    dandiset_yaml = tmp_path / dandiset_id / dandiset_metadata_file
    file_in_version = tmp_path / dandiset_id / "subdir" / "file.txt"

    (dspath / "subdir" / "file.txt").write_text("This is different text.\n")
    (dspath / "subdir" / "file2.txt").write_text("This is more text.\n")
    new_dandiset.upload(allow_any_path=True)
    d.get_asset_by_path("subdir/doomed.txt").delete()

    download(d.version_api_url, tmp_path)
    assert list_paths(tmp_path) == [
        dandiset_yaml,
        file_in_version,
        file_in_version.with_name("file2.txt"),
    ]
    assert file_in_version.read_text() == "This is different text.\n"
    assert file_in_version.with_name("file2.txt").read_text() == "This is more text.\n"

    rmtree(tmp_path / dandiset_id)
    download(dv.version_api_url, tmp_path)
    assert list_paths(tmp_path) == [
        dandiset_yaml,
        file_in_version.with_name("doomed.txt"),
        file_in_version,
    ]
    assert file_in_version.read_text() == "This is test text.\n"
    assert (
        file_in_version.with_name("doomed.txt").read_text() == "This will be deleted.\n"
    )


def test_get_asset_metadata(new_dandiset: SampleDandiset, simple1_nwb: str) -> None:
    d = new_dandiset.dandiset
    d.upload_raw_asset(simple1_nwb, {"path": "testing/simple1.nwb", "foo": "bar"})
    (asset,) = d.get_assets()
    assert str(asset) == f"DANDI-API-LOCAL-DOCKER-TESTS:assets/{asset.identifier}"
    metadata = asset.get_raw_metadata()
    assert metadata["path"] == "testing/simple1.nwb"
    assert metadata["foo"] == "bar"


def test_large_upload(new_dandiset: SampleDandiset, tmp_path: Path) -> None:
    asset_file = tmp_path / "asset.dat"
    meg = bytes(random.choices(range(256), k=1 << 20))
    with asset_file.open("wb") as fp:
        for _ in range(100):
            fp.write(meg)
    new_dandiset.dandiset.upload_raw_asset(asset_file, {"path": "testing/asset.dat"})


def test_authenticate_bad_key_good_key_input(
    local_dandi_api: DandiAPI, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    good_key = local_dandi_api.api_key
    bad_key = "1234567890"
    client_name = local_dandi_api.instance_id
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

    client = DandiAPIClient(local_dandi_api.api_url)
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


def test_authenticate_good_key_keyring(
    local_dandi_api: DandiAPI, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    good_key = local_dandi_api.api_key
    client_name = local_dandi_api.instance_id
    app_id = f"dandi-api-{client_name}"

    backend_mock = mocker.Mock(spec=["set_password"])
    keyring_lookup_mock = mocker.patch(
        "dandi.dandiapi.keyring_lookup", return_value=(backend_mock, good_key)
    )
    input_spy = mocker.spy(builtins, "input")
    is_interactive_spy = mocker.spy(dandiapi, "is_interactive")
    confirm_spy = mocker.spy(click, "confirm")

    monkeypatch.delenv("DANDI_API_KEY", raising=False)

    client = DandiAPIClient(local_dandi_api.api_url)
    assert "Authorization" not in client.session.headers
    client.dandi_authenticate()
    assert client.session.headers["Authorization"] == f"token {good_key}"

    backend_mock.set_password.assert_not_called()
    keyring_lookup_mock.assert_called_once_with(app_id, "key")
    input_spy.assert_not_called()
    is_interactive_spy.assert_not_called()
    confirm_spy.assert_not_called()


def test_authenticate_bad_key_keyring_good_key_input(
    local_dandi_api: DandiAPI, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    good_key = local_dandi_api.api_key
    bad_key = "1234567890"
    client_name = local_dandi_api.instance_id
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

    client = DandiAPIClient(local_dandi_api.api_url)
    assert "Authorization" not in client.session.headers
    client.dandi_authenticate()
    assert client.session.headers["Authorization"] == f"token {good_key}"

    backend_mock.set_password.assert_called_once_with(app_id, "key", good_key)
    keyring_lookup_mock.assert_called_once_with(app_id, "key")
    input_mock.assert_called_once_with(f"Please provide API Key for {client_name}: ")
    is_interactive_mock.assert_called_once()
    confirm_mock.assert_called_once_with("API key is invalid; enter another?")


@mark.skipif_no_network
def test_get_content_url(tmp_path: Path) -> None:
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


@mark.skipif_no_network
def test_get_content_url_regex(tmp_path: Path) -> None:
    with DandiAPIClient.for_dandi_instance("dandi") as client:
        asset = client.get_dandiset("000027", "draft").get_asset_by_path(
            "sub-RAT123/sub-RAT123.nwb"
        )
        url = asset.get_content_url(r"amazonaws.com/.*blobs/")
        r = client.get(url, stream=True, json_resp=False)
        with open(tmp_path / "asset.nwb", "wb") as fp:
            for chunk in r.iter_content(chunk_size=8192):
                fp.write(chunk)


@mark.skipif_no_network
def test_get_content_url_follow_one_redirects_strip_query() -> None:
    with DandiAPIClient.for_dandi_instance("dandi") as client:
        asset = client.get_dandiset("000027", "draft").get_asset_by_path(
            "sub-RAT123/sub-RAT123.nwb"
        )
        url = asset.get_content_url(follow_redirects=1, strip_query=True)
        assert url == (
            "https://dandiarchive.s3.amazonaws.com/blobs/2db/af0/2dbaf0fd-5003"
            "-4a0a-b4c0-bc8cdbdb3826"
        )


def test_get_content_url_follow_redirects_zarr(zarr_dandiset: SampleDandiset) -> None:
    asset = zarr_dandiset.dandiset.get_asset_by_path("sample.zarr")
    assert isinstance(asset, RemoteZarrAsset)
    url = asset.get_content_url(follow_redirects=True, strip_query=True)
    assert re.fullmatch(
        f"http://localhost:9000/dandi-dandisets/zarr/{asset.zarr}/*",
        url,
    )


def test_remote_asset_json_dict(text_dandiset: SampleDandiset) -> None:
    asset = text_dandiset.dandiset.get_asset_by_path("file.txt")
    assert asset.json_dict() == {
        "asset_id": anys.ANY_STR,
        "modified": anys.ANY_AWARE_DATETIME_STR,
        "created": anys.ANY_AWARE_DATETIME_STR,
        "path": anys.ANY_STR,
        "size": anys.ANY_INT,
        "blob": anys.ANY_STR,
    }


@responses.activate
def test_check_schema_version_matches_default() -> None:
    responses.add(
        responses.GET,
        "https://test.nil/api/info/",
        json={"schema_version": get_schema_version()},
    )
    client = DandiAPIClient("https://test.nil/api")
    client.check_schema_version()


@responses.activate
def test_check_schema_version_mismatch() -> None:
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


def test_get_dandisets(text_dandiset: SampleDandiset) -> None:
    dandisets = list(text_dandiset.client.get_dandisets())
    assert sum(1 for d in dandisets if d.identifier == text_dandiset.dandiset_id) == 1


def test_get_dandiset_lazy(
    mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    client = text_dandiset.client
    get_spy = mocker.spy(client, "get")
    dandiset = client.get_dandiset(text_dandiset.dandiset_id, DRAFT, lazy=True)
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


def test_get_dandiset_non_lazy(
    mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    client = text_dandiset.client
    get_spy = mocker.spy(client, "get")
    dandiset = client.get_dandiset(text_dandiset.dandiset_id, DRAFT, lazy=False)
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
def test_get_dandiset_no_version_id(lazy: bool, text_dandiset: SampleDandiset) -> None:
    dandiset = text_dandiset.client.get_dandiset(text_dandiset.dandiset_id, lazy=lazy)
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
def test_get_dandiset_published(lazy: bool, text_dandiset: SampleDandiset) -> None:
    d = text_dandiset.dandiset
    d.wait_until_valid()
    v = d.publish().version.identifier
    dandiset = text_dandiset.client.get_dandiset(d.identifier, v, lazy=lazy)
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
def test_get_dandiset_published_no_version_id(
    lazy: bool, text_dandiset: SampleDandiset
) -> None:
    d = text_dandiset.dandiset
    d.wait_until_valid()
    v = d.publish().version.identifier
    dandiset = text_dandiset.client.get_dandiset(d.identifier, lazy=lazy)
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
def test_get_dandiset_published_draft(
    lazy: bool, text_dandiset: SampleDandiset
) -> None:
    d = text_dandiset.dandiset
    d.wait_until_valid()
    v = d.publish().version.identifier
    dandiset = text_dandiset.client.get_dandiset(d.identifier, DRAFT, lazy=lazy)
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
def test_get_dandiset_published_other_version(
    lazy: bool, text_dandiset: SampleDandiset
) -> None:
    d = text_dandiset.dandiset
    d.wait_until_valid()
    v1 = d.publish().version.identifier

    (text_dandiset.dspath / "file2.txt").write_text("This is more text.\n")
    text_dandiset.upload()
    d.wait_until_valid()
    v2 = d.publish().version.identifier
    assert v1 != v2

    dandiset = text_dandiset.client.get_dandiset(d.identifier, v1, lazy=lazy)
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


def test_set_asset_metadata(text_dandiset: SampleDandiset) -> None:
    asset = text_dandiset.dandiset.get_asset_by_path("file.txt")
    md = asset.get_metadata()
    md.blobDateModified = datetime(2038, 1, 19, 3, 14, 7, tzinfo=timezone.utc)
    asset.set_metadata(md)
    assert asset.get_raw_metadata()["blobDateModified"] == "2038-01-19T03:14:07+00:00"


def test_remote_dandiset_json_dict(text_dandiset: SampleDandiset) -> None:
    data = text_dandiset.dandiset.json_dict()
    assert data == {
        "identifier": anys.AnyFullmatch(dandiset_identifier_regex),
        "created": anys.ANY_AWARE_DATETIME_STR,
        "modified": anys.ANY_AWARE_DATETIME_STR,
        "contact_person": anys.ANY_STR,
        "embargo_status": anys.ANY_STR,
        "most_recent_published_version": None,
        "draft_version": {
            "version": anys.AnyFullmatch(VERSION_REGEX),
            "name": anys.ANY_STR,
            "asset_count": anys.ANY_INT,
            "size": anys.ANY_INT,
            "created": anys.ANY_AWARE_DATETIME_STR,
            "modified": anys.ANY_AWARE_DATETIME_STR,
            "status": anys.ANY_STR,
        },
        "version": anys.ANY_DICT,
    }
    assert data["draft_version"] == data["version"]


def test_set_dandiset_metadata(text_dandiset: SampleDandiset) -> None:
    dandiset = text_dandiset.dandiset
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
        (None, r"[0-9a-f]{32}-\d{1,5}"),
    ],
)
def test_get_raw_digest(
    digest_type: Union[str, DigestType, None],
    digest_regex: str,
    text_dandiset: SampleDandiset,
) -> None:
    asset = text_dandiset.dandiset.get_asset_by_path("file.txt")
    d = asset.get_raw_digest(digest_type)
    assert re.fullmatch(digest_regex, d)


def test_get_raw_digest_nonexistent(text_dandiset: SampleDandiset) -> None:
    asset = text_dandiset.dandiset.get_asset_by_path("file.txt")
    with pytest.raises(NotFoundError):
        asset.get_raw_digest("md5")


def test_refresh(text_dandiset: SampleDandiset) -> None:
    dandiset = text_dandiset.dandiset
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


def test_get_asset_with_and_without_metadata(
    mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    path_asset = text_dandiset.dandiset.get_asset_by_path("file.txt")
    id_asset = text_dandiset.dandiset.get_asset(path_asset.identifier)
    assert path_asset == id_asset
    assert path_asset._metadata is None
    assert id_asset._metadata is not None
    get_spy = mocker.spy(text_dandiset.client, "get")
    id_metadata = id_asset.get_raw_metadata()
    get_spy.assert_not_called()
    path_metadata = path_asset.get_raw_metadata()
    get_spy.assert_called_once()
    assert path_metadata == id_metadata


@responses.activate
def test_retry_logging(caplog: pytest.LogCaptureFixture) -> None:
    responses.add(responses.GET, "https://test.nil/api/info/", status=503)
    responses.add(responses.GET, "https://test.nil/api/info/", status=503)
    responses.add(responses.GET, "https://test.nil/api/info/", json={"foo": "bar"})
    client = DandiAPIClient("https://test.nil/api")
    assert client.get("/info/") == {"foo": "bar"}
    responses.assert_call_count("https://test.nil/api/info/", 3)
    assert (
        "dandi",
        logging.DEBUG,
        "GET https://test.nil/api/info/",
    ) in caplog.record_tuples
    assert (
        "dandi",
        logging.WARNING,
        "Retrying GET https://test.nil/api/info/",
    ) in caplog.record_tuples
    assert (
        "dandi",
        logging.INFO,
        "GET https://test.nil/api/info/ succeeded after 2 retries",
    ) in caplog.record_tuples
    assert ("dandi", logging.DEBUG, "Response: 200") in caplog.record_tuples


def test_get_assets_order(text_dandiset: SampleDandiset) -> None:
    assert [
        asset.path for asset in text_dandiset.dandiset.get_assets(order="path")
    ] == ["file.txt", "subdir1/apple.txt", "subdir2/banana.txt", "subdir2/coconut.txt"]
    assert [
        asset.path for asset in text_dandiset.dandiset.get_assets(order="-path")
    ] == ["subdir2/coconut.txt", "subdir2/banana.txt", "subdir1/apple.txt", "file.txt"]


def test_get_assets_with_path_prefix(text_dandiset: SampleDandiset) -> None:
    assert sorted(
        asset.path
        for asset in text_dandiset.dandiset.get_assets_with_path_prefix("subdir")
    ) == ["subdir1/apple.txt", "subdir2/banana.txt", "subdir2/coconut.txt"]
    assert sorted(
        asset.path
        for asset in text_dandiset.dandiset.get_assets_with_path_prefix("subdir2")
    ) == ["subdir2/banana.txt", "subdir2/coconut.txt"]
    assert [
        asset.path
        for asset in text_dandiset.dandiset.get_assets_with_path_prefix(
            "subdir", order="path"
        )
    ] == ["subdir1/apple.txt", "subdir2/banana.txt", "subdir2/coconut.txt"]
    assert [
        asset.path
        for asset in text_dandiset.dandiset.get_assets_with_path_prefix(
            "subdir", order="-path"
        )
    ] == ["subdir2/coconut.txt", "subdir2/banana.txt", "subdir1/apple.txt"]


def test_get_assets_by_glob(text_dandiset: SampleDandiset) -> None:
    assert sorted(
        asset.path for asset in text_dandiset.dandiset.get_assets_by_glob("*a*.txt")
    ) == ["subdir1/apple.txt", "subdir2/banana.txt"]
    assert [
        asset.path
        for asset in text_dandiset.dandiset.get_assets_by_glob("*a*.txt", order="path")
    ] == ["subdir1/apple.txt", "subdir2/banana.txt"]
    assert [
        asset.path
        for asset in text_dandiset.dandiset.get_assets_by_glob("*a*.txt", order="-path")
    ] == ["subdir2/banana.txt", "subdir1/apple.txt"]


def test_empty_zarr_iterfiles(new_dandiset: SampleDandiset) -> None:
    client = new_dandiset.client
    r = client.post(
        "/zarr/", json={"name": "empty.zarr", "dandiset": new_dandiset.dandiset_id}
    )
    zarr_id = r["zarr_id"]
    r = client.post(
        f"{new_dandiset.dandiset.version_api_path}assets/",
        json={"metadata": {"path": "empty.zarr"}, "zarr_id": zarr_id},
    )
    a = RemoteAsset.from_data(new_dandiset.dandiset, r)
    assert isinstance(a, RemoteZarrAsset)
    assert list(a.iterfiles()) == []


def test_get_many_pages_of_assets(
    mocker: MockerFixture, new_dandiset: SampleDandiset
) -> None:
    new_dandiset.client.page_size = 4
    get_spy = mocker.spy(new_dandiset.client, "get")
    paths: List[str] = []
    for i in range(26):
        p = new_dandiset.dspath / f"{i:04}.txt"
        paths.append(p.name)
        p.write_text(f"File #{i}\n")
        df = dandi_file(p, new_dandiset.dspath)
        assert isinstance(df, GenericAsset)
        df.upload(new_dandiset.dandiset, {"description": f"File #{i}"})
    assert [
        asset.path for asset in new_dandiset.dandiset.get_assets(order="path")
    ] == paths
    assert get_spy.call_count == 7
    pth = f"{new_dandiset.dandiset.version_api_path}assets/"
    get_spy.assert_any_call(
        pth, params={"order": "path", "page_size": 4}, json_resp=False
    )
    for n in range(2, 8):
        get_spy.assert_any_call(
            pth, params={"order": "path", "page_size": 4, "page": n}
        )


def test_rename(text_dandiset: SampleDandiset) -> None:
    asset = text_dandiset.dandiset.get_asset_by_path("file.txt")
    asset.rename("foo/bar.txt")
    assert asset.path == "foo/bar.txt"
    assert asset.get_raw_metadata()["path"] == "foo/bar.txt"
    asset2 = text_dandiset.dandiset.get_asset_by_path("foo/bar.txt")
    assert asset.identifier == asset2.identifier


def test_rename_collision(text_dandiset: SampleDandiset) -> None:
    asset1 = text_dandiset.dandiset.get_asset_by_path("file.txt")
    asset2 = text_dandiset.dandiset.get_asset_by_path("subdir1/apple.txt")
    with pytest.raises(requests.HTTPError):
        asset1.rename("subdir1/apple.txt")
    assert asset1.path == "file.txt"
    assert asset1.get_raw_metadata()["path"] == "file.txt"
    asset1a = text_dandiset.dandiset.get_asset_by_path("file.txt")
    assert asset1a.path == "file.txt"
    assert asset1a.get_raw_metadata()["path"] == "file.txt"
    asset2a = text_dandiset.dandiset.get_asset_by_path("subdir1/apple.txt")
    assert asset2.identifier == asset2a.identifier


@pytest.mark.xfail(reason="https://github.com/dandi/dandi-archive/issues/1109")
@pytest.mark.parametrize("dest", ["subdir1", "subdir1/apple.txt/core.dat"])
def test_rename_type_mismatch(text_dandiset: SampleDandiset, dest: str) -> None:
    asset1 = text_dandiset.dandiset.get_asset_by_path("file.txt")
    with pytest.raises(requests.HTTPError):
        asset1.rename(dest)
    assert asset1.path == "file.txt"
    assert asset1.get_raw_metadata()["path"] == "file.txt"
    asset1a = text_dandiset.dandiset.get_asset_by_path("file.txt")
    assert asset1a.path == "file.txt"
    assert asset1a.get_raw_metadata()["path"] == "file.txt"
    with pytest.raises(NotFoundError):
        text_dandiset.dandiset.get_asset_by_path(dest)
