import pytest

from ..models import DandiMeta, AssetMeta
from ..models import AccessType, RoleType, Relation, License, IdentifierType, DigestType


def test_dandiset():
    assert DandiMeta.unvalidated()


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
            Relation,
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
            License,
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
                "SHA256": "dandi:SHA256",
                "sha512": "dandi:sha512",
            },
        ),
    ],
)
def test_types(enumtype, values):
    assert {v.name: v.value for v in enumtype} == values
