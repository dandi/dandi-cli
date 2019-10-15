import sys

#
# Additional handlers
#
_sys_excepthook = sys.excepthook  # Just in case we ever need original one


def is_interactive():
    """Return True if all in/outs are tty"""
    # TODO: check on windows if hasattr check would work correctly and add value:
    #
    return sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty()


def setup_exceptionhook(ipython=False):
    """Overloads default sys.excepthook with our exceptionhook handler.

       If interactive, our exceptionhook handler will invoke
       pdb.post_mortem; if not interactive, then invokes default handler.
    """

    def _pdb_excepthook(type, value, tb):
        import traceback

        traceback.print_exception(type, value, tb)
        print()
        if is_interactive():
            import pdb

            pdb.post_mortem(tb)

    if ipython:
        from IPython.core import ultratb

        sys.excepthook = ultratb.FormattedTB(
            mode="Verbose",
            # color_scheme='Linux',
            call_pdb=is_interactive(),
        )
    else:
        sys.excepthook = _pdb_excepthook


# Public domain.
def memoize(f):
    """
    Memoize function, clear cache on last return.
    """
    import pickle

    count = [0]
    cache = {}

    def g(*args, **kwargs):
        count[0] += 1
        try:
            try:
                if len(kwargs) != 0:
                    raise ValueError
                hash(args)
                key = (args,)
            except:
                key = pickle.dumps((args, kwargs))
            if key not in cache:
                cache[key] = f(*args, **kwargs)
            return cache[key]
        finally:
            count[0] -= 1
            if count[0] == 0:
                cache.clear()

    return g
