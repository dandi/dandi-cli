# DANDI Client

[![Tests](https://github.com/dandi/dandi-cli/workflows/Tests/badge.svg)](https://github.com/dandi/dandi-cli/actions?query=workflow%3ATests)
[![codecov.io](https://codecov.io/github/dandi/dandi-cli/coverage.svg?branch=master)](https://codecov.io/github/dandi/dandi-cli?branch=master)
[![GitHub release](https://img.shields.io/github/release/dandi/dandi-cli.svg)](https://GitHub.com/dandi/dandi-cli/releases/)
[![PyPI version fury.io](https://badge.fury.io/py/dandi.svg)](https://pypi.python.org/pypi/dandi/)

This project is under heavy development.  Beware of [hidden](I-wish-we-knew) and
[disclosed](https://github.com/dandi/dandi-cli/issues) issues and
Work-in-Progress (WiP) (again might be [hidden](still-on-the-laptop-only) or
[public](https://github.com/dandi/dandi-cli/pulls)).

## Installation

At the moment DANDI client releases are [available from PyPI](https://pypi.org/project/dandi).  You could
install them in your Python (native, virtualenv, or conda) environment via

    pip install dandi

## dandi tool

This package provides a `dandi` command line utility with a basic interface
which should assist you in preparing and uploading your data to and/or obtaining
data from the http://dandiarchive.org:

```bash
$> dandi
Usage: dandi [OPTIONS] COMMAND [ARGS]...

  A client to support interactions with DANDI archive
  (http://dandiarchive.org).

Options:
  --version
  -l, --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  Log level name  [default: INFO]
  --pdb                           Fall into pdb if errors out
  --help                          Show this message and exit.

Commands:
  download  Download a file or entire folder from DANDI
  ls        List .nwb files and dandisets metadata.
  organize  (Re)organize files according to the metadata.
  register  Register a new dandiset in the DANDI archive
  upload    Upload dandiset (files) to DANDI archive.
  validate  Validate files for NWB (and DANDI) compliance.
```

Each of the commands has a set of options to alter their behavior.  Please run
`dandi COMMAND --help` to get more information, e.g.

```
$> dandi ls --help
Usage: dandi ls [OPTIONS] [PATHS]...

  List .nwb files metadata

Options:
  -F, --fields TEXT               Comma-separated list of fields to display.
                                  An empty value to trigger a list of
                                  available fields to be printed out
  -f, --format [auto|pyout|json|json_pp|yaml]
                                  Choose the format/frontend for output. If
                                  'auto', 'pyout' will be used in case of
                                  multiple files, and 'yaml' for a single
                                  file.
  --help                          Show this message and exit.
```

## Preparing and uploading a dandiset to dandiarchive.org

Although some functionality and final interface is still Work-in-Progress (WiP),
overall tentative target workflow will be:

1. Collect or convert your data files to [NWB](https://www.nwb.org) format.
   Files should have `.nwb` file extension.
2. Use `dandi validate` to verify that files conform
   [NWB schema](https://github.com/NeurodataWithoutBorders/nwb-schema/) and
   [DANDI requirements](TODO) (WiP) on contained in them metadata.
   If necessary, adjust your conversion scripts or use
   [helper utilities](TODO) to address concerns identified by `dandi validate`
   command.
3. Use `dandi organize` to

   - re-layout (move, rename) your files into a consistent naming convention
   - generate a template `dataset.yaml` with some fields pre-populated from
     metadata extracted from the `.nwb` files.

   1. If file names for some files could not be disambiguated, possibly see in
   providing additional metadata within `.nwb` files so they could be named
   without collisions, or
   [file an issue](https://github.com/dandi/dandi-cli/issues) describing your case.
   `dandi ls` command could come useful to quickly view metadata we consider.

   2. Fill out missing fields marked REQUIRED in the `dataset.yaml`, remove templated
   RECOMMENDED or OPTIONAL.

   Result of the reorganization is a dandiset -- a dataset with consistent layout,
   and dataset level metadata.

4. Rerun `dandi validate` on the entire dandiset to assure that everything is
   correct.
5. Use `dandi register` to register a new dataset ID on DANDI archive.  If you
   run it within a dandiset, its `dandiset.yaml` will be automatically updated
   to contain new dandiset identifier.
6. Use `dandi upload` to upload your dandiset to the archive
   ["drafts" collection](https://gui.dandiarchive.org/#/collection/5e59bb0af19e820ab6ea6c62).

If you change anything in your dandiset and decide to update its state in the
archive, just use `dandi upload` again.

You could also visit [doc/demos/basic-workflow1.sh](./doc/demos/basic-workflow1.sh) for an example script
which does all above actions (assuming no changes to files are necessary).


## Downloading dandiset from the archive

`dandi download` can be used to download full dandisets or individual files or
folders from the archive.

Using `--existing refresh` option available for
`dandi upload` and `dandi download` it is possible to avoid transfer if files
are identical locally and in the archive.

**Warning:**  There is no version control tracking beyond checking correspondence
of file size and modification time.  So in collaborative setting it is possible
to "refresh" a file which was modified locally with a version from the archive,
or vise versa.


## Development/contributing

Please see [DEVELOPMENT.md](./DEVELOPMENT.md) file.

## 3rd party components included

### dandi/support/generatorify.py

From https://github.com/eric-wieser/generatorify, as of 7bd759ecf88f836ece6cdbcf7ce1074260c0c5ef
Copyright (c) 2019 Eric Wieser, MIT/Expat licensed.

### dandi/tests/skip.py

From https://github.com/ReproNim/reproman, as of v0.2.1-40-gf4f026d
Copyright (c) 2016-2020  ReproMan Team
