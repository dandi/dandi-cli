"""Write ``ecephys_v2.nwb.zarr``, an NWB file stored as Zarr v2, for the tests

It must be run with hdmf-zarr < 0.14 (and thus zarr-python 2, e.g. on Python
3.11), which writes Zarr v2, as all NWB files stored as Zarr were before
hdmf-zarr 0.14: hdmf-zarr >= 0.14, which the tests need, writes only Zarr v3.
Hence the tests cannot write it themselves, but read it from where the
``DANDI_TESTS_NWB_ZARR_V2`` environment variable says (as CI does, caching
it), and skip the tests needing it without it::

    python -m venv /tmp/hdmf-zarr-0.13
    /tmp/hdmf-zarr-0.13/bin/pip install "hdmf-zarr >= 0.13, < 0.14"
    /tmp/hdmf-zarr-0.13/bin/python dandi/tests/data/nwb_zarr/make_ecephys_v2.py /tmp
    DANDI_TESTS_NWB_ZARR_V2=/tmp/ecephys_v2.nwb.zarr pytest ...

Its electrodes table has a ``group`` column, which hdmf-zarr < 0.14 stores
with the pickle codec.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import numpy as np
import pynwb
from pynwb.ecephys import ElectricalSeries
from pynwb.file import Subject


def make_nwbfile() -> pynwb.NWBFile:
    nwbfile = pynwb.NWBFile(
        session_description="An ecephys session",
        identifier="5d0b7cd8-5b44-4f71-b0d5-ec0e5f4a2b0a",
        session_start_time=datetime(2020, 1, 1, 12, tzinfo=timezone.utc),
        session_id="session1",
        experimenter=["Doe, Jane"],
        keywords=["ecephys", "zarr"],
        institution="An institution",
        lab="A lab",
        subject=Subject(
            subject_id="mouse001",
            species="Mus musculus",
            sex="F",
            age="P30D",
        ),
    )
    device = nwbfile.create_device(name="probe")
    group = nwbfile.create_electrode_group(
        name="shank0", description="A shank", location="CA1", device=device
    )
    for _ in range(3):
        nwbfile.add_electrode(location="CA1", group=group)
    nwbfile.add_acquisition(
        ElectricalSeries(
            name="ElectricalSeries",
            data=np.zeros((20, 3), dtype="int16"),
            electrodes=nwbfile.create_electrode_table_region([0, 1, 2], "all"),
            rate=10.0,
        )
    )
    nwbfile.add_trial(start_time=0.0, stop_time=1.0)
    nwbfile.add_trial(start_time=1.0, stop_time=2.0)
    nwbfile.add_unit(spike_times=[0.1, 0.5, 1.5])
    nwbfile.add_unit(spike_times=[0.2, 1.9])
    return nwbfile


def main() -> None:
    from hdmf_zarr import NWBZarrIO

    with NWBZarrIO(str(Path(sys.argv[1], "ecephys_v2.nwb.zarr")), mode="w") as io:
        io.write(make_nwbfile(), cache_spec=True)


if __name__ == "__main__":
    main()
