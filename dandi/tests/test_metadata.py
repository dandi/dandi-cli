from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import shutil
from typing import Any

from anys import ANY_AWARE_DATETIME, AnyFullmatch, AnyIn
from dandischema.consts import DANDI_SCHEMA_VERSION
from dandischema.metadata import validate
from dandischema.models import (
    AccessRequirements,
    AccessType,
    Activity,
    AgeReferenceType,
    BareAsset,
)
from dandischema.models import (
    DigestType,
    Participant,
    PropertyValue,
    Session,
    SexType,
    Software,
    SpeciesType,
)
from dandischema.models import Dandiset as DandisetMeta
from dateutil.tz import tzutc
from pydantic import ByteSize
import pytest
import requests
from semantic_version import Version

from .fixtures import SampleDandiset
from .skip import mark
from .. import __version__
from ..consts import metadata_nwb_subject_fields
from ..dandiapi import RemoteBlobAsset
from ..metadata.core import prepare_metadata
from ..metadata.nwb import get_metadata, nwb2asset
from ..metadata.util import (
    extract_age,
    extract_cellLine,
    extract_species,
    parse_age,
    parse_purlobourl,
    process_ndtypes,
    species_map,
    timedelta2duration,
)
from ..misctypes import DUMMY_DANDI_ETAG
from ..utils import ensure_datetime

METADATA_DIR = Path(__file__).with_name("data") / "metadata"

mark_xfail_ontobee = pytest.mark.xfail(
    condition="not config.getoption('--scheduled')",
    reason="Flaky ontobee site",
    strict=False,
    raises=requests.RequestException,
)


def test_get_metadata(simple1_nwb: Path, simple1_nwb_metadata: dict[str, Any]) -> None:
    target_metadata = simple1_nwb_metadata.copy()
    # we will also get some counts
    target_metadata["number_of_electrodes"] = 0
    target_metadata["number_of_units"] = 0
    target_metadata["number_of_units"] = 0
    # We also populate with nd_types now, although here they would be empty
    target_metadata["nd_types"] = []
    target_metadata["external_file_objects"] = []
    # we do not populate any subject fields in our simple1_nwb
    for f in metadata_nwb_subject_fields:
        target_metadata[f] = None
    metadata = get_metadata(simple1_nwb)
    # we also load nwb_version field, so it must not be degenerate and ATM
    # it is 2.X.Y. And since I don't know how to query pynwb on what
    # version it currently "supports", we will just pop it
    assert metadata.pop("nwb_version").startswith("2.")
    assert target_metadata == metadata


