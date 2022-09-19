from glob import glob
import os
import os.path as op
from pathlib import Path
from typing import Any, NoReturn

from click.testing import CliRunner
from pynwb import NWBHDF5IO
import pytest
import ruamel.yaml

from ..cli.command import organize
from ..consts import file_operation_modes
from ..organize import (
    _sanitize_value,
    create_dataset_yml_template,
    create_unique_filenames_from_metadata,
    detect_link_type,
    get_obj_id,
    populate_dataset_yml,
)
from ..pynwb_utils import _get_image_series, copy_nwb_file, get_object_id
from ..utils import find_files, on_windows, yaml_load


def test_sanitize_value() -> None:
    # . is not sanitized in extension but elsewhere
    assert _sanitize_value("_.ext", "extension") == "-.ext"
    assert _sanitize_value("_.ext", "unrelated") == "--ext"
    assert _sanitize_value("A;B", "unrelated") == "A-B"
    assert _sanitize_value("A\\/B", "unrelated") == "A--B"
    assert _sanitize_value("A\"'B", "unrelated") == "A--B"


def test_populate_dataset_yml(tmp_path: Path) -> None:
    # should work even on an empty file
    path = tmp_path / "blah.yaml"

    def c() -> Any:  # shortcut
        with open(path) as f:
            return yaml_load(f, typ="safe")

    path.write_text("")
    populate_dataset_yml(str(path), [])  # doesn't crash

    path.write_text("id: test1  # comment")  # no ID assumptions, or querying
    populate_dataset_yml(str(path), [])  # doesn't crash
    # even comments should be preserved and no changes if no relevant metadata
    assert path.read_text().strip() == "id: test1  # comment"

    metadata = [
        # context for all the ids are dataset level ATM, so even when no
        # subject_id, counts would be just of unique values
        {"age": 1, "cell_id": "1", "tissue_sample_id": 1, "sex": "M"},
        {"age": 2, "cell_id": "2", "tissue_sample_id": 1, "sex": "F"},
    ]

    # even though we use ruamel for manipulation, we should assure it is readable
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
    m = yaml_load(path.read_text())
    m["age"]["units"] = "years"
    with open(path, "w") as fp:
        ruamel.yaml.YAML().dump(m, fp)

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
def test_organize_nwb_test_data(nwb_test_data: str, tmp_path: Path, mode: str) -> None:
    outdir = str(tmp_path / "organized")

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

    src = tmp_path / "src"
    src.touch()
    dest = tmp_path / "dest"
    try:
        dest.symlink_to(src)
    except OSError:
        symlinks_work = False
    else:
        symlinks_work = True
    try:
        dest.unlink()
    except FileNotFoundError:
        pass
    try:
        os.link(src, dest)
    except OSError:
        hardlinks_work = False
    else:
        hardlinks_work = True

    if mode in ("simulate", "symlink") and not symlinks_work:
        pytest.skip("Symlinks not supported")
    elif mode == "hardlink" and not hardlinks_work:
        pytest.skip("Hard links not supported")

    input_files = op.join(nwb_test_data, "v2.0.1")

    cmd = ["-d", outdir, "--files-mode", mode, input_files]
    r = CliRunner().invoke(organize, cmd)

    # with @map_to_click_exceptions we loose original str of message somehow
    # although it is shown to the user - checked. TODO - figure it out
    # assert "not containing all" in str(r.exc_info[1])
    assert r.exit_code != 0, "Must have aborted since many files lack subject_id"
    assert not glob(op.join(outdir, "*")), "no files should have been populated"

    r = CliRunner().invoke(organize, cmd + ["--invalid", "warn"])
    assert r.exit_code == 0
    # this beast doesn't capture our logs ATM so cannot check anything there.
    # At the end we endup only with a single file (we no longer produce dandiset.yaml)
    produced_paths = sorted(find_files(".*", paths=outdir))
    produced_nwb_paths = sorted(find_files(r"\.nwb\Z", paths=outdir))
    produced_relpaths = [op.relpath(p, outdir) for p in produced_paths]
    if mode == "dry":
        assert produced_relpaths == []
    else:
        assert produced_relpaths == [
            op.join("sub-RAT123", "sub-RAT123.nwb"),
        ]
        # and that all files are accessible (so in case of symlinking - no broken
        # symlinks)
        assert all(map(op.exists, produced_paths))

    if mode == "simulate":
        assert all((op.isabs(p) != relative) for p in produced_paths)
    elif mode == "symlink" or (mode == "auto" and symlinks_work):
        assert all(op.islink(p) for p in produced_nwb_paths)
    else:
        assert not any(op.islink(p) for p in produced_paths)


def test_ambiguous(simple2_nwb: str, tmp_path: Path) -> None:
    copy2 = copy_nwb_file(simple2_nwb, tmp_path)
    outdir = str(tmp_path / "organized")
    args = ["--files-mode", "copy", "-d", outdir, simple2_nwb, copy2]
    r = CliRunner().invoke(organize, args)
    assert r.exit_code == 0
    produced_paths = sorted(find_files(".*", paths=outdir))
    produced_paths_rel = [op.relpath(p, outdir) for p in produced_paths]
    assert produced_paths_rel == sorted(
        op.join(
            "sub-mouse001", "sub-mouse001_obj-%s.nwb" % get_obj_id(get_object_id(f))
        )
        for f in [simple2_nwb, copy2]
    )


