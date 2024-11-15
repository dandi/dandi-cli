from __future__ import annotations

from bisect import bisect
from collections.abc import Iterable, Iterator
import datetime
from functools import lru_cache
from importlib.metadata import version as importlib_version
import inspect
import io
import itertools
import json
from mimetypes import guess_type
import os
import os.path as op
from pathlib import Path, PurePath, PurePosixPath
import pdb
import platform
import re
import shutil
import subprocess
import sys
from time import sleep
import traceback
import types
from typing import IO, Any, List, Optional, Protocol, TypeVar, Union

import dateutil.parser
from multidict import MultiDict  # dependency of yarl
from pydantic import BaseModel, Field
import requests
import ruamel.yaml
from semantic_version import Version
from yarl import URL

from . import __version__, get_logger
from .consts import DandiInstance, known_instances, known_instances_rev
from .exceptions import BadCliVersionError, CliVersionTooOldError

AnyPath = Union[str, Path]


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


class Hasher(Protocol):
    def update(self, data: bytes) -> None:
        ...

    def hexdigest(self) -> str:
        ...


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
        exc_type: type[BaseException],
        value: BaseException,
        tb: types.TracebackType | None,
    ) -> None:
        traceback.print_exception(exc_type, value, tb)
        print()
        if is_interactive():
            pdb.post_mortem(tb)

    if ipython:
        from IPython.core import ultratb  # type: ignore[import]

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
    ret = datetime.datetime.now(datetime.timezone.utc).astimezone()
    if microseconds:
        return ret
    else:
        return ret.replace(microsecond=0)


