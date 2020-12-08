# 0.10.0 (Tue Dec 08 2020)

#### 🚀 Enhancement

- Set chunk size on per-file basis; limit to 1000 chunks; upload files up to 400GB ATM [#310](https://github.com/dandi/dandi-cli/pull/310) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Autogenerate schema element titles [#304](https://github.com/dandi/dandi-cli/pull/304) ([@jwodder](https://github.com/jwodder))
- Compare uploaded file size against what download headers report [#306](https://github.com/dandi/dandi-cli/pull/306) ([@jwodder](https://github.com/jwodder))
- fix: rat to common lab rat [#307](https://github.com/dandi/dandi-cli/pull/307) ([@satra](https://github.com/satra))

#### Authors: 3

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.9.0 (Fri Dec 04 2020)

#### 🚀 Enhancement

- Function for converting NWB file to AssetMeta instance [#226](https://github.com/dandi/dandi-cli/pull/226) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic) [@satra](https://github.com/satra))

#### 🐛 Bug Fix

- Temporary workaround: prevent upload of files larger than 67108864000 [#303](https://github.com/dandi/dandi-cli/pull/303) ([@yarikoptic](https://github.com/yarikoptic))
- Add title to `Field` calls where necessary [#299](https://github.com/dandi/dandi-cli/pull/299) ([@AlmightyYakob](https://github.com/AlmightyYakob) [@satra](https://github.com/satra))
- Replace askyesno() with click.confirm() [#296](https://github.com/dandi/dandi-cli/pull/296) ([@jwodder](https://github.com/jwodder))
- Test against & support Python 3.9 [#297](https://github.com/dandi/dandi-cli/pull/297) ([@jwodder](https://github.com/jwodder))
- ls - avoid workaround, more consistent reporting of errors [#293](https://github.com/dandi/dandi-cli/pull/293) ([@yarikoptic](https://github.com/yarikoptic))
- add dandimeta migration [#295](https://github.com/dandi/dandi-cli/pull/295) ([@satra](https://github.com/satra))
- Nwb2asset [#294](https://github.com/dandi/dandi-cli/pull/294) ([@satra](https://github.com/satra))
- Some schema updates [#286](https://github.com/dandi/dandi-cli/pull/286) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic) [@dandibot](https://github.com/dandibot) auto@nil [@satra](https://github.com/satra))
- make most things optional [#234](https://github.com/dandi/dandi-cli/pull/234) ([@satra](https://github.com/satra))

#### 🏠 Internal

- Fix more of publish-schemata workflow [#292](https://github.com/dandi/dandi-cli/pull/292) ([@jwodder](https://github.com/jwodder))

#### Authors: 6

- [@dandibot](https://github.com/dandibot)
- auto (auto@nil)
- Jacob Nesbitt ([@AlmightyYakob](https://github.com/AlmightyYakob))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.8.0 (Tue Dec 01 2020)

#### 🚀 Enhancement

- Add rudimentary duecredit support using zenodo's dandi-cli DOI [#285](https://github.com/dandi/dandi-cli/pull/285) ([@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- BF: add h5py.__version__ into the list of tokens for caching [#284](https://github.com/dandi/dandi-cli/pull/284) ([@yarikoptic](https://github.com/yarikoptic))
- change from disease to disorder [#291](https://github.com/dandi/dandi-cli/pull/291) ([@satra](https://github.com/satra))

#### 🏠 Internal

- Fix publish-schemata workflow [#290](https://github.com/dandi/dandi-cli/pull/290) ([@jwodder](https://github.com/jwodder))
- updated just models [#287](https://github.com/dandi/dandi-cli/pull/287) ([@satra](https://github.com/satra))
- Add workflow for publishing model schemata to dandi/schema [#276](https://github.com/dandi/dandi-cli/pull/276) ([@jwodder](https://github.com/jwodder))
- DOC: strip away duplicate with the handbook information [#279](https://github.com/dandi/dandi-cli/pull/279) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 3

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Satrajit Ghosh ([@satra](https://github.com/satra))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.7.2 (Thu Nov 19 2020)

#### 🐛 Bug Fix

- Support h5py 3.0 [#275](https://github.com/dandi/dandi-cli/pull/275) ([@jwodder](https://github.com/jwodder))
- Include item path in "Multiple files found for item" message [#271](https://github.com/dandi/dandi-cli/pull/271) ([@jwodder](https://github.com/jwodder))
- Copy files with `cp --reflink=auto` where supported [#269](https://github.com/dandi/dandi-cli/pull/269) ([@jwodder](https://github.com/jwodder))
- Make keyring lookup more flexible [#267](https://github.com/dandi/dandi-cli/pull/267) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Add healthchecks for the Postgres and minio Docker containers [#272](https://github.com/dandi/dandi-cli/pull/272) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# 0.7.1 (Thu Nov 05 2020)

#### 🐛 Bug Fix

- Use oldest file when race condition causes multiple files per item [#265](https://github.com/dandi/dandi-cli/pull/265) ([@jwodder](https://github.com/jwodder))

#### 🏠 Internal

- Set up workflow with auto for releasing & PyPI uploads [#257](https://github.com/dandi/dandi-cli/pull/257) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Remove unused link from CHANGELOG.md [#266](https://github.com/dandi/dandi-cli/pull/266) ([@jwodder](https://github.com/jwodder))

#### Authors: 1

- John T. Wodder II ([@jwodder](https://github.com/jwodder))

---

# [0.7.0] - 2020-11-04

## Added
- Files are now stored in temporary directories while downloading alongside
  metadata for use in resuming interrupted downloads

## Changed
- Moved code for navigating Dandi Archive into new `dandiarchive` submodule
- YAML output now sorts keys
- `dandiset.yaml` is no longer uploaded to the archive
- Restrict h5py dependency to pre-v3.0

# [0.6.4] - 2020-09-04

Primarily a range of bugfixes to ensure correct operation with current state
of other components of DANDI, and use of the client on Windows OS.

## Added
- Initial DANDI schema files
- More tests for various code paths
- `download`: new option `--download [assets,dandiset.yaml,all]`
## Fixed
- `download` - account for changes in DANDI API (relevant only for released
  datasets, of which we do not have any "real" ones yet)
- `upload` - various Windows specific fixes

Note: [0.6.3] was released under missing some of the fixes, so overall
abandoned.

# [0.6.2] - 2020-08-19

## Fixed
- `organize` treatment of paths on window (gh-204)

# [0.6.1] - 2020-08-18

## Changed
- CLI modules RF to avoid circular imports
- `pytest` default traceback style is short and shows 10 slowest tsts
## Fixed
- `download` of draft datasets from Windows (gh-202)
- `upload` and other tests to account for new web UI

# [0.6.0] - 2020-08-12

A variety of improvements and bug fixes, with major changes toward support
of a new DANDI API, and improving DX (Development eXperience).

## Added
- Support for WiP DANDI API service.
  `download` now can download from "published" (versioned) dandisets.
- A wide range of development enhancements
  - `tox` setup
  - code linting via `tox` and on github workflows
  - testing against Python 3.8
  - testing against a local instance of the archive via `docker-compose`,
    which is used against
- Locking of the dandiset during upload to prevent multiple sessions modifying
  the same dandiset in the archive
- `upload` now adds `uploaded_by` field into the item metadata
## Changed
- `download` was refactored and new UI also uses pyout (as
  `upload` and `ls`) so there will be no tqdm progress bar indicators.
  `download` also does "on-the-fly" integrity of the data as received
  (whenever corresponding metadata provided from the archive)
- `--log-level` could be numeric or specified in lower-case
- Unified YAML operations to `ruamel.yaml`
- Avoid hardcoded URLs for dandiarchive components by querying `/server-info`
- Improved logging for interactions with girder server
## Fixed
- minor compatibility issues across OSes

# [0.5.0] - 2020-06-04

## Added
- `metadata` and `organize`: extract and use `probe_ids` metadata to
  disambiguate (if needed)
- `organize`: `--devel-debug` option to perform metadata extraction serially
- `upload`:
  - `--allow-any-path` development option to allow upload of DANDI
    not yet 'unsupported' file types/paths
  - compute 4 digests (all are checksums ATM): md5, sha1, sha256, sha512
    and upload as a part of the metadata record
- `download`:
  - use the "fastest" available digest (sha1) to validate correctness of the
    download
  - follow redirections from arbitrary redirector (e.g., bit.ly). Succeeds
    only if the final URL is known to DANDI.
## Fixed
- `upload`: a crash while issuing a record to update about deleted empty item
## Refactored
- `organize`: disambiguation process now could use a flexible list of metadata
  fields (ATM only `probe_ids` and `obj_id`)
- `download`: handling of redirection - now uses `HEAD` request instead of `GET`

# [0.4.6] - 2020-05-07

## Fixed
- invoke etelemetry only in command line (at click interface level)
- download of updated dandiset landing page url (`/dandiset` not `/dandiset-meta`)

# [0.4.5] - 2020-05-01

## Added
- support for downloading dandisets and files in the just released
  gui.dandiarchive.org UI refactor
## Fixed
- `validate` should no longer crash if loading metadata raises an exception
## Refactored
- the way URLs are mapped into girder instances. Now more regex driven

# [0.4.4] - 2020-04-14

## Added
- `validate` now will report absent `subject_id` as an error
## Fixed
- Caching of multiple functions re-using the same cache -- it could
  have resulted in our case neural data types returned where full metadata
  was requested, or vise vera
- Tolerate outdated (before 2.0.0) etelemetry


# [0.4.3] - 2020-04-14

## Added
- Ability to download (multiple) individual files (using URL from
  gui.dandiarchive.org having files selected)
## Changed
- `DANDI_CACHE_CLEAR` -> `DANDI_CACHE=(ignore|clear)` env variable.
- Sanitize and tollerate better incorrect `nwb_version` field.
## Fixed
- Test to not invoke Popen with shell=True to avoid stalling.
- Explicit `NO_ET=1` in workflows to avoid overreporting to etelemetry.


# [0.4.2] - 2020-03-18

## Added
- Use of etelemetry for informing about new (or bad) versions
## Changed
- Fixed saving into yaml so it is consistently not using a flow style
  (#59)
- All file names starting with a period are not considered (#63)

# [0.4.1] - 2020-03-16

## Changed
- `organize` -- now would add `_obj-` key with the crc32 checksum
  of the nwb file `object_id` if files could not be otherwise
  disambiguated
- variety of small tune ups and fixes
## Removed
- `organize` -- not implemented option `--format`
- `upload` -- not properly implemented option `-d|--dandiset-path`

# [0.4.0] - 2020-03-13

Provides interfaces for a full cycle of dandiset preparation,
registration, upload, and download.

## Added
- caching of read metadata and validation results for .nwb files.
  Typically those take too long and as long as dandi and pynwb
  versions do not change -- results should not change.
  Set `DANDI_DEVEL` variable to forcefully reset all the caches.
## Changed
- DEVELOPMENT.md provides more information about full local
  test setup of the dandiarchive, and description of
  environment variables which could assist in development.

# [0.3.0] - 2020-02-28

## Added
- `organize`: organize files into hierarchy using metadata.
  ATM operates only in "simulate" mode using .json files dumped by `ls`
## Changed
- various refactorings and minor improvements (docs, testing, etc).


# [0.2.0] - 2020-02-04

Improvements to `ls` and `upload` commands

## Added
- `ls`: include a list (with counts) of neural datatypes in the file
- `upload`:
  - ability to reupload files (by removing already existing ones)
  - ability to "sync" (skip if not modified) to girder based on mtime
    and size
- CI (github actions): testing on macos-latest
## Changed
- removed `hdmf !=` statement in setup.cfg to not confuse pypi.
## Fixed
- `upload` - assure string for an error message
- mitigated crashes in pynwb if neural data type schema is not cached
  in the file and requires import of the extension module.  ATM the
  known/handled only the `AIBS_ecephys` from `allensdk`
