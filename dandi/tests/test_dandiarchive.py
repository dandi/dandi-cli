import pytest

from dandi.consts import known_instances
from dandi.dandiarchive import parse_dandi_url, follow_redirect
from dandi.exceptions import NotFoundError
from dandi.tests.skip import mark


def _assert_parse_girder_url(url):
    st, s, a, aid = parse_dandi_url(url)
    assert st == "girder"
    assert s == known_instances["dandi"].girder + "/"
    return a, aid


def _assert_parse_api_url(url):
    st, s, a, aid = parse_dandi_url(url)
    assert st == "api"
    assert s == known_instances["dandi"].api + "/"
    return a, aid


def test_parse_dandi_url():
    # ATM we point to drafts, so girder
    assert _assert_parse_api_url("DANDI:000027") == (
        "dandiset",
        {"dandiset_id": "000027", "version": "draft"},
    )

    # user
    # we do not care about user -- we care about folder id
    assert _assert_parse_girder_url(
        "https://girder.dandiarchive.org/"
        "#user/5da4b8fe51c340795cb18fd0/folder/5e5593cc1a343161ff7c5a92"
    ) == ("folder", ["5e5593cc1a343161ff7c5a92"])
    # dandiset

    # folder
    assert _assert_parse_girder_url(
        "https://gui.dandiarchive.org/#/folder/5e5593cc1a343161ff7c5a92"
    ) == ("folder", ["5e5593cc1a343161ff7c5a92"])

    # selected folder(s)
    # "https://gui.dandiarchive.org/#/folder/5d978d9ecc10d1bc31040bca/selected/folder+5e8672e06cce296e2e817318"

    # selected items and folders
    # "https://gui.dandiarchive.org/#/folder/5d978d9ecc10d1bc31040bca/selected/item+5e8674dc6cce296e2e8173c5/folder+5e8672e06cce296e2e817318"

    # Selected multiple items
    assert _assert_parse_girder_url(
        "https://gui.dandiarchive.org/#/folder/5e7b9e43529c28f35128c745/selected/"
        "item+5e7b9e44529c28f35128c747/item+5e7b9e43529c28f35128c746"
    ) == ("item", ["5e7b9e44529c28f35128c747", "5e7b9e43529c28f35128c746"])

    # new (v1? not yet tagged) web UI, and as it comes from a PR,
    # so we need to provide yet another mapping to stock girder
    assert _assert_parse_girder_url(
        "https://refactor--gui-dandiarchive-org.netlify.app/#/file-browser"
        "/folder/5e9f9588b5c9745bad9f58fe"
    ) == ("folder", ["5e9f9588b5c9745bad9f58fe"])

    # New DANDI web UI driven by DANDI API.  Again no version assigned/planned!
    # see https://github.com/dandi/dandiarchive/pull/341
    url1 = (
        "https://deploy-preview-341--gui-dandiarchive-org.netlify.app/"
        "#/dandiset/000006/0.200714.1807"
    )
    assert _assert_parse_api_url(url1) == (
        "dandiset",
        {"dandiset_id": "000006", "version": "0.200714.1807"},
    )
    assert _assert_parse_api_url(url1 + "/files") == (
        "dandiset",
        {"dandiset_id": "000006", "version": "0.200714.1807"},
    )
    assert _assert_parse_api_url(url1 + "/files?location=%2F") == (
        "dandiset",
        {"dandiset_id": "000006", "version": "0.200714.1807"},
    )
    assert _assert_parse_api_url(url1 + "/files?location=%2Fsub-anm369962%2F") == (
        "folder",
        {
            "dandiset_id": "000006",
            "version": "0.200714.1807",
            "location": "sub-anm369962/",
        },
    )
    # no trailing / - Yarik considers it to be an item (file)
    assert _assert_parse_api_url(url1 + "/files?location=%2Fsub-anm369962") == (
        "item",
        {
            "dandiset_id": "000006",
            "version": "0.200714.1807",
            "location": "sub-anm369962",
        },
    )
    # And the hybrid for "drafts" where it still goes by girder ID
    assert _assert_parse_api_url(
        "https://deploy-preview-341--gui-dandiarchive-org.netlify.app/#/dandiset/000027"
        "/draft/files?_id=5f176583f63d62e1dbd06943&_modelType=folder"
    ) == (
        "folder",
        {
            "dandiset_id": "000027",
            "version": "draft",
            "folder_id": "5f176583f63d62e1dbd06943",
        },
    )


@mark.skipif_no_network
def test_parse_dandi_url_redirect():
    # Unlikely this one would ever come to existence
    with pytest.raises(NotFoundError):
        parse_dandi_url("https://dandiarchive.org/dandiset/999999")
    # Is there ATM
    assert _assert_parse_api_url("https://dandiarchive.org/dandiset/000003") == (
        "dandiset",
        {"dandiset_id": "000003", "version": "draft"},
    )
    # And this one would point to a folder
    assert (
        follow_redirect("https://bit.ly/dandi12")
        == "https://gui.dandiarchive.org/#/file-browser/folder/5e72b6ac3da50caa9adb0498"
    )
