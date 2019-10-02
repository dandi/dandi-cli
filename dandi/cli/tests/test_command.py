from ..command import (
    ls,
    validate,
)

from click.testing import CliRunner
import pytest


@pytest.mark.parametrize("command", (ls, validate))
def test_smoke(simple1_nwb, command):
    runner = CliRunner()
    result = runner.invoke(command, [simple1_nwb])
    assert result.exit_code == 0
    # we would need to redirect pyout for its analysis

    # empty invocation should not crash
    result = runner.invoke(command, [])
    assert result.exit_code == 0
