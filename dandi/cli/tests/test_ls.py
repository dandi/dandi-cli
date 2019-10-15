from click.testing import CliRunner
import pytest

from ..command import ls
from ...pynwb_utils import metadata_fields


@pytest.mark.parametrize("format", ("auto", "json", "json_pp", "yaml", "pyout"))
def test_smoke(simple1_nwb_metadata, simple1_nwb, format):
    runner = CliRunner()
    r = runner.invoke(ls, ["-f", format, simple1_nwb])
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    # we would need to redirect pyout for its analysis
    out = r.stdout

    if format.startswith("json"):
        import json

        load = json.loads
    elif format == "yaml":
        import yaml

        def load(s):
            obj = yaml.load(s, Loader=yaml.BaseLoader)
            assert len(obj) == 1  # will be a list with a single elem
            return obj[0]

    else:
        return

    metadata = load(out)
    assert metadata
    # check a few fields
    assert metadata.pop("nwb_version").startswith("2.")
    for f in ["session_id", "experiment_description"]:
        assert metadata[f] == simple1_nwb_metadata[f]
