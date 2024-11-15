import os

from click.testing import CliRunner

from ..cmd_instances import instances


def test_cmd_instances(monkeypatch):
    instancehost = os.environ.get("DANDI_INSTANCEHOST", "localhost")
    r = CliRunner().invoke(instances, [])
    assert r.exit_code == 0
    assert r.output == (
        "dandi:\n"
        "  api: https://api.dandiarchive.org/api\n"
        "  gui: https://dandiarchive.org\n"
        "dandi-api-local-docker-tests:\n"
        f"  api: http://{instancehost}:8000/api\n"
        f"  gui: http://{instancehost}:8085\n"
        "dandi-staging:\n"
        "  api: https://api-staging.dandiarchive.org/api\n"
        "  gui: https://gui-staging.dandiarchive.org\n"
        "linc:\n"
        "  api: https://api.lincbrain.org/api\n"
        "  gui: https://lincbrain.org\n"
        "linc-staging:\n"
        "  api: https://staging-api.lincbrain.org/api\n"
        "  gui: https://staging.lincbrain.org\n"
    )
