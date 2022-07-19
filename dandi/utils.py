import datetime
import inspect
import io
import itertools
from mimetypes import guess_type
import os
import os.path as op
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import types
from typing import (
    Any,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    TextIO,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from urllib.parse import parse_qs, urlparse

import dateutil.parser
import requests
import ruamel.yaml
from semantic_version import Version

from . import __version__, get_logger
from .consts import DandiInstance, known_instances, known_instances_rev
from .exceptions import BadCliVersionError, CliVersionTooOldError

if sys.version_info >= (3, 8):
    from importlib.metadata import version as importlib_version
else:
    from importlib_metadata import version as importlib_version

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


def is_interactive() -> bool:
    """Return True if all in/outs are tty"""
    # TODO: check on windows if hasattr check would work correctly and add value:
    #
    return sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty()


def setup_exceptionhook(ipython: bool = False) -> None:
    """Overloads default sys.excepthook with our exceptionhook handler.

    If interactive, our exceptionhook handler will invoke
    pdb.post_mortem; if not interactive, then invokes default handler.
    """

    def _pdb_excepthook(
        type: Type[BaseException],
        value: BaseException,
        tb: Optional[types.TracebackType],
    ) -> None:
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


def get_utcnow_datetime(microseconds: bool = True) -> datetime.datetime:
    """Return current time as datetime with time zone information.

    Microseconds are stripped away.

    If string representation is desired, just "apply" .isoformat()
    """
    ret = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).astimezone()
    if microseconds:
        return ret
    else:
        return ret.replace(microsecond=0)


def is_same_time(
    *times: Union[datetime.datetime, int, float, str],
    tolerance: float = 1e-6,
    strip_tzinfo: bool = False,
) -> bool:
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


def ensure_strtime(
    t: Union[str, int, float, datetime.datetime], isoformat: bool = True
) -> str:
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


def fromisoformat(t: str) -> datetime.datetime:
    # datetime.fromisoformat "does not support parsing arbitrary ISO 8601
    # strings" <https://docs.python.org/3/library/datetime.html>.  In
    # particular, it does not parse the time zone suffixes recently
    # introduced into timestamps provided by the API.  Hence, we need to use
    # dateutil instead.
    return dateutil.parser.isoparse(t)


def ensure_datetime(
    t: Union[datetime.datetime, int, float, str],
    strip_tzinfo: bool = False,
    tz: Optional[datetime.tzinfo] = None,
) -> datetime.datetime:
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
def flatten(it: Iterable) -> Iterator:
    """Yield items flattened if list, tuple or a generator"""
    for i in it:
        if isinstance(i, (list, tuple)) or inspect.isgenerator(i):
            yield from flattened(i)
        else:
            yield i


def flattened(it: Iterable) -> list:
    """Return list with items flattened if list, tuple or a generator"""
    return list(flatten(it))


#
# Paths and files
#


def load_jsonl(filename: Union[str, Path]) -> list:
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


AnyPath = Union[str, Path]


def find_files(
    regex: str,
    paths: Union[List[AnyPath], Tuple[AnyPath, ...], Set[AnyPath], AnyPath] = os.curdir,
    exclude: Optional[str] = None,
    exclude_dotfiles: bool = True,
    exclude_dotdirs: bool = True,
    exclude_vcs: bool = True,
    exclude_datalad: bool = False,
    dirs: bool = False,
    dirs_avoid: Optional[str] = None,
) -> Iterator[str]:
    """Generator to find files matching regex

    Parameters
    ----------
    regex: string
      Regex to search target files. Is not applied to filter out directories
    paths: string or list, optional
      Directories or files to search among (directories are searched recursively)
    exclude: string, optional
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
    dirs_avoid: string, optional
      Regex for directories to not rercurse under (they might still be reported
      if `dirs=True`)
    """

    def exclude_path(path: str) -> bool:
        path = path.rstrip(op.sep)
        if exclude and re.search(exclude, path):
            return True
        if exclude_vcs and re.search(_VCS_REGEX, path):
            return True
        if exclude_datalad and re.search(_DATALAD_REGEX, path):
            return True
        return False

    def good_file(path: str) -> bool:
        return bool(re.search(regex, path)) and not exclude_path(path)

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
                    dirs_avoid=dirs_avoid,
                )
            elif good_file(str(path)):
                yield str(path)
            else:
                # Provided path didn't match regex, thus excluded
                pass
        return
    elif op.isfile(paths):
        if good_file(str(paths)):
            yield str(paths)
        return

    for dirpath, dirnames, filenames in os.walk(paths):
        names = (dirnames + filenames) if dirs else filenames
        # TODO: might want to uniformize on windows to use '/'
        if exclude_dotfiles:
            names = [n for n in names if not n.startswith(".")]
        if exclude_dotdirs or dirs_avoid:
            # and we should filter out directories from dirnames
            # Since we need to del which would change index, let's
            # start from the end
            for i in range(len(dirnames))[::-1]:
                if (exclude_dotdirs and dirnames[i].startswith(".")) or (
                    dirs_avoid and re.search(dirs_avoid, dirnames[i])
                ):
                    del dirnames[i]
        strpaths = [op.join(dirpath, name) for name in names]
        for p in filter(re.compile(regex).search, strpaths):
            if not exclude_path(p):
                if op.islink(p) and op.isdir(p):
                    lgr.warning(
                        "%s: Ignoring unsupported symbolic link to directory", path
                    )
                else:
                    yield p


