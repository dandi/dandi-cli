import inspect
import os.path as op

from ..utils import find_files, on_windows


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

    import pdb

    pdb.set_trace()
    pass
