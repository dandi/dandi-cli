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
    ends with a trailing slash, the URL refers to an asset folder by path, and
    `parse_dandi_url()` will convert the URL to an `AssetFolderURL`.

  - If the ``glob``/``--path-type glob`` option is not in effect and ``path``
    does not end with a trailing slash, the URL refers to a single asset by
    path, and `parse_dandi_url()` will convert the URL to an `AssetItemURL`.

- Any other HTTPS URL that redirects to one of the above
