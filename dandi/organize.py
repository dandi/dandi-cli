"""
ATM primarily a sandbox for some functionality for  dandi organize
"""

import binascii
import numpy as np
import re
from collections import Counter

import dateutil.parser
import os.path as op

from .exceptions import OrganizeImpossibleError
from . import get_logger
from .consts import dandiset_metadata_file
from .pynwb_utils import get_neurodata_types_to_modalities_map, get_object_id
from .utils import ensure_datetime, flattened

lgr = get_logger()

# Fields which would be used to compose the filename
# TODO: add full description into command --help etc
potential_fields = {
    "subject_id": "sub-{}",
    "session_id": "_ses-{}",
    "tissue_sample_id": "_tis-{}",
    "slice_id": "_slice-{}",
    "cell_id": "_cell-{}",
    "obj_id": "_obj-{}",  # will be not id, but checksum of it to shorten
    # "session_description"
    "modalities": "_{}",
    "extension": "{}",
}
dandi_path = "sub-{subject_id}/{dandi_filename}"


def filter_invalid_metadata_rows(metadata_rows):
    """Split into two lists - valid and invalid entries"""
    valid, invalid = [], []
    for row in metadata_rows:
        if list(row.keys()) == ["path"]:
            lgr.warning("Completely empty record for {path}".format(**row))
            invalid.append(row)
        elif row["nwb_version"] == "ERROR":
            lgr.warning("nwb_version is ERROR for {path}".format(**row))
            invalid.append(row)
        elif not row.get("subject_id", None):
            lgr.warning("subject_id is missing for {path}".format(**row))
            invalid.append(row)
        else:
            valid.append(row)
    return valid, invalid


def create_unique_filenames_from_metadata(
    metadata,
    mandatory=["subject_id", "extension"],
    mandatory_if_not_empty=["modalities,"],
    add_object_id_for_non_unique=True,
):
    """

    Parameters
    ----------
    metadata: list of dict
      List of metadata records
    mandatory: list of str
      Fields in addition to "subject_id" and (file) "extension" which would be
      mandatory to be included in the filename

    Returns
    -------

    """

    # TODO this does not act in a greedy fashion
    # i.e., only using enough fields to ensure uniqueness of filenames, but that
    # greedy field set could break if another file is incrementally added to the set
    # of filenames from which the greedy fields were determined.

    # TODO what to do if not all files have values for the same set of fields, i.e. some rows
    # are empty for certain fields?

    #
    # Additional fields
    #

    # Add "modalities" composed from the ones we could deduce
    _populate_modalities(metadata)

    # handle cases where session_id was not provided
    # In some of those we could have session_start_time, so we could produce
    # session_id based on those
    if not all(m.get("session_id") for m in metadata):
        _populate_session_ids_from_time(metadata)

    # And some initial sanitization
    for r in metadata:
        # extract File name extension and place them into the records
        r["extension"] = op.splitext(r["path"])[1]
        # since those might be used in dandi_path
        for field in "subject_id", "session_id":
            value = r.get(field, None)
            if value:
                r[field] = _sanitize_value(value, field)

    _assign_dandi_names(metadata, mandatory, mandatory_if_not_empty)

    non_unique = _get_non_unique_paths(metadata)

    if non_unique:
        if not add_object_id_for_non_unique:
            msg = "%d out of %d paths are not unique" % (len(non_unique), len(metadata))
            msg_detailed = msg + ":\n%s" % "\n".join(
                "   %s: %s" % i for i in non_unique.items()
            )
            raise OrganizeImpossibleError(
                msg_detailed + "\nPlease adjust/provide metadata in your .nwb "
                "files to disambiguate or rerun allowing adding object_id."
            )
        _assign_obj_id(metadata, non_unique)
        _assign_dandi_names(
            metadata, mandatory, (mandatory_if_not_empty or []) + ["obj_id"]
        )
        non_unique = _get_non_unique_paths(metadata)
        if non_unique:
            raise OrganizeImpossibleError(
                "Even after adding obj_id we ended up with non-unique file names. "
                "Should not have happened: %s" % str(non_unique)
            )
    return metadata


