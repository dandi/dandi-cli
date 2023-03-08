:program:`dandi service-scripts`
================================

::

    dandi [<global options>] service-scripts [<command>]

:program:`dandi service-scripts` is a collection of subcommands for various
utility operations.

``reextract-metadata``
----------------------

::

    dandi [<global options>] service-scripts reextract-metadata [<options>] <url>

Recompute & update the metadata for NWB assets on a remote server.

``<url>`` must point to a draft Dandiset or one or more assets inside a draft
Dandiset.  See :ref:`resource_ids` for allowed URL formats.

Running this command requires the fsspec_ library to be installed with the
``http`` extra (e.g., ``pip install "fsspec[http]"``).

.. _fsspec: http://github.com/fsspec/filesystem_spec

Options
^^^^^^^

.. option:: --diff

    Show diffs of old & new metadata for each re-extracted asset

.. option:: --when [newer-schema-version|always]

    Specify when to re-extract an asset's metadata:

    - ``newer-schema-version`` (default) — when the ``schemaVersion`` in the
      asset's current metadata is missing or older than the schema version
      currently in use by DANDI

    - ``always`` — always
