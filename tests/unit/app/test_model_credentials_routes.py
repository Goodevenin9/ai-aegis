"""Web-configurable model credentials: token gate, precedence and non-echo.

These cover the two failure modes the feature exists to prevent: a stale
exported ``DEEPSEEK_API_KEY`` silently outranking the key the operator typed
into the browser, and a key that is accepted by the UI but never reaches the two
consumers that snapshot it in ``__init__``.
"""

import json

import pytest
from fastapi import HTTPException

from aegis.app.server.routes import runtime_pipeline, security_operations
from aegis.app.server.routes.jit_access import _UI_TOKEN
from aegis.app.server.routes.security_operations import (
    ModelCredentialRequest,
    get_model_credentials,
    remove_model_credentials,
    update_model_credentials,
)
from aegis.app.services import model_key_store
from aegis.app.services.agent_delivery import read_model_key
from aegis.app.services.security_agent import DeepSeekAgentModel

ENV_KEYS = (
    "AEGIS_DEEPSEEK_API_KEY",
    "AEGIS_DEEPSEEK_API_KEY_FILE",
    "DEEPSEEK_API_KEY",
    "AEGIS_DRIFT_LLM_ENABLED",
)

NEW_KEY = "sk-ui-written-0000000000000000beef"
STALE_KEY = "sk-stale-environment-00000000000000"


class _StubAgent:
    """Stands in for SecurityAnalystAgent: only ``.model`` is read by the refresh."""

    def __init__(self, model):
        self.model = model


@pytest.fixture(autouse=True)
def isolated_credentials(tmp_path, monkeypatch):
    """Keep every test off the real data dir and out of the ambient environment.

    monkeypatch already restores the four env vars it clears, including the ones
    the code under test sets directly (``promote_key_file`` exports
    ``AEGIS_DEEPSEEK_API_KEY_FILE``), so no manual teardown is needed.
    """
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(model_key_store, "_data_dir", lambda: tmp_path)
    # _refresh_model_consumers() rebinds this module global; snapshot it so the
    # replacement does not leak into the rest of the suite.
    monkeypatch.setattr(runtime_pipeline, "_extractor", runtime_pipeline._extractor)
    monkeypatch.setattr(security_operations, "_agent", None)
    return tmp_path


async def _put(api_key=None, drift=None, token=_UI_TOKEN):
    return await update_model_credentials(
        ModelCredentialRequest(api_key=api_key, drift_llm_enabled=drift), token
    )


@pytest.mark.asyncio
async def test_writes_require_the_ui_token_and_reads_do_not():
    for call in (
        lambda: _put(api_key=NEW_KEY, token=None),
        lambda: remove_model_credentials(None),
    ):
        with pytest.raises(HTTPException) as error:
            await call()
        assert error.value.status_code == 403

    # The status endpoint stays readable so the page can render a badge before
    # the operator has done anything.
    assert isinstance(await get_model_credentials(), dict)


@pytest.mark.asyncio
async def test_a_ui_write_reaches_both_consumers_that_froze_the_key():
    primary = DeepSeekAgentModel()
    primary.connection_status = "online"
    security_operations._agent = _StubAgent(primary)
    # Bound at import time, so it may hold whatever the ambient environment had.
    before = runtime_pipeline._extractor

    await _put(api_key=NEW_KEY)

    # The extractor captures api_key in __init__ and an empty key poisons it
    # permanently, so the refresh must rebuild rather than patch it.
    assert runtime_pipeline._extractor is not before
    assert runtime_pipeline._extractor.api_key == NEW_KEY
    assert primary.api_key == NEW_KEY
    assert primary.connection_status == "untested"


@pytest.mark.asyncio
async def test_status_returns_a_mask_and_never_the_key_body_or_path(isolated_credentials):
    await _put(api_key=NEW_KEY)

    payload = json.dumps(await get_model_credentials())

    assert NEW_KEY not in payload
    assert str(isolated_credentials) not in payload
    assert "sk-****beef" in payload
    assert json.loads(payload)["key_source"] == "file"


@pytest.mark.asyncio
async def test_a_ui_write_outranks_a_stale_exported_key(monkeypatch):
    """Regression for the shadowing bug: the file must win after an explicit write."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", STALE_KEY)
    assert read_model_key() == STALE_KEY

    await _put(api_key=NEW_KEY)

    assert read_model_key() == NEW_KEY
    assert json.loads(json.dumps(await get_model_credentials()))["key_source"] == "file"


@pytest.mark.asyncio
async def test_delete_returns_to_unconfigured(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", STALE_KEY)
    await _put(api_key=NEW_KEY)
    assert read_model_key() == NEW_KEY

    status = await remove_model_credentials(_UI_TOKEN)

    # The exported key was only ever shadowed, not erased, so it resurfaces.
    assert status["key_configured"] is True
    assert read_model_key() == STALE_KEY

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("AEGIS_DEEPSEEK_API_KEY_FILE", raising=False)
    assert (await get_model_credentials())["key_configured"] is False


@pytest.mark.asyncio
async def test_delete_refuses_a_launcher_supplied_key_file(tmp_path, monkeypatch):
    launcher_key = tmp_path / "operator-supplied"
    launcher_key.write_text("sk-launcher-owned", encoding="utf-8")
    monkeypatch.setenv("AEGIS_DEEPSEEK_API_KEY_FILE", str(launcher_key))

    with pytest.raises(HTTPException) as error:
        await remove_model_credentials(_UI_TOKEN)

    assert error.value.status_code == 409
    assert launcher_key.exists()


@pytest.mark.asyncio
async def test_drift_toggle_is_persisted_and_can_be_set_alone():
    status = await _put(drift=True)
    assert status["drift_llm_enabled"] is True
    assert json.loads((model_key_store.settings_path()).read_text(encoding="utf-8")) == {
        "drift_llm_enabled": True
    }

    await _put(drift=False)
    assert (await get_model_credentials())["drift_llm_enabled"] is False
    # Toggling must not have touched the key.
    assert read_model_key() == ""


@pytest.mark.asyncio
async def test_empty_update_is_rejected():
    with pytest.raises(HTTPException) as error:
        await update_model_credentials(ModelCredentialRequest(), _UI_TOKEN)
    assert error.value.status_code == 422
