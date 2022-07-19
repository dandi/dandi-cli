import inspect
import os
import os.path as op
from pathlib import Path
import time
from typing import Iterable, List

import pytest
import requests
import responses
from semantic_version import Version

from .skip import mark
from .. import __version__
from ..consts import DandiInstance, known_instances
from ..exceptions import BadCliVersionError, CliVersionTooOldError
from ..utils import (
    ensure_datetime,
    ensure_strtime,
    find_files,
    flatten,
    flattened,
    get_instance,
    get_mime_type,
    get_module_version,
    get_utcnow_datetime,
    is_page2_url,
    is_same_time,
    on_windows,
)


def test_find_files() -> None:
    tests_dir = op.dirname(__file__)
    proj_dir = op.normpath(op.join(op.dirname(__file__), op.pardir))

    ff = find_files(".*", proj_dir)
    assert inspect.isgenerator(ff)
    files = list(ff)
    assert len(files) > 3  # we have more than 3 test files here
    assert op.join(tests_dir, "test_utils.py") in files
    # and no directories should be mentioned
    assert tests_dir not in files

    ff2 = find_files(".*", proj_dir, dirs=True)
    files2 = list(ff2)
    assert op.join(tests_dir, "test_utils.py") in files2
    assert tests_dir in files2

    # now actually matching the path
    ff3 = find_files(
        r".*\\test_.*\.py$" if on_windows else r".*/test_.*\.py$", proj_dir, dirs=True
    )
    files3 = list(ff3)
    assert op.join(tests_dir, "test_utils.py") in files3
    assert tests_dir not in files3
    for f in files3:
        assert op.basename(f).startswith("test_")

    # TODO: more tests


def test_find_files_dotfiles(tmp_path: Path) -> None:
    tmpsubdir = tmp_path / "subdir"
    tmpsubdir.mkdir()
    for p in (".dot.nwb", "regular"):
        for f in (tmp_path / p, tmpsubdir / p):
            f.touch()
    (tmp_path / ".git").mkdir()  # a "proper" .git/ directory
    (tmp_path / ".git" / "config").touch()
    (tmpsubdir / ".git").touch()  # a ".git" link file

    def relpaths(paths: Iterable[str]) -> List[str]:
        return sorted(op.relpath(p, tmp_path) for p in paths)

    regular = ["regular", op.join("subdir", "regular")]
    dotfiles = [".dot.nwb", op.join("subdir", ".dot.nwb")]
    vcs = [".git", op.join(".git", "config"), op.join("subdir", ".git")]

    ff = find_files(".*", tmp_path)
    assert relpaths(ff) == regular

    ff = find_files(".*", tmp_path, exclude_dotfiles=False)
    # we still exclude VCS
    assert relpaths(ff) == sorted(regular + dotfiles)

    # current VCS are also dot files
    ff = find_files(".*", tmp_path, exclude_vcs=False)
    assert relpaths(ff) == regular

    # one VCS file is also a dot file
    ff = find_files(".*", tmp_path, exclude_vcs=False, exclude_dotfiles=False)
    assert relpaths(ff) == sorted(regular + dotfiles + [op.join("subdir", ".git")])

    # with dirs=True we should match all VCS
    ff = find_files(
        ".*",
        tmp_path,
        exclude_vcs=False,
        exclude_dotfiles=False,
        exclude_dotdirs=False,
        dirs=True,
    )
    assert relpaths(ff) == sorted(regular + dotfiles + vcs + ["subdir"])

    # and we can filter .git directories and their content using dirs_avoid
    ff = find_files(
        ".*",
        tmp_path,
        exclude_vcs=False,
        exclude_dotfiles=False,
        exclude_dotdirs=False,
        dirs=False,
        dirs_avoid=r"\.git$",
    )
    assert relpaths(ff) == sorted(regular + dotfiles + [op.join("subdir", ".git")])


def test_times_manipulations() -> None:
    t0 = get_utcnow_datetime()
    t0_isoformat = ensure_strtime(t0)
    t0_str = ensure_strtime(t0, isoformat=False)

    assert t0 == ensure_datetime(t0)
    assert isinstance(t0_isoformat, str)
    # Test comparison and round-trips
    assert is_same_time(t0, t0_isoformat, t0_str)
    assert is_same_time(t0, t0_str)
    assert is_same_time(t0, t0_str, tolerance=0)  # exactly the same
    assert t0_str != t0_isoformat  # " " vs "T"

    time.sleep(0.001)  # so there is a definite notable delay, in particular for Windows
    t1_epoch = time.time()
    t1 = ensure_datetime(t1_epoch)
    assert is_same_time(t1, t1_epoch)
    # We must not consume more than half a second between start of this test
    # and here
    assert is_same_time(t0, t1, tolerance=0.5)
    assert is_same_time(t1, t0, tolerance=0.5)
    # but must not be exactly the same unless we are way too fast or disregard
    # milliseconds
    assert not is_same_time(t0, t1, tolerance=0)
    assert is_same_time(t0, t1_epoch + 100, tolerance=101)


