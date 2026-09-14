.. module:: dandi.dandiapi

``dandi.dandiapi``
==================

This module provides functionality for interacting with a DANDI instance
via the REST API.  Interaction begins with the creation of a `DandiAPIClient`
instance, which can be used to retrieve `RemoteDandiset` objects (representing
Dandisets on the server) and `BaseRemoteAsset` objects (representing assets
without any data associating them with their Dandisets).  `RemoteDandiset`
objects can, in turn, be used to retrieve `RemoteAsset` objects (representing
assets associated with Dandisets).  Aside from `DandiAPIClient`, none of these
classes should be instantiated directly by the user.

All operations that merely fetch data from the server can be done without
authenticating, but any operation that writes, uploads, modifies, or deletes
data requires the user to authenticate the `DandiAPIClient` instance by
supplying an API key either when creating the instance or by calling the
`~DandiAPIClient.authenticate()` or `~DandiAPIClient.dandi_authenticate()`
method.

Example code for printing the metadata of all assets with "two-photon" in their
``metadata.measurementTechnique[].name`` for the latest published version of
every Dandiset:

.. literalinclude:: /examples/dandiapi-example.py
    :language: python

Example code for accessing asset files as regular Python file objects without
downloading their entire content locally.  Such file objects could then
be passed to functions of pynwb etc.

.. literalinclude:: /examples/dandiapi-as_readable.py
    :language: python

You can see more usages of DANDI API to assist with data streaming at
`PyNWB: Streaming NWB files <https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/streaming.html>`_.

Client
------

.. autoclass:: RESTFullAPIClient

.. autoclass:: DandiAPIClient
    :show-inheritance:

Dandisets
---------

.. autoclass:: RemoteDandiset()

Browsing directories
^^^^^^^^^^^^^^^^^^^^

Use ``RemoteDandiset.get_path()`` to list one level without retrieving every asset:

.. code-block:: python

    with DandiAPIClient() as client:
        root = client.get_dandiset("000026", "draft").get_path()
        for entry in root.iterdir():
            print(entry.name, entry.is_dir(), entry.aggregate_files, entry.size)

The result follows the ``BasePath`` interface: ``/``, ``parent``, ``iterdir()``,
``exists()``, ``is_file()``, ``is_dir()`` and ``size``. Both blob and Zarr assets
are files in this tree; Zarr chunks are not children. Call ``entry.get_asset()``
to retrieve the full asset record.

Remote listing costs one paginated request sequence per directory. Listed
children already contain recursive sizes and counts, so inspecting those
properties does not fetch each asset. Resolving an arbitrary unlisted path
requires listing its parent. A full asset record requires an additional request.
Listings are cached on the path objects; create a new root to see later changes.
Authorization and server errors propagate to the caller.

For a local Dandiset, ``Dandiset(directory).get_path()`` provides the same path
operations. It discovers all assets once using DANDI's existing discovery rules,
including generic files. Empty directories, dot-prefixed paths and directory
symlinks follow those rules; they are not additional assets. Metadata in
``dandiset.yaml`` is not part of the asset tree. Local sizes are calculated from
the files; remote sizes come from Archive aggregates.

For organized Dandisets, path-derived subject IDs can be obtained as follows:

.. code-block:: python

    import re
    from dandi.consts import ORGANIZED_FOLDER_REGEX

    subjects = sorted(p.name[4:] for p in root.iterdir()
                      if p.is_dir() and re.fullmatch(ORGANIZED_FOLDER_REGEX, p.name))

This recipe does not inspect NWB metadata or BIDS participants tables. Directory
names do not necessarily describe every dataset's scientific subjects.

.. autoclass:: RemoteDandisetPath()
    :show-inheritance:

.. autoclass:: Version()
    :inherited-members: BaseModel
    :exclude-members: Config, JSON_EXCLUDE

.. autoclass:: VersionInfo()
    :show-inheritance:

.. autoclass:: RemoteValidationError()
    :inherited-members: BaseModel

Assets
------

.. autoclass:: BaseRemoteAsset()
    :inherited-members: BaseModel
    :exclude-members: Config, JSON_EXCLUDE

.. autoclass:: BaseRemoteBlobAsset()
    :show-inheritance:

.. autoclass:: AssetType

.. autoclass:: RemoteAsset()
    :show-inheritance:
    :exclude-members: JSON_EXCLUDE

.. autoclass:: RemoteBlobAsset()
    :show-inheritance:

Zarr Assets
^^^^^^^^^^^

.. autoclass:: BaseRemoteZarrAsset()
    :show-inheritance:

.. autoclass:: RemoteZarrAsset()
    :show-inheritance:

.. autoclass:: RemoteZarrEntry()
    :show-inheritance:

.. Excluded from documentation: APIBase, RemoteDandisetData, ZarrEntryServerData
