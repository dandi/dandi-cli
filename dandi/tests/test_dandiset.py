from pathlib import Path

from ..dandiset import Dandiset


def test_get_dandiset_record() -> None:
    out = Dandiset.get_dandiset_record({"identifier": "000000"})
    # Should have only header with "DO NOT EDIT"
    assert out.startswith("# DO NOT EDIT")
    assert "000000" in out


def test_get_subject_ids(tmp_path: Path) -> None:
    (tmp_path / "dandiset.yaml").write_text("identifier: '000001'\n")
    (tmp_path / "sub-mouse2").mkdir()
    (tmp_path / "sub-mouse2" / "record.nwb").touch()
    (tmp_path / "sub-mouse1").mkdir()
    (tmp_path / "sub-").mkdir()
    (tmp_path / "sub-root.nwb").touch()
    (tmp_path / "subjects").mkdir()

    assert Dandiset(tmp_path).get_subject_ids() == ["mouse1", "mouse2"]