def test_bids_nwb_metadata_integration(bids_examples: Path, tmp_path: Path) -> None:
    """
    Notes
    -----
    * Generating data manually here, as fixture workflow calls `new_dandiset`,
        which requires spinning up docker:
        https://github.com/dandi/dandi-cli/pull/1183#discussion_r1061622910
    """

    source_dpath = bids_examples / "ieeg_epilepsyNWB"
    dpath = tmp_path / "ieeg_epilepsyNWB"
    shutil.copytree(source_dpath, dpath)

    file_path = (
        dpath
        / "sub-01"
        / "ses-postimp"
        / "ieeg"
        / "sub-01_ses-postimp_task-seizure_run-01_ieeg.nwb"
    )
    metadata = get_metadata(file_path)
    # This is a key sourced from both NWB and BIDS:
    assert metadata["subject_id"] == "01"
    # This is a key sourced from NWB only:
    assert metadata["sex"] == "U"


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
        ("2mo", "P2M"),
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
        ("7 day", "P7D"),
        ("7 Days", "P7D"),
        ("7.5 Days", "P7.5D"),
        ("7.0 Days", "P7D"),
        ("P136D", "P136D"),
        ("P22265.0D", "P22265.0D"),  # "P22265.D" is not allowed
        ("P22265,0D", "P22265.0D"),
        ("P2DT10H20M", "P2DT10H20M"),
        ("P2DT10.5H", "P2DT10.5H"),
        ("P2DT10,5H", "P2DT10.5H"),
        ("349 days, 4 hours", "P349DT4H"),
        ("4 days, 4.5 hours", "P4DT4.5H"),
        ("12 weeks, 13 d; 10 hours, 30 min 1sec", "P12W13DT10H30M1S"),
        ("342 days, 4:30:02", "P342DT4H30M2S"),
        ("342 days, 00:00:00", "P342DT0H0M0S"),
        ("14 (Units: days)", "P14D"),
        ("14 unit day", "P14D"),
        ("Gestational Week 19", ("P19W", "Gestational")),
        ("P100D/P200D", "P100D/P200D"),
        ("P1DT10H/P1DT20H", "P1DT10H/P1DT20H"),
        ("P1DT10H/P1DT10H20M", "P1DT10H/P1DT10H20M"),
        ("P100D / P200D ", "P100D/P200D"),
        ("/P200D", "/P200D"),
        ("P100D/", "P100D/"),
        ("/", "/"),
    ],
)
def test_parse_age(age: str, duration: str | tuple[str, str]) -> None:
    if isinstance(duration, tuple):
        duration, ref = duration
    else:  # birth will be a default ref
        ref = "Birth"
    assert parse_age(age) == (duration, ref)


@pytest.mark.parametrize(
    "s, t",
    [
        ("cellline: abcdef/1", "abcdef/1"),
        ("CellLine:  cellline:1 ", "cellline:1"),
        ("cell line: 1", None),
    ],
)
def test_extract_cellLine(s, t):
    assert extract_cellLine({"strain": s}) == t


@pytest.mark.parametrize(
    "age, errmsg",
    [
        ("123", "Cannot parse age '123': no rules to convert '123'"),
        ("P12", "ISO 8601 expected, but 'P12' was received"),
        (
            "3-7 months",
            "Cannot parse age '3-7 months': no rules to convert '3-7 months'",
        ),
        (
            "3 months, some extra",
            "Cannot parse age '3 months, some extra': no rules to convert 'some extra'",
        ),
        (" , ", "Age doesn't have any information"),
        ("", "Age is empty"),
        (None, "Age is empty"),
        ("P2DT10.5H10M", "Decimal fraction allowed in the lowest order part only."),
        (
            "4.5 hours 10 sec",
            "Decimal fraction allowed in the lowest order part only.",
        ),
        (
            "14 /",
            "Ages that use / for range need to use ISO8601 format, but '14' found.",
        ),
        (
            "P12Y/P10Y",
            "The upper limit has to be larger than the lower limit, and they should have "
            "consistent units.",
        ),
        (
            "P12Y2W/P12Y",
            "The upper limit has to be larger than the lower limit, and they should have "
            "consistent units.",
        ),
        # the upper limit is bigger than lower, but I think we should not allow for this
        (
            "P1Y/P500D",
            "The upper limit has to be larger than the lower limit, and they should have "
            "consistent units.",
        ),
    ],
)
def test_parse_error(age: str | None, errmsg: str) -> None:
    with pytest.raises(ValueError) as excinfo:
        parse_age(age)
    assert str(excinfo.value) == errmsg


@pytest.mark.parametrize(
    "td,duration",
    [
        (timedelta(), "P0D"),
        (timedelta(weeks=3), "P21D"),
        (timedelta(seconds=42), "PT42S"),
        (timedelta(days=5, seconds=23, microseconds=2000), "P5DT23.002S"),
    ],
)
def test_timedelta2duration(td: timedelta, duration: str) -> None:
    assert timedelta2duration(td) == duration


