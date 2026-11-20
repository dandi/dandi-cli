"""NWB files stored as Zarr (:file:`*.nwb.zarr` directories)"""

from __future__ import annotations

from dandischema.models import BareAsset
from packaging.version import Version

from dandi import get_logger
from dandi.consts import ZARR_MIME_TYPE
from dandi.misctypes import Digest

from .bases import (
    _get_nwb_asset_metadata,
    _get_nwb_inspector_version,
    _get_nwb_validation_errors,
)
from .zarr import ZarrAsset, get_zarr_format_version
from ..validate._types import (
    ORIGIN_VALIDATION_DANDI_ZARR,
    MissingFileContent,
    Scope,
    Severity,
    ValidationResult,
)

lgr = get_logger()


class NWBZarrAsset(ZarrAsset):
    """
    Representation of a local NWB file stored as Zarr (a :file:`*.nwb.zarr`
    directory): a Zarr asset whose metadata is extracted from the NWB file,
    which is validated as well

    Reading its NWB content requires hdmf-zarr >= 0.14, and thus Python >=
    3.12: the optional ``nwb-zarr`` dependency.
    """

    def get_metadata(
        self,
        digest: Digest | None = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        metadata = _get_nwb_asset_metadata(self, digest, ignore_errors)
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
        Validate the Zarr as any Zarr asset is (along with the asset's
        metadata), and the NWB file it stores as
        `NWBAsset.get_validation_errors()` does
        """
        return super().get_validation_errors(
            schema_version=schema_version,
            devel_debug=devel_debug,
            missing_file_content=missing_file_content,
        ) + self._get_nwb_errors(
            schema_version=schema_version,
            devel_debug=devel_debug,
            missing_file_content=missing_file_content,
        )

    def _get_nwb_errors(
        self,
        schema_version: str | None,
        devel_debug: bool,
        missing_file_content: MissingFileContent | None,
    ) -> list[ValidationResult]:
        """Validate the NWB file, but not the asset's metadata, which
        `ZarrAsset.get_validation_errors()` validates"""
        # Avoid heavy import by importing within function:
        from dandi.pynwb_utils import get_nwb_zarr_reading_problem

        if missing_file_content == MissingFileContent.only_non_data:
            # Only the path layout is validated
            return _get_nwb_validation_errors(
                self,
                schema_version,
                devel_debug,
                missing_file_content,
                validate_metadata=False,
            )
        if problem := get_nwb_zarr_reading_problem(self.filepath):
            # Not validating the NWB content at all, rather than with an error
            # from each validator failing to read it, but still its path
            return [
                ValidationResult(
                    origin=ORIGIN_VALIDATION_DANDI_ZARR,
                    severity=Severity.ERROR,
                    id="dandi_zarr.nwb_unreadable",
                    scope=Scope.FILE,
                    path=self.filepath,
                    message=f"Cannot validate NWB file stored as Zarr: {problem}",
                )
            ] + _get_nwb_validation_errors(
                self,
                schema_version,
                devel_debug,
                missing_file_content=MissingFileContent.only_non_data,
                validate_metadata=False,
            )
        return _get_nwb_validation_errors(
            self,
            schema_version=schema_version,
            devel_debug=devel_debug,
            missing_file_content=missing_file_content,
            # NWB Inspector runs only without a schema_version
            nwbinspector_ignore=(
                self._get_nwbinspector_ignore() if schema_version is None else None
            ),
            validate_metadata=False,
        )

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
