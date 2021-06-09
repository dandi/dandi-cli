"""Various helpful iterators"""

from queue import Empty, Queue
from threading import Thread


class IteratorWithAggregation:
    """
    An iterable over an iterable which also makes an aggregate of the values available asap

    It iterates over the iterable in a separate thread.

    A use case is a generator which collects information about resources,
    which might be relatively fast but still take time.  While we are iterating over it,
    we could perform other operations on yielded records, but we would also like to have access to
    the "summary" object as soon as that iterator completes but while we might still be
    iterating over items in the outside loop.

    Use case: iterate over remote resource for downloads, and get "Total" size/number as
    soon as it becomes known inside the underlying iterator.

    TODO: probably could be more elegant etc if implemented via async/coroutines.

    Attributes
    ----------
    .total:
      Aggregated value as known to the moment. None if nothing was aggregated.
      It is a final value if `finished` is True.
    .finished: bool
      Set to True upon completion of iteration
    .exc: BaseException or None
      If not None -- the exception which was raised

    Example
    -------

    Very simplistic example, since typically (not range) it would be taking some time to
    iterate for the nested iteration::

        it = IteratorWithAggregation(range(3), lambda v, t=0: v+t)
        for v in it:
            print(it.total, it.finished, v)
            sleep(0.02)  # doing smth heavy, but we would know .total as soon as it is known

    would produce (so 3 is known right away, again since it is just range)

        3 True 0
        3 True 1
        3 True 2

    """

    def __init__(self, gen, agg, reraise_immediately=False):
        """

        Parameters
        ----------
        gen: iterable
          Generator (but could be any iterable, but it would not make much sense)
          to yield from
        agg: callable
          A callable with two args: new_value[, total=None] which should return adjusted
          total. Upon first iteration, no prior `total` is provided
        reraise_immediately: bool, optional
          If True, it would stop yielding values as soon as it detects that some
          exception has occurred (although there might still be values in the queue to be yielded
          which were collected before the exception was raised)
        """
        self.gen = gen
        self.agg = agg
        self.reraise_immediately = reraise_immediately

        self.total = None
        self.finished = None
        self._exc = None

    def __iter__(self):
        self.finished = False
        self._exc = None

        queue = Queue()

        def worker():
            """That is the one which interrogates gen and places total
            into queue_total upon completion"""
            total = None
            try:
                for value in self.gen:
                    queue.put(value)
                    self.total = total = (
                        self.agg(value, total) if total is not None else self.agg(value)
                    )
            except BaseException as e:  # lgtm [py/catch-base-exception]
                self._exc = e
            finally:
                self.finished = True

        t = Thread(target=worker)
        t.start()

        # yield from the queue (.total and .finished could be accessed meanwhile)
        while True:
            if self.reraise_immediately and self._exc is not None:
                break

            # race condition HERE between checking for self.finished and
            if self.finished and queue.empty():
                break
            # in general queue should not be empty, but if it is, e.g. due to race
            # condition with above check
            try:
                yield queue.get(timeout=0.001)
            except Empty:
                continue
        t.join()
        if self._exc is not None:
            raise self._exc  # lgtm [py/illegal-raise]
