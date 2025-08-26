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
        "dandi-sandbox:\n"
        "  api: https://api.sandbox.dandiarchive.org/api\n"
        "  gui: https://sandbox.dandiarchive.org\n"
        "dandi-staging:\n"
        "  api: https://api.sandbox.dandiarchive.org/api\n"
        "  gui: https://sandbox.dandiarchive.org\n"
        "ember:\n"
        "  api: https://api-dandi.emberarchive.org/api\n"
        "  gui: https://dandi.emberarchive.org\n"
        "ember-sandbox:\n"
        "  api: https://api-dandi-sandbox.emberarchive.org/api\n"
        "  gui: https://apl-setup--ember-dandi-archive.netlify.app/\n"
        "linc:\n"
        "  api: https://api.lincbrain.org/api\n"
        "  gui: https://lincbrain.org\n"
        "linc-staging:\n"
        "  api: https://staging-api.lincbrain.org/api\n"
        "  gui: https://staging.lincbrain.org\n"
    )
