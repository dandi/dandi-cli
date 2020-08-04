# name: url
from collections import namedtuple

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

# checksums and other digests to compute on the files to upload
# Order matters - observed compute time from shorter to longer
# Those are not to be included in metadata reported for a local file,
# but will be available for files in the archive
metadata_digests = ("sha1", "md5", "sha512", "sha256")

dandiset_metadata_file = "dandiset.yaml"
dandiset_identifier_regex = "^[0-9]{6}$"

dandi_instance = namedtuple("dandi_instance", ("girder", "gui", "redirector"))

known_instances = {
    "local-girder-only": dandi_instance(
        "http://localhost:8080", None, None
    ),  # just pure girder
    # Redirector: TODO https://github.com/dandi/dandiarchive/issues/139
    "local-docker": dandi_instance(
        "http://localhost:8080", "http://localhost:8085", None
    ),
    "dandi": dandi_instance(
        "https://girder.dandiarchive.org",
        "https://gui.dandiarchive.org",
        "https://dandiarchive.org",
    ),
}
# to map back url: name
known_instances_rev = {vv: k for k, v in known_instances.items() for vv in v if vv}

collection_drafts = "drafts"
collection_releases = "releases"

file_operation_modes = ["dry", "simulate", "copy", "move", "hardlink", "symlink"]

#
# Some routes
# TODO: possibly centralize in dandi-common from our redirection service
#


# just a structure, better than dict for RFing etc
class routes(object):
    dandiset_draft = "{dandi_instance.redirector}/dandiset/{dandiset[identifier]}/draft"
