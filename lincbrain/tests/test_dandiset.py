from ..dandiset import Dandiset


def test_get_dandiset_record() -> None:
    out = Dandiset.get_dandiset_record({"identifier": "000000"})
    # Should have only header with "DO NOT EDIT"
    assert out.startswith("# DO NOT EDIT")
    assert "000000" in out
