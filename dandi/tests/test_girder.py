import os.path

from keyring.backend import get_all_keyring
from keyring.backends import fail, null
from keyring.errors import KeyringError
from keyrings.alt import file as keyfile
import pytest

from ..exceptions import LockingError
from .. import girder


@pytest.fixture(scope="module", autouse=True)
def ensure_keyring_backends():
    # Ensure that keyring backends are initialized before running any tests, as
    # EncryptedKeyring cannot be initialized (on macOS, at least) while
    # pyfakefs is in effect.
    get_all_keyring()
    # This function caches its results, so it's safe to call if the backends
    # have already been initialized.
    # We need to call get_all_keyring() instead of init_backend() because the
    # latter's behavior can be affected by any keyring config files the user
    # happens to have.


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
    monkeypatch.delenv("DANDI_GIRDER_API_KEY", raising=False)
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
    monkeypatch.delenv("DANDI_GIRDER_API_KEY", raising=False)
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.null.Keyring")
    keyiter = iter(["badkey", local_docker_compose_env["api_key"]])
    inputmock = mocker.patch("dandi.girder.input", side_effect=lambda _: next(keyiter))
    girder.get_client(local_docker_compose_env["instance"].girder)
    msg = (
        "Please provide API Key (created/found in My Account/API keys "
        "in Girder) for {}: ".format(local_docker_compose_env["instance_id"])
    )
    assert inputmock.call_args_list == [mocker.call(msg), mocker.call(msg)]


def setup_keyringrc_no_password(fs):
    fs.create_file(
        girder.keyringrc_file(),
        contents="[backend]\ndefault-keyring = keyring.backends.null.Keyring\n",
    )


def setup_keyringrc_password(fs):
    fs.create_file(
        girder.keyringrc_file(),
        contents="[backend]\ndefault-keyring = keyrings.alt.file.PlaintextKeyring\n",
    )
    keyfile.PlaintextKeyring().set_password(
        "testservice", "testusername", "testpassword"
    )


def setup_keyringrc_fail(fs):
    fs.create_file(
        girder.keyringrc_file(),
        contents="[backend]\ndefault-keyring = keyring.backends.fail.Keyring\n",
    )


@pytest.mark.parametrize(
    "rcconfig",
    [None, setup_keyringrc_no_password, setup_keyringrc_password, setup_keyringrc_fail],
)
def test_keyring_lookup_envvar_no_password(fs, monkeypatch, rcconfig):
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.null.Keyring")
    if rcconfig is not None:
        rcconfig(fs)
    kb, password = girder.keyring_lookup("testservice", "testusername")
    assert isinstance(kb, null.Keyring)
    assert password is None


@pytest.mark.parametrize(
    "rcconfig", [None, setup_keyringrc_no_password, setup_keyringrc_fail]
)
def test_keyring_lookup_envvar_password(fs, monkeypatch, rcconfig):
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyrings.alt.file.PlaintextKeyring")
    keyfile.PlaintextKeyring().set_password(
        "testservice", "testusername", "testpassword"
    )
    if rcconfig is not None:
        rcconfig(fs)
    kb, password = girder.keyring_lookup("testservice", "testusername")
    assert isinstance(kb, keyfile.PlaintextKeyring)
    assert password == "testpassword"


@pytest.mark.parametrize(
    "rcconfig",
    [None, setup_keyringrc_no_password, setup_keyringrc_password, setup_keyringrc_fail],
)
def test_keyring_lookup_envvar_fail(fs, monkeypatch, rcconfig):
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.fail.Keyring")
    if rcconfig is not None:
        rcconfig(fs)
    with pytest.raises(KeyringError):
        girder.keyring_lookup("testservice", "testusername")


def test_keyring_lookup_rccfg_no_password(fs, monkeypatch):
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    setup_keyringrc_no_password(fs)
    kb, password = girder.keyring_lookup("testservice", "testusername")
    assert isinstance(kb, null.Keyring)
    assert password is None


def test_keyring_lookup_rccfg_password(fs, monkeypatch):
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    setup_keyringrc_password(fs)
    kb, password = girder.keyring_lookup("testservice", "testusername")
    assert isinstance(kb, keyfile.PlaintextKeyring)
    assert password == "testpassword"


def test_keyring_lookup_rccfg_fail(fs, monkeypatch):
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    setup_keyringrc_fail(fs)
    with pytest.raises(KeyringError):
        girder.keyring_lookup("testservice", "testusername")


def test_keyring_lookup_default_no_password(fs, mocker, monkeypatch):
    # Requesting the `fs` fixture (even if it's not directly used) should
    # guarantee that a keyringrc.cfg file on the real filesystem isn't found.
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    kb0 = null.Keyring()
    get_keyring = mocker.patch("dandi.girder.get_keyring", return_value=kb0)
    kb, password = girder.keyring_lookup("testservice", "testusername")
    assert kb is kb0
    assert password is None
    get_keyring.assert_called_once_with()


