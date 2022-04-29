# Requirements for being a valid DANDI asset

## General
- dandiset.yaml must conform dandischema's model.
- All assets must have a non-zero file size.
- dandisets must conform BIDS or our DANDI layout
  - if dataset_description.json found on top level - BIDS, if not -- DANDI

### Upload

- we do not longer upload `dandiset.yaml` AFAIK -- that one should be edited
  online to ensure conformance to the schema etc
- echoing layout specific: we get a list of files, run validator(s) (depending on --validation option), get a list of
  valid/invalid files, behave according to `--validation` option (might skip invalid files)
- validation at "dataset" levels should happen before (unless --validation skip) and errors should be communicated before upload of individual files. Most likely we should
not abort upload on dandiset level errors.

### Validation

- we need to validate at dataset levels unless path restriction provided which does
  not include dataset(s) top directories
- then proceed to validation of all files in all datasets.
- all records should follow the structure decided upon in https://github.com/dandi/dandi-cli/issues/943 .
- Python interface would likely just return the list of validation records, but there might be a desire of another mode or alternative interface which would raise an exception with information if any error.
- We should provide output formatting options, so that default rendering would be alike one of `bids-validator` and/or `nwbinspect`, neatly summarizing across types of problems encountered
- Exit code in CLI should be non-0 if any error encountered
- TODO long term -- allow for config file options

## Dataset Layouts

### DANDI layout

- A simplified BIDS, no `/ses-*` subfolder, entities are known and slightly different
from BIDS.

#### Disambiguation requirements

At least one of the following should be present. in case of having to disambiguate
- session
- sample
- cell
- probe
- task (not in nwb at the moment, but we could use session timestamp)

#### Upload

- so far we were uploading only .nwb files and ignored all the others.

### BIDS datasets

#### Requirements

- Ultimate: be a valid BIDS dataset conforming to the BIDSVersion specified in `dataset_description.json`.
- ATM we support only two version `1.7.0+012` and `  `1.7.0+012+dandi001` as shipped under `dandi/support/bids/schemadata`.
- BIDS dataset might just contain `derivatives/` (i.e. lack directly present data)
  - if there is a `derivatives/{name}/dataset_description.json` -- BIDS (derivative) dataset and validated. If no -- then no validation

#### Upload

- `dandi upload` should upload all files, may be just ignoring `.dotfiles`, eventually
  whitelisting some (e.g. .datalad/, .bidsignore, ...)
- Horea: bids-validator outputs list of valid files.  So similarly to upload
  of nwb files ATM we want to warrant the `--validation` switch mode.

## Assets

## NWB files
- subject id (nwb.subject.subject_id)
- age in iso8601 interval format or datetime of birth (nwb.subject.age or nwb.subject.date_of_birth)
- age reference (not yet present in NWB, see issue https://github.com/NeurodataWithoutBorders/nwb-schema/issues/412)
- sex (nwb.subject.sex)

### Zarr/NGFF

- .zarr/,.ngff/ folders must be "openable" zarr "files"
