import os.path as op
import re
from .models import AssetMeta, BioSample, PropertyValue
from .pynwb_utils import (
    _get_pynwb_metadata,
    get_neurodata_types,
    get_nwb_version,
    ignore_benign_pynwb_warnings,
    metadata_cache,
)

from . import get_logger
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
    m = re.fullmatch(r"(\d+)\s*(y(ear)?|m(onth)?|w(eek)?|d(ay)?)s?", age, flags=re.I)
    if m:
        qty = int(m.group(1))
        unit = m.group(2)[0].upper()
        return f"P{qty}{unit}"
    else:
        raise ValueError(age)


def extract_age(metadata):
    from .utils import ensure_datetime

    try:
        dob = ensure_datetime(metadata["date_of_birth"])
        start = ensure_datetime(metadata["session_start_time"])
    except (KeyError, ValueError):
        try:
            duration = parse_age(metadata["age"])
        except (KeyError, ValueError):
            return ...
    else:
        if start < dob:
            raise ValueError("session_start_time precedes date_of_birth")
        duration = timedelta2duration(start - dob)
    return PropertyValue(value=duration, unitText="Years from birth")


def timedelta2duration(delta):
    """ Convert a datetime.timedelta to ISO 8601 duration format """
    s = "P"
    if delta.days:
        s += f"{duration.days}D"
    if delta.seconds or delta.microseconds:
        sec = delta.seconds + delta.microseconds / 1000000
        s += f"T{sec}S"
    if s == "P":
        s += "0D"
    return s


def extract_sex(metadata):
    from .models import SexType

    if "sex" in metadata:
        return SexType(identifier="sex", name=metadata["sex"])
    else:
        return ...


def extract_assay_type(metadata):
    from .models import AssayType

    if "assayType" in metadata:
        return [AssayType(identifier="assayType", name=metadata["assayType"])]
    else:
        return []


def extract_anatomy(metadata):
    from .models import Anatomy

    if "anatomy" in metadata:
        return [Anatomy(identifier="anatomy", name=metadata["anatomy"])]
    else:
        return []


def extract_model(modelcls, metadata):
    m = modelcls.unvalidated()
    for field in m.__fields__.keys():
        value = extract_field(field, metadata)
        if value is not Ellipsis:
            setattr(m, field, value)
    # return modelcls(**m.dict())
    return m


def extract_wasDerivedFrom(metadata):
    return [extract_model(BioSample, metadata)]


def extract_keywords(metadata):
    if "keywords" in metadata:
        return metadata["keywords"].split()
    else:
        return ...


def extract_encodingFormat(metadata):
    return "application/x-nwb"


FIELD_EXTRACTORS = {
    "wasDerivedFrom": extract_wasDerivedFrom,
    "age": extract_age,
    "sex": extract_sex,
    "assayType": extract_assay_type,
    "anatomy": extract_anatomy,
    "keywords": extract_keywords,
    "encodingFormat": extract_encodingFormat,
}


def extract_field(field, metadata):
    if field in FIELD_EXTRACTORS:
        return FIELD_EXTRACTORS[field](metadata)
    else:
        return metadata.get(field, ...)


def nwb2asset(nwb_path, digest=None):
    metadata = get_metadata(nwb_path)
    if digest is not None:
        metadata["digest"] = digest
    metadata["contentSize"] = op.getsize(nwb_path)
    return extract_model(AssetMeta, metadata)
