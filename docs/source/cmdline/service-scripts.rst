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


``update-dandiset-from-doi``
----------------------------

::

    dandi [<global options>] service-scripts update-dandiset-from-doi --dandiset=<DANDISET ID> [<options>] <doi>

Update the metadata for the draft version of a Dandiset with information from a
given DOI record.

Options
^^^^^^^

.. option:: -d, --dandiset <DANDISET ID>

    Specify the ID of the Dandiset to operate on.  This option is required.

.. option:: -i, --dandi-instance <instance-name>

    Specify the DANDI instance where the Dandiset is located [default:
    ``dandi``]

.. option:: -e, --existing [ask|overwrite|skip]

    Specify the behavior when a value would be set on or added to the Dandiset
    metadata:

    - ``ask`` [default] — Ask the user with confirmation before making the
      change

    - ``overwrite`` — Make the change without asking for confirmation

    - ``skip`` — Do not change anything, but still print out details on what
      would have been changed

.. option:: -F, --fields [contributor,name,description,relatedResource,all]

    Comma-separated list of Dandiset metadata fields to update [default:
    ``all``]

.. option:: -y, --yes

    Show the final metadata diff and save any changes without asking for
    confirmation
