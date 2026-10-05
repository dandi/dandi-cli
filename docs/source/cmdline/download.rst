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

.. option:: --zarr FILTER

    Only download the entries of Zarr assets that match the given filter.  The
    filter is either the predefined name ``metadata``, which selects the Zarr
    metadata files — any entry named ``zarr.json`` or whose name begins with
    ``.z`` (``.zarray``, ``.zattrs``, ``.zgroup``, ``.zmetadata``), at any
    depth — or ``TYPE:PATTERN``, where ``TYPE`` is one of:

    - ``glob`` — ``PATTERN`` is a glob matched against the entry's path within
      the Zarr, with ``*`` matching within a single path component and ``**``
      matching across directories (e.g., ``glob:0/**/*``, ``glob:**/.zarray``)

    - ``path`` — ``PATTERN`` is a path within the Zarr; the entry at that path
      and all entries under it are downloaded (e.g., ``path:0/0``)

    - ``regex`` — ``PATTERN`` is a regular expression searched for in the
      entry's path within the Zarr.  The search is unanchored, so anchor it
      yourself to match from the start (e.g., ``regex:^0/[0-9]+/``)

    Can be specified multiple times, in which case an entry is downloaded if it
    matches any of the filters.

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
        the subtree in the filters themselves rather than in the URL::

            dandi download --zarr 'glob:0/0/**/.z*' \
                --zarr 'glob:0/0/**/zarr.json' \
                dandi://dandi/000108/sub-1/file.ome.zarr

        Both filters are needed, as ``metadata`` covers Zarr v2's dot-files
        and Zarr v3's :file:`zarr.json` alike.

    Because only part of a Zarr is fetched, extra local files are not deleted
    and the Zarr checksum of the result is not verified; the checksum of each
    individual downloaded entry still is.
