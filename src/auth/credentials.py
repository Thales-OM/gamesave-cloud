"""
Credential resolution for remote storage backends.

Resolution order per field:
  1. explicitly passed named argument (CLI / API)
  2. previously persisted value in the OS keyring
  3. interactive prompt (getpass for secrets)

Secrets are stored only in the OS keyring (Windows Credential Manager,
macOS Keychain, Secret Service). Non-secret options go back to the
caller so they can be persisted in metadata.
"""

import getpass
from typing import Any, Dict, List, Optional

from src.constants import KEYRING_SERVICE
from src.exceptions import StorageAuthError
from src.logger import LoggerFactory
from src.models.remote_config import CredentialField

logger = LoggerFactory.getLogger(__name__)

try:
    import keyring
    from keyring.errors import KeyringError

    _keyring_ok = True
except ImportError:  # pragma: no cover
    keyring = None
    _keyring_ok = False


def _scope(remote_id: str, field_name: str) -> str:
    return f"remote/{remote_id}/{field_name}"


def store_secret(remote_id: str, field_name: str, value: str) -> bool:
    if not _keyring_ok:
        logger.warning("keyring package not available - secret NOT persisted")
        return False
    try:
        keyring.set_password(
            KEYRING_SERVICE, _scope(remote_id, field_name), value
        )
        return True
    except KeyringError as ex:
        logger.warning(f"Could not store secret in keyring: {ex}")
        return False


def load_secret(remote_id: str, field_name: str) -> Optional[str]:
    if not _keyring_ok:
        return None
    try:
        return keyring.get_password(
            KEYRING_SERVICE, _scope(remote_id, field_name)
        )
    except KeyringError as ex:
        logger.warning(f"Could not read secret from keyring: {ex}")
        return None


def delete_secrets(remote_id: str, fields: List[CredentialField]) -> None:
    if not _keyring_ok:
        return
    for field in fields:
        try:
            keyring.delete_password(
                KEYRING_SERVICE, _scope(remote_id, field.name)
            )
        except Exception:
            pass


def _prompt(field: CredentialField) -> str:
    label = f"{field.prompt}"
    if field.secret:
        return getpass.getpass(f"{label}: ")
    return input(f"{label}: ").strip()


def resolve_credentials(
    fields: List[CredentialField],
    provided: Dict[str, Any],
    remote_id: str = "new",
    persist_secrets: bool = True,
) -> Dict[str, Any]:
    """
    Resolve every declared field to a concrete value.

    Returns {field_name: value}. Callers must split secrets out (they are
    never written to metadata) using CredentialField.secret.
    """
    resolved: Dict[str, Any] = {}
    for field in fields:
        value = provided.get(field.name)
        source = "argument"
        if not value and field.secret:
            value = load_secret(remote_id, field.name)
            source = "keyring"
        if not value:
            value = _prompt(field)
            source = "prompt"
            if field.secret and persist_secrets and value:
                store_secret(remote_id, field.name, value)
        if not value:
            if field.required:
                raise StorageAuthError(
                    f"Missing required credential '{field.name}' "
                    f"({field.prompt})"
                )
            continue
        logger.debug(f"Credential '{field.name}' resolved from {source}")
        resolved[field.name] = value
    return resolved
