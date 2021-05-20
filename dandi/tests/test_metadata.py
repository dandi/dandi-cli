from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path

from dandischema.consts import DANDI_SCHEMA_VERSION
from dandischema.metadata import (
    publish_model_schemata,
    validate_asset_json,
    validate_dandiset_json,
)
from dandischema.models import BareAssetMeta, DandisetMeta
from dateutil.tz import tzutc
import pytest

from ..metadata import get_metadata, metadata2asset, parse_age, timedelta2duration
from ..pynwb_utils import metadata_nwb_subject_fields

METADATA_DIR = Path(__file__).with_name("data") / "metadata"


@pytest.fixture(scope="module")
def schema_dir(tmp_path_factory):
    return publish_model_schemata(tmp_path_factory.mktemp("schema_dir"))


def test_get_metadata(simple1_nwb, simple1_nwb_metadata):
    target_metadata = simple1_nwb_metadata.copy()
    # we will also get some counts
    target_metadata["number_of_electrodes"] = 0
    target_metadata["number_of_units"] = 0
    target_metadata["number_of_units"] = 0
    # We also populate with nd_types now, although here they would be empty
    target_metadata["nd_types"] = []
    # we do not populate any subject fields in our simple1_nwb
    for f in metadata_nwb_subject_fields:
        target_metadata[f] = None
    metadata = get_metadata(str(simple1_nwb))
    # we also load nwb_version field, so it must not be degenerate and ATM
    # it is 2.X.Y. And since I don't know how to query pynwb on what
    # version it currently "supports", we will just pop it
    assert metadata.pop("nwb_version").startswith("2.")
    assert target_metadata == metadata


@pytest.mark.parametrize(
    "age,duration",
    [
        ("5y", "P5Y"),
        ("5Y", "P5Y"),
        ("5 years", "P5Y"),
        ("1year", "P1Y"),
        ("0y", "P0Y"),
        ("2 months", "P2M"),
        ("2 M", "P2M"),
        ("2 m", "P2M"),
        ("2M", "P2M"),
        ("2m", "P2M"),
        ("3 weeks", "P3W"),
        ("3 w", "P3W"),
        ("3 W", "P3W"),
        ("3w", "P3W"),
        ("3W", "P3W"),
        ("0 days", "P0D"),
        ("7 d", "P7D"),
        ("7 D", "P7D"),
        ("7d", "P7D"),
        ("7D", "P7D"),
    ],
)
def test_parse_age(age, duration):
    assert parse_age(age) == duration


@pytest.mark.parametrize(
    "td,duration",
    [
        (timedelta(), "P0D"),
        (timedelta(weeks=3), "P21D"),
        (timedelta(seconds=42), "PT42S"),
        (timedelta(days=5, seconds=23, microseconds=2000), "P5DT23.002S"),
    ],
)
def test_timedelta2duration(td, duration):
    assert timedelta2duration(td) == duration


def test_metadata2asset(schema_dir):
    data = metadata2asset(
        {
            "contentSize": 69105,
            "digest": "783ad2afe455839e5ab2fa659861f58a423fd17f",
            "digest_type": "sha1",
            "encodingFormat": "application/x-nwb",
            "experiment_description": "Experiment Description",
            "experimenter": "Joe Q. Experimenter",
            "id": "dandiasset:0b0a1a0b-e3ea-4cf6-be94-e02c830d54be",
            "institution": "University College",
            "keywords": ["test", "sample", "example", "test-case"],
            "lab": "Retriever Laboratory",
            "related_publications": "A Brief History of Test Cases",
            "session_description": "Some test data",
            "session_id": "XYZ789",
            "session_start_time": "2020-08-31T15:58:28-04:00",
            "age": "23 days",
            "date_of_birth": "2020-03-14T12:34:56-04:00",
            "genotype": "Typical",
            "sex": "M",
            "species": "human",
            "subject_id": "a1b2c3",
            "cell_id": "cell01",
            "slice_id": "slice02",
            "tissue_sample_id": "tissue03",
            "probe_ids": "probe04",
            "number_of_electrodes": 42,
            "number_of_units": 6,
            "nwb_version": "2.2.5",
            "nd_types": [
                "Device (2)",
                "DynamicTable",
                "ElectricalSeries",
                "ElectrodeGroup",
                "Subject",
            ],
        }
    )
    with (METADATA_DIR / "metadata2asset.json").open() as fp:
        data_as_dict = json.load(fp)
    data_as_dict["schemaVersion"] = DANDI_SCHEMA_VERSION
    assert data == BareAssetMeta(**data_as_dict)
    bare_dict = deepcopy(data_as_dict)
    assert data.json_dict() == bare_dict
    validate_asset_json(data_as_dict, schema_dir)


def test_metadata2asset_simple1(schema_dir):
    data = metadata2asset(
        {
            "contentSize": 69105,
            "digest": "783ad2afe455839e5ab2fa659861f58a423fd17f",
            "digest_type": "sha1",
            "encodingFormat": "application/x-nwb",
            "nwb_version": "2.2.5",
            "experiment_description": "experiment_description1",
            "experimenter": ("experimenter1",),
            "id": "dandiasset:bfc23fb6192b41c083a7257e09a3702b",
            "institution": "institution1",
            "keywords": ["keyword1", "keyword 2"],
            "lab": "lab1",
            "related_publications": ("related_publications1",),
            "session_description": "session_description1",
            "session_id": "session_id1",
            "session_start_time": datetime(2017, 4, 15, 12, 0, tzinfo=tzutc()),
            "age": None,
            "date_of_birth": None,
            "genotype": None,
            "sex": None,
            "species": None,
            "subject_id": "sub-01",
            "number_of_electrodes": 0,
            "number_of_units": 0,
            "nd_types": [],
            "tissue_sample_id": "tissue42",
        }
    )
    with (METADATA_DIR / "metadata2asset_simple1.json").open() as fp:
        data_as_dict = json.load(fp)
    data_as_dict["schemaVersion"] = DANDI_SCHEMA_VERSION
    assert data == BareAssetMeta(**data_as_dict)
    bare_dict = deepcopy(data_as_dict)
    assert data.json_dict() == bare_dict
    validate_asset_json(data_as_dict, schema_dir)


def test_dandimeta_migration(schema_dir):
    with (METADATA_DIR / "dandimeta_migration.new.json").open() as fp:
        data_as_dict = json.load(fp)
    data_as_dict["schemaVersion"] = DANDI_SCHEMA_VERSION
    DandisetMeta(**data_as_dict)
    validate_dandiset_json(data_as_dict, schema_dir)
