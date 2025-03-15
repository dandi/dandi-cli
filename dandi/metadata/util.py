from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from functools import lru_cache
import re
from typing import Any, TypedDict, TypeVar
from uuid import uuid4
from xml.dom.minidom import parseString

from dandischema import models
import requests
import tenacity
from yarl import URL

from .. import __version__
from ..utils import ensure_datetime


def _parse_iso8601(age: str) -> list[str]:
    """checking if age is proper iso8601, additional formatting"""
    # allowing for comma instead of ., e.g. P1,5D
    age = age.replace(",", ".")
    pattern = (
        r"^P(?!$)(\d+(?:\.\d+)?Y)?(\d+(?:\.\d+)?M)?(\d+(?:\.\d+)?W)?(\d+(?:\.\d+)?D)?"
        r"(T(?=\d)(\d+(?:\.\d+)?H)?(\d+(?:\.\d+)?M)?(\d+(?:\.\d+)?S)?)?$"
    )
    m = re.match(pattern, age, flags=re.I)
    if m:
        age_f = ["P"] + [m[i] for i in range(1, 6) if m[i]]
        # expanding the Time part (todo: can be done already in pattern)
        if "T" in age_f[-1]:
            mT = re.match(
                r"^T(\d+(?:\.\d+)?H)?(\d+(?:\.\d+)?M)?(\d+(?:\.\d+)?S)?",
                age_f[-1],
                flags=re.I,
            )
            if mT is None:
                raise ValueError(
                    f"Failed to parse the trailing part of age {age_f[-1]!r}"
                )
            age_f = age_f[:-1] + ["T"] + [mT[i] for i in range(1, 3) if mT[i]]
        # checking if there are decimal parts in the higher order components
        _check_decimal_parts(age_f)
        return age_f
    else:
        raise ValueError(f"ISO 8601 expected, but {age!r} was received")


def _parse_age_re(age: str, unit: str, tp: str = "date") -> tuple[str, str | None]:
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
    else:
        raise AssertionError(f"Unexpected unit: {unit!r}")

    m = re.match(rf"(\d+\.?\d*)\s*({pat_un}s?)", age, flags=re.I)
    swap_flag = False
    if m is None:
        # checking pattern with "unit" word
        m = re.match(rf"(\d+\.?\d*)\s*units?:?\s*({pat_un}s?)", age, flags=re.I)
        if m is None:
            # checking pattern with swapped order
            m = re.match(rf"({pat_un}s?)\s*(\d+\.?\d*)", age, flags=re.I)
            swap_flag = True
            if m is None:
                return age, None
    qty = m[3 if swap_flag else 1]
    if "." in qty:
        qty = float(qty)
        if int(qty) == qty:
            qty = int(qty)
    else:
        qty = int(qty)
    return (age[: m.start()] + age[m.end() :]).strip(), f"{qty}{unit}"


def _parse_hours_format(age: str) -> tuple[str, list[str]]:
    """parsing format 0:30:10"""
    m = re.match(r"\s*(\d\d?):(\d\d):(\d\d)", age)
    if m:
        time_part = ["T", f"{int(m[1])}H", f"{int(m[2])}M", f"{int(m[3])}S"]
        return (age[: m.start()] + age[m.end() :]).strip(), time_part
    else:
        return age, []


def _check_decimal_parts(age_parts: list[str]) -> None:
    """checking if decimal parts are only in the lowest order component"""
    # if the last part is the T component I have to separate the parts
    decim_part = ["." in el for el in age_parts]
    if len(decim_part) > 1 and any(decim_part[:-1]):
        raise ValueError("Decimal fraction allowed in the lowest order part only.")


def _check_range_limits(limits: list[list[str]]) -> None:
    """checking if the upper limit is bigger than the lower limit"""
    ok = True
    units_t = dict(zip(["S", "M", "H"], range(3)))
    units_d = dict(zip(["D", "W", "M", "Y"], range(4)))
    lower, upper = limits
    units_order = units_d
    for ii, el in enumerate(upper):
        if ii == len(lower):  # nothing to compare in the lower limit
            break
        if el == "T":  # changing to the time-related unit order
            if lower[ii] != "T":  # lower unit still has
                ok = False
                break
            units_order = units_t
        elif el == lower[ii]:
            continue
        else:  # comparing the first element that differs
            if el[-1] == lower[ii][-1]:  # the same unit
                if float(el[:-1]) > float(lower[ii][:-1]):
                    break
                elif float(el[:-1]) == float(
                    lower[ii][:-1]
                ):  # in case having 2.D and 2D
                    continue
                else:
                    ok = False
                    break
            elif units_order[el[-1]] > units_order[lower[ii][-1]]:
                break
            else:  # lower limit has higher unit
                ok = False
                break
    if len(lower) > len(upper):  # lower has still more elements
        ok = False
    if not ok:
        raise ValueError(
            "The upper limit has to be larger than the lower limit, "
            "and they should have consistent units."
        )