@pytest.mark.parametrize(
    "t", ["2018-09-26 17:29:17.000000-07:00", "2018-09-26 17:29:17-07:00"]
)
def test_time_samples(t: str) -> None:
    assert is_same_time(
        ensure_datetime(t), "2018-09-27 00:29:17-00:00", tolerance=0
    )  # exactly the same


def test_flatten() -> None:
    assert inspect.isgenerator(flatten([1]))
    # flattened is just a list() around flatten
    assert flattened([1, [2, 3, [4]], 5, (i for i in range(2))]) == [
        1,
        2,
        3,
        4,
        5,
        0,
        1,
    ]


redirector_base = known_instances["dandi"].redirector


@responses.activate
def test_get_instance_dandi_with_api() -> None:
    responses.add(
        responses.GET,
        f"{redirector_base}/server-info",
        json={
            "version": "1.0.0",
            "cli-minimal-version": "0.5.0",
            "cli-bad-versions": [],
            "services": {
                "webui": {"url": "https://gui.dandi"},
                "api": {"url": "https://api.dandi"},
                "jupyterhub": {"url": "https://hub.dandi"},
            },
        },
    )
    assert get_instance("dandi") == DandiInstance(
        gui="https://gui.dandi",
        redirector=redirector_base,
        api="https://api.dandi",
    )


@responses.activate
def test_get_instance_url() -> None:
    responses.add(
        responses.GET,
        "https://example.dandi/server-info",
        json={
            "version": "1.0.0",
            "cli-minimal-version": "0.5.0",
            "cli-bad-versions": [],
            "services": {
                "webui": {"url": "https://gui.dandi"},
                "api": {"url": "https://api.dandi"},
                "jupyterhub": {"url": "https://hub.dandi"},
            },
        },
    )
    assert get_instance("https://example.dandi/") == DandiInstance(
        gui="https://gui.dandi",
        redirector="https://example.dandi/",
        api="https://api.dandi",
    )


@responses.activate
def test_get_instance_cli_version_too_old() -> None:
    responses.add(
        responses.GET,
        "https://example.dandi/server-info",
        json={
            "version": "1.0.0",
            "cli-minimal-version": "99.99.99",
            "cli-bad-versions": [],
            "services": {
                "webui": {"url": "https://gui.dandi"},
                "api": {"url": "https://api.dandi"},
                "jupyterhub": {"url": "https://hub.dandi"},
            },
        },
    )
    with pytest.raises(CliVersionTooOldError) as excinfo:
        get_instance("https://example.dandi/")
    assert str(excinfo.value) == (
        f"Client version {__version__} is too old!"
        "  Server requires at least version 99.99.99"
    )


@responses.activate
def test_get_instance_bad_cli_version() -> None:
    responses.add(
        responses.GET,
        "https://example.dandi/server-info",
        json={
            "version": "1.0.0",
            "cli-minimal-version": "0.5.0",
            "cli-bad-versions": [__version__],
            "services": {
                "webui": {"url": "https://gui.dandi"},
                "api": {"url": "https://api.dandi"},
                "jupyterhub": {"url": "https://hub.dandi"},
            },
        },
    )
    with pytest.raises(BadCliVersionError) as excinfo:
        get_instance("https://example.dandi/")
    assert str(excinfo.value) == (
        f"Client version {__version__} is rejected by server!"
        f"  Server requires at least version 0.5.0 (but not {__version__})"
    )


@responses.activate
def test_get_instance_id_bad_response() -> None:
    responses.add(
        responses.GET,
        f"{redirector_base}/server-info",
        body="404 -- not found",
        status=404,
    )
    assert get_instance("dandi") is known_instances["dandi"]


@responses.activate
def test_get_instance_known_url_bad_response() -> None:
    assert redirector_base is not None
    responses.add(
        responses.GET,
        f"{redirector_base}/server-info",
        body="404 -- not found",
        status=404,
    )
    assert get_instance(redirector_base) is known_instances["dandi"]


@responses.activate
def test_get_instance_unknown_url_bad_response() -> None:
    responses.add(
        responses.GET,
        "https://dandi.nil/server-info",
        body="404 -- not found",
        status=404,
    )
    with pytest.raises(RuntimeError) as excinfo:
        get_instance("https://dandi.nil")
    assert str(excinfo.value) == (
        "Could not retrieve server info from https://dandi.nil,"
        " and client does not recognize URL"
    )


@responses.activate
def test_get_instance_bad_version_from_server() -> None:
    responses.add(
        responses.GET,
        "https://example.dandi/server-info",
        json={
            "version": "1.0.0",
            "cli-minimal-version": "foobar",
            "cli-bad-versions": [],
            "services": {
                "webui": {"url": "https://gui.dandi"},
                "api": {"url": "https://api.dandi"},
                "jupyterhub": {"url": "https://hub.dandi"},
            },
        },
    )
    with pytest.raises(ValueError) as excinfo:
        get_instance("https://example.dandi/")
    assert str(excinfo.value).startswith(
        "https://example.dandi/ returned an incorrectly formatted version;"
        " please contact that server's administrators: "
    )
    assert "foobar" in str(excinfo.value)


