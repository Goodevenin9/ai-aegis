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
