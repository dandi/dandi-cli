from collections import namedtuple
import os

# A list of metadata fields which dandi extracts from .nwb files.
# Additional fields (such as `number_of_*`) might be added by the
# get_metadata`
metadata_nwb_file_fields = (
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

metadata_nwb_subject_fields = (
    "age",
    "date_of_birth",
    "genotype",
    "sex",
    "species",
    "subject_id",
)

metadata_nwb_dandi_fields = ("cell_id", "slice_id", "tissue_sample_id", "probe_ids")

metadata_nwb_computed_fields = (
    "number_of_electrodes",
    "number_of_units",
    "nwb_version",
    "nd_types",
)

metadata_nwb_fields = (
    metadata_nwb_file_fields
    + metadata_nwb_subject_fields
    + metadata_nwb_dandi_fields
    + metadata_nwb_computed_fields
)

# TODO: include/use schema, for now hardcoding most useful ones to be used
# while listing dandisets
metadata_dandiset_fields = (
    "identifier",
    "name",
    "description",
    "license",
    "keywords",
    "version",
    "doi",
    "url",
    "variables_measured",
    "sex",
    "organism",
    "probe_ids",
    "number_of_subjects",
    "number_of_cells",
    "number_of_tissue_samples",
)

metadata_all_fields = metadata_nwb_fields + metadata_dandiset_fields

dandiset_metadata_file = "dandiset.yaml"
dandiset_identifier_regex = "^[0-9]{6}$"
VERSION_REGEX = r"(?:[.0-9]{5,}|draft)"

DandiInstance = namedtuple("DandiInstance", ("gui", "redirector", "api"))

# So it could be easily mapped to external IP (e.g. from within VM)
# to test against instance running outside of current environment
instancehost = os.environ.get("DANDI_INSTANCEHOST", "localhost")

redirector_base = os.environ.get("DANDI_REDIRECTOR_BASE", "https://dandiarchive.org")

known_instances = {
    "dandi": DandiInstance(
        "https://gui.dandiarchive.org",
        redirector_base,
        "https://api.dandiarchive.org/api",
    ),
    "dandi-devel": DandiInstance(
        "https://gui-beta-dandiarchive-org.netlify.app",
        None,
        None,
    ),
    "dandi-staging": DandiInstance(
        "https://gui-staging.dandiarchive.org",
        None,
        "https://api-staging.dandiarchive.org/api",
    ),
    "dandi-api-local-docker-tests": DandiInstance(
        None, None, f"http://{instancehost}:8000/api"
    ),
}
# to map back url: name
known_instances_rev = {vv: k for k, v in known_instances.items() for vv in v if vv}

file_operation_modes = [
    "dry",
    "simulate",
    "copy",
    "move",
    "hardlink",
    "symlink",
    "auto",
]

#
# Download (upload?) specific constants
#
# Chunk size when iterating a download (and upload) body. Taken from girder-cli
# TODO: should we make them smaller for download than for upload?
# ATM used only in download
MAX_CHUNK_SIZE = int(os.environ.get("DANDI_MAX_CHUNK_SIZE", 1024 * 1024 * 8))  # 64

DRAFT = "draft"
