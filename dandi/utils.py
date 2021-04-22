import datetime

try:
    from importlib.metadata import version as importlib_version
except ImportError:
    # TODO - remove whenever python >= 3.8
    from importlib_metadata import version as importlib_version
import inspect
import io
import itertools
import logging
import os
import os.path as op
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import types
from typing import Optional, Union

import dateutil.parser
import requests
import ruamel.yaml
from semantic_version import Version
import tenacity

from .consts import dandi_instance, known_instances, known_instances_rev
from .exceptions import BadCliVersionError, CliVersionTooOldError

#
# Additional handlers
#
from . import __version__, get_logger

lgr = get_logger()

_sys_excepthook = sys.excepthook  # Just in case we ever need original one

#
# Some useful variables
#
platform_system = platform.system().lower()
on_windows = platform_system == "windows"
on_osx = platform_system == "darwin"
on_linux = platform_system == "linux"
on_msys_tainted_paths = (
    on_windows
    and "MSYS_NO_PATHCONV" not in os.environ
    and os.environ.get("MSYSTEM", "")[:4] in ("MSYS", "MING")
)

USER_AGENT = "dandi/{} requests/{} {}/{}".format(
    __version__,
    requests.__version__,
    platform.python_implementation(),
    platform.python_version(),
)


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


def get_utcnow_datetime(microseconds=True):
    """Return current time as datetime with time zone information.

    Microseconds are stripped away.

    If string representation is desired, just "apply" .isoformat()
    """
    ret = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).astimezone()
    if microseconds:
        return ret
    else:
        return ret.replace(microsecond=0)


def is_same_time(*times, tolerance=1e-6, strip_tzinfo=False):
    """Helper to do comparison between time points

    Time zone information gets stripped
    Does it by first normalizing all times to datetime, and then
    comparing to the first entry

    Parameters
    ----------
    tolerance: float, optional
      Seconds of difference between times to tolerate.  By default difference
      up to a microsecond is ok
    """
    assert len(times) >= 2

    norm_times = [
        ensure_datetime(t, strip_tzinfo=strip_tzinfo, tz=datetime.timezone.utc)
        for t in times
    ]

    # we need to have all pairs
    tolerance_dt = datetime.timedelta(seconds=tolerance)
    return all(
        # if we subtract from smaller - we get negative days etc
        (t1 - t2 if t1 > t2 else t2 - t1) <= tolerance_dt
        for (t1, t2) in itertools.combinations(norm_times, 2)
    )


def ensure_strtime(t, isoformat=True):
    """Ensures that time is a string in iso format

    Note: if `t` is already a string, no conversion of any kind is done.

    epoch time assumed to be local (not utc)

    Parameters
    ----------
    isoformat: bool, optional
     If True, use .isoformat() and otherwise str().  With .isoformat() there
     is no space but T to separate date from time.
    """
    t_orig = t
    if isinstance(t, str):
        return t
    if isinstance(t, (int, float)):
        t = ensure_datetime(t)
    if isinstance(t, datetime.datetime):
        return t.isoformat() if isoformat else str(t)
    raise TypeError(f"Do not know how to convert {t_orig!r} to string datetime")


def fromisoformat(t):
    # datetime.fromisoformat "does not support parsing arbitrary ISO 8601
    # strings" <https://docs.python.org/3/library/datetime.html>.  In
    # particular, it does not parse the time zone suffixes recently
    # introduced into timestamps provided by the API.  Hence, we need to use
    # dateutil instead.
    return dateutil.parser.isoparse(t)


def ensure_datetime(t, strip_tzinfo=False, tz=None):
    """Ensures that time is a datetime

    strip_tzinfo applies only to str records passed in

    epoch time assumed to be local (not utc)
    """
    if isinstance(t, datetime.datetime):
        pass
    elif isinstance(t, (int, float)):
        t = datetime.datetime.fromtimestamp(t).astimezone()
    elif isinstance(t, str):
        # could be in different formats, for now parse as ISO
        t = fromisoformat(t)
        if strip_tzinfo and t.tzinfo:
            # TODO: check a proper way to handle this so we could account
            # for a possibly present tz
            t = t.replace(tzinfo=None)
    else:
        raise TypeError(f"Do not know how to convert {t!r} to datetime")
    if tz:
        t = t.astimezone(tz=tz)
    return t


#
# Generic
#
def flatten(it):
    """Yield items flattened if list, tuple or a generator"""
    for i in it:
        if isinstance(i, (list, tuple)) or inspect.isgenerator(i):
            yield from flattened(i)
        else:
            yield i


def flattened(it):
    """Return list with items flattened if list, tuple or a generator"""
    return list(flatten(it))


