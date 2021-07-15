:program:`dandi upload`
=======================

::

    dandi [<global options>] upload [<options>] [<path> ...]

Upload dandiset (files) to DANDI archive.

Target dandiset to upload to must already be registered in the archive and
locally :file:`dandiset.yaml` should exist in :option:`--dandiset-path`.

Local dandiset should pass validation.  For that it should be first organized
using ``dandi organize`` command.

By default all files in the dandiset (not following directories starting with a
period) will be considered for the upload.  You can point to specific files you
would like to validate and have uploaded.

Options
-------

.. option:: -e, --existing [error|skip|force|overwrite|refresh]

    What to do if a file found existing on the server. 'skip' would skip the
    file, 'force' - force reupload, 'overwrite' - force upload if either size
    or modification time differs; 'refresh' (default) - upload only if local
    modification time is ahead of the remote.

.. option:: -J, --jobs N[:M]

    Number of files to upload in parallel and, optionally, number of upload
    threads per file

.. option:: --sync

    Delete assets on the server that do not exist locally

.. option:: --validation [require|skip|ignore]

    Data must pass validation before the upload.  Use of this option is highly
    discouraged.
