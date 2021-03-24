from datetime import datetime, timedelta
import json

from dateutil.tz import tzutc
import pytest

from ..consts import DANDI_SCHEMA_VERSION
from ..metadata import (
    metadata2asset,
    migrate2newschema,
    parse_age,
    publish_model_schemata,
    timedelta2duration,
    validate_asset_json,
    validate_dandiset_json,
)
from ..models import BareAssetMeta, DandisetMeta


@pytest.fixture(scope="module")
def schema_dir(tmp_path_factory):
    return publish_model_schemata(tmp_path_factory.mktemp("schema_dir"))


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
            "identifier": "6a42c273881f45e8ad4d538f7ede1437",
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
    # data.json(exclude_unset=True, exclude_none=True, indent=2)
    json_data = """{
  "identifier": "0b0a1a0b-e3ea-4cf6-be94-e02c830d54be",
  "schemaVersion": null,
  "keywords": [
    "test",
    "sample",
    "example",
    "test-case"
  ],
  "access": [
    {
      "status": "dandi:Open"
    }
  ],
  "repository": "https://dandiarchive.org/",
  "wasGeneratedBy": [
    {
      "name": "XYZ789",
      "schemaKey": "Session"
    }
  ],
  "contentSize": 69105,
  "encodingFormat": "application/x-nwb",
  "digest": [
    {
      "value": "783ad2afe455839e5ab2fa659861f58a423fd17f",
      "cryptoType": "dandi:sha1"
    }
  ],
  "wasDerivedFrom": [
    {
      "identifier": "cell01",
      "schemaKey": "BioSample",
      "sampleType": {
        "name": "cell",
        "schemaKey": "SampleType"
      },
      "wasDerivedFrom": [
        {
          "identifier": "slice02",
          "schemaKey": "BioSample",
          "sampleType": {
            "name": "slice",
            "schemaKey": "SampleType"
          },
          "wasDerivedFrom": [
            {
              "identifier": "tissue03",
              "schemaKey": "BioSample",
              "sampleType": {
                "name": "tissuesample",
                "schemaKey": "SampleType"
              }
            }
          ]
        }
      ]
    }
  ],
  "wasAttributedTo": [
    {
      "identifier": "a1b2c3",
      "age": {
        "unitText": "Years from birth",
        "value": "P170DT12212S"
      },
      "sex": {
        "identifier": "http://purl.obolibrary.org/obo/PATO_0000384",
        "name": "Male"
      },
      "genotype": "Typical",
      "species": {
        "identifier": "http://purl.obolibrary.org/obo/NCBITaxon_9606",
        "name": "Human"
      },
      "schemaKey": "Participant"
    }
  ]
}"""
    data_as_dict = json.loads(json_data)
    data_as_dict["schemaVersion"] = DANDI_SCHEMA_VERSION
    assert data == BareAssetMeta(**data_as_dict)
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
            "identifier": "bfc23fb6192b41c083a7257e09a3702b",
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
    # data.json(exclude_unset=True, exclude_none=True, indent=2)
    json_data = """{
  "schemaVersion": null,
  "identifier": "bfc23fb6192b41c083a7257e09a3702b",
  "keywords": [
    "keyword1",
    "keyword 2"
  ],
  "access": [
    {
      "status": "dandi:Open"
    }
  ],
  "repository": "https://dandiarchive.org/",
  "contentSize": 69105,
  "encodingFormat": "application/x-nwb",
  "digest": [
    {
      "value": "783ad2afe455839e5ab2fa659861f58a423fd17f",
      "cryptoType": "dandi:sha1"
    }
  ],
  "wasDerivedFrom": [
    {
      "identifier": "tissue42",
      "sampleType": {
        "name": "tissuesample",
        "schemaKey": "SampleType"
      }
    }
  ],
  "wasGeneratedBy": [
    {
        "name": "session_id1",
        "schemaKey": "Session"
    }
  ],
  "wasAttributedTo": [
    {
        "identifier": "sub-01",
        "schemaKey": "Participant"
    }
  ]
}"""
    data_as_dict = json.loads(json_data)
    data_as_dict["schemaVersion"] = DANDI_SCHEMA_VERSION
    assert data == BareAssetMeta(**data_as_dict)
    validate_asset_json(data_as_dict, schema_dir)


