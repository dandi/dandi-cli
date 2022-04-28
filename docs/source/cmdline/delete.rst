:program:`dandi delete`
=======================

::

    dandi [<global options>] delete [<options>] [<paths> ...]

Delete Dandisets and assets from the server.

Each argument must be either a file path pointing to an asset file or directory
in a local Dandiset (in which case the corresponding assets are deleted on the
remote server) or a :ref:`resource identifier <resource_ids>` pointing to a
remote asset, directory, or entire Dandiset.

Options
-------

.. option:: -i, --instance <instance-name>

    DANDI instance to delete assets & Dandisets from  [default: ``dandi``]

.. option:: --skip-missing

    By default, if an argument points to a remote resource that does not exist,
    an error is raised.  If :option:`--skip-missing` is supplied, missing
    resources are instead simply silently ignored.


Development Options
-------------------

The following options are intended only for development & testing purposes.
They are only available if the :envvar:`DANDI_DEVEL` environment variable is
set to a nonempty value.

.. option:: --devel-debug

    Do not use pyout callbacks, do not swallow exceptions, do not parallelize.
