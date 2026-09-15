from pathlib import Path, PurePosixPath

import pytest
from pytest_mock import MockerFixture

from .test_files import mkpaths
from ..dandiset import Dandiset
from ..files import find_dandi_files
from ..upload import _partition_upload_assets, upload


@pytest.mark.ai_generated
@pytest.mark.parametrize("allow_any_path", [False, True])
@pytest.mark.parametrize(
    "roots, expected",
    [
        (["."], ["Thumbs.db", "mixed/sidecar.json", "notes", "unknown.txt"]),
        (["mixed"], ["mixed/sidecar.json"]),
        (["notes"], ["notes/nested"]),
        (["notes/nested/readme.txt"], ["notes/nested/readme.txt"]),
        (["mixed", "mixed/known.nwb"], ["mixed/sidecar.json"]),
        (["sample.zarr"], []),
        (["empty", ".hidden"], []),
    ],
)
def test_partition_matches_discovery(
    tmp_path: Path, roots: list[str], expected: list[str], allow_any_path: bool
) -> None:
    mkpaths(
        tmp_path,
        "dandiset.yaml",
        "known.nwb",
        "unknown.txt",
        "Thumbs.db",
        "notes/nested/readme.txt",
        "mixed/known.nwb",
        "mixed/sidecar.json",
        "sample.zarr/chunk",
        "empty/",
        ".hidden/secret.nwb",
        "__MACOSX/._known.nwb",
    )
    ds = Dandiset(tmp_path)
    assets = ds.assets(allow_all=True)
    selected, omitted = _partition_upload_assets(
        assets, [PurePosixPath(p) for p in roots], allow_any_path
    )
    # Compare against the real discovery pipeline, including request scoping.
    baseline = ds.assets(allow_all=allow_any_path)
    assert sorted(a.path for a in selected) == sorted(
        {a.path for root in roots for a in baseline.under_paths([root])}
    )
    assert [str(p) for p in omitted] == ([] if allow_any_path else expected)


@pytest.mark.ai_generated
def test_wholly_unrecognized_dandiset(tmp_path: Path) -> None:
    mkpaths(tmp_path, "dandiset.yaml", "a.txt", "notes/readme.txt")
    selected, omitted = _partition_upload_assets(
        Dandiset(tmp_path).assets(allow_all=True), [PurePosixPath(".")], False
    )
    assert selected == []
    assert omitted == [PurePosixPath("a.txt"), PurePosixPath("notes")]


@pytest.mark.ai_generated
def test_bids_assets_stay_recognized(tmp_path: Path) -> None:
    mkpaths(tmp_path, "dandiset.yaml", "dataset_description.json", "sidecar.json")
    assets = Dandiset(tmp_path).assets(allow_all=True)
    selected, omitted = _partition_upload_assets(assets, [PurePosixPath(".")], False)
    assert sorted(a.filepath for a in selected) == sorted(
        a.filepath for a in find_dandi_files(tmp_path, dandiset_path=tmp_path)
    )
    assert omitted == []


@pytest.mark.ai_generated
def test_symlinked_directory_is_not_an_omitted_asset(tmp_path: Path) -> None:
    mkpaths(tmp_path, "dandiset.yaml", "target/notes.txt")
    try:
        (tmp_path / "linked").symlink_to(tmp_path / "target", target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Cannot create directory symlink: {exc}")
    selected, omitted = _partition_upload_assets(
        Dandiset(tmp_path).assets(allow_all=True), [PurePosixPath("linked")], False
    )
    assert selected == []
    assert omitted == []


@pytest.mark.ai_generated
@pytest.mark.parametrize("count", [1, 12])
def test_upload_unknown_only_reports_paths(
    tmp_path: Path, mocker: MockerFixture, caplog: pytest.LogCaptureFixture, count: int
) -> None:
    mkpaths(tmp_path, "dandiset.yaml", *(f"note-{i:02}.txt" for i in range(count)))
    (tmp_path / "dandiset.yaml").write_text("identifier: '000001'\n")
    mocker.patch("dandi.upload.DandiAPIClient.for_dandi_instance")
    upload([tmp_path])
    (record,) = [
        r for r in caplog.records if "not recognized as DANDI assets" in r.message
    ]
    expected = ", ".join(f"note-{i:02}.txt" for i in range(min(count, 10)))
    if count > 10:
        expected += ", ..."
    assert isinstance(record.args, tuple)
    assert record.args[-1] == expected
    assert "note-11.txt" in caplog.text if count > 10 else "note-00.txt" in caplog.text
