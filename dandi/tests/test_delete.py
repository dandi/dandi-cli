from pathlib import Path
from typing import List

import pytest
from pytest_mock import MockerFixture

from .fixtures import DandiAPI, SampleDandiset
from ..consts import DRAFT, dandiset_metadata_file
from ..dandiapi import RESTFullAPIClient
from ..delete import delete
from ..download import download
from ..exceptions import NotFoundError
from ..utils import list_paths


@pytest.mark.parametrize(
    "paths,remainder",
    [
        (
            ["subdir2/coconut.txt"],
            [
                Path("file.txt"),
                Path("subdir1", "apple.txt"),
                Path("subdir2", "banana.txt"),
            ],
        ),
        (["subdir2"], [Path("file.txt"), Path("subdir1", "apple.txt")]),
        (
            ["subdir2", "subdir2/coconut.txt"],
            [Path("file.txt"), Path("subdir1", "apple.txt")],
        ),
        (
            ["dandi://{instance}/{dandiset_id}/subdir2/coconut.txt"],
            [
                Path("file.txt"),
                Path("subdir1", "apple.txt"),
                Path("subdir2", "banana.txt"),
            ],
        ),
        (
            ["dandi://{instance}/{dandiset_id}/subdir2/"],
            [Path("file.txt"), Path("subdir1", "apple.txt")],
        ),
        (
            [
                "dandi://{instance}/{dandiset_id}/subdir2/",
                "dandi://{instance}/{dandiset_id}/subdir2/coconut.txt",
            ],
            [Path("file.txt"), Path("subdir1", "apple.txt")],
        ),
        (
            [
                "subdir1",
                "dandi://{instance}/{dandiset_id}/subdir2/coconut.txt",
            ],
            [Path("file.txt"), Path("subdir2", "banana.txt")],
        ),
    ],
)
def test_delete_paths(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
    tmp_path: Path,
    paths: List[str],
    remainder: List[Path],
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", text_dandiset.api.api_key)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    delete(
        [p.format(instance=instance, dandiset_id=dandiset_id) for p in paths],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
    )
    delete_spy.assert_called()
    download(text_dandiset.dandiset.version_api_url, tmp_path)
    assert list_paths(tmp_path) == [
        tmp_path / dandiset_id / f for f in [Path("dandiset.yaml")] + remainder
    ]