def test_ambiguous_probe1() -> None:
    base = dict(subject_id="1", session="2", extension="nwb")
    # fake filenames should be ok since we never should get to reading them for object_id
    metadata = [
        dict(path="1.nwb", probe_ids=[1, 2], **base),
        dict(path="2.nwb", probe_ids=[1], modalities=["mod"], **base),
        dict(path="3.nwb", probe_ids=[2], modalities=["mod"], **base),
    ]
    # we should get a copy
    metadata_ = create_unique_filenames_from_metadata(metadata)
    assert metadata_ != metadata
    assert [m["dandi_path"] for m in metadata_] == [
        op.join("sub-1", "sub-1.nwb"),
        op.join("sub-1", "sub-1_probe-1_mod.nwb"),
        op.join("sub-1", "sub-1_probe-2_mod.nwb"),
    ]
    # if modalities is present but different -- no probe for _mod2
    metadata[0]["modalities"] = ["mod2"]
    metadata_ = create_unique_filenames_from_metadata(metadata)
    assert [m["dandi_path"] for m in metadata_] == [
        op.join("sub-1", "sub-1_mod2.nwb"),
        op.join("sub-1", "sub-1_probe-1_mod.nwb"),
        op.join("sub-1", "sub-1_probe-2_mod.nwb"),
    ]

    # but if modalities is same -- we would get probes listed
    metadata[0]["modalities"] = ["mod"]
    metadata_ = create_unique_filenames_from_metadata(metadata)
    assert [m["dandi_path"] for m in metadata_] == [
        op.join("sub-1", "sub-1_probe-1+2_mod.nwb"),
        op.join("sub-1", "sub-1_probe-1_mod.nwb"),
        op.join("sub-1", "sub-1_probe-2_mod.nwb"),
    ]


@pytest.mark.parametrize(
    "sym_success,hard_success,result",
    [
        (True, True, "symlink"),
        (True, False, "symlink"),
        (False, True, "hardlink"),
        (False, False, "copy"),
    ],
)
def test_detect_link_type(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sym_success: bool,
    hard_success: bool,
    result: str,
) -> None:
    def succeed_link(src: Any, dest: Any) -> None:
        pass

    def error_link(src: Any, dest: Any) -> NoReturn:
        raise OSError("Operation failed")

    monkeypatch.setattr(os, "symlink", succeed_link if sym_success else error_link)
    monkeypatch.setattr(os, "link", succeed_link if hard_success else error_link)
    p = tmp_path / "file"
    p.touch()
    assert detect_link_type(p, tmp_path) == result


@pytest.mark.parametrize("mode", ["copy", "move"])
@pytest.mark.parametrize("video_mode", ["copy", "move", "symlink", "hardlink"])
def test_video_organize(video_mode, mode, nwbfiles_video_unique):
    dandi_organize_path = nwbfiles_video_unique.parent / "dandi_organized"
    cmd = [
        "--files-mode",
        mode,
        "--update-external-file-paths",
        "--media-files-mode",
        video_mode,
        "-d",
        str(dandi_organize_path),
        str(nwbfiles_video_unique),
    ]
    video_files_list = list((nwbfiles_video_unique.parent / "video_files").iterdir())
    video_files_organized = []
    r = CliRunner().invoke(organize, cmd)
    assert r.exit_code == 0
    for nwbfile_name in dandi_organize_path.glob("**/*.nwb"):
        vid_folder = nwbfile_name.with_suffix("")
        assert vid_folder.exists()
        with NWBHDF5IO(str(nwbfile_name), "r", load_namespaces=True) as io:
            nwbfile = io.read()
            # get iamgeseries objects as dict(id=object_id, external_files=[])
            ext_file_objects = _get_image_series(nwbfile)
            for ext_file_ob in ext_file_objects:
                for no, name in enumerate(ext_file_ob["external_files"]):
                    video_files_organized.append(name)
                    # check if external_file arguments are correctly named according to convention:
                    filename = Path(
                        f"{vid_folder.name}/{ext_file_ob['id']}_external_file_{no}"
                    )
                    assert str(filename) == str(Path(name).with_suffix(""))
                    # check if the files exist( both in case of move/copy):
                    assert (vid_folder.parent / name).exists()
    # check all video files are organized:
    assert len(video_files_list) == len(video_files_organized)


@pytest.mark.parametrize("video_mode", ["copy", "move"])
def test_video_organize_common(video_mode, nwbfiles_video_common):
    dandi_organize_path = nwbfiles_video_common.parent / "dandi_organized"
    cmd = [
        "--files-mode",
        "move",
        "--update-external-file-paths",
        "--media-files-mode",
        video_mode,
        "-d",
        str(dandi_organize_path),
        str(nwbfiles_video_common),
    ]
    r = CliRunner().invoke(organize, cmd)
    if video_mode == "move":
        assert r.exit_code == 1
        print(r.exception)
    else:
        assert r.exit_code == 0
        print(r.stdout)
