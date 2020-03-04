import yaml
import ruamel.yaml

yaml_ruamel = ruamel.yaml.YAML()  # defaults to round-trip if no parameters given

from ..organize import (
    _sanitize_value,
    populate_dataset_yml,
    create_dataset_yml_template,
)


def test_sanitize_value():
    # . is not sanitized in extension but elsewhere
    assert _sanitize_value("_.ext", "extension") == "-.ext"
    assert _sanitize_value("_.ext", "unrelated") == "--ext"


def test_populate_dataset_yml(tmpdir):
    # should work even on an empty file
    path = tmpdir / "blah.yaml"

    def c():  # shortcut
        with open(path) as f:
            return yaml.safe_load(f)

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

    # even though we use ruyaml for manipulation, we should assure it is readable
    # by regular yaml
    populate_dataset_yml(str(path), metadata)
    assert c() == {
        "id": "test1",
        "number_cells": 2,
        "number_tissueSamples": 1,
        "sex": ["F", "M"],
        "age": {"maximum": 2, "minimum": 1, "units": "TODO"},
    }

    # and if we set units and redo -- years should stay unchanged, while other fields change
    m = yaml_ruamel.load(path.read())
    m["age"]["units"] = "years"
    yaml_ruamel.dump(m, open(path, "w"))

    populate_dataset_yml(str(path), metadata[:1])
    assert c() == {
        "id": "test1",
        "number_cells": 1,
        "number_tissueSamples": 1,
        "sex": ["M"],
        "age": {"maximum": 1, "minimum": 1, "units": "years"},
    }

    # Let's play with a templated version
    create_dataset_yml_template(path)
    c1 = c()
    assert str(c1).count("REQUIRED") > 10  # plenty of those
    populate_dataset_yml(str(path), [])
    assert c1 == c()  # no changes

    populate_dataset_yml(str(path), metadata)
    # too big, check one
    assert c()["number_cells"] == 2
