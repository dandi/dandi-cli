.. module:: dandi.dandiapi

``dandi.dandiapi``
==================

This module provides functionality for interacting with a DANDI instance server
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
