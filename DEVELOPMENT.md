# DANDI Client Development

## Development environment

Assuming that you have `python3` (and virtualenv) installed, the fastest
way to establish yourself a development environment (or a sample deployment),
is via virtualenv:

    git clone https://github.com/dandi/dandi-cli \
        && cd dandi-cli \
        &&  virtualenv --system-site-packages --python=python3 venvs/dev3 \
        && source venvs/dev3/bin/activate \
        && pip install -e .[test]

### Install and activate precommit

Install pre-commit dependency with `pip install pre-commit`

In the source directory
```
pre-commit install
```

### dandiarchive instance

[dandiarchive](https://github.com/dandi/dandiarchive) repository provides
docker-compose recipe to establish local instance of the minimally provisioned
dandiarchive (both with our web frontend, and girder backend).
See [README.md:Docker](https://github.com/dandi/dandiarchive#docker) for the
instructions.  In a new instance you would need to generate a new API key to be
used by `dandi` client for upload etc.

Relevant `dandi` client commands are aware of such an instance (such as `upload`)
as `local91` (as opposed from `local` for a plain girder instance).  See note
below on `DANDI_DEVEL` environment variable which would be needed to expose
development command line options.

## Environment variables

- `DANDI_DEVEL` -- enables otherwise hidden command line options,
  such as explicit specification of the girder instance, collection, etc.
  All those options would otherwise be hidden from the user visible (`--help`)
  interface, unless this env variable is set to non-empty value

- `DANDI_API_KEY` -- avoids using keyrings, thus making it possible to
  "temporarily" use another account etc.
