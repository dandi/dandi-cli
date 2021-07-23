from datetime import datetime
import os
import os.path as op
import re
from uuid import uuid4

from dandischema import models

from . import __version__, get_logger
from .dandiset import Dandiset
from .pynwb_utils import (
    _get_pynwb_metadata,
    get_neurodata_types,
    get_nwb_version,
    ignore_benign_pynwb_warnings,
    metadata_cache,
)
from .utils import ensure_datetime, get_mime_type, get_utcnow_datetime

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


def _parse_iso8601(age):
    """checking if age is proper iso8601, additional formatting"""
    # allowing for comma instead of ., e.g. P1,5D
    age = age.replace(",", ".")
    pattern = (
        "^P(?!$)(\\d+(?:\\.\\d+)?Y)?(\\d+(?:\\.\\d+)?M)?(\\d+(?:\\.\\d+)?W)?(\\d+(?:\\.\\d+)?D)?"
        "(T(?=\\d)(\\d+(?:\\.\\d+)?H)?(\\d+(?:\\.\\d+)?M)?(\\d+(?:\\.\\d+)?S)?)?$"
    )

    matchstr = re.match(pattern, age, flags=re.I)
    if matchstr:
        age_frm = [matchstr.group(i) for i in range(1, 6) if matchstr.group(i)]
        age_frm = ["P"] + age_frm
        return age_frm
    else:
        raise ValueError(f"ISO 8601 expected, but {age} was received")


def _parse_age_re(age, unit, tp="date"):
    """finding parts that have <value> <unit> in various forms"""

    if unit == "Y":
        pat_un = "y(ear)?"
    elif unit == "M" and tp == "date":
        pat_un = "(month|mon|mo|m)"
    elif unit == "W":
        pat_un = "w(eek)?"
    elif unit == "D":
        pat_un = "d(ay)?"
    elif unit == "H":
        pat_un = "h(our)?"
    elif unit == "M" and tp == "time":
        pat_un = "(min|m(inute)?)"
    elif unit == "S":
        pat_un = "(sec|s(econd)?)"

    pattern = rf"(\d+\.?\d*)\s*({pat_un}s?)"
    matchstr = re.match(pattern, age, flags=re.I)
    swap_flag = False
    if matchstr is None:
        # checking pattern with "unit" word
        pattern_unit = rf"(\d+\.?\d*)\s*units?:?\s*({pat_un}s?)"
        matchstr = re.match(pattern_unit, age, flags=re.I)
        if matchstr is None:
            # checking patter with swapped order
            pattern = rf"({pat_un}s?)\s*(\d+\.?\d*)"
            matchstr = re.match(pattern, age, flags=re.I)
            swap_flag = True
            if matchstr is None:
                return age, None
    if swap_flag:
        qty = matchstr.group(3)
    else:
        qty = matchstr.group(1)
    if "." in qty:
        qty = float(qty)
        if int(qty) == qty:
            qty = int(qty)
    else:
        qty = int(qty)
    age_rem = age.replace(matchstr.group(0), "")
    age_rem = age_rem.strip()
    return age_rem, f"{qty}{unit}"


def _parse_hours_format(age):
    """parsing format 0:30:10"""
    pattern = r"\s*(\d\d?):(\d\d):(\d\d)"
    matchstr = re.match(pattern, age, flags=re.I)
    if matchstr:
        time_part = f"T{int(matchstr.group(1))}H{int(matchstr.group(2))}M{int(matchstr.group(3))}S"
        age_rem = age.replace(matchstr.group(0), "")
        age_rem = age_rem.strip()
        return age_rem, [time_part]
    else:
        return age, []


def _check_decimal_parts(age_parts):
    """checking if decimal parts are only in the lowest order component"""
    # if the last part is the T component I have to separate the parts
    if "T" in age_parts[-1]:
        pattern_time = "^T(\\d+(?:\\.\\d+)?H)?(\\d+(?:\\.\\d+)?M)?(\\d+(?:\\.\\d+)?S)?"
        matchstr = re.match(pattern_time, age_parts[-1], flags=re.I)
        time_parts = [matchstr.group(i) for i in range(1, 3) if matchstr.group(i)]
        age_parts = age_parts[:-1] + time_parts
    decim_part = ["." in el for el in age_parts]
    if any(decim_part) and any(decim_part[:-1]):
        return False
    else:
        return True


