# DANDI Client

This repository is under heavy development.  Check-in later.

## Development/contributing

Assuming that you have `python3` (and virtualenv) installed, the fastest
way to establish yourself a development environment (or a sample deployment),
is via virtualenv:

    git clone https://github.com/dandi/dandi-cli \
        && cd dandi-cli \
        &&  virtualenv --system-site-packages --python=python3 venvs/dev3 \
        && source venvs/dev3/bin/activate \
        && pip install -e .

### Install and activate precommit

Install pre-commit dependency with `pip install pre-commit`

In the source directory
```
pre-commit install
```
## 3rd party components included

### dandi/support/generatorify.py

From https://github.com/eric-wieser/generatorify, as of 7bd759ecf88f836ece6cdbcf7ce1074260c0c5ef
Copyright (c) 2019 Eric Wieser, MIT/Expat licensed.
