from time import sleep

from ..iterators import IteratorWithAggregation

import pytest


def sleeping_range(n, secs=0.01, thr=None):
    """Fast generator"""
    for i in range(n):
        yield i
        sleep(secs)
        if thr and i >= thr:
            raise ValueError(i)


def test_IteratorWithAggregation():
    sumup = lambda v, t=0: v + t

    it = IteratorWithAggregation(sleeping_range(3, 0.0001), agg=sumup)
    # we should get our summary available after 2nd iteration and before it finishes
    for t, i in enumerate(it):
        sleep(0.01)  # 0.0003 should be sufficient but to deal with Windows failures,
        # making it longer
        assert t == i  # it is just a range after all
        if i:
            assert it.finished

    # If there is an exception thrown, it would be raised only by the end
    it = IteratorWithAggregation(sleeping_range(5, 0.0001, thr=2), agg=sumup)
    got = []
    with pytest.raises(ValueError):
        for i in it:
            got.append(i)
            sleep(0.001)
    assert got == [0, 1, 2]
    assert it.finished

    # If there is an exception thrown, it would be raised only by the end
    it = IteratorWithAggregation(
        sleeping_range(5, 0.0001, thr=2), agg=sumup, reraise_immediately=True
    )
    got = []
    with pytest.raises(ValueError):
        for i in it:
            got.append(i)
            # 0.005 should be more than enough, but Windows is still lagging
            sleep(0.02)
    assert got == [0]
    assert it.finished