def _assign_obj_id(metadata, non_unique):
    msg = "%d out of %d paths are not unique" % (len(non_unique), len(metadata))

    lgr.info(msg + ". We will try adding _obj- based on crc32 of object_id")
    seen_obj_ids = {}  # obj_id: object_id
    seen_object_ids = {}  # object_id: path
    recent_nwb_msg = "NWB>=2.1.0 standard (supported by pynwb>=1.1.0)."
    for r in metadata:
        if r["dandi_path"] in non_unique:
            try:
                object_id = get_object_id(r["path"])
            except KeyError:
                raise OrganizeImpossibleError(
                    msg
                    + f". We tried to use object_id but it is absent in {r['path']!r}. "
                    f"It is either not .nwb file or produced by older *nwb libraries. "
                    f"You must re-save files e.g. using {recent_nwb_msg}"
                )

            if not object_id:
                raise OrganizeImpossibleError(
                    msg
                    + f". We tried to use object_id but it was {object_id!r} for {r['path']!r}. "
                    f"You might need to re-save files using {recent_nwb_msg}"
                )
            # shorter version
            obj_id = get_obj_id(object_id)
            if obj_id in seen_obj_ids:
                seen_object_id = seen_obj_ids[obj_id]
                if seen_object_id == object_id:
                    raise OrganizeImpossibleError(
                        f"Two files ({r['path']!r} and {seen_object_ids[object_id]!r}) "
                        f"have the same object_id {object_id}. Must not "
                        f"happen. Either files are duplicates (remove one) "
                        f"or were not saved correctly using {recent_nwb_msg}"
                    )
                else:
                    raise RuntimeError(
                        f"Wrong assumption by DANDI developers that first "
                        f"CRC32 checksum of object_id would be sufficient.  Please "
                        f"report: {obj_id} the same for "
                        f"{seen_object_ids[seen_object_id]}={seen_object_id} "
                        f"{r['path']}={object_id} "
                    )
            r["obj_id"] = obj_id
            seen_obj_ids[obj_id] = object_id
            seen_object_ids[object_id] = r["path"]


def get_obj_id(object_id):
    """Given full object_id, get its shortened version
    """
    return np.base_repr(binascii.crc32(object_id.encode("ascii")), 36).lower()


def _assign_dandi_names(metadata, mandatory, mandatory_if_not_empty):
    unique_values = _get_unique_values(metadata, potential_fields)
    # unless it is mandatory, we would not include the fields with more than
    # a single unique field
    for r in metadata:
        dandi_filename = ""
        for field, field_format in potential_fields.items():
            if (field in mandatory or len(unique_values[field]) > 1) or (
                field in mandatory_if_not_empty and unique_values[field]
            ):
                value = r.get(field, None)
                if value is not None:
                    if isinstance(value, (list, tuple)):
                        value = "+".join(value)
                    # sanitize value to avoid undesired characters
                    value = _sanitize_value(value, field)
                    # Format _key-value according to the "schema"
                    formatted_value = field_format.format(value)
                    dandi_filename += formatted_value
        r["dandi_filename"] = dandi_filename
        r["dandi_path"] = dandi_path.format(**r)


def _get_unique_values(metadata, fields, filter_=False):
    unique_values = {}
    for field in fields:
        unique_values[field] = set(r.get(field, None) for r in metadata)
        if filter_:
            unique_values[field] = set(v for v in unique_values[field] if v)
    return unique_values


def _sanitize_value(value, field):
    """Replace all "non-compliant" characters with -

    Of particular importance is _ which we use, as in BIDS, to separate
    _key-value entries
    """
    value = re.sub("[_*:%@]", "-", value)
    if field != "extension":
        value = value.replace(".", "-")
    return value


