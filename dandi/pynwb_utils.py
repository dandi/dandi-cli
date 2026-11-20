"""Utilities for working with NWB (Neurodata Without Borders) files.

This module provides helper functions for reading, validating, and extracting
metadata from NWB files using PyNWB. Features include:
- NWB file I/O with caching
- Metadata extraction for DANDI schema
- Version compatibility checking
- External link detection
- Validation against NWB standards
"""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from functools import wraps
import inspect
import json
import os
import os.path as op
from pathlib import Path, PurePosixPath
import re
import sys
from typing import IO, Any, TypeGuard, TypeVar, cast
import warnings

import dandischema
from fscacher import PersistentCache
import h5py
import hdmf
from hdmf.backends.io import HDMFIO
import numpy as np
from packaging.version import InvalidVersion, Version
import pynwb
from pynwb import NWBHDF5IO
from pynwb.base import ExternalImage
import semantic_version

from . import __version__, get_logger
from .consts import (
    IMAGE_FILE_EXTENSIONS,
    VIDEO_FILE_EXTENSIONS,
    VIDEO_FILE_MODULES,
    metadata_nwb_computed_fields,
    metadata_nwb_file_fields,
    metadata_nwb_subject_fields,
)
from .exceptions import NWBZarrReadError
from .files.zarr import ZarrNode, get_zarr_format_version, read_zarr_node
from .misctypes import Readable
from .utils import get_module_version, is_url, pluralize
from .validate._types import (
    Origin,
    OriginType,
    Scope,
    Severity,
    Standard,
    ValidationResult,
    Validator,
)

lgr = get_logger()

# strip away possible development version marker
dandi_rel_version = __version__.split("+", 1)[0]
dandi_cache_tokens = [
    get_module_version(pynwb),
    dandi_rel_version,
    get_module_version(hdmf),
    get_module_version(h5py),
]
metadata_cache = PersistentCache(
    name="dandi-metadata", tokens=dandi_cache_tokens, envvar="DANDI_CACHE"
)
validate_cache = PersistentCache(
    name="dandi-validate",
    tokens=dandi_cache_tokens + [get_module_version(dandischema)],
    envvar="DANDI_CACHE",
)

#: How to install hdmf-zarr >= 0.14 (the first release reading Zarr v3, and
#: Zarr v2 with zarr-python 3), the optional dependency for reading NWB files
#: stored as Zarr, which requires Python >= 3.12
NWB_ZARR_INSTALL_HINT = (
    "NWB files stored as Zarr need hdmf-zarr >= 0.14: install it with "
    "`pip install 'dandi[nwb-zarr]'`."
    if sys.version_info >= (3, 12)
    else "NWB files stored as Zarr need hdmf-zarr >= 0.14, and thus Python >= 3.12."
)

#: The environment variable with which numcodecs, and dandi, allow decoding
#: data stored with the pickle codec
PICKLE_DECODE_ENVVAR = "NUMCODECS_ALLOW_UNSAFE_PICKLE_DECODE"

F = TypeVar("F", bound=Callable[..., Any])


def is_nwb_zarr(path: str | Path | Readable) -> TypeGuard[str | Path]:
    """Whether ``path`` is an NWB file stored as Zarr, i.e. a local directory

    NWB files stored in HDF5 are regular files; those stored as Zarr
    (:file:`*.nwb.zarr`) are directories.
    """
    return not isinstance(path, Readable) and op.isdir(path)


def memoize_path_unless_dir(cache: PersistentCache) -> Callable[[F], F]:
    """Like ``cache.memoize_path``, but not memoizing calls on a directory (an
    NWB file stored as Zarr)

    fscacher fingerprints a directory by stat-ing every file below it, i.e.
    every chunk of every array of a Zarr, which takes longer than the calls it
    would spare.
    """

    def decorator(f: F) -> F:
        memoized = cache.memoize_path(f)

        @wraps(f)
        def wrapper(path: Any, *args: Any, **kwargs: Any) -> Any:
            if is_nwb_zarr(path):
                return f(path, *args, **kwargs)
            return memoized(path, *args, **kwargs)

        return cast(F, wrapper)

    return decorator


