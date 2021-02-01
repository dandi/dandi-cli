import collections.abc
import queue
import threading


class generator_from_callback(collections.abc.Generator):
    """
    A generator wrapper for a function that invokes a callback multiple times.

    Calling `send` on the generator emits a value from one callback, and returns
    the next.

    Note this starts a background thread
    """

    def __init__(self, func):
        self._ready_queue = queue.Queue(1)
        self._done_queue = queue.Queue(1)
        self._done_holder = [False]

        # local to avoid reference cycles
        ready_queue = self._ready_queue
        done_queue = self._done_queue
        done_holder = self._done_holder

        def callback(value):
            done_queue.put((False, value))
            cmd, val = ready_queue.get()
            if cmd == "send":
                return val
            elif cmd == "throw":
                raise val
            else:
                assert False  # pragma: no cover

        def thread_func():
            while True:
                cmd, val = ready_queue.get()
                if cmd == "send" and val is not None:
                    done_queue.put(
                        (
                            True,
                            TypeError(
                                "can't send non-None value to a just-started generator"
                            ),
                        )
                    )
                    continue
                break
            try:
                if cmd == "throw":
                    raise val
                ret = func(callback)
                raise StopIteration(ret) if ret is not None else StopIteration
            except BaseException as e:
                done_holder[0] = True
                done_queue.put((True, e))

        self._thread = threading.Thread(target=thread_func)
        self._thread.start()

    def _put(self, *args):
        if self._done_holder[0]:
            raise StopIteration
        self._ready_queue.put(args)
        is_exception, val = self._done_queue.get()
        if is_exception:
            try:
                raise val
            finally:
                # prevent val's traceback containing a reference cycle
                del val
        else:
            return val

    def send(self, value):
        return self._put("send", value)

    def throw(self, exc):
        return self._put("throw", exc)

    def __next__(self):
        return self.send(None)

    def close(self):
        try:
            self.throw(GeneratorExit)
        except StopIteration:
            self._thread.join()
        except GeneratorExit:
            self._thread.join()
        except BaseException:
            self._thread.join()
            raise
        else:
            # yielded again, can't clean up the thread
            raise RuntimeError("Task with callback ignored GeneratorExit")

    def __del__(self):
        self.close()


class callback_from_generator(collections.abc.Callable):
    """
    Wraps a generator function into a function that emits items
    via callbacks instead
    """

    def __init__(self, generator_func):
        self._generator_func = generator_func

    def __call__(self, callback):
        g = self._generator_func()
        try:
            try:
                from_g = next(g)
            except StopIteration as si:
                return si.value
            # other exceptions propagate

            while True:
                try:
                    v_from_c = callback(from_g)
                except BaseException as e_from_c:
                    try:
                        from_g = g.throw(e_from_c)
                    except StopIteration as si:
                        return si.value
                else:
                    try:
                        from_g = g.send(v_from_c)
                    except StopIteration as si:
                        return si.value
        finally:
            g.close()