def updated(d, update):
    """Return a copy of the input with the 'update'

    Primarily for updating dictionaries
    """
    d = d.copy()
    d.update(update)
    return d


def remap_dict(rec, revmapping):
    """Remap nested dicts according to mapping

    Parameters
    ----------
    revmapping: dict
      (to, from)

    TODO: document and test more
    """
    out = {}

    def split(path):
        # map path from key.subkey if given in a string (not tuple) form
        return path.split(".") if isinstance(path, str) else path

    for to, from_ in revmapping.items():
        in_v = rec
        for p in split(from_):
            if p not in in_v:
                continue  # it is not there -- cannot map
            in_v = in_v[p]

        # and now set
        out_v = out
        t_split = split(to)
        for p in t_split[:-1]:
            out_v[p] = out_v.get(p, {})  # container for the next field
            out_v = out_v[p]
        out_v[t_split[-1]] = in_v  # and the last one gets the in_v
    return out


#
# Paths and files
#


def load_jsonl(filename):
    """Load json lines formatted file"""
    import json

    with open(filename, "r") as f:
        return list(map(json.loads, f))


_encoded_dirsep = r"\\" if on_windows else r"/"
_VCS_REGEX = r"%s\.(?:git|gitattributes|svn|bzr|hg)(?:%s|$)" % (
    _encoded_dirsep,
    _encoded_dirsep,
)
_DATALAD_REGEX = r"%s\.(?:datalad)(?:%s|$)" % (_encoded_dirsep, _encoded_dirsep)


def find_files(
    regex,
    paths=os.curdir,
    exclude=None,
    exclude_dotfiles=True,
    exclude_dotdirs=True,
    exclude_vcs=True,
    exclude_datalad=False,
    dirs=False,
):
    """Generator to find files matching regex

    Parameters
    ----------
    regex: basestring
      Regex to search target files. Is not applied to filter out directories
    paths: basestring or list, optional
      Directories or files to search among (directories are searched recursively)
    exclude: basestring, optional
      Matches to exclude
    exclude_vcs:
      If True, excludes commonly known VCS subdirectories.  If string, used
      as regex to exclude those files (regex: `%r`)
    exclude_dotdirs:
      If True, does not descend into directories starting with ".".
    exclude_datalad:
      If True, excludes files known to be datalad meta-data files (e.g. under
      .datalad/ subdirectory) (regex: `%r`)
    dirs: bool, optional
      Whether to match directories as well as files
    """

    def exclude_path(path):
        path = path.rstrip(op.sep)
        if exclude and re.search(exclude, path):
            return True
        if exclude_vcs and re.search(_VCS_REGEX, path):
            return True
        if exclude_datalad and re.search(_DATALAD_REGEX, path):
            return True
        return False

    def good_file(path):
        return re.search(regex, path) and not exclude_path(path)

    if isinstance(paths, (list, tuple, set)):
        for path in paths:
            if op.isdir(path):
                yield from find_files(
                    regex,
                    paths=path,
                    exclude=exclude,
                    exclude_dotfiles=exclude_dotfiles,
                    exclude_dotdirs=exclude_dotdirs,
                    exclude_vcs=exclude_vcs,
                    exclude_datalad=exclude_datalad,
                    dirs=dirs,
                )
            elif good_file(path):
                yield path
            else:
                # Provided path didn't match regex, thus excluded
                pass
        return
    elif op.isfile(paths):
        if good_file(paths):
            yield paths
        return

    for dirpath, dirnames, filenames in os.walk(paths):
        names = (dirnames + filenames) if dirs else filenames
        # TODO: might want to uniformize on windows to use '/'
        if exclude_dotfiles:
            names = (n for n in names if not n.startswith("."))
        if exclude_dotdirs:
            # and we should filter out directories from dirnames
            # Since we need to del which would change index, let's
            # start from the end
            for i in range(len(dirnames))[::-1]:
                if dirnames[i].startswith("."):
                    del dirnames[i]
        paths = (op.join(dirpath, name) for name in names)
        for path in filter(re.compile(regex).search, paths):
            if not exclude_path(path):
                yield path


_cp_supports_reflink = None


