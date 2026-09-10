"""AI Aegis Guardian local ML layer (bundled, offline, fail-open)."""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_loaded = False
_guardian = None
_analyze_fn = None
_loaded_source = None
_loaded_version = None


def _ensure_loaded() -> None:
    global _loaded, _guardian, _analyze_fn, _loaded_source, _loaded_version
    if _loaded:
        return
    with _lock:
        if _loaded:
            return
        _loaded = True
        try:
            from aegis import __version__
            from aegis.guardian import GuardianModel, analyze as guardian_analyze
            from aegis.guardian import bundled_model_path

            _guardian = GuardianModel.load(bundled_model_path())
            _analyze_fn = guardian_analyze
            _loaded_source = "bundled"
            _loaded_version = __version__
            logger.info("AI Aegis Guardian ML loaded from bundled asset v%s", _loaded_version)
        except Exception as exc:  # noqa: BLE001 - fail-open by design
            logger.warning("Guardian ML unavailable, continuing with rules only: %s", exc)
            _guardian = None
            _analyze_fn = None


def is_available() -> bool:
    _ensure_loaded()
    return _guardian is not None


def model_version() -> "str | None":
    _ensure_loaded()
    return _loaded_version


def model_source() -> "str | None":
    _ensure_loaded()
    return _loaded_source


def analyze(text: str, *, direction: str = "outgoing") -> dict | None:
    _ensure_loaded()
    if _guardian is None or _analyze_fn is None:
        return None
    try:
        return _analyze_fn(text, _guardian, direction=direction)
    except Exception as exc:  # noqa: BLE001 - fail-open by design
        logger.warning("Guardian analyze failed (ignored): %s", exc)
        return None
