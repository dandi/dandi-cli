from datetime import datetime
import os.path as op
import re
from uuid import uuid4
from . import models
from .pynwb_utils import (
    _get_pynwb_metadata,
    get_neurodata_types,
    get_nwb_version,
    ignore_benign_pynwb_warnings,
    metadata_cache,
)
from .utils import ensure_datetime

from . import __version__, get_logger
from .dandiset import Dandiset

lgr = get_logger()


@metadata_cache.memoize_path
def get_metadata(path):
    """Get selected metadata from a .nwb file or a dandiset directory

    If a directory given and it is not a Dandiset, None is returned

    Parameters
    ----------
    path: str or Path

    Returns
    -------
    dict
    """
    # when we run in parallel, these annoying warnings appear
    ignore_benign_pynwb_warnings()
    path = str(path)  # for Path
    meta = dict()

    if op.isdir(path):
        try:
            dandiset = Dandiset(path)
            return dandiset.metadata
        except ValueError as exc:
            lgr.debug("Failed to get metadata for %s: %s", path, exc)
            return None

    # First read out possibly available versions of specifications for NWB(:N)
    meta["nwb_version"] = get_nwb_version(path)

    # PyNWB might fail to load because of missing extensions.
    # There is a new initiative of establishing registry of such extensions.
    # Not yet sure if PyNWB is going to provide "native" support for needed
    # functionality: https://github.com/NeurodataWithoutBorders/pynwb/issues/1143
    # So meanwhile, hard-coded workaround for data types we care about
    ndtypes_registry = {
        "AIBS_ecephys": "allensdk.brain_observatory.ecephys.nwb",
        "ndx-labmetadata-abf": "ndx_dandi_icephys",
    }
    tried_imports = set()
    while True:
        try:
            meta.update(_get_pynwb_metadata(path))
            break
        except KeyError as exc:  # ATM there is
            lgr.debug("Failed to read %s: %s", path, exc)
            import re

            res = re.match(r"^['\"\\]+(\S+). not a namespace", str(exc))
            if not res:
                raise
            ndtype = res.groups()[0]
            if ndtype not in ndtypes_registry:
                raise ValueError(
                    "We do not know which extension provides %s. "
                    "Original exception was: %s. " % (ndtype, exc)
                )
            import_mod = ndtypes_registry[ndtype]
            lgr.debug("Importing %r which should provide %r", import_mod, ndtype)
            if import_mod in tried_imports:
                raise RuntimeError(
                    "We already tried importing %s to provide %s, but it seems it didn't help"
                    % (import_mod, ndtype)
                )
            tried_imports.add(import_mod)
            __import__(import_mod)

    meta["nd_types"] = get_neurodata_types(path)

    return meta


def parse_age(age):
    """
    Convert a human-friendly duration string into an ISO 8601 duration

    Parameters
    ----------
    age : str

    Returns
    -------
    str
    """
    m = re.fullmatch(r"(\d+)\s*(y(ear)?|m(onth)?|w(eek)?|d(ay)?)s?", age, flags=re.I)
    if m:
        qty = int(m.group(1))
        unit = m.group(2)[0].upper()
        return f"P{qty}{unit}"
    else:
        raise ValueError(age)


def extract_age(metadata):
    try:
        dob = ensure_datetime(metadata["date_of_birth"])
        start = ensure_datetime(metadata["session_start_time"])
    except (KeyError, TypeError, ValueError):
        try:
            duration = parse_age(metadata["age"])
        except (KeyError, TypeError, ValueError):
            return ...
    else:
        if start < dob:
            raise ValueError("session_start_time precedes date_of_birth")
        duration = timedelta2duration(start - dob)
    return models.PropertyValue(value=duration, unitText="Years from birth")


def timedelta2duration(delta):
    """
    Convert a datetime.timedelta to ISO 8601 duration format

    Parameters
    ----------
    delta : datetime.timedelta

    Returns
    -------
    str
    """
    s = "P"
    if delta.days:
        s += f"{delta.days}D"
    if delta.seconds or delta.microseconds:
        sec = delta.seconds
        if delta.microseconds:
            # Don't add when microseconds is 0, so that sec will be an int then
            sec += delta.microseconds / 1000000
        s += f"T{sec}S"
    if s == "P":
        s += "0D"
    return s


def extract_sex(metadata):
    value = metadata.get("sex", None)
    if value is not None:
        value = value.lower()
        if value in ["m", "male"]:
            value_id = "http://purl.obolibrary.org/obo/PATO_0000384"
            value = "Male"
        elif value in ["f", "female"]:
            value_id = "http://purl.obolibrary.org/obo/PATO_0000383"
            value = "Female"
        elif value in ["unknown"]:
            value_id = None
            value = "Unknown"
        elif value in ["other"]:
            value_id = None
            value = "Other"
        elif value.startswith("http"):
            value_id = value
            value = None
        else:
            raise ValueError(f"Cannot interpret sex field: {value}")
        return models.SexType(identifier=value_id, name=value)
    else:
        return ...


