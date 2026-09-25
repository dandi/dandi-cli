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

    Cannot be combined with ``--zarr`` or with a URL that points inside a Zarr
    asset: a partial download of a Zarr leaves out entries that are on the
    server, which ``--sync`` would then delete locally.

.. option:: --zarr <filter>

    Download only the entries within Zarr assets that match ``filter``, given
    as :samp:`{type}:{pattern}` where ``type`` is one of:

    ``glob``
        Match the entry path against a glob pattern.  ``*`` matches within a
        single path component and ``**`` matches across components, e.g.
        ``glob:**/.zarray``.

    ``path``
        Match the entry at ``pattern`` and everything under it, e.g.
        ``path:0/0``.

    ``regex``
        Search the entry path for a Python regular expression.  The match is
        unanchored, so anchor it yourself to match from the start, e.g.
        ``regex:^0/[0-9]+/``.

    In place of :samp:`{type}:{pattern}`, the predefined filter ``metadata``
    may be given; it selects the Zarr metadata files, i.e. any entry named
    ``zarr.json`` or whose name begins with ``.z`` (``.zarray``, ``.zgroup``,
    ``.zattrs``, ``.zmetadata``), at any depth.

    The option may be given more than once, in which case an entry is
    downloaded if it matches **any** of the filters.

    A URL that points inside a Zarr asset (see :ref:`resource_ids`) selects
    entries in the same way, as though ``path:`` had been given for the
    portion of the URL below the Zarr asset::

        dandi download dandi://dandi/000108/sub-1/file.ome.zarr/0/0

    Unlike ``--zarr``, such a URL names entries that the Dandiset is expected
    to have: if no entry matches, the download fails rather than quietly
    downloading nothing.

    .. warning::

        A URL subpath and ``--zarr`` are **unioned**, not intersected, so
        passing both *widens* the download rather than narrowing it.  In::

            dandi download --zarr metadata \
                dandi://dandi/000108/sub-1/file.ome.zarr/0/0

        the entries under ``0/0`` are downloaded *and* so is every metadata
        file anywhere in the Zarr.  To restrict metadata to a subtree, give
        the subtree in the filter itself (``--zarr 'glob:0/0/**/.z*'``) rather
        than in the URL.

    Because only part of a Zarr is fetched, extra local files are not deleted
    and the Zarr checksum of the result is not verified; the checksum of each
    individual downloaded entry still is.
