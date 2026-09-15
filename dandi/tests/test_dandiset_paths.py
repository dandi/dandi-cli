from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest
import responses

from .fixtures import SampleDandiset
from .test_files import mkpaths
from ..consts import DandiInstance
from ..dandiapi import DandiAPIClient, RemoteDandiset
from ..dandiset import Dandiset
from ..exceptions import NotFoundError


@pytest.mark.ai_generated
def test_local_path_tree(tmp_path: Path) -> None:
    mkpaths(
        tmp_path,
        "dandiset.yaml",
        "file.txt",
        "sub-01/a.nwb",
        "sub-01/b.nwb",
        "record.zarr/chunk",
        ".hidden/a.txt",
        "empty/",
    )
    (tmp_path / "file.txt").write_bytes(b"123")
    root = Dandiset(tmp_path).get_path()
    assert root.exists() and root.is_dir() and not root.is_file()
    assert [p.name for p in root.iterdir()] == ["file.txt", "record.zarr", "sub-01"]
    assert root.aggregate_files == 4
    assert root.size == 3
    assert root.parent == root
    assert root / "." == root
    assert (root / "sub-01/..") == root
    assert (root / "sub-01").aggregate_files == 2
    assert [str(p) for p in (root / "sub-01").iterdir()] == [
        "sub-01/a.nwb",
        "sub-01/b.nwb",
    ]
    assert (root / "file.txt").get_asset().path == "file.txt"
    assert (root / "record.zarr").is_file()
    assert not (root / "record.zarr/chunk").exists()
    assert not (root / ".hidden").exists()
    assert not (root / "empty").exists()
    with pytest.raises(NotADirectoryError):
        list((root / "record.zarr").iterdir())
    with pytest.raises(IsADirectoryError):
        root.get_asset()
    missing = root / "missing"
    assert not missing.exists() and not missing.is_file() and not missing.is_dir()
    for operation in (
        lambda: list(missing.iterdir()),
        lambda: missing.size,
        lambda: missing.aggregate_files,
        missing.get_asset,
    ):
        with pytest.raises(NotFoundError):
            operation()
    with pytest.raises(ValueError, match="Absolute"):
        root.joinpath("/etc")
    with pytest.raises(ValueError):
        root._get_subpath("")
    with pytest.raises(ValueError):
        root._get_subpath("a/b")


@pytest.mark.ai_generated
def test_local_empty_and_snapshot(tmp_path: Path) -> None:
    mkpaths(tmp_path, "dandiset.yaml")
    ds = Dandiset(tmp_path)
    root = ds.get_path()
    assert list(root.iterdir()) == []
    assert root.aggregate_files == root.size == 0
    mkpaths(tmp_path, "new.txt")
    assert not (root / "new.txt").exists()
    assert ds.get_path("new.txt").exists()


