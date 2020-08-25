import os.path as op

import time
import tqdm

from ..download import download, follow_redirect, parse_dandi_url
from ..exceptions import NotFoundError
from ..tests.skip import mark
from ..consts import known_instances

from ..girder import GirderCli, gcl, TQDMProgressReporter

import pytest


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


@mark.skipif_no_network
def test_download_multiple_files(monkeypatch, tmpdir):
    url = (
        "https://gui.dandiarchive.org/#/folder/5e70d3173da50caa9adaf334/selected/"
        "item+5e70d3173da50caa9adaf335/item+5e70d3183da50caa9adaf336"
    )

    # In 0.6 RF of download we stopped using girder's downloadFile.
    # But we still do up to 3 tries also while getting the downloadFileAsIterator,
    # to this test will test those retries.
    # While at it we will also test girder downloadFile to retry at least 3 times
    # in case of some errors, and that it sleeps between retries
    orig_downloadFileAsIterator = GirderCli.downloadFileAsIterator

    class Mocks:
        ntries = 0
        sleeps = 0

        @staticmethod
        def downloadFileAsIterator(self, *args, **kwargs):
            Mocks.ntries += 1
            if Mocks.ntries < 3:
                raise gcl.HttpError(
                    text="Failing to download", url=url, method="GET", status=500
                )
            return orig_downloadFileAsIterator(self, *args, **kwargs)

        @staticmethod
        def sleep(duration):
            Mocks.sleeps += duration
            # no actual sleeping

    monkeypatch.setattr(
        GirderCli, "downloadFileAsIterator", Mocks.downloadFileAsIterator
    )
    monkeypatch.setattr(time, "sleep", Mocks.sleep)  # to not sleep in the test

    ret = download(url, tmpdir)
    assert not ret  # we return nothing ATM, might want to "generate"

    assert Mocks.ntries == 3 + 1  # 3 on the first since 2 fail + 1 on 2nd file
    assert Mocks.sleeps >= 2  # slept at least 1 sec each time

    downloads = (x.basename for x in tmpdir.listdir())
    assert sorted(downloads) == [
        "sub-anm372795_ses-20170714.nwb",
        "sub-anm372795_ses-20170715.nwb",
    ]
    assert all(x.lstat().size > 1e5 for x in tmpdir.listdir())  # all bigish files


# both urls point to 000027 (lean test dataset), and both draft and "released"
# version have only a single file ATM
@pytest.mark.parametrize(
    "url",
    [  # Should go through API
        "https://dandiarchive.org/dandiset/000027/0.200721.2222",
        # Drafts do not go through API ATM, but that should not be visible to user
        "https://dandiarchive.org/dandiset/000027/draft",
    ],
)
def test_download_000027(url, tmpdir):
    ret = download(url, tmpdir)
    assert not ret  # we return nothing ATM, might want to "generate"
    dsdir = tmpdir / "000027"
    downloads = (x.relto(dsdir) for x in dsdir.visit())
    assert sorted(downloads) == [
        "dandiset.yaml",
        "sub-RAT123",
        op.join("sub-RAT123", "sub-RAT123.nwb"),
    ]
    # and checksum should be correct as well
    from ..support.digests import Digester

    assert (
        Digester(["md5"])(dsdir / "sub-RAT123" / "sub-RAT123.nwb")["md5"]
        == "33318fd510094e4304868b4a481d4a5a"
    )
    # redownload - since already exist there should be an exception
    with pytest.raises(FileExistsError):
        download(url, tmpdir)

    # TODO: somehow get that status report about what was downloaded and what not
    download(url, tmpdir, existing="skip")  # TODO: check that skipped
    download(url, tmpdir, existing="overwrite")  # TODO: check that redownloaded
    download(url, tmpdir, existing="refresh")  # TODO: check that skipped (the same)


@pytest.mark.parametrize(
    "url",
    [  # Should go through API
        "https://dandiarchive.org/dandiset/000027/0.200721.2222",
        # Drafts do not go through API ATM, but that should not be visible to user
        "https://dandiarchive.org/dandiset/000027/draft",
    ],
)
def test_download_000027_metadata_only(url, tmpdir):
    ret = download(url, tmpdir, get_assets=False)
    assert not ret  # we return nothing ATM, might want to "generate"
    dsdir = tmpdir / "000027"
    downloads = (x.relto(dsdir) for x in dsdir.visit())
    assert sorted(downloads) == ["dandiset.yaml"]


@pytest.mark.parametrize(
    "url",
    [  # Should go through API
        "https://dandiarchive.org/dandiset/000027/0.200721.2222",
        # Drafts do not go through API ATM, but that should not be visible to user
        "https://dandiarchive.org/dandiset/000027/draft",
    ],
)
def test_download_000027_assets_only(url, tmpdir):
    ret = download(url, tmpdir, get_metadata=False)
    assert not ret  # we return nothing ATM, might want to "generate"
    dsdir = tmpdir / "000027"
    downloads = (x.relto(dsdir) for x in dsdir.visit())
    assert sorted(downloads) == ["sub-RAT123", op.join("sub-RAT123", "sub-RAT123.nwb")]


def test_girder_tqdm(monkeypatch):
    # smoke test to ensure we do not blow up
    def raise_assertion_error(*args, **kwargs):
        assert False, "pretend locking failed"

    monkeypatch.setattr(tqdm, "tqdm", raise_assertion_error)

    with TQDMProgressReporter() as pr:
        pr.update(10)
