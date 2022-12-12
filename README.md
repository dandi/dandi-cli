# DANDI Client

[![Tests](https://github.com/dandi/dandi-cli/workflows/Tests/badge.svg)](https://github.com/dandi/dandi-cli/actions?query=workflow%3ATests)
[![codecov.io](https://codecov.io/github/dandi/dandi-cli/coverage.svg?branch=master)](https://codecov.io/github/dandi/dandi-cli?branch=master)
[![GitHub release](https://img.shields.io/github/release/dandi/dandi-cli.svg)](https://GitHub.com/dandi/dandi-cli/releases/)
[![PyPI version fury.io](https://badge.fury.io/py/dandi.svg)](https://pypi.python.org/pypi/dandi/)
[![Documentation Status](https://readthedocs.org/projects/dandi/badge/?version=latest)](https://dandi.readthedocs.io/en/latest/?badge=latest)

The [DANDI Python client](https://pypi.org/project/dandi/) allows you to:

* Download `Dandisets` and individual subject folders or files
* Validate data to locally conform to standards
* Organize your data locally before upload
* Upload `Dandisets`
* Interact with the DANDI archive's web API from Python
* Delete data in the DANDI archive
* Perform other auxiliary operations with data or the DANDI archive

**Note**: This project is under heavy development. See [the issues log](https://github.com/dandi/dandi-cli/issues) or
[Work-in-Progress (WiP)](https://github.com/dandi/dandi-cli/pulls).

## Installation

DANDI Client releases are [available from PyPI](https://pypi.org/project/dandi)
and [conda-forge](https://anaconda.org/conda-forge/dandi).  Install them in your Python (native, virtualenv, or 
conda) environment via

    pip install dandi

or

    conda install -c conda-forge dandi


## CLI Tool

This package provides a command line utility with a basic interface
to help you prepare and upload your data to, or obtain data from, the [DANDI archive](http://dandiarchive.org):

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
                                  Log level (case insensitive).  May be
                                  specified as an integer.  [default: INFO]
  --pdb                           Fall into pdb if errors out
  --help                          Show this message and exit.

Commands:
  delete            Delete dandisets and assets from the server.
  digest            Calculate file digests
  download          Download a file or entire folder from DANDI.
  instances         List known Dandi Archive instances that the CLI can...
  ls                List .nwb files and dandisets metadata.
  move              Move or rename assets in a local Dandiset and/or on...
  organize          (Re)organize files according to the metadata.
  service-scripts   Various utility operations
  shell-completion  Emit shell script for enabling command completion.
  upload            Upload Dandiset files to DANDI Archive.
  validate          Validate files for NWB and DANDI compliance.
  validate-bids     Validate BIDS paths.
```

Each of the commands has a set of options to alter its behavior.  Run
`dandi COMMAND --help` to get more information:

```
$> dandi ls --help
Usage: dandi ls [OPTIONS] PATH|URL

  List .nwb files and dandisets metadata.

  The arguments may be either resource identifiers or paths to local
  files/directories.

  Accepted resource identifier patterns:
   - DANDI:<dandiset id>[/<version>]
   - https://dandiarchive.org/...
   - https://identifiers.org/DANDI:<dandiset id>[/<version id>] (<version id> cannot be 'draft')
   - https://<server>[/api]/[#/]dandiset/<dandiset id>[/<version>][/files[?location=<path>]]
   - https://*dandiarchive-org.netflify.app/...
   - https://<server>[/api]/dandisets/<dandiset id>[/versions[/<version>]]
   - https://<server>[/api]/assets/<asset id>[/download]
   - https://<server>[/api]/dandisets/<dandiset id>/versions/<version>/assets/<asset id>[/download]
   - https://<server>[/api]/dandisets/<dandiset id>/versions/<version>/assets/?path=<path>
   - dandi://<instance name>/<dandiset id>[@<version>][/<path>]
   - https://<server>/...

Options:
  -F, --fields TEXT               Comma-separated list of fields to display.
                                  An empty value to trigger a list of
                                  available fields to be printed out
  -f, --format [auto|pyout|json|json_pp|json_lines|yaml]
                                  Choose the format/frontend for output. If
                                  'auto', 'pyout' will be used in case of
                                  multiple files, and 'yaml' for a single
                                  file.
  -r, --recursive                 Recurse into content of
                                  dandisets/directories. Only .nwb files will
                                  be considered.
  -J, --jobs INTEGER              Number of parallel download jobs.  [default:
                                  6]
  --metadata [api|all|assets]
  --schema VERSION                Convert metadata to new schema version
  --help                          Show this message and exit.
```


## Third-party Components

**dandi/tests/skip.py** -- from https://github.com/ReproNim/reproman, as of v0.2.1-40-gf4f026d
Copyright (c) 2016-2020  ReproMan Team

## Resources

* To learn how to interact with the DANDI archive and for examples on how to use the DANDI Client in various use cases,
see [the handbook](https://www.dandiarchive.org/handbook/).

* To get help:
  - ask a question: https://github.com/dandi/helpdesk/discussions
  - file a feature request or bug report: https://github.com/dandi/helpdesk/issues/new/choose
  - contact the DANDI team: help@dandiarchive.org

* To understand how to contribute to the dandi-cli repository, see the [DEVELOPMENT.md](./DEVELOPMENT.md) file.
