from ..command import ls

from click.testing import CliRunner


def test_ls_smoke(simple1_nwb):
    runner = CliRunner()
    result = runner.invoke(ls, [simple1_nwb])
    assert result.exit_code == 0
    # we would need to redirect pyout for its analysis

    # empty invocation should not crash
    result = runner.invoke(ls, [])
    assert result.exit_code == 0
