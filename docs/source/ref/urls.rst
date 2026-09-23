.. currentmodule:: dandi.dandiarchive

.. _resource_ids:

Resource Identifiers
====================

``dandi`` commands and Python functions accept URLs and URL-like identifiers in
the following formats for identifying Dandisets, assets, and asset collections.

Text in [brackets] is optional.  A ``server`` field is a base API or GUI URL
for a DANDI Archive instance.  If an optional ``version`` field is omitted from
a URL, the given Dandiset's most recent published version will be used if it
has one, and its draft version will be used otherwise.

- :samp:`https://identifiers.org/DANDI:{dandiset-id}[/{version}]`
  (case insensitive; ``version`` cannot be "draft") when it redirects
  to one of the other URL formats

- :samp:`{instance-name}:{dandiset-id}[/{version}]` (case insensitive,
  where ``instance-name`` is a known DANDI instance such as ``DANDI``,
  ``DANDI-SANDBOX``, ``LINC``, ``EMBER``, etc.)
  — Refers to a Dandiset on the specified DANDI Archive instance.
  `parse_dandi_url()` converts this format to a `DandisetURL`.

- Any ``https://gui.dandiarchive.org/`` or
  ``https://*dandiarchive-org.netlify.app/`` URL which redirects to
  one of the other URL formats

- :samp:`https://{server}[/api]/[#/]dandiset/{dandiset-id}[/{version}][/files]`
  — Refers to a Dandiset.  `parse_dandi_url()` converts this format to a
  `DandisetURL`.

- :samp:`https://{server}[/api]/[#/]dandiset/{dandiset-id}[/{version}]/files?location={path}`

  - If the ``glob``/``--path-type glob`` option is in effect, the URL refers to
    a collection of assets whose paths match the glob pattern ``path``, and
    `parse_dandi_url()` will convert the URL to an `AssetGlobURL`.

  - If the ``glob``/``--path-type glob`` option is not in effect and ``path``
    descends into a Zarr asset, the URL refers to the entries at or under that
    location within the Zarr, and `parse_dandi_url()` will convert the URL to
    an `AssetZarrEntryURL`.  See :ref:`zarr_entry_urls` below.

  - If the ``glob``/``--path-type glob`` option is not in effect, the URL
    refers to an asset folder by path, and `parse_dandi_url()` will convert the
    URL to an `AssetFolderURL`.

- :samp:`https://{server}[/api]/dandisets/{dandiset-id}[/versions[/{version}]]`
  — Refers to a Dandiset.  `parse_dandi_url()` converts this format to a
  `DandisetURL`.

- :samp:`https://{server}[/api]/assets/{asset-id}[/download]` — Refers to a
  single asset by identifier.  `parse_dandi_url()` converts this format to a
  `BaseAssetIDURL`.

- :samp:`https://{server}[/api]/dandisets/{dandiset-id}/versions/{version}/assets/{asset-id}[/download]`
  — Refers to a single asset by identifier.  `parse_dandi_url()` converts this
  format to an `AssetIDURL`.

- :samp:`https://{server}[/api]/dandisets/{dandiset-id}/versions/{version}/assets/?path={path}`
  — Refers to all assets in the given Dandiset whose paths begin with the
  prefix ``path``.  `parse_dandi_url()` converts this format to an
  `AssetPathPrefixURL`.

- :samp:`https://{server}[/api]/dandisets/{dandiset-id}/versions/{version}/assets/?glob={path}`
  — Refers to all assets in the given Dandiset whose paths match the glob
  pattern ``path``.  `parse_dandi_url()` converts this format to an
  `AssetGlobURL`.

- :samp:`dandi://{instance-name}/{dandiset-id}[@{version}]` (where
  ``instance-name`` is the name of a registered DANDI instance) —
  Refers to a Dandiset.  `parse_dandi_url()` converts this format to a
  `DandisetURL`.

- :samp:`dandi://{instance-name}/{dandiset-id}[@{version}]/{path}` (where
  ``instance-name`` is the name of a registered DANDI instance)

  - If the ``glob``/``--path-type glob`` option is in effect, the URL refers to
    a collection of assets whose paths match the glob pattern ``path``, and
    `parse_dandi_url()` will convert the URL to an `AssetGlobURL`.

  - If the ``glob``/``--path-type glob`` option is not in effect and ``path``
    descends into a Zarr asset, the URL refers to the entries at or under that
    location within the Zarr, and `parse_dandi_url()` will convert the URL to
    an `AssetZarrEntryURL`.  See :ref:`zarr_entry_urls` below.

  - If the ``glob``/``--path-type glob`` option is not in effect and ``path``
    ends with a trailing slash, the URL refers to an asset folder by path, and
    `parse_dandi_url()` will convert the URL to an `AssetFolderURL`.

  - If the ``glob``/``--path-type glob`` option is not in effect and ``path``
    does not end with a trailing slash, the URL refers to a single asset by
    path, and `parse_dandi_url()` will convert the URL to an `AssetItemURL`.

- Any other HTTPS URL that redirects to one of the above


.. _zarr_entry_urls:

Paths Within Zarr Assets
------------------------

A Zarr asset is a directory, and the paths inside it are entries of that asset
rather than assets of their own.  A URL whose path continues past a Zarr asset
therefore refers to entries within it.  The boundary is recognised by the
extensions in ``dandi.consts.ZARR_EXTENSIONS`` (:file:`.zarr` and
:file:`.ngff`), so in::

    dandi://dandi/000108/sub-1/file.ome.zarr/0/0

the asset is :file:`sub-1/file.ome.zarr` and ``0/0`` names the entries at or
under :file:`0/0` within it.  `parse_dandi_url()` converts this to an
`AssetZarrEntryURL`.

:program:`dandi download` recreates the Zarr's leading directories locally and
fetches only the matching entries; see the ``--zarr`` option of
:doc:`dandi download </cmdline/download>`.  :program:`dandi ls`
lists the matching entries.  Because such a URL names entries the Dandiset is
expected to have, a download whose path matches no entry fails rather than
quietly downloading nothing.

A trailing slash is not meaningful at or below a Zarr boundary, since entries
within a Zarr are not assets: :samp:`{...}/file.ome.zarr/0/0/` is equivalent to
:samp:`{...}/file.ome.zarr/0/0`, and :samp:`{...}/file.ome.zarr/` refers to the
Zarr asset as a whole, just as :samp:`{...}/file.ome.zarr` does.
