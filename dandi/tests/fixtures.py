from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import shutil
from subprocess import DEVNULL, check_output, run
import tempfile
from time import sleep
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, List, Optional, Union
from uuid import uuid4

from _pytest.fixtures import FixtureRequest
from click.testing import CliRunner
from dandischema.consts import DANDI_SCHEMA_VERSION
from dateutil.tz import tzlocal, tzutc
import numpy as np
import pynwb
from pynwb import NWBHDF5IO, NWBFile
from pynwb.device import Device
from pynwb.file import Subject
import pynwb.image
from pynwb.ophys import ImageSeries
import pytest
import requests
import zarr

from .skip import skipif
from .. import get_logger
from ..cli.command import organize
from ..consts import DandiInstance, dandiset_metadata_file, known_instances
from ..dandiapi import DandiAPIClient, RemoteDandiset
from ..pynwb_utils import make_nwb_file, metadata_nwb_file_fields
from ..upload import upload

lgr = get_logger()


def copytree(src, dst, symlinks=False, ignore=None):
    """Function mimicking `shutil.copytree()` behaviour but supporting existing target
    directories.

    Notes
    -----
    * This function can be removed and replaced by a call to `shutil.copytree()`
        setting the `dirs_exist_ok` keyword argument to true, whenever Python 3.7
        is no longer supported.

    References
    ----------
    https://docs.python.org/3/whatsnew/3.8.html#shutil
    """
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copytree(s, d, symlinks, ignore)
        else:
            if not os.path.exists(d) or os.stat(s).st_mtime - os.stat(d).st_mtime > 1:
                shutil.copy2(s, d)


@pytest.fixture(autouse=True)
def capture_all_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="dandi")


# TODO: move into some common fixtures.  We might produce a number of files
#       and also carry some small ones directly in git for regression testing
@pytest.fixture(scope="session")
def simple1_nwb_metadata() -> Dict[str, Any]:
    # very simple assignment with the same values as the key with 1 as suffix
    metadata: Dict[str, Any] = {f: f"{f}1" for f in metadata_nwb_file_fields}
    metadata["identifier"] = uuid4().hex
    # subject_fields

    # tune specific ones:
    # Needs an explicit time zone since otherwise pynwb would add one
    # But then comparison breaks anyways any ways yoh have tried to set it
    # for datetime.now.  Taking example from pynwb tests
    metadata["session_start_time"] = datetime(2017, 4, 15, 12, tzinfo=tzutc())
    metadata["keywords"] = ["keyword1", "keyword 2"]
    # since NWB 2.1.0 some fields values become "arrays" which are
    # then reloaded as tuples, so we force them being tuples here
    # See e.g. https://github.com/NeurodataWithoutBorders/pynwb/issues/1091
    for f in "related_publications", "experimenter":
        metadata[f] = (metadata[f],)
    return metadata


@pytest.fixture(scope="session")
def simple1_nwb(
    simple1_nwb_metadata: Dict[str, Any], tmpdir_factory: pytest.TempdirFactory
) -> str:
    return make_nwb_file(
        str(tmpdir_factory.mktemp("simple1").join("simple1.nwb")),
        **simple1_nwb_metadata,
    )


@pytest.fixture(scope="session")
def simple2_nwb(
    simple1_nwb_metadata: Dict[str, Any], tmpdir_factory: pytest.TempdirFactory
) -> str:
    """With a subject"""
    return make_nwb_file(
        str(tmpdir_factory.mktemp("simple2").join("simple2.nwb")),
        subject=pynwb.file.Subject(
            subject_id="mouse001",
            date_of_birth=datetime(2016, 12, 1, tzinfo=tzutc()),
            sex="U",
            species="Mus musculus",
        ),
        **simple1_nwb_metadata,
    )


@pytest.fixture(scope="session")
def simple3_nwb(
    simple1_nwb_metadata: Dict[str, Any], tmpdir_factory: pytest.TempdirFactory
) -> str:
    """With a subject, but no subject_id."""
    return make_nwb_file(
        str(tmpdir_factory.mktemp("simple2").join("simple2.nwb")),
        subject=pynwb.file.Subject(
            age="P1D/",
            sex="O",
            species="Mus musculus",
        ),
        **simple1_nwb_metadata,
    )


