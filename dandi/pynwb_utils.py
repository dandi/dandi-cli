from collections import Counter
import os
import os.path as op
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple, TypeVar, Union
import warnings

import dandischema
from fscacher import PersistentCache
import h5py
import hdmf
import pynwb
from pynwb import NWBHDF5IO
import semantic_version

from . import __version__, get_logger
from .consts import (
    VIDEO_FILE_EXTENSIONS,
    VIDEO_FILE_MODULES,
    metadata_nwb_computed_fields,
    metadata_nwb_file_fields,
    metadata_nwb_subject_fields,
)
from .utils import get_module_version, is_url

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


def _sanitize_nwb_version(v, filename=None, log=None):
    """Helper to sanitize the value of nwb_version where possible

    Would log a warning if something detected to be fishy"""
    msg = f"File {filename}: " if filename else ""
    msg += f"nwb_version {v!r}"

    if log is None:
        log = lgr.warning
    elif not log:

        def log(v: str) -> str:  # does nothing
            return v

    if isinstance(v, str):
        if v.startswith("NWB-"):
            v_ = v[4:]
            # should be semver since 2.1.0
            if not (v_.startswith("1.") or v_.startswith("2.0")):
                log(
                    f"{msg} starts with NWB- prefix, which is not part of the "
                    f"specification since NWB 2.1.0"
                )
            v = v_
    elif isinstance(v, int):
        log(f"{msg} is an integer whenever it should be text")
        v = str(v)
    elif v:
        log(f"{msg} is not text which follows semver specification")

    if isinstance(v, str) and not semantic_version.validate(v):
        log(f"error: {msg} is not a proper semantic version. See http://semver.org")

    return v


def get_nwb_version(filepath, sanitize=False):
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
    _sanitize = _sanitize_nwb_version if sanitize else lambda v: v

    with h5py.File(filepath, "r") as h5file:
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


def get_neurodata_types_to_modalities_map() -> Dict[str, str]:
    """Return a dict to map neurodata types known to pynwb to "modalities"

    It is an ugly hack, largely to check feasibility.
    It would base modality on the filename within pynwb providing that neural
    data type
    """
    import inspect

    ndtypes: Dict[str, str] = {}

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
                    print("Skipping %s coming from %s" % (v_, v_.__module__))
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


@metadata_cache.memoize_path
def get_neurodata_types(filepath: Union[str, Path]) -> List[str]:
    with h5py.File(filepath, "r") as h5file:
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


def _scan_neurodata_types(grp: h5py.File) -> List[Tuple[Any, Any]]:
    out = []
    if "neurodata_type" in grp.attrs:
        out.append((grp.attrs["neurodata_type"], grp.attrs.get("description", None)))
    for v in list(grp.values()):
        if isinstance(v, h5py._hl.group.Group):
            out += _scan_neurodata_types(v)
    return out


def _get_pynwb_metadata(path: Union[str, Path]) -> Dict[str, Any]:
    out = {}
    with NWBHDF5IO(path, "r", load_namespaces=True) as io:
        nwb = io.read()
        for key in metadata_nwb_file_fields:
            value = getattr(nwb, key)
            if isinstance(value, h5py.Dataset):
                # serialize into a basic container (list), since otherwise
                # it would be a closed Dataset upon return
                value = list(value)
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
                    "ATM can only compute number_of_ fields. Got {}".format(f)
                )
            key = f[len("number_of_") :]
            out[f] = len(getattr(nwb, key, []) or [])

        # get external_file data:
        out["external_file_objects"] = _get_image_series(nwb)

    return out


def _get_image_series(nwb: pynwb.NWBFile) -> List[dict]:
    """Retrieves all ImageSeries related metadata from an open nwb file.

    Specifically it pulls out the ImageSeries uuid, name and all the
    externally linked files named under the argument 'external_file'.

    Parameters
    ----------
    nwb: pynwb.NWBFile

    Returns
    -------
    out: List[dict]
        list of dicts : [{id: <ImageSeries uuid>, name: <IMageSeries name>,
        external_files=[ImageSeries.external_file]}]
        if no ImageSeries found in the given modules to check, then it returns an empty list.
    """
    out = []
    for module_name in VIDEO_FILE_MODULES:
        module_cont = getattr(nwb, module_name)
        for name, ob in module_cont.items():
            if isinstance(ob, pynwb.image.ImageSeries) and ob.external_file is not None:
                out_dict = dict(id=ob.object_id, name=ob.name, external_files=[])
                for ext_file in ob.external_file:
                    if Path(ext_file).suffix in VIDEO_FILE_EXTENSIONS:
                        out_dict["external_files"].append(Path(ext_file))
                    else:
                        lgr.warning(
                            "external file %s should be one of: %s",
                            ext_file,
                            ", ".join(VIDEO_FILE_EXTENSIONS),
                        )
                out.append(out_dict)
    return out


