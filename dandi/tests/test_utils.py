import inspect
import os.path as op
import time

from ..utils import (
    ensure_datetime,
    ensure_strtime,
    find_files,
    get_utcnow_datetime,
    is_same_time,
    on_windows,
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

    t1_epoch = time.time()
    t1 = ensure_datetime(t1_epoch)
    assert is_same_time(t1, t1_epoch)
    # We must not consume more than half a second between start of this test
    # and here
    assert is_same_time(t0, t1, tollerance=0.5)
    assert is_same_time(t1, t0, tollerance=0.5)
    # but must not be exactly the same unless we are way too fast or disregard
    # microseconds
    assert not is_same_time(t0, t1, tollerance=0)
    assert is_same_time(t0, t1_epoch + 100, tollerance=101)
