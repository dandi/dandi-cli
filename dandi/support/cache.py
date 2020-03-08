import appdirs
import joblib
import os
import os.path as op
import time
from functools import wraps

from .. import get_logger

lgr = get_logger()


class PersistentCache(object):
    """Persistent cache providing @memoize and @memoize_path decorators
    """

    _min_dtime = 0.01  # min difference between now and mtime to consider
    # for caching

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
        self._cache_file = op.join(dirs.user_cache_dir, (name or "cache") + ".dat")
        self._memory = joblib.Memory(self._cache_file, verbose=0)
        self._tokens = tokens

    def clear(self):
        try:
            self._memory.clear(warn=False)
        except Exception as exc:
            lgr.debug("joblib failed to clear its cache: %s", exc)

        # and completely destroy the directory
        try:
            for d in (op.join(self._memory.location, "joblib"), self._memory.location):
                if op.exists(d):
                    os.rmdir(d)
        except Exception as exc:
            lgr.warning(f"Failed to clear out the cache directory: {exc}")

    def memoize(self, f):
        return self._memory.cache(f)

    def memoize_path(self, f):
        # we need to actually decorate a function
        fingerprint_kwarg = "_cache_fingerprint"

        @self.memoize
        def fingerprinted(path, *args, **kwargs):
            _ = kwargs.pop(fingerprint_kwarg)  # discard
            lgr.debug("Running original %s on %r", f, path)
            return f(path, *args, **kwargs)

        @wraps(f)
        def fingerprinter(path, *args, **kwargs):
            fprint = self._get_file_fingerprint(path)
            # We should still pass through if file was modified just now,
            # since that could mask out quick modifications.
            # Target use cases will not be like that.
            time_now = time.time()
            dtime = abs(time_now - fprint[0] * 1e-9) if fprint else None
            if fprint is None:
                lgr.debug("Calling %s directly since no fingerprint for %r", f, path)
                # just call the function -- we have no fingerprint,
                # probably does not exist or permissions are wrong
                return f(path, *args, **kwargs)
            elif dtime is not None and dtime < self._min_dtime:
                lgr.debug(
                    "Calling %s directly since too short (%f) for %r", f, dtime, path
                )
                return f(path, *args, **kwargs)
            else:
                lgr.debug("Calling memoized version of %s for %s", f, path)
                # If there is a fingerprint -- inject it into the signature
                kwargs_ = kwargs.copy()
                kwargs_[fingerprint_kwarg] = tuple(fprint) + (
                    tuple(self._tokens) if self._tokens else tuple()
                )
                return fingerprinted(path, *args, **kwargs_)

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
            return s.st_mtime_ns, s.st_ctime_ns, s.st_size
        except Exception as exc:
            lgr.debug(f"Cannot fingerptint {path}: {exc}")
