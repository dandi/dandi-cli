.. currentmodule:: dandi.dandiarchive

.. _resource_ids:

Resource Identifiers
====================

``dandi`` commands and Python functions accept URLs and URL-like identifiers in
the following formats for identifying Dandisets, assets, and asset collections.

Text in [brackets] is optional.  A ``server`` field is a base API, GUI, or
redirector URL for a registered DANDI Archive instance.  If an optional
``version`` field is omitted from a URL, the given Dandiset's most recent
published version will be used if it has one, and its draft version will be
used otherwise.

- :samp:`https://identifiers.org/DANDI:{dandiset-id}[/{version}]`
  (case insensitive; ``version`` cannot be "draft") when it redirects
  to one of the other URL formats

- :samp:`DANDI:{dandiset-id}[/{version}]` (case insensitive)
  — Refers to a Dandiset on the main archive instance named "dandi".
  `parse_dandi_url()` converts this format to a `DandisetURL`.

- Any ``https://dandiarchive.org/`` or
  ``https://*dandiarchive-org.netflify.app/`` URL which redirects to
  one of the other URL formats

- :samp:`https://{server}[/api]/[#/]dandiset/{dandiset-id}[/{version}][/files]`
  — Refers to a Dandiset.  `parse_dandi_url()` converts this format to a
  `DandisetURL`.

- :samp:`https://{server}[/api]/[#/]dandiset/{dandiset-id}[/{version}]/files?location={path}/`
  (trailing slash) — Refers to an asset folder by path.  `parse_dandi_url()`
  converts this format to an `AssetFolderURL`.

- :samp:`https://{server}[/api]/[#/]dandiset/{dandiset-id}[/{version}]/files?location={path}`
  (no trailing slash) — Refers to a single asset by path.  `parse_dandi_url()`
  converts this format to an `AssetItemURL`.

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

- :samp:`dandi://{instance-name}/{dandiset-id}[@{version}]` (where
  ``instance-name`` is the name of a registered Dandi Archive instance) —
  Refers to a Dandiset.  `parse_dandi_url()` converts this format to a
  `DandisetURL`.

- :samp:`dandi://{instance-name}/{dandiset-id}[@{version}]/{path}/` (where
  ``instance-name`` is the name of a registered Dandi Archive instance)
  (trailing slash) — Refers to an asset folder by path.  `parse_dandi_url()`
  converts this format to an `AssetFolderURL`.

- :samp:`dandi://{instance-name}/{dandiset-id}[@{version}]/{path}` (where
  ``instance-name`` is the name of a registered Dandi Archive instance) (no
  trailing slash) — Refers to a single asset by path.  `parse_dandi_url()`
  converts this format to an `AssetItemURL`.

- Any other HTTPS URL that redirects to one of the above
