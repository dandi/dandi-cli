import yaml

from ..organize import _sanitize_value, populate_dataset_yml


def test_sanitize_value():
    # . is not sanitized in extension but elsewhere
    assert _sanitize_value("_.ext", "extension") == "-.ext"
    assert _sanitize_value("_.ext", "unrelated") == "--ext"


def test_populate_dataset_yml(tmpdir):
    # should work even on an empty file
    path = tmpdir / "blah.yaml"
    path.write("")
    populate_dataset_yml(str(path), [])  # doesn't crash

    path.write("id: test1  # comment")  # no ID assumptions, or querying
    populate_dataset_yml(str(path), [])  # doesn't crash
    # even comments should be preserved and no changes if no relevant metadata
    assert path.read().strip() == "id: test1  # comment"

    metadata = [
        # context for all the ids are dataset level ATM, so even when no
        # subject_id, counts would be just of unique values
        {"age": 1, "cell_id": "1", "tissue_sample_id": 1, "sex": "M"},
        {"age": 2, "cell_id": "2", "tissue_sample_id": 1, "sex": "F"},
    ]
    populate_dataset_yml(str(path), metadata)

    # even though we use ruyaml for manipulation, we should assure it is readable
    # by regular yaml
    with open(path) as f:
        assert yaml.safe_load(f) == {
            "id": "test1",
            "number_cells": 2,
            "number_tissueSamples": 1,
            "sex": ["F", "M"],
        }
