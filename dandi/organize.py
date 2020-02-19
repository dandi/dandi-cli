"""
ATM primarily a sandbox for some functionality for  dandi organize
"""

import os.path as op

from . import get_logger
from .pynwb_utils import get_neurodata_types_to_modalities_map

lgr = get_logger()


def filter_invalid_metadata_rows(metadata_rows):
    """Split into two lists - valid and invalid entries"""
    valid, invalid = [], []
    for row in metadata_rows:
        if row["nwb_version"] == "ERROR" or "subject_id" not in row:
            invalid.append(row)
        else:
            valid.append(row)
    return valid, invalid


def create_unique_filenames_from_metadata(metadata_rows, mandatory=["modalities"]):
    """

    Parameters
    ----------
    metadata_rows
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

    # Fields which would be used to compose the filename
    potential_fields = {
        "subject_id": "sub-{}",
        "session_id": "_ses-{}",
        # "session_description"
        "modalities": "_{}",
        "extension": "{}",
    }
    dandi_path = "sub-{subject_id}/{dandi_filename}"

    # extract extensions and place them into the records
    for r in metadata_rows:
        r["extension"] = op.splitext(r["path"])[1]

    # Add "modalities" composed from the ones we could deduce
    ndtypes_to_modalities = get_neurodata_types_to_modalities_map()
    ndtypes_unassigned = set()
    for r in metadata_rows:
        mods = set()
        for nd_rec in r.get("nd_types", "").split(","):
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

    unique_values = {}
    for field in potential_fields:
        unique_values[field] = set(r.get(field, None) for r in metadata_rows)

    # unless it is mandatory, we would not include the fields with more than
    # a single unique field
    for r in metadata_rows:
        dandi_filename = ""
        for field, field_format in potential_fields.items():
            if field in mandatory or len(unique_values[field]) > 1:
                value = r.get(field, None)
                if value is not None:
                    if isinstance(value, (list, tuple)):
                        value = "+".join(value)
                    formatted_value = field_format.format(value)
                    dandi_filename += formatted_value
        r["dandi_filename"] = dandi_filename
        r["dandi_path"] = dandi_path.format(**r)

    return metadata_rows
    # Only include fields with more than one value, for disambiguation
    # TODO this doesn't include the fact that somes might have a value and some
    # won't, and that would be disambiguating, but would require changes to how
    # the filename is constructed.
    disambiguating_fields = []
    for field in potential_fields:
        if len(unique_values[field]) > 1:
            disambiguating_fields.append(field)

    def construct_filename(metadata_row):
        filename = None
        for field in disambiguating_fields:
            if filename:
                filename += "_"
            else:
                filename = ""
            filename += field + "_" + metadata_row[field]
        return filename

    unique_filenames = set()
    for row in metadata_rows:
        dandi_filename = construct_filename(row)
        if dandi_filename in unique_filenames:
            # Abort because we do not have enough info for uniqueness
            raise RuntimeError("dandi_filename %s is NOT unique" % dandi_filename)
        else:
            row["dandi_filename"] = dandi_filename

    lgr.debug("disambiguating fields: %s", disambiguating_fields)

    return metadata_rows
