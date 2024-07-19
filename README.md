# LINC Brain Client

[![Tests](https://github.com/lincbrain/linc-cli/workflows/Tests/badge.svg)](https://github.com/lincbrain/linc-cli/actions?query=workflow%3ATests)
[![GitHub release](https://img.shields.io/github/release/lincbrain/linc-cli.svg)](https://GitHub.com/lincbrain/linc-cli/releases/)
[![PyPI version fury.io](https://badge.fury.io/py/lincbrain-cli.svg)](https://pypi.python.org/pypi/lincbrain-cli/)

The [LINC Brain Python client](https://pypi.org/project/lincbrain-cli/) allows you to:

* Download `Datasets` and individual subject folders or files
* Validate data to locally conform to standards
* Organize your data locally before upload
* Upload `Datasets`
* Interact with the LINC Data Platform's web API from Python
* Delete data in the LINC Data Platform
* Perform other auxiliary operations with data or the LINC Data Platform

**Note**: This project is under heavy development. See [the issues log](https://github.com/linc/linc-cli/issues) or
[Work-in-Progress (WiP)](https://github.com/linc/linc-cli/pulls).

## Installation

LINC Brain client releases are available from [PyPI](https://pypi.org/project/lincbrain-cli).
Install them in your Python (native, virtualenv, or conda) environment via

    pip install lincbrain-cli

## CLI Tool

This package provides a command line utility with a basic interface
to help you prepare and upload your data to, or obtain data from, the [LINC Data Platform](http://lincbrain.org).


```bash
$> lincbrain
Usage: lincbrain [OPTIONS] COMMAND [ARGS]...

  A client to support interactions with the LINC Data Platform
  (https://lincbrain.org).

  To see help for a specific command, run

      lincbrain COMMAND --help

  e.g. lincbrain upload --help

Options:
  --version
  -l, --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  Log level (case insensitive).  May be
                                  specified as an integer.  [default: INFO]
  --pdb                           Fall into pdb if errors out
  --help                          Show this message and exit.

Commands:
  delete            Delete datasets and assets from the server.
  digest            Calculate file digests
  download          Download a file or entire folder from the LINC Data Platform.
  instances         List known LINC Data Platform instances that the CLI can...
  ls                List .nwb files and datasets metadata.
  move              Move or rename assets in a local Dataset and/or on...
  organize          (Re)organize files according to the metadata.
  shell-completion  Emit shell script for enabling command completion.
  upload            Upload dataset files to the LINC Data Platform.
  validate          Validate files for NWB and LINC Brain compliance.
  validate-bids     Validate BIDS paths.
```
Run `lincbrain --help` or `lincbrain <subcommand> --help` (e.g. `lincbrain upload --help`) to see manual pages.

## Resources

The LINC Brain ecosystem is forked from the [DANDI Archive project](https://github.com/dandi). Resources there should point
you towards common questions encountered within the LINC Brain project.

* To learn how to interact with the LINC Data Platform (e.g. a forked DANDI archive) and for examples on how to use the DANDI Client in various use cases,
see [the DANDI handbook](https://www.dandiarchive.org/handbook/)
  (specifically the sections on using the CLI to
[download](https://www.dandiarchive.org/handbook/12_download/) and
[upload](https://www.dandiarchive.org/handbook/13_upload/) `Dandisets`).

* To get help:
  - file a feature request or bug report: https://github.com/lincbrain/linc-archive/issues/new
  - contact the LINC team: kabi@mit.edu or akanzer@mit.edu

* To understand how to contribute to the linc-cli repository, see the [DEVELOPMENT.md](./DEVELOPMENT.md) file.
