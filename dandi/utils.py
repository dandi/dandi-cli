import datetime
import itertools
import os
import os.path as op
import re
import sys
import platform

from pathlib import Path

#
# Additional handlers
#
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


def is_same_time(*times, tollerance=1e-6, strip_tzinfo=False):
    """Helper to do comparison between time points

    Time zone information gets stripped
    Does it by first normalizing all times to datetime, and then
    comparing to the first entry

    Parameters
    ----------
    tollerance: float, optional
      Seconds of difference between times to tollerate.  By default difference
      up to a microsecond is ok
    """
    assert len(times) >= 2

    norm_times = [
        ensure_datetime(t, strip_tzinfo=strip_tzinfo, tz=datetime.timezone.utc)
        for t in times
    ]

    # we need to have all pairs
    tollerance_dt = datetime.timedelta(seconds=tollerance)
    return all(
        # if we subtract from smaller - we get negative days etc
        (t1 - t2 if t1 > t2 else t2 - t1) <= tollerance_dt
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


def ensure_datetime(t, strip_tzinfo=False, tz=None):
    """Ensures that time is a datetime

    strip_tzinfo applies only to str records passed in

    epoch time assumed to be local (not utc)
    """
    t_orig = t
    if isinstance(t, datetime.datetime):
        pass
    elif isinstance(t, (int, float)):
        t = datetime.datetime.fromtimestamp(t).astimezone()
    elif isinstance(t, str):
        # could be in different formats, for now parse as ISO
        t = datetime.datetime.fromisoformat(t)
        if strip_tzinfo and t.tzinfo:
            # TODO: check a proper way to handle this so we could account
            # for a possibly present tz
            t = t.replace(tzinfo=None)
    else:
        raise TypeError(f"Do not know how to convert {t!r} to datetime")
    if tz:
        t = t.astimezone(tz=tz)
    return t


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
        paths = (op.join(dirpath, name) for name in names)
        for path in filter(re.compile(regex).search, paths):
            if not exclude_path(path):
                yield path


def find_dandi_files(paths):
    """Adapter to find_files to find files of interest to dandi project
    """
    yield from find_files("(dandiset\.yaml|\.nwb)$", paths)


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
