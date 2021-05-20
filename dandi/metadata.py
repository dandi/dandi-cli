from datetime import datetime
import os
import os.path as op
import re
from uuid import uuid4

from dandischema import models

from .dandiset import Dandiset
from . import __version__, get_logger
from .pynwb_utils import (
    _get_pynwb_metadata,
    get_neurodata_types,
    get_nwb_version,
    ignore_benign_pynwb_warnings,
    metadata_cache,
)
from .utils import ensure_datetime, get_utcnow_datetime

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
    if value is not None and value != "":
        value = value.lower()
        if value in ["m", "male"]:
            value_id = "http://purl.obolibrary.org/obo/PATO_0000384"
            value = "Male"
        elif value in ["f", "female"]:
            value_id = "http://purl.obolibrary.org/obo/PATO_0000383"
            value = "Female"
        elif value in ["unknown", "u"]:
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
    if value is not None and value != "":
        value = value.lower()
        if "mouse" in value or value.startswith("mus"):
            value_id = "http://purl.obolibrary.org/obo/NCBITaxon_10090"
            value = "House mouse"
        elif "human" in value or value.startswith("homo"):
            value_id = "http://purl.obolibrary.org/obo/NCBITaxon_9606"
            value = "Human"
        elif "norvegicus" in value:
            value_id = "http://purl.obolibrary.org/obo/NCBITaxon_10116"
            value = "Brown rat"
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


def extract_model_list(modelcls, id_field, id_source, **kwargs):
    def func(metadata):
        m = extract_model(
            modelcls, metadata, **{id_field: metadata.get(id_source)}, **kwargs
        )
        if all(v is None for k, v in m.dict().items() if k != "schemaKey"):
            return []
        else:
            return [m]

    return func


def extract_wasDerivedFrom(metadata):
    derived_from = None
    for field, sample_name in [
        ("tissue_sample_id", "tissuesample"),
        ("slice_id", "slice"),
        ("cell_id", "cell"),
    ]:
        if metadata.get(field) is not None:
            derived_from = [
                models.BioSample(
                    identifier=metadata[field],
                    wasDerivedFrom=derived_from,
                    sampleType=models.SampleType(name=sample_name),
                )
            ]
    return derived_from


extract_wasAttributedTo = extract_model_list(
    models.Participant, "identifier", "subject_id", id=...
)

extract_wasGeneratedBy = extract_model_list(
    models.Session, "name", "session_id", id=...
)


def extract_digest(metadata):
    if "digest" in metadata:
        return {models.DigestType[metadata["digest_type"]]: metadata["digest"]}
    else:
        return ...


FIELD_EXTRACTORS = {
    "wasDerivedFrom": extract_wasDerivedFrom,
    "wasAttributedTo": extract_wasAttributedTo,
    "wasGeneratedBy": extract_wasGeneratedBy,
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


def nwb2asset(
    nwb_path, digest=None, digest_type=None, schema_version=None
) -> models.BareAssetMeta:
    if schema_version is not None:
        current_version = models.get_schema_version()
        if schema_version != current_version:
            raise ValueError(
                f"Unsupported schema version: {schema_version}; expected {current_version}"
            )
    start_time = datetime.now().astimezone()
    metadata = get_metadata(nwb_path)
    if digest is not None:
        metadata["digest"] = digest
        metadata["digest_type"] = digest_type
    metadata["contentSize"] = op.getsize(nwb_path)
    metadata["encodingFormat"] = "application/x-nwb"
    metadata["dateModified"] = get_utcnow_datetime()
    metadata["blobDateModified"] = ensure_datetime(os.stat(nwb_path).st_mtime)
    if metadata["blobDateModified"] > metadata["dateModified"]:
        lgr.warning(
            "mtime %s of %s is in the future", metadata["blobDateModified"], nwb_path
        )
    asset = metadata2asset(metadata)
    end_time = datetime.now().astimezone()
    if asset.wasGeneratedBy is None:
        asset.wasGeneratedBy = []
    asset.wasGeneratedBy.append(get_generator(start_time, end_time))
    return asset


def get_default_metadata(path, digest=None, digest_type=None) -> models.BareAssetMeta:
    start_time = datetime.now().astimezone()
    if digest is not None:
        digest_model = {models.DigestType[digest_type]: digest}
    else:
        digest_model = []
    dateModified = get_utcnow_datetime()
    blobDateModified = ensure_datetime(os.stat(path).st_mtime)
    if blobDateModified > dateModified:
        lgr.warning("mtime %s of %s is in the future", blobDateModified, path)
    end_time = datetime.now().astimezone()
    return models.BareAssetMeta.unvalidated(
        contentSize=os.path.getsize(path),
        digest=digest_model,
        dateModified=dateModified,
        blobDateModified=blobDateModified,
        wasGeneratedBy=[get_generator(start_time, end_time)],
        # encodingFormat # TODO
    )


def get_generator(start_time: datetime, end_time: datetime) -> models.Activity:
    return models.Activity(
        id=uuid4().urn,
        name="Metadata generation",
        description="Metadata generated by DANDI cli",
        wasAssociatedWith=[
            models.Software(
                identifier="RRID:SCR_019009",
                name="DANDI Command Line Interface",
                version=__version__,
                url="https://github.com/dandi/dandi-cli",
                schemaKey="Software",
            )
        ],
        startedAt=start_time,
        endedAt=end_time,
    )


def metadata2asset(metadata):
    return extract_model(models.BareAssetMeta, metadata)
