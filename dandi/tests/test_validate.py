from ..validate import validate_file


def test_validate_simple1(simple1_nwb):
    # this file lacks subject_id
    errors = validate_file(simple1_nwb)
    assert len(errors) == 1
    assert errors[0] == "Required field 'subject_id' has no value"


def test_validate_simple2(simple2_nwb):
    # this file should be ok
    errors = validate_file(simple2_nwb)
    assert not errors
