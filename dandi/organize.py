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
from typing import List
import uuid

import numpy as np

from . import get_logger
from .dandiset import Dandiset
from .exceptions import OrganizeImpossibleError
from .metadata import get_metadata
from .pynwb_utils import (
    get_neurodata_types_to_modalities_map,
    get_object_id,
    ignore_benign_pynwb_warnings,
    rename_nwb_external_files,
)
from .utils import (
    Parallel,
    copy_file,
    delayed,
    ensure_datetime,
    find_files,
    flattened,
    is_url,
    load_jsonl,
    move_file,
    yaml_load,
)

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


def _create_external_file_names(metadata: List[dict]) -> List[dict]:
    """Updates the metadata dict with renamed external files.

    Renames the external_file attribute in an ImageSeries according to the rule:
    <nwbfile name>/<ImageSeries uuid>_external_file_<no><.ext>
    Example, the Initial name of file:
        external_file = [name1.mp4]
    rename to:
        external_file = [dandiset-path-of-nwbfile/
                dandi-renamed-nwbfile_name(folder without extension .nwb)/
                f'{ImageSeries.object_id}_external_file_0.mp4'
    This is stored in a new field in the metadata:
    metadata['external_file_objects'][0]['external_files_renamed'] = <renamed_string>

    Parameters
    ----------
    metadata: list
        list of metadata dictionaries created during the call to pynwb_utils._get_pynwb_metadata
    Returns
    -------
    metadata: list
        updated list of metadata dictionaries
    """
    metadata = deepcopy(metadata)
    for meta in metadata:
        if "dandi_path" not in meta or "external_file_objects" not in meta:
            continue
        nwb_folder_name = op.splitext(op.basename(meta["dandi_path"]))[0]
        for ext_file_dict in meta["external_file_objects"]:
            renamed_path_list = []
            uuid_str = ext_file_dict.get("id", str(uuid.uuid4()))
            for no, ext_file in enumerate(ext_file_dict["external_files"]):
                renamed = op.join(
                    nwb_folder_name, f"{uuid_str}_external_file_{no}{ext_file.suffix}"
                )
                renamed_path_list.append(renamed)
            ext_file_dict["external_files_renamed"] = renamed_path_list
    return metadata


def organize_external_files(
    metadata: List[dict], dandiset_path: str, files_mode: str
) -> None:
    """Organizes the external_files into the new Dandiset folder structure.

    Parameters
    ----------
    metadata: list
        list of metadata dictionaries created during the call to pynwb_utils._get_pynwb_metadata
    dandiset_path: str
        full path of the main dandiset folder.
    files_mode: str
        one of "symlink", "copy", "move", "hardlink"

    """
    for e in metadata:
        for ext_file_dict in e["external_file_objects"]:
            for no, (name_old, name_new) in enumerate(
                zip(
                    ext_file_dict["external_files"],
                    ext_file_dict["external_files_renamed"],
                )
            ):
                if is_url(str(name_old)):
                    continue
                new_path = op.join(dandiset_path, op.dirname(e["dandi_path"]), name_new)
                name_old_str = str(name_old)
                if not op.isabs(name_old_str):
                    name_old_str = op.join(op.dirname(e["path"]), name_old_str)
                if not op.exists(name_old_str):
                    lgr.error("%s does not exist", name_old_str)
                    raise FileNotFoundError(f"{name_old_str} does not exist")
                os.makedirs(op.dirname(new_path), exist_ok=True)
                if files_mode == "symlink":
                    os.symlink(name_old_str, new_path)
                elif files_mode == "hardlink":
                    os.link(name_old_str, new_path)
                elif files_mode == "copy":
                    copy_file(name_old_str, new_path)
                elif files_mode == "move":
                    move_file(name_old_str, new_path)
                else:
                    raise NotImplementedError(files_mode)


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
    """Per each non-unique path return values"""
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
    value = re.sub(r"[_*\\/<>:|\"'?%@;]", "-", value)
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


def detect_link_type(srcfile, destdir):
    """
    Determine what type of links the filesystem will let us make from the file
    ``srcfile`` to the directory ``destdir``.  If symlinks are allowed, returns
    ``"symlink"``.  Otherwise, if hard links are allowed, returns
    ``"hardlink"``.  Otherwise, returns ``"copy"``.
    """
    destfile = Path(destdir, f".dandi.{os.getpid()}.dest")
    try:
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