def parse_age(age: str | None) -> tuple[str, str]:
    """
    Parsing age field and converting into an ISO 8601 duration

    Parameters
    ----------
    age : str

    Returns
    -------
    tuple[str, str]
    """

    if not age:
        raise ValueError("Age is empty")

    age_orig = age

    if age.lower().startswith("gestation"):
        age = re.sub("^gest[a-z]*", "", age, flags=re.I)
        ref = "Gestational"
    else:
        ref = "Birth"

    age = age.strip()

    if "/" in age and len(age.split("/")) == 2:  # age as a range
        age = age.replace(" ", "")
        limits = []
        for el in age.split("/"):
            if el.startswith("P"):
                limits.append(_parse_iso8601(el))
            elif el == "":  # start or end of range is unknown
                limits.append([""])
            else:
                raise ValueError(
                    f"Ages that use / for range need to use ISO8601 format, "
                    f"but {el!r} found."
                )
        age_f = limits[0] + ["/"] + limits[1]
        # if both limits provided checking if the upper limit is bigegr than the lower
        if limits[0][0] and limits[1][0]:
            _check_range_limits(limits)
    elif age.startswith("P"):
        age_f = _parse_iso8601(age)
    else:  # trying to figure out any free form
        # removing some symbols
        for symb in [",", ";", "(", ")"]:
            age = age.replace(symb, " ")
        age = age.strip()
        if not age:
            raise ValueError("Age doesn't have any information")

        date_f: list[str] = []
        for unit in ["Y", "M", "W", "D"]:
            if not age:
                break
            age, part_f = _parse_age_re(age, unit)
            if part_f and date_f:
                date_f.append(part_f)
            elif part_f:
                date_f = ["P", part_f]

        if ref == "Birth":
            time_f: list[str] = []
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
                f"Cannot parse age {age_orig!r}: no rules to convert {age!r}"
            )
        # checking if there are decimal parts in the higher order components
        _check_decimal_parts(age_f)

    return "".join(age_f), ref


def extract_age(metadata: dict) -> models.PropertyValue | None:
    try:
        dob = ensure_datetime(metadata["date_of_birth"])
        start = ensure_datetime(metadata["session_start_time"])
    except (KeyError, TypeError, ValueError):
        if metadata.get("age") is not None:
            duration, ref = parse_age(metadata["age"])
        else:
            return None
    else:
        duration, ref = timedelta2duration(start - dob), "Birth"
    return models.PropertyValue(
        value=duration,
        unitText="ISO-8601 duration",
        valueReference=models.PropertyValue(
            value=getattr(models.AgeReferenceType, f"{ref}Reference")
        ),
    )


def timedelta2duration(delta: timedelta) -> str:
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
        sec: int | float = delta.seconds
        if delta.microseconds:
            # Don't add when microseconds is 0, so that sec will be an int then
            sec += delta.microseconds / 1e6
        s += f"T{sec}S"
    if s == "P":
        s += "0D"
    return s


def extract_sex(metadata: dict) -> models.SexType | None:
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
        elif value in ["other", "o"]:
            value_id = None
            value = "Other"
        elif value.startswith("http"):
            value_id = value
            value = None
        else:
            raise ValueError(f"Cannot interpret sex field: {value}")
        return models.SexType(identifier=value_id, name=value)
    else:
        return None


def extract_strain(metadata: dict) -> models.StrainType | None:
    value = metadata.get("strain", None)
    if value:
        # Don't assign cell lines to strain
        if value.lower().startswith("cellline:"):
            return None
        return models.StrainType(name=value)
    else:
        return None


def extract_cellLine(metadata: dict) -> str | None:
    value: str = metadata.get("strain", "")
    if value and value.lower().startswith("cellline:"):
        return value.split(":", 1)[1].strip()
    else:
        return None


NCBITAXON_URI_TEMPLATE = "http://purl.obolibrary.org/obo/NCBITaxon_{}"

