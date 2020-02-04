# Changelog
All notable changes to this project will be documented (for humans) in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

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
