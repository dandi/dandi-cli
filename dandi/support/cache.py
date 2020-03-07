import appdirs
import joblib
import os
import os.path as op
from functools import wraps

from .. import get_logger

lgr = get_logger()


class PersistentCache(object):
    """Persistent cache providing @memoize and @memoize_path decorators
    """

    def __init__(self, name=None):
        dirs = appdirs.AppDirs("dandi")
        self._cache_file = op.join(dirs.user_cache_dir, (name or "cache") + ".dat")
        self._memory = joblib.Memory(self._cache_file, verbose=0)

    def clear(self):
        self._memory.clear(warn=False)
        # and completely destroy the directory
        try:
            os.rmdir(op.join(self._memory.location, "joblib"))
            os.rmdir(self._memory.location)
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
            return f(path, *args, **kwargs)

        @wraps(f)
        def fingerprinter(path, *args, **kwargs):
            fprint = self._get_file_fingerprint(path)
            if fprint is None:
                # just call the function -- we have no fingerprint,
                # probably does not exist or permissions are wrong
                return f(path, *args, **kwargs)
            else:
                # If there is a fingerprint -- inject it into the signature
                kwargs_ = kwargs.copy()
                kwargs_[fingerprint_kwarg] = fprint
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
            return s.st_ctime_ns, s.st_mtime_ns, s.st_size
        except Exception as exc:
            lgr.debug(f"Cannot fingerptint {path}: {exc}")
