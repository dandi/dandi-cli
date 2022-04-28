import os.path as op
from pathlib import Path
from typing import Optional, Tuple

import click
from keyring.backend import KeyringBackend, get_all_keyring
from keyring.core import get_keyring, load_config, load_env
from keyring.errors import KeyringError
from keyring.util.platform_ import config_root
from keyrings.alt.file import EncryptedKeyring

from . import get_logger

lgr = get_logger()


def keyring_lookup(
    service_name: str, username: str
) -> Tuple[KeyringBackend, Optional[str]]:
    """
    Determine a keyring backend to use for storing & retrieving credentials as
    follows:

    - If the user has specified a backend explicitly via the
      ``PYTHON_KEYRING_BACKEND`` environment variable or a ``keyringrc.cfg``
      file, use that backend without checking whether it's usable (If it's not,
      the user messed up).

    - Otherwise, query the default backend (which is guaranteed to already have
      the requisite dependencies installed) for the credentials for the given
      service name and username.  If this completes without error (regardless
      of whether the backend contains any such credentials), use that backend.

    - If the query fails (e.g., because a GUI is required but the session is in
      a plain terminal), try using the ``EncryptedKeyring`` backend.

      - If the default backend *was* the ``EncryptedKeyring`` backend, error.

      - If the ``EncryptedKeyring`` backend is not in the list of available
        backends (likely because its dependencies are not installed, though
        that shouldn't happen if dandi was installed properly), error.

      - If ``EncryptedKeyring``'s data file already exists, use it as the
        backend.

      - If ``EncryptedKeyring``'s data file does not already exist, ask the
        user whether they want to start using ``EncryptedKeyring``.  If yes,
        then set ``keyringrc.cfg`` (if it does not already exist) to specify it
        as the default backend, and return the backend.  If no, error.

    Returns a keyring backend and the password it holds (if any) for the given
    service and username.
    """

    kb = load_env() or load_config()
    if kb:
        return (kb, kb.get_password(service_name, username))
    kb = get_keyring()
    try:
        password = kb.get_password(service_name, username)
    except KeyringError as e:
        lgr.info("Default keyring errors on query: %s", e)
        if isinstance(kb, EncryptedKeyring):
            lgr.info(
                "Default keyring is EncryptedKeyring; abandoning keyring procedure"
            )
            raise
        # Use `type(..) is` instead of `isinstance()` to weed out subclasses
        kbs = [k for k in get_all_keyring() if type(k) is EncryptedKeyring]
        assert (
            len(kbs) == 1
        ), "EncryptedKeyring not available; is pycryptodomex installed?"
        kb = kbs[0]
        if op.exists(kb.file_path):
            lgr.info("EncryptedKeyring file exists; using as keyring backend")
            return (kb, kb.get_password(service_name, username))
        lgr.info("EncryptedKeyring file does not exist")
        if click.confirm(
            "Would you like to establish an encrypted keyring?", default=True
        ):
            keyring_cfg = keyringrc_file()
            if keyring_cfg.exists():
                lgr.info("%s exists; refusing to overwrite", keyring_cfg)
            else:
                lgr.info(
                    "Configuring %s to use EncryptedKeyring as default backend",
                    keyring_cfg,
                )
                keyring_cfg.parent.mkdir(parents=True, exist_ok=True)
                keyring_cfg.write_text(
                    "[backend]\n"
                    "default-keyring = keyrings.alt.file.EncryptedKeyring\n"
                )
            return (kb, None)
        raise
    else:
        return (kb, password)


def keyringrc_file() -> Path:
    return Path(config_root(), "keyringrc.cfg")
