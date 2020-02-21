"""
ATM primarily a sandbox for some functionality for  dandi organize
"""

import dateutil.parser
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


def create_unique_filenames_from_metadata(
    metadata, mandatory=["modalities", "extension"]
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

    # Fields which would be used to compose the filename
    potential_fields = {
        "subject_id": "sub-{}",
        "session_id": "_ses-{}",
        # "session_description"
        "modalities": "_{}",
        "extension": "{}",
    }
    dandi_path = "sub-{subject_id}/{dandi_filename}"

    #
    # Additional fields
    #

    # extract File name extension and place them into the records
    for r in metadata:
        r["extension"] = op.splitext(r["path"])[1]

    # Add "modalities" composed from the ones we could deduce
    _populate_modalities(metadata)

    # handle cases where session_id was not provided
    # In some of those we could have session_start_time, so we could produce
    # session_id based on those
    if not all(m.get("session_id") for m in metadata):
        _populate_session_ids_from_time(metadata)

    unique_values = {}
    for field in potential_fields:
        unique_values[field] = set(r.get(field, None) for r in metadata)
    import pdb

    pdb.set_trace()
    # unless it is mandatory, we would not include the fields with more than
    # a single unique field
    for r in metadata:
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

    return metadata


def _populate_modalities(metadata):
    ndtypes_to_modalities = get_neurodata_types_to_modalities_map()
    ndtypes_unassigned = set()
    for r in metadata:
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
        ses_time = dateutil.parser.parse(ses_time)
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
        ses_time = dateutil.parser.parse(ses_time)
        m["session_id"] = "%d%02d%02d" % (ses_time.year, ses_time.month, ses_time.day)
        if not degenerate_time:
            m["session_id"] += "T%02d%02d%02d" % (
                ses_time.hour,
                ses_time.minute,
                ses_time.second,
            )
        nassigned += 1
    lgr.debug("Assigned %d session_id's based on the date" % nassigned)
