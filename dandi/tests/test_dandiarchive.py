import pytest

from dandi.consts import known_instances
from dandi.dandiarchive import follow_redirect, parse_dandi_url
from dandi.exceptions import NotFoundError
from dandi.tests.skip import mark


@pytest.mark.parametrize(
    "url,asset_type,asset_id",
    [
        # ATM we point to drafts, so girder
        ("DANDI:000027", "dandiset", {"dandiset_id": "000027", "version": "draft"}),
        # Example of current web ui (with girder backend) as of 20210119
        (
            "https://gui.dandiarchive.org/#/dandiset/000003/draft/"
            "files?_id=5e74ee41368d3c79a8006d29&_modelType=folder",
            "folder",
            {
                "dandiset_id": "000003",
                "version": "draft",
                "folder_id": "5e74ee41368d3c79a8006d29",
            },
        ),
        pytest.param(
            "https://dandiarchive.org/dandiset/000003",
            "dandiset",
            {"dandiset_id": "000003", "version": "draft"},
            marks=mark.skipif_no_network,
        ),
    ],
)
def test_parse_girder_url(url, asset_type, asset_id):
    st, s, a, aid = parse_dandi_url(url)
    assert st == "girder"
    assert s == known_instances["dandi"].girder + "/"
    assert a == asset_type
    assert aid == asset_id


@pytest.mark.parametrize(
    "url,instance,asset_type,asset_id",
    [
        # New DANDI web UI driven by DANDI API.
        (
            "https://gui-beta-dandiarchive-org.netlify.app/#/dandiset/000001",
            "dandi-api",
            "dandiset",
            {"dandiset_id": "000001", "version": None},
        ),
        (
            "https://gui-beta-dandiarchive-org.netlify.app/#/dandiset/000001/0.201104.2302",
            "dandi-api",
            "dandiset",
            {"dandiset_id": "000001", "version": "0.201104.2302"},
        ),
        (
            "https://gui-beta-dandiarchive-org.netlify.app/#/dandiset/000001/0.201104.2302/files",
            "dandi-api",
            "dandiset",
            {"dandiset_id": "000001", "version": "0.201104.2302"},
        ),
        (
            "http://localhost:8000/api/dandisets/000002/versions/draft",
            "dandi-api-local-docker-tests",
            "dandiset",
            {"dandiset_id": "000002", "version": "draft"},
        ),
        (
            "https://gui-beta-dandiarchive-org.netlify.app/#/dandiset/000001/"
            "files?location=%2Fsub-anm369962",
            "dandi-api",
            "item",
            {"dandiset_id": "000001", "version": None, "location": "sub-anm369962"},
        ),
        (
            "https://gui-beta-dandiarchive-org.netlify.app/#/dandiset/000006/"
            "0.200714.1807/files?location=%2Fsub-anm369962",
            "dandi-api",
            "item",
            {
                "dandiset_id": "000006",
                "version": "0.200714.1807",
                "location": "sub-anm369962",
            },
        ),
        (
            "https://gui-beta-dandiarchive-org.netlify.app/#/dandiset/001001/"
            "draft/files?location=sub-RAT123%2F",
            "dandi-api",
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
            "dandi://dandi-api/000002/path/",
            "dandi-api",
            "folder",
            {"dandiset_id": "000002", "location": "path/", "version": None},
        ),
        # TODO: bring back a test on deploy-preview-
        # # And the hybrid for "drafts" where it still goes by girder ID
        # (
        #     "https://deploy-preview-341--gui-dandiarchive-org.netlify.app/#/dandiset/000027"
        #     "/draft/files?_id=5f176583f63d62e1dbd06943&_modelType=folder",
        #     "dandi-api",
        #     "folder",
        #     {
        #         "dandiset_id": "000027",
        #         "version": "draft",
        #         "folder_id": "5f176583f63d62e1dbd06943",
        #     },
        # )
        (
            "https://api.dandiarchive.org/api/dandisets/000003/versions/draft"
            "/assets/0a748f90-d497-4a9c-822e-9c63811db412/download/",
            "dandi-api",
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
            "dandi-api",
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