@mark_xfail_ontobee
@mark.skipif_no_network
@pytest.mark.parametrize(
    "filename, metadata",
    [
        (
            "metadata2asset.json",
            {
                "contentSize": 69105,
                "digest": "e455839e5ab2fa659861f58a423fd17f-1",
                "digest_type": "dandi_etag",
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
                "path": "/test/path",
            },
        ),
        (
            "metadata2asset_simple1.json",
            {
                "contentSize": 69105,
                "digest": "e455839e5ab2fa659861f58a423fd17f-1",
                "digest_type": "dandi_etag",
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
                "path": "/test/path",
            },
        ),
        # Put all corner cases in this test case:
        pytest.param(
            "metadata2asset_3.json",
            {
                "contentSize": 69105,
                "digest": "e455839e5ab2fa659861f58a423fd17f-1",
                "digest_type": "dandi_etag",
                "encodingFormat": "application/x-nwb",
                "experiment_description": "Experiment Description",
                "experimenter": "Joe Q. Experimenter",
                "id": "dandiasset:0b0a1a0b-e3ea-4cf6-be94-e02c830d54be",
                "institution": "University College",
                "keywords": ["test", "sample", "example", "test-case"],
                "lab": "Retriever Laboratory",
                "related_publications": [
                    "https://doi.org/10.48324/dandi.000027/0.210831.2033"
                ],
                "session_description": "Some test data",
                "session_id": "XYZ789",
                "session_start_time": "2020-08-31T15:58:28-04:00",
                "age": "23 days",
                "date_of_birth": "2020-03-14T12:34:56-04:00",
                "genotype": "Typical",
                "sex": "M",
                "strain": "abcdef/1",
                "species": "http://purl.obolibrary.org/obo/NCBITaxon_1234175",  # Corner case
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
                "path": "/test/path",
            },
            marks=pytest.mark.obolibrary,
        ),
        # add cellline exception to a new json object
        pytest.param(
            "metadata2asset_cellline.json",
            {
                "contentSize": 69105,
                "digest": "e455839e5ab2fa659861f58a423fd17f-1",
                "digest_type": "dandi_etag",
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
                "strain": "cellline: abcdef/1",
                "species": "http://purl.obolibrary.org/obo/NCBITaxon_1234175",  # Corner case
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
                "path": "/test/path",
            },
            marks=pytest.mark.obolibrary,
        ),
    ],
)
def test_prepare_metadata(filename: str, metadata: dict[str, Any]) -> None:
    data = prepare_metadata(metadata).model_dump(mode="json", exclude_none=True)
    with (METADATA_DIR / filename).open() as fp:
        data_as_dict = json.load(fp)
    data_as_dict["schemaVersion"] = DANDI_SCHEMA_VERSION
    assert data == data_as_dict
    data_as_dict["identifier"] = "0b0a1a0b-e3ea-4cf6-be94-e02c830d54be"
    # as of schema-0.5.0 (https://github.com/dandi/dandischema/pull/52)
    # contentUrl is required, and validate below would map into Asset,
    # due to schemaKey
    if Version(DANDI_SCHEMA_VERSION) >= Version("0.5.0"):
        data_as_dict["contentUrl"] = ["http://example.com"]
    validate(data_as_dict)


def test_dandimeta_migration() -> None:
    with (METADATA_DIR / "dandimeta_migration.new.json").open() as fp:
        data_as_dict = json.load(fp)
    data_as_dict["schemaVersion"] = DANDI_SCHEMA_VERSION
    DandisetMeta(**data_as_dict)
    validate(data_as_dict)


def test_time_extract() -> None:
    # if metadata contains date_of_birth and session_start_time,
    # age will be calculated from the values
    meta_birth = {
        "session_start_time": "2020-08-31T12:21:28-04:00",
        "age": "31 days",
        "date_of_birth": "2020-07-31T12:20:00-04:00",
    }
    age_birth = extract_age(meta_birth)
    assert age_birth is not None
    assert age_birth.value == "P31DT88S"
    assert age_birth.valueReference == PropertyValue(
        value=AgeReferenceType("dandi:BirthReference")
    )

    # if metadata doesn't contain date_of_birth, the age field will be used
    meta = {"session_start_time": "2020-08-31T12:21:28-04:00", "age": "31 days"}
    age = extract_age(meta)
    assert age is not None
    assert age.value == "P31D"
    assert age.valueReference == PropertyValue(
        value=AgeReferenceType("dandi:BirthReference")
    )


