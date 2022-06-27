:program:`dandi upload`
=======================

::

    dandi [<global options>] upload [<options>] [<path> ...]

Upload Dandiset files to DANDI Archive.

The target Dandiset to upload to must already be registered in the archive, and
a :file:`dandiset.yaml` file must exist in the common ancestor of the given
paths (or the current directory, if no paths are specified) or a parent
directory thereof.

Local Dandisets should pass validation.  For that, the assets should first be
organized using the :ref:`dandi_organize` command.

By default, all :file:`*.nwb`, :file:`*.zarr`, and :file:`*.ngff` assets in the
Dandiset (ignoring directories starting with a period) will be considered for
the upload.  You can point to specific files you would like to validate and
have uploaded.

Options
-------

.. option:: -e, --existing [error|skip|force|overwrite|refresh]

    How to handle files that already exist on the server:

    - ``error`` — raise an error
    - ``skip`` — skip the file
    - ``force`` — force reupload
    - ``overwrite`` — force upload if either size or modification time differs
    - ``refresh`` [default] — upload only if local modification time is ahead
      of the remote

.. option:: -i, --dandi-instance <instance-name>

    DANDI instance to upload to  [default: ``dandi``]

.. option:: -J, --jobs N[:M]

    Number of assets to upload in parallel and, optionally, number of upload
    threads per asset  [default: ``5:5``]

.. option:: --sync

    Delete assets on the server that do not exist locally after uploading

.. option:: --validation [require|skip|ignore]

    How to handle invalid assets:

    - ``require`` [default] — Do not upload any invalid assets
    - ``skip`` — Do not check assets for validity
    - ``ignore`` — Emit an error message for invalid assets but upload them
      anyway

    Data should pass validation before uploading.  Use of this option is highly
    discouraged.


Development Options
-------------------

The following options are intended only for development & testing purposes.
They are only available if the :envvar:`DANDI_DEVEL` environment variable is
set to a nonempty value.

.. option:: --allow-any-path

    Upload all file types, not just NWBs and Zarrs

.. option:: --devel-debug

    Do not use pyout callbacks, do not swallow exceptions, do not parallelize.

.. option:: --upload-dandiset-metadata

    Update Dandiset metadata based on the local :file:`dandiset.yaml` file
