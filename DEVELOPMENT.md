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
as `local-docker` (as opposed from `local` for a plain girder instance).  See note
below on `DANDI_DEVEL` environment variable which would be needed to expose
development command line options.

## Operating against current "beta" instance of the dandiarchive.org

`dandi-cli` has all functionality for interaction with the beta instance deployed at
https://gui-beta-dandiarchive-org.netlify.app . Some operations (like `upload`) would
need that instance to be explicitly specified, and for that `DANDI_DEVEL=1` env variable
should be set.  Here is an example for the upload invocation

   DANDI_DEVEL=1 dandi upload -i dandi-api

in the simplest scenario.  Additional options might come handy, such as

- `--jobs 10:2` - upload 10 files in parallel with up to 2 threads per file
- `--allow-any-path --validation ignore` - if you need to upload non-nwb files

## Environment variables

- `DANDI_DEVEL` -- enables otherwise hidden command line options,
  such as explicit specification of the girder instance, collection, etc.
  All those options would otherwise be hidden from the user visible (`--help`)
  interface, unless this env variable is set to non-empty value

- `DANDI_API_KEY` -- avoids using keyrings, thus making it possible to
  "temporarily" use another account etc for the "API" version of the server.

- `DANDI_GIRDER_API_KEY` -- avoids using keyrings, thus making it possible to
  "temporarily" use another account etc for the Girder version of the server.

- `DANDI_LOG_LEVEL` -- set log level. By default `INFO`, should be an int (`10` - `DEBUG`).

- `DANDI_LOG_GIRDER` -- log REST requests.

- `DANDI_CACHE` -- clear persistent cache handling. Known values
  are `clear` - would clear the cache, `ignore` - would ignore it. Note that for
  metadata cache we use only released portion of `dandi.__version__` as a token.
  If handling of metadata has changed while developing, set this env var to
  `clear` to have cache `clear()`ed before use.

- `DANDI_INSTANCEHOST` -- defaults to `localhost`. Point to host/IP which hosts
  a local instance of dandiarchive. Typically,
  `DANDI_REUSE_LOCAL_DOCKER_TESTS_API_KEY`
  should also be set.

- `DANDI_REUSE_LOCAL_DOCKER_TESTS_API_KEY` -- make the
 `local_docker_compose*` fixtures use the given API key for
 `DANDI_INSTANCEHOST` instead of spinning up a new environment with a new key.

- `DANDI_TESTS_PERSIST_DOCKER_COMPOSE` -- When set, the tests will reuse the
  same Docker containers across test runs instead of creating & destroying a
  new set on each run.  Set this environment variable to `0` to cause the
  containers to be destroyed at the end of the next run.

## Sourcegraph

The [Sourcegraph](https://sourcegraph.com) browser extension can be used to
view code coverage information as follows:

1. Install the [Sourcegraph browser
   extension](https://docs.sourcegraph.com/integration/browser_extension) in
   your browser (Chrome or Firefox only)

2. [Sign up](https://sourcegraph.com/sign-up) for a Sourcegraph account if you
   don't already have one.  You must be signed in to Sourcegraph for the
   remaining steps.

3. Enable the [Codecov Sourcegraph
   extension](https://sourcegraph.com/extensions/sourcegraph/codecov)

4. On GitHub, when viewing a dandi-cli source file (either on a branch or in a
   pull request diff), there will be a "Coverage: X%" button at the top of the
   source listing.  Pressing this button will toggle highlighting of the source
   lines based on whether they are covered by tests or not.


## Releasing with GitHub Actions, auto, and pull requests

New releases of dandi-cli are created via a GitHub Actions workflow built
around [`auto`](https://github.com/intuit/auto).  Whenever a pull request is
merged that has the "`release`" label, `auto` updates the changelog based on
the pull requests since the last release, commits the results, tags the new
commit with the next version number, and creates a GitHub release for the tag.
This in turn triggers a job for building an sdist & wheel for the project and
uploading them to PyPI.

### Labelling pull requests

The section that `auto` adds to the changelog on a new release consists of the
titles of all pull requests merged into master since the previous release,
organized by label.  `auto` recognizes the following PR labels:

- `major` — for changes corresponding to an increase in the major version
  component
- `minor` — for changes corresponding to an increase in the minor version
  component
- `patch` — for changes corresponding to an increase in the patch/micro version
  component; this is the default label for unlabelled PRs
- `internal` — for changes only affecting the internal API
- `documentation` — for changes only affecting the documentation
- `tests` — for changes to tests
- `dependencies` — for updates to dependency versions
- `performance` — for performance improvements
