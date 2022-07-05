:program:`dandi service-scripts`
================================

::

    dandi [<global options>] service-scripts [<command>]

:program:`dandi service-scripts` is a collection of subcommands for various
utility operations.

``cancel-zarr-upload``
----------------------

::

    dandi [<global options>] service-scripts cancel-zarr-upload [<options>] <path> ...

Cancel an in-progress Zarr upload operation on the server.

If a process uploading a Zarr is suddenly interrupted or killed, the server
might not be properly notified.  If a later attempt is made to upload the same
Zarr, the server will then report back that there is already an upload
operation in progress and prohibit the new upload.  Use this command in such a
case to tell the server to cancel the old upload operations for the Zarrs at
the given path(s).

Options
^^^^^^^

.. option:: -i, --dandi-instance <instance-name>

    DANDI instance on which to cancel uploads  [default: ``dandi``]