def list_paths(dirpath: Union[str, Path], dirs: bool = False) -> List[Path]:
    return sorted(map(Path, find_files(r".*", [dirpath], dirs=dirs)))


_cp_supports_reflink: Optional[bool] = None


def copy_file(src: Union[str, Path], dst: Union[str, Path]) -> None:
    """Copy file from src to dst"""
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
        shutil.copy2(src, dst)


def move_file(src: Union[str, Path], dst: Union[str, Path]) -> Any:
    """Move file from src to dst"""
    return shutil.move(str(src), str(dst))


def find_parent_directory_containing(
    filename: Union[str, Path], path: Union[str, Path, None] = None
) -> Optional[Path]:
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


def yaml_dump(rec: Any) -> str:
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


def yaml_load(f: Union[str, TextIO], typ: Optional[str] = None) -> Any:
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


def with_pathsep(path: str) -> str:
    """Little helper to guarantee that path ends with /"""
    return path + op.sep if not path.endswith(op.sep) else path


def _get_normalized_paths(path: str, prefix: str) -> Tuple[str, str]:
    if op.isabs(path) != op.isabs(prefix):
        raise ValueError(
            "Both paths must either be absolute or relative. "
            "Got %r and %r" % (path, prefix)
        )
    path = with_pathsep(path)
    prefix = with_pathsep(prefix)
    return path, prefix


def path_is_subpath(path: str, prefix: str) -> bool:
    """Return True if path is a subpath of prefix

    It will return False if path == prefix.

    Parameters
    ----------
    path: str
    prefix: str
    """
    path, prefix = _get_normalized_paths(path, prefix)
    return (len(prefix) < len(path)) and path.startswith(prefix)


def shortened_repr(value: Any, length: int = 30) -> str:
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


def __auto_repr__(obj: Any) -> str:
    attr_names: Tuple[str, ...] = ()
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


TT = TypeVar("TT", bound=type)


def auto_repr(cls: TT) -> TT:
    """Decorator for a class to assign it an automagic quick and dirty __repr__

    It uses public class attributes to prepare repr of a class

    Original idea: http://stackoverflow.com/a/27799004/1265472
    """

    cls.__repr__ = __auto_repr__  # type: ignore[assignment]
    return cls


def Parallel(**kwargs: Any) -> Any:  # TODO: disable lint complaint
    """Adapter for joblib.Parallel so we could if desired, centralize control"""
    # ATM just a straight invocation
    import joblib

    return joblib.Parallel(**kwargs)


def delayed(*args, **kwargs):
    """Adapter for joblib.delayed so we could if desired, centralize control"""
    # ATM just a straight invocation
    import joblib

    return joblib.delayed(*args, **kwargs)


