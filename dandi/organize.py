"""
ATM primarily a sandbox for some functionality for  dandi organize
"""


def create_unique_filenames_from_metadata(metadata_rows):

    # TODO this does not act in a greedy fashion
    # i.e., only using enough fields to ensure uniqueness of filenames, but that
    # greedy field set could break if another file is incrementally added to the set
    # of filenames from which the greedy fields were determined.

    # TODO what to do if not all files have values for the same set of fields, i.e. some rows
    # are empty for certain fields?

    def filter_invalid_metadata_rows(metadata_rows):
        return [
            row
            for row in metadata_rows
            if not (row["nwb_version"] == "ERROR" or "subject_id" not in row)
        ]

    total_count = len(metadata_rows)
    metadata_rows = filter_invalid_metadata_rows(metadata_rows)
    error_count = total_count - len(metadata_rows)

    potential_filename_fields = ["subject_id", "session_id", "session_description"]
    metadata_key_unique_values = {}

    # TODO switch to default dict
    for field in potential_filename_fields:
        metadata_key_unique_values[field] = set()

    for row in metadata_rows:
        for field in potential_filename_fields:
            if field in row:
                metadata_key_unique_values[field].add(row[field])

    # Only include fields with more than one value, for disambiguation
    # TODO this doesn't include the fact that somes might have a value and some
    # won't, and that would be disambiguating, but would require changes to how
    # the filename is constructed.
    disambiguating_fields = []
    for field in potential_filename_fields:
        if len(metadata_key_unique_values[field]) > 1:
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
            print("dandi_filename %s is NOT unique" % dandi_filename)
            exit()
        else:
            row["dandi_filename"] = dandi_filename

    print("disambiguating fields: %s" % disambiguating_fields)
    print(
        "%s error files out of %s total files for error fraction of %s"
        % (error_count, total_count, (float(error_count) / float(total_count)))
    )

    return metadata_rows


if __name__ == "__main__":
    #from dandi.pynwb_utils import get_neurodata_types_to_modalities_map

    #print(get_neurodata_types_to_modalities_map())

    import json

    meta_filename = ""
    metadata_rows = []
    with open(meta_filename, "r") as f:
        for line in f.readlines():
            metadata_rows.append(json.loads(line))
    create_unique_filenames_from_metadata(metadata_rows)