# common_names, prefix, uri, name
species_map = [
    (
        ["mouse"],
        "mus",
        NCBITAXON_URI_TEMPLATE.format("10090"),
        "Mus musculus - House mouse",
    ),
    (
        ["human"],
        "homo",
        NCBITAXON_URI_TEMPLATE.format("9606"),
        "Homo sapiens - Human",
    ),
    (
        ["rat", "norvegicus"],
        None,
        NCBITAXON_URI_TEMPLATE.format("10116"),
        "Rattus norvegicus - Norway rat",
    ),
    (
        ["rattus rattus"],
        None,
        NCBITAXON_URI_TEMPLATE.format("10117"),
        "Rattus rattus - Black rat",
    ),
    (
        ["mulatta", "rhesus"],
        None,
        NCBITAXON_URI_TEMPLATE.format("9544"),
        "Macaca mulatta - Rhesus monkey",
    ),
    (
        ["jacchus"],
        None,
        NCBITAXON_URI_TEMPLATE.format("9483"),
        "Callithrix jacchus - Common marmoset",
    ),
    (
        ["melanogaster", "fruit fly"],
        None,
        NCBITAXON_URI_TEMPLATE.format("7227"),
        "Drosophila melanogaster - Fruit fly",
    ),
    (
        ["danio", "zebrafish", "zebra fish"],
        None,
        NCBITAXON_URI_TEMPLATE.format("7955"),
        "Danio rerio - Zebra fish",
    ),
    (
        ["c. elegans", "caenorhabditis elegans"],
        "caenorhabditis",
        NCBITAXON_URI_TEMPLATE.format("6239"),
        "Caenorhabditis elegans",
    ),
    (
        ["pig-tailed macaque", "pigtail monkey", "pigtail macaque"],
        None,
        NCBITAXON_URI_TEMPLATE.format("9545"),
        "Macaca nemestrina",
    ),
    (
        ["mongolian gerbil", "mongolian jird"],
        None,
        NCBITAXON_URI_TEMPLATE.format("10047"),
        "Meriones unguiculatus",
    ),
]


@lru_cache(maxsize=None)  # type: ignore[arg-type]
@tenacity.retry(
    reraise=True,
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(exp_base=1.25, multiplier=1.25),
)
def parse_purlobourl(
    url: str, lookup: tuple[str, ...] | None = None
) -> dict[str, str] | None:
    """Parse an Ontobee URL to return properties of a Class node

    :param url: Ontobee URL
    :param lookup: list of XML nodes to lookup
    :return: dictionary containing found nodes
    """

    req = requests.get(url, allow_redirects=True)
    req.raise_for_status()
    doc = parseString(req.text)
    for elfound in doc.getElementsByTagName("Class"):
        about = elfound.attributes.getNamedItem("rdf:about")
        if about is not None and about.value == url:
            break
    else:
        return None
    values = {}
    if lookup is None:
        lookup = ("rdfs:label", "oboInOwl:hasExactSynonym")
    for key in lookup:
        elchild = elfound.getElementsByTagName(key)
        if elchild:
            elchild0 = elchild[0]
            values[key] = elchild0.childNodes[0].nodeValue.capitalize()
    return values


def extract_species(metadata: dict) -> models.SpeciesType | None:
    value_orig = metadata.get("species", None)
    value_id = None
    if value_orig is not None and value_orig != "":
        if m := re.fullmatch(
            r"https?://purl\.obolibrary\.org/obo/NCBITaxon_([0-9]+)/?",
            value_orig,
            flags=re.I,
        ):
            normed_value = NCBITAXON_URI_TEMPLATE.format(m[1])
            for _common_names, _prefix, uri, name in species_map:
                if uri == normed_value:
                    value_id = uri
                    value = name
                    break
            else:
                value_id = value_orig
                lookup = ("rdfs:label", "oboInOwl:hasExactSynonym")
                try:
                    result: dict[str, str] | None = parse_purlobourl(
                        value_orig, lookup=lookup
                    )
                except ConnectionError:
                    value = None
                else:
                    value = None
                    if result is not None:
                        value = " - ".join(
                            [result[key] for key in lookup if key in result]
                        )
        else:
            lower_value = value_orig.lower()
            for common_names, prefix, uri, name in species_map:
                if (
                    lower_value == name.lower()
                    or any(key in lower_value for key in common_names)
                    or (prefix is not None and lower_value.startswith(prefix))
                ):
                    value_id = uri
                    value = name
                    break
        if value_id is None:
            raise ValueError(
                f"Cannot interpret species field: {value_orig}. Please "
                "contact help@dandiarchive.org to add your species. "
                "You can also put the entire url from NCBITaxon "
                "(http://www.ontobee.org/ontology/NCBITaxon) into "
                "your species field in your NWB file. For example: "
                "http://purl.obolibrary.org/obo/NCBITaxon_9606 is the "
                "url for the species Homo sapiens. Please note that "
                "this url is case sensitive."
            )
        return models.SpeciesType(identifier=value_id, name=value)
    else:
        return None


