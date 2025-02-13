from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import ANY

from click.testing import CliRunner
from dandischema.consts import DANDI_SCHEMA_VERSION
import pytest

from dandi.tests.skip import mark

from ..cmd_ls import ls
from ...utils import yaml_load


@pytest.mark.parametrize(
    "format", ("auto", "json", "json_pp", "json_lines", "yaml", "pyout")
)
def test_smoke(
    simple1_nwb_metadata: dict[str, Any], simple1_nwb: Path, format: str
) -> None:
    runner = CliRunner()
    r = runner.invoke(ls, ["-f", format, str(simple1_nwb)])
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    # we would need to redirect pyout for its analysis
    out = r.stdout

    if format == "json_lines":

        def load(s: str) -> Any:
            return json.loads(s)

    elif format.startswith("json"):

        def load(s: str) -> Any:
            obj = json.loads(s)
            assert len(obj) == 1  # will be a list with a single elem
            return obj[0]

    elif format == "yaml":

        def load(s: str) -> Any:
            obj = yaml_load(s, typ="base")
            assert len(obj) == 1  # will be a list with a single elem
            return obj[0]

    else:
        return

    metadata = load(out)
    assert metadata
    # check a few fields
    assert metadata.pop("nwb_version").startswith("2.")
    for f in ["session_id", "experiment_description"]:
        assert metadata[f] == simple1_nwb_metadata[f]


def test_ls_nwb_file(simple2_nwb: Path) -> None:
    bids_file_path = simple2_nwb / "simple2.nwb"
    r = CliRunner().invoke(ls, ["-f", "yaml", str(bids_file_path)])
    assert r.exit_code == 0, r.output
    data = yaml_load(r.stdout, "safe")
    assert len(data) == 1


@mark.skipif_no_network
def test_ls_bids_file(bids_examples: Path) -> None:
    bids_file_path = (
        bids_examples / "asl003" / "sub-Sub1" / "anat" / "sub-Sub1_T1w.nii.gz"
    )
    r = CliRunner().invoke(ls, ["-f", "yaml", str(bids_file_path)])
    assert r.exit_code == 0, r.output
    data = yaml_load(r.stdout, "safe")
    assert len(data) == 1
    assert data[0]["identifier"] == "Sub1"


@mark.skipif_no_network
def test_ls_zarrbids_file(bids_examples: Path) -> None:
    bids_file_path = (
        bids_examples
        / "micr_SEMzarr"
        / "sub-01"
        / "ses-01"
        / "micr"
        / "sub-01_ses-01_sample-A_SPIM.ome.zarr"
    )
    r = CliRunner().invoke(ls, ["-f", "yaml", str(bids_file_path)])
    assert r.exit_code == 0, r.output
    data = yaml_load(r.stdout, "safe")
    assert len(data) == 1
    assert data[0]["identifier"] == "01"


@mark.skipif_no_network
def test_ls_dandiset_url() -> None:
    r = CliRunner().invoke(
        ls, ["-f", "yaml", "https://api.dandiarchive.org/api/dandisets/000027"]
    )
    assert r.exit_code == 0, r.output
    data = yaml_load(r.stdout, "safe")
    assert len(data) == 1
    assert data[0]["path"] == "000027"


@mark.skipif_no_network
def test_ls_dandiset_url_recursive() -> None:
    r = CliRunner().invoke(
        ls, ["-f", "yaml", "-r", "https://api.dandiarchive.org/api/dandisets/000027"]
    )
    assert r.exit_code == 0, r.output
    data = yaml_load(r.stdout, "safe")
    assert len(data) == 2
    assert data[0]["path"] == "000027"
    assert data[1]["path"] == "sub-RAT123/sub-RAT123.nwb"


@mark.skipif_no_network
def test_ls_path_url() -> None:
    r = CliRunner().invoke(
        ls,
        [
            "-f",
            "yaml",
            (
                "https://api.dandiarchive.org/api/dandisets/000027/versions/draft"
                "/assets/?path=sub-RAT123/"
            ),
        ],
    )
    assert r.exit_code == 0, r.output
    data = yaml_load(r.stdout, "safe")
    assert len(data) == 1
    assert data[0]["path"] == "sub-RAT123/sub-RAT123.nwb"


def test_smoke_local_schema(simple1_nwb: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(
        ls,
        [
            "-f",
            "json",
            "--schema",
            DANDI_SCHEMA_VERSION,
            str(simple1_nwb),
        ],
    )
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    out = r.stdout
    metadata = json.loads(out)
    assert len(metadata) == 1
    assert metadata[0]["digest"] == {"dandi:dandi-etag": ANY}
