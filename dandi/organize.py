"""
ATM primarily a sandbox for some functionality for  dandi organize
"""

# TODO this does not act in a greedy fashion, that would be an update
# i.e., only using enough fields to ensure uniqueness of filenames, but that
# greedy field set could break if another file is incrementally added to the set
# of filenames from which the greedy fields were determined.

# TODO what to do if not all files have values for the same fields?

key_values = {}
# assume path is unique for now
nwbs = {}
fields_of_interest = ['subject_id', 'session_id', 'session_description']

import json

meta_filename = 'TODO'

with open(meta_filename, 'r') as f:
    error_count, total_count = 0, 0
    for line in f.readlines():
        data = json.loads(line)
        total_count += 1
        # subject_id is the only required filed for now
        if data['nwb_version'] == 'ERROR' or 'subject_id' not in data:
            error_count += 1
        else:
            if data['path'] in nwbs:
                # Assuming path is unique, if not, the script has a broken assumption
                print('path %s is NOT unique, aborting' % data['path'])
                exit()

            nwbs[data['path']] = data
 
            for field in fields_of_interest:
                field_set = key_values.get(field, set())
                field_set.add(data[field])
                key_values[field] = field_set

    # only include fields with more than one value, for disambiguation
    disambiguating_fields = []
    for field in fields_of_interest:
        if len(key_values[field]) > 1:
            disambiguating_fields.append(field)
 
    unique_filenames = set()
    for path, nwb_meta in nwbs.items():
        filename = None
        for field in disambiguating_fields:
            if filename:
                filename += '_'
            else:
                filename = ''
            filename += field + '_' + nwb_meta[field]
        if filename in unique_filenames:
            # Abort because we do not have enough info for uniqueness
            print('filename %s is NOT unique' % filename)
            exit()
        else:
            print('filename %s is unique' % filename)

    print('disambiguating fields: %s' % disambiguating_fields) 
    print('%s error files out of %s total files for error fraction of %s' % (error_count, total_count, error_count / total_count))

if __name__ == "__main__":
    from dandi.pynwb_utils import get_neurodata_types_to_modalities_map

    print(get_neurodata_types_to_modalities_map())