def test_time_extract_gest() -> None:
    """extract age with Gestational ref"""
    meta_birth = {
        "session_start_time": "2020-08-31T12:21:28-04:00",
        "age": "Gestational week 3",
    }
    age_birth = extract_age(meta_birth)
    assert age_birth is not None
    assert age_birth.value == "P3W"
    assert age_birth.valueReference == PropertyValue(
        value=AgeReferenceType("dandi:GestationalReference")
    )


@mark_xfail_ontobee
@mark.skipif_no_network
@pytest.mark.obolibrary
@pytest.mark.parametrize(
    "url,value",
    [
        (
            "http://purl.obolibrary.org/obo/NCBITaxon_10090",
            {"rdfs:label": "Mus musculus", "oboInOwl:hasExactSynonym": "House mouse"},
        ),
        (
            "http://purl.obolibrary.org/obo/NCBITaxon_10116",
            {
                "rdfs:label": "Rattus norvegicus",
                "oboInOwl:hasExactSynonym": AnyIn(
                    ["Rat", "Rats", "Brown rat", "Norway rat"]
                ),
            },
        ),
        (
            "http://purl.obolibrary.org/obo/NCBITaxon_28584",
            {
                "rdfs:label": "Drosophila suzukii",
            },
        ),
    ],
)
def test_parseobourl(url, value):
    assert parse_purlobourl(url) == value


@mark_xfail_ontobee
@pytest.mark.obolibrary
@mark.skipif_no_network
def test_species():
    m = {"species": "http://purl.obolibrary.org/obo/NCBITaxon_28584"}
    assert extract_species(m).model_dump(mode="json", exclude_none=True) == {
        "identifier": "http://purl.obolibrary.org/obo/NCBITaxon_28584",
        "schemaKey": "SpeciesType",
        "name": "Drosophila suzukii",
    }


# all of them should match the same record
# There should be no network access -- just matching records
@pytest.mark.parametrize(
    "species",
    [
        "mongolian gerbil",
        "mongolian jird",
        "Mongolian jird",
        "http://purl.obolibrary.org/obo/NCBITaxon_10047",
        "Meriones unguiculatus",
        "Meriones Unguiculatus",
        "meriones Unguiculatus",
    ],
)
def test_species_all_possible(species: str) -> None:
    species_rec = extract_species({"species": species})
    assert species_rec
    assert species_rec.model_dump(mode="json", exclude_none=True) == {
        "identifier": "http://purl.obolibrary.org/obo/NCBITaxon_10047",
        "schemaKey": "SpeciesType",
        "name": "Meriones unguiculatus",
    }


def test_extract_unknown_species():
    with pytest.raises(ValueError) as excinfo:
        extract_species({"species": "mumba-jumba"})
    assert str(excinfo.value).startswith("Cannot interpret species field: mumba-jumba")


def test_species_map():
    # all alternative names should be lower case
    for common_names, *_ in species_map:
        for key in common_names:
            assert key.lower() == key