def pickle_decoding_allowed() -> bool:
    """Whether decoding data stored with the pickle codec, which can execute
    arbitrary code, was allowed as numcodecs allows it:
    ``numcodecs.pickles.ALLOW_UNSAFE_PICKLE_DECODE``, set from the
    ``NUMCODECS_ALLOW_UNSAFE_PICKLE_DECODE`` environment variable when
    numcodecs is imported, or for numcodecs releases without it, that
    environment variable"""
    # Avoid heavy import by importing within function:
    import numcodecs.pickles

    if hasattr(numcodecs.pickles, "ALLOW_UNSAFE_PICKLE_DECODE"):
        return bool(numcodecs.pickles.ALLOW_UNSAFE_PICKLE_DECODE)
    return os.environ.get(PICKLE_DECODE_ENVVAR, "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def get_nwb_zarr_reading_problem(path: str | Path) -> str | None:
    """Why the NWB file stored as Zarr at ``path`` cannot be read, if it cannot

    It cannot be read if hdmf-zarr >= 0.14, an optional dependency, is not
    installed, or if it stores data with the pickle codec (as hdmf-zarr < 0.14
    did for some columns, e.g. the ``group`` of the electrodes table) and
    decoding such data, which can execute arbitrary code, was not allowed
    (`pickle_decoding_allowed()`), which hdmf-zarr would otherwise report
    less clearly, if at all.
    """
    try:
        # Avoid heavy import by importing within function:
        import hdmf_zarr
    except ImportError as e:
        return f"hdmf-zarr is not installed ({e}).  {NWB_ZARR_INSTALL_HINT}"
    if not hasattr(hdmf_zarr, "NWBZarrV2IO"):
        # Added in hdmf-zarr 0.14, which reads Zarr v3, and Zarr v2 with it
        return f"hdmf-zarr {hdmf_zarr.__version__} is too old.  {NWB_ZARR_INSTALL_HINT}"
    path = Path(path)
    if pickle_decoding_allowed():
        return None
    try:
        pickled = get_pickled_zarr_arrays(path)
    except (OSError, ValueError) as e:
        return f"its Zarr metadata cannot be read: {type(e).__name__}: {e}"
    if pickled:
        return (
            f"it stores data with the pickle codec in "
            f"{pluralize(len(pickled), 'array')} (e.g. {pickled[0]}), and decoding "
            "it can execute arbitrary code.  If you trust this file, set the "
            f"environment variable {PICKLE_DECODE_ENVVAR}=1 to allow it.  NWB "
            "files stored as Zarr v3 (by hdmf-zarr >= 0.14) do not use the pickle "
            "codec"
        )
    return None


def open_nwb_zarr(path: str | Path) -> HDMFIO:
    """Open the NWB file stored as Zarr at ``path`` for reading with its cached
    namespaces, with the hdmf-zarr IO class for its Zarr format

    :raises NWBZarrReadError:
        if `get_nwb_zarr_reading_problem()` finds that it cannot be read
    """
    if (problem := get_nwb_zarr_reading_problem(path)) is not None:
        raise NWBZarrReadError(f"Cannot read NWB file stored as Zarr {path}: {problem}")
    # Avoid heavy import by importing within function:
    import hdmf_zarr

    if get_zarr_format_version(Path(path)) == "2":
        # NWBZarrIO reads only Zarr v3
        return cast(
            HDMFIO,
            hdmf_zarr.NWBZarrV2IO(
                str(path),
                mode="r",
                load_namespaces=True,
                allow_pickle=pickle_decoding_allowed(),
            ),
        )
    return cast(HDMFIO, hdmf_zarr.NWBZarrIO(str(path), mode="r", load_namespaces=True))


@contextmanager
def _open_nwb_io(path: str | Path | Readable) -> Iterator[HDMFIO]:
    """Open an NWB file stored as HDF5 or Zarr for reading with its cached
    namespaces"""
    if is_nwb_zarr(path):
        with open_nwb_zarr(path) as io:
            yield io
    else:
        with open_readable(path) as fp, h5py.File(fp, "r") as h5, NWBHDF5IO(
            file=h5, load_namespaces=True
        ) as io:
            yield io


def _is_zarr_array(value: Any) -> bool:
    """Whether ``value`` is a (lazily read) Zarr array"""
    # Not importing zarr only for this check: it is imported (by hdmf-zarr)
    # once an NWB file stored as Zarr is read
    return (zarr := sys.modules.get("zarr")) is not None and isinstance(
        value, zarr.Array
    )


def _get_zarr_group_attrs(dirpath: Path) -> dict[str, Any]:
    """Attributes of the Zarr group at ``dirpath``"""
    node = read_zarr_node(dirpath)
    if node is None or node.node_type != "group":
        raise ValueError(f"{dirpath} is not a Zarr group")
    return node.attributes


def _iter_zarr_children(dirpath: Path) -> Iterator[tuple[Path, ZarrNode]]:
    """Yield the path and node of each Zarr group or array directly within the
    Zarr group at ``dirpath``"""
    for p in sorted(dirpath.iterdir()):
        if p.is_dir() and (node := read_zarr_node(p)) is not None:
            yield p, node


def _iter_zarr_subgroups(dirpath: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Yield the path and attributes of each Zarr group directly within the
    Zarr group at ``dirpath``"""
    for p, node in _iter_zarr_children(dirpath):
        if node.node_type == "group":
            yield p, node.attributes


def _walk_zarr_nodes(dirpath: Path) -> Iterator[tuple[Path, ZarrNode]]:
    """Yield the path and node of the Zarr group at ``dirpath`` and of all
    groups and arrays below it, without descending into arrays (and their
    chunks)"""
    root = read_zarr_node(dirpath)
    if root is None or root.node_type != "group":
        raise ValueError(f"{dirpath} is not a Zarr group")
    yield dirpath, root
    queue = deque([dirpath])
    while queue:
        for p, node in _iter_zarr_children(queue.popleft()):
            yield p, node
            if node.node_type == "group":
                queue.append(p)


def _walk_zarr_groups(dirpath: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Yield the path and attributes of the Zarr group at ``dirpath`` and of
    all groups below it"""
    for p, node in _walk_zarr_nodes(dirpath):
        if node.node_type == "group":
            yield p, node.attributes


def _uses_pickle(array_metadata: dict[str, Any]) -> bool:
    """Whether the Zarr array with the given metadata uses the pickle codec"""

    def as_list(value: Any) -> list:
        return value if isinstance(value, list) else []

    def is_pickle(codec: Any) -> bool:
        if not isinstance(codec, dict):
            return False
        if "pickle" in str(codec.get("id") or codec.get("name")):
            return True
        # The codecs nested in a codec, e.g. that of Zarr v3 sharding
        configuration = codec.get("configuration")
        return isinstance(configuration, dict) and any(
            is_pickle(c)
            for key in ("codecs", "index_codecs")
            for c in as_list(configuration.get(key))
        )

    # Zarr v2 has a compressor and filters, Zarr v3 codecs
    codecs = [
        array_metadata.get("compressor"),
        *as_list(array_metadata.get("filters")),
        *as_list(array_metadata.get("codecs")),
    ]
    return any(is_pickle(c) for c in codecs)


def _iter_consolidated_arrays(
    metadata: dict[str, Any], prefix: str = ""
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield the path and metadata of each array in the (possibly nested)
    consolidated metadata of a Zarr v3 group"""
    consolidated = metadata.get("consolidated_metadata")
    if not isinstance(consolidated, dict):
        return
    nodes = consolidated.get("metadata")
    if not isinstance(nodes, dict):
        return
    for key, node in nodes.items():
        if isinstance(node, dict):
            path = f"{prefix}{key}"
            if node.get("node_type") == "array":
                yield path, node
            else:
                yield from _iter_consolidated_arrays(node, f"{path}/")


def get_pickled_zarr_arrays(dirpath: str | Path) -> list[str]:
    """Paths (within it) of the arrays of the Zarr group at ``dirpath`` that
    store their data with the pickle codec, per their metadata, or per the
    consolidated metadata of the group, by which zarr may open them instead

    :raises OSError, ValueError: if the Zarr metadata cannot be read
    """
    dirpath = Path(dirpath)
    pickled = set()
    for p, node in _walk_zarr_nodes(dirpath):
        if node.node_type == "array" and _uses_pickle(node.metadata):
            pickled.add(p.relative_to(dirpath).as_posix())
        if p == dirpath:
            # Zarr v3 consolidated metadata, in the group's zarr.json
            pickled.update(
                path
                for path, metadata in _iter_consolidated_arrays(node.metadata)
                if _uses_pickle(metadata)
            )
    # Zarr v2 consolidated metadata
    if (zmetadata := dirpath / ".zmetadata").is_file():
        with zmetadata.open(encoding="utf-8") as fp:
            consolidated = json.load(fp)
        if not isinstance(consolidated, dict):
            raise ValueError(f"{zmetadata} does not hold a JSON object")
        entries = consolidated.get("metadata")
        for key, metadata in (entries if isinstance(entries, dict) else {}).items():
            if (
                key.endswith(".zarray")
                and isinstance(metadata, dict)
                and _uses_pickle(metadata)
            ):
                pickled.add(PurePosixPath(key).parent.as_posix())
    return sorted(pickled)


def _sanitize_nwb_version(
    v: Any,
    filename: str | Path | None = None,
    log: Callable[[str], Any] | None = None,
) -> str:
    """Helper to sanitize the value of nwb_version where possible

    Would log a warning if something detected to be fishy"""
    msg = f"File {filename}: " if filename else ""
    msg += f"nwb_version {v!r}"

    if log is None:
        log = lgr.warning

    if isinstance(v, str):
        if v.startswith("NWB-"):
            vstr = v[4:]
            # should be semver since 2.1.0
            if not (vstr.startswith("1.") or vstr.startswith("2.0")):
                log(
                    f"{msg} starts with NWB- prefix, which is not part of the "
                    f"specification since NWB 2.1.0"
                )
        else:
            vstr = v
        if not semantic_version.validate(vstr):
            log(f"error: {msg} is not a proper semantic version. See http://semver.org")
    elif isinstance(v, int):
        vstr = str(v)
        log(
            f"error: {msg} is an integer instead of a proper semantic version."
            " See http://semver.org"
        )
    else:
        log(f"{msg} is not text which follows semver specification")
        vstr = str(v)
    return vstr


def get_nwb_version(
    filepath: str | Path | Readable, sanitize: bool = False
) -> str | None:
    """Return a version of the NWB standard used by a file

    Parameters
    ----------
    sanitize: bool, optional
      Either to sanitize version and return it non-raw where we detect version
      which does not follow semantic but we possibly can handle

    Returns
    -------
    str or None
       None if there is no version detected
    """
    if sanitize:

        def _sanitize(v: Any) -> str:
            return _sanitize_nwb_version(v)

    else:

        def _sanitize(v: Any) -> str:
            return str(v)

    if is_nwb_zarr(filepath):
        attrs = _get_zarr_group_attrs(Path(filepath))
        if "nwb_version" in attrs:
            return _sanitize(attrs["nwb_version"])
        lgr.debug("%s has no nwb_version", filepath)
        return None

    with open_readable(filepath) as fp, h5py.File(fp, "r") as h5file:
        # 2.x stored it as an attribute
        try:
            return _sanitize(h5file.attrs["nwb_version"])
        except KeyError:
            pass

        # 1.x stored it as a dataset
        try:
            return _sanitize(h5file["nwb_version"][...].tostring().decode())
        except Exception:
            lgr.debug("%s has no nwb_version", filepath)
    return None


# Namespaces bundled with NWB/HDMF core — not extensions
_NWB_CORE_NAMESPACES = frozenset({"core", "hdmf-common", "hdmf-experimental"})


def get_nwb_extensions(filepath: str | Path | Readable) -> dict[str, str]:
    """Return NWB extensions embedded in an NWB file.

    Reads the ``specifications`` group of an NWB file (stored as HDF5 or Zarr)
    and returns a mapping of extension namespace names to their latest
    embedded version, excluding core NWB/HDMF namespaces.

    Parameters
    ----------
    filepath
        Path to an NWB ``.nwb`` HDF5 file or ``.nwb.zarr`` Zarr directory, or
        a :class:`Readable`.

    Returns
    -------
    dict[str, str]
        ``{namespace_name: latest_version}`` for each non-core namespace
        found in the file's ``specifications`` group.  Empty dict if no
        extensions are present or the group does not exist.
    """
    namespaces: dict[str, list[str]] = {}
    if is_nwb_zarr(filepath):
        specs_path = Path(filepath, "specifications")
        if read_zarr_node(specs_path) is not None:
            for ns_path, _ in _iter_zarr_subgroups(specs_path):
                namespaces[ns_path.name] = [
                    p.name for p, _ in _iter_zarr_subgroups(ns_path)
                ]
    else:
        with open_readable(filepath) as fp, h5py.File(fp, "r") as h5file:
            if (specs := h5file.get("specifications")) is not None:
                for name, ns_group in specs.items():
                    if isinstance(ns_group, h5py.Group):
                        namespaces[name] = list(ns_group)
    extensions: dict[str, str] = {}
    for name, versions in namespaces.items():
        if name in _NWB_CORE_NAMESPACES or not versions:
            continue
        try:
            extensions[name] = max(versions, key=Version)
        except InvalidVersion:
            lgr.debug(
                "Cannot parse versions %s of NWB extension %s, taking the "
                "lexicographically last",
                versions,
                name,
            )
            extensions[name] = max(versions)
    return extensions


def get_neurodata_types_to_modalities_map() -> dict[str, str]:
    """Return a dict to map neurodata types known to pynwb to "modalities"

    It is an ugly hack, largely to check feasibility.
    It would base modality on the filename within pynwb providing that neural
    data type
    """
    ndtypes: dict[str, str] = {}

    # TODO: if there are extensions, they might have types subclassed from the base
    # types.  There might be a map within pynwb (pynwb.get_type_map?) to return
    # known extensions. We would need to go along MRO to the base to figure out
    # "modality"
    #
    # They import all submods within __init__
    for a, v in pynwb.__dict__.items():
        if not (inspect.ismodule(v) and v.__name__.startswith("pynwb.")):
            continue
        for a_, v_ in v.__dict__.items():
            # now inspect all things within and get neural datatypes
            if inspect.isclass(v_) and issubclass(v_, pynwb.core.NWBMixin):
                ndtype = v_.__name__

                v_split = v_.__module__.split(".")
                if len(v_split) != 2:
                    print(f"Skipping {v_} coming from {v_.__module__}")
                    continue
                modality = v_split[1]  # so smth like ecephys

                if ndtype in ndtypes:
                    if ndtypes[ndtype] == modality:
                        continue  # all good, just already known
                    raise RuntimeError(
                        "We already have %s pointing to %s, but now got %s"
                        % (ndtype, ndtypes[ndtype], modality)
                    )
                ndtypes[ndtype] = modality

    return ndtypes


@memoize_path_unless_dir(metadata_cache)
def get_neurodata_types(filepath: str | Path | Readable) -> list[str]:
    if is_nwb_zarr(filepath):
        all_pairs = [
            (attrs["neurodata_type"], attrs.get("description", None))
            for _, attrs in _walk_zarr_groups(Path(filepath))
            if "neurodata_type" in attrs
        ]
    else:
        with open_readable(filepath) as fp, h5py.File(fp, "r") as h5file:
            all_pairs = _scan_neurodata_types(h5file)

    # so far descriptions are useless so let's just output actual names only
    # with a count if there is multiple
    # return [': '.join(filter(bool, p)) for p in all_pairs]
    names = [p[0] for p in all_pairs if p[0] not in {"NWBFile"}]
    counts = Counter(names)
    out = []
    for name, count in sorted(counts.items()):
        if count > 1:
            out.append("%s (%d)" % (name, count))
        else:
            out.append(name)
    return out


def _scan_neurodata_types(grp: h5py.File) -> list[tuple[Any, Any]]:
    out = []
    if "neurodata_type" in grp.attrs:
        out.append((grp.attrs["neurodata_type"], grp.attrs.get("description", None)))
    for v in list(grp.values()):
        if isinstance(v, h5py._hl.group.Group):
            out += _scan_neurodata_types(v)
    return out


def _get_pynwb_metadata(path: str | Path | Readable) -> dict[str, Any]:
    out = {}
    with _open_nwb_io(path) as io:
        nwb = io.read()
        for key in metadata_nwb_file_fields:
            value = getattr(nwb, key)
            if isinstance(value, h5py.Dataset):
                # serialize into a basic container (list), since otherwise
                # it would be a closed Dataset upon return
                value = list(value)
            elif _is_zarr_array(value):
                value = list(value[...])
            if isinstance(value, (list, tuple)) and all(
                isinstance(v, bytes) for v in value
            ):
                value = type(value)(v.decode("utf-8") for v in value)
            out[key] = value

        # .subject can be None as the test shows
        for subject_feature in metadata_nwb_subject_fields:
            out[subject_feature] = getattr(nwb.subject, subject_feature, None)
        # Add a few additional useful fields

        # "Custom" DANDI extension by Ben for now to contain additional metadata
        # not present in nwb-schema
        dandi_icephys = getattr(nwb, "lab_meta_data", {}).get(
            "DandiIcephysMetadata", None
        )
        if dandi_icephys:
            out.update(dandi_icephys.fields)
        # Go through devices and see if there any probes used to record this file
        probe_ids = [
            v.probe_id.item()  # .item to avoid numpy types
            for v in getattr(nwb, "devices", {}).values()
            if hasattr(v, "probe_id")  # duck typing
        ]
        if probe_ids:
            out["probe_ids"] = probe_ids

        # Counts
        for f in metadata_nwb_computed_fields:
            if f in ("nwb_version", "nd_types"):
                continue
            if not f.startswith("number_of_"):
                raise NotImplementedError(
                    f"ATM can only compute number_of_ fields. Got {f}"
                )
            key = f[len("number_of_") :]
            out[f] = len(getattr(nwb, key, []) or [])

        # get external_file data:
        out["external_file_objects"] = _get_image_series(nwb)

        # Calculate session duration for metadata
        session_duration = _get_session_duration(nwb)
        if session_duration is not None and out.get("session_start_time") is not None:
            # Convert to absolute datetime by adding duration to session_start_time
            start_time = out["session_start_time"]
            out["session_end_time"] = start_time + timedelta(seconds=session_duration)

        # Extract brain locations for anatomy metadata
        out["brain_locations"] = _get_brain_locations(nwb)

    return out


def _get_session_duration(nwb: pynwb.NWBFile) -> float | None:
    """Calculate the duration of a recording session from NWB file contents.

    This function finds the minimum and maximum timestamps across all TimeSeries
    and DynamicTable objects with time information, then returns the duration as
    max - min.

    Parameters
    ----------
    nwb: pynwb.NWBFile
        An open NWB file object

    Returns
    -------
    float or None
        The session duration in seconds (max_time - min_time),
        or None if no time information could be extracted
    """
    start_times: list[float] = []
    end_times: list[float] = []

    # Iterate through all objects in the NWB file
    for obj in nwb.objects.values():
        # Handle TimeSeries objects
        if isinstance(obj, pynwb.base.TimeSeries):
            if obj.timestamps is not None and len(obj.timestamps) > 0:
                # Use first and last timestamps
                start_times.append(float(obj.timestamps[0]))
                end_times.append(float(obj.timestamps[-1]))
            elif (
                obj.starting_time is not None
                and obj.rate is not None
                and obj.data is not None
            ):
                # Calculate start and end time
                start_times.append(float(obj.starting_time))
                num_samples = len(obj.data)
                if obj.rate == 0:
                    continue
                end_times.append(float(obj.starting_time + (num_samples / obj.rate)))

        # Handle DynamicTable objects with time columns
        elif isinstance(obj, hdmf.common.DynamicTable):
            # Handle start_time and stop_time columns (e.g., trials)
            if "start_time" in obj.colnames and len(obj["start_time"]):
                start_times.append(float(obj["start_time"][0]))
            if "stop_time" in obj.colnames and len(obj["stop_time"]):
                end_times.append(float(obj["stop_time"][-1]))

            # Handle spike_times column (e.g., Units table)
            # Assume spike times are ordered within each unit
            # Read only the first and last spike time from each unit
            if "spike_times" in obj.colnames and len(obj["spike_times"]):
                idxs = obj["spike_times"].data[:]
                # Keep only boundaries where cumulative spike count increases.
                # Non-spiking units repeat the prior cumulative index and are skipped.
                unit_end_idxs = idxs[np.diff(np.r_[0, idxs]) > 0]

                if len(unit_end_idxs) == 0:
                    continue

                st_data = obj["spike_times"].target

                if len(unit_end_idxs) > 1:
                    start = float(
                        np.min(np.r_[st_data[0], st_data[unit_end_idxs[:-1]]])
                    )
                else:
                    start = float(st_data[0])

                end = float(np.max(st_data[unit_end_idxs - 1]))
                start_times.append(float(start))
                end_times.append(float(end))

            # Handle timestamp column (e.g., EventsTable)
            if "timestamp" in obj.colnames and len(obj["timestamp"]):
                timestamp_data = obj["timestamp"]
                start_times.append(float(timestamp_data[0]))
                # Check if duration column exists to calculate end times
                if "duration" in obj.colnames:
                    duration_data = obj["duration"]
                    end_times.append(float(timestamp_data[-1] + duration_data[-1]))
                else:
                    # No duration, use max timestamp as end
                    end_times.append(float(timestamp_data[-1]))

    # Return duration as max - min
    if start_times and end_times:
        duration = max(end_times) - min(start_times)
        if (
            duration < 3600 * 24 * 365 * 5
        ):  # if duration is over 5 years, something went wrong
            return duration
        else:
            lgr.warning(
                "Session duration of %.2f seconds (%.2f years) exceeds 5-year limit; "
                "returning None as this likely indicates an error in timestamps",
                duration,
                duration / (3600 * 24 * 365),
            )
    return None


def _get_brain_locations(nwb: pynwb.NWBFile) -> list[str]:
    """Extract brain location strings from an NWB file.

    Collects location values from imaging planes (ophys), the electrodes
    table (ecephys), and intracellular electrodes (icephys).

    Parameters
    ----------
    nwb : pynwb.NWBFile
        An open NWB file object.

    Returns
    -------
    list[str]
        Raw location strings found in the file.
    """
    locations: list[str] = []

    # Ophys: imaging planes
    for plane in getattr(nwb, "imaging_planes", {}).values():
        loc = getattr(plane, "location", None)
        if loc and isinstance(loc, str):
            locations.append(loc)

    # Ecephys: electrodes table "location" column
    electrodes = getattr(nwb, "electrodes", None)
    if electrodes is not None:
        try:
            col_names = electrodes.colnames
        except Exception:
            lgr.debug(
                "Failed to read colnames from electrodes table",
                exc_info=True,
            )
            col_names = ()
        if col_names and "location" in col_names:
            try:
                locs = electrodes["location"].data[:]
            except Exception:
                lgr.debug(
                    "Failed to read location data from electrodes table",
                    exc_info=True,
                )
                locs = []
            for val in locs:
                if isinstance(val, bytes):
                    val = val.decode("utf-8", errors="replace")
                if val and isinstance(val, str):
                    locations.append(val)

    # Icephys: intracellular electrodes
    ic_electrodes = getattr(nwb, "ic_electrodes", None) or getattr(
        nwb, "icephys_electrodes", None
    )
    if ic_electrodes is not None:
        if isinstance(ic_electrodes, dict):
            for elec in ic_electrodes.values():
                loc = getattr(elec, "location", None)
                if loc and isinstance(loc, str):
                    locations.append(loc)
        else:
            # Might be a DynamicTable in some NWB versions
            try:
                col_names = getattr(ic_electrodes, "colnames", ())
                if col_names and "location" in col_names:
                    for val in ic_electrodes["location"].data[:]:
                        if isinstance(val, bytes):
                            val = val.decode("utf-8", errors="replace")
                        if val and isinstance(val, str):
                            locations.append(val)
            except Exception:
                lgr.debug(
                    "Failed to read location from ic_electrodes table: %s",
                    ic_electrodes,
                    exc_info=True,
                )

    return locations


def _get_image_series(nwb: pynwb.NWBFile) -> list[dict]:
    """Retrieves all ImageSeries related metadata from an open nwb file.

    Specifically it pulls out the ImageSeries uuid, name and all the
    externally linked files named under the argument 'external_file'.

    Parameters
    ----------
    nwb: pynwb.NWBFile

    Returns
    -------
    out: list[dict]
        list of dicts : [{id: <ImageSeries uuid>, name: <IMageSeries name>,
        external_files=[ImageSeries.external_file]}]
        if no ImageSeries found in the given modules to check, then it returns an empty list.
    """
    out = []
    for module_name in VIDEO_FILE_MODULES:
        module_cont = getattr(nwb, module_name)
        for name, ob in module_cont.items():
            if isinstance(ob, pynwb.image.ImageSeries) and ob.external_file is not None:
                out_dict = dict(
                    id=ob.object_id,
                    name=ob.name,
                    external_files=[],
                    field="external_file",
                )
                for ext_file in ob.external_file:
                    if (
                        path := PurePosixPath(ext_file)
                    ).suffix.lower() in VIDEO_FILE_EXTENSIONS:
                        out_dict["external_files"].append(path)
                    else:
                        lgr.warning(
                            "external file %s should be one of: %s",
                            ext_file,
                            ", ".join(VIDEO_FILE_EXTENSIONS),
                        )
                out.append(out_dict)
    out.extend(_get_external_images(nwb))
    return out


def _get_external_images(nwb: pynwb.NWBFile) -> list[dict]:
    """Retrieves all ExternalImage metadata from an open nwb file.

    An `ExternalImage` holds a single path or URL in ``data`` rather than a list in
    ``external_file``, and it sits inside an `Images` container rather than directly in a module,
    so the whole file is walked instead of the top level of the video modules.

    Parameters
    ----------
    nwb: pynwb.NWBFile

    Returns
    -------
    out: list[dict]
        list of dicts : [{id: <ExternalImage uuid>, name: <ExternalImage name>,
        external_files=[ExternalImage.data], field: "data"}]
    """
    out = []
    for ob in nwb.objects.values():
        if not isinstance(ob, ExternalImage) or ob.data is None:
            continue
        data = ob.data.decode() if isinstance(ob.data, bytes) else str(ob.data)
        if (path := PurePosixPath(data)).suffix.lower() not in IMAGE_FILE_EXTENSIONS:
            lgr.warning(
                "external image %s should be one of: %s",
                data,
                ", ".join(IMAGE_FILE_EXTENSIONS),
            )
            continue
        out.append(
            dict(id=ob.object_id, name=ob.name, external_files=[path], field="data")
        )
    return out


def rename_nwb_external_files(metadata: list[dict], dandiset_path: str) -> None:
    """Rename external media references in an open NWB file.

    This updates ``ImageSeries.external_file`` entries and legacy
    ``PoseEstimation.original_videos`` references using the path mapping
    collected in ``metadata["external_file_objects"]``.

    It pulls information about the ImageSeries objects from metadata:
    metadata["external_file_objects"] populated during _get_pynwb_metadata() call.

    Parameters
    ----------
    metadata: list[dict]
        list of dictionaries containing the metadata gathered from the nwbfile
    dandiset_path: str
        base path of dandiset
    """
    for meta in metadata:
        if not all(i in meta for i in ["path", "dandi_path", "external_file_objects"]):
            lgr.warning(
                "could not rename external files, update metadata "
                'with "path", "dandi_path", "external_file_objects"'
            )
            return
        dandiset_nwbfile_path = op.join(dandiset_path, meta["dandi_path"])
        image_series = [
            d
            for d in meta["external_file_objects"]
            if d.get("field", "external_file") == "external_file"
        ]
        external_images = [
            d for d in meta["external_file_objects"] if d.get("field") == "data"
        ]
        if image_series:
            with NWBHDF5IO(
                dandiset_nwbfile_path, mode="r+", load_namespaces=True
            ) as io:
                nwb = io.read()
                pose_video_renames: dict[str, str] = {}
                for ext_file_dict in image_series:
                    # retrieve nwb neurodata object of the given object id:
                    container_list = [
                        child
                        for child in nwb.children
                        if ext_file_dict["id"] == child.object_id
                    ]
                    if len(container_list) == 0:
                        continue
                    else:
                        container = container_list[0]
                    # rename all external files:
                    for no, (name_old, name_new) in enumerate(
                        zip(
                            ext_file_dict["external_files"],
                            ext_file_dict["external_files_renamed"],
                        )
                    ):
                        reference = _external_reference_key(name_old)
                        if not is_url(reference):
                            container.external_file[no] = str(name_new)
                            pose_video_renames[reference] = str(name_new)
                _rename_pose_estimation_original_videos(nwb, pose_video_renames)
        if external_images:
            _rename_external_images(dandiset_nwbfile_path, external_images)


def _external_reference_key(value: Any) -> str:
    """Return a comparable representation of a legacy external-file reference."""

    if isinstance(value, bytes):
        value = value.decode()
    return str(value).replace("\\", "/")


def _rename_pose_estimation_original_videos(
    nwb: pynwb.NWBFile, renames: dict[str, str]
) -> None:
    """Update legacy ndx-pose ``original_videos`` references in an NWB file.

    ``original_videos`` is deprecated in ndx-pose in favor of the linked
    ``source_video`` field.  Older files can still contain the path list, so
    use the same old-to-new mapping as the source ``ImageSeries`` without
    importing ndx-pose or reading waveform/video payloads.
    """

    if not renames:
        return
    for container in nwb.objects.values():
        if getattr(container, "neurodata_type", None) != "PoseEstimation":
            continue
        original_videos = getattr(container, "original_videos", None)
        if original_videos is None or isinstance(original_videos, (str, bytes)):
            continue
        for no, name_old in enumerate(original_videos):
            reference = _external_reference_key(name_old)
            if is_url(reference):
                continue
            if (name_new := renames.get(reference)) is not None:
                original_videos[no] = name_new


def _rename_external_images(nwbfile_path: str, external_images: list[dict]) -> None:
    """Rewrites the ``data`` of the given `ExternalImage` objects in an NWB file on disk.

    `ExternalImage.data` is a scalar string rather than the array `ImageSeries.external_file` is,
    so assigning through the read container does not reach the file and the dataset is written
    directly instead. Objects are matched on the ``object_id`` attribute, since an `ExternalImage`
    sits inside an `Images` container at a path this function is not told.

    Parameters
    ----------
    nwbfile_path: str
        full path of the NWB file to rewrite
    external_images: list[dict]
        the ``field == "data"`` entries of ``metadata["external_file_objects"]``
    """
    # Avoid a module level dependency on h5py for a path most callers never take:
    import h5py

    renames = {}
    for ext_file_dict in external_images:
        for name_old, name_new in zip(
            ext_file_dict["external_files"], ext_file_dict["external_files_renamed"]
        ):
            if not is_url(str(name_old)):
                renames[ext_file_dict["id"]] = str(name_new)
    if not renames:
        return

    def rename_if_matched(_name: str, obj: Any) -> None:
        if not isinstance(obj, h5py.Dataset):
            return
        object_id = obj.attrs.get("object_id")
        if isinstance(object_id, bytes):
            object_id = object_id.decode()
        if object_id in renames:
            obj[()] = renames[object_id]

    with h5py.File(nwbfile_path, "r+") as f:
        f.visititems(rename_if_matched)


@memoize_path_unless_dir(validate_cache)
def validate(path: str | Path, devel_debug: bool = False) -> list[ValidationResult]:
    """Run validation on a file and return errors

    In case of an exception being thrown, an error message added to the
    returned list of validation errors

    Parameters
    ----------
    path: str or Path
    """
    path = str(path)  # Might come in as pathlib's PATH
    errors: list[ValidationResult] = []

    # To overcome
    #   https://github.com/NeurodataWithoutBorders/pynwb/issues/1090
    #   https://github.com/NeurodataWithoutBorders/pynwb/issues/1091
    re_ok_prior_210 = re.compile(
        r"general/(experimenter|related_publications)\): "
        r"incorrect shape - expected an array of shape .\[None\]."
    )
    version = None
    try:
        version = get_nwb_version(path, sanitize=False)
    except Exception:
        # we just will not remove any errors, it is required so should be some
        pass
    else:
        if version is not None:
            # Explicitly sanitize so we collect warnings.
            nwb_errors: list[str] = []
            version = _sanitize_nwb_version(version, log=nwb_errors.append)
            for e in nwb_errors:
                errors.append(
                    ValidationResult(
                        origin=Origin(
                            type=OriginType.VALIDATION,
                            validator=Validator.dandi,
                            validator_version=__version__,
                        ),
                        severity=Severity.ERROR,
                        id="pynwb.GENERIC",
                        scope=Scope.FILE,
                        origin_result=e,
                        path=Path(path),
                        message=e,
                    )
                )
            # Do we really need this custom internal function? string comparison works fine.
            try:
                v = semantic_version.Version(version)
            except ValueError:
                v = None
            if v is not None and v < semantic_version.Version("2.1.0"):
                errors_ = errors[:]
                errors = [
                    e
                    for e in errors
                    if not re_ok_prior_210.search(cast(str, getattr(e, "message", "")))
                ]
                # This is not an error, just logging about the process, hence logging:
                if errors != errors_:
                    lgr.debug(
                        "Filtered out %d validation errors on %s",
                        len(errors_) - len(errors),
                        path,
                    )

    try:
        # Validates against the namespaces cached in the file; pynwb falls back
        # to its own namespaces if the file has none cached
        if is_nwb_zarr(path):
            # pynwb.validate(path=...) cannot open Zarr: it passes HDF5
            # arguments (driver, aws_region) to ZarrIO.load_namespaces() (as of
            # pynwb 4.2.0 and hdmf-zarr 0.14.0), and opens Zarr v2 with the
            # wrong class for hdmf-zarr >= 0.14, so give it an open io, for
            # which it also validates against the namespaces cached in the file.
            with open_nwb_zarr(path) as io:
                error_outputs = pynwb.validate(io=io)
        else:
            error_outputs = pynwb.validate(path=path)
    except Exception as exc:
        if devel_debug:
            raise
        errors.append(
            ValidationResult(
                origin=Origin(
                    type=OriginType.INTERNAL,
                    validator=Validator.pynwb,
                    validator_version=pynwb.__version__,
                ),
                severity=Severity.ERROR,
                id="pynwb.GENERIC",
                scope=Scope.FILE,
                origin_result=exc,
                path=Path(path),
                message=f"{exc}",
            )
        )
    else:
        for error in error_outputs:
            errors.append(
                ValidationResult(
                    origin=Origin(
                        type=OriginType.VALIDATION,
                        validator=Validator.pynwb,
                        validator_version=pynwb.__version__,
                        standard=Standard.NWB,
                        standard_version=version,
                    ),
                    severity=Severity.ERROR,
                    id=f"pynwb.{error}",
                    scope=Scope.FILE,
                    origin_result=error,
                    path=Path(path),
                    message=f"Failed to validate. {error.reason}",
                    within_asset_paths={path: error.location},
                )
            )

    return errors


# Many commands might be using load_namespaces but it causes HDMF to whine if there
# is no cached name spaces in the file.  It is benign but not really useful
# at this point, so we ignore it although ideally there should be a formal
# way to get relevant warnings (not errors) from PyNWB.  It is a bad manner
# to have this as a side effect of the importing this module, we should add/remove
# that filter in our top level commands
_ignored_benign_pynwb_warnings = False


def ignore_benign_pynwb_warnings() -> None:
    global _ignored_benign_pynwb_warnings
    if _ignored_benign_pynwb_warnings:
        return
    #   See https://github.com/dandi/dandi-cli/issues/14 for more info
    for s in (
        "No cached namespaces found .*",
        "ignoring namespace '.*' because it already exists",
    ):
        warnings.filterwarnings("ignore", s, UserWarning)
    # hdmf-zarr >= 0.14 warns about each of its fallbacks when zarr-python 3
    # cannot read parts of an NWB file stored as Zarr v2
    warnings.filterwarnings(
        "ignore", category=UserWarning, module="hdmf_zarr.backend_zarrv2"
    )
    _ignored_benign_pynwb_warnings = True


def get_object_id(path: str | Path | Readable) -> Any:
    """Read, if present an object_id

    if not available -- would simply raise a corresponding exception
    """
    if is_nwb_zarr(path):
        return _get_zarr_group_attrs(Path(path))["object_id"]
    with open_readable(path) as fp, h5py.File(fp, "r") as f:
        return f.attrs["object_id"]


StrPath = TypeVar("StrPath", str, Path)


def make_nwb_file(
    filename: StrPath, *args: Any, cache_spec: bool = False, **kwargs: Any
) -> StrPath:
    """A little helper to produce an .nwb file in the path using NWBFile

    If ``filename`` ends with ``.zarr``, the file is stored as Zarr (with
    hdmf-zarr), and otherwise as HDF5.

    Note: it doesn't cache_spec by default
    """
    nwbfile = pynwb.NWBFile(*args, **kwargs)
    io_class: type[HDMFIO]
    if str(filename).endswith(".zarr"):
        # Avoid heavy import by importing within function:
        from hdmf_zarr import NWBZarrIO

        io_class = NWBZarrIO
    else:
        io_class = pynwb.NWBHDF5IO
    with io_class(str(filename), mode="w") as io:
        io.write(nwbfile, cache_spec=cache_spec)
    return filename


def copy_nwb_file(src: str | Path, dest: str | Path) -> str:
    """ "Copy" .nwb file by opening and saving into a new path.

    New file (`dest`) then should have new `object_id` attribute, and thus be
    considered "different" although containing the same data

    Parameters
    ----------
    src: str
      Source file
    dest: str
      Destination file or directory. If points to an existing directory, file with
      the same name is created (exception if already exists).  If not an
      existing directory - target directory is created.

    Returns
    -------
    dest

    """
    if op.isdir(dest):
        dest = op.join(dest, op.basename(src))
    else:
        os.makedirs(op.dirname(dest), exist_ok=True)
    with pynwb.NWBHDF5IO(src, "r") as ior, pynwb.NWBHDF5IO(dest, "w") as iow:
        data = ior.read()
        data.generate_new_id()
        iow.export(
            ior,
            nwbfile=data,
            # keep the copy leaner by not caching the spec if the original
            # file did not have it cached either
            cache_spec=bool(pynwb.NWBHDF5IO.get_namespaces(src)),
        )
    return str(dest)


@memoize_path_unless_dir(metadata_cache)
def nwb_has_external_links(filepath: str | Path | Readable) -> bool:
    if is_nwb_zarr(filepath):
        # hdmf-zarr records the links of a group in its "_LINKS" attribute
        # ("zarr_link" before hdmf-zarr 0.14), with the path of the target's
        # file relative to the linking file, i.e. "." within the same file, as
        # their source
        return any(
            op.normpath(str(link.get("source", "."))) != "."
            for _, attrs in _walk_zarr_groups(Path(filepath))
            for link in (attrs.get("_LINKS") or attrs.get("zarr_link") or [])
        )
    with open_readable(filepath) as f, h5py.File(f, "r") as fp:
        visited = set()

        # cannot use `file.visititems` because it skips external links
        # (https://github.com/h5py/h5py/issues/671)
        def visit(path: str = "/") -> bool:
            if isinstance(fp[path], h5py.Group):
                for key in fp[path].keys():
                    key_path = path + "/" + key
                    if key_path not in visited:
                        visited.add(key_path)
                        if isinstance(
                            fp.get(key_path, getlink=True), h5py.ExternalLink
                        ) or visit(key_path):
                            return True
            elif isinstance(fp.get(path, getlink=True), h5py.ExternalLink):
                return True
            return False

        return visit()


def open_readable(r: str | Path | Readable) -> IO[bytes]:
    if isinstance(r, Readable):
        return r.open()
    else:
        return open(r, "rb")
