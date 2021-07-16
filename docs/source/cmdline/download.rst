:program:`dandi download`
=========================

::

    dandi [<global options>] download [<options>] [<url> ...]

Options
-------

.. option:: -o, --output-dir <dir>

    Directory where to download to (directory must exist).  Files will be
    downloaded with paths relative to that directory.

.. option:: -e, --existing [error|skip|overwrite|overwrite-different|refresh]

    What to do if a file found existing locally. 'refresh': verify
    that according to the size and mtime, it is the same file, if not -
    download and overwrite.

.. option:: -f, --format [pyout|debug]

    Choose the format/frontend for output.

.. option:: -J, --jobs <int>

    Number of parallel download jobs.

.. option:: --download [dandiset.yaml,assets,all]

    Comma-separated list of elements to download

.. option:: --sync

    Delete local assets that do not exist on the server
