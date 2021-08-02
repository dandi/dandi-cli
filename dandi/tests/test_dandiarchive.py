import pytest
import responses

from dandi.consts import known_instances
from dandi.dandiarchive import (
    AssetFolderURL,
    AssetIDURL,
    AssetItemURL,
    AssetPathPrefixURL,
    BaseAssetIDURL,
    DandisetURL,
    follow_redirect,
    parse_dandi_url,
)
from dandi.exceptions import NotFoundError
from dandi.tests.skip import mark


@pytest.mark.parametrize(
    "url,parsed_url",
    [
        # New DANDI web UI driven by DANDI API.
        (
            "https://gui.dandiarchive.org/#/dandiset/000001",
            DandisetURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000001",
                version_id=None,
            ),
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/000001/",
            DandisetURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000001",
                version_id=None,
            ),
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/000001/0.201104.2302",
            DandisetURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000001",
                version_id="0.201104.2302",
            ),
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/000001/0.201104.2302/",
            DandisetURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000001",
                version_id="0.201104.2302",
            ),
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/000001/0.201104.2302/files",
            DandisetURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000001",
                version_id="0.201104.2302",
            ),
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/000001/draft",
            DandisetURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000001",
                version_id="draft",
            ),
        ),
        (
            "https://gui.dandiarchive.org/dandiset/000001",
            DandisetURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000001",
                version_id=None,
            ),
        ),
        (
            "https://gui.dandiarchive.org/dandiset/000001/0.201104.2302",
            DandisetURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000001",
                version_id="0.201104.2302",
            ),
        ),
        (
            "https://gui.dandiarchive.org/dandiset/000001/0.201104.2302/files",
            DandisetURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000001",
                version_id="0.201104.2302",
            ),
        ),
        (
            "https://gui.dandiarchive.org/dandiset/000001/draft",
            DandisetURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000001",
                version_id="draft",
            ),
        ),
        (
            "DANDI:000027",
            DandisetURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000027",
                version_id="draft",  # TODO: why not None?
            ),
        ),
        (
            "http://localhost:8000/api/dandisets/000002/versions/draft",
            DandisetURL(
                api_url="http://localhost:8000/api",
                dandiset_id="000002",
                version_id="draft",
            ),
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/000001/files"
            "?location=%2Fsub-anm369962",
            AssetItemURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000001",
                version_id=None,
                path="sub-anm369962",
            ),
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/000006/0.200714.1807/files"
            "?location=%2Fsub-anm369962",
            AssetItemURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000006",
                version_id="0.200714.1807",
                path="sub-anm369962",
            ),
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/001001/draft/files"
            "?location=sub-RAT123%2F",
            AssetFolderURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="001001",
                version_id="draft",
                path="sub-RAT123/",
            ),
        ),
        # by direct instance name ad-hoc URI instance:ID[@version][/path]
        (
            "dandi://dandi-api-local-docker-tests/000002@draft",
            DandisetURL(
                api_url=known_instances["dandi-api-local-docker-tests"].api,
                dandiset_id="000002",
                version_id="draft",
            ),
        ),
        (
            "dandi://dandi-api-local-docker-tests/000002@draft/path",
            AssetItemURL(
                api_url=known_instances["dandi-api-local-docker-tests"].api,
                dandiset_id="000002",
                version_id="draft",
                path="path",
            ),
        ),
        (
            "dandi://dandi-api-local-docker-tests/000002/path",
            AssetItemURL(
                api_url=known_instances["dandi-api-local-docker-tests"].api,
                dandiset_id="000002",
                version_id=None,
                path="path",
            ),
        ),
        (  # test on "public" instance and have trailing / to signal the folder
            "dandi://dandi/000002/path/",
            AssetFolderURL(
                api_url=known_instances["dandi"].api,
                dandiset_id="000002",
                version_id=None,
                path="path/",
            ),
        ),
        (
            "https://api.dandiarchive.org/api/dandisets/000003/versions/draft"
            "/assets/0a748f90-d497-4a9c-822e-9c63811db412/download/",
            AssetIDURL(
                api_url="https://api.dandiarchive.org/api",
                dandiset_id="000003",
                version_id="draft",
                asset_id="0a748f90-d497-4a9c-822e-9c63811db412",
            ),
        ),
        (
            "https://api.dandiarchive.org/api"
            "/assets/0a748f90-d497-4a9c-822e-9c63811db412/download/",
            BaseAssetIDURL(
                api_url="https://api.dandiarchive.org/api",
                asset_id="0a748f90-d497-4a9c-822e-9c63811db412",
            ),
        ),
        (
            "https://api.dandiarchive.org/api/dandisets/000003/versions/draft"
            "/assets/?path=sub-YutaMouse20",
            AssetPathPrefixURL(
                api_url="https://api.dandiarchive.org/api",
                dandiset_id="000003",
                version_id="draft",
                path="sub-YutaMouse20",
            ),
        ),
    ],
)
def test_parse_api_url(url, parsed_url):
    assert parse_dandi_url(url) == parsed_url


@mark.skipif_no_network
def test_parse_dandi_url_not_found():
    # Unlikely this one would ever come to existence
    with pytest.raises(NotFoundError):
        parse_dandi_url("https://dandiarchive.org/dandiset/999999")


@mark.skipif_no_network
def test_follow_redirect():
    assert (
        follow_redirect("https://bit.ly/dandi12")
        == "https://gui.dandiarchive.org/#/file-browser/folder/5e72b6ac3da50caa9adb0498"
    )


@responses.activate
def test_parse_gui_new_redirect():
    redirector_base = known_instances["dandi"].redirector
    responses.add(
        responses.GET,
        f"{redirector_base}/server-info",
        json={
            "version": "1.2.0",
            "cli-minimal-version": "0.6.0",
            "cli-bad-versions": [],
            "services": {
                "webui": {"url": "https://gui.dandirchive.org"},
                "api": {"url": "https://api.dandiarchive.org/api"},
                "jupyterhub": {"url": "https://hub.dandiarchive.org"},
            },
        },
    )
    assert parse_dandi_url(
        "https://gui.dandiarchive.org/#/dandiset/000003"
    ) == DandisetURL(
        api_url="https://api.dandiarchive.org/api",
        dandiset_id="000003",
        version_id=None,
    )