def copy_file(src, dst):
    """ Copy file from src to dst """
    global _cp_supports_reflink
    if _cp_supports_reflink is None:
        r = subprocess.run(
            ["cp", "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        # Ignore command failures (e.g., if cp doesn't support --help), as the
        # command will still likely output its usage info.
        _cp_supports_reflink = "--reflink" in r.stdout
    if _cp_supports_reflink:
        subprocess.run(
            ["cp", "-f", "--reflink=auto", "--", str(src), str(dst)], check=True
        )
    else:
        return shutil.copy2(src, dst)


def move_file(src, dst):
    """Move file from src to dst"""
    return shutil.move(src, dst)


def find_dandi_files(paths):
    """Adapter to find_files to find files of interest to dandi project"""
    sep = re.escape(os.sep)
    yield from find_files(rf"((^|{sep})dandiset\.yaml|\.nwb)\Z", paths)


def find_parent_directory_containing(filename, path=None):
    """Find a directory, on the path to 'path' containing filename

    if no 'path' - path from cwd
    Returns None if no such found, pathlib's Path to the directory if found
    """
    if not path:
        path = Path.cwd()
    else:  # assure pathlib object
        path = Path(path)

    while True:
        if (path / filename).exists():
            return path
        if path.parent == path:
            return None
        path = path.parent  # go up


def yaml_dump(rec):
    """Consistent dump into yaml

    Of primary importance is default_flow_style=False
    to assure proper formatting on versions of pyyaml before
    5.1: https://github.com/yaml/pyyaml/pull/256
    """
    yaml = ruamel.yaml.YAML(typ="safe")
    yaml.default_flow_style = False
    out = io.StringIO()
    yaml.dump(rec, out)
    return out.getvalue()


def yaml_load(f, typ=None):
    """
    Load YAML source from a file or string.

    Parameters
    ----------
    f: str or IO[str]
      The YAML source to load
    typ: str, optional
      The value of `typ` to pass to `ruamel.yaml.YAML`.  May be "rt" (default),
      "safe", "unsafe", or "base"

    Returns
    -------
    Any
      The parsed YAML value
    """
    return ruamel.yaml.YAML(typ=typ).load(f)


#
# Borrowed from DataLad (MIT license)
#


def with_pathsep(path):
    """Little helper to guarantee that path ends with /"""
    return path + op.sep if not path.endswith(op.sep) else path


def _get_normalized_paths(path, prefix):
    if op.isabs(path) != op.isabs(prefix):
        raise ValueError(
            "Both paths must either be absolute or relative. "
            "Got %r and %r" % (path, prefix)
        )
    path = with_pathsep(path)
    prefix = with_pathsep(prefix)
    return path, prefix


def path_startswith(path, prefix):
    """Return True if path starts with prefix path

    Parameters
    ----------
    path: str
    prefix: str
    """
    path, prefix = _get_normalized_paths(path, prefix)
    return path.startswith(prefix)


def path_is_subpath(path, prefix):
    """Return True if path is a subpath of prefix

    It will return False if path == prefix.

    Parameters
    ----------
    path: str
    prefix: str
    """
    path, prefix = _get_normalized_paths(path, prefix)
    return (len(prefix) < len(path)) and path.startswith(prefix)


def safe_call(func, path, default=None):
    try:
        return func(path)
    except Exception as exc:
        lgr.debug("Call to %s on %s failed: %s", func.__name__, path, exc)
        return default


def shortened_repr(value, length=30):
    try:
        if hasattr(value, "__repr__") and (value.__repr__ is not object.__repr__):
            value_repr = repr(value)
            if not value_repr.startswith("<") and len(value_repr) > length:
                value_repr = "<<%s++%d chars++%s>>" % (
                    value_repr[: length - 16],
                    len(value_repr) - (length - 16 + 4),
                    value_repr[-4:],
                )
            elif (
                value_repr.startswith("<")
                and value_repr.endswith(">")
                and " object at 0x"
            ):
                raise ValueError("I hate those useless long reprs")
        else:
            raise ValueError("gimme class")
    except Exception:
        value_repr = "<%s>" % value.__class__.__name__.split(".")[-1]
    return value_repr


def __auto_repr__(obj):
    attr_names = tuple()
    if hasattr(obj, "__dict__"):
        attr_names += tuple(obj.__dict__.keys())
    if hasattr(obj, "__slots__"):
        attr_names += tuple(obj.__slots__)

    items = []
    for attr in sorted(set(attr_names)):
        if attr.startswith("_"):
            continue
        value = getattr(obj, attr)
        # TODO:  should we add this feature to minimize some talktative reprs
        # such as of URL?
        # if value is None:
        #    continue
        items.append("%s=%s" % (attr, shortened_repr(value)))

    return "%s(%s)" % (obj.__class__.__name__, ", ".join(items))


def auto_repr(cls):
    """Decorator for a class to assign it an automagic quick and dirty __repr__

    It uses public class attributes to prepare repr of a class

    Original idea: http://stackoverflow.com/a/27799004/1265472
    """

    cls.__repr__ = __auto_repr__
    return cls


def Parallel(**kwargs):  # TODO: disable lint complaint
    """Adapter for joblib.Parallel so we could if desired, centralize control"""
    # ATM just a straight invocation
    import joblib

    return joblib.Parallel(**kwargs)


def delayed(*args, **kwargs):
    """Adapter for joblib.delayed so we could if desired, centralize control"""
    # ATM just a straight invocation
    import joblib

    return joblib.delayed(*args, **kwargs)


def get_instance(dandi_instance_id):
    if dandi_instance_id.lower().startswith(("http://", "https://")):
        redirector_url = dandi_instance_id
        dandi_id = known_instances_rev.get(redirector_url)
        if dandi_id is not None:
            instance = known_instances[dandi_id]
        else:
            instance = None
    else:
        instance = known_instances[dandi_instance_id]
        redirector_url = instance.redirector
        if redirector_url is None:
            return instance
    try:
        r = requests.get(redirector_url.rstrip("/") + "/server-info")
        r.raise_for_status()
    except Exception as e:
        lgr.warning("Request to %s failed (%s)", redirector_url, str(e))
        if instance is not None:
            lgr.warning("Using hard-coded URLs")
            return instance
        else:
            raise RuntimeError(
                f"Could not retrieve server info from {redirector_url},"
                " and client does not recognize URL"
            )
    server_info = r.json()
    try:
        minversion = Version(server_info["cli-minimal-version"])
        bad_versions = [Version(v) for v in server_info["cli-bad-versions"]]
    except ValueError as e:
        raise ValueError(
            f"{redirector_url} returned an incorrectly formatted version;"
            f" please contact that server's administrators: {e}"
        )
    our_version = Version(__version__)
    if our_version < minversion:
        raise CliVersionTooOldError(our_version, minversion, bad_versions)
    if our_version in bad_versions:
        raise BadCliVersionError(our_version, minversion, bad_versions)
    # note: service: url, not a full record
    services = {
        name: (rec or {}).get(
            "url"
        )  # note: somehow was ending up with {"girder": None}
        for name, rec in server_info.get("services", {}).items()
    }
    if services.get("girder"):
        return dandi_instance(
            metadata_version=0,
            girder=services.get("girder"),
            gui=services.get("webui"),
            redirector=redirector_url,
            api=None,
        )
    elif services.get("api"):
        return dandi_instance(
            metadata_version=1,
            girder=None,
            gui=services.get("webui"),
            redirector=redirector_url,
            api=services.get("api"),
        )
    else:
        raise RuntimeError(
            "redirector's server-info returned unknown set of services keys: "
            + ", ".join(
                k for k, v in server_info.get("services", {}).items() if v is not None
            )
        )


TITLE_CASE_LOWER = {
    "a",
    "an",
    "and",
    "as",
    "but",
    "by",
    "for",
    "in",
    "nor",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def name2title(name):
    # For use in autopopulating the titles of model schema fields
    words = []
    for w in split_camel_case(name):
        w = w.lower()
        if w == "id" or w == "url":
            w = w.upper()
        elif not words or w not in TITLE_CASE_LOWER:
            w = w.capitalize()
        words.append(w)
    return " ".join(words)


def split_camel_case(s):
    last_start = 0
    # Don't split apart "ID":
    for m in re.finditer(r"(?<=I)[A-CE-Z]|(?<=[^I])[A-Z]", s):
        yield s[last_start : m.start()]
        last_start = m.start()
    if last_start < len(s):
        yield s[last_start:]


def try_multiple(ntrials, retry, base):
    """
    ``try_multiple(ntrials, retry, base)(f, *args, **kwargs)`` calls ``f``
    multiple times until it succeeds, with exponentially increasing delay
    between calls
    """
    # `retry` must be an exception type, a tuple of exception types, or a valid
    # `retry` argument to tenacity.
    if isinstance(retry, (type, tuple)):
        retry = tenacity.retry_if_exception_type(retry)
    return tenacity.Retrying(
        wait=tenacity.wait_exponential(exp_base=base, multiplier=base),
        retry=retry,
        stop=tenacity.stop_after_attempt(ntrials),
        before_sleep=tenacity.before_sleep_log(lgr, logging.WARNING),
        reraise=True,
    )


def is_url(s):
    """Very primitive url detection for now

    TODO: redo
    """
    return s.lower().startswith(("http://", "https://", "dandi://"))


def get_module_version(module: Union[str, types.ModuleType]) -> Optional[str]:
    """Return version of the module

    Return module's `__version__` if present, or use importlib
    to get version.

    Returns
    -------
    object
    """
    if isinstance(module, str):
        mod_name = module
        module = sys.modules.get(module)
    else:
        mod_name = module.__name__.split(".", 1)[0]

    if module is not None:
        version = getattr(module, "__version__", None)
    else:
        version = None
    if version is None:
        # Let's use the standard Python mechanism if underlying module
        # did not provide __version__
        try:
            version = importlib_version(mod_name)
        except Exception as exc:
            lgr.debug("Failed to determine version of the %s: %s", mod_name, exc)
    return version
