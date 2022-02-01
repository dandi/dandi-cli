from pathlib import Path
from typing import Callable, Optional

from keyring.backend import get_all_keyring
from keyring.backends import fail, null
from keyring.errors import KeyringError
from keyrings.alt import file as keyfile
import pytest
from pytest_mock import MockerFixture

from .fixtures import DandiAPI
from ..dandiapi import DandiAPIClient
from ..keyring import keyring_lookup, keyringrc_file


@pytest.fixture(scope="module", autouse=True)
def ensure_keyring_backends() -> None:
    # Ensure that keyring backends are initialized before running any tests
    get_all_keyring()
    # This function caches its results, so it's safe to call if the backends
    # have already been initialized.
    # We need to call get_all_keyring() instead of init_backend() because the
    # latter's behavior can be affected by any keyring config files the user
    # happens to have.


def test_dandi_authenticate_no_env_var(
    local_dandi_api: DandiAPI, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.delenv("DANDI_API_KEY", raising=False)
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.null.Keyring")
    inputmock = mocker.patch(
        "dandi.dandiapi.input", return_value=local_dandi_api.api_key
    )
    DandiAPIClient(local_dandi_api.api_url).dandi_authenticate()
    inputmock.assert_called_once_with(
        "Please provide API Key for {}: ".format(local_dandi_api.instance_id)
    )


def setup_keyringrc_no_password() -> None:
    rc = keyringrc_file()
    rc.parent.mkdir(parents=True, exist_ok=True)
    rc.write_text("[backend]\ndefault-keyring = keyring.backends.null.Keyring\n")


def setup_keyringrc_password():
    rc = keyringrc_file()
    rc.parent.mkdir(parents=True, exist_ok=True)
    rc.write_text("[backend]\ndefault-keyring = keyrings.alt.file.PlaintextKeyring\n")
    keyfile.PlaintextKeyring().set_password(
        "testservice", "testusername", "testpassword"
    )


def setup_keyringrc_fail() -> None:
    rc = keyringrc_file()
    rc.parent.mkdir(parents=True, exist_ok=True)
    rc.write_text("[backend]\ndefault-keyring = keyring.backends.fail.Keyring\n")


@pytest.mark.parametrize(
    "rcconfig",
    [None, setup_keyringrc_no_password, setup_keyringrc_password, setup_keyringrc_fail],
)
@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_envvar_no_password(
    monkeypatch: pytest.MonkeyPatch,
    rcconfig: Optional[Callable[[], None]],
) -> None:
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.null.Keyring")
    if rcconfig is not None:
        rcconfig()
    kb, password = keyring_lookup("testservice", "testusername")
    assert isinstance(kb, null.Keyring)
    assert password is None


@pytest.mark.parametrize(
    "rcconfig", [None, setup_keyringrc_no_password, setup_keyringrc_fail]
)
@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_envvar_password(
    monkeypatch: pytest.MonkeyPatch,
    rcconfig: Optional[Callable[[], None]],
) -> None:
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyrings.alt.file.PlaintextKeyring")
    keyfile.PlaintextKeyring().set_password(
        "testservice", "testusername", "testpassword"
    )
    if rcconfig is not None:
        rcconfig()
    kb, password = keyring_lookup("testservice", "testusername")
    assert isinstance(kb, keyfile.PlaintextKeyring)
    assert password == "testpassword"


@pytest.mark.parametrize(
    "rcconfig",
    [None, setup_keyringrc_no_password, setup_keyringrc_password, setup_keyringrc_fail],
)
@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_envvar_fail(
    monkeypatch: pytest.MonkeyPatch,
    rcconfig: Optional[Callable[[], None]],
) -> None:
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.fail.Keyring")
    if rcconfig is not None:
        rcconfig()
    with pytest.raises(KeyringError):
        keyring_lookup("testservice", "testusername")


@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_rccfg_no_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    setup_keyringrc_no_password()
    kb, password = keyring_lookup("testservice", "testusername")
    assert isinstance(kb, null.Keyring)
    assert password is None


@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_rccfg_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    setup_keyringrc_password()
    kb, password = keyring_lookup("testservice", "testusername")
    assert isinstance(kb, keyfile.PlaintextKeyring)
    assert password == "testpassword"


@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_rccfg_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    setup_keyringrc_fail()
    with pytest.raises(KeyringError):
        keyring_lookup("testservice", "testusername")


@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_default_no_password(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    kb0 = null.Keyring()
    get_keyring = mocker.patch("dandi.keyring.get_keyring", return_value=kb0)
    kb, password = keyring_lookup("testservice", "testusername")
    assert kb is kb0
    assert password is None
    get_keyring.assert_called_once_with()


@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_default_password(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    kb0 = keyfile.PlaintextKeyring()
    kb0.set_password("testservice", "testusername", "testpassword")
    get_keyring = mocker.patch("dandi.keyring.get_keyring", return_value=kb0)
    kb, password = keyring_lookup("testservice", "testusername")
    assert kb is kb0
    assert password == "testpassword"
    get_keyring.assert_called_once_with()


class EncryptedFailure(fail.Keyring, keyfile.EncryptedKeyring):
    pass


@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_fail_default_encrypted(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    get_keyring = mocker.patch(
        "dandi.keyring.get_keyring", return_value=EncryptedFailure()
    )
    with pytest.raises(KeyringError):
        keyring_lookup("testservice", "testusername")
    get_keyring.assert_called_once_with()


@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_encrypted_fallback_exists_no_password(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    get_keyring = mocker.patch("dandi.keyring.get_keyring", return_value=fail.Keyring())
    kf = Path(keyfile.EncryptedKeyring().file_path)
    kf.parent.mkdir(parents=True, exist_ok=True)
    kf.touch()
    kb, password = keyring_lookup("testservice", "testusername")
    assert isinstance(kb, keyfile.EncryptedKeyring)
    assert password is None
    get_keyring.assert_called_once_with()


@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_encrypted_fallback_exists_password(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    get_keyring = mocker.patch("dandi.keyring.get_keyring", return_value=fail.Keyring())
    kb0 = keyfile.EncryptedKeyring()
    getpass = mocker.patch("getpass.getpass", return_value="file-password")
    kb0.set_password("testservice", "testusername", "testpassword")
    assert getpass.call_count == 2
    getpass.reset_mock()
    kb, password = keyring_lookup("testservice", "testusername")
    assert getpass.call_count == 1
    assert isinstance(kb, keyfile.EncryptedKeyring)
    assert password == "testpassword"
    get_keyring.assert_called_once_with()


@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_encrypted_fallback_not_exists_no_create(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    get_keyring = mocker.patch("dandi.keyring.get_keyring", return_value=fail.Keyring())
    confirm = mocker.patch("click.confirm", return_value=False)
    with pytest.raises(KeyringError):
        keyring_lookup("testservice", "testusername")
    get_keyring.assert_called_once_with()
    confirm.assert_called_once_with(
        "Would you like to establish an encrypted keyring?", default=True
    )


@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_encrypted_fallback_not_exists_create_rcconf(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    get_keyring = mocker.patch("dandi.keyring.get_keyring", return_value=fail.Keyring())
    confirm = mocker.patch("click.confirm", return_value=True)
    kb, password = keyring_lookup("testservice", "testusername")
    assert isinstance(kb, keyfile.EncryptedKeyring)
    assert password is None
    get_keyring.assert_called_once_with()
    confirm.assert_called_once_with(
        "Would you like to establish an encrypted keyring?", default=True
    )
    assert keyringrc_file().exists()
    assert keyringrc_file().read_text() == (
        "[backend]\ndefault-keyring = keyrings.alt.file.EncryptedKeyring\n"
    )


@pytest.mark.usefixtures("tmp_home")
def test_keyring_lookup_encrypted_fallback_not_exists_create_rcconf_exists(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PYTHON_KEYRING_BACKEND", raising=False)
    get_keyring = mocker.patch("dandi.keyring.get_keyring", return_value=fail.Keyring())
    confirm = mocker.patch("click.confirm", return_value=True)
    rc = keyringrc_file()
    rc.parent.mkdir(parents=True, exist_ok=True)
    rc.write_text("# placeholder\n")
    kb, password = keyring_lookup("testservice", "testusername")
    assert isinstance(kb, keyfile.EncryptedKeyring)
    assert password is None
    get_keyring.assert_called_once_with()
    confirm.assert_called_once_with(
        "Would you like to establish an encrypted keyring?", default=True
    )
    assert rc.read_text() == "# placeholder\n"
