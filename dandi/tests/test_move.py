import logging
from pathlib import Path
from typing import Dict, List, Optional, cast

import pytest

from .fixtures import SampleDandiset
from ..dandiapi import RemoteAsset
from ..exceptions import NotFoundError
from ..move import AssetMismatchError, move


@pytest.fixture()
def moving_dandiset(new_dandiset: SampleDandiset) -> SampleDandiset:
    for path in [
        "file.txt",
        "subdir1/apple.txt",
        "subdir2/banana.txt",
        "subdir2/coconut.txt",
        "subdir3/red.dat",
        "subdir3/green.dat",
        "subdir3/blue.dat",
        "subdir4/foo.json",
        "subdir5/foo.json",
    ]:
        p = new_dandiset.dspath / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{path}\n")
    new_dandiset.upload_kwargs["allow_any_path"] = True
    new_dandiset.upload()
    return new_dandiset


def check_assets(
    sample_dandiset: SampleDandiset,
    starting_assets: List[RemoteAsset],
    work_on: str,
    remapping: Dict[str, Optional[str]],
) -> None:
    for asset in starting_assets:
        if asset.path in remapping and remapping[asset.path] is None:
            # Asset was overwritten
            continue
        if work_on in ("local", "both") and asset.path in remapping:
            assert not (sample_dandiset.dspath / asset.path).exists()
            assert (
                sample_dandiset.dspath / cast(str, remapping[asset.path])
            ).read_text() == f"{asset.path}\n"
        else:
            assert (
                sample_dandiset.dspath / asset.path
            ).read_text() == f"{asset.path}\n"
        if work_on in ("remote", "both") and asset.path in remapping:
            with pytest.raises(NotFoundError):
                sample_dandiset.dandiset.get_asset_by_path(asset.path)
            assert (
                sample_dandiset.dandiset.get_asset_by_path(  # type: ignore[attr-defined]
                    cast(str, remapping[asset.path])
                ).blob
                == asset.blob  # type: ignore[attr-defined]
            )
        else:
            assert (
                sample_dandiset.dandiset.get_asset_by_path(asset.path).identifier
                == asset.identifier
            )


