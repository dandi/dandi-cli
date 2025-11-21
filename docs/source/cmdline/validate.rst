:program:`dandi validate`
=========================

::

    dandi [<global options>] validate [<path> ...]

Validate files for data standards compliance.

Exits with non-zero exit code if any file is not compliant.

Options
-------

.. option:: -g, --grouping [none|path]

    Set how to group reported errors & warnings: by path or not at all
    (default)

.. option:: --ignore REGEX

    Ignore any validation errors & warnings whose ID matches the given regular
    expression

.. option:: --match REGEX,REGEX,...

    Comma-separated regex patterns used to filter issues in validation results by their
    ID. Only issues with an ID matching at least one of the given patterns are included
    in the eventual result. Note: The separator used to separate the patterns is a
    comma (`,`), so no pattern should contain a comma.

.. option:: --include-path PATH

    Filter issues in the validation results to only those associated with the
    given path(s). A validation issue is associated with a path if its associated
    path(s) are the same as or falls under the provided path. This option can be
    specified multiple times to include multiple paths.

.. option:: --min-severity [HINT|WARNING|ERROR]

    Only display issues with severities above this level (HINT by default)


Development Options
-------------------

The following options are intended only for development & testing purposes.
They are only available if the :envvar:`DANDI_DEVEL` environment variable is
set to a nonempty value.

.. option:: --allow-any-path

    Validate all file types, not just NWBs and Zarrs

.. option:: --devel-debug

    Do not use pyout callbacks, do not swallow exceptions, do not parallelize.

.. option:: --schema <version>

    Validate against new schema version
