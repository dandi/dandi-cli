import os

from click.testing import CliRunner

from ..command import instances


def test_cmd_instances(monkeypatch):
    redirector_base = os.environ.get(
        "DANDI_REDIRECTOR_BASE", "https://dandiarchive.org"
    )
    instancehost = os.environ.get("DANDI_INSTANCEHOST", "localhost")
    r = CliRunner().invoke(instances, [])
    assert r.exit_code == 0
    assert r.output == (
        "dandi:\n"
        "  api: https://api.dandiarchive.org/api\n"
        "  gui: https://gui.dandiarchive.org\n"
        f"  redirector: {redirector_base}\n"
        "dandi-api-local-docker-tests:\n"
        f"  api: http://{instancehost}:8000/api\n"
        f"  gui: http://{instancehost}:8085\n"
        "  redirector: null\n"
        "dandi-devel:\n"
        "  api: null\n"
        "  gui: https://gui-beta-dandiarchive-org.netlify.app\n"
        "  redirector: null\n"
        "dandi-staging:\n"
        "  api: https://api-staging.dandiarchive.org/api\n"
        "  gui: https://gui-staging.dandiarchive.org\n"
        "  redirector: null\n"
    )
