import appdirs
import joblib
import os
import os.path as op
import shutil
import time
from functools import wraps

from .. import get_logger

lgr = get_logger()


class PersistentCache(object):
    """Persistent cache providing @memoize and @memoize_path decorators
    """

    _min_dtime = 0.01  # min difference between now and mtime to consider
    # for caching

    _cache_var_values = ("", "clear", "ignore")

    def __init__(self, name=None, tokens=None):
        """

        Parameters
        ----------
        name
        tokens: list of objects, optional
         To add to the fingerprint of @memoize_path (regular @memoize ATM does
         not use it).  Could be e.g. versions of relevant/used
         python modules (pynwb, etc)
        """
        dirs = appdirs.AppDirs("dandi")
        self._cache_file = op.join(dirs.user_cache_dir, (name or "cache"))
        self._memory = joblib.Memory(self._cache_file, verbose=0)
        cache_var = os.environ.get("DANDI_CACHE", "").lower()
        if cache_var not in self._cache_var_values:
            lgr.warning(
                f"DANDI_CACHE={cache_var} is not understood and thus ignored. "
                f"Known values are {self._cache_var_values}"
            )
        if cache_var == "clear":
            self.clear()
        self._ignore_cache = cache_var == "ignore"
        self._tokens = tokens

    def clear(self):
        try:
            self._memory.clear(warn=False)
        except Exception as exc:
            lgr.debug("joblib failed to clear its cache: %s", exc)

        # and completely destroy the directory
        try:
            if op.exists(self._memory.location):
                shutil.rmtree(self._memory.location)
        except Exception as exc:
            lgr.warning(f"Failed to clear out the cache directory: {exc}")

    def memoize(self, f):
        if self._ignore_cache:
            return f
        return self._memory.cache(f)

    def memoize_path(self, f):
        # we need to actually decorate a function
        fingerprint_kwarg = "_cache_fingerprint"

        @self.memoize
        @wraps(f)  # important, so .memoize correctly caches different `f`
        def fingerprinted(path, *args, **kwargs):
            _ = kwargs.pop(fingerprint_kwarg)  # discard
            lgr.debug("Running original %s on %r", f, path)
            return f(path, *args, **kwargs)

        @wraps(f)
        def fingerprinter(path, *args, **kwargs):
            # we need to dereference symlinks and use that path in the function
            # call signature
            path_orig = path
            path = op.realpath(path)
            if path != path_orig:
                lgr.log(5, "Dereferenced %r into %r", path_orig, path)
            fprint = None if op.isdir(path) else self._get_file_fingerprint(path)
            # We should still pass through if file was modified just now,
            # since that could mask out quick modifications.
            # Target use cases will not be like that.
            time_now = time.time()
            dtime = abs(time_now - fprint[0] * 1e-9) if fprint else None
            if fprint is None:
                lgr.debug("Calling %s directly since no fingerprint for %r", f, path)
                # just call the function -- we have no fingerprint,
                # probably does not exist or permissions are wrong
                ret = f(path, *args, **kwargs)
            elif dtime is not None and dtime < self._min_dtime:
                lgr.debug(
                    "Calling %s directly since too short (%f) for %r", f, dtime, path
                )
                ret = f(path, *args, **kwargs)
            else:
                lgr.debug("Calling memoized version of %s for %s", f, path)
                # If there is a fingerprint -- inject it into the signature
                kwargs_ = kwargs.copy()
                kwargs_[fingerprint_kwarg] = tuple(fprint) + (
                    tuple(self._tokens) if self._tokens else tuple()
                )
                ret = fingerprinted(path, *args, **kwargs_)
            lgr.log(1, "Returning value %r", ret)
            return ret

        # and we memoize actually that function
        return fingerprinter

    @staticmethod
    def _get_file_fingerprint(path):
        """Simplistic generic file fingerprinting based on ctime, mtime, and size
        """
        try:
            # we can't take everything, since atime can change, etc.
            # So let's take some
            s = os.stat(path, follow_symlinks=True)
            fprint = s.st_mtime_ns, s.st_ctime_ns, s.st_size
            lgr.log(5, "Fingerprint for %s: %s", path, fprint)
            return fprint
        except Exception as exc:
            lgr.debug(f"Cannot fingerprint {path}: {exc}")
