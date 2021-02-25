"""
ATM primarily a sandbox for some functionality for  dandi organize
"""

import binascii
from collections import Counter
from copy import deepcopy
import os
import os.path as op
from pathlib import Path
import re

import numpy as np

from .exceptions import OrganizeImpossibleError
from . import get_logger
from .pynwb_utils import get_neurodata_types_to_modalities_map, get_object_id
from .utils import ensure_datetime, flattened, yaml_load

lgr = get_logger()

# Fields which would be used to compose the filename
# TODO: add full description into command --help etc
# Order matters!
potential_fields = {
    # "type" - if not defined, additional
    "subject_id": {"format": "sub-{}", "type": "mandatory"},
    "session_id": {"format": "_ses-{}"},
    "tissue_sample_id": {"format": "_tis-{}"},
    "slice_id": {"format": "_slice-{}"},
    "cell_id": {"format": "_cell-{}"},
    # disambiguation ones
    "probe_ids": {"format": "_probe-{}", "type": "disambiguation"},
    "obj_id": {
        "format": "_obj-{}",
        "type": "disambiguation",
    },  # will be not id, but checksum of it to shorten
    # "session_description"
    "modalities": {"format": "_{}", "type": "mandatory_if_not_empty"},
    "extension": {"format": "{}", "type": "mandatory"},
}
# verify no typos
assert {v.get("type", "additional") for v in potential_fields.values()} == {
    "mandatory",
    "disambiguation",
    "additional",
    "mandatory_if_not_empty",
}
dandi_path = op.join("sub-{subject_id}", "{dandi_filename}")


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


def create_unique_filenames_from_metadata(metadata):
    """Create unique filenames given metadata

    Parameters
    ----------
    metadata: list of dict
      List of metadata records

    Returns
    -------
    dict
      Adjusted metadata. A copy, which might have removed some metadata fields
      Do not rely on it being the same
    """
    # need a deepcopy since we will be tuning fields, and there should be no
    # side effects to original metadata
    metadata = deepcopy(metadata)

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

    _assign_dandi_names(metadata)

    non_unique = _get_non_unique_paths(metadata)

    additional_nonunique = []
    if non_unique:
        # Consider additional fields which might provide disambiguation
        # but which we otherwise do not include ATM
        for field, field_rec in potential_fields.items():
            if not field_rec.get("type") == "disambiguation":
                continue
            additional_nonunique.append(field)
            if field == "obj_id":  # yet to be computed
                _assign_obj_id(metadata, non_unique)
            # If a given field is found useful to disambiguate in a single case,
            # we will add _mandatory_if_not_empty to those files records, which will
            # _assign_dandi_names will use in addition to the ones specified.
            # The use case of 000022 - there is a common to many probes file (has many probe_ids)
            # but listing them all in filename -- does not scale, so we only limit to where
            # needs disambiguation.
            # Cconsider conflicting groups and adjust their records
            for conflicting_path, paths in non_unique.items():
                # I think it might not work out entirely correctly if we have multiple
                # instances of non-unique, but then will consider not within each group...
                # yoh: TODO
                values = _get_unique_values_among_non_unique(metadata, paths, field)
                if values:  # helps disambiguation, but might still be non-unique
                    # add to all files in the group
                    for r in metadata:
                        if r["dandi_path"] == conflicting_path:
                            r["_mandatory_if_not_empty"] = r.get(
                                "_mandatory_if_not_empty", []
                            ) + [field]
                _assign_dandi_names(metadata)
            non_unique = _get_non_unique_paths(metadata)
            if not non_unique:
                break

    if non_unique:
        msg = "%d out of %d paths are still not unique" % (
            len(non_unique),
            len(metadata),
        )
        msg_detailed = msg + ":\n%s" % "\n".join(
            "   %s: %s" % i for i in non_unique.items()
        )
        raise OrganizeImpossibleError(
            msg_detailed
            + "\nEven after considering %s fields we ended up with non-unique file names. "
            "Should not have happened.\n"
            "Please adjust/provide metadata in your .nwb files to disambiguate"
            % (", ".join(additional_nonunique),)
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


def _get_hashable(v):
    """if a list - would cast to tuple"""
    if isinstance(v, list):
        return tuple(v)
    else:
        return v


def _get_unique_values_among_non_unique(metadata, non_unique_paths, field):
    """Per each non-unique path return values """
    return {
        _get_hashable(r.get(field))
        for r in metadata
        if (r["path"] in non_unique_paths) and not is_undefined(r.get(field))
    }


def get_obj_id(object_id):
    """Given full object_id, get its shortened version"""
    return np.base_repr(binascii.crc32(object_id.encode("ascii")), 36).lower()


def is_undefined(value):
    """Return True if None or an empty container"""
    return value is None or (hasattr(value, "__len__") and not len(value))


def _assign_dandi_names(metadata):
    unique_values = _get_unique_values(metadata, potential_fields)
    # unless it is mandatory, we would not include the fields with more than
    # a single unique field
    for r in metadata:
        dandi_filename = ""
        for field, field_rec in potential_fields.items():
            field_format = field_rec["format"]
            field_type = field_rec.get("type", "additional")
            if (
                (field_type == "mandatory")
                or (field_type == "additional" and len(unique_values[field]) > 1)
                or (
                    field_type == "mandatory_if_not_empty"
                    or (field in r.get("_mandatory_if_not_empty", []))
                )
            ):
                value = r.get(field, None)
                if is_undefined(value):
                    # skip empty things
                    continue
                if isinstance(value, (list, tuple)):
                    value = "+".join(map(str, value))
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
        unique_values[field] = set(_get_hashable(r.get(field, None)) for r in metadata)
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
        r["modalities"] = tuple(sorted(mods.union(set(r.get("modalities", {})))))


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
        rec = yaml_load(f)

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


def detect_link_type(workdir):
    """
    Determine what type of links the filesystem will let us make in the
    directory ``workdir``.  If symlinks are allowed, returns ``"symlink"``.
    Otherwise, if hard links are allowed, returns ``"hardlink"``.  Otherwise,
    returns ``"copy"``.
    """
    srcfile = Path(workdir, f".dandi.{os.getpid()}.src")
    destfile = Path(workdir, f".dandi.{os.getpid()}.dest")
    try:
        srcfile.touch()
        try:
            os.symlink(srcfile, destfile)
        except OSError:
            try:
                os.link(srcfile, destfile)
            except OSError:
                lgr.info(
                    "Symlink and hardlink tests both failed; setting files_mode='copy'"
                )
                return "copy"
            else:
                lgr.info(
                    "Hard link support autodetected; setting files_mode='hardlink'"
                )
                return "hardlink"
        else:
            lgr.info("Symlink support autodetected; setting files_mode='symlink'")
            return "symlink"
    finally:
        try:
            destfile.unlink()
        except FileNotFoundError:
            pass
        try:
            srcfile.unlink()
        except FileNotFoundError:
            pass
