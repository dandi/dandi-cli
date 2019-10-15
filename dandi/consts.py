# A list of metadata fields which dandi extracts from .nwb files.
# Additional fields (such as `number_of_*`) might be added by the
# get_metadata`
metadata_fields = (
    "experiment_description",
    "experimenter",
    "identifier",  # note: required arg2 of NWBFile
    "institution",
    "keywords",
    "lab",
    "related_publications",
    "session_description",  # note: required arg1 of NWBFile
    "session_id",
    "session_start_time",
)

metadata_subject_fields = (
    "age",
    "date_of_birth",
    "genotype",
    "sex",
    "species",
    "subject_id",
)

metadata_computed_fields = ("number_of_electrodes", "number_of_units", "nwb_version")

metadata_all_fields = (
    metadata_fields + metadata_subject_fields + metadata_computed_fields
)
