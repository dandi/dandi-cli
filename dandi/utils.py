import datetime
import os
import os.path as op
import re
import sys
import platform

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


def get_utcnow_datetime(microseconds=False):
    """Return current time as datetime with time zone information.

    Microseconds are stripped away.

    If string representation is desired, just "apply" .isoformat()
    """
    ret = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).astimezone()
    if microseconds:
        return ret
    else:
        return ret.replace(microsecond=0)


def is_same_time(*times):
    """Helper to do comparison between time points

    Time zone information gets stripped
    Does it by first normalizing all times to datetime, and then
    comparing to the first entry
    """
    assert len(times) >= 2
    norm_times = []
    for t in times:
        if isinstance(t, datetime.datetime):
            pass
        elif isinstance(t, (int, float)):
            t = datetime.datetime.utcfromtimestamp(t)
        elif isinstance(t, str):
            # could be in different formats, for now parse as ISO
            t = datetime.datetime.fromisoformat(t)
            if t.tzinfo:
                # TODO: check a proper way to handle this so we could account
                # for a possibly present tz
                t = t.replace(tzinfo=None)
        else:
            raise TypeError(f"Do not know how to work with {t!r}")
        norm_times.append(t)
    return all(t == norm_times[0] for t in norm_times[1:])


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
