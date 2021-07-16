:program:`dandi ls`
===================

::

    dandi [<global options>] ls [<options>] [<path|url> ...]

List .nwb files and dandisets metadata.

Patterns for known setups:

- ``DANDI:<dandiset id>``
- ``https://dandiarchive.org/...``
- ``https://identifiers.org/DANDI:<dandiset id>``
- ``https://<server>[/api]/[#/]dandiset/<dandiset id>[/<version>][/files[?location=<path>]]``
- ``https://*dandiarchive-org.netflify.app/...``
- ``https://<server>[/api]/dandisets/<dandiset id>[/versions[/<version>]]``
- ``https://<server>[/api]/dandisets/<dandiset id>/versions/<version>/assets/<asset id>[/download]``
- ``https://<server>[/api]/dandisets/<dandiset id>/versions/<version>/assets/?path=<path>``
- ``dandi://<instance name>/<dandiset id>[@<version>][/<path>]``
- ``https://<server>/...``


Options
-------

.. option:: -F, --fields <fields>

    Comma-separated list of fields to display.  An empty value to trigger a
    list of available fields to be printed out

.. option:: -f, --format [auto|pyout|json|json_pp|json_lines|yaml]

    Choose the format/frontend for output. If 'auto' (default), 'pyout' will be
    used in case of multiple files, and 'yaml' for a single file.

.. option:: -r, --recursive

    Recurse into content of dandisets/directories. Only .nwb files will be
    considered.

.. option:: -J, --jobs <int>

    Number of parallel download jobs.

.. option:: --metadata [api|all|assets]

.. option:: --schema <version>

    Convert metadata to new schema version