def organize(
    paths,
    dandiset_path=None,
    invalid="fail",
    files_mode="auto",
    devel_debug=False,
    update_external_file_paths=False,
    media_files_mode=None,
):
    in_place = False  # If we deduce that we are organizing in-place

    # will come handy when dry becomes proper separate option
    def dry_print(msg):
        print(f"DRY: {msg}")

    if files_mode == "dry":

        def act(func, *args, **kwargs):
            dry_print(f"{func.__name__} {args}, {kwargs}")

    else:

        def act(func, *args, **kwargs):
            lgr.debug("%s %s %s", func.__name__, args, kwargs)
            return func(*args, **kwargs)

    if update_external_file_paths and files_mode not in ["copy", "move"]:
        raise ValueError(
            "--files-mode needs to be one of 'copy/move' for the rewrite option to work"
        )

    if dandiset_path is None:
        dandiset = Dandiset.find(os.curdir)
        if not dandiset:
            raise ValueError(
                "No --dandiset-path was provided, and no dandiset was found "
                "in/above current directory"
            )
        dandiset_path = dandiset.path
        del dandiset

    # Early checks to not wait to fail
    if files_mode == "simulate":
        # in this mode we will demand the entire output folder to be absent
        if op.exists(dandiset_path):
            # TODO: RF away
            raise RuntimeError(
                "In simulate mode %r (--dandiset-path) must not exist, we will create it."
                % dandiset_path
            )

    ignore_benign_pynwb_warnings()

    if not paths:
        try:
            Dandiset(dandiset_path)
        except Exception as exc:
            lgr.debug("Failed to find dandiset at %s: %s", dandiset_path, exc)
            raise ValueError(
                f"No dandiset was found at {dandiset_path}, and no "
                f"paths were provided"
            )
        if files_mode not in ("dry", "move"):
            raise ValueError(
                "Only 'dry' or 'move' mode could be used to operate in-place "
                "within a dandiset (no paths were provided)"
            )
        lgr.info("We will organize %s in-place", dandiset_path)
        in_place = True
        paths = [dandiset_path]

    if len(paths) == 1 and paths[0].endswith(".json"):
        # Our dumps of metadata
        metadata = load_jsonl(paths[0])
        link_test_file = metadata[0]["path"]
    else:
        paths = list(find_files(r"\.nwb\Z", paths=paths))
        link_test_file = paths[0] if paths else None
        lgr.info("Loading metadata from %d files", len(paths))
        # Done here so we could still reuse cached 'get_metadata'
        # without having two types of invocation and to guard against
        # problematic ones -- we have an explicit option on how to
        # react to those
        # Doesn't play nice with Parallel
        # with tqdm.tqdm(desc="Files", total=len(paths), unit="file", unit_scale=False) as pbar:
        failed = []

        def _get_metadata(path):
            try:
                meta = get_metadata(path)
            except Exception as exc:
                meta = {}
                failed.append(path)
                # pbar.desc = "Files (%d failed)" % len(failed)
                lgr.debug("Failed to get metadata for %s: %s", path, exc)
            # pbar.update(1)
            meta["path"] = path
            return meta

        if not devel_debug:
            # Note: It is Python (pynwb) intensive, not IO, so ATM there is little
            # to no benefit from Parallel without using multiproc!  But that would
            # complicate progress bar indication... TODO
            metadata = list(
                Parallel(n_jobs=-1, verbose=10)(
                    delayed(_get_metadata)(path) for path in paths
                )
            )
        else:
            metadata = list(map(_get_metadata, paths))
        if failed:
            lgr.warning(
                "Failed to load metadata for %d out of %d files",
                len(failed),
                len(paths),
            )

    metadata, skip_invalid = filter_invalid_metadata_rows(metadata)
    if skip_invalid:
        msg = (
            "%d out of %d files were found not containing all necessary "
            "metadata: %s"
            % (
                len(skip_invalid),
                len(metadata) + len(skip_invalid),
                ", ".join(m["path"] for m in skip_invalid),
            )
        )
        if invalid == "fail":
            raise ValueError(msg)
        elif invalid == "warn":
            lgr.warning(msg + " They will be skipped")
        else:
            raise ValueError(f"invalid has an invalid value {invalid}")

    if not op.exists(dandiset_path):
        act(os.makedirs, dandiset_path)

    if files_mode == "auto":
        files_mode = detect_link_type(link_test_file, dandiset_path)

    metadata = create_unique_filenames_from_metadata(metadata)

    # update metadata with external_file information:
    external_files_missing_in_nwbfiles = [
        len(m["external_file_objects"]) == 0 for m in metadata
    ]

    if all(external_files_missing_in_nwbfiles) and update_external_file_paths:
        lgr.warning(
            "--update-external-file-paths specified but no external_files found "
            "linked to any nwbfile found in %s",
            paths,
        )
    elif not all(external_files_missing_in_nwbfiles) and not update_external_file_paths:
        files_list = [
            metadata[no]["path"]
            for no, a in enumerate(external_files_missing_in_nwbfiles)
            if not a
        ]
        raise ValueError(
            "--update-external-file-paths option not specified but found "
            "external video files linked to the nwbfiles "
            f"{', '.join(files_list)}"
        )

    if update_external_file_paths and media_files_mode is None:
        media_files_mode = "symlink"
        lgr.warning(
            "--media-files-mode not specified, setting to recommended mode: 'symlink' "
        )

    # look for multiple nwbfiles linking to one video:
    if media_files_mode == "move":
        videos_list = []
        for meta in metadata:
            for ext_ob in meta["external_file_objects"]:
                videos_list.extend(ext_ob.get("external_files", []))
        if len(set(videos_list)) < len(videos_list):
            raise ValueError(
                "multiple nwbfiles linked to one video file, "
                "provide 'media_files_mode' as copy/symlink/hardlink"
            )

    metadata = _create_external_file_names(metadata)

    # Verify first that the target paths do not exist yet, and fail if they do
    # Note: in "simulate" mode we do early check as well, so this would be
    # duplicate but shouldn't hurt
    existing = []
    for e in metadata:
        dandi_fullpath = op.join(dandiset_path, e["dandi_path"])
        if op.exists(dandi_fullpath):
            # It might be the same file, then we would not complain
            if not (
                op.realpath(e["path"])
                == op.realpath(op.join(dandiset_path, e["dandi_path"]))
            ):
                existing.append(dandi_fullpath)
            # TODO: it might happen that with "move" we are renaming files
            # so there is an existing, which also gets moved away "first"
            # May be we should RF so the actual loop below would be first done
            # "dry", collect info on what is actually to be done, and then we would complain here
    if existing:
        raise AssertionError(
            "%d paths already exist: %s%s.  Remove them first."
            % (
                len(existing),
                ", ".join(existing[:5]),
                " and more" if len(existing) > 5 else "",
            )
        )

    # we should take additional care about paths if both top_path and
    # provided paths are relative
    use_abs_paths = op.isabs(dandiset_path) or any(
        op.isabs(e["path"]) for e in metadata
    )
    skip_same = []
    acted_upon = []
    for e in metadata:
        dandi_path = e["dandi_path"]
        dandi_fullpath = op.join(dandiset_path, dandi_path)
        dandi_abs_fullpath = (
            op.abspath(dandi_fullpath)
            if not op.isabs(dandi_fullpath)
            else dandi_fullpath
        )
        dandi_dirpath = op.dirname(dandi_fullpath)  # could be sub-... subdir

        e_path = e["path"]
        e_abs_path = e_path

        if not op.isabs(e_path):
            e_abs_path = op.abspath(e_path)
            if use_abs_paths:
                e_path = e_abs_path
            elif files_mode == "symlink":  # path should be relative to the target
                e_path = op.relpath(e_abs_path, dandi_dirpath)

        if dandi_abs_fullpath == e_abs_path:
            lgr.debug("Skipping %s since the same in source/destination", e_path)
            skip_same.append(e)
            continue
        elif files_mode == "symlink" and op.realpath(dandi_abs_fullpath) == op.realpath(
            e_abs_path
        ):
            lgr.debug(
                "Skipping %s since mode is symlink and both resolve to the same path",
                e_path,
            )
            skip_same.append(e)
            continue

        if (
            files_mode == "dry"
        ):  # TODO: this is actually a files_mode on top of modes!!!?
            dry_print(f"{e_path} -> {dandi_path}")
        else:
            if not op.exists(dandi_dirpath):
                os.makedirs(dandi_dirpath)
            if files_mode == "simulate":
                os.symlink(e_path, dandi_fullpath)
                continue
            #
            if files_mode == "symlink":
                os.symlink(e_path, dandi_fullpath)
            elif files_mode == "hardlink":
                os.link(e_path, dandi_fullpath)
            elif files_mode == "copy":
                copy_file(e_path, dandi_fullpath)
            elif files_mode == "move":
                move_file(e_path, dandi_fullpath)
            else:
                raise NotImplementedError(files_mode)
            acted_upon.append(e)

    if acted_upon and in_place:
        # We might need to cleanup a bit - e.g. prune empty directories left
        # by the move in in-place mode
        dirs = set(op.dirname(e["path"]) for e in acted_upon)
        for d in sorted(dirs)[::-1]:  # from longest to shortest
            if op.exists(d):
                try:
                    os.rmdir(d)
                    lgr.info("Removed empty directory %s", d)
                except Exception as exc:
                    lgr.debug("Failed to remove directory %s: %s", d, exc)

    # create video file name and re write nwb file external files:
    if update_external_file_paths:
        rename_nwb_external_files(metadata, dandiset_path)
        organize_external_files(metadata, dandiset_path, media_files_mode)

    def msg_(msg, n, cond=None):
        if hasattr(n, "__len__"):
            n = len(n)
        if cond is None:
            cond = bool(n)
        if not cond:
            return ""
        return msg % n

    lgr.info(
        "Organized %d%s paths%s.%s Visit %s/",
        len(acted_upon),
        msg_(" out of %d", metadata, len(metadata) != len(acted_upon)),
        msg_(" (%d same existing skipped)", skip_same),
        msg_(" %d invalid not considered.", skip_invalid),
        dandiset_path.rstrip("/"),
    )
