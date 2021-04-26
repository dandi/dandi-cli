# DANDI Client

[![Tests](https://github.com/dandi/dandi-cli/workflows/Tests/badge.svg)](https://github.com/dandi/dandi-cli/actions?query=workflow%3ATests)
[![codecov.io](https://codecov.io/github/dandi/dandi-cli/coverage.svg?branch=master)](https://codecov.io/github/dandi/dandi-cli?branch=master)
[![GitHub release](https://img.shields.io/github/release/dandi/dandi-cli.svg)](https://GitHub.com/dandi/dandi-cli/releases/)
[![PyPI version fury.io](https://badge.fury.io/py/dandi.svg)](https://pypi.python.org/pypi/dandi/)

This project is under heavy development.  Beware of [hidden](I-wish-we-knew) and
[disclosed](https://github.com/dandi/dandi-cli/issues) issues, or
[Work-in-Progress (WiP)](https://github.com/dandi/dandi-cli/pulls).

## Installation

At the moment DANDI client releases are [available from PyPI](https://pypi.org/project/dandi)
and [conda-forge](https://anaconda.org/conda-forge/dandi).  You could
install them in your Python (native, virtualenv, or conda) environment via

    pip install dandi

or

   conda install -c conda-forge dandi

if you are in a conda environment.

## dandi tool

This package provides a `dandi` command line utility with a basic interface
which should assist you in preparing and uploading your data to and/or obtaining
data from the http://dandiarchive.org:

```bash
$> dandi
Usage: dandi [OPTIONS] COMMAND [ARGS]...

  A client to support interactions with DANDI archive
  (http://dandiarchive.org).

  To see help for a specific command, run

      dandi COMMAND --help

  e.g. dandi upload --help

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

See [DANDI Handbook](https://www.dandiarchive.org/handbook/10_using_dandi/)
for examples on how to use this client in various use cases.

## Development/contributing

Please see [DEVELOPMENT.md](./DEVELOPMENT.md) file.

## 3rd party components included

### dandi/core/digests/dandietag.py

From <https://github.com/girder/django-s3-file-field> as of v0.1.1-10-g829b9b0
Copyright (c) 2019-2021 Kitware, Inc., Apache 2.0 license

### dandi/support/generatorify.py

From https://github.com/eric-wieser/generatorify, as of 7bd759ecf88f836ece6cdbcf7ce1074260c0c5ef
Copyright (c) 2019 Eric Wieser, MIT/Expat licensed.

### dandi/tests/skip.py

From https://github.com/ReproNim/reproman, as of v0.2.1-40-gf4f026d
Copyright (c) 2016-2020  ReproMan Team
