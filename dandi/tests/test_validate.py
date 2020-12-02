from ..validate import validate_file


def test_validate_simple1(monkeypatch, simple1_nwb):
    monkeypatch.setenv("DANDI_SCHEMA", "1")
    # this file lacks subject_id
    errors = validate_file(simple1_nwb)
    assert len(errors) == 1
    assert errors[0] == (
        "1 validation error for AssetMeta\n"
        "wasDerivedFrom -> 0 -> identifier\n"
        "  none is not an allowed value (type=type_error.none.not_allowed)"
    )


def test_validate_simple2(simple2_nwb):
    # this file should be ok
    errors = validate_file(simple2_nwb)
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