def rename_nwb_external_files(metadata: List[dict], dandiset_path: str) -> None:
    """Renames the external_file attribute in an ImageSeries datatype in an open nwb file.

    It pulls information about the ImageSeries objects from metadata:
    metadata["external_file_objects"] populated during _get_pynwb_metadata() call.

    Parameters
    ----------
    metadata: List[dict]
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
        with NWBHDF5IO(dandiset_nwbfile_path, mode="r+", load_namespaces=True) as io:
            nwb = io.read()
            for ext_file_dict in meta["external_file_objects"]:
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
                    if not is_url(str(name_old)):
                        container.external_file[no] = str(name_new)


@validate_cache.memoize_path
def validate(path: Union[str, Path], devel_debug: bool = False) -> List[str]:
    """Run validation on a file and return errors

    In case of an exception being thrown, an error message added to the
    returned list of validation errors

    Parameters
    ----------
    path: str or Path
    """
    path = str(path)  # Might come in as pathlib's PATH
    errors: List[str]
    try:
        with pynwb.NWBHDF5IO(path, "r", load_namespaces=True) as reader:
            errors = pynwb.validate(reader)
        lgr.warning(
            "pynwb validation errors for %s: %s",
            path,
            errors,
            extra={"validating": True},
        )
    except Exception as exc:
        if devel_debug:
            raise
        lgr.warning("Failed to validate %s: %s", path, exc, extra={"validating": True})
        errors = [f"Failed to validate {path}: {exc}"]

    # To overcome
    #   https://github.com/NeurodataWithoutBorders/pynwb/issues/1090
    #   https://github.com/NeurodataWithoutBorders/pynwb/issues/1091
    re_ok_prior_210 = re.compile(
        r"general/(experimenter|related_publications)\): "
        r"incorrect shape - expected an array of shape .\[None\]."
    )
    try:
        version = get_nwb_version(path, sanitize=False)
    except Exception:
        # we just will not remove any errors, it is required so should be some
        pass
    else:
        if version is not None:
            # Explicitly sanitize so we collect warnings.
            # TODO: later cast into proper ERRORs
            version = _sanitize_nwb_version(version, log=errors.append)
            try:
                v = semantic_version.Version(version)
            except ValueError:
                v = None
            if v is not None and v < semantic_version.Version("2.1.0"):
                errors_ = errors[:]
                errors = [e for e in errors if not re_ok_prior_210.search(str(e))]
                if errors != errors_:
                    lgr.debug(
                        "Filtered out %d validation errors on %s",
                        len(errors_) - len(errors),
                        path,
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
    _ignored_benign_pynwb_warnings = True


def get_object_id(path: Union[str, Path]) -> Any:
    """Read, if present an object_id

    if not available -- would simply raise a corresponding exception
    """
    with h5py.File(path, "r") as f:
        return f.attrs["object_id"]


StrPath = TypeVar("StrPath", str, Path)


def make_nwb_file(
    filename: StrPath, *args: Any, cache_spec: bool = False, **kwargs: Any
) -> StrPath:
    """A little helper to produce an .nwb file in the path using NWBFile

    Note: it doesn't cache_spec by default
    """
    nwbfile = pynwb.NWBFile(*args, **kwargs)
    with pynwb.NWBHDF5IO(filename, "w") as io:
        io.write(nwbfile, cache_spec=cache_spec)
    return filename


def copy_nwb_file(src: Union[str, Path], dest: Union[str, Path]) -> str:
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
        iow.export(ior, nwbfile=data)
    return str(dest)


@metadata_cache.memoize_path
def nwb_has_external_links(filepath: Union[str, Path]) -> bool:
    with h5py.File(filepath, "r") as fp:
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
