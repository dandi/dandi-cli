# DANDI Client

[![Tests](https://github.com/dandi/dandi-cli/workflows/Tests/badge.svg)](https://github.com/dandi/dandi-cli/actions?query=workflow%3ATests)
[![codecov.io](https://codecov.io/github/dandi/dandi-cli/coverage.svg?branch=master)](https://codecov.io/github/dandi/dandi-cli?branch=master)
[![Conda](https://anaconda.org/conda-forge/dandi/badges/version.svg)](https://anaconda.org/conda-forge/dandi)
[![Gentoo (::science)](https://repology.org/badge/version-for-repo/gentoo_ovl_science/dandi-cli.svg?header=Gentoo%20%28%3A%3Ascience%29)](https://repology.org/project/dandi-cli/versions)
[![GitHub release](https://img.shields.io/github/release/dandi/dandi-cli.svg)](https://GitHub.com/dandi/dandi-cli/releases/)
[![PyPI version fury.io](https://badge.fury.io/py/dandi.svg)](https://pypi.python.org/pypi/dandi/)
[![Documentation Status](https://readthedocs.org/projects/dandi/badge/?version=latest)](https://dandi.readthedocs.io/en/latest/?badge=latest)

The [DANDI Python client](https://pypi.org/project/dandi/) allows you to:

* Download `Dandisets` and individual subject folders or files
* Validate data to locally conform to standards
* Organize your data locally before upload
* Upload `Dandisets`
* Interact with the DANDI instance's web API from Python
* Delete data in the DANDI instance
* Perform other auxiliary operations with data on the DANDI instance

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
to help you prepare and upload your data to, or obtain data from, a DANDI instance such as the [DANDI Archive](http://dandiarchive.org).


```bash
$> dandi
Usage: dandi [OPTIONS] COMMAND [ARGS]...

  A client to support interactions with a DANDI instance, such as the DANDI Archive
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
  instances         List known DANDI instances that the CLI can interact
  ls                List .nwb files and dandisets metadata.
  move              Move or rename assets in a local Dandiset and/or on...
  organize          (Re)organize NWB files according to their metadata.
  shell-completion  Emit shell script for enabling command completion.
  upload            Upload Dandiset files to DANDI Archive.
  validate          Validate files for data standards compliance.
```
Run `dandi --help` or `dandi <subcommand> --help` (e.g. `dandi upload --help`) to see manual pages.

## Resources

* To learn how to interact with the DANDI Archive and for examples on how to use the DANDI Client in various use cases,
see the [DANDI Docs](https://docs.dandiarchive.org)
  (specifically the sections on using the CLI to
[download](https://docs.dandiarchive.org/12_download/) and
[upload](https://docs.dandiarchive.org/13_upload/) `Dandisets`).

* To get help:
  - ask a question: https://github.com/dandi/helpdesk/discussions
  - file a feature request or bug report: https://github.com/dandi/helpdesk/issues/new/choose
  - contact the DANDI team: help@dandiarchive.org

* To understand how to contribute to the dandi-cli repository, see the [DEVELOPMENT.md](./DEVELOPMENT.md) file.
