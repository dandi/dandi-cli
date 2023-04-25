from __future__ import annotations

import json
from pathlib import Path
import re

import anys
from click.testing import CliRunner
from dandischema.consts import DANDI_SCHEMA_VERSION
import pytest

from dandi import __version__
from dandi.tests.fixtures import SampleDandiset

from ..command import service_scripts

DATA_DIR = Path(__file__).with_name("data")


def test_reextract_metadata(
    monkeypatch: pytest.MonkeyPatch, nwb_dandiset: SampleDandiset
) -> None:
    pytest.importorskip("fsspec")
    asset_id = nwb_dandiset.dandiset.get_asset_by_path(
        "sub-mouse001/sub-mouse001.nwb"
    ).identifier
    monkeypatch.setenv("DANDI_API_KEY", nwb_dandiset.api.api_key)
    r = CliRunner().invoke(
        service_scripts,
        ["reextract-metadata", "--when=always", nwb_dandiset.dandiset.version_api_url],
    )
    assert r.exit_code == 0
    asset_id2 = nwb_dandiset.dandiset.get_asset_by_path(
        "sub-mouse001/sub-mouse001.nwb"
    ).identifier
    assert asset_id2 != asset_id


@pytest.mark.parametrize(
    "doi,filename",
    [
        ("10.1101/2020.01.17.909838", "biorxiv.json"),
        ("10.1523/JNEUROSCI.6157-08.2009", "jneurosci.json"),
        ("10.1016/j.neuron.2019.10.012", "neuron.json"),
        ("10.7554/eLife.48198", "elife.json"),
        ("10.1038/s41467-023-37704-5", "nature.json"),
    ],
)
def test_update_dandiset_from_doi(
    doi: str,
    filename: str,
    new_dandiset: SampleDandiset,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dandiset_id = new_dandiset.dandiset_id
    repository = new_dandiset.api.instance.gui
    monkeypatch.setenv("DANDI_API_KEY", new_dandiset.api.api_key)
    r = CliRunner().invoke(
        service_scripts,
        [
            "update-dandiset-from-doi",
            "--dandiset",
            dandiset_id,
            "--dandi-instance",
            new_dandiset.api.instance_id,
            "--existing=overwrite",
            "--yes",
            doi,
        ],
    )
    assert r.exit_code == 0
    metadata = new_dandiset.dandiset.get_raw_metadata()
    with (DATA_DIR / "update_dandiset_from_doi" / filename).open() as fp:
        expected = json.load(fp)
    expected["id"] = f"DANDI:{dandiset_id}/draft"
    expected["url"] = f"{repository}/dandiset/{dandiset_id}/draft"
    expected["@context"] = (
        "https://raw.githubusercontent.com/dandi/schema/master/releases"
        f"/{DANDI_SCHEMA_VERSION}/context.json"
    )
    expected["identifier"] = f"DANDI:{dandiset_id}"
    expected["repository"] = repository
    expected["dateCreated"] = anys.ANY_AWARE_DATETIME_STR
    expected["schemaVersion"] = DANDI_SCHEMA_VERSION
    expected["wasGeneratedBy"][0]["id"] = anys.AnyFullmatch(
        r"urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    )
    expected["wasGeneratedBy"][0]["endDate"] = anys.ANY_AWARE_DATETIME_STR
    expected["wasGeneratedBy"][0]["startDate"] = anys.ANY_AWARE_DATETIME_STR
    expected["wasGeneratedBy"][0]["wasAssociatedWith"][0]["version"] = __version__
    expected["manifestLocation"][
        0
    ] = f"{new_dandiset.api.api_url}/dandisets/{dandiset_id}/versions/draft/assets/"
    expected["citation"] = re.sub(
        r"\S+\Z",
        f"{repository}/dandiset/{dandiset_id}/draft",
        expected["citation"],
    )
    assert metadata == expected
