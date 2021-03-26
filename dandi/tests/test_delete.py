from pathlib import Path

import pytest

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
    ],
)
def test_delete_paths(
    local_dandi_api, monkeypatch, text_dandiset, tmp_path, paths, remainder
):
    monkeypatch.chdir(text_dandiset["dspath"])
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    dandiset_id = text_dandiset["dandiset_id"]
    delete(
        [
            p.format(instance=local_dandi_api["instance_id"], dandiset_id=dandiset_id)
            for p in paths
        ],
        dandi_instance=local_dandi_api["instance_id"],
        devel_debug=True,
        force=True,
    )
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/draft",
        tmp_path,
    )
    files = sorted(map(Path, find_files(r".*", paths=[tmp_path])))
    assert files == [tmp_path / dandiset_id / f for f in ["dandiset.yaml"] + remainder]
