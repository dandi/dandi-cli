:program:`dandi instances`
==========================

::

    dandi [<global options>] instances

List known Dandi Archive instances that can be passed to the
``-i``/``--dandi-instance`` option of other subcommands for the CLI to
interact with.  Output is in YAML.

Example output:

.. code:: yaml

    dandi:
      api: https://api.dandiarchive.org/api
      gui: https://gui.dandiarchive.org
      redirector: https://dandiarchive.org
    dandi-api-local-docker-tests:
      api: http://localhost:8000/api
      gui: http://localhost:8085
      redirector: null
    dandi-devel:
      api: null
      gui: https://gui-beta-dandiarchive-org.netlify.app
      redirector: null
    dandi-staging:
      api: https://api-staging.dandiarchive.org/api
      gui: https://gui-staging.dandiarchive.org
      redirector: null
