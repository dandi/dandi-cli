from ..download import download, parse_dandi_url
from ..exceptions import NotFoundError
from ..tests.skip import mark

import pytest


def test_parse_dandi_url():
    # user
    s, a, aid = parse_dandi_url(
        "https://girder.dandiarchive.org/"
        "#user/5da4b8fe51c340795cb18fd0/folder/5e5593cc1a343161ff7c5a92"
    )
    # we do not care about user -- we care about folder id
    assert a, aid == ("folder", "5e5593cc1a343161ff7c5a92")
    # dandiset

    # folder
    s, a, aid = parse_dandi_url(
        "https://gui.dandiarchive.org/#/folder/5e5593cc1a343161ff7c5a92"
    )
    assert s == "https://girder.dandiarchive.org/"
    assert a, aid == ("folder", "5e5593cc1a343161ff7c5a92")

    # selected folder(s)
    # "https://gui.dandiarchive.org/#/folder/5d978d9ecc10d1bc31040bca/selected/folder+5e8672e06cce296e2e817318"

    # selected items and folders
    # "https://gui.dandiarchive.org/#/folder/5d978d9ecc10d1bc31040bca/selected/item+5e8674dc6cce296e2e8173c5/folder+5e8672e06cce296e2e817318"

    # Selected multiple items
    s, a, aid = parse_dandi_url(
        "https://gui.dandiarchive.org/#/folder/5e7b9e43529c28f35128c745/selected/"
        "item+5e7b9e44529c28f35128c747/item+5e7b9e43529c28f35128c746"
    )
    assert s == "https://girder.dandiarchive.org/"
    assert a, aid == ("item", ["5e7b9e44529c28f35128c747", "5e7b9e43529c28f35128c746"])

    # new (v1? not yet tagged) web UI, and as it comes from a PR,
    # so we need to provide yet another mapping to stock girder
    s, a, aid = parse_dandi_url(
        "https://refactor--gui-dandiarchive-org.netlify.app/#/file-browser/folder/5e9f9588b5c9745bad9f58fe"
    )
    assert s == "https://girder.dandiarchive.org"
    assert a, aid == "folder"["5e9f9588b5c9745bad9f58fe"]


@mark.skipif_no_network
def test_parse_dandi_url_redirect():
    # Unlikely this one would ever come to existence
    with pytest.raises(NotFoundError):
        parse_dandi_url("https://dandiarchive.org/dandiset/999999")
    # Is there ATM
    s, a, aid = parse_dandi_url("https://dandiarchive.org/dandiset/000003")
    assert s == "https://girder.dandiarchive.org/"
    assert a, aid == ("dandiset-meta", "5e6eb2b776569eb93f451f8d")


@mark.skipif_no_network
def test_download_multiple_files(tmpdir):
    url = (
        "https://gui.dandiarchive.org/#/folder/5e70d3173da50caa9adaf334/selected/"
        "item+5e70d3173da50caa9adaf335/item+5e70d3183da50caa9adaf336"
    )

    ret = download(url, tmpdir)
    assert not ret  # we return nothing ATM, might want to "generate"
    downloads = (x.basename for x in tmpdir.listdir())
    assert sorted(downloads) == [
        "sub-anm372795_ses-20170714.nwb",
        "sub-anm372795_ses-20170715.nwb",
    ]
    assert all(x.lstat().size > 1e5 for x in tmpdir.listdir())  # all bigish files
