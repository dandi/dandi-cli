from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
import os

#: A list of metadata fields which dandi extracts from .nwb files.
#: Additional fields (such as ``number_of_*``) might be added by
#: `get_metadata()`
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

metadata_bids_fields = ("bids_schema_version",)

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

metadata_all_fields = (
    metadata_bids_fields + metadata_nwb_fields + metadata_dandiset_fields
)

#: Regular expression for a valid Dandiset identifier.  This regex is not
#: anchored.
DANDISET_ID_REGEX = r"[0-9]{6}"

#: Regular expression for a valid published (i.e., non-draft) Dandiset version
#: identifier.  This regex is not anchored.
PUBLISHED_VERSION_REGEX = r"[0-9]+\.[0-9]+\.[0-9]+"

#: Regular expression for a valid Dandiset version identifier.  This regex is
#: not anchored.
VERSION_REGEX = rf"(?:{PUBLISHED_VERSION_REGEX}|draft)"


class EmbargoStatus(Enum):
    OPEN = "OPEN"
    UNEMBARGOING = "UNEMBARGOING"
    EMBARGOED = "EMBARGOED"


dandiset_metadata_file = "dandiset.yaml"
dandiset_identifier_regex = f"^{DANDISET_ID_REGEX}$"


@dataclass(frozen=True)
class DandiInstance:
    name: str
    gui: str | None
    api: str

    @property
    def redirector(self) -> None:
        # For "backwards compatibility"
        return None

    def urls(self) -> Iterator[str]:
        if self.gui is not None:
            yield self.gui
        yield self.api


# So it could be easily mapped to external IP (e.g. from within VM)
# to test against instance running outside of current environment
instancehost = os.environ.get("DANDI_INSTANCEHOST", "localhost")

known_instances = {
    "dandi": DandiInstance(
        "dandi",
        "https://dandiarchive.org",
        "https://api.dandiarchive.org/api",
    ),
    "dandi-staging": DandiInstance(
        "dandi-staging",
        "https://gui-staging.dandiarchive.org",
        "https://api-staging.dandiarchive.org/api",
    ),
    "dandi-api-local-docker-tests": DandiInstance(
        "dandi-api-local-docker-tests",
        f"http://{instancehost}:8085",
        f"http://{instancehost}:8000/api",
    ),
    "linc": DandiInstance(
        "linc",
        "https://lincbrain.org",
        "https://api.lincbrain.org/api",
    ),
    "linc-staging": DandiInstance(
        "linc-staging",
        "https://staging.lincbrain.org",
        "https://staging-api.lincbrain.org/api",
    )
}
# to map back url: name
known_instances_rev = {
    vv: k for k, v in known_instances.items() for vv in v.urls() if vv
}

# Download (upload?) specific constants

#: Chunk size when iterating a download (and upload) body. Taken from girder-cli
#: TODO: should we make them smaller for download than for upload?
#: ATM used only in download
MAX_CHUNK_SIZE = int(os.environ.get("DANDI_MAX_CHUNK_SIZE", 1024 * 1024 * 8))  # 64

#: The identifier for draft Dandiset versions
DRAFT = "draft"

#: HTTP response status codes that should always be retried (until we run out
#: of retries)
RETRY_STATUSES = (500, 502, 503, 504)

VIDEO_FILE_EXTENSIONS = [".mp4", ".avi", ".wmv", ".mov", ".flv", ".mkv"]
VIDEO_FILE_MODULES = ["processing", "acquisition"]

ZARR_EXTENSIONS = [".ngff", ".zarr"]

#: Maximum allowed depth of a Zarr directory tree
MAX_ZARR_DEPTH = 7

#: MIME type assigned to & used to identify Zarr assets
ZARR_MIME_TYPE = "application/x-zarr"

#: Maximum number of Zarr directory entries to upload at once
ZARR_UPLOAD_BATCH_SIZE = 255

#: Maximum number of Zarr directory entries to delete at once
ZARR_DELETE_BATCH_SIZE = 100

BIDS_DATASET_DESCRIPTION = "dataset_description.json"

# Fields which would be used to compose organized filenames
# TODO: add full description into command --help etc
# Order matters!
dandi_layout_fields = {
    # "type" - if not defined, additional
    "subject_id": {"format": "sub-{}", "type": "required"},
    "session_id": {"format": "_ses-{}"},
    "tissue_sample_id": {"format": "_tis-{}"},
    "slice_id": {"format": "_slice-{}"},
    "cell_id": {"format": "_cell-{}"},
    # disambiguation ones
    "description": {"format": "_desc-{}", "type": "disambiguation"},
    "probe_ids": {"format": "_probe-{}", "type": "disambiguation"},
    "obj_id": {
        "format": "_obj-{}",
        "type": "disambiguation",
    },  # will be not id, but checksum of it to shorten
    # "session_description"
    "modalities": {"format": "_{}", "type": "required_if_not_empty"},
    "extension": {"format": "{}", "type": "required"},
}
# verify no typos
assert {v.get("type", "additional") for v in dandi_layout_fields.values()} == {
    "required",
    "disambiguation",
    "additional",
    "required_if_not_empty",
}

REQUEST_RETRIES = 12

DOWNLOAD_TIMEOUT = 30