def _populate_modalities(metadata):
    ndtypes_to_modalities = get_neurodata_types_to_modalities_map()
    ndtypes_unassigned = set()
    for r in metadata:
        mods = set()
        nd_types = r.get("nd_types", [])
        if isinstance(nd_types, str):
            nd_types = nd_types.split(",")
        for nd_rec in nd_types:
            # split away the count
            ndtype = nd_rec.split()[0]
            mod = ndtypes_to_modalities.get(ndtype, None)
            if mod:
                if mod not in ("base", "device", "file", "misc"):
                    # skip some trivial/generic ones
                    mods.add(mod)
            else:
                ndtypes_unassigned.add(ndtype)
        # tuple so we could easier figure out "unique" values below
        r["modalities"] = tuple(sorted(mods))


def _populate_session_ids_from_time(metadata):
    ses_times = [m.get("session_start_time", None) for m in metadata]
    if not all(ses_times):
        lgr.warning("No session_id and no session_start_time for all samples.")
    # Let's check if we could strip away the 0 times
    # In ls output json we have
    #  e.g. "2015-02-12 00:00:00+00:00"
    # while nwb-schema says it should be ISO8601
    #  e.g. "2018-09-28T14:43:54.123+02:00"
    # So in the first pass just figure out if degenerate times
    degenerate_time = True
    for m in metadata:
        ses_time = m.get("session_start_time", None)
        if not ses_time:
            continue  # we can do nothing
        ses_time = ensure_datetime(ses_time)
        if (ses_time.hour, ses_time.minute, ses_time.second) != (0, 0, 0):
            degenerate_time = False
            break
    nassigned = 0
    for m in metadata:
        if m.get("session_id", None):
            continue  # this one has it
        ses_time = m.get("session_start_time", None)
        if not ses_time:
            continue  # we can do nothing
        ses_time = ensure_datetime(ses_time)
        m["session_id"] = "%d%02d%02d" % (ses_time.year, ses_time.month, ses_time.day)
        if not degenerate_time:
            m["session_id"] += "T%02d%02d%02d" % (
                ses_time.hour,
                ses_time.minute,
                ses_time.second,
            )
        nassigned += 1
    lgr.debug("Assigned %d session_id's based on the date" % nassigned)


def create_dataset_yml_template(filepath):
    with open(filepath, "w") as f:
        # pasted as is from WiP google doc.  We write it, read it, adjust,
        # re-save
        f.write(
            """\
identifier: REQUIRED ## Post upload (or during dandi organize)
name: REQUIRED
description: REQUIRED
contributors: # required for author and contact
- orcid: # REQUIRED
  roles: # REQUIRED from https://casrai.org/credit/ + maintainer, contact:
  email: Recommended # filled from orcid
  name: Recommended  # filled from orcid
  affiliations: optional  # filled from orcid
sponsors:
- identifier: RECOMMENDED
  name: REQUIRED
  url: RECOMMENDED
license:
- url # REQUIRED
keywords: [key1, key2,]
consortium/project:
- name: REQUIRED
  identifier: REQUIRED #RRID
associated_disease: # RECOMMENDED
- name: REQUIRED
  identifier: REQUIRED
associated_anatomy: # RECOMMENDED
- name: REQUIRED
  identifier: REQUIRED
protocols: # OPTIONAL
- name: REQUIRED
  identifier: REQUIRED
ethicsApprovals: # RECOMMENDED
- name: REQUIRED # name of committee
  country: REQUIRED
  identifier: REQUIRED # protocol number
access: # OPTIONAL
  status: REQUIRED # open, embargoed, restricted
  access_request_url: REQUIRED for embargoed and restricted
  access_contact_email: REQUIRED for embargoed and restricted
language: RECOMMENDED

## All metadata below could either be added after publication or
## extracted from NWB files

## Post publication (i.e. added by DANDI)
version: REQUIRED
releaseDate: REQUIRED
associatedData:
- name: REQUIRED
  identifier: REQUIRED
  repository: REQUIRED
  url: REQUIRED
publications:
- url: REQUIRED # doi preferred
  identifiers: RECOMMENDED # PMCID
  relation: RECOMMENDED
doi: REQUIRED
url: REQUIRED
repository: # REQUIRED
- name: REQUIRED
  identifier: RRID/REQUIRED
distribution:
- data_download:
  - contentURL:  REQUIRED
    name: required
    content_size: REQUIRED
    date_published: REQUIRED
    date_modified: REQUIRED
    measurement_type: OPTIONAL
altid: # OPTIONAL
- id1

## NWB files + additional metadata provided

variables_measured: OPTIONAL
age:
  minimum: REQUIRED
  maximum: REQUIRED
  units: REQUIRED
sex: REQUIRED
organism:
- species: REQUIRED
  strain: REQUIRED
  identifier: REQUIRED
  vendor: OPTIONAL
number_of_subjects: REQUIRED
number_of_tissue_samples: RECOMMENDED
number_of_cells: RECOMMENDED
"""
        )


