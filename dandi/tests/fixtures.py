from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import re
import shutil
from subprocess import DEVNULL, check_output, run
from time import sleep
from typing import Any, Literal
from uuid import uuid4

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
from ..cli.cmd_organize import organize
from ..consts import (
    DandiInstance,
    dandiset_metadata_file,
    known_instances,
    metadata_nwb_file_fields,
)
from ..dandiapi import DandiAPIClient, RemoteDandiset
from ..pynwb_utils import make_nwb_file
from ..upload import upload

lgr = get_logger()


BIDS_TESTDATA_SELECTION = [
    "asl003",
    "eeg_cbm",
    "ieeg_epilepsyNWB",
    # uncomment once upstream releases fixed spec:
    # https://github.com/bids-standard/bids-specification/pull/1346#event-7696972438
    # "hcp_example_bids",
    "micr_SEMzarr",
    "micr_SPIM",
    "pet003",
    "qmri_tb1tfl",
    "qmri_vfa",
]

BIDS_ERROR_TESTDATA_SELECTION = ["invalid_asl003", "invalid_pet001"]


@pytest.fixture(autouse=True)
def capture_all_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="dandi")


# TODO: move into some common fixtures.  We might produce a number of files
#       and also carry some small ones directly in git for regression testing
@pytest.fixture(scope="session")
def simple1_nwb_metadata() -> dict[str, Any]:
    # very simple assignment with the same values as the key with 1 as suffix
    metadata: dict[str, Any] = {f: f"{f}1" for f in metadata_nwb_file_fields}
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
    simple1_nwb_metadata: dict[str, Any], tmp_path_factory: pytest.TempPathFactory
) -> Path:
    return make_nwb_file(
        tmp_path_factory.mktemp("simple1") / "simple1.nwb",
        **simple1_nwb_metadata,
    )