def extract_species(metadata):
    value = metadata.get("species", None)
    if value is not None:
        value = value.lower()
        if "mouse" in value or value.startswith("mus"):
            value_id = "http://purl.obolibrary.org/obo/NCBITaxon_10090"
            value = "House mouse"
        elif "human" in value or value.startswith("homo"):
            value_id = "http://purl.obolibrary.org/obo/NCBITaxon_9606"
            value = "Human"
        elif "rat" in value:
            value_id = "http://purl.obolibrary.org/obo/NCBITaxon_10117"
            value = "House rat"
        elif "mulatta" in value or "rhesus" in value:
            value_id = "http://purl.obolibrary.org/obo/NCBITaxon_9544"
            value = "Rhesus monkey"
        elif "jacchus" in value:
            value_id = "http://purl.obolibrary.org/obo/NCBITaxon_9483"
            value = "Common marmoset"
        elif "melanogaster" in value or "fruit fly" in value:
            value_id = "http://purl.obolibrary.org/obo/NCBITaxon_7227"
            value = "Common fruit fly"
        elif value.startswith("http"):
            value_id = value
            value = None
        else:
            raise ValueError(f"Cannot interpret species field: {value}")
        return models.SpeciesType(identifier=value_id, name=value.capitalize())
    else:
        return ...


def extract_assay_type(metadata):
    if "assayType" in metadata:
        return [models.AssayType(identifier="assayType", name=metadata["assayType"])]
    else:
        return ...


def extract_anatomy(metadata):
    if "anatomy" in metadata:
        return [models.Anatomy(identifier="anatomy", name=metadata["anatomy"])]
    else:
        return ...


def extract_model(modelcls, metadata, **kwargs):
    m = modelcls.unvalidated()
    for field in m.__fields__.keys():
        value = kwargs.get(field, extract_field(field, metadata))
        if value is not Ellipsis:
            setattr(m, field, value)
    # return modelcls(**m.dict())
    return m


def extract_wasDerivedFrom(metadata):
    return [
        extract_model(models.BioSample, metadata, identifier=metadata.get("subject_id"))
    ]


def extract_digest(metadata):
    if "digest" in metadata:
        return models.Digest(
            value=metadata["digest"],
            cryptoType=models.DigestType[metadata["digest_type"]],
        )
    else:
        return ...


FIELD_EXTRACTORS = {
    "wasDerivedFrom": extract_wasDerivedFrom,
    "age": extract_age,
    "sex": extract_sex,
    "assayType": extract_assay_type,
    "anatomy": extract_anatomy,
    "digest": extract_digest,
    "species": extract_species,
}


def extract_field(field, metadata):
    if field in FIELD_EXTRACTORS:
        return FIELD_EXTRACTORS[field](metadata)
    else:
        return metadata.get(field, ...)


def nwb2asset(nwb_path, digest=None, digest_type=None):
    start_time = datetime.now().astimezone()
    metadata = get_metadata(nwb_path)
    if digest is not None:
        metadata["digest"] = digest
        metadata["digest_type"] = digest_type
    metadata["contentSize"] = op.getsize(nwb_path)
    metadata["encodingFormat"] = "application/x-nwb"
    asset = metadata2asset(metadata)
    end_time = datetime.now().astimezone()
    asset.wasGeneratedBy = models.Activity(
        identifier=str(uuid4()),
        name="Metadata generation",
        description="Metadata generated by DANDI cli",
        wasAssociatedWith=models.Software(
            identifier={"propertyID": "RRID", "value": "SCR_019009"},
            name="DANDI Command Line Interface",
            description=f"dandi-cli {__version__}",
            version=__version__,
            url="https://github.com/dandi/dandi-cli",
        ),
        startedAt=start_time,
        endedAt=end_time,
    )
    return asset


def metadata2asset(metadata):
    return extract_model(models.AssetMeta, metadata)


"""
The following section converts metadata schema from the current girder dandiset
model to the new schema in dandi-cli. This section should be removed
after the migration is finished to the
"""

mapping = {
    "identifier": ["identifier"],
    "name": ["name"],
    "description": ["description"],
    "contributors": ["contributor"],
    "sponsors": ["contributor", ["Sponsor"]],
    "license": ["license"],
    "keywords": ["keywords"],
    "project": ["generatedBy"],
    "conditions_studied": ["about"],
    "associated_anatomy": ["about"],
    "protocols": ["protocol"],
    "ethicsApprovals": ["ethicsApproval"],
    "access": ["access"],
    "associatedData": ["relatedResource", "IsDerivedFrom"],
    "publications": ["relatedResource", "IsDescribedBy"],
    "age": ["variableMeasured"],
    "organism": ["variableMeasured"],
    "sex": ["variableMeasured"],
    "number_of_subjects": ["assetsSummary", "numberOfSubjects"],
    "number_of_cells": ["assetsSummary", "numberOfCells"],
    "number_of_tissue_samples": ["assetsSummary", "numberOfSamples"],
}