def extract_assay_type(metadata: dict) -> list[models.AssayType] | None:
    if "assayType" in metadata:
        return [models.AssayType(identifier="assayType", name=metadata["assayType"])]
    else:
        return None


def extract_anatomy(metadata: dict) -> list[models.Anatomy] | None:
    if "anatomy" in metadata:
        return [models.Anatomy(identifier="anatomy", name=metadata["anatomy"])]
    else:
        return None


M = TypeVar("M", bound=models.DandiBaseModel)


def extract_model(modelcls: type[M], metadata: dict, **kwargs: Any) -> M:
    m = modelcls.model_construct()
    for field in m.model_fields.keys():
        value = kwargs.get(field, extract_field(field, metadata))
        if value is not None:
            setattr(m, field, value)
    # I can't figure out why mypy doesn't like this line:
    return m  # type: ignore[return-value]


def extract_model_list(
    modelcls: type[M], id_field: str, id_source: str, **kwargs: Any
) -> Callable[[dict], list[M]]:
    def func(metadata: dict) -> list[M]:
        m = extract_model(
            modelcls, metadata, **{id_field: metadata.get(id_source)}, **kwargs
        )
        if all(v is None for k, v in m.model_dump().items() if k != "schemaKey"):
            return []
        else:
            return [m]

    return func


def extract_wasDerivedFrom(metadata: dict) -> list[models.BioSample] | None:
    derived_from: list[models.BioSample] | None = None
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
    models.Participant, "identifier", "subject_id", id=None
)


def extract_session(metadata: dict) -> list[models.Session] | None:
    probe_ids = metadata.get("probe_ids", [])
    if isinstance(probe_ids, str):
        probe_ids = [probe_ids]
    probes = [
        models.Equipment(identifier=f"probe:{val}", name="Ecephys Probe")
        for val in probe_ids
    ] or None
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


def extract_digest(metadata: dict) -> dict[models.DigestType, str] | None:
    if "digest" in metadata:
        return {models.DigestType[metadata["digest_type"]]: metadata["digest"]}
    else:
        return None


def extract_related_resource(metadata: dict) -> list[models.Resource] | None:
    pubs = metadata.get("related_publications")
    if not isinstance(pubs, (list, tuple)):
        return None
    related = []
    for v in pubs:
        if not isinstance(v, str):
            continue
        try:
            u = URL(v)
        except ValueError:
            continue
        if u.scheme not in ("http", "https") or u.host != "doi.org":
            continue
        related.append(
            models.Resource(
                identifier=v,
                relation=models.RelationType.IsDescribedBy,
            )
        )
    return related


FIELD_EXTRACTORS: dict[str, Callable[[dict], Any]] = {
    "wasDerivedFrom": extract_wasDerivedFrom,
    "wasAttributedTo": extract_wasAttributedTo,
    "wasGeneratedBy": extract_session,
    "age": extract_age,
    "sex": extract_sex,
    "strain": extract_strain,
    "cellLine": extract_cellLine,
    "assayType": extract_assay_type,
    "anatomy": extract_anatomy,
    "digest": extract_digest,
    "species": extract_species,
    "relatedResource": extract_related_resource,
}


def extract_field(field: str, metadata: dict) -> Any:
    if field in FIELD_EXTRACTORS:
        return FIELD_EXTRACTORS[field](metadata)
    else:
        return metadata.get(field)


class Neurodatum(TypedDict):
    module: str
    neurodata_type: str
    technique: str | None
    approach: str | None


neurodata_typemap: dict[str, Neurodatum] = {
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
    "OnePhotonSeries": {
        "module": "ophys",
        "neurodata_type": "OnePhotonSeries",
        "technique": "one-photon microscopy technique",
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


def process_ndtypes(metadata: models.BareAsset, nd_types: Iterable[str]) -> None:
    approach = set()
    technique = set()
    variables = set()
    for val in nd_types:
        val = val.split()[0]
        if val not in neurodata_typemap:
            continue
        if neurodata_typemap[val]["approach"]:
            approach.add(neurodata_typemap[val]["approach"])
        if neurodata_typemap[val]["technique"]:
            technique.add(neurodata_typemap[val]["technique"])
        variables.add(val)
    metadata.approach = [models.ApproachType(name=val) for val in approach]
    metadata.measurementTechnique = [
        models.MeasurementTechniqueType(name=val) for val in technique
    ]
    metadata.variableMeasured = [models.PropertyValue(value=val) for val in variables]


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
        startDate=start_time,
        endDate=end_time,
    )