@pytest.mark.ai_generated
def test_local_symlink_directory(tmp_path: Path) -> None:
    mkpaths(tmp_path, "dandiset.yaml", "target/a.txt")
    try:
        (tmp_path / "linked").symlink_to(tmp_path / "target", target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Cannot create directory symlink: {exc}")
    assert not Dandiset(tmp_path).get_path("linked").exists()


def _entry(path: str, count: int, size: int, asset: Any = None) -> dict:
    return {
        "path": path,
        "aggregate_files": count,
        "aggregate_size": size,
        "asset": asset,
    }


def _query_matcher(expected: dict[str, str]):
    """Match the raw query so empty values work with all supported responses versions."""

    def match(request: Any) -> tuple[bool, str]:
        actual = dict(parse_qsl(urlsplit(request.url).query, keep_blank_values=True))
        valid = actual == expected
        return valid, f"Query parameters do not match: {actual!r} != {expected!r}"

    return match


@pytest.mark.ai_generated
@responses.activate
def test_remote_listing_pagination_and_cached_children(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://example.test/api/dandisets/000001/versions/draft/assets/paths/"
    first = _entry(
        "file.txt", 1, 5, {"asset_id": "test-id", "url": "https://example.test/blob"}
    )
    directory = _entry("sub-01", 2, 9)
    responses.get(
        url,
        json={"count": 2, "results": [first], "next": url + "?path_prefix=&page=2"},
        match=[_query_matcher({"path_prefix": ""})],
    )
    responses.get(
        url,
        json={"count": 2, "results": [directory], "next": None},
        match=[_query_matcher({"path_prefix": "", "page": "2"})],
    )
    responses.get(
        url,
        json={
            "count": 1,
            "results": [_entry("sub-01/a.nwb", 1, 9, {"asset_id": "other"})],
            "next": None,
        },
        match=[_query_matcher({"path_prefix": "sub-01"})],
    )
    monkeypatch.setenv("DANDI_PAGINATION_DISABLE_FALLBACK", "1")
    with DandiAPIClient(
        dandi_instance=DandiInstance(
            name="test", gui="https://example.test", api="https://example.test/api/"
        )
    ) as client:
        root = RemoteDandiset(
            client=client, identifier="000001", version="draft"
        ).get_path()
        responses.calls.reset()
        children = list(root.iterdir())
        assert [str(p) for p in children] == ["file.txt", "sub-01"]
        count = len(responses.calls)
        assert count == 2
        assert children[0].is_file() and not children[0].is_dir()
        assert children[1].is_dir() and not children[1].is_file()
        assert children[0].size == 5
        assert children[1].aggregate_files == 2
        assert root.size == 14 and root.aggregate_files == 3
        assert list(root.iterdir()) == children
        assert len(responses.calls) == count
        nested = list(children[1].iterdir())
        assert nested[0].name == "a.nwb"
        assert str(nested[0]) == "sub-01/a.nwb"
        assert nested[0].size == 9
        assert len(responses.calls) == count + 1
        with pytest.raises(NotADirectoryError):
            list(children[0].iterdir())
        with pytest.raises(IsADirectoryError):
            children[1].get_asset()
        assert root / "." == root and root / ".." == root
        with pytest.raises(ValueError):
            root._get_subpath("a/b")
        with pytest.raises(ValueError):
            root._get_subpath("")


@pytest.mark.ai_generated
@responses.activate
@pytest.mark.parametrize("status", [200, 404, 403])
def test_remote_unlisted_path_errors(status: int) -> None:
    import requests

    url = "https://example.test/api/dandisets/000001/versions/draft/assets/paths/"
    responses.get(url, json={"results": [], "next": None}, status=status)
    with DandiAPIClient(
        dandi_instance=DandiInstance(
            name="test", gui="https://example.test", api="https://example.test/api/"
        )
    ) as client:
        path = RemoteDandiset(
            client=client, identifier="000001", version="draft"
        ).get_path("missing")
        if status == 403:
            with pytest.raises(requests.HTTPError):
                path.exists()
        else:
            assert not path.exists() and not path.is_file() and not path.is_dir()
            with pytest.raises(NotFoundError):
                path.get_asset()
            with pytest.raises(NotFoundError):
                list(path.iterdir())


@pytest.mark.ai_generated
def test_path_listing_local_remote_parity(text_dandiset: SampleDandiset) -> None:
    mkpaths(text_dandiset.dspath, "sub-01/session/a.txt", "sub-02/b.txt")
    (text_dandiset.dspath / "sub-01/session/a.txt").write_bytes(b"alpha\n")
    (text_dandiset.dspath / "sub-02/b.txt").write_bytes(b"beta\n")
    text_dandiset.upload()
    local = Dandiset(text_dandiset.dspath).get_path()
    remote = text_dandiset.dandiset.get_path()

    def describe(root: Any) -> dict:
        return {
            str(p): (p.is_file(), p.size, p.aggregate_files) for p in root.iterdir()
        }

    assert describe(local) == describe(remote)
    assert local.size == remote.size
    assert local.aggregate_files == remote.aggregate_files == 6
    assert describe(local / "subdir2") == describe(remote / "subdir2")
    asset = (remote / "file.txt").get_asset()
    assert asset.path == "file.txt"
    assert asset.size == (local / "file.txt").size
    assert not (remote / "absent").exists()


@pytest.mark.ai_generated
@responses.activate
@pytest.mark.parametrize("kind", ["blob", "zarr"])
def test_remote_unlisted_asset_can_be_fetched(kind: str) -> None:
    base = "https://example.test/api/dandisets/000001/versions/draft/assets/"
    name = "sample.zarr" if kind == "zarr" else "file.txt"
    responses.get(
        base + "paths/",
        json={"results": [_entry(name, 1, 5, {"asset_id": "id"})], "next": None},
    )
    responses.get(
        base + "id/info/",
        json={
            "asset_id": "id",
            "path": name,
            "size": 5,
            kind: "storage-id",
            "created": "2026-01-01T00:00:00Z",
            "modified": "2026-01-01T00:00:00Z",
        },
    )
    with DandiAPIClient(
        dandi_instance=DandiInstance(
            name="test", gui="https://example.test", api="https://example.test/api/"
        )
    ) as client:
        path = RemoteDandiset(client, "000001", "draft").get_path(name)
        assert path.exists() and path.is_file() and not path.is_dir()
        assert path.size == 5 and path.aggregate_files == 1
        asset = path.get_asset()
        assert asset.path == name and asset.size == 5


@pytest.mark.ai_generated
@responses.activate
@pytest.mark.parametrize("status", [200, 404])
def test_remote_empty_or_missing_root(status: int) -> None:
    responses.get(
        "https://example.test/api/dandisets/000001/versions/draft/assets/paths/",
        json={"results": [], "next": None},
        status=status,
    )
    with DandiAPIClient(
        dandi_instance=DandiInstance(
            name="test", gui="https://example.test", api="https://example.test/api/"
        )
    ) as client:
        root = RemoteDandiset(client, "000001", "draft").get_path()
        assert root.exists() == (status == 200)
        if status == 200:
            assert list(root.iterdir()) == []
            assert root.size == root.aggregate_files == 0
        else:
            with pytest.raises(NotFoundError):
                list(root.iterdir())
