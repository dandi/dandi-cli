import pytest

from dandi.consts import known_instances
from dandi.dandiarchive import follow_redirect, parse_dandi_url
from dandi.exceptions import NotFoundError
from dandi.tests.skip import mark


def _assert_parse_girder_url(url):
    st, s, a, aid = parse_dandi_url(url)
    assert st == "girder"
    assert s == known_instances["dandi"].girder + "/"
    return a, aid


def _assert_parse_api_url(url, instance="dandi-api"):
    st, s, a, aid = parse_dandi_url(url)
    assert st == "api"
    assert s == known_instances[instance].api + "/"
    return a, aid


def test_parse_dandi_url():
    # ATM we point to drafts, so girder
    assert _assert_parse_girder_url("DANDI:000027") == (
        "dandiset",
        {"dandiset_id": "000027", "version": "draft"},
    )

    # Example of current web ui (with girder backend) as of 20210119
    assert _assert_parse_girder_url(
        "https://gui.dandiarchive.org/#/dandiset/000003/draft/"
        "files?_id=5e74ee41368d3c79a8006d29&_modelType=folder"
    ) == (
        "folder",
        {
            "dandiset_id": "000003",
            "version": "draft",
            "folder_id": "5e74ee41368d3c79a8006d29",
        },
    )

    # New DANDI web UI driven by DANDI API.
    url1 = "https://gui-beta-dandiarchive-org.netlify.app/#/dandiset/000001"
    assert _assert_parse_api_url(url1) == (
        "dandiset",
        # TODO: in -cli we assume draft, but web ui might be taking the "latest"
        {"dandiset_id": "000001", "version": "draft"},
    )
    assert _assert_parse_api_url(url1 + "/0.201104.2302") == (
        "dandiset",
        {"dandiset_id": "000001", "version": "0.201104.2302"},
    )
    assert _assert_parse_api_url(url1 + "/0.201104.2302/files") == (
        "dandiset",
        {"dandiset_id": "000001", "version": "0.201104.2302"},
    )

    assert _assert_parse_api_url(
        "http://localhost:8000/api/dandisets/000002/versions/draft",
        instance="dandi-api-local-docker-tests",
    ) == ("dandiset", {"dandiset_id": "000002", "version": "draft"})
    # TODO: bring it inline with how it would look whenever there is a folder
    # ATM there is not a single dataset with a folder to see how it looks
    # no trailing / - Yarik considers it to be an item (file)
    # assert _assert_parse_api_url(url1 + "/files?location=%2Fsub-anm369962") == (
    #     "item",
    #     {
    #         "dandiset_id": "000006",
    #         "version": "0.200714.1807",
    #         "location": "sub-anm369962",
    #     },
    # )

    # TODO: bring back a test on deploy-preview-
    # # And the hybrid for "drafts" where it still goes by girder ID
    # assert _assert_parse_api_url(
    #     "https://deploy-preview-341--gui-dandiarchive-org.netlify.app/#/dandiset/000027"
    #     "/draft/files?_id=5f176583f63d62e1dbd06943&_modelType=folder"
    # ) == (
    #     "folder",
    #     {
    #         "dandiset_id": "000027",
    #         "version": "draft",
    #         "folder_id": "5f176583f63d62e1dbd06943",
    #     },
    # )


@mark.skipif_no_network
def test_parse_dandi_url_redirect():
    # Unlikely this one would ever come to existence
    with pytest.raises(NotFoundError):
        parse_dandi_url("https://dandiarchive.org/dandiset/999999")
    # Is there ATM
    assert _assert_parse_girder_url("https://dandiarchive.org/dandiset/000003") == (
        "dandiset",
        {"dandiset_id": "000003", "version": "draft"},
    )
    # And this one would point to a folder
    assert (
        follow_redirect("https://bit.ly/dandi12")
        == "https://gui.dandiarchive.org/#/file-browser/folder/5e72b6ac3da50caa9adb0498"
    )
