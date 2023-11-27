from __future__ import annotations

from collections.abc import Callable
import json
import os
import os.path
from pathlib import Path
import re
from shutil import rmtree
import time

import numpy as np
import pytest
from pytest_mock import MockerFixture
import responses
import zarr

from .fixtures import SampleDandiset, SampleDandisetFactory
from .skip import mark
from .test_helpers import assert_dirtrees_eq
from ..consts import DRAFT, dandiset_metadata_file
from ..dandiarchive import DandisetURL
from ..download import (
    Downloader,
    DownloadExisting,
    DownloadFormat,
    PathType,
    ProgressCombiner,
    PYOUTHelper,
    download,
)
from ..exceptions import NotFoundError
from ..utils import list_paths


# both urls point to 000027 (lean test dataset), and both draft and "released"
# version have only a single file ATM
@mark.skipif_no_network
@pytest.mark.parametrize(
    "url",
    [  # Should go through API
        "https://dandiarchive.org/dandiset/000027/0.210831.2033",
        # Drafts do not go through API ATM, but that should not be visible to user
        "https://dandiarchive.org/dandiset/000027/draft",
    ],
)
def test_download_000027(
    url: str, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    ret = download(url, tmp_path)  # type: ignore[func-returns-value]
    assert not ret  # we return nothing ATM, might want to "generate"
    dsdir = tmp_path / "000027"
    assert list_paths(dsdir, dirs=True) == [
        dsdir / "dandiset.yaml",
        dsdir / "sub-RAT123",
        dsdir / "sub-RAT123" / "sub-RAT123.nwb",
    ]
    # and checksum should be correct as well
    from ..support.digests import Digester

    assert (
        Digester(["md5"])(dsdir / "sub-RAT123" / "sub-RAT123.nwb")["md5"]
        == "33318fd510094e4304868b4a481d4a5a"
    )
    # redownload - since already exist there should be an exception if we are
    # not using pyout
    with pytest.raises(FileExistsError):
        download(url, tmp_path, format=DownloadFormat.DEBUG)
    assert "FileExistsError" not in capsys.readouterr().out
    # but  no exception is raised, and rather it gets output to pyout otherwise
    download(url, tmp_path)
    assert "FileExistsError" in capsys.readouterr().out

    # TODO: somehow get that status report about what was downloaded and what not
    download(url, tmp_path, existing=DownloadExisting.SKIP)  # TODO: check that skipped
    download(
        url, tmp_path, existing=DownloadExisting.OVERWRITE
    )  # TODO: check that redownloaded
    download(
        url, tmp_path, existing=DownloadExisting.REFRESH
    )  # TODO: check that skipped (the same)


@mark.skipif_no_network
@pytest.mark.parametrize(
    "url",
    [  # Should go through API
        "https://dandiarchive.org/dandiset/000027/0.210831.2033",
        # Drafts do not go through API ATM, but that should not be visible to user
        "https://dandiarchive.org/dandiset/000027/draft",
    ],
)
def test_download_000027_metadata_only(url: str, tmp_path: Path) -> None:
    ret = download(url, tmp_path, get_assets=False)  # type: ignore[func-returns-value]
    assert not ret  # we return nothing ATM, might want to "generate"
    dsdir = tmp_path / "000027"
    assert list_paths(dsdir, dirs=True) == [dsdir / "dandiset.yaml"]


@mark.skipif_no_network
@pytest.mark.parametrize(
    "url",
    [  # Should go through API
        "https://dandiarchive.org/dandiset/000027/0.210831.2033",
        # Drafts do not go through API ATM, but that should not be visible to user
        "https://dandiarchive.org/dandiset/000027/draft",
    ],
)
def test_download_000027_assets_only(url: str, tmp_path: Path) -> None:
    ret = download(url, tmp_path, get_metadata=False)  # type: ignore[func-returns-value]
    assert not ret  # we return nothing ATM, might want to "generate"
    dsdir = tmp_path / "000027"
    assert list_paths(dsdir, dirs=True) == [
        dsdir / "sub-RAT123",
        dsdir / "sub-RAT123" / "sub-RAT123.nwb",
    ]


@mark.skipif_no_network
@pytest.mark.parametrize("resizer", [lambda sz: 0, lambda sz: sz // 2, lambda sz: sz])
@pytest.mark.parametrize("version", ["0.210831.2033", DRAFT])
def test_download_000027_resume(
    tmp_path: Path, resizer: Callable[[int], int], version: str
) -> None:
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
    assert list_paths(dsdir, dirs=True) == [
        dsdir / "sub-RAT123",
        dsdir / "sub-RAT123" / "sub-RAT123.nwb",
    ]
    assert nwb.stat().st_size == size
    assert digester(str(nwb)) == digests


def test_download_newest_version(text_dandiset: SampleDandiset, tmp_path: Path) -> None:
    dandiset = text_dandiset.dandiset
    dandiset_id = text_dandiset.dandiset_id
    download(dandiset.api_url, tmp_path)
    assert (tmp_path / dandiset_id / "file.txt").read_text() == "This is test text.\n"
    dandiset.wait_until_valid()
    dandiset.publish()
    (text_dandiset.dspath / "file.txt").write_text("This is different text.\n")
    text_dandiset.upload()
    rmtree(tmp_path / dandiset_id)
    download(dandiset.api_url, tmp_path)
    assert (tmp_path / dandiset_id / "file.txt").read_text() == "This is test text.\n"


def test_download_folder(text_dandiset: SampleDandiset, tmp_path: Path) -> None:
    dandiset_id = text_dandiset.dandiset_id
    download(
        f"dandi://{text_dandiset.api.instance_id}/{dandiset_id}/subdir2/", tmp_path
    )
    assert list_paths(tmp_path, dirs=True) == [
        tmp_path / "subdir2",
        tmp_path / "subdir2" / "banana.txt",
        tmp_path / "subdir2" / "coconut.txt",
    ]
    assert (tmp_path / "subdir2" / "banana.txt").read_text() == "Banana\n"
    assert (tmp_path / "subdir2" / "coconut.txt").read_text() == "Coconut\n"


def test_download_item(text_dandiset: SampleDandiset, tmp_path: Path) -> None:
    dandiset_id = text_dandiset.dandiset_id
    download(
        f"dandi://{text_dandiset.api.instance_id}/{dandiset_id}/subdir2/coconut.txt",
        tmp_path,
    )
    assert list_paths(tmp_path, dirs=True) == [tmp_path / "coconut.txt"]
    assert (tmp_path / "coconut.txt").read_text() == "Coconut\n"


def test_download_asset_id(text_dandiset: SampleDandiset, tmp_path: Path) -> None:
    asset = text_dandiset.dandiset.get_asset_by_path("subdir2/coconut.txt")
    download(asset.download_url, tmp_path)
    assert list_paths(tmp_path, dirs=True) == [tmp_path / "coconut.txt"]
    assert (tmp_path / "coconut.txt").read_text() == "Coconut\n"


def test_download_asset_id_only(text_dandiset: SampleDandiset, tmp_path: Path) -> None:
    asset = text_dandiset.dandiset.get_asset_by_path("subdir2/coconut.txt")
    download(asset.base_download_url, tmp_path)
    assert list_paths(tmp_path, dirs=True) == [tmp_path / "coconut.txt"]
    assert (tmp_path / "coconut.txt").read_text() == "Coconut\n"


def test_download_asset_by_equal_prefix(
    text_dandiset: SampleDandiset, tmp_path: Path
) -> None:
    download(
        f"{text_dandiset.dandiset.version_api_url}assets/?path=subdir1/apple.txt",
        tmp_path,
    )
    assert list_paths(tmp_path, dirs=True) == [tmp_path / "apple.txt"]
    assert (tmp_path / "apple.txt").read_text() == "Apple\n"


@pytest.mark.parametrize("confirm", [True, False])
def test_download_sync(
    confirm: bool, mocker: MockerFixture, text_dandiset: SampleDandiset, tmp_path: Path
) -> None:
    text_dandiset.dandiset.get_asset_by_path("file.txt").delete()
    dspath = tmp_path / text_dandiset.dandiset_id
    os.rename(text_dandiset.dspath, dspath)
    confirm_mock = mocker.patch(
        "dandi.download.abbrev_prompt", return_value="yes" if confirm else "no"
    )
    download(
        f"dandi://{text_dandiset.api.instance_id}/{text_dandiset.dandiset_id}",
        tmp_path,
        existing=DownloadExisting.OVERWRITE,
        sync=True,
    )
    confirm_mock.assert_called_with("Delete 1 local asset?", "yes", "no", "list")
    if confirm:
        assert not (dspath / "file.txt").exists()
    else:
        assert (dspath / "file.txt").exists()


def test_download_sync_folder(
    mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    text_dandiset.dandiset.get_asset_by_path("file.txt").delete()
    text_dandiset.dandiset.get_asset_by_path("subdir2/banana.txt").delete()
    confirm_mock = mocker.patch("dandi.download.abbrev_prompt", return_value="yes")
    download(
        f"dandi://{text_dandiset.api.instance_id}/{text_dandiset.dandiset_id}/subdir2/",
        text_dandiset.dspath,
        existing=DownloadExisting.OVERWRITE,
        sync=True,
    )
    confirm_mock.assert_called_with("Delete 1 local asset?", "yes", "no", "list")
    assert (text_dandiset.dspath / "file.txt").exists()
    assert not (text_dandiset.dspath / "subdir2" / "banana.txt").exists()


def test_download_sync_list(
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
    text_dandiset: SampleDandiset,
    tmp_path: Path,
) -> None:
    text_dandiset.dandiset.get_asset_by_path("file.txt").delete()
    dspath = tmp_path / text_dandiset.dandiset_id
    os.rename(text_dandiset.dspath, dspath)
    input_mock = mocker.patch("dandi.utils.input", side_effect=["list", "yes"])
    download(
        f"dandi://{text_dandiset.api.instance_id}/{text_dandiset.dandiset_id}",
        tmp_path,
        existing=DownloadExisting.OVERWRITE,
        sync=True,
    )
    assert not (dspath / "file.txt").exists()
    assert input_mock.call_args_list == [
        mocker.call("Delete 1 local asset? ([y]es/[n]o/[l]ist): "),
        mocker.call("Delete 1 local asset? ([y]es/[n]o/[l]ist): "),
    ]
    assert capsys.readouterr().out.splitlines()[-1] == str(dspath / "file.txt")


def test_download_sync_zarr(
    mocker: MockerFixture, zarr_dandiset: SampleDandiset, tmp_path: Path
) -> None:
    zarr_dandiset.dandiset.get_asset_by_path("sample.zarr").delete()
    dspath = tmp_path / zarr_dandiset.dandiset_id
    os.rename(zarr_dandiset.dspath, dspath)
    confirm_mock = mocker.patch("dandi.download.abbrev_prompt", return_value="yes")
    download(
        zarr_dandiset.dandiset.version_api_url,
        tmp_path,
        existing=DownloadExisting.OVERWRITE,
        sync=True,
    )
    confirm_mock.assert_called_with("Delete 1 local asset?", "yes", "no", "list")
    assert not (dspath / "sample.zarr").exists()


@responses.activate
def test_download_no_blobDateModified(
    text_dandiset: SampleDandiset, tmp_path: Path
) -> None:
    # Regression test for #806
    responses.add_passthru(re.compile("^http"))
    dandiset = text_dandiset.dandiset
    asset = dandiset.get_asset_by_path("file.txt")
    metadata = asset.get_raw_metadata()
    del metadata["blobDateModified"]
    responses.add(responses.GET, asset.api_url, json=metadata)
    download(dandiset.api_url, tmp_path)


@responses.activate
def test_download_metadata404(text_dandiset: SampleDandiset, tmp_path: Path) -> None:
    responses.add_passthru(re.compile("^http"))
    asset = text_dandiset.dandiset.get_asset_by_path("subdir1/apple.txt")
    responses.add(responses.GET, asset.api_url, status=404)
    statuses = list(
        Downloader(
            url=DandisetURL(
                instance=text_dandiset.api.instance,
                dandiset_id=text_dandiset.dandiset.identifier,
                version_id=text_dandiset.dandiset.version_id,
            ),
            output_dir=tmp_path,
            existing=DownloadExisting.ERROR,
            get_metadata=True,
            get_assets=True,
            jobs_per_zarr=None,
            on_error="raise",
        ).download_generator()
    )
    errors = [s for s in statuses if s.get("status") == "error"]
    assert errors == [
        {
            "path": os.path.join(text_dandiset.dandiset_id, "subdir1", "apple.txt"),
            "status": "error",
            "message": f"No such asset: {asset}",
        }
    ]
    assert list_paths(tmp_path, dirs=True) == [
        tmp_path / text_dandiset.dandiset_id,
        tmp_path / text_dandiset.dandiset_id / dandiset_metadata_file,
        tmp_path / text_dandiset.dandiset_id / "file.txt",
        tmp_path / text_dandiset.dandiset_id / "subdir2",
        tmp_path / text_dandiset.dandiset_id / "subdir2" / "banana.txt",
        tmp_path / text_dandiset.dandiset_id / "subdir2" / "coconut.txt",
    ]


def test_download_zarr(tmp_path: Path, zarr_dandiset: SampleDandiset) -> None:
    download(zarr_dandiset.dandiset.version_api_url, tmp_path)
    assert_dirtrees_eq(
        zarr_dandiset.dspath / "sample.zarr",
        tmp_path / zarr_dandiset.dandiset_id / "sample.zarr",
    )


def test_download_different_zarr(tmp_path: Path, zarr_dandiset: SampleDandiset) -> None:
    dd = tmp_path / zarr_dandiset.dandiset_id
    dd.mkdir()
    zarr.save(dd / "sample.zarr", np.eye(5))
    download(
        zarr_dandiset.dandiset.version_api_url,
        tmp_path,
        existing=DownloadExisting.OVERWRITE_DIFFERENT,
    )
    assert_dirtrees_eq(
        zarr_dandiset.dspath / "sample.zarr",
        tmp_path / zarr_dandiset.dandiset_id / "sample.zarr",
    )


def test_download_different_zarr_onto_excluded_dotfiles(
    tmp_path: Path, zarr_dandiset: SampleDandiset
) -> None:
    dd = tmp_path / zarr_dandiset.dandiset_id
    dd.mkdir()
    zarr_path = dd / "sample.zarr"
    zarr.save(zarr_path, np.eye(5))
    (zarr_path / ".git").touch()
    (zarr_path / ".dandi").mkdir()
    (zarr_path / ".dandi" / "somefile.txt").touch()
    (zarr_path / ".datalad").mkdir()
    (zarr_path / ".gitattributes").touch()
    (zarr_path / "arr_0").mkdir()
    (zarr_path / "arr_0" / ".gitmodules").touch()
    download(
        zarr_dandiset.dandiset.version_api_url,
        tmp_path,
        existing=DownloadExisting.OVERWRITE_DIFFERENT,
    )
    assert list_paths(zarr_path, dirs=True, exclude_vcs=False) == [
        zarr_path / ".dandi",
        zarr_path / ".dandi" / "somefile.txt",
        zarr_path / ".datalad",
        zarr_path / ".git",
        zarr_path / ".gitattributes",
        zarr_path / ".zgroup",
        zarr_path / "arr_0",
        zarr_path / "arr_0" / ".gitmodules",
        zarr_path / "arr_0" / ".zarray",
        zarr_path / "arr_0" / "0",
        zarr_path / "arr_1",
        zarr_path / "arr_1" / ".zarray",
        zarr_path / "arr_1" / "0",
    ]


def test_download_different_zarr_delete_dir(
    new_dandiset: SampleDandiset, tmp_path: Path
) -> None:
    d = new_dandiset.dandiset
    dspath = new_dandiset.dspath
    zarr.save(dspath / "sample.zarr", np.eye(5))
    assert not any(p.is_dir() for p in (dspath / "sample.zarr").iterdir())
    new_dandiset.upload()
    dd = tmp_path / d.identifier
    dd.mkdir(parents=True, exist_ok=True)
    zarr.save(dd / "sample.zarr", np.arange(1000), np.arange(1000, 0, -1))
    assert any(p.is_dir() for p in (dd / "sample.zarr").iterdir())
    download(d.version_api_url, tmp_path, existing=DownloadExisting.OVERWRITE_DIFFERENT)
    assert_dirtrees_eq(dspath / "sample.zarr", dd / "sample.zarr")


def test_download_zarr_to_nonzarr_path(
    tmp_path: Path, zarr_dandiset: SampleDandiset
) -> None:
    dd = tmp_path / zarr_dandiset.dandiset_id
    dd.mkdir()
    (dd / "sample.zarr").write_text("This is not a Zarr.\n")
    download(
        zarr_dandiset.dandiset.version_api_url,
        tmp_path,
        existing=DownloadExisting.OVERWRITE_DIFFERENT,
    )
    assert_dirtrees_eq(
        zarr_dandiset.dspath / "sample.zarr",
        tmp_path / zarr_dandiset.dandiset_id / "sample.zarr",
    )


def test_download_nonzarr_to_zarr_path(
    new_dandiset: SampleDandiset, tmp_path: Path
) -> None:
    d = new_dandiset.dandiset
    (new_dandiset.dspath / "sample.zarr").write_text("This is not a Zarr.\n")
    new_dandiset.upload(allow_any_path=True)
    dd = tmp_path / d.identifier
    dd.mkdir(parents=True, exist_ok=True)
    zarr.save(dd / "sample.zarr", np.arange(1000), np.arange(1000, 0, -1))
    download(d.version_api_url, tmp_path, existing=DownloadExisting.OVERWRITE_DIFFERENT)
    assert (dd / "sample.zarr").is_file()
    assert (dd / "sample.zarr").read_text() == "This is not a Zarr.\n"


def test_download_zarr_asset_id_only(
    zarr_dandiset: SampleDandiset, tmp_path: Path
) -> None:
    asset = zarr_dandiset.dandiset.get_asset_by_path("sample.zarr")
    download(asset.base_download_url, tmp_path)
    assert list(tmp_path.iterdir()) == [tmp_path / "sample.zarr"]
    assert_dirtrees_eq(zarr_dandiset.dspath / "sample.zarr", tmp_path / "sample.zarr")


def test_download_zarr_subdir_has_only_subdirs(
    tmp_path: Path, new_dandiset: SampleDandiset
) -> None:
    zf = new_dandiset.dspath / "sample.zarr"
    zf.mkdir()
    (zf / "dirs").mkdir()
    (zf / "dirs" / "apple").mkdir()
    (zf / "dirs" / "apple" / "file.txt").write_text("Apple\n")
    (zf / "dirs" / "banana").mkdir()
    (zf / "dirs" / "banana" / "file.txt").write_text("Banana\n")
    (zf / "dirs" / "coconut").mkdir()
    (zf / "dirs" / "coconut" / "file.txt").write_text("Coconut\n")
    new_dandiset.upload(validation="skip")
    download(new_dandiset.dandiset.version_api_url, tmp_path)
    assert_dirtrees_eq(zf, tmp_path / new_dandiset.dandiset_id / "sample.zarr")


@pytest.mark.parametrize(
    "file_qty,inputs,expected",
    [
        (
            1,
            [
                ("lonely.txt", {"size": 42}),
                ("lonely.txt", {"status": "downloading"}),
                ("lonely.txt", {"done": 0, "done%": 0.0}),
                ("lonely.txt", {"done": 20, "done%": 20 / 42 * 100}),
                ("lonely.txt", {"done": 40, "done%": 40 / 42 * 100}),
                ("lonely.txt", {"done": 42, "done%": 100.0}),
                ("lonely.txt", {"checksum": "ok"}),
                ("lonely.txt", {"status": "setting mtime"}),
                ("lonely.txt", {"status": "done"}),
            ],
            [
                {"size": 69105},
                {"status": "downloading"},
                {"done": 0, "done%": 0.0},
                {"done": 20, "done%": 20 / 42 * 100},
                {"done": 40, "done%": 40 / 42 * 100},
                {"done": 42, "done%": 100.0},
                {"status": "done", "message": "1 done"},
            ],
        ),
        (
            2,
            [
                ("apple.txt", {"size": 42}),
                ("banana.txt", {"size": 127}),
                ("apple.txt", {"status": "downloading"}),
                ("banana.txt", {"status": "downloading"}),
                ("apple.txt", {"done": 0, "done%": 0.0}),
                ("banana.txt", {"done": 0, "done%": 0.0}),
                ("apple.txt", {"done": 20, "done%": 20 / 42 * 100}),
                ("banana.txt", {"done": 40, "done%": 40 / 127 * 100}),
                ("apple.txt", {"done": 40, "done%": 40 / 42 * 100}),
                ("banana.txt", {"done": 80, "done%": 80 / 127 * 100}),
                ("apple.txt", {"done": 42, "done%": 100.0}),
                ("banana.txt", {"done": 120, "done%": 120 / 127 * 100}),
                ("apple.txt", {"checksum": "ok"}),
                ("banana.txt", {"done": 127, "done%": 100.0}),
                ("apple.txt", {"status": "setting mtime"}),
                ("banana.txt", {"checksum": "ok"}),
                ("apple.txt", {"status": "done"}),
                ("banana.txt", {"status": "setting mtime"}),
                ("banana.txt", {"status": "done"}),
            ],
            [
                {"size": 69105},
                {"status": "downloading"},
                {"done": 0, "done%": 0.0},
                {"done": 0, "done%": 0.0},
                {"done": 20, "done%": 20 / 169 * 100},
                {"done": 60, "done%": 60 / 169 * 100},
                {"done": 80, "done%": 80 / 169 * 100},
                {"done": 120, "done%": 120 / 169 * 100},
                {"done": 122, "done%": 122 / 169 * 100},
                {"done": 162, "done%": 162 / 169 * 100},
                {"done": 169, "done%": 100.0},
                {"message": "1 done"},
                {"status": "done", "message": "2 done"},
            ],
        ),
        (
            2,
            [
                ("apple.txt", {"size": 42}),
                ("apple.txt", {"status": "downloading"}),
                ("apple.txt", {"done": 0, "done%": 0.0}),
                ("apple.txt", {"done": 20, "done%": 20 / 42 * 100}),
                ("banana.txt", {"size": 127}),
                ("apple.txt", {"done": 40, "done%": 40 / 42 * 100}),
                ("banana.txt", {"status": "downloading"}),
                ("apple.txt", {"done": 42, "done%": 100.0}),
                ("banana.txt", {"done": 0, "done%": 0.0}),
                ("apple.txt", {"checksum": "ok"}),
                ("banana.txt", {"done": 40, "done%": 40 / 127 * 100}),
                ("apple.txt", {"status": "setting mtime"}),
                ("banana.txt", {"done": 80, "done%": 80 / 127 * 100}),
                ("apple.txt", {"status": "done"}),
                ("banana.txt", {"done": 120, "done%": 120 / 127 * 100}),
                ("banana.txt", {"done": 127, "done%": 100.0}),
                ("banana.txt", {"checksum": "ok"}),
                ("banana.txt", {"status": "setting mtime"}),
                ("banana.txt", {"status": "done"}),
            ],
            [
                {"size": 69105},
                {"status": "downloading"},
                {"done": 0, "done%": 0.0},
                {"done": 20, "done%": 20 / 42 * 100},
                {"done": 20, "done%": 20 / 169 * 100},
                {"done": 40, "done%": 40 / 169 * 100},
                {"done": 42, "done%": 42 / 169 * 100},
                {"done": 42, "done%": 42 / 169 * 100},
                {"done": 82, "done%": 82 / 169 * 100},
                {"done": 122, "done%": 122 / 169 * 100},
                {"message": "1 done"},
                {"done": 162, "done%": 162 / 169 * 100},
                {"done": 169, "done%": 169 / 169 * 100},
                {"status": "done", "message": "2 done"},
            ],
        ),
        (
            2,
            [
                ("apple.txt", {"size": 42}),
                ("apple.txt", {"status": "downloading"}),
                ("apple.txt", {"done": 0, "done%": 0.0}),
                ("apple.txt", {"done": 20, "done%": 20 / 42 * 100}),
                ("apple.txt", {"done": 40, "done%": 40 / 42 * 100}),
                ("apple.txt", {"done": 42, "done%": 100.0}),
                ("apple.txt", {"checksum": "ok"}),
                ("apple.txt", {"status": "setting mtime"}),
                ("apple.txt", {"status": "done"}),
                ("banana.txt", {"size": 127}),
                ("banana.txt", {"status": "downloading"}),
                ("banana.txt", {"done": 0, "done%": 0.0}),
                ("banana.txt", {"done": 40, "done%": 40 / 127 * 100}),
                ("banana.txt", {"done": 80, "done%": 80 / 127 * 100}),
                ("banana.txt", {"done": 120, "done%": 120 / 127 * 100}),
                ("banana.txt", {"done": 127, "done%": 100.0}),
                ("banana.txt", {"checksum": "ok"}),
                ("banana.txt", {"status": "setting mtime"}),
                ("banana.txt", {"status": "done"}),
            ],
            [
                {"size": 69105},
                {"status": "downloading"},
                {"done": 0, "done%": 0.0},
                {"done": 20, "done%": 20 / 42 * 100},
                {"done": 40, "done%": 40 / 42 * 100},
                {"done": 42, "done%": 42 / 42 * 100},
                {"message": "1 done"},
                {"done": 42, "done%": 42 / 169 * 100},
                {"done": 82, "done%": 82 / 169 * 100},
                {"done": 122, "done%": 122 / 169 * 100},
                {"done": 162, "done%": 162 / 169 * 100},
                {"done": 169, "done%": 100.0},
                {"status": "done", "message": "2 done"},
            ],
        ),
        (
            2,
            [
                ("apple.txt", {"size": 42}),
                ("banana.txt", {"size": 127}),
                ("apple.txt", {"status": "downloading"}),
                ("banana.txt", {"status": "downloading"}),
                ("apple.txt", {"done": 0, "done%": 0.0}),
                ("banana.txt", {"done": 0, "done%": 0.0}),
                ("apple.txt", {"done": 20, "done%": 20 / 42 * 100}),
                ("banana.txt", {"done": 40, "done%": 40 / 127 * 100}),
                ("apple.txt", {"done": 40, "done%": 40 / 42 * 100}),
                ("banana.txt", {"status": "error", "message": "Internet broke"}),
                ("apple.txt", {"done": 42, "done%": 100.0}),
                ("apple.txt", {"checksum": "ok"}),
                ("apple.txt", {"status": "setting mtime"}),
                ("apple.txt", {"status": "done"}),
            ],
            [
                {"size": 69105},
                {"status": "downloading"},
                {"done": 0, "done%": 0.0},
                {"done": 0, "done%": 0.0},
                {"done": 20, "done%": 20 / 169 * 100},
                {"done": 60, "done%": 60 / 169 * 100},
                {"done": 80, "done%": 80 / 169 * 100},
                {"message": "1 errored"},
                {"done": 40, "done%": 40 / 42 * 100},
                {"done": 42, "done%": 100.0},
                {"status": "error", "message": "1 done, 1 errored"},
            ],
        ),
        (
            1,
            [("lonely.txt", {"status": "skipped", "message": "already exists"})],
            [{"status": "skipped", "message": "1 skipped"}],
        ),
        (
            2,
            [
                ("apple.txt", {"size": 42}),
                ("banana.txt", {"status": "skipped", "message": "already exists"}),
                ("apple.txt", {"status": "downloading"}),
                ("apple.txt", {"done": 0, "done%": 0.0}),
                ("apple.txt", {"done": 20, "done%": 20 / 42 * 100}),
                ("apple.txt", {"done": 40, "done%": 40 / 42 * 100}),
                ("apple.txt", {"done": 42, "done%": 100.0}),
                ("apple.txt", {"checksum": "ok"}),
                ("apple.txt", {"status": "setting mtime"}),
                ("apple.txt", {"status": "done"}),
            ],
            [
                {"size": 69105},
                {"message": "1 skipped"},
                {"status": "downloading"},
                {"done": 0, "done%": 0.0},
                {"done": 20, "done%": 20 / 42 * 100},
                {"done": 40, "done%": 40 / 42 * 100},
                {"done": 42, "done%": 100.0},
                {"status": "done", "message": "1 done, 1 skipped"},
            ],
        ),
        (
            2,
            [
                ("apple.txt", {"size": 42}),
                ("banana.txt", {"size": 127}),
                ("apple.txt", {"status": "downloading"}),
                ("banana.txt", {"status": "downloading"}),
                ("apple.txt", {"done": 0, "done%": 0.0}),
                ("banana.txt", {"done": 0, "done%": 0.0}),
                ("apple.txt", {"done": 20, "done%": 20 / 42 * 100}),
                ("banana.txt", {"done": 40, "done%": 40 / 127 * 100}),
                ("apple.txt", {"done": 40, "done%": 40 / 42 * 100}),
                ("banana.txt", {"done": 80, "done%": 80 / 127 * 100}),
                ("apple.txt", {"done": 42, "done%": 100.0}),
                ("banana.txt", {"done": 120, "done%": 120 / 127 * 100}),
                ("apple.txt", {"checksum": "ok"}),
                ("banana.txt", {"done": 127, "done%": 100.0}),
                ("apple.txt", {"status": "setting mtime"}),
                (
                    "banana.txt",
                    {
                        "checksum": "differs",
                        "status": "error",
                        "message": "Checksum differs",
                    },
                ),
                ("apple.txt", {"status": "done"}),
            ],
            [
                {"size": 69105},
                {"status": "downloading"},
                {"done": 0, "done%": 0.0},
                {"done": 0, "done%": 0.0},
                {"done": 20, "done%": 20 / 169 * 100},
                {"done": 60, "done%": 60 / 169 * 100},
                {"done": 80, "done%": 80 / 169 * 100},
                {"done": 120, "done%": 120 / 169 * 100},
                {"done": 122, "done%": 122 / 169 * 100},
                {"done": 162, "done%": 162 / 169 * 100},
                {"done": 169, "done%": 100.0},
                {"message": "1 errored"},
                {"status": "error", "message": "1 done, 1 errored"},
            ],
        ),
        (
            3,
            [
                ("apple.txt", {"size": 42}),
                ("banana.txt", {"size": 127}),
                ("apple.txt", {"status": "downloading"}),
                ("banana.txt", {"status": "downloading"}),
                ("coconut", {"status": "skipped", "message": "already exists"}),
                ("apple.txt", {"done": 0, "done%": 0.0}),
                ("banana.txt", {"done": 0, "done%": 0.0}),
                ("apple.txt", {"done": 20, "done%": 20 / 42 * 100}),
                ("banana.txt", {"done": 40, "done%": 40 / 127 * 100}),
                ("apple.txt", {"done": 40, "done%": 40 / 42 * 100}),
                ("banana.txt", {"done": 80, "done%": 80 / 127 * 100}),
                ("apple.txt", {"done": 42, "done%": 100.0}),
                (
                    "apple.txt",
                    {
                        "checksum": "differs",
                        "status": "error",
                        "message": "Checksum differs",
                    },
                ),
                ("banana.txt", {"done": 120, "done%": 120 / 127 * 100}),
                ("banana.txt", {"done": 127, "done%": 100.0}),
                ("banana.txt", {"checksum": "ok"}),
                ("banana.txt", {"status": "setting mtime"}),
                ("banana.txt", {"status": "done"}),
            ],
            [
                {"size": 69105},
                {"status": "downloading"},
                {"message": "1 skipped"},
                {"done": 0, "done%": 0.0},
                {"done": 0, "done%": 0.0},
                {"done": 20, "done%": 20 / 169 * 100},
                {"done": 60, "done%": 60 / 169 * 100},
                {"done": 80, "done%": 80 / 169 * 100},
                {"done": 120, "done%": 120 / 169 * 100},
                {"done": 122, "done%": 122 / 169 * 100},
                {"message": "1 errored, 1 skipped"},
                {"done": 162, "done%": 162 / 169 * 100},
                {"done": 169, "done%": 100.0},
                {"status": "error", "message": "1 done, 1 errored, 1 skipped"},
            ],
        ),
    ],
)
def test_progress_combiner(
    file_qty: int, inputs: list[tuple[str, dict]], expected: list[dict]
) -> None:
    pc = ProgressCombiner(zarr_size=69105, file_qty=file_qty)
    outputs: list[dict] = []
    for path, status in inputs:
        outputs.extend(pc.feed(path, status))
    assert outputs == expected


def test_download_multiple_urls(
    text_dandiset: SampleDandiset,
    tmp_path: Path,
    sample_dandiset_factory: SampleDandisetFactory,
) -> None:
    # We can't request both `text_dandiset` and `zarr_dandiset`, as those will
    # end up using the same `new_dandiset`.  Hence, we need to fall back to
    # using `sample_dandiset_factory` here.
    zarr_dandiset = sample_dandiset_factory.mkdandiset("Sample Zarr Dandiset")
    zarr.save(
        zarr_dandiset.dspath / "sample.zarr", np.arange(1000), np.arange(1000, 0, -1)
    )
    zarr_dandiset.upload()

    download([text_dandiset.dandiset.api_url, zarr_dandiset.dandiset.api_url], tmp_path)
    assert list_paths(tmp_path) == [
        tmp_path / text_dandiset.dandiset_id / "dandiset.yaml",
        tmp_path / text_dandiset.dandiset_id / "file.txt",
        tmp_path / text_dandiset.dandiset_id / "subdir1" / "apple.txt",
        tmp_path / text_dandiset.dandiset_id / "subdir2" / "banana.txt",
        tmp_path / text_dandiset.dandiset_id / "subdir2" / "coconut.txt",
        tmp_path / zarr_dandiset.dandiset_id / "dandiset.yaml",
        tmp_path
        / zarr_dandiset.dandiset_id
        / tmp_path
        / zarr_dandiset.dandiset_id
        / "sample.zarr"
        / ".zgroup",
        tmp_path / zarr_dandiset.dandiset_id / "sample.zarr" / "arr_0" / ".zarray",
        tmp_path / zarr_dandiset.dandiset_id / "sample.zarr" / "arr_0" / "0",
        tmp_path / zarr_dandiset.dandiset_id / "sample.zarr" / "arr_1" / ".zarray",
        tmp_path / zarr_dandiset.dandiset_id / "sample.zarr" / "arr_1" / "0",
    ]


def test_download_glob_option(text_dandiset: SampleDandiset, tmp_path: Path) -> None:
    dandiset_id = text_dandiset.dandiset_id
    download(
        f"dandi://{text_dandiset.api.instance_id}/{dandiset_id}/s*.Txt",
        tmp_path,
        path_type=PathType.GLOB,
    )
    assert list_paths(tmp_path, dirs=True) == [
        tmp_path / "subdir1",
        tmp_path / "subdir1" / "apple.txt",
        tmp_path / "subdir2",
        tmp_path / "subdir2" / "banana.txt",
        tmp_path / "subdir2" / "coconut.txt",
    ]
    assert (tmp_path / "subdir1" / "apple.txt").read_text() == "Apple\n"
    assert (tmp_path / "subdir2" / "banana.txt").read_text() == "Banana\n"
    assert (tmp_path / "subdir2" / "coconut.txt").read_text() == "Coconut\n"


def test_download_glob_url(text_dandiset: SampleDandiset, tmp_path: Path) -> None:
    download(f"{text_dandiset.dandiset.version_api_url}assets/?glob=s*.Txt", tmp_path)
    assert list_paths(tmp_path, dirs=True) == [
        tmp_path / "subdir1",
        tmp_path / "subdir1" / "apple.txt",
        tmp_path / "subdir2",
        tmp_path / "subdir2" / "banana.txt",
        tmp_path / "subdir2" / "coconut.txt",
    ]
    assert (tmp_path / "subdir1" / "apple.txt").read_text() == "Apple\n"
    assert (tmp_path / "subdir2" / "banana.txt").read_text() == "Banana\n"
    assert (tmp_path / "subdir2" / "coconut.txt").read_text() == "Coconut\n"


def test_download_sync_glob(
    mocker: MockerFixture, text_dandiset: SampleDandiset
) -> None:
    text_dandiset.dandiset.get_asset_by_path("file.txt").delete()
    text_dandiset.dandiset.get_asset_by_path("subdir2/banana.txt").delete()
    confirm_mock = mocker.patch("dandi.download.abbrev_prompt", return_value="yes")
    download(
        f"{text_dandiset.dandiset.version_api_url}assets/?glob=s*.Txt",
        text_dandiset.dspath,
        existing=DownloadExisting.OVERWRITE,
        sync=True,
    )
    confirm_mock.assert_called_with("Delete 1 local asset?", "yes", "no", "list")
    assert (text_dandiset.dspath / "file.txt").exists()
    assert not (text_dandiset.dspath / "subdir2" / "banana.txt").exists()


@pytest.mark.parametrize(
    "url",
    [
        "dandi://{instance_id}/{dandiset_id}/does/not/exist/",
        "{api_url}/dandisets/{dandiset_id}/versions/draft/assets/?path=does/not/exist",
        "{api_url}/dandisets/{dandiset_id}/versions/draft/assets/?glob=d*/*/*st",
    ],
)
def test_download_nonexistent_multiasset(
    text_dandiset: SampleDandiset, tmp_path: Path, url: str
) -> None:
    with pytest.raises(NotFoundError):
        download(
            url.format(
                instance_id=text_dandiset.api.instance_id,
                api_url=text_dandiset.dandiset.api_url,
                dandiset_id=text_dandiset.dandiset_id,
            ),
            tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


def test_download_empty_dandiset(new_dandiset: SampleDandiset, tmp_path: Path) -> None:
    download(new_dandiset.dandiset.api_url, tmp_path)
    assert list_paths(tmp_path, dirs=True) == [
        tmp_path / new_dandiset.dandiset_id,
        tmp_path / new_dandiset.dandiset_id / "dandiset.yaml",
    ]


def test_download_empty_dandiset_and_nonexistent_multiasset(
    sample_dandiset_factory: SampleDandisetFactory,
    text_dandiset: SampleDandiset,
    tmp_path: Path,
) -> None:
    empty_dandiset = sample_dandiset_factory.mkdandiset("Empty Dandiset")
    with pytest.raises(NotFoundError):
        download(
            [
                empty_dandiset.dandiset.api_url,
                (
                    f"dandi://{text_dandiset.api.instance_id}"
                    f"/{text_dandiset.dandiset_id}/does/not/exist/"
                ),
            ],
            tmp_path,
        )
    assert list_paths(tmp_path, dirs=True) == [
        tmp_path / empty_dandiset.dandiset_id,
        tmp_path / empty_dandiset.dandiset_id / "dandiset.yaml",
    ]


def test_pyouthelper_time_remaining_1339():
    """
    Ensure that time remaining goes down!
    https://github.com/dandi/dandi-cli/issues/1339

    Since time.now() is called inside the agg methods, we
    simulate time elapsing by changing t0

    Assume downloading files totaling 100 arbitrary units at rates to trigger
    a few hours, then countdown to 0.
    check that ETA goes down like we want it to
    """

    helper = PYOUTHelper()
    helper.items_summary.size = 100

    # first check hours
    # 5 hours remaining = 50% done in 60*60*5
    helper.items_summary.t0 = time.time() - (60 * 60 * 5)
    done = helper.agg_done(iter([50]))
    assert done[-1] == "ETA: 5 hours<"

    # 5 minutes remaining = 50% done in 60 * 5
    helper.items_summary.t0 = time.time() - (5 * 60)
    done = helper.agg_done(iter([50]))
    assert done[-1] == "ETA: 5 minutes<"

    # countdown the last 10 seconds!
    for i in range(11):
        helper.items_summary.t0 = time.time() - (100 - (10 - i))
        done = helper.agg_done(iter([100 - (10 - i)]))
        if i == 9:
            assert done[-1] == "ETA: a second<"
        elif i == 10:
            # once done, dont print ETA
            assert len(done) == 2
        else:
            assert done[-1] == f"ETA: {10-i} seconds<"
