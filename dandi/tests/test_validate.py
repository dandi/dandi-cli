from ..models import get_schema_version
from ..validate import validate_file


def test_validate_simple1(simple1_nwb):
    # this file should be ok
    errors = validate_file(simple1_nwb, schema_version=get_schema_version())
    assert not errors


def test_validate_simple2(simple2_nwb):
    # this file should be ok
    errors = validate_file(simple2_nwb)
    assert not errors


def test_validate_simple2_new(simple2_nwb):
    # this file should be ok
    errors = validate_file(simple2_nwb, schema_version=get_schema_version())
    assert not errors


def test_validate_bogus(tmp_path):
    path = tmp_path / "wannabe.nwb"
    path.write_text("not really nwb")
    # intended to produce use-case for https://github.com/dandi/dandi-cli/issues/93
    # but it would be tricky, so it is more of a smoke test that
    # we do not crash
    errors = validate_file(str(path))
    # ATM we would get 2 errors -- since could not be open in two places,
    # but that would be too rigid to test. Let's just see that we have expected errors
    assert any(e.startswith("Failed to read metadata") for e in errors)