def test_keyring_lookup_default_password(fs, mocker, monkeypatch):
    # Requesting the `fs` fixture (even if it's not directly used) should
    # guarantee that a keyringrc.cfg file on the real filesystem isn't found
    # and that the PlaintextKeyring file is only created on the fake
    # filesystem.
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    kb0 = keyfile.PlaintextKeyring()
    kb0.set_password("testservice", "testusername", "testpassword")
    get_keyring = mocker.patch("dandi.girder.get_keyring", return_value=kb0)
    kb, password = girder.keyring_lookup("testservice", "testusername")
    assert kb is kb0
    assert password == "testpassword"
    get_keyring.assert_called_once_with()


class EncryptedFailure(fail.Keyring, keyfile.EncryptedKeyring):
    pass


def test_keyring_lookup_fail_default_encrypted(fs, mocker, monkeypatch):
    # Requesting the `fs` fixture (even if it's not directly used) should
    # guarantee that a keyringrc.cfg file on the real filesystem isn't found.
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    get_keyring = mocker.patch(
        "dandi.girder.get_keyring", return_value=EncryptedFailure()
    )
    with pytest.raises(KeyringError):
        girder.keyring_lookup("testservice", "testusername")
    get_keyring.assert_called_once_with()


def test_keyring_lookup_encrypted_fallback_exists_no_password(fs, mocker, monkeypatch):
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    get_keyring = mocker.patch("dandi.girder.get_keyring", return_value=fail.Keyring())
    fs.create_file(keyfile.EncryptedKeyring().file_path)
    kb, password = girder.keyring_lookup("testservice", "testusername")
    assert isinstance(kb, keyfile.EncryptedKeyring)
    assert password is None
    get_keyring.assert_called_once_with()


def test_keyring_lookup_encrypted_fallback_exists_password(fs, mocker, monkeypatch):
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    get_keyring = mocker.patch("dandi.girder.get_keyring", return_value=fail.Keyring())
    kb0 = keyfile.EncryptedKeyring()
    getpass = mocker.patch("getpass.getpass", return_value="file-password")
    kb0.set_password("testservice", "testusername", "testpassword")
    assert getpass.call_count == 2
    getpass.reset_mock()
    kb, password = girder.keyring_lookup("testservice", "testusername")
    assert getpass.call_count == 1
    assert isinstance(kb, keyfile.EncryptedKeyring)
    assert password == "testpassword"
    get_keyring.assert_called_once_with()


def test_keyring_lookup_encrypted_fallback_not_exists_no_create(
    fs, mocker, monkeypatch
):
    # Requesting the `fs` fixture (even if it's not directly used) should
    # guarantee that an encrypted keyring on the real filesystem isn't found.
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    get_keyring = mocker.patch("dandi.girder.get_keyring", return_value=fail.Keyring())
    confirm = mocker.patch("click.confirm", return_value=False)
    with pytest.raises(KeyringError):
        girder.keyring_lookup("testservice", "testusername")
    get_keyring.assert_called_once_with()
    confirm.assert_called_once_with(
        "Would you like to establish an encrypted keyring?", default=True
    )


def test_keyring_lookup_encrypted_fallback_not_exists_create_rcconf(
    fs, mocker, monkeypatch
):
    # Requesting the `fs` fixture (even if it's not directly used) should
    # guarantee that a fake filesystem is used.
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    get_keyring = mocker.patch("dandi.girder.get_keyring", return_value=fail.Keyring())
    confirm = mocker.patch("click.confirm", return_value=True)
    kb, password = girder.keyring_lookup("testservice", "testusername")
    assert isinstance(kb, keyfile.EncryptedKeyring)
    assert password is None
    get_keyring.assert_called_once_with()
    confirm.assert_called_once_with(
        "Would you like to establish an encrypted keyring?", default=True
    )
    assert os.path.exists(girder.keyringrc_file())
    with open(girder.keyringrc_file()) as fp:
        assert fp.read() == (
            "[backend]\ndefault-keyring = keyrings.alt.file.EncryptedKeyring\n"
        )


def test_keyring_lookup_encrypted_fallback_not_exists_create_rcconf_exists(
    fs, mocker, monkeypatch
):
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    get_keyring = mocker.patch("dandi.girder.get_keyring", return_value=fail.Keyring())
    confirm = mocker.patch("click.confirm", return_value=True)
    fs.create_file(girder.keyringrc_file(), contents="# placeholder\n")
    kb, password = girder.keyring_lookup("testservice", "testusername")
    assert isinstance(kb, keyfile.EncryptedKeyring)
    assert password is None
    get_keyring.assert_called_once_with()
    confirm.assert_called_once_with(
        "Would you like to establish an encrypted keyring?", default=True
    )
    with open(girder.keyringrc_file()) as fp:
        assert fp.read() == "# placeholder\n"