def is_same_time(
    *times: datetime.datetime | int | float | str,
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
    t: str | int | float | datetime.datetime, isoformat: bool = True
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
    t: datetime.datetime | int | float | str,
    strip_tzinfo: bool = False,
    tz: datetime.tzinfo | None = None,
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


def load_jsonl(filename: AnyPath) -> list:
    """Load json lines formatted file"""
    with open(filename) as f:
        return list(map(json.loads, f))


_VCS_NAMES = {".git", ".gitattributes", ".svn", ".bzr", ".hg"}


def find_files(
    regex: str,
    paths: AnyPath | Iterable[AnyPath] = os.curdir,
    exclude: str | None = None,
    exclude_dotfiles: bool = True,
    exclude_dotdirs: bool = True,
    exclude_vcs: bool = True,
    exclude_datalad: bool = False,
    dirs: bool = False,
    dirs_avoid: str | None = None,
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
        parts = Path(path).parts
        if exclude_vcs and any(p in _VCS_NAMES for p in parts):
            return True
        if exclude_datalad and any(p == ".datalad" for p in parts):
            return True
        return False

    def good_file(path: str) -> bool:
        return bool(re.search(regex, path)) and not exclude_path(path)

    if not isinstance(paths, (str, Path)):
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


def list_paths(
    dirpath: AnyPath, dirs: bool = False, exclude_vcs: bool = True
) -> list[Path]:
    return sorted(
        map(
            Path,
            find_files(
                r".*",
                [dirpath],
                dirs=dirs,
                exclude_dotfiles=False,
                exclude_dotdirs=False,
                exclude_vcs=exclude_vcs,
            ),
        )
    )


_cp_supports_reflink: bool | None = False if on_windows else None


def copy_file(src: AnyPath, dst: AnyPath) -> None:
    """Copy file from src to dst"""
    global _cp_supports_reflink
    if _cp_supports_reflink is None:
        r = subprocess.run(
            ["cp", "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
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


def move_file(src: AnyPath, dst: AnyPath) -> Any:
    """Move file from src to dst"""
    return shutil.move(str(src), str(dst))


def find_parent_directory_containing(
    filename: AnyPath, path: AnyPath | None = None
) -> Path | None:
    """Find a directory, on the path to 'path' containing filename

    if no 'path' - path from cwd. If 'path' is not absolute, absolute path
    is taken assuming relative to cwd.

    Returns None if no such found, pathlib's Path (absolute) to the directory
    if found.
    """
    if not path:
        path = Path.cwd()
    else:  # assure pathlib object
        path = Path(path)

    if not path.is_absolute():
        path = path.absolute()

    while True:
        if op.lexists(path / filename):
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


def yaml_load(f: str | IO[str], typ: str | None = None) -> Any:
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


def _get_normalized_paths(path: str, prefix: str) -> tuple[str, str]:
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


class ServiceURL(BaseModel):
    # Don't use pydantic.AnyHttpUrl, as that adds a trailing slash, and so URLs
    # retrieved for known instances won't match the known values
    url: str


class ServerServices(BaseModel):
    api: ServiceURL
    webui: Optional[ServiceURL] = None
    jupyterhub: Optional[ServiceURL] = None


class ServerInfo(BaseModel):
    # schema_version: str
    # schema_url: str
    version: str
    services: ServerServices
    cli_minimal_version: str = Field(alias="cli-minimal-version")
    cli_bad_versions: List[str] = Field(alias="cli-bad-versions")


def get_instance(dandi_instance_id: str | DandiInstance) -> DandiInstance:
    dandi_id = None
    is_api = True
    redirector_url = None
    if isinstance(dandi_instance_id, DandiInstance):
        instance = dandi_instance_id
        dandi_id = instance.name
    elif dandi_instance_id.lower().startswith(("http://", "https://")):
        redirector_url = dandi_instance_id.rstrip("/")
        dandi_id = known_instances_rev.get(redirector_url)
        if dandi_id is not None:
            instance = known_instances[dandi_id]
            is_api = instance.api.rstrip("/") == redirector_url
        else:
            instance = None
            is_api = False
            redirector_url = str(
                URL(redirector_url).with_path("").with_query(None).with_fragment(None)
            )
    else:
        dandi_id = dandi_instance_id
        instance = known_instances[dandi_id]
    if redirector_url is None:
        assert instance is not None
        return _get_instance(instance.api.rstrip("/"), True, instance, dandi_id)
    else:
        return _get_instance(redirector_url, is_api, instance, dandi_id)


@lru_cache
def _get_instance(
    url: str, is_api: bool, instance: DandiInstance | None, dandi_id: str | None
) -> DandiInstance:
    try:
        if is_api:
            r = requests.get(joinurl(url, "/info/"))
        else:
            r = requests.get(joinurl(url, "/server-info"))
            if r.status_code == 404:
                r = requests.get(joinurl(url, "/api/info/"))
        r.raise_for_status()
        server_info = ServerInfo.model_validate(r.json())
    except Exception as e:
        lgr.warning("Request to %s failed (%s)", url, str(e))
        if instance is not None:
            lgr.warning("Using hard-coded URLs")
            return instance
        else:
            raise RuntimeError(
                f"Could not retrieve server info from {url},"
                " and client does not recognize URL"
            )
    try:
        minversion = Version(server_info.cli_minimal_version)
        bad_versions = [Version(v) for v in server_info.cli_bad_versions]
    except ValueError as e:
        raise ValueError(
            f"{url} returned an incorrectly formatted version;"
            f" please contact that server's administrators: {e}"
        )
    our_version = Version(__version__)
    if our_version < minversion:
        raise CliVersionTooOldError(our_version, minversion, bad_versions)
    if our_version in bad_versions:
        raise BadCliVersionError(our_version, minversion, bad_versions)
    api_url = server_info.services.api.url
    if dandi_id is None:
        # Don't use pydantic.AnyHttpUrl, as that sets the `port` attribute even
        # if it's not present in the string.
        u = URL(api_url)
        if u.host is not None:
            dandi_id = u.host
            if (port := u.explicit_port) is not None:
                if ":" in dandi_id:
                    dandi_id = f"[{dandi_id}]"
                dandi_id += f":{port}"
        else:
            dandi_id = api_url
    return DandiInstance(
        name=dandi_id,
        gui=(
            server_info.services.webui.url
            if server_info.services.webui is not None
            else None
        ),
        api=api_url,
    )


def is_url(s: str) -> bool:
    """Very primitive url detection for now

    TODO: redo
    """
    return s.lower().startswith(("http://", "https://", "dandi:", "ftp://"))
    # Slashes are not required after "dandi:" so as to support "DANDI:<id>"


def get_module_version(module: str | types.ModuleType) -> str | None:
    """Return version of the module

    Return module's `__version__` if present, or use importlib
    to get version.

    Returns
    -------
    object
    """
    modobj: types.ModuleType | None
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


def pluralize(n: int, word: str, plural: str | None = None) -> str:
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


def chunked(iterable: Iterable[T], size: int) -> Iterator[list[T]]:
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
    url1 = URL(page1)
    params1 = MultiDict(url1.query)
    params1["page"] = "2"
    url1 = url1.with_query(None)
    url2 = URL(page2)
    params2 = url2.query
    url2 = url2.with_query(None)
    return (url1, sorted(params1.items())) == (url2, sorted(params2.items()))


def exclude_from_zarr(path: Path) -> bool:
    """
    Returns `True` if the ``path`` is a file or directory that should be
    excluded from consideration when located in a Zarr
    """
    return path.name in (".dandi", ".datalad", ".git", ".gitattributes", ".gitmodules")


def under_paths(
    paths: Iterable[str | PurePath], filter_paths: Iterable[str | PurePath]
) -> Iterator[PurePosixPath]:
    """
    Return all elements of ``paths`` (converted to `PurePosixPath` instances)
    that are equal to or under/start with one or more paths in
    ``filter_paths``.  The elements of both iterables must be relative &
    normalized.

    Based on ``get_filtered_paths_`` from datalad's
    :file:`datalad/support/path.py`
    """
    path_parts = _prepare_path_parts(paths)
    filter_path_parts = _prepare_path_parts(filter_paths)
    for path in path_parts:
        i = bisect(filter_path_parts, path)
        if i > 0 and _starts_with(path, filter_path_parts[i - 1]):
            yield PurePosixPath(*path)
        elif i == len(filter_path_parts):
            break


def _prepare_path_parts(paths: Iterable[str | PurePath]) -> list[tuple[str, ...]]:
    path_parts: list[tuple[str, ...]] = []
    for p in paths:
        pp = PurePosixPath(p)
        if pp.is_absolute():
            raise ValueError(f"Absolute path: {p!r}")
        parts = pp.parts
        if ".." in parts or "." in parts:
            raise ValueError(f"Non-normalized path: {p!r}")
        path_parts.append(parts)
    path_parts.sort()
    return path_parts


def _starts_with(t: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    return t[: len(prefix)] == prefix


def pre_upload_size_check(path: Path) -> int:
    # If the filesystem reports a size of zero for a file we're about to
    # upload, double-check the size in case we're on a flaky NFS system.
    for naptime in [0] + [0.1] * 19:
        sleep(naptime)
        size = path.stat().st_size
        if size != 0:
            return size
    return size


def post_upload_size_check(path: Path, pre_check_size: int, erroring: bool) -> None:
    # More checks for NFS flakiness
    size = path.stat().st_size
    if size != pre_check_size:
        msg = (
            f"Size of {path} was {pre_check_size} at start of upload but is"
            f" now {size} after upload"
        )
        if erroring:
            lgr.error(msg)
        else:
            raise RuntimeError(msg)


def joinurl(base: str, path: str) -> str:
    """
    Append a slash-separated ``path`` to a base HTTP(S) URL ``base``.  The two
    components are separated by a single slash, removing any excess slashes
    that would be present after naïve concatenation.

    If ``path`` is already an absolute HTTP(S) URL, it is returned unchanged.

    Note that this function differs from `urllib.parse.urljoin()` when the path
    portion of ``base`` is nonempty and does not end in a slash.
    """
    if path.lower().startswith(("http://", "https://")):
        return path
    else:
        return base.rstrip("/") + "/" + path.lstrip("/")
