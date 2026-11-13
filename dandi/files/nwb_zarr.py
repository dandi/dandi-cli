"""NWB files stored as Zarr (:file:`*.nwb.zarr` directories)"""

from __future__ import annotations

from collections.abc import Iterator
import traceback
from typing import Any

from dandischema.models import BareAsset
from packaging.version import Version

from dandi import get_logger
from dandi.consts import ZARR_MIME_TYPE
from dandi.misctypes import Digest

from .bases import NWBMixin, _get_nwb_inspector_version
from .zarr import ZarrAsset, get_zarr_format_version
from ..validate._types import (
    ORIGIN_VALIDATION_DANDI_ZARR,
    MissingFileContent,
    Scope,
    Severity,
    ValidationResult,
)

lgr = get_logger()


class NWBZarrAsset(NWBMixin, ZarrAsset):
    """
    Representation of a local NWB file stored as Zarr (a :file:`*.nwb.zarr`
    directory): a Zarr asset whose metadata is extracted from the NWB file,
    which is validated as well, as for any NWB file (`NWBMixin`)

    Reading its NWB content requires hdmf-zarr >= 0.14, and thus Python >=
    3.12: the optional ``nwb-zarr`` dependency.
    """

    def get_metadata(
        self,
        digest: Digest | None = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        metadata = super().get_metadata(digest, ignore_errors)
        # As for any Zarr asset; dataStandard says it is NWB
        metadata.encodingFormat = ZARR_MIME_TYPE
        return metadata

    def get_validation_errors(
        self,
        schema_version: str | None = None,
        devel_debug: bool = False,
        missing_file_content: MissingFileContent | None = None,
    ) -> list[ValidationResult]:
        """
        Validate the NWB file as any NWB file is (`NWBMixin`), and the Zarr as
        any Zarr asset is, along with the asset's metadata
        """
        # Avoid heavy import by importing within function:
        from dandi.pynwb_utils import get_nwb_zarr_reading_problem

        kwargs: dict[str, Any] = {
            "schema_version": schema_version,
            "devel_debug": devel_debug,
        }
        content = missing_file_content != MissingFileContent.only_non_data
        if content and (problem := get_nwb_zarr_reading_problem(self.filepath)):
            # Not validating the NWB content at all, rather than with an error
            # from each validator failing to read it, but still its path
            return (
                ZarrAsset.get_validation_errors(
                    self, missing_file_content=missing_file_content, **kwargs
                )
                + [
                    ValidationResult(
                        origin=ORIGIN_VALIDATION_DANDI_ZARR,
                        severity=Severity.ERROR,
                        id="dandi_zarr.nwb_unreadable",
                        scope=Scope.FILE,
                        path=self.filepath,
                        message=f"Cannot validate NWB file stored as Zarr: {problem}",
                    )
                ]
                + super().get_validation_errors(
                    missing_file_content=MissingFileContent.only_non_data, **kwargs
                )
            )
        errors = super().get_validation_errors(
            missing_file_content=missing_file_content, **kwargs
        )
        if schema_version is None or not content:
            # Only with a schema_version, and the content, does NWBMixin
            # validate the asset as its other base class, ZarrAsset, does
            errors = (
                ZarrAsset.get_validation_errors(
                    self, missing_file_content=missing_file_content, **kwargs
                )
                + errors
            )
        return errors

    def _inspect_nwbfile(self) -> Iterator[Any]:
        """
        Inspect the NWB file with NWB Inspector, as `NWBMixin` does, but
        reading it with `open_nwb_zarr()`: nwbinspector opens Zarr with
        NWBZarrIO, which reads only Zarr v3 as of hdmf-zarr 0.14 (Zarr v2
        needs NWBZarrV2IO)
        """
        # Avoid heavy import by importing within function:
        from nwbinspector import (
            Importance,
            InspectorMessage,
            inspect_nwbfile_object,
            load_config,
        )

        # Avoid heavy import by importing within function:
        from dandi.pynwb_utils import open_nwb_zarr

        def read_error(e: Exception) -> InspectorMessage:
            # As inspect_nwbfile() reports it
            return InspectorMessage(
                message=traceback.format_exc(),
                importance=Importance.ERROR,
                check_function_name=(
                    "During io.read(), an error occurred: "
                    f"{type(e).__module__}.{type(e).__name__}. This indicates "
                    "that PyNWB was unable to read the file. See the traceback "
                    "message for more details."
                ),
                file_path=str(self.filepath),
            )

        try:
            io = open_nwb_zarr(self.filepath)
        except Exception as e:
            yield read_error(e)
            return
        with io:
            try:
                nwbfile = io.read()
            except Exception as e:
                yield read_error(e)
                return
            for message in inspect_nwbfile_object(
                nwbfile_object=nwbfile,
                config=load_config(filepath_or_keyword="dandi"),
                ignore=self._get_nwbinspector_ignore(),
                importance_threshold=Importance.BEST_PRACTICE_VIOLATION,
            ):
                # As inspect_nwbfile() sets it
                message.file_path = str(self.filepath)
                yield message

    def _get_nwbinspector_ignore(self) -> list[str] | None:
        """Names of NWB Inspector checks which crash on this file, which would
        be reported as an ERROR"""
        # Stop ignoring it once nwbinspector > 0.7.2 is required
        if (
            _get_nwb_inspector_version() > Version("0.7.2")
            or get_zarr_format_version(self.filepath) != "3"
        ):
            return None
        # check_large_dataset_compression crashes on Zarr v3 arrays (`compressor`
        # is not available for Zarr format 3 arrays); fixed by
        # https://github.com/NeurodataWithoutBorders/nwbinspector/pull/767
        ignore = ["check_large_dataset_compression"]
        lgr.debug(
            "%s: not running NWB Inspector's %s, which nwbinspector %s cannot run on"
            " Zarr v3",
            self.filepath,
            ", ".join(ignore),
            _get_nwb_inspector_version(),
        )
        return ignore