@pytest.mark.parametrize(
    "ndtypes,asset_dict",
    [
        (
            ["ElectricalSeries"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": [
                    "multi electrode extracellular electrophysiology recording technique"
                ],
                "variableMeasured": ["ElectricalSeries"],
            },
        ),
        (
            ["SpikeEventSeries"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": ["spike sorting technique"],
                "variableMeasured": ["SpikeEventSeries"],
            },
        ),
        (
            ["FeatureExtraction"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": ["spike sorting technique"],
                "variableMeasured": ["FeatureExtraction"],
            },
        ),
        (
            ["LFP"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": ["signal filtering technique"],
                "variableMeasured": ["LFP"],
            },
        ),
        (
            ["EventWaveform"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": ["spike sorting technique"],
                "variableMeasured": ["EventWaveform"],
            },
        ),
        (
            ["EventDetection"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": ["spike sorting technique"],
                "variableMeasured": ["EventDetection"],
            },
        ),
        (
            ["ElectrodeGroup"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": ["surgical technique"],
                "variableMeasured": ["ElectrodeGroup"],
            },
        ),
        (
            ["PatchClampSeries"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": ["patch clamp technique"],
                "variableMeasured": ["PatchClampSeries"],
            },
        ),
        (
            ["CurrentClampSeries"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": ["current clamp technique"],
                "variableMeasured": ["CurrentClampSeries"],
            },
        ),
        (
            ["CurrentClampStimulusSeries"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": ["current clamp technique"],
                "variableMeasured": ["CurrentClampStimulusSeries"],
            },
        ),
        (
            ["VoltageClampSeries"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": ["voltage clamp technique"],
                "variableMeasured": ["VoltageClampSeries"],
            },
        ),
        (
            ["VoltageClampStimulusSeries"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": ["voltage clamp technique"],
                "variableMeasured": ["VoltageClampStimulusSeries"],
            },
        ),
        (
            ["TwoPhotonSeries"],
            {
                "approach": ["microscopy approach; cell population imaging"],
                "measurementTechnique": ["two-photon microscopy technique"],
                "variableMeasured": ["TwoPhotonSeries"],
            },
        ),
        (
            ["OpticalChannel"],
            {
                "approach": ["microscopy approach; cell population imaging"],
                "measurementTechnique": ["surgical technique"],
                "variableMeasured": ["OpticalChannel"],
            },
        ),
        (
            ["ImagingPlane"],
            {
                "approach": ["microscopy approach; cell population imaging"],
                "measurementTechnique": None,
                "variableMeasured": ["ImagingPlane"],
            },
        ),
        (
            ["PlaneSegmentation"],
            {
                "approach": ["microscopy approach; cell population imaging"],
                "measurementTechnique": None,
                "variableMeasured": ["PlaneSegmentation"],
            },
        ),
        (
            ["Position"],
            {
                "approach": ["behavioral approach"],
                "measurementTechnique": ["behavioral technique"],
                "variableMeasured": ["Position"],
            },
        ),
        (
            ["SpatialSeries"],
            {
                "approach": ["behavioral approach"],
                "measurementTechnique": ["behavioral technique"],
                "variableMeasured": ["SpatialSeries"],
            },
        ),
        (
            ["BehavioralEpochs"],
            {
                "approach": ["behavioral approach"],
                "measurementTechnique": ["behavioral technique"],
                "variableMeasured": ["BehavioralEpochs"],
            },
        ),
        (
            ["BehavioralEvents"],
            {
                "approach": ["behavioral approach"],
                "measurementTechnique": ["behavioral technique"],
                "variableMeasured": ["BehavioralEvents"],
            },
        ),
        (
            ["BehavioralTimeSeries"],
            {
                "approach": ["behavioral approach"],
                "measurementTechnique": ["behavioral technique"],
                "variableMeasured": ["BehavioralTimeSeries"],
            },
        ),
        (
            ["PupilTracking"],
            {
                "approach": ["behavioral approach"],
                "measurementTechnique": ["behavioral technique"],
                "variableMeasured": ["PupilTracking"],
            },
        ),
        (
            ["EyeTracking"],
            {
                "approach": ["behavioral approach"],
                "measurementTechnique": ["behavioral technique"],
                "variableMeasured": ["EyeTracking"],
            },
        ),
        (
            ["CompassDirection"],
            {
                "approach": ["behavioral approach"],
                "measurementTechnique": ["behavioral technique"],
                "variableMeasured": ["CompassDirection"],
            },
        ),
        (
            ["ProcessingModule"],
            {
                "approach": None,
                "measurementTechnique": ["analytical technique"],
                "variableMeasured": ["ProcessingModule"],
            },
        ),
        (
            ["RGBImage"],
            {
                "approach": None,
                "measurementTechnique": ["photographic technique"],
                "variableMeasured": ["RGBImage"],
            },
        ),
        (
            ["DecompositionSeries"],
            {
                "approach": None,
                "measurementTechnique": ["fourier analysis technique"],
                "variableMeasured": ["DecompositionSeries"],
            },
        ),
        (
            ["Units"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": ["spike sorting technique"],
                "variableMeasured": ["Units"],
            },
        ),
        (
            ["Spectrum"],
            {
                "approach": None,
                "measurementTechnique": ["fourier analysis technique"],
                "variableMeasured": ["Spectrum"],
            },
        ),
        (
            ["OptogeneticStimulusSIte"],
            {
                "approach": ["optogenetic approach"],
                "measurementTechnique": None,
                "variableMeasured": ["OptogeneticStimulusSIte"],
            },
        ),
        (
            ["OptogeneticSeries"],
            {
                "approach": ["optogenetic approach"],
                "measurementTechnique": None,
                "variableMeasured": ["OptogeneticSeries"],
            },
        ),
        (
            # the tricky case of having number of instances of the data type
            # https://github.com/dandi/dandi-cli/issues/890
            ["CurrentClampSeries (94)"],
            {
                "approach": ["electrophysiological approach"],
                "measurementTechnique": ["current clamp technique"],
                "variableMeasured": ["CurrentClampSeries"],
            },
        ),
    ],
)
def test_ndtypes(ndtypes, asset_dict):
    metadata = BareAsset(
        contentSize=1,
        encodingFormat="application/x-nwb",
        digest={DigestType.dandi_etag: "0" * 32 + "-1"},
        path="test.nwb",
    )
    process_ndtypes(metadata, ndtypes)
    for key in ["approach", "measurementTechnique"]:
        if asset_dict.get(key) is None:
            assert getattr(metadata, key) == []
        else:
            assert getattr(metadata, key)[0].name == asset_dict.get(key)[0]
    key = "variableMeasured"
    assert metadata.variableMeasured[0].value == asset_dict.get(key)[0]


