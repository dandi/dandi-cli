import json
import os
import os.path as op

import time
import tqdm

from ..download import download
from ..tests.skip import mark

from ..girder import GirderCli, gcl, TQDMProgressReporter

import pytest


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
    orig_sendRestRequest = GirderCli.sendRestRequest

    class Mocks:
        ntries = 0
        sleeps = 0

        @staticmethod
        def sendRestRequest(self, *args, **kwargs):
            if (
                len(args) > 1
                and args[1].startswith("file/")
                and args[1].endswith("/download")
            ):
                Mocks.ntries += 1
                if Mocks.ntries < 3:
                    raise gcl.HttpError(
                        text="Failing to download", url=url, method="GET", status=500
                    )
            return orig_sendRestRequest(self, *args, **kwargs)

        @staticmethod
        def sleep(duration):
            Mocks.sleeps += duration
            # no actual sleeping

    monkeypatch.setattr(GirderCli, "sendRestRequest", Mocks.sendRestRequest)
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
        pytest.param(
            "https://dandiarchive.org/dandiset/000027/0.200721.2222",
            marks=pytest.mark.xfail(reason="publish.dandiarchive.org is gone"),
        ),
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
        pytest.param(
            "https://dandiarchive.org/dandiset/000027/0.200721.2222",
            marks=pytest.mark.xfail(reason="publish.dandiarchive.org is gone"),
        ),
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
        pytest.param(
            "https://dandiarchive.org/dandiset/000027/0.200721.2222",
            marks=pytest.mark.xfail(reason="publish.dandiarchive.org is gone"),
        ),
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


@pytest.mark.parametrize("resizer", [lambda sz: 0, lambda sz: sz // 2, lambda sz: sz])
@pytest.mark.parametrize(
    "version",
    [
        pytest.param(
            "0.200721.2222",
            marks=pytest.mark.xfail(reason="publish.dandiarchive.org is gone"),
        ),
        "draft",
    ],
)
def test_download_000027_resume(tmp_path, resizer, version):
    from ..support.digests import Digester

    url = f"https://dandiarchive.org/dandiset/000027/{version}"
    digester = Digester()
    download(url, tmp_path, get_metadata=False)
    dsdir = tmp_path / "000027"
    nwb = dsdir / "sub-RAT123" / "sub-RAT123.nwb"
    digests = digester(str(nwb))
    dldir = nwb.with_name(nwb.name + ".dandidownload")
    dldir.mkdir()
    dlfile = dldir / "file"
    nwb.rename(dlfile)
    size = dlfile.stat().st_size
    os.truncate(dlfile, resizer(size))
    with (dldir / "checksum").open("w") as fp:
        json.dump(digests, fp)
    download(url, tmp_path, get_metadata=False)
    contents = [
        op.relpath(op.join(dirpath, entry), dsdir)
        for (dirpath, dirnames, filenames) in os.walk(dsdir)
        for entry in dirnames + filenames
    ]
    assert sorted(contents) == ["sub-RAT123", op.join("sub-RAT123", "sub-RAT123.nwb")]
    assert nwb.stat().st_size == size
    assert digester(str(nwb)) == digests
