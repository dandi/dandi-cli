from datetime import datetime, timedelta
from dateutil.tz import tzutc
import pytest
from ..metadata import metadata2asset, parse_age, timedelta2duration
from ..models import (
    AccessRequirements,
    AccessType,
    AssetMeta,
    BioSample,
    Digest,
    DigestType,
    PropertyValue,
    SexType,
)


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


def test_metadata2asset():
    assert metadata2asset(
        {
            "contentSize": 69105,
            "digest": "783ad2afe455839e5ab2fa659861f58a423fd17f",
            "digest_type": "sha1",
            "encodingFormat": "application/x-nwb",
            "experiment_description": "Experiment Description",
            "experimenter": "Joe Q. Experimenter",
            "identifier": "ABC123",
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
            "species": "Examen exemplar",
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
    ) == AssetMeta.unvalidated(
        schemaVersion="1.0.0-rc1",
        identifier="ABC123",
        name=None,
        description=None,
        contributor=None,
        about=None,
        studyTarget=None,
        protocol=None,
        ethicsApproval=None,
        license=None,
        keywords=["test", "sample", "example", "test-case"],
        acknowledgement=None,
        access=[AccessRequirements(status=AccessType.Open)],
        url=None,
        repository="https://dandiarchive.org/",
        relatedResource=None,
        wasGeneratedBy=None,
        contentSize=69105,
        encodingFormat="application/x-nwb",
        digest=Digest(
            value="783ad2afe455839e5ab2fa659861f58a423fd17f", cryptoType=DigestType.sha1
        ),
        path=None,
        isPartOf=None,
        dataType=None,
        sameAs=None,
        modality=None,
        measurementTechnique=None,
        variableMeasured=None,
        wasDerivedFrom=[
            BioSample(
                identifier="a1b2c3",
                assayType=None,
                anatomy=None,
                strain=None,
                cellLine=None,
                vendor=None,
                age=PropertyValue(value="P170DT12212S", unitText="Years from birth"),
                sex=SexType(identifier="sex", name="M"),
                taxonomy=None,
                disease=None,
            )
        ],
        contentUrl=None,
    )


def test_metadata2asset_simple1():
    assert metadata2asset(
        {
            "contentSize": 69105,
            "digest": "783ad2afe455839e5ab2fa659861f58a423fd17f",
            "digest_type": "sha1",
            "encodingFormat": "application/x-nwb",
            "nwb_version": "2.2.5",
            "experiment_description": "experiment_description1",
            "experimenter": ("experimenter1",),
            "identifier": "identifier1",
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
            "subject_id": None,
            "number_of_electrodes": 0,
            "number_of_units": 0,
            "nd_types": [],
        }
    ) == AssetMeta.unvalidated(
        schemaVersion="1.0.0-rc1",
        identifier="identifier1",
        name=None,
        description=None,
        contributor=None,
        about=None,
        studyTarget=None,
        protocol=None,
        ethicsApproval=None,
        license=None,
        keywords=["keyword1", "keyword 2"],
        acknowledgement=None,
        access=[AccessRequirements(status=AccessType.Open)],
        url=None,
        repository="https://dandiarchive.org/",
        relatedResource=None,
        wasGeneratedBy=None,
        contentSize=69105,
        encodingFormat="application/x-nwb",
        digest=Digest(
            value="783ad2afe455839e5ab2fa659861f58a423fd17f", cryptoType=DigestType.sha1
        ),
        path=None,
        isPartOf=None,
        dataType=None,
        sameAs=None,
        modality=None,
        measurementTechnique=None,
        variableMeasured=None,
        wasDerivedFrom=[
            BioSample.unvalidated(
                identifier=None,
                assayType=None,
                anatomy=None,
                strain=None,
                cellLine=None,
                vendor=None,
                age=None,
                sex=None,
                taxonomy=None,
                disease=None,
            )
        ],
        contentUrl=None,
    )
