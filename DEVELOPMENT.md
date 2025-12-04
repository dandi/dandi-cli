# DANDI Client Development

## Development environment

Assuming that you have `python3` (and virtualenv) installed, the fastest
way to establish yourself a development environment (or a sample deployment),
is via virtualenv:

    git clone https://github.com/dandi/dandi-cli \
        && cd dandi-cli \
        &&  virtualenv --system-site-packages --python=python3 venvs/dev3 \
        && source venvs/dev3/bin/activate \
        && pip install -e ".[test]"

### Install and activate precommit

Install pre-commit dependency with `pip install pre-commit`

In the source directory
```
pre-commit install
```

### Running tests locally

You can run all tests locally by running `tox` (you can install `tox` running `pip install tox`):
```
tox -e py3
```

In order to check proper linting and typing of your changes
you can also run `tox` with `lint` and `typing`:
```
tox -e lint,typing
```

### dandi-archive instance

The [dandi-archive](https://github.com/dandi/dandi-archive) repository provides a
docker-compose recipe for establishing a local instance of a fresh dandi-archive.
See
[DEVELOPMENT.md:Docker](https://github.com/dandi/dandi-archive/blob/master/DEVELOPMENT.md#develop-with-docker-recommended-quickstart)
for the instructions.  In a new instance, you would need to generate a new API
key to be used by the `dandi` client for upload etc.

Relevant `dandi` client commands (such as `upload`) are aware of such an
instance as `dandi-api-local-docker-tests`.  See the note below on the
`DANDI_DEVEL` environment variable, which is needed in order to expose the
development command line options.

## Environment variables

- `DANDI_DEVEL` -- enables otherwise hidden command line options, such as
  explicit specification of the dandi-api instance.  All those options would
  otherwise be hidden from the user-visible (`--help`) interface, unless this
  env variable is set to a non-empty value

- `{CAPITALIZED_INSTANCE_NAME_WITH_UNDERSCORE}_API_KEY` --
  Provides the API key to access a known DANDI instance.
  Respective keys for multiple instances can be provided. The name of the environment
  variable providing the key for a specific known DANDI instance corresponds to the name
  of the instance. For example, the environment variable `DANDI_API_KEY` provides the key
  for the known instance named `dandi` and the environment variable
  `EMBER_DANDI_SANDBOX_API_KEY` provides the key for the known instance named `ember-dandi-sandbox`.
  I.e., the environment variable name is the capitalized version of the instance's name
  with "-" replaced by "_" suffixed by "_API_KEY". Providing API keys through environment
  variables avoids using keyrings, thus making it possible to "temporarily" use another
  account etc for the "API" version of the server.

- `DANDI_LOG_LEVEL` -- set log level. By default `INFO`, should be an int (`10` - `DEBUG`).

- `DANDI_CACHE` -- clear persistent cache handling. Known values
  are `clear` - would clear the cache, `ignore` - would ignore it. Note that for
  metadata cache we use only released portion of `dandi.__version__` as a token.
  If handling of metadata has changed while developing, set this env var to
  `clear` to have cache `clear()`ed before use.

- `DANDI_INSTANCEHOST` -- defaults to `localhost`. Point to host/IP which hosts
  a local instance of dandiarchive.

- `DANDI_TESTS_PERSIST_DOCKER_COMPOSE` -- When set, the tests will reuse the
  same Docker containers across test runs instead of creating & destroying a
  new set on each run.  Set this environment variable to `0` to cause the
  containers to be destroyed at the end of the next run.

- `DANDI_TESTS_PULL_DOCKER_COMPOSE` -- When set to an empty string or `0`, the
  tests will not pull the latest needed Docker images at the start of a run if
  older versions of the images are already present.

- `DANDI_TESTS_NO_VCR` — When set, the use of vcrpy to playback captured HTTP
  requests during testing will be disabled

- `DANDI_TESTS_INSTANCE_NAME` -- Sets the instance name for the dandi-archive instance used for
  testing. Defaults to `"DANDI"`. Useful for testing dandi-cli against a dandi-archive instance with
  a particular vendor information.

- `DANDI_TESTS_INSTANCE_IDENTIFIER` -- Sets the instance identifier (RRID) for the dandi-archive
  instance used for testing. Defaults to `"RRID:ABC_123456"`. Useful for testing dandi-cli against
  a dandi-archive instance with a particular vendor information.

- `DANDI_TESTS_DOI_PREFIX` -- Sets the DOI API prefix for the dandi-archive instance used for
  testing. Defaults to `"10.80507"`. Useful for testing dandi-cli against a dandi-archive instance
  with a particular vendor information.

- `DANDI_DEVEL_INSTRUMENT_REQUESTS_SUPERLEN` -- When set, the `upload()`
  function will patch `requests` to log the results of calls to
  `requests.utils.super_len()`

- `DANDI_DOWNLOAD_AGGRESSIVE_RETRY` -- When set, would make `download()` retry
  very aggressively - it would keep trying if at least some bytes are downloaded
  on each attempt.  Typically is not needed and could be a sign of network issues.

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
