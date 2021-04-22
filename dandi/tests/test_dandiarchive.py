import pytest
import responses

from dandi.consts import known_instances
from dandi.dandiarchive import follow_redirect, parse_dandi_url
from dandi.exceptions import NotFoundError
from dandi.tests.skip import mark


@pytest.mark.parametrize(
    "url,instance,asset_type,asset_id",
    [
        # New DANDI web UI driven by DANDI API.
        (
            "https://gui.dandiarchive.org/#/dandiset/000001",
            "dandi",
            "dandiset",
            {"dandiset_id": "000001", "version": None},
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/000001/0.201104.2302",
            "dandi",
            "dandiset",
            {"dandiset_id": "000001", "version": "0.201104.2302"},
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/000001/0.201104.2302/files",
            "dandi",
            "dandiset",
            {"dandiset_id": "000001", "version": "0.201104.2302"},
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/000001",
            "dandi",
            "dandiset",
            {"dandiset_id": "000001", "version": None},
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/000001/draft",
            "dandi",
            "dandiset",
            {"dandiset_id": "000001", "version": "draft"},
        ),
        (
            "DANDI:000027",
            "dandi",
            "dandiset",
            {"dandiset_id": "000027", "version": "draft"},  # TODO: why not None?
        ),
        (
            "http://localhost:8000/api/dandisets/000002/versions/draft",
            "dandi-api-local-docker-tests",
            "dandiset",
            {"dandiset_id": "000002", "version": "draft"},
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/000001/files"
            "?location=%2Fsub-anm369962",
            "dandi",
            "item",
            {"dandiset_id": "000001", "version": None, "location": "sub-anm369962"},
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/000006/0.200714.1807/files"
            "?location=%2Fsub-anm369962",
            "dandi",
            "item",
            {
                "dandiset_id": "000006",
                "version": "0.200714.1807",
                "location": "sub-anm369962",
            },
        ),
        (
            "https://gui.dandiarchive.org/#/dandiset/001001/draft/files"
            "?location=sub-RAT123%2F",
            "dandi",
            "folder",
            {"dandiset_id": "001001", "version": "draft", "location": "sub-RAT123/"},
        ),
        # by direct instance name ad-hoc URI instance:ID[@version][/path]
        (
            "dandi://dandi-api-local-docker-tests/000002@draft",
            "dandi-api-local-docker-tests",
            "dandiset",
            {"dandiset_id": "000002", "version": "draft"},
        ),
        (
            "dandi://dandi-api-local-docker-tests/000002@draft/path",
            "dandi-api-local-docker-tests",
            "item",
            {"dandiset_id": "000002", "location": "path", "version": "draft"},
        ),
        (
            "dandi://dandi-api-local-docker-tests/000002/path",
            "dandi-api-local-docker-tests",
            "item",
            {"dandiset_id": "000002", "location": "path", "version": None},
        ),
        (  # test on "public" instance and have trailing / to signal the folder
            "dandi://dandi/000002/path/",
            "dandi",
            "folder",
            {"dandiset_id": "000002", "location": "path/", "version": None},
        ),
        (
            "https://api.dandiarchive.org/api/dandisets/000003/versions/draft"
            "/assets/0a748f90-d497-4a9c-822e-9c63811db412/download/",
            "dandi",
            "item",
            {
                "dandiset_id": "000003",
                "version": "draft",
                "asset_id": "0a748f90-d497-4a9c-822e-9c63811db412",
            },
        ),
        (
            "https://api.dandiarchive.org/api/dandisets/000003/versions/draft"
            "/assets/?path=sub-YutaMouse20",
            "dandi",
            "folder",
            {
                "dandiset_id": "000003",
                "version": "draft",
                "location": "sub-YutaMouse20",
            },
        ),
    ],
)
def test_parse_api_url(url, instance, asset_type, asset_id):
    st, s, a, aid = parse_dandi_url(url)
    assert st == "api"
    assert s == known_instances[instance].api + "/"
    assert a == asset_type
    assert aid == asset_id


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
    assert parse_dandi_url("https://gui.dandiarchive.org/#/dandiset/000003") == (
        "api",
        "https://api.dandiarchive.org/api/",
        "dandiset",
        {"dandiset_id": "000003", "version": None},
    )
