:program:`lincbrain instances`
==============================

::

    lincbrain [<global options>] instances

List known LINC Archive instances that can be passed to the
``-i``/``--dandi-instance`` option of other subcommands for the CLI to
interact with.  Output is in YAML.

Example output:

.. code:: yaml

    dandi:
      api: https://api.lincbrain.org/api
      gui: https://lincbrain.org
    dandi-api-local-docker-tests:
      api: http://localhost:8000/api
      gui: http://localhost:8085
    dandi-staging:
      api: https://staging-api.lincbrain.org/api
      gui: https://staging.lincbrain.org