@pytest.fixture(scope="session")
def simple2_nwb(
    simple1_nwb_metadata: dict[str, Any], tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """With a subject"""
    return make_nwb_file(
        tmp_path_factory.mktemp("simple2") / "simple2.nwb",
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
    simple1_nwb_metadata: dict[str, Any], tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """With a subject, but no subject_id."""
    return make_nwb_file(
        tmp_path_factory.mktemp("simple3") / "simple3.nwb",
        subject=pynwb.file.Subject(
            age="P1D/",
            sex="O",
            species="Mus musculus",
        ),
        **simple1_nwb_metadata,
    )


@pytest.fixture(scope="session")
def simple4_nwb(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """With subject, subject_id, species, but including data orientation ambiguity."""

    start_time = datetime(2017, 4, 3, 11, tzinfo=timezone.utc)
    time_series = pynwb.TimeSeries(
        name="test_time_series",
        unit="test_units",
        data=np.zeros(shape=(2, 100)),
        rate=1.0,
    )

    nwbfile = NWBFile(
        session_description="some session",
        identifier="NWBE4",
        session_start_time=start_time,
        subject=Subject(
            subject_id="mouse004",
            age="P1D/",
            sex="O",
            species="Mus musculus",
        ),
    )
    nwbfile.add_acquisition(time_series)
    filename = tmp_path_factory.mktemp("simple4") / "simple4.nwb"
    with pynwb.NWBHDF5IO(filename, "w") as io:
        io.write(nwbfile, cache_spec=False)
    return filename


@pytest.fixture(scope="session")
def simple5_nwb(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    With subject, subject_id, species, but including data orientation ambiguity, and missing
    the `pynwb.Timeseries` `unit` attribute.

    Notes
    -----
    * These are both best practice violations, as per the discussion upstream:
        https://github.com/NeurodataWithoutBorders/nwbinspector/issues/345#issuecomment-1459232718

    """

    start_time = datetime(2017, 4, 3, 11, tzinfo=timezone.utc)
    time_series = pynwb.TimeSeries(
        name="test_time_series",
        unit="",
        data=np.zeros(shape=(2, 100)),
        rate=1.0,
    )

    nwbfile = NWBFile(
        session_description="some session",
        identifier="NWBE4",
        session_start_time=start_time,
        subject=Subject(
            subject_id="mouse001",
            age="P1D/",
            sex="O",
            species="Mus musculus",
        ),
    )
    nwbfile.add_acquisition(time_series)
    filename = tmp_path_factory.mktemp("simple4") / "simple4.nwb"
    with pynwb.NWBHDF5IO(filename, "w") as io:
        io.write(nwbfile, cache_spec=False)
    return filename


@pytest.fixture(scope="session")
def organized_nwb_dir(
    simple2_nwb: Path, tmp_path_factory: pytest.TempPathFactory
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
    simple1_nwb_metadata: dict[str, Any],
    simple2_nwb: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    tmp_path = tmp_path_factory.mktemp("organized_nwb_dir2")

    # need to copy first and then use -f move since we will create one more
    # file to be "organized"
    shutil.copy(simple2_nwb, tmp_path)
    make_nwb_file(
        tmp_path / "simple3.nwb",
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


@pytest.fixture(scope="session")
def organized_nwb_dir3(
    simple4_nwb: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    tmp_path = tmp_path_factory.mktemp("organized_nwb_dir")
    (tmp_path / dandiset_metadata_file).write_text("{}\n")
    r = CliRunner().invoke(
        organize, ["-f", "copy", "--dandiset-path", str(tmp_path), str(simple4_nwb)]
    )
    assert r.exit_code == 0, r.stdout
    return tmp_path


@pytest.fixture(scope="session")
def organized_nwb_dir4(
    simple4_nwb: Path,
    simple5_nwb: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """
    Organized NWB directory with one file having one best practice violation, and another file
    having two best practice violations.
    """
    tmp_path = tmp_path_factory.mktemp("organized_nwb_dir")
    (tmp_path / dandiset_metadata_file).write_text("{}\n")
    r = CliRunner().invoke(
        organize,
        [
            "-f",
            "copy",
            "--dandiset-path",
            str(tmp_path),
            str(simple4_nwb),
            str(simple5_nwb),
        ],
    )
    assert r.exit_code == 0, r.stdout
    return tmp_path


Scope = Literal["session", "package", "module", "class", "function"]


def get_gitrepo_fixture(
    url: str,
    committish: str | None = None,
    scope: Scope = "session",
    make_subdirs_dandisets: bool = False,
) -> Callable[[pytest.TempPathFactory], Path]:

    if committish:
        raise NotImplementedError()

    @pytest.fixture(scope=scope)
    def fixture(tmp_path_factory: pytest.TempPathFactory) -> Path:
        skipif.no_network()
        skipif.no_git()
        path = tmp_path_factory.mktemp("gitrepo")
        lgr.debug("Cloning %r into %r", url, path)
        run(["git", "clone", "--depth=1", url, str(path)], check=True)
        if make_subdirs_dandisets:
            _make_subdirs_dandisets(path)
        return path

    return fixture


def get_filtered_gitrepo_fixture(
    url: str,
    whitelist: list[str],
    make_subdirs_dandisets: bool | None = False,
) -> Callable[[pytest.TempPathFactory], Iterator[Path]]:
    @pytest.fixture(scope="session")
    def fixture(
        tmp_path_factory: pytest.TempPathFactory,
    ) -> Iterator[Path]:
        skipif.no_network()
        skipif.no_git()
        path = tmp_path_factory.mktemp("gitrepo")
        lgr.debug("Cloning %r into %r", url, path)
        run(
            [
                "git",
                "clone",
                "--depth=1",
                "--filter=blob:none",
                "--sparse",
                url,
                str(path),
            ],
            check=True,
        )
        # cwd specification is VERY important, not only to achieve the correct
        # effects, but also to avoid dropping files from your repository if you
        # were to run `git sparse-checkout` inside the software repo.
        run(["git", "sparse-checkout", "init", "--cone"], cwd=str(path), check=True)
        run(["git", "sparse-checkout", "set"] + whitelist, cwd=str(path), check=True)
        if make_subdirs_dandisets:
            _make_subdirs_dandisets(path)
        yield path

    return fixture


def _make_subdirs_dandisets(path: Path) -> None:
    for bids_dataset_path in path.iterdir():
        if bids_dataset_path.is_dir():
            (bids_dataset_path / dandiset_metadata_file).write_text(
                "identifier: '000001'\n"
            )


nwb_test_data = get_gitrepo_fixture("http://github.com/dandi-datasets/nwb_test_data")
bids_examples = get_filtered_gitrepo_fixture(
    url="https://github.com/bids-standard/bids-examples",
    whitelist=BIDS_TESTDATA_SELECTION,
    make_subdirs_dandisets=True,
)
bids_error_examples = get_filtered_gitrepo_fixture(
    "https://github.com/bids-standard/bids-error-examples",
    whitelist=BIDS_ERROR_TESTDATA_SELECTION,
    make_subdirs_dandisets=True,
)

LOCAL_DOCKER_DIR = Path(__file__).with_name("data") / "dandiarchive-docker"
LOCAL_DOCKER_ENV = LOCAL_DOCKER_DIR.name


@pytest.fixture(scope="session")
def docker_compose_setup() -> Iterator[dict[str, str]]:
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
            if os.environ.get("DANDI_TESTS_PULL_DOCKER_COMPOSE", "1") not in ("", "0"):
                run(
                    ["docker", "compose", "pull"], cwd=str(LOCAL_DOCKER_DIR), check=True
                )
            run(
                [
                    "docker",
                    "compose",
                    "run",
                    "--rm",
                    "django",
                    "./manage.py",
                    "migrate",
                ],
                cwd=str(LOCAL_DOCKER_DIR),
                env=env,
                check=True,
            )
            run(
                [
                    "docker",
                    "compose",
                    "run",
                    "--rm",
                    "django",
                    "./manage.py",
                    "createcachetable",
                ],
                cwd=str(LOCAL_DOCKER_DIR),
                env=env,
                check=True,
            )
            run(
                [
                    "docker",
                    "compose",
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
                "docker",
                "compose",
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
            text=True,
        )
        m = re.search(r"^Generated token (\w+) for user admin@nil.nil$", r, flags=re.M)
        if not m:
            raise RuntimeError(
                f"Could not extract Django auth token from drf_create_token output: {r!r}"
            )
        django_api_key = m[1]

        if create:
            run(
                ["docker", "compose", "up", "-d", "django", "celery"],
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
        if auditfile := os.environ.get("DANDI_TESTS_AUDIT_CSV", ""):
            with open(auditfile, "wb") as fp:
                run(
                    [
                        "docker",
                        "compose",
                        "exec",
                        "postgres",
                        "psql",
                        "-U",
                        "postgres",
                        "-d",
                        "django",
                        "--csv",
                        "-c",
                        "SELECT * FROM api_auditrecord;",
                    ],
                    stdout=fp,
                    cwd=str(LOCAL_DOCKER_DIR),
                    check=True,
                )
        if persist in (None, "0"):
            run(
                ["docker", "compose", "down", "-v"],
                cwd=str(LOCAL_DOCKER_DIR),
                check=True,
            )


@dataclass
class DandiAPI:
    api_key: str
    client: DandiAPIClient

    @property
    def instance(self) -> DandiInstance:
        return self.client.dandi_instance

    @property
    def instance_id(self) -> str:
        return self.instance.name

    @property
    def api_url(self) -> str:
        return self.instance.api


@pytest.fixture(scope="session")
def local_dandi_api(docker_compose_setup: dict[str, str]) -> Iterator[DandiAPI]:
    instance = known_instances["dandi-api-local-docker-tests"]
    api_key = docker_compose_setup["django_api_key"]
    with DandiAPIClient.for_dandi_instance(instance, token=api_key) as client:
        yield DandiAPI(api_key=api_key, client=client)


@dataclass
class SampleDandiset:
    api: DandiAPI
    dspath: Path
    dandiset: RemoteDandiset
    dandiset_id: str
    upload_kwargs: dict[str, Any] = field(default_factory=dict)

    @property
    def client(self) -> DandiAPIClient:
        return self.api.client

    def upload(self, paths: list[str | Path] | None = None, **kwargs: Any) -> None:
        with pytest.MonkeyPatch().context() as m:
            m.setenv("DANDI_API_KEY", self.api.api_key)
            upload(
                paths=paths or [self.dspath],
                dandi_instance=self.api.instance_id,
                devel_debug=True,
                **{**self.upload_kwargs, **kwargs},
            )


@dataclass
class SampleDandisetFactory:
    local_dandi_api: DandiAPI
    tmp_path_factory: pytest.TempPathFactory

    def mkdandiset(self, name: str, embargo: bool = False) -> SampleDandiset:
        d = self.local_dandi_api.client.create_dandiset(
            name,
            # Minimal metadata needed to create a publishable Dandiset:
            {
                "description": "A test Dandiset",
                "license": ["spdx:CC0-1.0"],
                # The contributor needs to be given explicitly here or else
                # it'll be set based on the user account.  For the Docker
                # Compose setup, that would mean basing it on the admin user,
                # whose name doesn't validate under dandischema.
                "contributor": [
                    {
                        "schemaKey": "Person",
                        "name": "Tests, DANDI-Cli",
                        "email": "nemo@example.com",
                        "roleName": ["dcite:Author", "dcite:ContactPerson"],
                    }
                ],
            },
            embargo=embargo,
        )
        dspath = self.tmp_path_factory.mktemp("dandiset")
        (dspath / dandiset_metadata_file).write_text(f"identifier: '{d.identifier}'\n")
        return SampleDandiset(
            api=self.local_dandi_api,
            dspath=dspath,
            dandiset=d,
            dandiset_id=d.identifier,
        )


@pytest.fixture
def sample_dandiset_factory(
    local_dandi_api: DandiAPI, tmp_path_factory: pytest.TempPathFactory
) -> SampleDandisetFactory:
    return SampleDandisetFactory(local_dandi_api, tmp_path_factory)


# @sweep_embargo can be used along with `new_dandiset` fixture to
# run the test against both embargoed and non-embargoed Dandisets.
# "embargo: bool" argument should be added to the test function.
sweep_embargo = pytest.mark.parametrize("embargo", [True, False])


@pytest.fixture()
def new_dandiset(
    request: pytest.FixtureRequest, sample_dandiset_factory: SampleDandisetFactory
) -> SampleDandiset:
    kws = {}
    if "embargo" in request.node.fixturenames:
        kws["embargo"] = request.node.callspec.params["embargo"]
    return sample_dandiset_factory.mkdandiset(
        f"Sample {'Embargoed' if kws.get('embargo') else 'Public'} "
        f"Dandiset for {request.node.name}",
        **kws,
    )


@pytest.fixture()
def nwb_dandiset(new_dandiset: SampleDandiset, simple2_nwb: Path) -> SampleDandiset:
    (new_dandiset.dspath / "sub-mouse001").mkdir()
    shutil.copy2(simple2_nwb, new_dandiset.dspath / "sub-mouse001" / "sub-mouse001.nwb")
    new_dandiset.upload()
    return new_dandiset


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
def bids_dandiset(new_dandiset: SampleDandiset, bids_examples: Path) -> SampleDandiset:
    shutil.copytree(
        bids_examples / "asl003",
        new_dandiset.dspath,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(dandiset_metadata_file),
    )
    (new_dandiset.dspath / "CHANGES").write_text("0.1.0 2014-11-03\n")
    return new_dandiset


@pytest.fixture()
def bids_nwb_dandiset(
    new_dandiset: SampleDandiset, bids_examples: Path
) -> SampleDandiset:
    shutil.copytree(
        bids_examples / "ieeg_epilepsyNWB",
        new_dandiset.dspath,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(dandiset_metadata_file),
    )
    (new_dandiset.dspath / "CHANGES").write_text("0.1.0 2014-11-03\n")
    return new_dandiset


# TODO: refactor: avoid duplication and come up with some fixture helper which would
# just need specify bids example name
@pytest.fixture()
def bids_zarr_dandiset(
    new_dandiset: SampleDandiset, bids_examples: Path
) -> SampleDandiset:
    shutil.copytree(
        bids_examples / "micr_SEMzarr",
        new_dandiset.dspath,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(dandiset_metadata_file),
    )
    (new_dandiset.dspath / "CHANGES").write_text("0.1.0 2014-11-03\n")
    return new_dandiset


@pytest.fixture()
def bids_dandiset_invalid(
    new_dandiset: SampleDandiset, bids_error_examples: Path
) -> SampleDandiset:
    dataset_path = new_dandiset.dspath
    shutil.copytree(
        bids_error_examples / "invalid_pet001",
        dataset_path,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(dandiset_metadata_file),
    )
    (dataset_path / "README").unlink()
    return new_dandiset


@pytest.fixture()
def video_files(tmp_path: Path) -> list[tuple[Path, Path]]:
    # Avoid heavy import by importing within function:
    import cv2

    video_paths = []
    video_path = tmp_path / "video_files"
    video_path.mkdir()
    for i in range(2):
        movie_file1 = video_path / f"test1_{i}.avi"
        movie_file2 = video_path / f"test2_{i}.avi"
        (nf, nx, ny) = (2, 2, 2)
        writer1 = cv2.VideoWriter(
            filename=str(movie_file1),
            apiPreference=0,
            fourcc=cv2.VideoWriter.fourcc(*"DIVX"),
            fps=25.0,
            frameSize=(ny, nx),
        )
        writer2 = cv2.VideoWriter(
            filename=str(movie_file2),
            apiPreference=0,
            fourcc=cv2.VideoWriter.fourcc(*"DIVX"),
            fps=25,
            frameSize=(ny, nx),
        )
        for k in range(nf):
            writer1.write(np.random.randint(0, 255, (nx, ny, 3)).astype("uint8"))
            writer2.write(np.random.randint(0, 255, (nx, ny, 3)).astype("uint8"))
        writer1.release()
        writer2.release()
        video_paths.append((movie_file1, movie_file2))
    return video_paths


def _create_nwb_files(video_list: list[tuple[Path, Path]]) -> Path:
    base_path = video_list[0][0].parent.parent
    base_nwb_path = base_path / "nwbfiles"
    base_nwb_path.mkdir(parents=True, exist_ok=True)
    for i, vid_loc in enumerate(video_list):
        vid_1 = vid_loc[0]
        vid_2 = vid_loc[1]
        subject_id = f"mouse{i}"
        session_id = f"sessionid{i}"
        subject = Subject(
            subject_id=subject_id,
            species="Mus musculus",
            sex="M",
            description="lab mouse ",
        )
        device = Device(f"imaging_device_{i}")
        name = f"{vid_1.stem}_{i}"
        nwbfile = NWBFile(
            f"{name}{i}",
            "desc: contains movie for dandi .mp4 storage as external",
            datetime.now(tzlocal()),
            experimenter="Experimenter name",
            session_id=session_id,
            subject=subject,
            devices=[device],
        )

        image_series = ImageSeries(
            name=f"MouseWhiskers{i}",
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
def nwbfiles_video_unique(video_files: list[tuple[Path, Path]]) -> Path:
    """Create nwbfiles linked with unique set of videos."""
    return _create_nwb_files(video_files)


@pytest.fixture()
def nwbfiles_video_common(video_files: list[tuple[Path, Path]]) -> Path:
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
