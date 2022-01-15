:program:`dandi ls`
===================

::

    dandi [<global options>] ls [<options>] [<path|url> ...]

List :file:`*.nwb` files' and Dandisets' metadata.

The arguments may be either :ref:`resource identifiers <resource_ids>` or paths
to local files/directories.

Options
-------

.. option:: -f, --format [auto|pyout|json|json_pp|json_lines|yaml]

    Choose the format/frontend for output.  If ``auto`` (the default),
    ``pyout`` will be used in case of multiple files, ``yaml`` for a single
    file.

.. option:: -F, --fields <fields>

    Comma-separated list of fields to display.  Specifying ``-F ""`` causes a
    list of available fields to be printed out.

.. option:: -J, --jobs <int>

    Number of parallel download jobs  [default: 6]

.. option:: --metadata [api|all|assets]

    Control when to include asset metadata for remote assets:

    - ``api`` [default] — only include asset metadata if returned by the API
      response (i.e., if a URL identifying an asset by ID was supplied)

    - ``all`` — make an additional request to fetch asset metadata if not
      returned by initial API response

    - ``assets`` — same as ``all``

.. option:: -r, --recursive

    Recurse into Dandisets/directories.  Only :file:`*.nwb` files will be
    considered.

.. option:: --schema <version>

    Convert metadata to new schema version


Development Options
-------------------

The following options are intended only for development & testing purposes.
They are only available if the :envvar:`DANDI_DEVEL` environment variable is
set to a nonempty value.

.. option:: --use-fake-digest

    Use dummy value for digests of local files instead of computing
