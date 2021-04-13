# name: url
from collections import namedtuple

# A list of metadata fields which dandi extracts from .nwb files.
# Additional fields (such as `number_of_*`) might be added by the
# get_metadata`
import os

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

# checksums and other digests to compute on the files to upload
# Order matters - observed compute time from shorter to longer
# Those are not to be included in metadata reported for a local file,
# but will be available for files in the archive
metadata_digests = ("sha1", "md5", "sha512", "sha256")

dandiset_metadata_file = "dandiset.yaml"
dandiset_identifier_regex = "^[0-9]{6}$"

dandi_instance = namedtuple(
    "dandi_instance", ("metadata_version", "girder", "gui", "redirector", "api")
)

# So it could be easily mapped to external IP (e.g. from within VM)
# to test against instance running outside of current environment
instancehost = os.environ.get("DANDI_INSTANCEHOST", "localhost")

known_instances = {
    "local-girder-only": dandi_instance(
        0, f"http://{instancehost}:8080", None, None, None
    ),  # just pure girder
    # Redirector: TODO https://github.com/dandi/dandiarchive/issues/139
    "local-docker": dandi_instance(
        0,
        f"http://{instancehost}:8080",
        f"http://{instancehost}:8085",
        None,
        f"http://{instancehost}:9000",  # ATM it is minio, not sure where /api etc
        # may be https://github.com/dandi/dandi-publish/pull/71 would help
    ),
    "local-docker-tests": dandi_instance(
        0,
        f"http://{instancehost}:8081",
        f"http://{instancehost}:8086",
        f"http://{instancehost}:8079",
        None,
    ),
    "dandi": dandi_instance(
        0,
        "https://girder.dandiarchive.org",
        "https://gui.dandiarchive.org",
        "https://dandiarchive.org",
        None,  # publish. is gone, superseded by API which did not yet fully superseded the rest
    ),
    "dandi-api": dandi_instance(
        1,
        None,
        "https://gui-beta-dandiarchive-org.netlify.app",
        None,
        "https://api.dandiarchive.org/api",
    ),
    "dandi-api-local-docker-tests": dandi_instance(
        1, None, None, None, f"http://{instancehost}:8000/api"
    ),
}
# to map back url: name
known_instances_rev = {vv: k for k, v in known_instances.items() for vv in v if vv}

collection_drafts = "drafts"
collection_releases = "releases"

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

#
# Some routes
# TODO: possibly centralize in dandi-common from our redirection service
#


# just a structure, better than dict for RFing etc
class routes(object):
    dandiset_draft = "{dandi_instance.redirector}/dandiset/{dandiset[identifier]}/draft"


DANDI_SCHEMA_VERSION = "0.3.0"
