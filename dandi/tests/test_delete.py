from pathlib import Path

import pytest
import requests

from ..consts import dandiset_metadata_file
from ..dandiapi import RESTFullAPIClient
from ..delete import delete
from ..download import download
from ..exceptions import NotFoundError
from ..utils import find_files


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
    local_dandi_api, mocker, monkeypatch, text_dandiset, tmp_path, paths, remainder
):
    monkeypatch.chdir(text_dandiset["dspath"])
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    instance = local_dandi_api["instance_id"]
    dandiset_id = text_dandiset["dandiset_id"]
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    delete(
        [p.format(instance=instance, dandiset_id=dandiset_id) for p in paths],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
    )
    delete_spy.assert_called()
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/draft",
        tmp_path,
    )
    files = sorted(map(Path, find_files(r".*", paths=[tmp_path])))
    assert files == [tmp_path / dandiset_id / f for f in ["dandiset.yaml"] + remainder]


@pytest.mark.parametrize("confirm", [True, False])
def test_delete_path_confirm(
    confirm, local_dandi_api, mocker, monkeypatch, text_dandiset
):
    monkeypatch.chdir(text_dandiset["dspath"])
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    instance = local_dandi_api["instance_id"]
    dandiset_id = text_dandiset["dandiset_id"]
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


def test_delete_path_pyout(local_dandi_api, mocker, monkeypatch, text_dandiset):
    monkeypatch.chdir(text_dandiset["dspath"])
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    instance = local_dandi_api["instance_id"]
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
def test_delete_dandiset(local_dandi_api, mocker, monkeypatch, text_dandiset, paths):
    monkeypatch.chdir(text_dandiset["dspath"])
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    instance = local_dandi_api["instance_id"]
    dandiset_id = text_dandiset["dandiset_id"]
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    delete(
        [p.format(instance=instance, dandiset_id=dandiset_id) for p in paths],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
    )
    delete_spy.assert_called()
    with pytest.raises(requests.HTTPError) as excinfo:
        local_dandi_api["client"].get_dandiset(dandiset_id, "draft")
    assert excinfo.value.response.status_code == 404


@pytest.mark.parametrize("confirm", [True, False])
def test_delete_dandiset_confirm(
    confirm, local_dandi_api, mocker, monkeypatch, text_dandiset
):
    monkeypatch.chdir(text_dandiset["dspath"])
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    instance = local_dandi_api["instance_id"]
    dandiset_id = text_dandiset["dandiset_id"]
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


def test_delete_dandiset_mismatch(local_dandi_api, mocker, monkeypatch, text_dandiset):
    monkeypatch.chdir(text_dandiset["dspath"])
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    instance = local_dandi_api["instance_id"]
    dandiset_id = text_dandiset["dandiset_id"]
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


def test_delete_instance_mismatch(local_dandi_api, mocker, monkeypatch, text_dandiset):
    monkeypatch.chdir(text_dandiset["dspath"])
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    instance = local_dandi_api["instance_id"]
    dandiset_id = text_dandiset["dandiset_id"]
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    for paths in [
        [
            "subdir1/apple.txt",
            f"dandi://dandi-api/{dandiset_id}/subdir2/coconut.txt",
        ],
        [
            f"dandi://{instance}/{dandiset_id}/subdir2/coconut.txt",
            f"dandi://dandi-api/{dandiset_id}/subdir1/apple.txt",
        ],
    ]:
        with pytest.raises(ValueError) as excinfo:
            delete(paths, dandi_instance=instance, devel_debug=True, force=True)
        assert (
            str(excinfo.value)
            == "Cannot delete assets from multiple API instances at once"
        )
        delete_spy.assert_not_called()


def test_delete_nonexistent_dandiset(local_dandi_api, mocker, monkeypatch):
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    instance = local_dandi_api["instance_id"]
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    with pytest.raises(NotFoundError) as excinfo:
        delete(
            [f"dandi://{instance}/999999/subdir1/apple.txt"],
            dandi_instance=instance,
            devel_debug=True,
            force=True,
        )
    assert str(excinfo.value) == "Dandiset 999999 not found on server"
    delete_spy.assert_not_called()


def test_delete_nonexistent_asset(local_dandi_api, mocker, monkeypatch, text_dandiset):
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    instance = local_dandi_api["instance_id"]
    dandiset_id = text_dandiset["dandiset_id"]
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
        == f"Asset at path 'subdir3/mango.txt' not found in Dandiset {dandiset_id}"
    )
    delete_spy.assert_not_called()


def test_delete_nonexistent_asset_folder(
    local_dandi_api, mocker, monkeypatch, text_dandiset
):
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    instance = local_dandi_api["instance_id"]
    dandiset_id = text_dandiset["dandiset_id"]
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
        == f"No assets under path 'subdir3/' found in Dandiset {dandiset_id}"
    )
    delete_spy.assert_not_called()


def test_delete_version(local_dandi_api, mocker, monkeypatch):
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    instance = local_dandi_api["instance_id"]
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


def test_delete_no_dandiset(mocker, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    with pytest.raises(RuntimeError) as excinfo:
        delete(
            ["dir/file.txt"],
            dandi_instance="dandi-api",
            devel_debug=True,
            force=True,
        )
    assert str(excinfo.value) == (
        f"Found no {dandiset_metadata_file} anywhere.  "
        "Use 'dandi register', 'download', or 'organize' first"
    )
    delete_spy.assert_not_called()
