import os.path as op
import random
import sys
import time

from dandi.support.cache import PersistentCache

import pytest


@pytest.fixture(scope="function")
def cache():
    # random so in case of parallel runs they do not "cross"
    c = PersistentCache(name="test-%d" % random.randint(1, 1000))
    yield c
    c.clear()


def test_memoize(cache):
    # Simplest testing to start with, not relying on persisting across
    # independent processes
    _comp = []

    @cache.memoize
    def f1(flag=False):
        if flag:
            raise ValueError("Got flag")
        if _comp:
            raise RuntimeError("Must not be recomputed")
        _comp.append(1)
        return 1

    assert f1() == 1
    assert f1() == 1

    # Now with some args
    _comp = []

    @cache.memoize
    def f2(*args):
        if args in _comp:
            raise RuntimeError("Must not be recomputed")
        _comp.append(args)
        return sum(args)

    assert f2(1) == 1
    assert f2(1) == 1
    assert f2(1, 2) == 3
    assert f2(1, 2) == 3
    assert _comp == [(1,), (1, 2)]


def test_memoize_path(cache, tmp_path):
    calls = []

    @cache.memoize_path
    def memoread(path, arg, kwarg=None):
        calls.append([path, arg, kwarg])
        with open(path) as f:
            return f.read()

    def check_new_memoread(arg, content, expect_new=False):
        ncalls = len(calls)
        assert memoread(path, arg) == content
        assert len(calls) == ncalls + 1
        assert memoread(path, arg) == content
        assert len(calls) == ncalls + 1 + int(expect_new)

    path = str(tmp_path / "file.dat")

    with pytest.raises(IOError):
        memoread(path, 0)
    # and again
    with pytest.raises(IOError):
        memoread(path, 0)
    assert len(calls) == 2

    with open(path, "w") as f:
        f.write("content")

    # unless this computer is too slow -- there should be less than
    # cache._min_dtime between our creating the file and testing,
    # so we would force a direct read:
    check_new_memoread(0, "content", True)
    assert calls[-1] == [path, 0, None]

    # but if we sleep - should memoize
    time.sleep(cache._min_dtime * 1.1)
    check_new_memoread(1, "content")

    # and if we modify the file -- a new read
    time.sleep(cache._min_dtime * 1.1)
    with open(path, "w") as f:
        f.write("Content")
    ncalls = len(calls)
    assert memoread(path, 1) == "Content"
    assert len(calls) == ncalls + 1

    time.sleep(cache._min_dtime * 1.1)
    check_new_memoread(0, "Content")

    # and if we "clear", would it still work?
    cache.clear()
    check_new_memoread(1, "Content")


def test_memoize_path_persist():
    from subprocess import run

    cache = PersistentCache(name=op.basename(__file__))
    cache.clear()

    outputs = [run([sys.executable, __file__], capture_output=True) for i in range(3)]
    assert outputs[0].stdout.strip().decode() == f"Running on {__file__}.DONE"
    for o in outputs[1:]:
        assert o.stdout.strip().decode() == f"DONE"

    cache.clear()


if __name__ == "__main__":
    infile = __file__
    cache = PersistentCache(name=op.basename(infile))

    @cache.memoize_path
    def func(path):
        print(f"Running on {path}.", end="")
        return "DONE"

    print(func(infile))