@mark.skipif_no_network
def test_nwb2asset(simple2_nwb: Path) -> None:
    # Classes with ANY_AWARE_DATETIME fields need to be constructed with
    # model_construct()
    assert nwb2asset(simple2_nwb, digest=DUMMY_DANDI_ETAG) == BareAsset.model_construct(
        schemaKey="Asset",
        schemaVersion=DANDI_SCHEMA_VERSION,
        keywords=["keyword1", "keyword 2"],
        access=[
            AccessRequirements(
                schemaKey="AccessRequirements", status=AccessType.OpenAccess
            )
        ],
        wasGeneratedBy=[
            Session.model_construct(
                schemaKey="Session",
                identifier="session_id1",
                name="session_id1",
                description="session_description1",
                startDate=ANY_AWARE_DATETIME,
            ),
            Activity.model_construct(
                id=AnyFullmatch(
                    r"urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
                ),
                schemaKey="Activity",
                name="Metadata generation",
                description="Metadata generated by DANDI cli",
                startDate=ANY_AWARE_DATETIME,
                endDate=ANY_AWARE_DATETIME,
                wasAssociatedWith=[
                    Software(
                        schemaKey="Software",
                        identifier="RRID:SCR_019009",
                        name="DANDI Command Line Interface",
                        version=__version__,
                        url="https://github.com/dandi/dandi-cli",
                    )
                ],
            ),
        ],
        contentSize=ByteSize(19664),
        encodingFormat="application/x-nwb",
        digest={DigestType.dandi_etag: "dddddddddddddddddddddddddddddddd-1"},
        path=str(simple2_nwb),
        dateModified=ANY_AWARE_DATETIME,
        blobDateModified=ANY_AWARE_DATETIME,
        wasAttributedTo=[
            Participant(
                identifier="mouse001",
                schemaKey="Participant",
                age=PropertyValue(
                    schemaKey="PropertyValue",
                    unitText="ISO-8601 duration",
                    value="P135DT43200S",
                    valueReference=PropertyValue(
                        schemaKey="PropertyValue",
                        value=AgeReferenceType.BirthReference,
                    ),
                ),
                sex=SexType(schemaKey="SexType", name="Unknown"),
                species=SpeciesType(
                    schemaKey="SpeciesType",
                    identifier="http://purl.obolibrary.org/obo/NCBITaxon_10090",
                    name="Mus musculus - House mouse",
                ),
            ),
        ],
        variableMeasured=[],
        measurementTechnique=[],
        approach=[],
        relatedResource=[],
    )


