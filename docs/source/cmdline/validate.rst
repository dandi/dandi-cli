:program:`dandi validate`
=========================

::

    dandi [<global options>] validate [<path> ...]

Validate files for NWB and DANDI compliance.

Exits with non-zero exit code if any file is not compliant.


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
