# Changelog
All notable changes to this project will be documented (for humans) in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [0.6.0-rc1] - 2020-08-10

This a Release Candidate which is based on a good number of changes
which are in `master` branch and might still be released as 0.5.1
release.  Those changes are yet to be documented.

### Added
- `download` now can download from "published" (versioned) dandisets.
  The entire `download` was refactored and new UI also uses pyout (as
  `upload` and `ls`) so there will be no tqdm progress bar indicators.

## [0.5.0] - 2020-06-04

### Added
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
### Fixed
- `upload`: a crash while issuing a record to update about deleted empty item
### Refactored
- `organize`: disambiguation process now could use a flexible list of metadata
  fields (ATM only `probe_ids` and `obj_id`)
- `download`: handling of redirection - now uses `HEAD` request instead of `GET`

## [0.4.6] - 2020-05-07

### Fixed
- invoke etelemetry only in command line (at click interface level)
- download of updated dandiset landing page url (`/dandiset` not `/dandiset-meta`)

## [0.4.5] - 2020-05-01

### Added
- support for downloading dandisets and files in the just released
  gui.dandiarchive.org UI refactor
### Fixed
- `validate` should no longer crash if loading metadata raises an exception
### Refactored
- the way URLs are mapped into girder instances. Now more regex driven

## [0.4.4] - 2020-04-14

### Added
- `validate` now will report absent `subject_id` as an error
### Fixed
- Caching of multiple functions re-using the same cache -- it could
  have resulted in our case neural data types returned where full metadata
  was requested, or vise vera
- Tolerate outdated (before 2.0.0) etelemetry


## [0.4.3] - 2020-04-14

### Added
- Ability to download (multiple) individual files (using URL from
  gui.dandiarchive.org having files selected)
### Changed
- `DANDI_CACHE_CLEAR` -> `DANDI_CACHE=(ignore|clear)` env variable.
- Sanitize and tollerate better incorrect `nwb_version` field.
### Fixed
- Test to not invoke Popen with shell=True to avoid stalling.
- Explicit `NO_ET=1` in workflows to avoid overreporting to etelemetry.


## [0.4.2] - 2020-03-18

### Added
- Use of etelemetry for informing about new (or bad) versions
### Changed
- Fixed saving into yaml so it is consistently not using a flow style
  (#59)
- All file names starting with a period are not considered (#63)

## [0.4.1] - 2020-03-16

### Changed
- `organize` -- now would add `_obj-` key with the crc32 checksum
  of the nwb file `object_id` if files could not be otherwise
  disambiguated
- variety of small tune ups and fixes
### Removed
- `organize` -- not implemented option `--format`
- `upload` -- not properly implemented option `-d|--dandiset-path`

## [0.4.0] - 2020-03-13

Provides interfaces for a full cycle of dandiset preparation,
registration, upload, and download.

### Added
- caching of read metadata and validation results for .nwb files.
  Typically those take too long and as long as dandi and pynwb
  versions do not change -- results should not change.
  Set `DANDI_DEVEL` variable to forcefully reset all the caches.
### Changed
- DEVELOPMENT.md provides more information about full local
  test setup of the dandiarchive, and description of
  environment variables which could assist in development.

## [0.3.0] - 2020-02-28

### Added
- `organize`: organize files into hierarchy using metadata.
  ATM operates only in "simulate" mode using .json files dumped by `ls`
### Changed
- various refactorings and minor improvements (docs, testing, etc).


## [0.2.0] - 2020-02-04

Improvements to `ls` and `upload` commands

### Added
- `ls`: include a list (with counts) of neural datatypes in the file
- `upload`:
  - ability to reupload files (by removing already existing ones)
  - ability to "sync" (skip if not modified) to girder based on mtime
    and size
- CI (github actions): testing on macos-latest
### Changed
- removed `hdmf !=` statement in setup.cfg to not confuse pypi.
### Fixed
- `upload` - assure string for an error message
- mitigated crashes in pynwb if neural data type schema is not cached
  in the file and requires import of the extension module.  ATM the
  known/handled only the `AIBS_ecephys` from `allensdk`


## [Unreleased]

TODO Summary

### Added
### Changed
### Fixed
### Removed
### Security


[0.2.0]: https://github.com/dandi/dandi-cli/commits/0.2.0