@pytest.mark.parametrize("confirm", [True, False])
def test_delete_path_confirm(
    confirm: bool,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", text_dandiset.api.api_key)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    confirm_mock = mocker.patch("click.confirm", return_value=confirm)
    delete(["subdir2/coconut.txt"], dandi_instance=instance, devel_debug=True)
    confirm_mock.assert_called_with(
        f"Delete 1 assets on server from Dandiset {dandiset_id}?"
    )
    if confirm:
        delete_spy.assert_called()
    else:
        delete_spy.assert_not_called()


def test_delete_path_pyout(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", text_dandiset.api.api_key)
    instance = text_dandiset.api.instance_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    delete(["subdir2/coconut.txt"], dandi_instance=instance, force=True)
    delete_spy.assert_called()


@pytest.mark.parametrize(
    "paths",
    [
        ["dandi://{instance}/{dandiset_id}"],
        ["dandi://{instance}/{dandiset_id}", "file.txt"],
        ["file.txt", "dandi://{instance}/{dandiset_id}"],
        [
            "dandi://{instance}/{dandiset_id}",
            "dandi://{instance}/{dandiset_id}/subdir2/coconut.txt",
        ],
        [
            "dandi://{instance}/{dandiset_id}/subdir2/coconut.txt",
            "dandi://{instance}/{dandiset_id}",
        ],
    ],
)
def test_delete_dandiset(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
    paths: List[str],
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", text_dandiset.api.api_key)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    delete(
        [p.format(instance=instance, dandiset_id=dandiset_id) for p in paths],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
    )
    delete_spy.assert_called()
    with pytest.raises(NotFoundError):
        text_dandiset.client.get_dandiset(dandiset_id, DRAFT, lazy=False)


@pytest.mark.parametrize("confirm", [True, False])
def test_delete_dandiset_confirm(
    confirm: bool,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", text_dandiset.api.api_key)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    confirm_mock = mocker.patch("click.confirm", return_value=confirm)
    delete(
        [f"dandi://{instance}/{dandiset_id}"], dandi_instance=instance, devel_debug=True
    )
    confirm_mock.assert_called_with(f"Delete Dandiset {dandiset_id}?")
    if confirm:
        delete_spy.assert_called()
    else:
        delete_spy.assert_not_called()


def test_delete_dandiset_mismatch(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", text_dandiset.api.api_key)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    not_dandiset = str(int(dandiset_id) - 1).zfill(6)
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    for paths in [
        [
            "subdir1/apple.txt",
            f"dandi://{instance}/{not_dandiset}/subdir2/coconut.txt",
        ],
        [
            f"dandi://{instance}/{dandiset_id}/subdir1/apple.txt",
            f"dandi://{instance}/{not_dandiset}/subdir2/coconut.txt",
        ],
    ]:
        with pytest.raises(ValueError) as excinfo:
            delete(paths, dandi_instance=instance, devel_debug=True, force=True)
        assert (
            str(excinfo.value) == "Cannot delete assets from multiple Dandisets at once"
        )
        delete_spy.assert_not_called()


def test_delete_instance_mismatch(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", text_dandiset.api.api_key)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    for paths in [
        [
            "subdir1/apple.txt",
            f"dandi://dandi/{dandiset_id}/subdir2/coconut.txt",
        ],
        [
            f"dandi://{instance}/{dandiset_id}/subdir2/coconut.txt",
            f"dandi://dandi/{dandiset_id}/subdir1/apple.txt",
        ],
    ]:
        with pytest.raises(ValueError) as excinfo:
            delete(paths, dandi_instance=instance, devel_debug=True, force=True)
        assert (
            str(excinfo.value)
            == "Cannot delete assets from multiple API instances at once"
        )
        delete_spy.assert_not_called()


def test_delete_nonexistent_dandiset(
    local_dandi_api: DandiAPI, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api.api_key)
    instance = local_dandi_api.instance_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    with pytest.raises(NotFoundError) as excinfo:
        delete(
            [f"dandi://{instance}/999999/subdir1/apple.txt"],
            dandi_instance=instance,
            devel_debug=True,
            force=True,
        )
    assert str(excinfo.value) == "No such Dandiset: '999999'"
    delete_spy.assert_not_called()


def test_delete_nonexistent_dandiset_skip_missing(
    local_dandi_api: DandiAPI, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api.api_key)
    instance = local_dandi_api.instance_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    delete(
        [f"dandi://{instance}/999999/subdir1/apple.txt"],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
        skip_missing=True,
    )
    delete_spy.assert_not_called()


def test_delete_nonexistent_asset(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.setenv("DANDI_API_KEY", text_dandiset.api.api_key)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    with pytest.raises(NotFoundError) as excinfo:
        delete(
            [
                f"dandi://{instance}/{dandiset_id}/file.txt",
                f"dandi://{instance}/{dandiset_id}/subdir3/mango.txt",
            ],
            dandi_instance=instance,
            devel_debug=True,
            force=True,
        )
    assert (
        str(excinfo.value)
        == f"No assets found for dandi://{instance}/{dandiset_id}/subdir3/mango.txt"
    )
    delete_spy.assert_not_called()


def test_delete_nonexistent_asset_skip_missing(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DANDI_API_KEY", text_dandiset.api.api_key)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    delete(
        [
            f"dandi://{instance}/{dandiset_id}/file.txt",
            f"dandi://{instance}/{dandiset_id}/subdir3/mango.txt",
        ],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
        skip_missing=True,
    )
    delete_spy.assert_called()
    download(text_dandiset.dandiset.version_api_url, tmp_path)
    assert list_paths(tmp_path) == [
        tmp_path / dandiset_id / "dandiset.yaml",
        tmp_path / dandiset_id / "subdir1" / "apple.txt",
        tmp_path / dandiset_id / "subdir2" / "banana.txt",
        tmp_path / dandiset_id / "subdir2" / "coconut.txt",
    ]


def test_delete_nonexistent_asset_folder(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.setenv("DANDI_API_KEY", text_dandiset.api.api_key)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    with pytest.raises(NotFoundError) as excinfo:
        delete(
            [
                f"dandi://{instance}/{dandiset_id}/subdir1/",
                f"dandi://{instance}/{dandiset_id}/subdir3/",
            ],
            dandi_instance=instance,
            devel_debug=True,
            force=True,
        )
    assert (
        str(excinfo.value)
        == f"No assets found for dandi://{instance}/{dandiset_id}/subdir3/"
    )
    delete_spy.assert_not_called()


def test_delete_nonexistent_asset_folder_skip_missing(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DANDI_API_KEY", text_dandiset.api.api_key)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    delete(
        [
            f"dandi://{instance}/{dandiset_id}/subdir1/",
            f"dandi://{instance}/{dandiset_id}/subdir3/",
        ],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
        skip_missing=True,
    )
    delete_spy.assert_called()
    download(text_dandiset.dandiset.version_api_url, tmp_path)
    assert list_paths(tmp_path) == [
        tmp_path / dandiset_id / "dandiset.yaml",
        tmp_path / dandiset_id / "file.txt",
        tmp_path / dandiset_id / "subdir2" / "banana.txt",
        tmp_path / dandiset_id / "subdir2" / "coconut.txt",
    ]


def test_delete_version(
    local_dandi_api: DandiAPI, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api.api_key)
    instance = local_dandi_api.instance_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    with pytest.raises(NotImplementedError) as excinfo:
        delete(
            [f"dandi://{instance}/999999@draft"],
            dandi_instance=instance,
            devel_debug=True,
            force=True,
        )
    assert str(excinfo.value) == (
        "Dandi API server does not support deletion of individual versions of a"
        " dandiset"
    )
    delete_spy.assert_not_called()


def test_delete_no_dandiset(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    with pytest.raises(RuntimeError) as excinfo:
        delete(
            ["dir/file.txt"],
            dandi_instance="dandi",
            devel_debug=True,
            force=True,
        )
    assert str(excinfo.value) == (
        f"Found no {dandiset_metadata_file} anywhere.  "
        "Use 'dandi download' or 'organize' first"
    )
    delete_spy.assert_not_called()


def test_delete_zarr_path(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    zarr_dandiset: SampleDandiset,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(zarr_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", zarr_dandiset.api.api_key)
    instance = zarr_dandiset.api.instance_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    delete(["sample.zarr"], dandi_instance=instance, devel_debug=True, force=True)
    delete_spy.assert_called()
    download(zarr_dandiset.dandiset.version_api_url, tmp_path)
    assert list_paths(tmp_path) == [
        tmp_path / zarr_dandiset.dandiset_id / "dandiset.yaml"
    ]
