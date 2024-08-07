:program:`lincbrain download`
=============================

::

    lincbrain [<global options>] download [<options>] <url> ...

Download one or more datasets, assets, or folders of assets from LINC.

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

.. option:: -i, --dandi-instance <instance>

    DANDI instance (either a base URL or a known instance name) to download
    from [default: ``dandi``]

.. option:: -J, --jobs N[:M]

    Number of parallel download jobs and, optionally, number of upload subjobs
    per Zarr asset job  [default: 6:4]

.. option:: -o, --output-dir <dir>

    Directory to download to (must exist).  Files will be downloaded with paths
    relative to that directory.  [default: current working directory]

.. option:: --path-type [exact|glob]

    Whether to interpret asset paths in URLs as exact matches or glob patterns

.. option:: --preserve-tree

    When downloading only part of a Dandiset, also download
    :file:`dandiset.yaml` (unless downloading an asset URL that does not
    include a Dandiset ID) and do not strip leading directories from asset
    paths.  Implies ``--download all``.

.. option:: --sync

    Delete local assets that do not exist on the server after downloading
