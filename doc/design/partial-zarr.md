# Design: Partial Zarr Download and Upload

## Status

Draft

## Related Issues

- dandi-cli [#1462](https://github.com/dandi/dandi-cli/issues/1462) -- Support partial zarr upload
- dandi-cli [#1474](https://github.com/dandi/dandi-cli/issues/1474) -- Partial Zarr Directory Updates (DANDI/LINC)
- dandi-cli [#1596](https://github.com/dandi/dandi-cli/pull/1596) -- Draft PR: Support for partial download of zarrs (stale)
- dandi-archive [#1993](https://github.com/dandi/dandi-archive/issues/1993) -- WebDAV access for zarr browsing
- dandi-archive [#931](https://github.com/dandi/dandi-archive/issues/931) -- Re-design zarr checksum (closed/completed)
- dandi-archive [#1892](https://github.com/dandi/dandi-archive/pull/1892) -- Zarr versioning/publishing design via manifests (closed)
- dandi-archive [#2702](https://github.com/dandi/dandi-archive/pull/2702) -- Versioned Zarr design doc (draft)
- zarr_checksum [#50](https://github.com/dandi/zarr_checksum/issues/50) -- Generalize to folder_checksum
- zarr_checksum [#56](https://github.com/dandi/zarr_checksum/issues/56) -- Generalize checksum algorithm

## Problem

Zarr assets on DANDI can be very large (multi-GB).  Users frequently need to
modify only metadata files (`.zarray`, `.zgroup`, `.zattrs` for Zarr v2;
`zarr.json` for Zarr v3) or work with a specific subdirectory of a Zarr archive
without downloading or uploading the entire thing.

Currently, `dandi download` of a Zarr asset always fetches every file, and
`dandi upload` of a Zarr always performs a full bidirectional sync (uploading new
or changed files **and deleting** remote files absent locally).  This makes even
small metadata edits prohibitively expensive for large Zarrs.

## Primary Use Case

From @kabilar (#1462):

```bash
# 1. Download just the metadata files from a zarr
dandi download --zarr glob:'**/.z*' --zarr glob:'**/zarr.json' \
    dandi://dandi/001289/rawdata/.../PC.ome.zarr

# 2. Edit .zattrs locally
vim PC.ome.zarr/.zattrs

# 3. Upload changes without deleting remote data chunks
dandi upload --zarr-mode patch
```

---

## Part 1: Zarr Entry Filtering (`--zarr`)

### Design Rationale

Rather than a narrow `--zarr-metadata` flag, we provide a general-purpose
`--zarr` option that accepts filter expressions for selecting entries within
Zarr assets.  This aligns with the existing `--path-type glob` mechanism that
filters *assets* by path, and extends the concept into the Zarr-internal
namespace.

### Filter Expression Syntax

The `--zarr` option takes a `TYPE:PATTERN` expression.  Multiple `--zarr`
options combine with OR semantics (entry matches if **any** filter matches):

| Type | Syntax | Description |
|------|--------|-------------|
| `glob:PATTERN` | `--zarr glob:'**/.z*'` | Glob matched against the zarr-internal path using `fnmatch` semantics per path component. `*` matches within a component, `**` matches across directory levels. |
| `path:PREFIX` | `--zarr path:0/1/2` | Exact prefix match -- download entries whose zarr-internal path starts with this prefix (maps to the API `prefix` parameter). |
| `regex:PATTERN` | `--zarr regex:'\.z(array|group|attrs)$'` | Full regex matched against the zarr-internal path. |

#### Predefined Aliases

Predefined aliases provide convenient shorthands for common filter sets:

| Alias | Expands To |
|-------|-----------|
| `metadata` | `glob:**/.z*` + `glob:**/zarr.json` + `glob:**/.zmetadata` |

So `--zarr metadata` is equivalent to
`--zarr glob:'**/.z*' --zarr glob:'**/zarr.json'`.

### Why This Approach

1. **Consistency with existing patterns**: The codebase already uses
   `fnmatchcase` for `RemoteZarrEntry.match()` (`dandiapi.py:2098`) and
   `BasePath.match()` (`misctypes.py:210`), and the server API supports
   `?glob=` for asset-level filtering via `get_assets_by_glob()`.  Reusing
   glob syntax at the zarr-entry level is natural.

2. **The server already supports prefix filtering**: `RemoteZarrAsset.iterfiles(prefix=...)`
   (`dandiapi.py:1813`) calls `/zarr/{id}/files?prefix=...`.  The `path:` type
   maps directly to this, minimizing API calls.

3. **Composability**: Users can combine glob and path filters to express complex
   selections.  E.g., download all `.zattrs` under a specific resolution level:
   `--zarr path:0/1 --zarr glob:'**/.zattrs'` (OR semantics; could later add
   AND with `+` or `--zarr-and`).

4. **Prior art**: `rsync` uses `--include`/`--exclude` with glob patterns;
   `rclone` uses `--include`/`--filter` with similar syntax; `git` uses
   pathspecs.  The `TYPE:PATTERN` syntax is closest to `git`'s
   `:(glob)pattern` / `:(literal)pattern` pathspec magic.

### Where Filters Apply

- `dandi download --zarr ...`: Filters which entries within Zarr assets to
  download.  When `--zarr` is specified, only matching entries are downloaded.
  Applies to **all** Zarr assets encountered (whether downloading a single zarr
  URL or an entire dandiset).

- `dandi upload` does **not** use `--zarr` filters for selecting what to upload
  (the local filesystem determines that).  Upload behavior is controlled by
  `--zarr-mode` (see Part 2).

### Implementation

#### New module: `dandi/zarr_filter.py`

```python
@dataclass
class ZarrFilter:
    """Filter for selecting entries within a Zarr asset."""
    filter_type: Literal["glob", "path", "regex"]
    pattern: str

    def matches(self, entry_path: str) -> bool:
        """Test if a zarr-internal path matches this filter."""
        ...

ZARR_FILTER_ALIASES: dict[str, list[ZarrFilter]] = {
    "metadata": [
        ZarrFilter("glob", "**/.z*"),
        ZarrFilter("glob", "**/zarr.json"),
        ZarrFilter("glob", "**/.zmetadata"),
    ],
}

def parse_zarr_filter(spec: str) -> list[ZarrFilter]:
    """Parse a --zarr filter spec like 'glob:**/.z*' or 'metadata'."""
    if spec in ZARR_FILTER_ALIASES:
        return ZARR_FILTER_ALIASES[spec]
    type_, _, pattern = spec.partition(":")
    if not pattern:
        raise click.BadParameter(f"Invalid zarr filter: {spec!r}")
    return [ZarrFilter(type_, pattern)]

def make_zarr_entry_filter(filters: list[ZarrFilter]) -> Callable[[str], bool]:
    """Return a predicate: entry_path -> bool (True = include)."""
    def predicate(entry_path: str) -> bool:
        return any(f.matches(entry_path) for f in filters)
    return predicate
```

#### CLI changes: `dandi/cli/cmd_download.py`

```python
@click.option(
    "--zarr",
    "zarr_filters",
    multiple=True,
    metavar="FILTER",
    help=(
        "Filter entries within Zarr assets.  Format: TYPE:PATTERN where TYPE "
        "is 'glob', 'path', or 'regex'.  Predefined: 'metadata'. "
        "Can be specified multiple times (OR logic)."
    ),
)
```

#### Download pipeline changes: `dandi/download.py`

`_download_zarr()` (line ~986) gains a `zarr_entry_filter: Callable | None` parameter:

- When a filter is active:
  - For `path:` filters, use `asset.iterfiles(prefix=...)` to reduce API calls
  - For other filters, iterate all entries and apply `predicate(str(entry))`
  - **Skip** the "deleting extra files" step (lines 1045-1075) -- we don't
    want to delete local files outside the filter scope
  - **Skip** zarr-level checksum verification (lines 1077-1091) -- partial
    downloads won't match the whole-zarr checksum
  - **Do** verify individual file checksums (MD5/etag) as they are downloaded --
    this already happens in `_download_file()`

---

## Part 2: URL Parsing -- Zarr-Internal Paths

### Problem

A user may specify a URL like:

```
dandi://dandi/000108/.../sub-MITU01.ome.zarr/0/0/0/0/0
```

Currently, `parse_dandi_url()` creates an `AssetItemURL` with the full path,
and `get_asset_by_path()` fails because no asset exists at that path -- the
asset path is `sub-MITU01.ome.zarr` and `0/0/0/0/0` is internal to the Zarr.

### Approach

Add zarr boundary detection in URL parsing (as discussed in #1462 by @jwodder),
mirroring dandidav's approach:

1. When `parse_dandi_url()` would create an `AssetItemURL`, scan the `location`
   path for segments ending with extensions in `ZARR_EXTENSIONS` (`.zarr`,
   `.ngff`).

2. If found, split into `asset_path` (up to and including the `.zarr`/`.ngff`
   segment) and `zarr_subpath` (the remainder).

3. Create a new `AssetZarrEntryURL` that carries both parts:

```python
@dataclass
class AssetZarrEntryURL(SingleAssetURL):
    """URL pointing to entries within a Zarr asset."""
    asset_path: str    # e.g., "sub-1/file.ome.zarr"
    zarr_subpath: str  # e.g., "0/0/0/0/0"

    def get_assets(self, client, order=None, strict=False):
        dandiset = self.get_dandiset(client, lazy=not strict)
        assert dandiset is not None
        yield dandiset.get_asset_by_path(self.asset_path)

    def get_zarr_filter(self) -> list[ZarrFilter]:
        """Convert the subpath into a path: filter for download."""
        return [ZarrFilter("path", self.zarr_subpath)]
```

The download pipeline then combines any URL-derived filters with explicit
`--zarr` filters (OR semantics).

### Validation

Use `PurePosixPath` to check path components properly (addressing @jwodder's
review on #1596 about rejecting paths like `foo/.zarr/bar`):

```python
from pathlib import PurePosixPath

def split_zarr_location(location: str) -> tuple[str, str] | None:
    """Split a location into (asset_path, zarr_subpath) if it crosses a zarr boundary."""
    parts = PurePosixPath(location).parts
    for i, part in enumerate(parts):
        if any(part.endswith(ext) for ext in ZARR_EXTENSIONS):
            asset_path = "/".join(parts[: i + 1])
            zarr_subpath = "/".join(parts[i + 1 :])
            return (asset_path, zarr_subpath) if zarr_subpath else None
    return None
```

---

## Part 3: Partial Zarr Upload (`--zarr-mode`)

### Modes

| Mode | Behavior |
|------|----------|
| `full` (default) | Current behavior: full bidirectional sync. Upload new/changed local files, **delete** remote files not present locally. |
| `patch` | Upload new/changed local files. **Never delete** remote files absent locally. |

**Why start with two modes**: The `partial-full` and `partial-lean` modes from
#1462 add complexity that isn't needed for the primary metadata-editing use
case.  We can add them later if requested.

**"patch" vs "dont-delete"**: "dont-delete" is misleading because even in `patch`
mode, if the user re-uploads a subdirectory tree, files within that tree that
were replaced by different structure should be cleaned up.  See "Subtree sync"
below.  "patch" better conveys "apply these changes on top of what's there."

### Subtree Sync Semantics

When uploading in `patch` mode, we still need to handle cases where a file at
path `a/b` locally is now a directory remotely (or vice versa).  The existing
conflict-resolution logic in `iter_upload()` (lines 658-688) handles this:
if a local file's parent is a remote file, or a local file's path is a remote
directory, the conflicting remote entries are deleted.  This behavior should be
preserved in `patch` mode.

What `patch` mode changes is **only** the final cleanup step: remote files that
simply don't have a corresponding local file are **not** deleted (lines 838-850
in `zarr.py`).

### Checksum Handling in `patch` Mode

After upload, the server computes a zarr-level checksum over **all** remote
files (via `POST /zarr/{id}/finalize/`).  In `patch` mode, the client only has
a subset of files locally, so it cannot independently compute the matching
whole-zarr checksum.

**Approach**: Skip local checksum comparison in `patch` mode.  The server still
finalizes and computes its checksum correctly.  Log a message explaining that
whole-zarr checksum verification is skipped due to partial upload mode.

Individual file checksums (MD5) are still verified during upload -- each file's
`Content-MD5` header is checked by S3 on upload, and the local digest is
compared against the remote entry's etag during the comparison phase.

### Implementation: `dandi/files/zarr.py`

`iter_upload()` gains `zarr_mode: str = "full"`:

```python
def iter_upload(self, dandiset, metadata, jobs=None, replacing=None,
                zarr_mode="full"):
    ...
    # Line ~650: Only collect to_delete in full mode
    if zarr_mode == "full":
        to_delete: list[RemoteZarrEntry] = []
    else:
        to_delete = None  # signal: skip deletion

    ...
    # Line ~838: Skip deleting extra remote files in patch mode
    if zarr_mode == "full":
        old_zarr_files = list(old_zarr_entries.values())
        if old_zarr_files:
            yield from _rmfiles(...)

    ...
    # Line ~861: Skip local checksum comparison in patch mode
    if zarr_mode == "patch":
        lgr.info("%s: Skipping local checksum verification (patch mode)", asset_path)
        mismatched = False
    else:
        our_checksum = str(zcc.process())
        ...
```

### CLI: `dandi/cli/cmd_upload.py`

```python
@click.option(
    "--zarr-mode",
    type=click.Choice(["full", "patch"]),
    default="full",
    help="Zarr sync mode: 'full' (default) syncs completely; "
         "'patch' uploads/updates without deleting remote files.",
    show_default=True,
)
```

---

## Part 4: Checksums and Manifests

### Current State

The zarr checksum is a **tree hash** (dandi-archive #931, resolved).  Each
directory's checksum is computed from its immediate children only (not full
paths), producing a hierarchical Merkle-like structure:

```
root_checksum = md5(json({"directories": [...], "files": [...]})) + "-N--S"
```

where each child entry is `{"digest": ..., "name": ..., "size": ...}`.

The `zarr_checksum` library (`~0.4.0`) implements this via `ZarrChecksumTree`
(see `zarr_checksum/tree.py`).  The tree processes nodes bottom-up: each
directory's digest is computed from sorted JSON of its immediate children's
`{name, digest, size}` entries.  This is repeated upward until the root digest
is produced.

### Per-Directory Checksums Are NOT Persisted

Although the algorithm is hierarchical and computes per-directory checksums as
intermediate results, the archive does **not** persist these intermediate
checksums anywhere.  Specifically:

- The archive's `ingest_zarr_archive` Celery task (in
  `dandiapi/zarr/tasks/__init__.py`) calls `compute_zarr_checksum()` which
  streams all files from S3, computes the tree hash **entirely in memory**,
  and stores only the final root digest in the database (`zarr.checksum`,
  `zarr.file_count`, `zarr.size`).

- An earlier design (`zarr-support-3.md`) wrote per-directory `.checksum`
  files to S3 under the `zarr-checksums/` prefix (note: hyphen, not
  underscore).  The server code that wrote these was removed in December 2022
  (dandi-archive commits removing `ZarrChecksumFileUpdater`, PRs #1390,
  #1395).  However, **legacy `.checksum` files still exist on S3** for
  ~3,930 out of 5,431 zarrs (~72%) — those ingested before the removal.
  Newer zarrs do not have them.  These legacy files are not exposed via any
  API endpoint and are effectively orphaned artifacts.

- There is no API endpoint to retrieve per-directory checksums.

This means **subtree checksum verification is not possible today** without
recomputing the checksum from individual file ETags (or reading the legacy
`.checksum` files directly from S3 for older zarrs, which is not a viable
general solution).

### Incorporating Checksums into Manifests

The versioned Zarr design doc (dandi-archive #2702, #1892) proposes **manifest
files** that track each Zarr snapshot's file inventory (paths, S3 version IDs,
sizes, ETags).  These manifests would enable publishing Zarr-bearing dandisets.

**Recommendation**: Include per-directory checksums in the manifest structure.
Since the algorithm is already hierarchical (each directory checksum depends only
on its immediate children), the manifest can encode the full Merkle tree.  This
would enable:

1. **Partial checksum verification**: After a partial download, verify the
   checksum of each downloaded subtree against the manifest's per-directory
   checksums, rather than only verifying individual file ETags.

2. **Efficient change detection**: When uploading in `patch` mode, compare
   the local subtree's checksum against the manifest to detect whether changes
   occurred, without comparing every file individually.

3. **Incremental manifest updates**: When a subtree is modified, only the
   checksums along the path from that subtree to the root need recomputation.

For the initial implementation here, we rely on per-file ETags for verification
and skip subtree-level checksums.  A follow-up could add subtree verification
if the archive exposes per-directory checksums via API or manifests.

### What We Verify Now

| Scenario | File-level (MD5/ETag) | Subtree checksum | Whole-zarr checksum |
|----------|-----------------------|------------------|---------------------|
| Full download | Yes | N/A | Yes |
| Partial download (`--zarr`) | Yes | No (future: via manifest) | No (skipped) |
| Full upload | Yes (via S3 Content-MD5) | N/A | Yes (client vs server) |
| Patch upload | Yes (via S3 Content-MD5) | No (future: via manifest) | No (skipped) |

---

## Part 5: `dandi ls` for Zarr Contents

See separate implementation task.  Summary: allow `dandi ls` to list files
within a Zarr asset when given a Zarr URL, using `asset.iterfiles(prefix=...)`.
Reuses `AssetZarrEntryURL` from Part 2.

---

## Implementation Order

1. **`dandi/zarr_filter.py`** -- filter parsing and matching (no deps)
2. **URL parsing** -- `AssetZarrEntryURL` and `split_zarr_location()` in
   `dandi/dandiarchive.py`
3. **Download pipeline** -- `_download_zarr()` partial support, `Downloader`
   plumbing
4. **`--zarr` CLI option** on `dandi download`
5. **`--zarr-mode` CLI option** on `dandi upload`
6. **`iter_upload()` patch mode** in `dandi/files/zarr.py`
7. **Upload plumbing** in `dandi/upload.py`
8. **`dandi ls` zarr contents** (separate PR)
9. Tests throughout

## Files to Modify

| File | Changes |
|------|---------|
| `dandi/zarr_filter.py` | **New**: filter parsing, matching, aliases |
| `dandi/consts.py` | `ZARR_METADATA_FILENAMES` constants (used by `metadata` alias) |
| `dandi/dandiarchive.py` | `AssetZarrEntryURL`, `split_zarr_location()`, modify `parse_dandi_url()` |
| `dandi/cli/cmd_download.py` | `--zarr` option |
| `dandi/cli/cmd_upload.py` | `--zarr-mode` option |
| `dandi/download.py` | `_download_zarr()` filtering, `Downloader` plumbing |
| `dandi/upload.py` | Pass `zarr_mode` through |
| `dandi/files/zarr.py` | `iter_upload()` patch mode support |
| `dandi/cli/cmd_ls.py` | Zarr contents listing (separate PR) |

## Open Questions

1. **`--zarr` AND vs OR**: Multiple `--zarr` options use OR.  Should we support
   AND composition (e.g., `--zarr path:0/1 --zarr-and glob:'**/.zattrs'`)?
   For now, OR suffices; AND can be added later.

2. **Server-side glob for zarr entries**: Currently the server only supports
   `prefix` filtering on zarr entries (not glob).  Glob filtering therefore
   happens client-side after fetching entries.  For large zarrs with millions of
   entries, this could be slow.  A future server API enhancement for
   entry-level glob would help.  For now, `path:` filters should be preferred
   for large zarrs to minimize data transfer.

3. **Interaction with `--sync`**: When `dandi download --zarr ... --sync` is
   used, should `--sync` only delete local zarr entries that match the filter
   but aren't remote?  Or should `--sync` be disallowed with `--zarr`?
   Recommendation: disallow `--sync` with `--zarr` initially, as the semantics
   are ambiguous.
