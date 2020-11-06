from base64 import b64encode
from keyring.backends import null
from keyrings.alt import file as keyfile

import pytest
from ..exceptions import LockingError
from .. import girder


def test_lock_dandiset(local_docker_compose_env):
    DANDISET_ID = "000001"
    client = girder.get_client(local_docker_compose_env["instance"].girder)
    resp = client.get(f"dandi/{DANDISET_ID}/lock/owner")
    assert resp is None
    with client.lock_dandiset(DANDISET_ID):
        resp = client.get(f"dandi/{DANDISET_ID}/lock/owner")
        assert resp is not None
    resp = client.get(f"dandi/{DANDISET_ID}/lock/owner")
    assert resp is None


def test_lock_dandiset_error_on_nest(local_docker_compose_env):
    DANDISET_ID = "000001"
    client = girder.get_client(local_docker_compose_env["instance"].girder)
    with client.lock_dandiset(DANDISET_ID):
        with pytest.raises(LockingError) as excinfo:
            with client.lock_dandiset(DANDISET_ID):
                raise AssertionError("This shouldn't be reached")  # pragma: no cover
        assert (
            str(excinfo.value) == f"Failed to lock dandiset {DANDISET_ID} due to: "
            f"Dandiset {DANDISET_ID} is currently locked by admin admin"
        )


def test_lock_dandiset_unlock_within(local_docker_compose_env):
    DANDISET_ID = "000001"
    client = girder.get_client(local_docker_compose_env["instance"].girder)
    unlocked = False
    with pytest.raises(LockingError) as excinfo:
        with client.lock_dandiset(DANDISET_ID):
            client.post(f"dandi/{DANDISET_ID}/unlock")
            unlocked = True
    assert unlocked
    assert (
        str(excinfo.value) == f"Failed to unlock dandiset {DANDISET_ID} due to: "
        f"Dandiset {DANDISET_ID} is currently unlocked"
    )


def test_dandi_authenticate_no_env_var(local_docker_compose_env, monkeypatch, mocker):
    monkeypatch.delenv("DANDI_API_KEY", raising=False)
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.null.Keyring")
    inputmock = mocker.patch(
        "dandi.girder.input", return_value=local_docker_compose_env["api_key"]
    )
    girder.get_client(local_docker_compose_env["instance"].girder)
    inputmock.assert_called_once_with(
        "Please provide API Key (created/found in My Account/API keys "
        "in Girder) for {}: ".format(local_docker_compose_env["instance_id"])
    )


def test_dandi_authenticate_no_env_var_ask_twice(
    local_docker_compose_env, monkeypatch, mocker
):
    monkeypatch.delenv("DANDI_API_KEY", raising=False)
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.null.Keyring")
    keyiter = iter(["badkey", local_docker_compose_env["api_key"]])
    inputmock = mocker.patch("dandi.girder.input", side_effect=lambda _: next(keyiter))
    girder.get_client(local_docker_compose_env["instance"].girder)
    msg = (
        "Please provide API Key (created/found in My Account/API keys "
        "in Girder) for {}: ".format(local_docker_compose_env["instance_id"])
    )
    assert inputmock.call_args_list == [mocker.call(msg), mocker.call(msg)]


def test_keyring_lookup_envvar_no_password(monkeypatch):
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.null.Keyring")
    kb, password = girder.keyring_lookup("test-service", "test-username")
    assert isinstance(kb, null.Keyring)
    assert password is None


def test_keyring_lookup_envvar_password(fs, monkeypatch):
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyrings.alt.file.PlaintextKeyring")
    fs.create_file(
        keyfile.PlaintextKeyring().file_path,
        contents=f"[testservice]\ntestusername = {b64encode(b'testpassword').decode()}\n",
    )
    kb, password = girder.keyring_lookup("testservice", "testusername")
    assert isinstance(kb, keyfile.PlaintextKeyring)
    assert password == "testpassword"
