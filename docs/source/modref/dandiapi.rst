.. module:: dandi.dandiapi

``dandi.dandiapi``
==================

This module provides functionality for interacting with a Dandi Archive server
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

Assets
------

.. autoclass:: BaseRemoteAsset()
    :inherited-members: BaseModel
    :exclude-members: Config, JSON_EXCLUDE

.. autoclass:: AssetType

.. autoclass:: RemoteAsset()
    :show-inheritance:
    :exclude-members: JSON_EXCLUDE

.. autoclass:: RemoteBlobAsset()
    :show-inheritance:

Zarr Assets
^^^^^^^^^^^

.. autoclass:: RemoteZarrAsset()
    :show-inheritance:

.. autoclass:: RemoteZarrEntry()
    :show-inheritance:

.. autoclass:: ZarrListing()

.. autoclass:: ZarrEntryStat()

.. Excluded from documentation: APIBase, RemoteDandisetData
