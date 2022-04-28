from time import sleep

import pytest

from ..iterators import IteratorWithAggregation


def sleeping_range(n, secs=0.01, thr=None):
    """Fast generator based on range

    Parameters
    ----------
    n : int
      Number to pass to `range`
    secs : float, optional
      Seconds to sleep between iterations
    thr : int, optional
      If specified, will cause loop to raise ValueError when it
      reaches that value

    Yields
    ------
    int
      Integers like range does

    """
    for i in range(n):
        yield i
        sleep(secs)
        if thr and i >= thr:
            raise ValueError(i)


def test_IteratorWithAggregation():
    def sumup(v, t=0):
        return v + t

    it = IteratorWithAggregation(sleeping_range(3, 0.0001), agg=sumup)
    # we should get our summary available after 2nd iteration and before it finishes
    slow_machine = False
    for t, i in enumerate(it):
        sleep(0.005)  # 0.0003 should be sufficient but to deal with Windows failures,
        # making it longer
        assert t == i  # it is just a range after all
        if i:
            if not it.finished:
                # give considerably more time for poor Windows VM
                slow_machine = True
                sleep(0.1)
            assert it.finished

    # If there is an exception thrown, it would be raised only by the end
    it = IteratorWithAggregation(sleeping_range(5, 0.0001, thr=2), agg=sumup)
    got = []
    with pytest.raises(ValueError):
        for i in it:
            got.append(i)
            sleep(0.001 if not slow_machine else 0.1)
    assert got == [0, 1, 2]
    assert it.finished

    # If there is an exception thrown, it would be raised immediately
    it = IteratorWithAggregation(
        sleeping_range(5, 0.0001, thr=2), agg=sumup, reraise_immediately=True
    )
    got = []
    with pytest.raises(ValueError):
        for i in it:
            got.append(i)
            # sleep long enough to trigger exception before next iteration
            sleep(0.02 if not slow_machine else 0.1)
    assert got in ([], [0])
    assert it.finished
