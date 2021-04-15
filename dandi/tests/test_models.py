import pytest

from ..models import (
    AccessType,
    AssetMeta,
    DandisetMeta,
    DigestType,
    IdentifierType,
    LicenseType,
    ParticipantRelationType,
    RelationType,
    RoleType,
)


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
                "CC0_10": "spdx:CC0-1.0",
                "CC_BY_40": "spdx:CC-BY-4.0",
                "CC_BY_NC_40": "spdx:CC-BY-NC-4.0",
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
