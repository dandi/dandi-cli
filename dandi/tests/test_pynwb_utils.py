from datetime import datetime, timezone
import re
from typing import Any, Callable, NoReturn

import numpy as np
from pynwb import NWBHDF5IO, NWBFile, TimeSeries

from ..pynwb_utils import _sanitize_nwb_version, nwb_has_external_links


def test_pynwb_io(simple1_nwb: str) -> None:
    # To verify that our dependencies spec is sufficient to avoid
    # stepping into known pynwb/hdmf issues
    with NWBHDF5IO(str(simple1_nwb), "r", load_namespaces=True) as reader:
        nwbfile = reader.read()
    assert repr(nwbfile)
    assert str(nwbfile)


def test_sanitize_nwb_version() -> None:
    def _nocall(*args: Any) -> NoReturn:
        raise AssertionError(f"Should have not been called. Was called with {args}")

    def assert_regex(regex: str) -> Callable[[str], None]:
        def search(v: str) -> None:
            assert re.search(regex, v)

        return search

    assert _sanitize_nwb_version("1.0.0", log=_nocall) == "1.0.0"
    assert _sanitize_nwb_version("NWB-1.0.0", log=_nocall) == "1.0.0"
    assert _sanitize_nwb_version("NWB-2.0.0", log=_nocall) == "2.0.0"
    assert (
        _sanitize_nwb_version(
            "NWB-2.1.0",
            log=assert_regex("^nwb_version 'NWB-2.1.0' starts with NWB- prefix,"),
        )
        == "2.1.0"
    )
    assert (
        _sanitize_nwb_version(
            "NWB-2.1.0",
            filename="/bu",
            log=assert_regex(
                "^File /bu: nwb_version 'NWB-2.1.0' starts with NWB- prefix,"
            ),
        )
        == "2.1.0"
    )


def test_nwb_has_external_links(tmp_path):
    # Create the base data
    start_time = datetime(2017, 4, 3, 11, tzinfo=timezone.utc)
    create_date = datetime(2017, 4, 15, 12, tzinfo=timezone.utc)
    data = np.arange(1000).reshape((100, 10))
    timestamps = np.arange(100)
    filename1 = tmp_path / "external1_example.nwb"
    filename4 = tmp_path / "external_linkdataset_example.nwb"

    # Create the first file
    nwbfile1 = NWBFile(
        session_description="demonstrate external files",
        identifier="NWBE1",
        session_start_time=start_time,
        file_create_date=create_date,
    )
    test_ts1 = TimeSeries(
        name="test_timeseries1", data=data, unit="SIunit", timestamps=timestamps
    )
    nwbfile1.add_acquisition(test_ts1)
    # Write the first file
    with NWBHDF5IO(filename1, "w") as io:
        io.write(nwbfile1)

    nwbfile4 = NWBFile(
        session_description="demonstrate external files",
        identifier="NWBE4",
        session_start_time=start_time,
        file_create_date=create_date,
    )

    # Get the first timeseries
    with NWBHDF5IO(filename1, "r") as io1:
        nwbfile1 = io1.read()
        timeseries_1_data = nwbfile1.get_acquisition("test_timeseries1").data

        # Create a new timeseries that links to our data
        test_ts4 = TimeSeries(
            name="test_timeseries4",
            data=timeseries_1_data,  # <-------
            unit="SIunit",
            timestamps=timestamps,
        )
        nwbfile4.add_acquisition(test_ts4)

        with NWBHDF5IO(filename4, "w") as io4:
            io4.write(nwbfile4, link_data=True)

    assert not nwb_has_external_links(filename1)
    assert nwb_has_external_links(filename4)
