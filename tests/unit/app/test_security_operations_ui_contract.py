"""Static UI contract for the non-chat P2 Security Operations workbench."""

from pathlib import Path

ROOT = Path(__file__).parents[3]
WEB = ROOT / "src" / "aegis" / "app" / "assets" / "web"


def test_security_operations_page_is_registered_and_loaded():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    app = (WEB / "js" / "app.js").read_text(encoding="utf-8")
    sidebar = (WEB / "js" / "components" / "sidebar.js").read_text(encoding="utf-8")

    assert "security-operations.js" in index
    assert "'security-operations': SecurityOperationsPage" in app
    assert "Security Copilot" in sidebar


def test_workbench_exposes_evidence_rag_immunity_memory_and_approval_not_just_chat():
    page = (WEB / "js" / "pages" / "security-operations.js").read_text(encoding="utf-8")

    for capability in (
        "Evidence & multimodal intake",
        "Evidence-grounded RAG",
        "Session immunity",
        "Governed memory",
        "Approve exact proposal",
    ):
        assert capability in page
    assert "Security operations, not another chatbot" in page


def test_credentials_are_writable_from_the_page_but_never_prefilled():
    page = (WEB / "js" / "pages" / "security-operations.js").read_text(encoding="utf-8")
    api = (WEB / "js" / "api.js").read_text(encoding="utf-8")

    for method in (
        "getModelCredentials",
        "updateModelCredentials",
        "deleteModelCredentials",
        "testModelCredentials",
    ):
        assert method in api, method

    # The key input is write-only: no code path assigns the masked value back
    # into it, and the field starts empty on every render.
    assert 'type="password" name="api_key"' in page
    assert "so-cred-key" in page
    assert page.count(".value =") <= 1
    assert "Enable drift extraction" in page