def test_get_instance_actual_dandi() -> None:
    inst = get_instance("dandi")
    assert inst.api is not None


if "DANDI_REDIRECTOR_BASE" in os.environ:
    using_docker = pytest.mark.usefixtures("local_dandi_api")
else:
    using_docker = mark.skipif_no_network


@pytest.mark.xfail(reason="https://github.com/dandi/dandi-archive/issues/1045")
@pytest.mark.redirector
@using_docker
def test_server_info() -> None:
    r = requests.get(f"{redirector_base}/server-info")
    r.raise_for_status()
    data = r.json()
    assert "version" in data
    assert Version(data["version"]) >= Version("1.2.0")
    assert "cli-minimal-version" in data
    assert "cli-bad-versions" in data
    assert "services" in data


def test_get_module_version() -> None:
    import pynwb

    import dandi

    assert get_module_version(dandi) == __version__
    assert get_module_version("dandi") == __version__
    assert get_module_version("pynwb") == pynwb.__version__
    assert get_module_version("abracadabra123") is None


@pytest.mark.parametrize(
    "filename,mtype",
    [
        ("foo.txt", "text/plain"),
        ("foo", "application/octet-stream"),
        ("foo.gz", "application/gzip"),
        ("foo.tar.gz", "application/gzip"),
        ("foo.tgz", "application/gzip"),
        ("foo.taz", "application/gzip"),
        ("foo.svg.gz", "application/gzip"),
        ("foo.svgz", "application/gzip"),
        ("foo.Z", "application/x-compress"),
        ("foo.tar.Z", "application/x-compress"),
        ("foo.bz2", "application/x-bzip2"),
        ("foo.tar.bz2", "application/x-bzip2"),
        ("foo.tbz2", "application/x-bzip2"),
        ("foo.xz", "application/x-xz"),
        ("foo.tar.xz", "application/x-xz"),
        ("foo.txz", "application/x-xz"),
    ],
)
def test_get_mime_type(filename: str, mtype: str) -> None:
    assert get_mime_type(filename) == mtype


@pytest.mark.parametrize(
    "page1,page2,r",
    [
        (
            "https://example.com/api/fruits",
            "https://example.com/api/fruits?page=2",
            True,
        ),
        (
            "https://example.com/api/fruits",
            "https://example.com/api/fruits",
            False,
        ),
        (
            "https://example.com/api/fruits",
            "http://example.com/api/fruits?page=2",
            False,
        ),
        (
            "https://example.com/api/fruits",
            "https://example.com/api/fruits/?page=2",
            False,
        ),
        (
            "https://example.com/api/fruits",
            "https://api.example.com/api/fruits?page=2",
            False,
        ),
        (
            "https://example.com/api/fruits",
            "/api/fruits?page=2",
            False,
        ),
        (
            "https://example.com/api/fruits?page=1",
            "https://example.com/api/fruits?page=2",
            True,
        ),
        (
            "https://example.com/api/fruits?per_page=100",
            "https://example.com/api/fruits?per_page=100&page=2",
            True,
        ),
        (
            "https://example.com/api/fruits?per_page=100",
            "https://example.com/api/fruits?page=2&per_page=100",
            True,
        ),
        (
            "https://example.com/api/fruits?per_page=100",
            "https://example.com/api/fruits?page=2",
            False,
        ),
        (
            "https://example.com/api/fruits?per_page=100&order=path",
            "https://example.com/api/fruits?page=2&per_page=100&order=path",
            True,
        ),
        (
            "https://example.com/api/fruits?per_page=100&order=path",
            "https://example.com/api/fruits?order=path&page=2&per_page=100",
            True,
        ),
        (
            "https://example.com/api/fruits?per_page=100&order=path",
            "https://example.com/api/fruits?page=2&per_page=100",
            False,
        ),
        (
            "https://example.com/api/fruits#here",
            "https://example.com/api/fruits?page=2#here",
            True,
        ),
        (
            "https://example.com/api/fruits",
            "https://example.com/api/fruits?page=2#here",
            False,
        ),
        (
            "https://example.com/api/fruits#here",
            "https://example.com/api/fruits?page=2",
            False,
        ),
        (
            "https://example.com/api/fruits#here",
            "https://example.com/api/fruits?page=2#there",
            False,
        ),
        (
            "https://example.com/api/fruits?path=åßç",
            "https://example.com/api/fruits?page=2&path=%C3%A5%C3%9F%C3%A7",
            True,
        ),
    ],
)
def test_is_page2_url(page1: str, page2: str, r: bool) -> None:
    assert is_page2_url(page1, page2) is r