def toContributor(value):
    if not isinstance(value, list):
        value = [value]
    out = []
    for item in value:
        contrib = {}
        if "name" in item:
            name = item["name"].split()
            item["name"] = f"{name[-1]}, {' '.join(name[:-1])}"
        if "roles" in item:
            roles = []
            for role in item["roles"]:
                tmp = role.split()
                if len(tmp) > 1:
                    roles.append("".join([val.capitalize() for val in tmp]))
                else:
                    roles.append(tmp.pop())
            contrib["roleName"] = roles
            del item["roles"]
        if "awardNumber" in item:
            contrib["awardNumber"] = item["awardNumber"]
            del item["awardNumber"]
        if "orcid" in item:
            if item["orcid"]:
                contrib["identifier"] = models.PropertyValue(
                    value=item["orcid"], propertyID="ORCID"
                )
            else:
                contrib["identifier"] = models.PropertyValue()
            del item["orcid"]
        if "affiliations" in item:
            item["affiliation"] = item["affiliations"]
            del item["affiliations"]
        contrib.update(**{f"{k}": v for k, v in item.items()})
        out.append(contrib)
    return out


def convertv1(data):
    oldmeta = data["dandiset"] if "dandiset" in data else data
    newmeta = {}
    for oldkey, value in oldmeta.items():
        if oldkey in ["language", "altid", "number_of_slices"]:
            continue
        if oldkey not in mapping:
            raise KeyError(f"Could not find {oldkey}")
        if len(mapping[oldkey]) == 0:
            newkey = f"schema:{oldkey}"
        else:
            newkey = mapping[oldkey][0]
        if oldkey in ["contributors", "sponsors"]:
            value = toContributor(value)
        if oldkey == "access":
            value = [
                models.AccessRequirements(
                    status=models.AccessType.Open, email=value["access_contact_email"]
                )
            ]
        if oldkey == "identifier":
            value = models.PropertyValue(value=value, propertyID="DANDI")
        if len(mapping[oldkey]) == 2:
            extra = mapping[oldkey][1]
            if newkey == "contributor":
                extrakey = "roleName"
            if oldkey == "sponsors":
                extrakey = "roleName"
            if oldkey in ["publications", "associatedData"]:
                extrakey = "relation"
                if not isinstance(value, list):
                    value = [value]
                out = []
                for item in value:
                    if isinstance(item, dict):
                        out.append({k: v for k, v in item.items()})
                    else:
                        present = False
                        for val in out:
                            if item in val.values():
                                present = True
                        if not present:
                            out.append({"url": item})
                value = out
            if oldkey in [
                "number_of_subjects",
                "number_of_cells",
                "number_of_tissue_samples",
            ]:
                value = {extra: value}
                extrakey = None
            if isinstance(value, list):
                for val in value:
                    if extrakey:
                        val[extrakey] = extra
            if isinstance(value, dict):
                if extrakey:
                    value[extrakey] = extra
        if newkey == "variableMeasured":
            if oldkey in ["age", "sex"]:
                vm = {"name": oldkey}
                if oldkey == "sex":
                    vm["value"] = value
                else:
                    if "maximum" in value:
                        if "days" in value["maximum"]:
                            value["units"] = "days"
                        if "Gestational" in value["maximum"]:
                            value["units"] = "Gestational Week"
                            value["maximum"] = value["maximum"].split()[-1]
                        if value["maximum"].startswith("P"):
                            value["maximum"] = value["maximum"][1:-1]
                            value["units"] = value["maximum"][-1]
                        if "None" not in value["maximum"]:
                            value["maximum"] = float(value["maximum"].split()[0])
                    if "minimum" in value:
                        if "days" in value["minimum"]:
                            value["units"] = "days"
                        if "Gestational" in value["minimum"]:
                            value["units"] = "Gestational Week"
                            value["minimum"] = value["minimum"].split()[-1]
                        if value["minimum"].startswith("P"):
                            value["minimum"] = value["minimum"][1:-1]
                            value["units"] = value["minimum"][-1]
                        if "None" not in value["minimum"]:
                            value["minimum"] = float(value["minimum"].split()[0])
                    value["unitText"] = value["units"]
                    del value["units"]
                    vm.update(**value)
            else:
                newvalues = []
                for val in value:
                    if "species" in val:
                        newvalues.append(val["species"])
                vm = {"name": "species", "value": newvalues}
            value = vm
        if newkey not in newmeta:
            newmeta[newkey] = value
        else:
            curvalue = newmeta[newkey]
            if not isinstance(curvalue, list):
                newmeta[newkey] = [curvalue]
            if not isinstance(value, list):
                value = [value]
            newmeta[newkey].extend(value)
    if "assetsSummary" in newmeta:
        del newmeta["assetsSummary"]
    if "variableMeasured" in newmeta:
        del newmeta["variableMeasured"]
    return newmeta


def migrate2newschema(meta):
    newmeta = convertv1(meta)
    dandimeta = models.DandiMeta.unvalidated(**newmeta)
    return dandimeta