def test_dandimeta_migration(schema_dir):
    data = migrate2newschema(
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
    )
    # This JSON dictionary is generated with:
    # data.json(exclude_none=True, indent=2)
    json_data = """{
  "access": [
    {
      "status": "dandi:Open"
    }
  ],
  "relatedResource": [
    {
      "identifier": "DOI:10.17605/OSF.IO/HV7JA",
      "name": "A NWB-based Dataset and Processing Pipeline of Human Single-Neuron Activity During a Declarative Memory Task",
      "repository": "Open Science Framework",
      "url": "https://osf.io/hv7ja/",
      "relation": "dandi:IsDerivedFrom"
    },
    {
      "identifier": "DOI:10.1038/s41597-020-0415-9",
      "relation": "dandi:IsDescribedBy",
      "url": "https://www.nature.com/articles/s41597-020-0415-9"
    }
  ],
  "about": [
    {
      "name": "Medial Temporal Lobe",
      "schemaKey": "GenericType"
    }
  ],
  "contributor": [
    {
      "roleName": [
        "dandi:Author",
        "dandi:ContactPerson",
        "dandi:DataCurator",
        "dandi:DataManager",
        "dandi:FormalAnalysis",
        "dandi:Investigation",
        "dandi:Maintainer",
        "dandi:Methodology",
        "dandi:ProjectLeader",
        "dandi:ProjectManager",
        "dandi:ProjectMember",
        "dandi:Researcher",
        "dandi:Software",
        "dandi:Validation",
        "dandi:Visualization"
      ],
      "identifier": "0000-0003-0161-4007",
      "email": "nand.chandravadia@cshs.org",
      "name": "Chandravadia, Nand",
      "affiliation": [
        {
          "name": "Department of Neurosurgery, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        }
      ],
      "includeInCitation": true,
      "schemaKey": "Person"
    },
    {
      "roleName": [
        "dandi:Author",
        "dandi:Methodology",
        "dandi:ProjectMember",
        "dandi:Software",
        "dandi:Validation"
      ],
      "email": "liang134@mail.chapman.edu",
      "name": "Liang, Dehua",
      "affiliation": [
        {
          "name": "Institute for Interdisciplinary Brain and Behavioral Sciences, Crean College of Health and Behavioral Sciences, Schmid College of Science and Technology, Chapman University, Orange, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        }
      ],
      "includeInCitation": true,
      "schemaKey": "Person"
    },
    {
      "roleName": [
        "dandi:Author",
        "dandi:DataCollector",
        "dandi:ProjectMember",
        "dandi:Validation"
      ],
      "identifier": "0000-0002-4319-7689",
      "email": "Andrea.Schjetan@uhnresearch.ca",
      "name": "Schjetnan, Andrea Gomez Palacio",
      "affiliation": [
        {
          "name": "Krembil Brain Institute, Toronto Western Hospital, Toronto, Canada",
          "includeInCitation": false,
          "schemaKey": "Organization"
        }
      ],
      "includeInCitation": true,
      "schemaKey": "Person"
    },
    {
      "roleName": [
        "dandi:Author",
        "dandi:DataCurator",
        "dandi:ProjectMember",
        "dandi:Validation"
      ],
      "identifier": "0000-0002-9207-7069",
      "email": "april.carlson@tufts.edu",
      "name": "Carlson, April",
      "affiliation": [
        {
          "name": "Department of Neurosurgery, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        }
      ],
      "includeInCitation": true,
      "schemaKey": "Person"
    },
    {
      "roleName": [
        "dandi:Author",
        "dandi:DataCollector",
        "dandi:ProjectMember",
        "dandi:Validation"
      ],
      "email": "mailyscm.faraut@gmail.com",
      "name": "Faraut, Mailys",
      "affiliation": [
        {
          "name": "Department of Neurosurgery, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        }
      ],
      "includeInCitation": true,
      "schemaKey": "Person"
    },
    {
      "roleName": [
        "dandi:Author",
        "dandi:ProjectMember",
        "dandi:Validation"
      ],
      "email": "Jeffrey.Chung@cshs.org",
      "name": "Chung, Jeffrey M.",
      "affiliation": [
        {
          "name": "Department of Neurology, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        }
      ],
      "includeInCitation": true,
      "schemaKey": "Person"
    },
    {
      "roleName": [
        "dandi:Author",
        "dandi:ProjectMember",
        "dandi:Validation"
      ],
      "email": "Chrystal.Reed@csmc.edu",
      "name": "Reed, Chrystal M.",
      "affiliation": [
        {
          "name": "Department of Neurology, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        }
      ],
      "includeInCitation": true,
      "schemaKey": "Person"
    },
    {
      "roleName": [
        "dandi:Author",
        "dandi:Software",
        "dandi:ProjectMember",
        "dandi:Validation"
      ],
      "email": "ben.dichter@gmail.com",
      "name": "Dichter, Ben",
      "affiliation": [
        {
          "name": "Biological Systems & Engineering Division, Lawrence Berkeley National Laboratory, Berkeley, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        },
        {
          "name": "Department of Neurosurgery, Stanford University, Stanford, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        }
      ],
      "includeInCitation": true,
      "schemaKey": "Person"
    },
    {
      "roleName": [
        "dandi:Author",
        "dandi:Conceptualization",
        "dandi:ProjectMember",
        "dandi:Validation"
      ],
      "email": "maoz.uri@gmail.com",
      "name": "Maoz, Uri",
      "affiliation": [
        {
          "name": "Institute for Interdisciplinary Brain and Behavioral Sciences, Crean College of Health and Behavioral Sciences, Schmid College of Science and Technology, Chapman University, Orange, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        },
        {
          "name": "Division of Biology and Biological Engineering, California Institute of Technology, Pasadena, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        }
      ],
      "includeInCitation": true,
      "schemaKey": "Person"
    },
    {
      "roleName": [
        "dandi:Author",
        "dandi:ProjectMember",
        "dandi:Validation"
      ],
      "email": "suneil.kalia@uhn.ca",
      "name": "Kalia, Suneil K.",
      "affiliation": [
        {
          "name": "Division of Neurosurgery, Department of Surgery, University of Toronto, Toronto, Canada",
          "includeInCitation": false,
          "schemaKey": "Organization"
        },
        {
          "name": "Krembil Brain Institute, Toronto Western Hospital, Toronto, Canada",
          "includeInCitation": false,
          "schemaKey": "Organization"
        }
      ],
      "includeInCitation": true,
      "schemaKey": "Person"
    },
    {
      "roleName": [
        "dandi:Author",
        "dandi:ProjectMember",
        "dandi:Validation"
      ],
      "email": "Taufik.Valiante@uhn.ca",
      "name": "Valiante, Taufik A.",
      "affiliation": [
        {
          "name": "Krembil Brain Institute, Toronto Western Hospital, Toronto, Canada",
          "includeInCitation": false,
          "schemaKey": "Organization"
        },
        {
          "name": "Division of Neurosurgery, Department of Surgery, University of Toronto, Toronto, Canada",
          "includeInCitation": false,
          "schemaKey": "Organization"
        }
      ],
      "includeInCitation": true,
      "schemaKey": "Person"
    },
    {
      "roleName": [
        "dandi:Author",
        "dandi:ProjectMember",
        "dandi:Validation"
      ],
      "email": "Adam.Mamelak@cshs.org",
      "name": "Mamelak, Adam N.",
      "affiliation": [
        {
          "name": "Department of Neurosurgery, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        }
      ],
      "includeInCitation": true,
      "schemaKey": "Person"
    },
    {
      "roleName": [
        "dandi:Author",
        "dandi:Conceptualization",
        "dandi:FundingAcquisition",
        "dandi:ProjectMember",
        "dandi:Resources",
        "dandi:Software",
        "dandi:Supervision",
        "dandi:Validation"
      ],
      "identifier": "0000-0002-9207-7069",
      "email": "Ueli.Rutishauser@cshs.org",
      "name": "Rutishauser, Ueli",
      "affiliation": [
        {
          "name": "Department of Neurosurgery, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        },
        {
          "name": "Department of Neurology, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        },
        {
          "name": "Division of Biology and Biological Engineering, California Institute of Technology, Pasadena, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        },
        {
          "name": "Computational and Neural Systems Program, California Institute of Technology, Pasadena, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        },
        {
          "name": "Center for Neural Science and Medicine, Department of Biomedical Science, Cedars-Sinai Medical Center, Los Angeles, CA, USA",
          "includeInCitation": false,
          "schemaKey": "Organization"
        }
      ],
      "includeInCitation": true,
      "schemaKey": "Person"
    },
    {
      "roleName": [
        "dandi:Sponsor"
      ],
      "awardNumber": "U01NS103792",
      "name": "Stroke, National Institute of Neurological Disorders and",
      "includeInCitation": false,
      "schemaKey": "Organization"
    },
    {
      "roleName": [
        "dandi:Sponsor"
      ],
      "awardNumber": "1554105",
      "name": "Foundation, National Science",
      "includeInCitation": false,
      "schemaKey": "Organization"
    },
    {
      "roleName": [
        "dandi:Sponsor"
      ],
      "awardNumber": "R01MH110831",
      "name": "Health, National Institute of Mental",
      "includeInCitation": false,
      "schemaKey": "Organization"
    },
    {
      "roleName": [
        "dandi:Sponsor"
      ],
      "name": "Neuroscience, McKnight Endowment for",
      "includeInCitation": false,
      "schemaKey": "Organization"
    },
    {
      "roleName": [
        "dandi:Sponsor"
      ],
      "name": "Foundation, NARSAD Young Investigator grant from the Brain & Behavior Research",
      "includeInCitation": false,
      "schemaKey": "Organization"
    },
    {
      "roleName": [
        "dandi:Sponsor"
      ],
      "name": "Foundation, Kavli",
      "includeInCitation": false,
      "schemaKey": "Organization"
    },
    {
      "roleName": [
        "dandi:Sponsor"
      ],
      "awardNumber": "U19NS104590",
      "name": "initiative, BRAIN",
      "includeInCitation": false,
      "schemaKey": "Organization"
    }
  ],
  "description": "A challenge for data sharing in systems neuroscience is the multitude of different data formats used. Neurodata Without Borders: Neurophysiology 2.0 (NWB:N) has emerged as a standardized data format for the storage of cellular-level data together with meta-data, stimulus information, and behavior. A key next step to facilitate NWB:N adoption is to provide easy to use processing pipelines to import/export data from/to NWB:N. Here, we present a NWB-formatted dataset of 1863 single neurons recorded from the medial temporal lobes of 59 human subjects undergoing intracranial monitoring while they performed a recognition memory task. We provide code to analyze and export/import stimuli, behavior, and electrophysiological recordings to/from NWB in both MATLAB and Python. The data files are NWB:N compliant, which affords interoperability between programming languages and operating systems. This combined data and code release is a case study for how to utilize NWB:N for human single-neuron recordings and enables easy re-use of this hard-to-obtain data for both teaching and research on the mechanisms of human memory.",
  "identifier": "DANDI:000004",
  "keywords": [
    "cognitive neuroscience",
    "data standardization",
    "decision making",
    "declarative memory",
    "neurophysiology",
    "neurosurgery",
    "NWB",
    "open source",
    "single-neurons"
  ],
  "license": [
    "dandi:CCBY40"
  ],
  "name": "A NWB-based dataset and processing pipeline of human single-neuron activity during a declarative memory task",
  "schemaVersion": null,
  "repository": "https://dandiarchive.org/"
}"""
    data_as_dict = json.loads(json_data)
    data_as_dict["schemaVersion"] = DANDI_SCHEMA_VERSION
    assert data == DandisetMeta(**data_as_dict)
    validate_dandiset_json(data_as_dict, schema_dir)
