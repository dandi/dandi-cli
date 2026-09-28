:program:`dandi download`
=========================

::

    dandi [<global options>] download [<options>] <url> ...

Download one or more Dandisets, assets, or folders of assets from DANDI.

See :ref:`resource_ids` for allowed URL formats.

Options
-------

.. option:: --download [dandiset.yaml,assets,all]

    Comma-separated list of elements to download  [default: ``all``]

.. option:: -e, --existing [error|skip|overwrite|overwrite-different|refresh]

    How to handle paths that already exist locally  [default: ``error``]

    For ``error``, if the local file exists, display an error and skip downloading that asset.

    For ``skip``, if the local file exists, skip downloading that asset.

    For ``overwrite``, if the local file exists, overwrite that asset.

    For ``overwrite-different``, if the local file's hash is the same as on the
    server, the asset is skipped; otherwise, it is redownloaded.

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

.. option:: --zarr FILTER

    Only download the entries of Zarr assets that match the given filter.  The
    filter is either the predefined name ``metadata``, which selects the Zarr
    metadata files (``.zarray``, ``.zattrs``, ``.zgroup``, ``.zmetadata``, and
    ``zarr.json``), or ``TYPE:PATTERN``, where ``TYPE`` is one of:

    - ``glob`` — ``PATTERN`` is a glob matched against the entry's path within
      the Zarr, with ``**`` matching across directories (e.g.,
      ``glob:0/**/*``)

    - ``path`` — ``PATTERN`` is a path within the Zarr; the entry at that path
      and all entries under it are downloaded

    - ``regex`` — ``PATTERN`` is a regular expression searched for in the
      entry's path within the Zarr

    Can be specified multiple times, in which case an entry is downloaded if it
    matches any of the filters.
