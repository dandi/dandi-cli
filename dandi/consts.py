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

metadata_dandi_fields = ("cell_id", "slice_id", "tissue_sample_id")

metadata_computed_fields = (
    "number_of_electrodes",
    "number_of_units",
    "nwb_version",
    "nd_types",
)

metadata_all_fields = (
    metadata_fields
    + metadata_subject_fields
    + metadata_dandi_fields
    + metadata_computed_fields
)

dandiset_metadata_file = "dandiset.yaml"
dandiset_identifier_regex = "^[0-9]{6}$"

# name: url
known_instances = {
    "local": "http://localhost:8080",
    "local91": "http://localhost:8091",  # as provided by entire archive docker compose. gui. on 8092
    "dandi": "https://girder.dandiarchive.org",
}
# to map back url: name
known_instances_rev = {v: k for k, v in known_instances.items()}
assert len(known_instances) == len(known_instances_rev)

collection_drafts = "drafts"
collection_releases = "releases"
