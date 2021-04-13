import json
import os
from pathlib import Path

from jsonschema import Draft6Validator
import pytest
import requests

from ..models import (
    AccessType,
    AssetMeta,
    DandisetMeta,
    DigestType,
    IdentifierType,
    LicenseType,
    ParticipantRelationType,
    PublishedDandisetMeta,
    RelationType,
    RoleType,
    to_datacite,
)

METADATA_DIR = Path(__file__).with_name("data") / "metadata"


def test_dandiset():
    assert DandisetMeta.unvalidated()


def test_asset():
    assert AssetMeta.unvalidated()


@pytest.mark.parametrize(
    "enumtype,values",
    [
        (
            AccessType,
            {
                "Open": "dandi:Open",
                "Embargoed": "dandi:Embargoed",
                "Restricted": "dandi:Restricted",
            },
        ),
        (
            RoleType,
            {
                "Author": "dandi:Author",
                "Conceptualization": "dandi:Conceptualization",
                "ContactPerson": "dandi:ContactPerson",
                "DataCollector": "dandi:DataCollector",
                "DataCurator": "dandi:DataCurator",
                "DataManager": "dandi:DataManager",
                "FormalAnalysis": "dandi:FormalAnalysis",
                "FundingAcquisition": "dandi:FundingAcquisition",
                "Investigation": "dandi:Investigation",
                "Maintainer": "dandi:Maintainer",
                "Methodology": "dandi:Methodology",
                "Producer": "dandi:Producer",
                "ProjectLeader": "dandi:ProjectLeader",
                "ProjectManager": "dandi:ProjectManager",
                "ProjectMember": "dandi:ProjectMember",
                "ProjectAdministration": "dandi:ProjectAdministration",
                "Researcher": "dandi:Researcher",
                "Resources": "dandi:Resources",
                "Software": "dandi:Software",
                "Supervision": "dandi:Supervision",
                "Validation": "dandi:Validation",
                "Visualization": "dandi:Visualization",
                "Funder": "dandi:Funder",
                "Sponsor": "dandi:Sponsor",
                "StudyParticipant": "dandi:StudyParticipant",
                "Affiliation": "dandi:Affiliation",
                "EthicsApproval": "dandi:EthicsApproval",
                "Other": "dandi:Other",
            },
        ),
        (
            RelationType,
            {
                "IsCitedBy": "dandi:IsCitedBy",
                "Cites": "dandi:Cites",
                "IsSupplementTo": "dandi:IsSupplementTo",
                "IsSupplementedBy": "dandi:IsSupplementedBy",
                "IsContinuedBy": "dandi:IsContinuedBy",
                "Continues": "dandi:Continues",
                "Describes": "dandi:Describes",
                "IsDescribedBy": "dandi:IsDescribedBy",
                "HasMetadata": "dandi:HasMetadata",
                "IsMetadataFor": "dandi:IsMetadataFor",
                "HasVersion": "dandi:HasVersion",
                "IsVersionOf": "dandi:IsVersionOf",
                "IsNewVersionOf": "dandi:IsNewVersionOf",
                "IsPreviousVersionOf": "dandi:IsPreviousVersionOf",
                "IsPartOf": "dandi:IsPartOf",
                "HasPart": "dandi:HasPart",
                "IsReferencedBy": "dandi:IsReferencedBy",
                "References": "dandi:References",
                "IsDocumentedBy": "dandi:IsDocumentedBy",
                "Documents": "dandi:Documents",
                "IsCompiledBy": "dandi:IsCompiledBy",
                "Compiles": "dandi:Compiles",
                "IsVariantFormOf": "dandi:IsVariantFormOf",
                "IsOriginalFormOf": "dandi:IsOriginalFormOf",
                "IsIdenticalTo": "dandi:IsIdenticalTo",
                "IsReviewedBy": "dandi:IsReviewedBy",
                "Reviews": "dandi:Reviews",
                "IsDerivedFrom": "dandi:IsDerivedFrom",
                "IsSourceOf": "dandi:IsSourceOf",
                "IsRequiredBy": "dandi:IsRequiredBy",
                "Requires": "dandi:Requires",
                "Obsoletes": "dandi:Obsoletes",
                "IsObsoletedBy": "dandi:IsObsoletedBy",
            },
        ),
        (
            ParticipantRelationType,
            {
                "IsChildOf": "dandi:IsChildOf",
                "IsDizygoticTwinOf": "dandi:IsDizygoticTwinOf",
                "IsMonozygoticTwinOf": "dandi:IsMonozygoticTwinOf",
                "IsSiblingOf": "dandi:IsSiblingOf",
                "isParentOf": "dandi:isParentOf",
            },
        ),
        (
            LicenseType,
            {
                "CC0": "dandi:CC0",
                "CCBY40": "dandi:CCBY40",
                "CCBYNC40": "dandi:CCBYNC40",
            },
        ),
        (
            IdentifierType,
            {
                "doi": "dandi:doi",
                "orcid": "dandi:orcid",
                "ror": "dandi:ror",
                "dandi": "dandi:dandi",
                "rrid": "dandi:rrid",
            },
        ),
        (
            DigestType,
            {
                "md5": "dandi:md5",
                "sha1": "dandi:sha1",
                "sha2_256": "dandi:sha2-256",
                "sha3_256": "dandi:sha3-256",
                "blake2b_256": "dandi:blake2b-256",
                "blake3": "dandi:blake3",
                "dandi_etag": "dandi:dandi-etag",
            },
        ),
    ],
)
def test_types(enumtype, values):
    assert {v.name: v.value for v in enumtype} == values