def get_instance(dandi_instance_id: str) -> DandiInstance:
    if dandi_instance_id.lower().startswith(("http://", "https://")):
        redirector_url = dandi_instance_id
        dandi_id = known_instances_rev.get(redirector_url)
        if dandi_id is not None:
            instance = known_instances[dandi_id]
        else:
            instance = None
    else:
        instance = known_instances[dandi_instance_id]
        if instance.redirector is None:
            return instance
        else:
            redirector_url = instance.redirector
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
    for k, v in list(services.items()):
        if v is not None:
            services[k] = v.rstrip("/")
    if services.get("api"):
        return DandiInstance(
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


def is_url(s: str) -> bool:
    """Very primitive url detection for now

    TODO: redo
    """
    return s.lower().startswith(("http://", "https://", "dandi:", "ftp://"))
    # Slashes are not required after "dandi:" so as to support "DANDI:<id>"


def get_module_version(module: Union[str, types.ModuleType]) -> Optional[str]:
    """Return version of the module

    Return module's `__version__` if present, or use importlib
    to get version.

    Returns
    -------
    object
    """
    modobj: Optional[types.ModuleType]
    if isinstance(module, str):
        modobj = sys.modules.get(module)
        mod_name = module
    else:
        modobj = module
        mod_name = module.__name__.split(".", 1)[0]

    if modobj is not None:
        version = getattr(modobj, "__version__", None)
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


def pluralize(n: int, word: str, plural: Optional[str] = None) -> str:
    if n == 1:
        return f"{n} {word}"
    else:
        if plural is None:
            plural = word + "s"
        return f"{n} {plural}"


def abbrev_prompt(msg: str, *options: str) -> str:
    """
    Prompt the user to input one of several options, which can be entered as
    either a whole word or the first letter of a word.  All input is handled
    case-insensitively.  Returns the complete word corresponding to the input,
    lowercased.

    For example, ``abbrev_prompt("Delete assets?", "yes", "no", "list")``
    prompts the user with the message ``Delete assets? ([y]es/[n]o/[l]ist): ``
    and accepts as input ``y`, ``yes``, ``n``, ``no``, ``l``, and ``list``.
    """
    options_map = {}
    optstrs = []
    for opt in options:
        opt = opt.lower()
        if opt in options_map:
            raise ValueError(f"Repeated option: {opt}")
        elif opt[0] in options_map:
            raise ValueError(f"Repeated abbreviated option: {opt[0]}")
        options_map[opt] = opt
        options_map[opt[0]] = opt
        optstrs.append(f"[{opt[0]}]{opt[1:]}")
    msg += " (" + "/".join(optstrs) + "): "
    while True:
        answer = input(msg).lower()
        if answer in options_map:
            return options_map[answer]


def get_mime_type(filename: str, strict: bool = False) -> str:
    """
    Like `mimetypes.guess_type()`, except that if the file is compressed, the
    MIME type for the compression is returned.  Also, the default return value
    is now ``'application/octet-stream'`` instead of `None`.
    """
    mtype, encoding = guess_type(filename, strict)
    if encoding is None:
        return mtype or "application/octet-stream"
    elif encoding == "gzip":
        # application/gzip is defined by RFC 6713
        return "application/gzip"
        # There is also a "+gzip" MIME structured syntax suffix defined by RFC
        # 8460; exactly when can that be used?
        # return mtype + '+gzip'
    else:
        return "application/x-" + encoding


def check_dandi_version() -> None:
    if os.environ.get("DANDI_NO_ET"):
        return
    try:
        import etelemetry

        try:
            etelemetry.check_available_version(
                "dandi/dandi-cli", __version__, lgr=lgr, raise_exception=True
            )
        except etelemetry.client.BadVersionError:
            # note: SystemExit is based of BaseException, so is not Exception
            raise SystemExit(
                "DANDI CLI has detected that you are using a version that is known to "
                "contain bugs, is incompatible with our current data archive, or has "
                "other significant performance limitations. "
                "To continue using DANDI CLI, please upgrade your dandi client to a newer "
                "version (e.g., using pip install --upgrade dandi if you installed using pip). "
                "If you have any issues, please contact the DANDI "
                "helpdesk at https://github.com/dandi/helpdesk/issues/new/choose ."
            )
    except Exception as exc:
        lgr.warning(
            "Failed to check for a more recent version available with etelemetry: %s",
            exc,
        )
    os.environ["DANDI_NO_ET"] = "1"


T = TypeVar("T")


def chunked(iterable: Iterable[T], size: int) -> Iterator[List[T]]:
    # cf. chunked() from more-itertools
    i = iter(iterable)
    while True:
        xs = []
        for _ in range(size):
            try:
                xs.append(next(i))
            except StopIteration:
                if xs:
                    break
                else:
                    return
        yield xs


def is_page2_url(page1: str, page2: str) -> bool:
    """
    Tests whether the URL ``page2`` is the same as ``page1`` but with the
    ``page`` query parameter set to ``2``
    """
    bits1 = urlparse(page1)
    params1 = parse_qs(bits1.query)
    params1["page"] = ["2"]
    bits2 = urlparse(page2)
    params2 = parse_qs(bits2.query)
    return (bits1[:3], params1, bits1.fragment) == (bits2[:3], params2, bits2.fragment)
