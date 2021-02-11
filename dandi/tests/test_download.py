import json
import os
import os.path as op
from pathlib import Path
from shutil import rmtree

import pytest
import tqdm

from ..consts import dandiset_metadata_file
from ..dandiapi import DandiAPIClient
from ..download import download
from ..girder import TQDMProgressReporter
from ..upload import upload
from ..utils import find_files


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


def test_download_newest_version(local_dandi_api, monkeypatch, tmp_path):
    client = DandiAPIClient(
        api_url=local_dandi_api["instance"].api, token=local_dandi_api["api_key"]
    )
    dandiset_id = client.create_dandiset("Test Dandiset", {})["identifier"]
    upload_dir = tmp_path / "upload"
    upload_dir.mkdir()
    (upload_dir / dandiset_metadata_file).write_text(f"identifier: '{dandiset_id}'\n")
    (upload_dir / "file.txt").write_text("This is test text.\n")
    monkeypatch.chdir(upload_dir)
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    upload(
        paths=[],
        dandi_instance=local_dandi_api["instance_id"],
        devel_debug=True,
        allow_any_path=True,
        validation="skip",
    )
    download_dir = tmp_path / "download"
    download_dir.mkdir()
    download(f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}", download_dir)
    assert (
        download_dir / dandiset_id / "file.txt"
    ).read_text() == "This is test text.\n"
    client.publish_version(dandiset_id, "draft")
    (upload_dir / "file.txt").write_text("This is different text.\n")
    upload(
        paths=[],
        dandi_instance=local_dandi_api["instance_id"],
        devel_debug=True,
        allow_any_path=True,
        validation="skip",
    )
    rmtree(download_dir / dandiset_id)
    download(f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}", download_dir)
    assert (
        download_dir / dandiset_id / "file.txt"
    ).read_text() == "This is test text.\n"


def test_download_folder(local_dandi_api, monkeypatch, tmp_path):
    client = DandiAPIClient(
        api_url=local_dandi_api["instance"].api, token=local_dandi_api["api_key"]
    )
    dandiset_id = client.create_dandiset("Test Dandiset", {})["identifier"]
    upload_dir = tmp_path / "upload"
    upload_dir.mkdir()
    (upload_dir / dandiset_metadata_file).write_text(f"identifier: '{dandiset_id}'\n")
    (upload_dir / "subdir1").mkdir()
    (upload_dir / "subdir1" / "file.txt").write_text("This is test text.\n")
    (upload_dir / "subdir2").mkdir()
    (upload_dir / "subdir2" / "apple.txt").write_text("Apple\n")
    (upload_dir / "subdir2" / "banana.txt").write_text("Banana\n")
    monkeypatch.chdir(upload_dir)
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    upload(
        paths=[],
        dandi_instance=local_dandi_api["instance_id"],
        devel_debug=True,
        allow_any_path=True,
        validation="skip",
    )
    download_dir = tmp_path / "download"
    download_dir.mkdir()
    download(
        f"dandi://{local_dandi_api['instance_id']}/{dandiset_id}/subdir2/", download_dir
    )
    assert sorted(map(Path, find_files(r".*", paths=[download_dir], dirs=True))) == [
        download_dir / "subdir2",
        download_dir / "subdir2" / "apple.txt",
        download_dir / "subdir2" / "banana.txt",
    ]
    assert (download_dir / "subdir2" / "apple.txt").read_text() == "Apple\n"
    assert (download_dir / "subdir2" / "banana.txt").read_text() == "Banana\n"


def test_download_item(local_dandi_api, monkeypatch, tmp_path):
    client = DandiAPIClient(
        api_url=local_dandi_api["instance"].api, token=local_dandi_api["api_key"]
    )
    dandiset_id = client.create_dandiset("Test Dandiset", {})["identifier"]
    upload_dir = tmp_path / "upload"
    upload_dir.mkdir()
    (upload_dir / dandiset_metadata_file).write_text(f"identifier: '{dandiset_id}'\n")
    (upload_dir / "subdir").mkdir()
    (upload_dir / "subdir" / "apple.txt").write_text("Apple\n")
    (upload_dir / "subdir" / "banana.txt").write_text("Banana\n")
    monkeypatch.chdir(upload_dir)
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    upload(
        paths=[],
        dandi_instance=local_dandi_api["instance_id"],
        devel_debug=True,
        allow_any_path=True,
        validation="skip",
    )
    download_dir = tmp_path / "download"
    download_dir.mkdir()
    download(
        f"dandi://{local_dandi_api['instance_id']}/{dandiset_id}/subdir/banana.txt",
        download_dir,
    )
    assert list(map(Path, find_files(r".*", paths=[download_dir], dirs=True))) == [
        download_dir / "banana.txt"
    ]
    assert (download_dir / "banana.txt").read_text() == "Banana\n"
