import os
import os.path as op
import random
import sys
import time

from dandi.support.cache import PersistentCache

import pytest


# not doing random for now within fixtures, so they could share the same name
_cache_name = "test-%d" % random.randint(1, 1000)


@pytest.fixture(scope="function")
def cache():
    c = PersistentCache(name=_cache_name)
    yield c
    c.clear()


@pytest.fixture(scope="function")
def cache_tokens():
    # random so in case of parallel runs they do not "cross"
    c = PersistentCache(name=_cache_name, tokens=["0.0.1", 1])
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


def test_memoize_multiple(cache):

    # Make sure that with the same cache can cover multiple functions
    @cache.memoize
    def f1():
        return 1

    @cache.memoize
    def f2():
        return 2

    @cache.memoize
    def f3():  # nesting call into f2
        return f2() + 1

    for i in range(3):
        assert f1() == 1
        assert f2() == 2
        assert f3() == 3


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

    fname = "file.dat"
    path = str(tmp_path / fname)

    with pytest.raises(IOError):
        memoread(path, 0)
    # and again
    with pytest.raises(IOError):
        memoread(path, 0)
    assert len(calls) == 2

    with open(path, "w") as f:
        f.write("content")

    t0 = time.time()
    try:
        # unless this computer is too slow -- there should be less than
        # cache._min_dtime between our creating the file and testing,
        # so we would force a direct read:
        check_new_memoread(0, "content", True)
    except AssertionError:
        # if computer is indeed slow (happens on shared CIs) we might fail
        # because distance is too short
        if time.time() - t0 < cache._min_dtime:
            raise  # if we were quick but still failed -- legit
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

    # Check that symlinks should be dereferenced
    symlink1 = str(tmp_path / (fname + ".link1"))
    os.symlink(fname, symlink1)
    if op.islink(fname):  # hopefully would just skip Windows if not supported
        ncalls = len(calls)
        assert memoread(symlink1, 0) == "Content"
        assert len(calls) == ncalls  # no new call

    # and if we "clear", would it still work?
    cache.clear()
    check_new_memoread(1, "Content")


def test_memoize_path_persist():
    from subprocess import run, PIPE

    cache = PersistentCache(name=op.basename(__file__))
    cache.clear()

    outputs = [run([sys.executable, __file__], stdout=PIPE) for i in range(3)]
    assert outputs[0].stdout.strip().decode() == f"Running on {__file__}.DONE"
    for o in outputs[1:]:
        assert o.stdout.strip().decode() == f"DONE"

    cache.clear()


def test_memoize_path_tokens(tmp_path, cache, cache_tokens):
    calls = []

    @cache.memoize_path
    def memoread(path, arg, kwarg=None):
        calls.append(["cache", path, arg, kwarg])
        with open(path) as f:
            return f.read()

    @cache_tokens.memoize_path
    def memoread_tokens(path, arg, kwarg=None):
        calls.append(["cache_tokens", path, arg, kwarg])
        with open(path) as f:
            return f.read()

    def check_new_memoread(call, arg, content, expect_first=True, expect_new=False):
        ncalls = len(calls)
        assert call(path, arg) == content
        assert len(calls) == ncalls + int(expect_first)
        assert call(path, arg) == content
        assert len(calls) == ncalls + int(expect_first) + int(expect_new)

    path = str(tmp_path / "file.dat")

    with open(path, "w") as f:
        f.write("content")

    time.sleep(cache._min_dtime * 1.1)
    # They both are independent, so both will cause a new readout
    check_new_memoread(memoread, 0, "content")
    check_new_memoread(memoread_tokens, 0, "content")


if __name__ == "__main__":
    infile = __file__
    cache = PersistentCache(name=op.basename(infile))

    @cache.memoize_path
    def func(path):
        print(f"Running on {path}.", end="")
        return "DONE"

    print(func(infile))
