from pathlib import Path

import pytest
import requests

from ..delete import delete
from ..download import download
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
    local_dandi_api, monkeypatch, text_dandiset, tmp_path, paths, remainder
):
    monkeypatch.chdir(text_dandiset["dspath"])
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    instance = local_dandi_api["instance_id"]
    dandiset_id = text_dandiset["dandiset_id"]
    delete(
        [p.format(instance=instance, dandiset_id=dandiset_id) for p in paths],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
    )
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/draft",
        tmp_path,
    )
    files = sorted(map(Path, find_files(r".*", paths=[tmp_path])))
    assert files == [tmp_path / dandiset_id / f for f in ["dandiset.yaml"] + remainder]


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
def test_delete_dandiset(local_dandi_api, monkeypatch, text_dandiset, paths):
    monkeypatch.chdir(text_dandiset["dspath"])
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    instance = local_dandi_api["instance_id"]
    dandiset_id = text_dandiset["dandiset_id"]
    delete(
        [p.format(instance=instance, dandiset_id=dandiset_id) for p in paths],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
    )
    with pytest.raises(requests.HTTPError) as excinfo:
        local_dandi_api["client"].get_dandiset(dandiset_id, "draft")
    assert excinfo.value.response.status_code == 404