def parse_age(age):
    """
    Parsing age field and converting into an ISO 8601 duration

    Parameters
    ----------
    age : str

    Returns
    -------
    str
    """

    if not age:
        raise ValueError("age is empty")

    age_orig = age

    if "gestation" in age.lower():
        pattern_time = "^gest[a-z]*"
        matchstr = re.match(pattern_time, age, flags=re.I)
        age = age.replace(matchstr.group(0), "")
        ref = "Gestational"
    else:
        ref = "Birth"

    age = age.strip()

    if age[0] == "P":
        age_f = _parse_iso8601(age)
    else:  # trying to figure out any free form
        # removing some symbols
        for symb in [",", ";", "(", ")"]:
            age = age.replace(symb, " ")
        age = age.strip()
        if not age:
            raise ValueError("age doesn't have any information")

        date_f = []
        for unit in ["Y", "M", "W", "D"]:
            if not age:
                break
            age, part_f = _parse_age_re(age, unit)
            if part_f and date_f:
                date_f.append(part_f)
            elif part_f:
                date_f = ["P", part_f]

        if ref == "Birth":
            time_f = []
            for un in ["H", "M", "S"]:
                if not age:
                    break
                age, part_f = _parse_age_re(age, un, tp="time")
                if part_f and time_f:
                    time_f.append(part_f)
                elif part_f:
                    time_f = ["T", part_f]
            # trying to find formats 00:00:00 for time
            if not time_f:
                age, time_f = _parse_hours_format(age)

            age_f = date_f + time_f
        elif ref == "Gestational":
            # ignore time formats for Gestational (unless it is needed in the future)
            age_f = date_f
        if set(age) - {" ", ".", ",", ":", ";"}:
            raise ValueError(
                f"not able to parse the age: {age_orig}, no rules to convert: {age}"
            )

    # checking if there are decimal parts in the higher order components
    if not _check_decimal_parts(age_f):
        raise ValueError(
            f"decimal fraction allowed in the lowest order part only,"
            f" but {age} was received "
        )
    return "".join(age_f), ref


def extract_age(metadata):
    try:
        dob = ensure_datetime(metadata["date_of_birth"])
        start = ensure_datetime(metadata["session_start_time"])
    except (KeyError, TypeError, ValueError):
        if metadata.get("age") is not None:
            duration, ref = parse_age(metadata["age"])
        else:
            return ...
    else:
        duration, ref = timedelta2duration(start - dob), "Birth"
    return models.PropertyValue(
        value=duration,
        unitText="ISO-8601 duration",
        valueReference=models.PropertyValue(
            value=getattr(models.AgeReferenceType, f"{ref}Reference")
        ),
    )


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
            sec += delta.microseconds / 1e6
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
            value = "Rat; Norway rat; rats; Brown rat"
        elif "rattus rattus" in value:
            value_id = "http://purl.obolibrary.org/obo/NCBITaxon_10117"
            value = "Black rat; Roof rat; House rat"
        elif "rat" in value:
            value_id = "http://purl.obolibrary.org/obo/NCBITaxon_10116"
            value = "Rat; Norway rat; rats; Brown rat"
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
            raise ValueError(
                f"Cannot interpret species field: {value}. Please "
                "contact help@dandiarchive.org to add your species."
            )
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


def extract_session(metadata: dict) -> list:
    probe_ids = metadata.get("probe_ids", [])
    if isinstance(probe_ids, str):
        probe_ids = [probe_ids]
    probes = []
    for val in probe_ids:
        probes.append(models.Equipment(identifier=f"probe:{val}", name="Ecephys Probe"))
    probes = probes or None
    session_id = None
    if metadata.get("session_id") is not None:
        session_id = str(metadata["session_id"])
    if (session_id or metadata.get("session_start_time") or probes) is None:
        return None
    return [
        models.Session(
            identifier=session_id,
            name=session_id or "Acquisition session",
            description=metadata.get("session_description"),
            startDate=metadata.get("session_start_time"),
            used=probes,
        )
    ]


def extract_digest(metadata):
    if "digest" in metadata:
        return {models.DigestType[metadata["digest_type"]]: metadata["digest"]}
    else:
        return ...