@pytest.mark.parametrize(
    "srcs,dest,regex,remapping",
    [
        (
            ["file.txt"],
            "blob.dat",
            False,
            {"file.txt": "blob.dat"},
        ),
        (
            ["file.txt"],
            "blob.dat/",
            False,
            {"file.txt": "blob.dat/file.txt"},
        ),
        (
            ["file.txt"],
            "subdir1",
            False,
            {"file.txt": "subdir1/file.txt"},
        ),
        (
            ["file.txt"],
            "subdir1/",
            False,
            {"file.txt": "subdir1/file.txt"},
        ),
        (
            ["subdir1/apple.txt"],
            "subdir2",
            False,
            {"subdir1/apple.txt": "subdir2/apple.txt"},
        ),
        (
            ["subdir2"],
            "subdir1",
            False,
            {
                "subdir2/banana.txt": "subdir1/subdir2/banana.txt",
                "subdir2/coconut.txt": "subdir1/subdir2/coconut.txt",
            },
        ),
        (
            ["file.txt", "subdir2/banana.txt"],
            "subdir1",
            False,
            {
                "file.txt": "subdir1/file.txt",
                "subdir2/banana.txt": "subdir1/banana.txt",
            },
        ),
        (
            ["file.txt", "subdir2/banana.txt"],
            "newdir",
            False,
            {
                "file.txt": "newdir/file.txt",
                "subdir2/banana.txt": "newdir/banana.txt",
            },
        ),
        (
            [r"\.dat$"],
            ".color",
            True,
            {
                "subdir3/red.dat": "subdir3/red.color",
                "subdir3/green.dat": "subdir3/green.color",
                "subdir3/blue.dat": "subdir3/blue.color",
            },
        ),
        (
            [r"^\w+?(\d+)/(.*)\.txt$"],
            r"text\1/\2.txt",
            True,
            {
                "subdir1/apple.txt": "text1/apple.txt",
                "subdir2/banana.txt": "text2/banana.txt",
                "subdir2/coconut.txt": "text2/coconut.txt",
            },
        ),
        (
            ["subdir1/apple.txt"],
            ".",
            False,
            {"subdir1/apple.txt": "apple.txt"},
        ),
    ],
)
@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move(
    monkeypatch: pytest.MonkeyPatch,
    moving_dandiset: SampleDandiset,
    srcs: List[str],
    dest: str,
    regex: bool,
    remapping: Dict[str, Optional[str]],
    work_on: str,
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        *srcs,
        dest=dest,
        regex=regex,
        work_on=work_on,
        dandi_instance=moving_dandiset.api.instance_id,
        devel_debug=True,
    )
    check_assets(moving_dandiset, starting_assets, work_on, remapping)


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_skip(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        "file.txt",
        "subdir4/foo.json",
        dest="subdir5",
        work_on=work_on,
        existing="skip",
        dandi_instance=moving_dandiset.api.instance_id,
        devel_debug=True,
    )
    check_assets(
        moving_dandiset, starting_assets, work_on, {"file.txt": "subdir5/file.txt"}
    )


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
@pytest.mark.parametrize("kwargs", [{"existing": "error"}, {}])
def test_move_error(
    monkeypatch: pytest.MonkeyPatch,
    moving_dandiset: SampleDandiset,
    work_on: str,
    kwargs: Dict[str, str],
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(ValueError) as excinfo:
        move(
            "file.txt",
            "subdir4/foo.json",
            dest="subdir5",
            work_on=work_on,
            dandi_instance=moving_dandiset.api.instance_id,
            **kwargs,  # type: ignore[arg-type]
        )
    assert (
        str(excinfo.value) == "Cannot move 'subdir4/foo.json' to 'subdir5/foo.json', as"
        f" {'remote' if work_on == 'remote' else 'local'} destination already exists"
    )
    check_assets(moving_dandiset, starting_assets, work_on, {})


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_overwrite(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        "file.txt",
        "subdir4/foo.json",
        dest="subdir5",
        work_on=work_on,
        existing="overwrite",
        devel_debug=True,
        dandi_instance=moving_dandiset.api.instance_id,
    )
    check_assets(
        moving_dandiset,
        starting_assets,
        work_on,
        {
            "file.txt": "subdir5/file.txt",
            "subdir4/foo.json": "subdir5/foo.json",
            "subdir5/foo.json": None,
        },
    )


def test_move_no_srcs(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(ValueError) as excinfo:
        move(
            dest="nowhere",
            work_on="both",
            dandi_instance=moving_dandiset.api.instance_id,
        )
    assert str(excinfo.value) == "No source paths given"
    check_assets(moving_dandiset, starting_assets, "both", {})


def test_move_regex_multisrcs(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(ValueError) as excinfo:
        move(
            r"\.txt",
            r"\.dat",
            dest=".blob",
            regex=True,
            work_on="both",
            dandi_instance=moving_dandiset.api.instance_id,
        )
    assert (
        str(excinfo.value) == "Cannot take multiple source paths when `regex` is True"
    )
    check_assets(moving_dandiset, starting_assets, "both", {})


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_multisrcs_file_dest(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(ValueError) as excinfo:
        move(
            "file.txt",
            "subdir1/apple.txt",
            dest="subdir2/banana.txt",
            work_on=work_on,
            dandi_instance=moving_dandiset.api.instance_id,
        )
    assert (
        str(excinfo.value)
        == "Cannot take multiple source paths when destination is a file"
    )
    check_assets(moving_dandiset, starting_assets, work_on, {})


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_folder_src_file_dest(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(ValueError) as excinfo:
        move(
            "subdir1",
            dest="subdir2/banana.txt",
            work_on=work_on,
            dandi_instance=moving_dandiset.api.instance_id,
        )
    assert str(excinfo.value) == "Cannot move folder 'subdir1' to a file path"
    check_assets(moving_dandiset, starting_assets, work_on, {})


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_nonexistent_src(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(NotFoundError) as excinfo:
        move(
            "file.txt",
            "subdir1/avocado.txt",
            dest="subdir2/",
            work_on=work_on,
            dandi_instance=moving_dandiset.api.instance_id,
        )
    assert (
        str(excinfo.value)
        == f"No asset at {'remote' if work_on == 'remote' else 'local'} path 'subdir1/avocado.txt'"
    )
    check_assets(moving_dandiset, starting_assets, work_on, {})


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_file_slash_src(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(ValueError) as excinfo:
        move(
            "file.txt",
            "subdir1/apple.txt/",
            dest="subdir2/",
            work_on=work_on,
            dandi_instance=moving_dandiset.api.instance_id,
        )
    assert (
        str(excinfo.value)
        == f"{'Remote' if work_on == 'remote' else 'Local'} path 'subdir1/apple.txt/' is a file"
    )
    check_assets(moving_dandiset, starting_assets, work_on, {})


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_file_slash_dest(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(ValueError) as excinfo:
        move(
            "file.txt",
            dest="subdir1/apple.txt/",
            work_on=work_on,
            dandi_instance=moving_dandiset.api.instance_id,
        )
    assert (
        str(excinfo.value)
        == f"{'Remote' if work_on == 'remote' else 'Local'} path 'subdir1/apple.txt/' is a file"
    )
    check_assets(moving_dandiset, starting_assets, work_on, {})


def test_move_regex_no_match(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(ValueError) as excinfo:
        move(
            "no-match",
            dest="nowhere",
            regex=True,
            work_on="both",
            dandi_instance=moving_dandiset.api.instance_id,
        )
    assert (
        str(excinfo.value)
        == "Regular expression 'no-match' did not match any local paths"
    )
    check_assets(moving_dandiset, starting_assets, "both", {})


def test_move_regex_collision(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(ValueError) as excinfo:
        move(
            r"^\w+/foo\.json$",
            dest="data/data.json",
            regex=True,
            work_on="both",
            dandi_instance=moving_dandiset.api.instance_id,
        )
    assert (
        str(excinfo.value)
        == "Local assets 'subdir4/foo.json' and 'subdir5/foo.json' would both"
        " be moved to 'data/data.json'"
    )
    check_assets(moving_dandiset, starting_assets, "both", {})


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_regex_some_to_self(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    moving_dandiset: SampleDandiset,
    work_on: str,
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        r"(.+[123])/([^.]+)\.(.+)",
        dest=r"\1/\2.dat",
        regex=True,
        work_on=work_on,
        dandi_instance=moving_dandiset.api.instance_id,
        devel_debug=True,
    )
    for path in ["subdir3/red.dat", "subdir3/green.dat", "subdir3/blue.dat"]:
        for where in ["local", "remote"] if work_on == "both" else [work_on]:
            assert (
                "dandi",
                logging.DEBUG,
                f"Would move {where} asset {path!r} to itself; ignoring",
            ) in caplog.record_tuples
    check_assets(
        moving_dandiset,
        starting_assets,
        work_on,
        {
            "subdir1/apple.txt": "subdir1/apple.dat",
            "subdir2/banana.txt": "subdir2/banana.dat",
            "subdir2/coconut.txt": "subdir2/coconut.dat",
        },
    )


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_from_subdir(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath / "subdir1")
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        "../file.txt",
        "apple.txt",
        dest="../subdir2",
        work_on=work_on,
        dandi_instance=moving_dandiset.api.instance_id,
        devel_debug=True,
    )
    check_assets(
        moving_dandiset,
        starting_assets,
        work_on,
        {
            "file.txt": "subdir2/file.txt",
            "subdir1/apple.txt": "subdir2/apple.txt",
        },
    )


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_in_subdir(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath / "subdir1")
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        "apple.txt",
        dest="macintosh.txt",
        work_on=work_on,
        dandi_instance=moving_dandiset.api.instance_id,
        devel_debug=True,
    )
    check_assets(
        moving_dandiset,
        starting_assets,
        work_on,
        {"subdir1/apple.txt": "subdir1/macintosh.txt"},
    )


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_from_subdir_abspaths(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath / "subdir1")
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(NotFoundError) as excinfo:
        move(
            "file.txt",
            "subdir1/apple.txt",
            dest="subdir2",
            work_on=work_on,
            dandi_instance=moving_dandiset.api.instance_id,
        )
    assert (
        str(excinfo.value)
        == f"No asset at {'remote' if work_on == 'remote' else 'local'} path 'file.txt'"
    )
    check_assets(moving_dandiset, starting_assets, work_on, {})


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_from_subdir_as_dot(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath / "subdir1")
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(ValueError) as excinfo:
        move(
            ".",
            dest="../subdir2",
            work_on=work_on,
            dandi_instance=moving_dandiset.api.instance_id,
            devel_debug=True,
        )
    assert str(excinfo.value) == "Cannot move current working directory"
    check_assets(moving_dandiset, starting_assets, work_on, {})


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_from_subdir_regex(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath / "subdir1")
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        r"\.txt",
        dest=".dat",
        regex=True,
        work_on=work_on,
        dandi_instance=moving_dandiset.api.instance_id,
        devel_debug=True,
    )
    check_assets(
        moving_dandiset,
        starting_assets,
        work_on,
        {"subdir1/apple.txt": "subdir1/apple.dat"},
    )


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_from_subdir_regex_no_changes(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    moving_dandiset: SampleDandiset,
    work_on: str,
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath / "subdir1")
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        r"\.txt",
        dest=".txt",
        regex=True,
        work_on=work_on,
        dandi_instance=moving_dandiset.api.instance_id,
        devel_debug=True,
    )
    assert ("dandi", logging.INFO, "Nothing to move") in caplog.record_tuples
    check_assets(moving_dandiset, starting_assets, work_on, {})


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_dandiset_path(
    monkeypatch: pytest.MonkeyPatch,
    moving_dandiset: SampleDandiset,
    tmp_path: Path,
    work_on: str,
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        "file.txt",
        "subdir2/banana.txt",
        dest="subdir1",
        work_on=work_on,
        dandiset=moving_dandiset.dspath,
        dandi_instance=moving_dandiset.api.instance_id,
        devel_debug=True,
    )
    check_assets(
        moving_dandiset,
        starting_assets,
        work_on,
        {
            "file.txt": "subdir1/file.txt",
            "subdir2/banana.txt": "subdir1/banana.txt",
        },
    )


@pytest.mark.parametrize("work_on", ["auto", "remote"])
def test_move_dandiset_url(
    monkeypatch: pytest.MonkeyPatch,
    moving_dandiset: SampleDandiset,
    tmp_path: Path,
    work_on: str,
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        "file.txt",
        "subdir2/banana.txt",
        dest="subdir1",
        work_on=work_on,
        dandiset=moving_dandiset.dandiset.api_url,
        devel_debug=True,
    )
    check_assets(
        moving_dandiset,
        starting_assets,
        "remote",
        {
            "file.txt": "subdir1/file.txt",
            "subdir2/banana.txt": "subdir1/banana.txt",
        },
    )


def test_move_work_on_auto(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, tmp_path: Path
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        "file.txt",
        "subdir2/banana.txt",
        dest="subdir1",
        work_on="auto",
        dandi_instance=moving_dandiset.api.instance_id,
        devel_debug=True,
    )
    check_assets(
        moving_dandiset,
        starting_assets,
        "both",
        {
            "file.txt": "subdir1/file.txt",
            "subdir2/banana.txt": "subdir1/banana.txt",
        },
    )


@pytest.mark.parametrize("work_on", ["auto", "both", "local", "remote"])
def test_move_not_dandiset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, work_on: str
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError) as excinfo:
        move("file.txt", "subdir2/banana.txt", dest="subdir1", work_on=work_on)
    assert str(excinfo.value) == f"{tmp_path.absolute()}: not a Dandiset"


def test_move_local_delete_empty_dirs(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath / "subdir4")
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        "../subdir1/apple.txt",
        "../subdir2/banana.txt",
        "foo.json",
        dest="../subdir3",
        work_on="local",
        devel_debug=True,
    )
    check_assets(
        moving_dandiset,
        starting_assets,
        "local",
        {
            "subdir1/apple.txt": "subdir3/apple.txt",
            "subdir2/banana.txt": "subdir3/banana.txt",
            "subdir4/foo.json": "subdir3/foo.json",
        },
    )
    assert not (moving_dandiset.dspath / "subdir1").exists()
    assert (moving_dandiset.dspath / "subdir2").exists()
    assert (moving_dandiset.dspath / "subdir4").exists()


def test_move_both_src_path_not_in_local(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset
) -> None:
    (moving_dandiset.dspath / "subdir2" / "banana.txt").unlink()
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(AssetMismatchError) as excinfo:
        move(
            "subdir2",
            dest="subdir3",
            work_on="both",
            dandi_instance=moving_dandiset.api.instance_id,
            devel_debug=True,
        )
    assert (
        str(excinfo.value) == "Mismatch between local and remote Dandisets:\n"
        "- Asset 'subdir2/banana.txt' only exists remotely\n"
        "- Asset 'subdir2/coconut.txt' only exists remotely"
    )
    check_assets(moving_dandiset, starting_assets, "both", {"subdir2/banana.txt": None})


def test_move_both_src_path_not_in_remote(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset
) -> None:
    (moving_dandiset.dspath / "subdir2" / "mango.txt").write_text("Mango\n")
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(AssetMismatchError) as excinfo:
        move(
            "subdir2",
            dest="subdir3",
            work_on="both",
            dandi_instance=moving_dandiset.api.instance_id,
            devel_debug=True,
        )
    assert (
        str(excinfo.value) == "Mismatch between local and remote Dandisets:\n"
        "- Asset 'subdir2/mango.txt' only exists locally"
    )
    check_assets(moving_dandiset, starting_assets, "both", {})


@pytest.mark.parametrize("existing", ["skip", "overwrite"])
def test_move_both_dest_path_not_in_remote(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, existing: str
) -> None:
    (moving_dandiset.dspath / "subdir2" / "file.txt").write_text("This is a file.\n")
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(AssetMismatchError) as excinfo:
        move(
            "file.txt",
            dest="subdir2",
            work_on="both",
            existing=existing,
            dandi_instance=moving_dandiset.api.instance_id,
            devel_debug=True,
        )
    assert (
        str(excinfo.value) == "Mismatch between local and remote Dandisets:\n"
        "- Asset 'file.txt' would be moved to 'subdir2/file.txt', which exists"
        " locally but not remotely"
    )
    check_assets(moving_dandiset, starting_assets, "both", {})


@pytest.mark.parametrize("existing", ["skip", "overwrite"])
def test_move_both_dest_path_not_in_local(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, existing: str
) -> None:
    (moving_dandiset.dspath / "subdir2" / "banana.txt").unlink()
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(AssetMismatchError) as excinfo:
        move(
            "file.txt",
            dest="subdir2/banana.txt",
            work_on="both",
            existing=existing,
            dandi_instance=moving_dandiset.api.instance_id,
            devel_debug=True,
        )
    assert (
        str(excinfo.value)
        == "Mismatch between local and remote Dandisets:\n- Asset 'file.txt'"
        " would be moved to 'subdir2/banana.txt', which exists remotely but"
        " not locally"
    )
    check_assets(moving_dandiset, starting_assets, "both", {"subdir2/banana.txt": None})


def test_move_both_dest_mismatch(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset
) -> None:
    (moving_dandiset.dspath / "subdir1" / "apple.txt").unlink()
    (moving_dandiset.dspath / "subdir1" / "apple.txt").mkdir()
    (moving_dandiset.dspath / "subdir1" / "apple.txt" / "seeds").write_text("12345\n")
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    with pytest.raises(AssetMismatchError) as excinfo:
        move(
            "file.txt",
            dest="subdir1/apple.txt",
            work_on="both",
            existing="overwrite",
            dandi_instance=moving_dandiset.api.instance_id,
            devel_debug=True,
        )
    assert (
        str(excinfo.value) == "Mismatch between local and remote Dandisets:\n"
        "- Asset 'file.txt' would be moved to 'subdir1/apple.txt/file.txt'"
        " locally but to 'subdir1/apple.txt' remotely"
    )
    check_assets(moving_dandiset, starting_assets, "both", {"subdir1/apple.txt": None})


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_pyout(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        "file.txt",
        "subdir4/foo.json",
        dest="subdir5",
        work_on=work_on,
        existing="overwrite",
        devel_debug=False,
        dandi_instance=moving_dandiset.api.instance_id,
    )
    check_assets(
        moving_dandiset,
        starting_assets,
        work_on,
        {
            "file.txt": "subdir5/file.txt",
            "subdir4/foo.json": "subdir5/foo.json",
            "subdir5/foo.json": None,
        },
    )


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_pyout_dry_run(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset, work_on: str
) -> None:
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        "file.txt",
        "subdir4/foo.json",
        dest="subdir5",
        work_on=work_on,
        existing="overwrite",
        devel_debug=False,
        dry_run=True,
        dandi_instance=moving_dandiset.api.instance_id,
    )
    check_assets(moving_dandiset, starting_assets, work_on, {})


@pytest.mark.parametrize("work_on", ["local", "remote", "both"])
def test_move_path_to_self(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    moving_dandiset: SampleDandiset,
    work_on: str,
) -> None:
    (moving_dandiset.dspath / "newdir").mkdir()
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath / "subdir1")
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        "apple.txt",
        dest="../subdir1",
        work_on=work_on,
        devel_debug=True,
        dandi_instance=moving_dandiset.api.instance_id,
    )
    for where in ["local", "remote"] if work_on == "both" else [work_on]:
        assert (
            "dandi",
            logging.DEBUG,
            f"Would move {where} asset 'subdir1/apple.txt' to itself; ignoring",
        ) in caplog.record_tuples
    assert ("dandi", logging.INFO, "Nothing to move") in caplog.record_tuples
    check_assets(moving_dandiset, starting_assets, work_on, {})


def test_move_remote_dest_is_local_dir_sans_slash(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset
) -> None:
    (moving_dandiset.dspath / "newdir").mkdir()
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        "file.txt",
        dest="newdir",
        work_on="remote",
        devel_debug=True,
        dandi_instance=moving_dandiset.api.instance_id,
    )
    check_assets(moving_dandiset, starting_assets, "remote", {"file.txt": "newdir"})


def test_move_both_dest_is_local_dir_sans_slash(
    monkeypatch: pytest.MonkeyPatch, moving_dandiset: SampleDandiset
) -> None:
    (moving_dandiset.dspath / "newdir").mkdir()
    starting_assets = list(moving_dandiset.dandiset.get_assets())
    monkeypatch.chdir(moving_dandiset.dspath)
    monkeypatch.setenv("DANDI_API_KEY", moving_dandiset.api.api_key)
    move(
        "file.txt",
        dest="newdir",
        work_on="both",
        devel_debug=True,
        dandi_instance=moving_dandiset.api.instance_id,
    )
    check_assets(
        moving_dandiset, starting_assets, "both", {"file.txt": "newdir/file.txt"}
    )
