from datetime import datetime, timedelta
from dateutil.tz import tzutc
import pytest
from ..metadata import metadata2asset, parse_age, timedelta2duration, migrate2newschema
from ..models import (
    AccessRequirements,
    AccessType,
    AssetMeta,
    BioSample,
    Digest,
    DigestType,
    PropertyValue,
    SexType,
    SpeciesType,
    AnyUrl,
    DandiMeta,
    Participant,
    Resource,
    RoleType,
    RelationType,
    Person,
    Organization,
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
    ) == AssetMeta.unvalidated(
        schemaVersion="1.0.0-rc1",
        identifier="ABC123",
        name=None,
        description=None,
        contributor=None,
        about=None,
        studyTarget=None,
        license=None,
        protocol=None,
        ethicsApproval=None,
        keywords=["test", "sample", "example", "test-case"],
        acknowledgement=None,
        access=[
            AccessRequirements(
                status=AccessType.Open,
                email=None,
                contactPoint=None,
                description=None,
                embargoedUntil=None,
            )
        ],
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
        dataType=None,
        sameAs=None,
        modality=None,
        measurementTechnique=None,
        variableMeasured=None,
        wasDerivedFrom=[
            BioSample(
                identifier="tissue03", assayType=None, anatomy=None, wasDerivedFrom=None
            )
        ],
        wasAttributedTo=[
            Participant(
                identifier="a1b2c3",
                source_id=None,
                strain=None,
                cellLine=None,
                vendor=None,
                age=PropertyValue(
                    maxValue=None,
                    minValue=None,
                    unitCode=None,
                    unitText="Years from birth",
                    value="P170DT12212S",
                    valueReference=None,
                    propertyID=None,
                ),
                sex=SexType(
                    identifier=AnyUrl(
                        "http://purl.obolibrary.org/obo/PATO_0000384",
                        scheme="http",
                        host="purl.obolibrary.org",
                        tld="org",
                        host_type="domain",
                        path="/obo/PATO_0000384",
                    ),
                    name="Male",
                ),
                genotype="Typical",
                species=SpeciesType(
                    identifier=AnyUrl(
                        "http://purl.obolibrary.org/obo/NCBITaxon_9606",
                        scheme="http",
                        host="purl.obolibrary.org",
                        tld="org",
                        host_type="domain",
                        path="/obo/NCBITaxon_9606",
                    ),
                    name="Human",
                ),
                disorder=None,
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
        license=None,
        protocol=None,
        ethicsApproval=None,
        keywords=["keyword1", "keyword 2"],
        acknowledgement=None,
        access=[
            AccessRequirements(
                status=AccessType.Open,
                email=None,
                contactPoint=None,
                description=None,
                embargoedUntil=None,
            )
        ],
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
        dataType=None,
        sameAs=None,
        modality=None,
        measurementTechnique=None,
        variableMeasured=None,
        wasDerivedFrom=[
            BioSample.unvalidated(
                identifier=None, assayType=None, anatomy=None, wasDerivedFrom=None
            )
        ],
        wasAttributedTo=[
            Participant.unvalidated(
                identifier=None,
                source_id=None,
                strain=None,
                cellLine=None,
                vendor=None,
                age=None,
                sex=None,
                genotype=None,
                species=None,
                disorder=None,
            )
        ],
        contentUrl=None,
    )


def test_dandimeta_migration():
    assert migrate2newschema(
        {
            "dandiset": {
                "access": {
                    "access_contact_email": "nand.chandravadia@cshs.org",
                    "status": "open",
                },
                "age": {"maximum": "70", "minimum": "16", "units": "Year"},
                "associatedData": [
                    {
                        "identifier": "DOI:10.17605/OSF.IO/HV7JA",
                        "name": (
                            "A NWB-based Dataset and Processing Pipeline of"
                            " Human Single-Neuron Activity During a Declarative"
                            " Memory Task"
                        ),
                        "repository": "Open Science Framework",
                        "url": "https://osf.io/hv7ja/",
                    }
                ],
                "associated_anatomy": [
                    {"identifier": "MTL", "name": "Medial Temporal Lobe"}
                ],
                "contributors": [
                    {
                        "affiliations": [
                            "Department of Neurosurgery, Cedars-Sinai Medical"
                            " Center, Los Angeles, CA, USA"
                        ],
                        "email": "nand.chandravadia@cshs.org",
                        "name": "Nand Chandravadia",
                        "orcid": "0000-0003-0161-4007",
                        "roles": [
                            "Author",
                            "ContactPerson",
                            "DataCurator",
                            "DataManager",
                            "Formal Analysis",
                            "Investigation",
                            "Maintainer",
                            "Methodology",
                            "ProjectLeader",
                            "ProjectManager",
                            "ProjectMember",
                            "Researcher",
                            "Software",
                            "Validation",
                            "Visualization",
                        ],
                    },
                    {
                        "affiliations": [
                            "Institute for Interdisciplinary Brain and"
                            " Behavioral Sciences, Crean College of Health and"
                            " Behavioral Sciences, Schmid College of Science"
                            " and Technology, Chapman University, Orange, CA,"
                            " USA"
                        ],
                        "email": "liang134@mail.chapman.edu",
                        "name": "Dehua Liang",
                        "orcid": "",
                        "roles": [
                            "Author",
                            "Methodology",
                            "ProjectMember",
                            "Software",
                            "Validation",
                        ],
                    },
                    {
                        "affiliations": [
                            "Krembil Brain Institute, Toronto Western Hospital,"
                            " Toronto, Canada"
                        ],
                        "email": "Andrea.Schjetan@uhnresearch.ca",
                        "name": "Andrea Gomez Palacio Schjetnan",
                        "orcid": "0000-0002-4319-7689",
                        "roles": [
                            "Author",
                            "Data Collector",
                            "ProjectMember",
                            "Validation",
                        ],
                    },
                    {
                        "affiliations": [
                            "Department of Neurosurgery, Cedars-Sinai Medical"
                            " Center, Los Angeles, CA, USA"
                        ],
                        "email": "april.carlson@tufts.edu",
                        "name": "April Carlson",
                        "orcid": "0000-0002-9207-7069",
                        "roles": [
                            "Author",
                            "DataCurator",
                            "ProjectMember",
                            "Validation",
                        ],
                    },
                    {
                        "affiliations": [
                            "Department of Neurosurgery, Cedars-Sinai Medical"
                            " Center, Los Angeles, CA, USA"
                        ],
                        "email": "mailyscm.faraut@gmail.com",
                        "name": "Mailys Faraut",
                        "roles": [
                            "Author",
                            "Data Collector",
                            "ProjectMember",
                            "Validation",
                        ],
                    },
                    {
                        "affiliations": [
                            "Department of Neurology, Cedars-Sinai Medical"
                            " Center, Los Angeles, CA, USA"
                        ],
                        "email": "Jeffrey.Chung@cshs.org",
                        "name": "Jeffrey M. Chung",
                        "roles": ["Author", "ProjectMember", "Validation"],
                    },
                    {
                        "affiliations": [
                            "Department of Neurology, Cedars-Sinai Medical"
                            " Center, Los Angeles, CA, USA"
                        ],
                        "email": "Chrystal.Reed@csmc.edu",
                        "name": "Chrystal M. Reed",
                        "roles": ["Author", "ProjectMember", "Validation"],
                    },
                    {
                        "affiliations": [
                            "Biological Systems & Engineering Division,"
                            " Lawrence Berkeley National Laboratory, Berkeley,"
                            " CA, USA",
                            "Department of Neurosurgery, Stanford University,"
                            " Stanford, CA, USA",
                        ],
                        "email": "ben.dichter@gmail.com",
                        "name": "Ben Dichter",
                        "roles": ["Author", "Software", "ProjectMember", "Validation"],
                    },
                    {
                        "affiliations": [
                            "Institute for Interdisciplinary Brain and"
                            " Behavioral Sciences, Crean College of Health and"
                            " Behavioral Sciences, Schmid College of Science"
                            " and Technology, Chapman University, Orange, CA,"
                            " USA",
                            "Division of Biology and Biological Engineering,"
                            " California Institute of Technology, Pasadena,"
                            " CA, USA",
                        ],
                        "email": "maoz.uri@gmail.com",
                        "name": "Uri Maoz",
                        "roles": [
                            "Author",
                            "Conceptualization",
                            "ProjectMember",
                            "Validation",
                        ],
                    },
                    {
                        "affiliations": [
                            "Division of Neurosurgery, Department of Surgery,"
                            " University of Toronto, Toronto, Canada",
                            "Krembil Brain Institute, Toronto Western Hospital,"
                            " Toronto, Canada",
                        ],
                        "email": "suneil.kalia@uhn.ca",
                        "name": "Suneil K. Kalia",
                        "roles": ["Author", "ProjectMember", "Validation"],
                    },
                    {
                        "affiliations": [
                            "Krembil Brain Institute, Toronto Western Hospital,"
                            " Toronto, Canada",
                            "Division of Neurosurgery, Department of Surgery,"
                            " University of Toronto, Toronto, Canada",
                        ],
                        "email": "Taufik.Valiante@uhn.ca",
                        "name": "Taufik A. Valiante",
                        "roles": ["Author", "ProjectMember", "Validation"],
                    },
                    {
                        "affiliations": [
                            "Department of Neurosurgery, Cedars-Sinai Medical"
                            " Center, Los Angeles, CA, USA"
                        ],
                        "email": "Adam.Mamelak@cshs.org",
                        "name": "Adam N. Mamelak",
                        "roles": ["Author", "ProjectMember", "Validation"],
                    },
                    {
                        "affiliations": [
                            "Department of Neurosurgery, Cedars-Sinai Medical"
                            " Center, Los Angeles, CA, USA",
                            "Department of Neurology, Cedars-Sinai Medical"
                            " Center, Los Angeles, CA, USA",
                            "Division of Biology and Biological Engineering,"
                            " California Institute of Technology, Pasadena, CA, USA",
                            "Computational and Neural Systems Program,"
                            " California Institute of Technology, Pasadena, CA, USA",
                            "Center for Neural Science and Medicine,"
                            " Department of Biomedical Science, Cedars-Sinai"
                            " Medical Center, Los Angeles, CA, USA",
                        ],
                        "email": "Ueli.Rutishauser@cshs.org",
                        "name": "Ueli Rutishauser",
                        "orcid": "0000-0002-9207-7069",
                        "roles": [
                            "Author",
                            "Conceptualization",
                            "Funding acquisition",
                            "ProjectMember",
                            "Resources",
                            "Software",
                            "Supervision",
                            "Validation",
                        ],
                    },
                ],
                "description": (
                    "A challenge for data sharing in systems neuroscience is"
                    " the multitude of different data formats used. Neurodata"
                    " Without Borders: Neurophysiology 2.0 (NWB:N) has emerged"
                    " as a standardized data format for the storage of"
                    " cellular-level data together with meta-data, stimulus"
                    " information, and behavior. A key next step to facilitate"
                    " NWB:N adoption is to provide easy to use processing"
                    " pipelines to import/export data from/to NWB:N. Here, we"
                    " present a NWB-formatted dataset of 1863 single neurons"
                    " recorded from the medial temporal lobes of 59 human"
                    " subjects undergoing intracranial monitoring while they"
                    " performed a recognition memory task. We provide code to"
                    " analyze and export/import stimuli, behavior, and"
                    " electrophysiological recordings to/from NWB in both"
                    " MATLAB and Python. The data files are NWB:N compliant,"
                    " which affords interoperability between programming"
                    " languages and operating systems. This combined data and"
                    " code release is a case study for how to utilize NWB:N"
                    " for human single-neuron recordings and enables easy"
                    " re-use of this hard-to-obtain data for both teaching and"
                    " research on the mechanisms of human memory."
                ),
                "identifier": "000004",
                "keywords": [
                    "cognitive neuroscience",
                    "data standardization",
                    "decision making",
                    "declarative memory",
                    "neurophysiology",
                    "neurosurgery",
                    "NWB",
                    "open source",
                    "single-neurons",
                ],
                "language": "English",
                "license": "CC-BY-4.0",
                "name": (
                    "A NWB-based dataset and processing pipeline of human"
                    " single-neuron activity during a declarative memory task"
                ),
                "number_of_subjects": 59,
                "organism": [{"species": "Homo sapiens"}],
                "publications": [
                    {
                        "identifier": "DOI:10.1038/s41597-020-0415-9",
                        "relation": "Initial Publication",
                        "url": "https://www.nature.com/articles/s41597-020-0415-9",
                    }
                ],
                "sex": ["F", "M"],
                "sponsors": [
                    {
                        "awardNumber": "U01NS103792",
                        "name": "National Institute of Neurological Disorders and Stroke",
                    },
                    {"awardNumber": "1554105", "name": "National Science Foundation"},
                    {
                        "awardNumber": "R01MH110831",
                        "name": "National Institute of Mental Health",
                    },
                    {"name": "McKnight Endowment for Neuroscience"},
                    {
                        "name": (
                            "NARSAD Young Investigator grant from the Brain &"
                            " Behavior Research Foundation"
                        )
                    },
                    {"name": "Kavli Foundation"},
                    {"awardNumber": "U19NS104590", "name": "BRAIN initiative"},
                ],
            }
        }
    ) == DandiMeta.unvalidated(
        access=[
            AccessRequirements(
                status=AccessType.Open,
                email="nand.chandravadia@cshs.org",
                contactPoint=None,
                description=None,
                embargoedUntil=None,
            )
        ],
        relatedResource=[
            Resource(
                identifier="DOI:10.17605/OSF.IO/HV7JA",
                name="A NWB-based Dataset and Processing Pipeline of Human Single-Neuron Activity During a Declarative Memory Task",
                repository="Open Science Framework",
                url="https://osf.io/hv7ja/",
                relation=RelationType.IsDerivedFrom,
            ),
            Resource(
                identifier="DOI:10.1038/s41597-020-0415-9",
                relation=RelationType.IsDescribedBy,
                url="https://www.nature.com/articles/s41597-020-0415-9",
                name=None,
                repository=None,
            ),
        ],
        about=[{"identifier": "MTL", "name": "Medial Temporal Lobe"}],
        contributor=[
            Person(
                roleName=[
                    RoleType.Author,
                    RoleType.ContactPerson,
                    RoleType.DataCurator,
                    RoleType.DataManager,
                    RoleType.FormalAnalysis,
                    RoleType.Investigation,
                    RoleType.Maintainer,
                    RoleType.Methodology,
                    RoleType.ProjectLeader,
                    RoleType.ProjectManager,
                    RoleType.ProjectMember,
                    RoleType.Researcher,
                    RoleType.Software,
                    RoleType.Validation,
                    RoleType.Visualization,
                ],
                identifier=PropertyValue(
                    maxValue=None,
                    minValue=None,
                    unitCode=None,
                    unitText=None,
                    value="0000-0003-0161-4007",
                    valueReference=None,
                    propertyID="ORCID",
                ),
                email="nand.chandravadia@cshs.org",
                name="Chandravadia, Nand",
                affiliation=[
                    Organization(
                        name="Department of Neurosurgery, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    )
                ],
                url=None,
                includeInCitation=True,
                awardNumber=None,
            ),
            Person(
                roleName=[
                    RoleType.Author,
                    RoleType.Methodology,
                    RoleType.ProjectMember,
                    RoleType.Software,
                    RoleType.Validation,
                ],
                identifier=PropertyValue(
                    maxValue=None,
                    minValue=None,
                    unitCode=None,
                    unitText=None,
                    value=None,
                    valueReference=None,
                    propertyID=None,
                ),
                email="liang134@mail.chapman.edu",
                name="Liang, Dehua",
                affiliation=[
                    Organization(
                        name="Institute for Interdisciplinary Brain and Behavioral Sciences, Crean College of Health and Behavioral Sciences, Schmid College of Science and Technology, Chapman University, Orange, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    )
                ],
                url=None,
                includeInCitation=True,
                awardNumber=None,
            ),
            Person(
                roleName=[
                    RoleType.Author,
                    RoleType.DataCollector,
                    RoleType.ProjectMember,
                    RoleType.Validation,
                ],
                identifier=PropertyValue(
                    maxValue=None,
                    minValue=None,
                    unitCode=None,
                    unitText=None,
                    value="0000-0002-4319-7689",
                    valueReference=None,
                    propertyID="ORCID",
                ),
                email="Andrea.Schjetan@uhnresearch.ca",
                name="Schjetnan, Andrea Gomez Palacio",
                affiliation=[
                    Organization(
                        name="Krembil Brain Institute, Toronto Western Hospital, Toronto, Canada",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    )
                ],
                url=None,
                includeInCitation=True,
                awardNumber=None,
            ),
            Person(
                roleName=[
                    RoleType.Author,
                    RoleType.DataCurator,
                    RoleType.ProjectMember,
                    RoleType.Validation,
                ],
                identifier=PropertyValue(
                    maxValue=None,
                    minValue=None,
                    unitCode=None,
                    unitText=None,
                    value="0000-0002-9207-7069",
                    valueReference=None,
                    propertyID="ORCID",
                ),
                email="april.carlson@tufts.edu",
                name="Carlson, April",
                affiliation=[
                    Organization(
                        name="Department of Neurosurgery, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    )
                ],
                url=None,
                includeInCitation=True,
                awardNumber=None,
            ),
            Person(
                roleName=[
                    RoleType.Author,
                    RoleType.DataCollector,
                    RoleType.ProjectMember,
                    RoleType.Validation,
                ],
                email="mailyscm.faraut@gmail.com",
                name="Faraut, Mailys",
                affiliation=[
                    Organization(
                        name="Department of Neurosurgery, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    )
                ],
                identifier=None,
                url=None,
                includeInCitation=True,
                awardNumber=None,
            ),
            Person(
                roleName=[RoleType.Author, RoleType.ProjectMember, RoleType.Validation],
                email="Jeffrey.Chung@cshs.org",
                name="Chung, Jeffrey M.",
                affiliation=[
                    Organization(
                        name="Department of Neurology, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    )
                ],
                identifier=None,
                url=None,
                includeInCitation=True,
                awardNumber=None,
            ),
            Person(
                roleName=[RoleType.Author, RoleType.ProjectMember, RoleType.Validation],
                email="Chrystal.Reed@csmc.edu",
                name="Reed, Chrystal M.",
                affiliation=[
                    Organization(
                        name="Department of Neurology, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    )
                ],
                identifier=None,
                url=None,
                includeInCitation=True,
                awardNumber=None,
            ),
            Person(
                roleName=[
                    RoleType.Author,
                    RoleType.Software,
                    RoleType.ProjectMember,
                    RoleType.Validation,
                ],
                email="ben.dichter@gmail.com",
                name="Dichter, Ben",
                affiliation=[
                    Organization(
                        name="Biological Systems & Engineering Division, Lawrence Berkeley National Laboratory, Berkeley, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    ),
                    Organization(
                        name="Department of Neurosurgery, Stanford University, Stanford, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    ),
                ],
                identifier=None,
                url=None,
                includeInCitation=True,
                awardNumber=None,
            ),
            Person(
                roleName=[
                    RoleType.Author,
                    RoleType.Conceptualization,
                    RoleType.ProjectMember,
                    RoleType.Validation,
                ],
                email="maoz.uri@gmail.com",
                name="Maoz, Uri",
                affiliation=[
                    Organization(
                        name="Institute for Interdisciplinary Brain and Behavioral Sciences, Crean College of Health and Behavioral Sciences, Schmid College of Science and Technology, Chapman University, Orange, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    ),
                    Organization(
                        name="Division of Biology and Biological Engineering, California Institute of Technology, Pasadena, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    ),
                ],
                identifier=None,
                url=None,
                includeInCitation=True,
                awardNumber=None,
            ),
            Person(
                roleName=[RoleType.Author, RoleType.ProjectMember, RoleType.Validation],
                email="suneil.kalia@uhn.ca",
                name="Kalia, Suneil K.",
                affiliation=[
                    Organization(
                        name="Division of Neurosurgery, Department of Surgery, University of Toronto, Toronto, Canada",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    ),
                    Organization(
                        name="Krembil Brain Institute, Toronto Western Hospital, Toronto, Canada",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    ),
                ],
                identifier=None,
                url=None,
                includeInCitation=True,
                awardNumber=None,
            ),
            Person(
                roleName=[RoleType.Author, RoleType.ProjectMember, RoleType.Validation],
                email="Taufik.Valiante@uhn.ca",
                name="Valiante, Taufik A.",
                affiliation=[
                    Organization(
                        name="Krembil Brain Institute, Toronto Western Hospital, Toronto, Canada",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    ),
                    Organization(
                        name="Division of Neurosurgery, Department of Surgery, University of Toronto, Toronto, Canada",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    ),
                ],
                identifier=None,
                url=None,
                includeInCitation=True,
                awardNumber=None,
            ),
            Person(
                roleName=[RoleType.Author, RoleType.ProjectMember, RoleType.Validation],
                email="Adam.Mamelak@cshs.org",
                name="Mamelak, Adam N.",
                affiliation=[
                    Organization(
                        name="Department of Neurosurgery, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    )
                ],
                identifier=None,
                url=None,
                includeInCitation=True,
                awardNumber=None,
            ),
            Person(
                roleName=[
                    RoleType.Author,
                    RoleType.Conceptualization,
                    RoleType.FundingAcquisition,
                    RoleType.ProjectMember,
                    RoleType.Resources,
                    RoleType.Software,
                    RoleType.Supervision,
                    RoleType.Validation,
                ],
                identifier=PropertyValue(
                    maxValue=None,
                    minValue=None,
                    unitCode=None,
                    unitText=None,
                    value="0000-0002-9207-7069",
                    valueReference=None,
                    propertyID="ORCID",
                ),
                email="Ueli.Rutishauser@cshs.org",
                name="Rutishauser, Ueli",
                affiliation=[
                    Organization(
                        name="Department of Neurosurgery, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    ),
                    Organization(
                        name="Department of Neurology, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    ),
                    Organization(
                        name="Division of Biology and Biological Engineering, California Institute of Technology, Pasadena, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    ),
                    Organization(
                        name="Computational and Neural Systems Program, California Institute of Technology, Pasadena, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    ),
                    Organization(
                        name="Center for Neural Science and Medicine, Department of Biomedical Science, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
                        identifier=None,
                        email=None,
                        url=None,
                        roleName=None,
                        includeInCitation=False,
                        awardNumber=None,
                        contactPoint=None,
                    ),
                ],
                url=None,
                includeInCitation=True,
                awardNumber=None,
            ),
            Organization(
                awardNumber="U01NS103792",
                name="Stroke, National Institute of Neurological Disorders and",
                identifier=None,
                email=None,
                url=None,
                roleName=[RoleType.Sponsor],
                includeInCitation=False,
                contactPoint=None,
            ),
            Organization(
                awardNumber="1554105",
                name="Foundation, National Science",
                identifier=None,
                email=None,
                url=None,
                roleName=[RoleType.Sponsor],
                includeInCitation=False,
                contactPoint=None,
            ),
            Organization(
                awardNumber="R01MH110831",
                name="Health, National Institute of Mental",
                identifier=None,
                email=None,
                url=None,
                roleName=[RoleType.Sponsor],
                includeInCitation=False,
                contactPoint=None,
            ),
            Person(
                name="Neuroscience, McKnight Endowment for",
                identifier=None,
                email=None,
                url=None,
                roleName=[RoleType.Sponsor],
                includeInCitation=True,
                awardNumber=None,
                affiliation=None,
            ),
            Person(
                name="Foundation, NARSAD Young Investigator grant from the Brain & Behavior Research",
                identifier=None,
                email=None,
                url=None,
                roleName=[RoleType.Sponsor],
                includeInCitation=True,
                awardNumber=None,
                affiliation=None,
            ),
            Person(
                name="Foundation, Kavli",
                identifier=None,
                email=None,
                url=None,
                roleName=[RoleType.Sponsor],
                includeInCitation=True,
                awardNumber=None,
                affiliation=None,
            ),
            Organization(
                awardNumber="U19NS104590",
                name="initiative, BRAIN",
                identifier=None,
                email=None,
                url=None,
                roleName=[RoleType.Sponsor],
                includeInCitation=False,
                contactPoint=None,
            ),
        ],
        description="A challenge for data sharing in systems neuroscience is the multitude of different data formats used. Neurodata Without Borders: Neurophysiology 2.0 (NWB:N) has emerged as a standardized data format for the storage of cellular-level data together with meta-data, stimulus information, and behavior. A key next step to facilitate NWB:N adoption is to provide easy to use processing pipelines to import/export data from/to NWB:N. Here, we present a NWB-formatted dataset of 1863 single neurons recorded from the medial temporal lobes of 59 human subjects undergoing intracranial monitoring while they performed a recognition memory task. We provide code to analyze and export/import stimuli, behavior, and electrophysiological recordings to/from NWB in both MATLAB and Python. The data files are NWB:N compliant, which affords interoperability between programming languages and operating systems. This combined data and code release is a case study for how to utilize NWB:N for human single-neuron recordings and enables easy re-use of this hard-to-obtain data for both teaching and research on the mechanisms of human memory.",
        identifier=PropertyValue(
            maxValue=None,
            minValue=None,
            unitCode=None,
            unitText=None,
            value="000004",
            valueReference=None,
            propertyID="DANDI",
        ),
        keywords=[
            "cognitive neuroscience",
            "data standardization",
            "decision making",
            "declarative memory",
            "neurophysiology",
            "neurosurgery",
            "NWB",
            "open source",
            "single-neurons",
        ],
        license="CC-BY-4.0",
        name="A NWB-based dataset and processing pipeline of human single-neuron activity during a declarative memory task",
        schemaVersion="1.0.0-rc1",
        studyTarget=None,
        protocol=None,
        ethicsApproval=None,
        acknowledgement=None,
        url=None,
        repository="https://dandiarchive.org/",
        wasGeneratedBy=None,
        citation=None,
        assetsSummary=None,
        manifestLocation=None,
        version=None,
        doi=None,
    )