FIELD_EXTRACTORS = {
    "wasDerivedFrom": extract_wasDerivedFrom,
    "wasAttributedTo": extract_wasAttributedTo,
    "wasGeneratedBy": extract_session,
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


neurodata_typemap = {
    "ElectricalSeries": {
        "module": "ecephys",
        "neurodata_type": "ElectricalSeries",
        "technique": "multi electrode extracellular electrophysiology recording technique",
        "approach": "electrophysiological approach",
    },
    "SpikeEventSeries": {
        "module": "ecephys",
        "neurodata_type": "SpikeEventSeries",
        "technique": "spike sorting technique",
        "approach": "electrophysiological approach",
    },
    "FeatureExtraction": {
        "module": "ecephys",
        "neurodata_type": "FeatureExtraction",
        "technique": "spike sorting technique",
        "approach": "electrophysiological approach",
    },
    "LFP": {
        "module": "ecephys",
        "neurodata_type": "LFP",
        "technique": "signal filtering technique",
        "approach": "electrophysiological approach",
    },
    "EventWaveform": {
        "module": "ecephys",
        "neurodata_type": "EventWaveform",
        "technique": "spike sorting technique",
        "approach": "electrophysiological approach",
    },
    "EventDetection": {
        "module": "ecephys",
        "neurodata_type": "EventDetection",
        "technique": "spike sorting technique",
        "approach": "electrophysiological approach",
    },
    "ElectrodeGroup": {
        "module": "ecephys",
        "neurodata_type": "ElectrodeGroup",
        "technique": "surgical technique",
        "approach": "electrophysiological approach",
    },
    "PatchClampSeries": {
        "module": "icephys",
        "neurodata_type": "PatchClampSeries",
        "technique": "patch clamp technique",
        "approach": "electrophysiological approach",
    },
    "CurrentClampSeries": {
        "module": "icephys",
        "neurodata_type": "CurrentClampSeries",
        "technique": "current clamp technique",
        "approach": "electrophysiological approach",
    },
    "CurrentClampStimulusSeries": {
        "module": "icephys",
        "neurodata_type": "CurrentClampStimulusSeries",
        "technique": "current clamp technique",
        "approach": "electrophysiological approach",
    },
    "VoltageClampSeries": {
        "module": "icephys",
        "neurodata_type": "VoltageClampSeries",
        "technique": "voltage clamp technique",
        "approach": "electrophysiological approach",
    },
    "VoltageClampStimulusSeries": {
        "module": "icephys",
        "neurodata_type": "VoltageClampStimulusSeries",
        "technique": "voltage clamp technique",
        "approach": "electrophysiological approach",
    },
    "TwoPhotonSeries": {
        "module": "ophys",
        "neurodata_type": "TwoPhotonSeries",
        "technique": "two-photon microscopy technique",
        "approach": "microscopy approach; cell population imaging",
    },
    "OpticalChannel": {
        "module": "ophys",
        "neurodata_type": "OpticalChannel",
        "technique": "surgical technique",
        "approach": "microscopy approach; cell population imaging",
    },
    "ImagingPlane": {
        "module": "ophys",
        "neurodata_type": "ImagingPlane",
        "technique": None,
        "approach": "microscopy approach; cell population imaging",
    },
    "PlaneSegmentation": {
        "module": "ophys",
        "neurodata_type": "PlaneSegmentation",
        "technique": None,
        "approach": "microscopy approach; cell population imaging",
    },
    "Position": {
        "module": "behavior",
        "neurodata_type": "Position",
        "technique": "behavioral technique",
        "approach": "behavioral approach",
    },
    "SpatialSeries": {
        "module": "behavior",
        "neurodata_type": "SpatialSeries",
        "technique": "behavioral technique",
        "approach": "behavioral approach",
    },
    "BehavioralEpochs": {
        "module": "behavior",
        "neurodata_type": "BehavioralEpochs",
        "technique": "behavioral technique",
        "approach": "behavioral approach",
    },
    "BehavioralEvents": {
        "module": "behavior",
        "neurodata_type": "BehavioralEvents",
        "technique": "behavioral technique",
        "approach": "behavioral approach",
    },
    "BehavioralTimeSeries": {
        "module": "behavior",
        "neurodata_type": "BehavioralTimeSeries",
        "technique": "behavioral technique",
        "approach": "behavioral approach",
    },
    "PupilTracking": {
        "module": "behavior",
        "neurodata_type": "PupilTracking",
        "technique": "behavioral technique",
        "approach": "behavioral approach",
    },
    "EyeTracking": {
        "module": "behavior",
        "neurodata_type": "EyeTracking",
        "technique": "behavioral technique",
        "approach": "behavioral approach",
    },
    "CompassDirection": {
        "module": "behavior",
        "neurodata_type": "CompassDirection",
        "technique": "behavioral technique",
        "approach": "behavioral approach",
    },
    "ProcessingModule": {
        "module": "base",
        "neurodata_type": "ProcessingModule",
        "technique": "analytical technique",
        "approach": None,
    },
    "RGBImage": {
        "module": "image",
        "neurodata_type": "RGBImage",
        "technique": "photographic technique",
        "approach": None,
    },
    "DecompositionSeries": {
        "module": "misc",
        "neurodata_type": "DecompositionSeries",
        "technique": "fourier analysis technique",
        "approach": None,
    },
    "Units": {
        "module": "misc",
        "neurodata_type": "Units",
        "technique": "spike sorting technique",
        "approach": "electrophysiological approach",
    },
    "Spectrum": {
        "module": "ndx-spectrum",
        "neurodata_type": "Spectrum",
        "technique": "fourier analysis technique",
        "approach": None,
    },
    "OptogeneticStimulusSIte": {
        "module": "ogen",
        "neurodata_type": "OptogeneticStimulusSIte",
        "technique": None,
        "approach": "optogenetic approach",
    },
    "OptogeneticSeries": {
        "module": "ogen",
        "neurodata_type": "OptogeneticSeries",
        "technique": None,
        "approach": "optogenetic approach",
    },
}


def process_ndtypes(asset, nd_types):
    approach = set()
    technique = set()
    variables = set()
    for val in nd_types:
        if val not in neurodata_typemap:
            continue
        if neurodata_typemap[val]["approach"]:
            approach.add(neurodata_typemap[val]["approach"])
        if neurodata_typemap[val]["technique"]:
            technique.add(neurodata_typemap[val]["technique"])
        variables.add(val)
    asset.approach = [models.ApproachType(name=val) for val in approach]
    asset.measurementTechnique = [
        models.MeasurementTechniqueType(name=val) for val in technique
    ]
    asset.variableMeasured = [models.PropertyValue(value=val) for val in variables]
    return asset


def get_asset_metadata(
    filepath, relpath, digest=None, digest_type=None, allow_any_path=True
) -> models.BareAsset:
    metadata = None
    if op.splitext(filepath)[1] == ".nwb":
        try:
            metadata = nwb2asset(filepath, digest=digest, digest_type=digest_type)
        except Exception as e:
            lgr.warning(
                "Failed to extract NWB metadata from %s: %s: %s",
                filepath,
                type(e).__name__,
                str(e),
            )
            if not allow_any_path:
                raise
    if metadata is None:
        metadata = get_default_metadata(
            filepath, digest=digest, digest_type=digest_type
        )
    metadata.path = str(relpath)
    return metadata


def nwb2asset(
    nwb_path, digest=None, digest_type=None, schema_version=None
) -> models.BareAsset:
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
    metadata["path"] = nwb_path
    if metadata["blobDateModified"] > metadata["dateModified"]:
        lgr.warning(
            "mtime %s of %s is in the future", metadata["blobDateModified"], nwb_path
        )
    asset = metadata2asset(metadata)
    asset = process_ndtypes(asset, metadata["nd_types"])
    end_time = datetime.now().astimezone()
    if asset.wasGeneratedBy is None:
        asset.wasGeneratedBy = []
    asset.wasGeneratedBy.append(get_generator(start_time, end_time))
    return asset


def get_default_metadata(path, digest=None, digest_type=None) -> models.BareAsset:
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
    return models.BareAsset.unvalidated(
        contentSize=os.path.getsize(path),
        digest=digest_model,
        dateModified=dateModified,
        blobDateModified=blobDateModified,
        wasGeneratedBy=[get_generator(start_time, end_time)],
        encodingFormat=get_mime_type(path),
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
    bare_dict = extract_model(models.BareAsset, metadata).json_dict()
    return models.BareAsset(**bare_dict)
