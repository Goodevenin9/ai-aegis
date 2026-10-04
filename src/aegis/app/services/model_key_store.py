"""Runtime-configurable DeepSeek model credentials.

The local web UI can set the model key and toggle drift extraction without a
restart. The key lives in a 0600 file so it never enters SQLite, a backup or an
evidence export; the drift toggle is a non-secret JSON sidecar next to it.

Security contract (keep in sync with docs/SECURITY_AGENT_RUNBOOK.md):

* the key body is never returned to any caller - only a last-four mask
* the key file path is never returned to any caller
* the key is never logged, and never included in an exception message

Precedence for the effective key is unchanged and still owned by
``agent_delivery.read_model_key``: AEGIS_DEEPSEEK_API_KEY ->
AEGIS_DEEPSEEK_API_KEY_FILE -> DEEPSEEK_API_KEY. ``promote_key_file`` only runs
after an explicit UI write, so a key exported by the operator keeps winning
until they deliberately replace it from the browser.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

KEY_FILENAME = "model_key"
SETTINGS_FILENAME = "model_key_settings.json"
DRIFT_FLAG = "AEGIS_DRIFT_LLM_ENABLED"

# Mirrors the size ceiling read_model_key() already enforces on the file.
MAX_KEY_BYTES = 4096
MASK_TAIL = 4

# DeepSeek keys are ``sk-`` + URL-safe token chars. Reject prose (e.g. a status
# message pasted into the UI field) before it can overwrite a real key file.
_KEY_PATTERN = re.compile(r"^sk-[A-Za-z0-9_-]{8,}$")


def _data_dir() -> Path:
    from aegis.app.utils.platform import get_app_data_dir

    return get_app_data_dir()


def default_key_path() -> Path:
    return _data_dir() / KEY_FILENAME


def key_file_path() -> Path:
    """The file the UI reads and writes.

    Honours ``AEGIS_DEEPSEEK_API_KEY_FILE`` so a launcher that already passed
    ``--key-file`` and the web UI share one source of truth. Callers must never
    return this path over HTTP.
    """
    configured = os.environ.get("AEGIS_DEEPSEEK_API_KEY_FILE")
    if configured:
        return Path(configured)
    return default_key_path()


def settings_path() -> Path:
    return _data_dir() / SETTINGS_FILENAME


def is_managed_path() -> bool:
    """True when the key lives in the file this feature owns.

    A launcher-provided ``--key-file`` is the operator's own artefact, so the UI
    must not delete it out from under them.
    """
    return key_file_path() == default_key_path()


def _atomic_write_text(path: Path, text: str) -> bool:
    """Write with 0600 in a single open() so the file is never briefly readable."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, text.encode("utf-8"))
        finally:
            os.close(fd)
        return True
    except OSError as exc:
        # Never echo the payload - only the OS-level failure.
        logger.warning("Failed to write model credential file: %s", exc)
        return False


def save_model_key(api_key: str) -> bool:
    key = (api_key or "").strip()
    if not key or len(key.encode("utf-8")) > MAX_KEY_BYTES:
        return False
    if not _KEY_PATTERN.match(key):
        # Never log the body; mask() is safe (tail/head only).
        logger.warning("Rejected model credential: not a DeepSeek key format (masked=%s)", mask(key))
        return False
    return _atomic_write_text(key_file_path(), key)


def load_model_key() -> str:
    try:
        path = key_file_path()
        if path.stat().st_size > MAX_KEY_BYTES:
            return ""
        return path.read_text(encoding="utf-8-sig").strip()
    except (OSError, UnicodeError):
        return ""


def delete_model_key() -> bool:
    """Remove the UI-managed key file. Refuses to delete a launcher-provided one."""
    if not is_managed_path():
        return False
    try:
        path = default_key_path()
        if path.exists():
            path.unlink()
        return True
    except OSError as exc:
        logger.warning("Failed to delete model key file: %s", exc)
        return False


def mask(api_key: str) -> str:
    """Last-four mask, e.g. ``sk-****3f7a``. Never returns more than the tail."""
    key = (api_key or "").strip()
    if not key:
        return ""
    if len(key) <= MASK_TAIL:
        return "*" * len(key)
    head = key[:3] if key.startswith("sk-") else key[:1]
    return f"{head}****{key[-MASK_TAIL:]}"


def _read_settings() -> dict:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def drift_enabled() -> bool:
    """Effective drift-extraction flag: live env wins over the persisted toggle."""
    value = os.environ.get(DRIFT_FLAG)
    if value is not None:
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(_read_settings().get("drift_llm_enabled"))


def set_drift_enabled(enabled: bool) -> bool:
    os.environ[DRIFT_FLAG] = "true" if enabled else "false"
    data = _read_settings()
    data["drift_llm_enabled"] = bool(enabled)
    return _atomic_write_text(settings_path(), json.dumps(data, indent=2))


def _key_source(effective_key: str) -> str:
    """Category only - never the path."""
    if not effective_key:
        return "none"
    if os.environ.get("AEGIS_DEEPSEEK_API_KEY", "").strip():
        return "environment"
    if load_model_key():
        return "file"
    return "legacy_environment"


def restore_persisted_state() -> None:
    """Startup: re-apply the saved toggle and re-promote a UI-saved key file.

    Without the promotion a key saved from the browser would silently lose to a
    stale exported ``DEEPSEEK_API_KEY`` after every restart. An explicitly
    exported ``AEGIS_DEEPSEEK_API_KEY`` still wins - that is the operator
    overriding the UI on purpose.
    """
    if os.environ.get(DRIFT_FLAG) is None:
        os.environ[DRIFT_FLAG] = "true" if drift_enabled() else "false"

    managed = default_key_path()
    if managed.is_file() and not os.environ.get("AEGIS_DEEPSEEK_API_KEY", "").strip():
        os.environ["AEGIS_DEEPSEEK_API_KEY_FILE"] = str(managed)


def promote_key_file() -> None:
    """After a UI write: make the stored file authoritative over an exported key."""
    os.environ["AEGIS_DEEPSEEK_API_KEY_FILE"] = str(key_file_path())
    os.environ.pop("AEGIS_DEEPSEEK_API_KEY", None)


def credential_status() -> dict:
    """Status safe to return over HTTP: no key body, no file path."""
    from aegis.app.services.agent_delivery import read_model_key

    effective = (read_model_key() or "").strip()
    return {
        "key_configured": bool(effective),
        "key_masked": mask(effective),
        "key_source": _key_source(effective),
        "key_managed": is_managed_path(),
        "drift_llm_enabled": drift_enabled(),
    }


__all__ = [
    "credential_status",
    "delete_model_key",
    "drift_enabled",
    "is_managed_path",
    "key_file_path",
    "load_model_key",
    "mask",
    "promote_key_file",
    "restore_persisted_state",
    "save_model_key",
    "set_drift_enabled",
]
