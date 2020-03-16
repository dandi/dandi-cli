import os
from glob import glob
import os.path as op
import ruamel.yaml
import yaml

from ..consts import file_operation_modes

from ..cli.command import organize
from ..organize import (
    _sanitize_value,
    create_dataset_yml_template,
    get_obj_id,
    populate_dataset_yml,
)
from ..utils import find_files, on_windows
from ..pynwb_utils import copy_nwb_file, get_object_id
import pytest


yaml_ruamel = ruamel.yaml.YAML()  # defaults to round-trip if no parameters given


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
        "number_of_cells": 2,
        "number_of_tissue_samples": 1,
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
        "number_of_cells": 1,
        "number_of_tissue_samples": 1,
        "sex": ["M"],
        "age": {"maximum": 1, "minimum": 1, "units": "years"},
    }

    # TODO: species
    # TODO: experiment_description
    # TODO: related_publications

    # Let's play with a templated version
    create_dataset_yml_template(path)
    c1 = c()
    assert str(c1).count("REQUIRED") > 10  # plenty of those
    populate_dataset_yml(str(path), [])
    assert c1 == c()  # no changes

    populate_dataset_yml(str(path), metadata)
    # too big, check one
    assert c()["number_of_cells"] == 2


# do not test 'move' - would need  a dedicated handling since it would
# really move data away and break testing of other modes
no_move_modes = file_operation_modes[:]
no_move_modes.remove("move")
if not on_windows:
    # github workflows start whining about cross-drives links
    no_move_modes.append("symlink-relative")


@pytest.mark.integration
@pytest.mark.parametrize("mode", no_move_modes)
def test_organize_nwb_test_data(nwb_test_data, tmpdir, clirunner, mode):
    outdir = str(tmpdir / "organized")

    relative = False
    if mode == "symlink-relative":
        # Force relative paths, as if e.g. user did provide
        relative = True
        mode = "symlink"
        # all paths will be relative to the curdir, which should cause
        # organize also organize using relative paths in case of 'symlink'
        # mode
        cwd = os.getcwd()
        nwb_test_data = op.relpath(nwb_test_data, cwd)
        outdir = op.relpath(outdir, cwd)

    input_files = op.join(nwb_test_data, "v2.0.1")

    cmd = ["-d", outdir, "--files-mode", mode, input_files]
    r = clirunner.invoke(organize, cmd)

    # with @map_to_click_exceptions we loose original str of message somehow
    # although it is shown to the user - checked. TODO - figure it out
    # assert "not containing all" in str(r.exc_info[1])
    assert r.exit_code != 0, f"Must have aborted since many files lack subject_id"
    assert not glob(op.join(outdir, "*")), "no files should have been populated"

    r = clirunner.invoke(organize, cmd + ["--invalid", "warn"])
    assert r.exit_code == 0
    # this beast doesn't capture our logs ATM so cannot check anything there.
    # At the end we endup only with dandiset.yaml and a single file
    produced_paths = sorted(find_files(".*", paths=outdir))
    produced_nwb_paths = sorted(find_files(".nwb$", paths=outdir))
    produced_relpaths = [op.relpath(p, outdir) for p in produced_paths]
    if mode == "dry":
        assert produced_relpaths == []
    else:
        assert produced_relpaths == [
            "dandiset.yaml",
            op.join("sub-RAT123", "sub-RAT123.nwb"),
        ]
        # and that all files are accessible (so in case of symlinking - no broken
        # symlinks)
        assert all(map(op.exists, produced_paths))

    if mode == "simulate":
        assert all((op.isabs(p) != relative) for p in produced_paths)
    elif mode == "symlink":
        assert all(op.islink(p) for p in produced_nwb_paths)
    else:
        assert not any(op.islink(p) for p in produced_paths)


def test_ambigous(simple2_nwb, tmp_path, clirunner):
    copy2 = copy_nwb_file(simple2_nwb, tmp_path)
    outdir = str(tmp_path / "organized")
    args = ["--files-mode", "copy", "-d", outdir, simple2_nwb, copy2]
    r = clirunner.invoke(organize, args)
    assert r.exit_code == 0
    produced_paths = sorted(find_files(".*", paths=outdir))
    produced_paths_rel = [op.relpath(p, outdir) for p in produced_paths]
    assert produced_paths_rel == sorted(
        ["dandiset.yaml"]
        + [
            op.join(
                "sub-mouse001", "sub-mouse001_obj-%s.nwb" % get_obj_id(get_object_id(f))
            )
            for f in [simple2_nwb, copy2]
        ]
    )
