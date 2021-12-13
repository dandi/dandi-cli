:program:`dandi download`
=========================

::

    dandi [<global options>] download [<options>] <url>

Download a Dandiset, asset, or folder of assets from DANDI.

See :ref:`resource_ids` for allowed URL formats.

Options
-------

.. option:: --download [dandiset.yaml,assets,all]

    Comma-separated list of elements to download  [default: ``all``]

.. option:: -e, --existing [error|skip|overwrite|overwrite-different|refresh]

    How to handle paths that already exist locally  [default: ``error``]

    For ``refresh``, if the local file's size and mtime are the same as on the
    server, the asset is skipped; otherwise, it is redownloaded.

.. option:: -f, --format [pyout|debug]

    Choose the format/frontend for output  [default: ``pyout``]

.. option:: -i, --instance <instance-name>

    DANDI instance to download from  [default: ``dandi``]

.. option:: -J, --jobs <int>

    Number of parallel download jobs  [default: 6]

.. option:: -o, --output-dir <dir>

    Directory to download to (must exist).  Files will be downloaded with paths
    relative to that directory.  [default: current working directory]

.. option:: --sync

    Delete local assets that do not exist on the server after downloading