@pytest.fixture(scope="session")
def organized_nwb_dir(
    simple2_nwb: str, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    tmp_path = tmp_path_factory.mktemp("organized_nwb_dir")
    (tmp_path / dandiset_metadata_file).write_text("{}\n")
    r = CliRunner().invoke(
        organize, ["-f", "copy", "--dandiset-path", str(tmp_path), str(simple2_nwb)]
    )
    assert r.exit_code == 0, r.stdout
    return tmp_path


@pytest.fixture(scope="session")
def organized_nwb_dir2(
    simple1_nwb_metadata: Dict[str, Any],
    simple2_nwb: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    tmp_path = tmp_path_factory.mktemp("organized_nwb_dir2")

    # need to copy first and then use -f move since we will create one more
    # file to be "organized"
    shutil.copy(simple2_nwb, tmp_path)
    make_nwb_file(
        str(tmp_path / "simple3.nwb"),
        subject=pynwb.file.Subject(
            subject_id="lizard001",
            date_of_birth=datetime(2016, 12, 1, tzinfo=tzutc()),
            sex="F",
            species="Gekko gecko",
        ),
        **simple1_nwb_metadata,
    )
    (tmp_path / dandiset_metadata_file).write_text("{}\n")
    r = CliRunner().invoke(organize, ["-f", "move", "--dandiset-path", str(tmp_path)])
    assert r.exit_code == 0, r.stdout
    assert sum(p.is_dir() for p in tmp_path.iterdir()) == 2
    return tmp_path


if TYPE_CHECKING:
    from ..support.typing import Literal

    Scope = Union[
        Literal["session"],
        Literal["package"],
        Literal["module"],
        Literal["class"],
        Literal["function"],
    ]


def get_gitrepo_fixture(
    url: str,
    committish: Optional[str] = None,
    scope: Scope = "session",
) -> Callable[[], Iterator[str]]:

    if committish:
        raise NotImplementedError()

    @pytest.fixture(scope=scope)
    def fixture() -> Iterator[str]:
        skipif.no_network()
        skipif.no_git()

        path = tempfile.mktemp()  # not using pytest's tmpdir fixture to not
        # collide in different scopes etc. But we
        # would need to remove it ourselves
        lgr.debug("Cloning %r into %r", url, path)
        try:
            runout = run(["git", "clone", "--depth=1", url, path])
            if runout.returncode:
                raise RuntimeError(f"Failed to clone {url} into {path}")
            yield path
        finally:
            try:
                shutil.rmtree(path)
            except BaseException as exc:
                lgr.warning("Failed to remove %s - using Windows?: %s", path, exc)

    return fixture


nwb_test_data = get_gitrepo_fixture("http://github.com/dandi-datasets/nwb_test_data")
bids_examples = get_gitrepo_fixture("https://github.com/dandi/bids-examples")

LOCAL_DOCKER_DIR = Path(__file__).with_name("data") / "dandiarchive-docker"
LOCAL_DOCKER_ENV = LOCAL_DOCKER_DIR.name


@pytest.fixture(scope="session")
def docker_compose_setup() -> Iterator[Dict[str, str]]:
    skipif.no_network()
    skipif.no_docker_engine()

    # Check that we're running on a Unix-based system (Linux or macOS), as the
    # Docker images don't work on Windows.
    if os.name != "posix":
        pytest.skip("Docker images require Unix host")

    persist = os.environ.get("DANDI_TESTS_PERSIST_DOCKER_COMPOSE")

    create = (
        persist is None
        or run(
            ["docker", "inspect", f"{LOCAL_DOCKER_ENV}_django_1"],
            stdout=DEVNULL,
            stderr=DEVNULL,
        ).returncode
        != 0
    )

    env = {**os.environ, "DJANGO_DANDI_SCHEMA_VERSION": DANDI_SCHEMA_VERSION}
    try:
        if create:
            run(["docker-compose", "pull"], cwd=str(LOCAL_DOCKER_DIR), check=True)
            run(
                ["docker-compose", "run", "--rm", "django", "./manage.py", "migrate"],
                cwd=str(LOCAL_DOCKER_DIR),
                env=env,
                check=True,
            )
            run(
                [
                    "docker-compose",
                    "run",
                    "--rm",
                    "-e",
                    "DJANGO_SUPERUSER_PASSWORD=nsNc48DBiS",
                    "django",
                    "./manage.py",
                    "createsuperuser",
                    "--no-input",
                    "--email",
                    "admin@nil.nil",
                ],
                cwd=str(LOCAL_DOCKER_DIR),
                env=env,
                check=True,
            )

        r = check_output(
            [
                "docker-compose",
                "run",
                "--rm",
                "-T",
                "django",
                "./manage.py",
                "drf_create_token",
                "admin@nil.nil",
            ],
            cwd=str(LOCAL_DOCKER_DIR),
            env=env,
            universal_newlines=True,
        )
        m = re.search(r"^Generated token (\w+) for user admin@nil.nil$", r, flags=re.M)
        if not m:
            raise RuntimeError(
                f"Could not extract Django auth token from drf_create_token output: {r!r}"
            )
        django_api_key = m[1]

        if create:
            run(
                ["docker-compose", "up", "-d", "django", "celery"],
                cwd=str(LOCAL_DOCKER_DIR),
                env=env,
                check=True,
            )
            API_URL = known_instances["dandi-api-local-docker-tests"].api
            for _ in range(25):
                try:
                    requests.get(f"{API_URL}/dandisets/")
                except requests.ConnectionError:
                    sleep(1)
                else:
                    break
            else:
                raise RuntimeError("Django container did not start up in time")
        yield {"django_api_key": django_api_key}
    finally:
        if persist in (None, "0"):
            run(["docker-compose", "down", "-v"], cwd=str(LOCAL_DOCKER_DIR), check=True)


@dataclass
class DandiAPI:
    api_key: str
    client: DandiAPIClient
    instance: DandiInstance
    instance_id: str

    @property
    def api_url(self) -> str:
        url = self.instance.api
        assert isinstance(url, str)
        return url


@pytest.fixture(scope="session")
def local_dandi_api(docker_compose_setup: Dict[str, str]) -> Iterator[DandiAPI]:
    instance_id = "dandi-api-local-docker-tests"
    instance = known_instances[instance_id]
    api_key = docker_compose_setup["django_api_key"]
    with DandiAPIClient(api_url=instance.api, token=api_key) as client:
        yield DandiAPI(
            api_key=api_key,
            client=client,
            instance=instance,
            instance_id=instance_id,
        )


@dataclass
class SampleDandiset:
    api: DandiAPI
    dspath: Path
    dandiset: RemoteDandiset
    dandiset_id: str
    upload_kwargs: Dict[str, Any] = field(default_factory=dict)

    @property
    def client(self) -> DandiAPIClient:
        return self.api.client

    def upload(
        self, paths: Optional[List[Union[str, Path]]] = None, **kwargs: Any
    ) -> None:
        with pytest.MonkeyPatch().context() as m:
            m.setenv("DANDI_API_KEY", self.api.api_key)
            upload(
                paths=paths or [self.dspath],
                dandi_instance=self.api.instance_id,
                devel_debug=True,
                **{**self.upload_kwargs, **kwargs},
            )


@pytest.fixture()
def new_dandiset(
    local_dandi_api: DandiAPI,
    request: FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> SampleDandiset:
    d = local_dandi_api.client.create_dandiset(
        f"Sample Dandiset for {request.node.name}",
        # Minimal metadata needed to create a publishable Dandiset:
        {
            "description": "A test Dandiset",
            "license": ["spdx:CC0-1.0"],
            # The contributor needs to be given explicitly here or else it'll
            # be set based on the user account.  For the Docker Compose setup,
            # that would mean basing it on the admin user, whose name doesn't
            # validate under dandischema.
            "contributor": [
                {
                    "schemaKey": "Person",
                    "name": "Wodder, John",
                    "roleName": ["dcite:Author", "dcite:ContactPerson"],
                }
            ],
        },
    )
    dspath = tmp_path_factory.mktemp("dandiset")
    (dspath / dandiset_metadata_file).write_text(f"identifier: '{d.identifier}'\n")
    return SampleDandiset(
        api=local_dandi_api,
        dspath=dspath,
        dandiset=d,
        dandiset_id=d.identifier,
    )


@pytest.fixture()
def text_dandiset(new_dandiset: SampleDandiset) -> SampleDandiset:
    (new_dandiset.dspath / "file.txt").write_text("This is test text.\n")
    (new_dandiset.dspath / "subdir1").mkdir()
    (new_dandiset.dspath / "subdir1" / "apple.txt").write_text("Apple\n")
    (new_dandiset.dspath / "subdir2").mkdir()
    (new_dandiset.dspath / "subdir2" / "banana.txt").write_text("Banana\n")
    (new_dandiset.dspath / "subdir2" / "coconut.txt").write_text("Coconut\n")
    new_dandiset.upload_kwargs["allow_any_path"] = True
    new_dandiset.upload()
    return new_dandiset


@pytest.fixture()
def zarr_dandiset(new_dandiset: SampleDandiset) -> SampleDandiset:
    zarr.save(
        new_dandiset.dspath / "sample.zarr", np.arange(1000), np.arange(1000, 0, -1)
    )
    new_dandiset.upload()
    return new_dandiset


@pytest.fixture()
def bids_dandiset(new_dandiset: SampleDandiset, bids_examples: str) -> SampleDandiset:
    copytree(
        os.path.join(bids_examples, "asl003"),
        str(new_dandiset.dspath) + "/",
    )
    (new_dandiset.dspath / "CHANGES").write_text("0.1.0 2014-11-03\n")
    return new_dandiset


@pytest.fixture()
def bids_dandiset_invalid(
    new_dandiset: SampleDandiset, bids_examples: str
) -> SampleDandiset:
    copytree(
        os.path.join(bids_examples, "invalid_pet001"),
        str(new_dandiset.dspath) + "/",
    )
    return new_dandiset


@pytest.fixture()
def video_files(tmp_path):
    video_paths = []
    import cv2

    video_path = tmp_path / "video_files"
    video_path.mkdir()
    for no in range(2):
        movie_file1 = video_path / f"test1_{no}.avi"
        movie_file2 = video_path / f"test2_{no}.avi"
        (nf, nx, ny) = (2, 2, 2)
        writer1 = cv2.VideoWriter(
            filename=str(movie_file1),
            apiPreference=None,
            fourcc=cv2.VideoWriter_fourcc(*"DIVX"),
            fps=25,
            frameSize=(ny, nx),
            params=None,
        )
        writer2 = cv2.VideoWriter(
            filename=str(movie_file2),
            apiPreference=None,
            fourcc=cv2.VideoWriter_fourcc(*"DIVX"),
            fps=25,
            frameSize=(ny, nx),
            params=None,
        )
        for k in range(nf):
            writer1.write(np.random.randint(0, 255, (nx, ny, 3)).astype("uint8"))
            writer2.write(np.random.randint(0, 255, (nx, ny, 3)).astype("uint8"))
        writer1.release()
        writer2.release()
        video_paths.append((movie_file1, movie_file2))
    return video_paths


def _create_nwb_files(video_list):
    base_path = video_list[0][0].parent.parent
    base_nwb_path = base_path / "nwbfiles"
    base_nwb_path.mkdir(parents=True, exist_ok=True)
    for no, vid_loc in enumerate(video_list):
        vid_1 = vid_loc[0]
        vid_2 = vid_loc[1]
        subject_id = f"mouse{no}"
        session_id = f"sessionid{no}"
        subject = Subject(
            subject_id=subject_id,
            species="Mus musculus",
            sex="M",
            description="lab mouse ",
        )
        device = Device(f"imaging_device_{no}")
        name = f"{vid_1.stem}_{no}"
        nwbfile = NWBFile(
            f"{name}{no}",
            "desc: contains movie for dandi .mp4 storage as external",
            datetime.now(tzlocal()),
            experimenter="Experimenter name",
            session_id=session_id,
            subject=subject,
            devices=[device],
        )

        image_series = ImageSeries(
            name=f"MouseWhiskers{no}",
            format="external",
            external_file=[str(vid_1), str(vid_2)],
            starting_frame=[0, 2],
            starting_time=0.0,
            rate=150.0,
        )
        nwbfile.add_acquisition(image_series)

        nwbfile_path = base_nwb_path / f"{name}.nwb"
        with NWBHDF5IO(str(nwbfile_path), "w") as io:
            io.write(nwbfile)
    return base_nwb_path


@pytest.fixture()
def nwbfiles_video_unique(video_files):
    """Create nwbfiles linked with unique set of videos."""
    return _create_nwb_files(video_files)


@pytest.fixture()
def nwbfiles_video_common(video_files):
    """Create nwbfiles sharing video files."""
    video_list = [video_files[0], video_files[0]]
    return _create_nwb_files(video_list)


@pytest.fixture()
def tmp_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    home = tmp_path_factory.mktemp("tmp_home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_DIRS", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("LOCALAPPDATA", str(home))
    return home