def populate_dataset_yml(filepath, metadata):
    # To preserve comments, let's use ruamel
    import ruamel.yaml

    yaml = ruamel.yaml.YAML()  # defaults to round-trip if no parameters given
    if not op.exists(filepath):
        # Create an empty one, which we would populate with information
        # we can
        with open(filepath, "w") as f:
            pass

    with open(filepath) as f:
        rec = yaml.load(f)

    if not rec:
        rec = {}

    # Let's use available metadata for at least some of the fields
    uvs = _get_unique_values(
        metadata,
        (
            "age",
            "cell_id",
            "experiment_description",
            "related_publications",
            "sex",
            "species",
            "subject_id",
            "tissue_sample_id",
            "slice_id",
        ),
        filter_=True,
    )

    DEFAULT_VALUES = ("REQUIRED", "RECOMMENDED", "OPTIONAL")

    def is_undefined(d, f):
        return d.get(f, DEFAULT_VALUES[0]) in DEFAULT_VALUES

    if uvs["age"]:
        if "age" not in rec:
            # TODO: could not figure out how to add proper ruaml structure here
            # so duplicating TODO
            rec["age"] = {"units": "TODO"}
        age = rec["age"]
        age["minimum"] = min(uvs["age"])
        age["maximum"] = max(uvs["age"])
        if age.get("units", None) in (None,) + DEFAULT_VALUES:  # template
            age.pop("units", None)
            age.insert(2, "units", "TODO", comment="REQUIRED")

    if uvs["sex"]:
        # TODO: may be group by subject_id and sex, and then get # per each sex
        rec["sex"] = sorted(uvs["sex"])

    for mfield, yfield in (
        ("subject_id", "subjects"),
        ("cell_id", "cells"),
        ("slice_id", "slices"),
        ("tissue_sample_id", "tissue_samples"),
    ):
        if uvs[mfield]:
            rec[f"number_of_{yfield}"] = len(uvs[mfield])

    if uvs["species"]:
        species = sorted(uvs["species"])
        if "organism" not in rec:
            rec["organism"] = [{}]
        rec["organism"][0]["species"] = species[0]
        for other in species[1:]:
            rec["organism"].append({"species": other})

    if uvs["experiment_description"] and is_undefined(rec, "description"):
        rec["description"] = "\n".join(sorted(uvs["experiment_description"]))

    for v in sorted(flattened(uvs["related_publications"] or [])):
        if "publications" not in rec:
            rec["publications"] = []
        # TODO: better harmonization
        strip_regex = "[- \t'\"]"
        v = re.sub("^" + strip_regex, "", v)
        v = re.sub(strip_regex + "$", "", v)
        if v not in rec["publications"]:
            rec["publications"].append(v)

    # Save result
    with open(filepath, "w") as f:
        yaml.dump(rec, f)


def _get_non_unique_paths(metadata):
    """Identify non-unique paths after mapping

    Parameters
    ----------
    metadata

    Returns
    -------
    dict:
       of dandi_path: list(orig paths)
    """
    # Verify that we got unique paths
    all_paths = [m["dandi_path"] for m in metadata]
    all_paths_unique = set(all_paths)
    non_unique = {}
    if not len(all_paths) == len(all_paths_unique):
        counts = Counter(all_paths)
        non_unique = {p: c for p, c in counts.items() if c > 1}
        # Let's prepare informative listing
        for p in non_unique:
            orig_paths = []
            for e in metadata:
                if e["dandi_path"] == p:
                    orig_paths.append(e["path"])
            non_unique[p] = orig_paths  # overload with the list instead of count
    return non_unique
