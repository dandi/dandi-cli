import inspect
import os.path as op
import time
import datetime
import pytest
from ..utils import (
    ensure_datetime,
    ensure_strtime,
    find_files,
    flatten,
    flattened,
    get_utcnow_datetime,
    is_same_time,
    on_windows,
    remap_dict,
)


def test_find_files():
    tests_dir = op.dirname(__file__)
    proj_dir = op.normpath(op.join(op.dirname(__file__), op.pardir))

    ff = find_files(".*", proj_dir)
    assert inspect.isgenerator(ff)
    files = list(ff)
    assert len(files) > 3  # we have more than 3 test files here
    assert op.join(tests_dir, "test_utils.py") in files
    # and no directories should be mentioned
    assert tests_dir not in files

    ff2 = find_files(".*", proj_dir, dirs=True)
    files2 = list(ff2)
    assert op.join(tests_dir, "test_utils.py") in files2
    assert tests_dir in files2

    # now actually matching the path
    ff3 = find_files(
        r".*\\test_.*\.py$" if on_windows else r".*/test_.*\.py$", proj_dir, dirs=True
    )
    files3 = list(ff3)
    assert op.join(tests_dir, "test_utils.py") in files3
    assert tests_dir not in files3
    for f in files3:
        assert op.basename(f).startswith("test_")

    # TODO: more tests


def test_find_files_dotfiles(tmpdir):
    tmpsubdir = tmpdir.mkdir("subdir")
    for p in (".dot.nwb", "regular", ".git"):
        for f in (tmpdir / p, tmpsubdir / p):
            f.write_text("", "utf-8")

    def relpaths(paths):
        return sorted(op.relpath(p, tmpdir) for p in paths)

    regular = ["regular", op.join("subdir", "regular")]
    dotfiles = [".dot.nwb", op.join("subdir", ".dot.nwb")]
    vcs = [".git", op.join("subdir", ".git")]

    ff = find_files(".*", tmpdir)
    assert relpaths(ff) == regular

    ff = find_files(".*", tmpdir, exclude_dotfiles=False)
    # we still exclude VCS
    assert relpaths(ff) == sorted(regular + dotfiles)

    # current VCS are also dot files
    ff = find_files(".*", tmpdir, exclude_vcs=False)
    assert relpaths(ff) == regular

    # current VCS are also dot files
    ff = find_files(".*", tmpdir, exclude_vcs=False, exclude_dotfiles=False)
    assert relpaths(ff) == sorted(regular + dotfiles + vcs)


def test_times_manipulations():
    t0 = get_utcnow_datetime()
    t0_isoformat = ensure_strtime(t0)
    t0_str = ensure_strtime(t0, isoformat=False)

    assert t0 == ensure_datetime(t0)
    assert isinstance(t0_isoformat, str)
    # Test comparison and round-trips
    assert is_same_time(t0, t0_isoformat, t0_str)
    assert is_same_time(t0, t0_str)
    assert is_same_time(t0, t0_str, tollerance=0)  # exactly the same
    assert t0_str != t0_isoformat  # " " vs "T"

    time.sleep(0.001)  # so there is a definite notable delay, in particular for Windows
    t1_epoch = time.time()
    t1 = ensure_datetime(t1_epoch)
    assert is_same_time(t1, t1_epoch)
    # We must not consume more than half a second between start of this test
    # and here
    assert is_same_time(t0, t1, tollerance=0.5)
    assert is_same_time(t1, t0, tollerance=0.5)
    # but must not be exactly the same unless we are way too fast or disregard
    # milliseconds
    assert not is_same_time(t0, t1, tollerance=0)
    assert is_same_time(t0, t1_epoch + 100, tollerance=101)


@pytest.mark.parametrize(
    "t", ["2018-09-26 17:29:17.000000-07:00", "2018-09-26 17:29:17-07:00"]
)
def test_time_samples(t):
    assert is_same_time(
        ensure_datetime(t), "2018-09-27 00:29:17-00:00", tollerance=0
    )  # exactly the same


def test_flatten():
    assert inspect.isgenerator(flatten([1]))
    # flattened is just a list() around flatten
    assert flattened([1, [2, 3, [4]], 5, (i for i in range(2))]) == [
        1,
        2,
        3,
        4,
        5,
        0,
        1,
    ]


@pytest.mark.parametrize(
    "from_,revmapping,to",
    [
        ({"1": 2}, {"1": "1"}, {"1": 2}),
        ({1: 2}, {(1,): [1]}, {1: 2}),  # if path must not be string, use list or tuple
        (
            {1: 2},
            {"sub.key": (1,)},
            {"sub": {"key": 2}},
        ),  # if path must not be string, use list or tuple
        (
            {1: 2, "a": {"b": [1]}},
            {"sub.key": (1,), "sub.key2.blah": "a.b"},
            {"sub": {"key": 2, "key2": {"blah": [1]}}},
        ),
    ],
)
def test_remap_dict(from_, revmapping, to):
    assert remap_dict(from_, revmapping) == to
