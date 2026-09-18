"""Static contract for the P0 session-security visualization."""

from pathlib import Path


WEB = Path(__file__).parents[3] / "src" / "aegis" / "app" / "assets" / "web"


def test_session_security_page_is_wired_into_navigation_and_api():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    app = (WEB / "js" / "app.js").read_text(encoding="utf-8")
    sidebar = (WEB / "js" / "components" / "sidebar.js").read_text(encoding="utf-8")
    api = (WEB / "js" / "api.js").read_text(encoding="utf-8")
    page = WEB / "js" / "pages" / "session-security.js"

    assert page.exists()
    assert "/js/pages/session-security.js" in index
    assert "'session-security': SessionSecurityPage" in app
    assert "id: 'session-security'" in sidebar
    assert "getRuntimeSessions" in api
    assert "getRuntimeSession" in api


def test_session_security_page_renders_pipeline_timeline_and_integrity():
    source = (WEB / "js" / "pages" / "session-security.js").read_text(encoding="utf-8")
    for token in ["Boundary", "Capability", "Radius", "Drift", "Friction"]:
        assert token in source
    assert "risk_curve" in source
    assert "integrity" in source
    assert "payload.layers" in source
    assert "layer.signals" in source


def test_p1_policy_manifest_evaluation_and_export_are_exposed_in_ui():
    api = (WEB / "js" / "api.js").read_text(encoding="utf-8")
    source = (WEB / "js" / "pages" / "session-security.js").read_text(encoding="utf-8")

    for token in [
        "getRuntimePipelineConfig",
        "updateRuntimePipelineConfig",
        "getRuntimeManifests",
        "updateRuntimeManifest",
        "runRuntimeEvaluation",
    ]:
        assert token in api
    assert "P1 policy & evaluation" in source
    assert "Developer capability Manifest" in source
    assert "Export evidence JSON" in source


def test_developer_manifest_designer_exposes_safe_presets_and_scope_guardrails():
    source = (WEB / "js" / "pages" / "session-security.js").read_text(encoding="utf-8")

    for token in [
        "data-manifest-preset=\"readonly\"",
        "data-manifest-preset=\"local\"",
        "data-manifest-preset=\"full\"",
        "file_read",
        "file_write",
        "shell_exec",
        "network_outbound",
        "Enter an absolute project root",
        "Full development is broad.",
        "Boundary and Drift remain active.",
    ]:
        assert token in source


def test_developer_manifest_copy_is_available_in_chinese_dictionary():
    dictionary = (WEB / "js" / "i18n-dict.js").read_text(encoding="utf-8")

    assert '"Developer capability Manifest": "开发能力 Manifest"' in dictionary
    assert '"Full development": "完整开发"' in dictionary
    assert '"Save and activate Manifest": "保存并激活 Manifest"' in dictionary
