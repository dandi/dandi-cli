from click.testing import CliRunner
import pytest

from ..command import ls


@pytest.mark.parametrize("format", ("auto", "json", "json_pp", "yaml", "pyout"))
def test_smoke(simple1_nwb, format):
    runner = CliRunner()
    result = runner.invoke(ls, ["-f", format, simple1_nwb])
    # import pdb; pdb.set_trace()
    assert result.exit_code == 0
    # we would need to redirect pyout for its analysis
    out = result.stdout
    # Something is off:
    #   When I run only test_smoke[yaml] -- there is out, otherwise it is empty
    return  # TODO - fix up
    if format.startswith("json"):
        import json

        assert json.loads(out)
    elif format == "yaml":
        print("OUT:", out)
        import yaml

        obj = yaml.load(out)
        assert obj