@pytest.mark.xfail(reason="https://github.com/dandi/dandi-cli/issues/1450")
def test_nwb2asset_remote_asset(nwb_dandiset: SampleDandiset) -> None:
    pytest.importorskip("fsspec")
    asset = nwb_dandiset.dandiset.get_asset_by_path("sub-mouse001/sub-mouse001.nwb")
    digest = asset.get_digest()
    mtime = ensure_datetime(asset.get_raw_metadata()["blobDateModified"])
    assert isinstance(asset, RemoteBlobAsset)
    r = asset.as_readable()
    # Classes with ANY_AWARE_DATETIME fields need to be constructed with
    # model_construct()
    assert nwb2asset(r, digest=digest) == BareAsset.model_construct(
        schemaKey="Asset",
        schemaVersion=DANDI_SCHEMA_VERSION,
        keywords=["keyword1", "keyword 2"],
        access=[
            AccessRequirements(
                schemaKey="AccessRequirements", status=AccessType.OpenAccess
            )
        ],
        wasGeneratedBy=[
            Session.model_construct(
                schemaKey="Session",
                identifier="session_id1",
                name="session_id1",
                description="session_description1",
                startDate=ANY_AWARE_DATETIME,
            ),
            Activity.model_construct(
                id=AnyFullmatch(
                    r"urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
                ),
                schemaKey="Activity",
                name="Metadata generation",
                description="Metadata generated by DANDI cli",
                startDate=ANY_AWARE_DATETIME,
                endDate=ANY_AWARE_DATETIME,
                wasAssociatedWith=[
                    Software(
                        schemaKey="Software",
                        identifier="RRID:SCR_019009",
                        name="DANDI Command Line Interface",
                        version=__version__,
                        url="https://github.com/dandi/dandi-cli",
                    )
                ],
            ),
        ],
        contentSize=ByteSize(asset.size),
        encodingFormat="application/x-nwb",
        digest={DigestType.dandi_etag: digest.value},
        path="sub-mouse001.nwb",
        dateModified=ANY_AWARE_DATETIME,
        blobDateModified=mtime,
        wasAttributedTo=[
            Participant(
                identifier="mouse001",
                schemaKey="Participant",
                age=PropertyValue(
                    schemaKey="PropertyValue",
                    unitText="ISO-8601 duration",
                    value="P135DT43200S",
                    valueReference=PropertyValue(
                        schemaKey="PropertyValue",
                        value=AgeReferenceType.BirthReference,
                    ),
                ),
                sex=SexType(schemaKey="SexType", name="Unknown"),
                species=SpeciesType(
                    schemaKey="SpeciesType",
                    identifier="http://purl.obolibrary.org/obo/NCBITaxon_10090",
                    name="Mus musculus - House mouse",
                ),
            ),
        ],
        variableMeasured=[],
        measurementTechnique=[],
        approach=[],
        relatedResource=[],
    )