def test_autogenerated_titles():
    schema = AssetMeta.schema()
    assert schema["title"] == "Asset Meta"
    assert schema["properties"]["schemaVersion"]["title"] == "Schema Version"
    assert schema["definitions"]["PropertyValue"]["title"] == "Property Value"


def _clean_doi(doi):
    """removing doi, ignoring the status code"""
    requests.delete(
        f"https://api.test.datacite.org/dois/{doi.replace('/', '%2F')}",
        auth=("DARTLIB.DANDI", os.environ["DATACITE_DEV_PASSWORD"]),
    )


@pytest.mark.parametrize("dandi_nr", ["000004", "000008"])
def test_datacite(dandi_nr):
    from datetime import datetime

    prefix = "10.80507"

    with (METADATA_DIR / f"newmeta{dandi_nr}.json").open() as f:
        newmeta_js = json.load(f)

    newmeta_js["doi"] = f"{prefix}/dandi.{dandi_nr}.v.0"
    newmeta_js["datePublished"] = str(datetime.now().year)
    newmeta_js["publishedBy"] = "https://doi.test.datacite.org/dois"
    newmeta = PublishedDandisetMeta(**newmeta_js)

    datacite = to_datacite(meta=newmeta)

    sr = requests.get(
        "https://raw.githubusercontent.com/datacite/schema/master/source/"
        "json/kernel-4.3/datacite_4.3_schema.json"
    )
    schema = sr.json()
    Draft6Validator.check_schema(schema)

    vv6 = Draft6Validator(schema)
    vv6.validate(datacite["data"]["attributes"])

    # removing doi in case it exists
    _clean_doi(newmeta.doi)

    # checking f I'm able to create doi
    rp = requests.post(
        "https://api.test.datacite.org/dois",
        json=datacite,
        headers={"Content-Type": "application/vnd.api+json"},
        auth=("DARTLIB.DANDI", os.environ["DATACITE_DEV_PASSWORD"]),
    )
    assert rp.status_code == 201

    # checking if i'm able to get the url
    rg = requests.get(
        url=f"https://api.test.datacite.org/dois/{newmeta.doi.replace('/','%2F')}/activities"
    )
    assert rg.status_code == 200

    # cleaning url
    _clean_doi(newmeta.doi)


def test_dantimeta_1():
    from datetime import datetime

    # meta data without doi, datePublished and publishedBy
    meta_dict = {
        "identifier": "DANDI:912",
        "name": "testing dataset",
        "description": "testing",
        "contributor": [
            {
                "name": "last name, first name",
                "roleName": [RoleType("dandi:ContactPerson")],
            }
        ],
        "license": [LicenseType("dandi:CCBYNC40")],
    }

    # should work for DandisetMeta but PublishedDandisetMeta should raise an error
    DandisetMeta(**meta_dict)
    with pytest.raises(Exception) as exc:
        PublishedDandisetMeta(**meta_dict)

    assert [el["msg"] == "field required" for el in exc.value.errors()]
    assert set([el["loc"][0] for el in exc.value.errors()]) == {
        "datePublished",
        "publishedBy",
        "doi",
    }

    # after adding doi, datePublished, publishedBy, PublishedDandisetMeta should work
    meta_dict["doi"] = "00000"
    meta_dict["datePublished"] = datetime.now().year
    meta_dict["publishedBy"] = "https://doi.test.datacite.org/dois"
    PublishedDandisetMeta(**meta_dict)
