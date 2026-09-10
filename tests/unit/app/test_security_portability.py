"""Cross-platform contracts for security helpers used during rule loading."""

from aegis.utils.security import timeout_context


def test_regex_timeout_context_is_available_on_platforms_without_sigalrm():
    with timeout_context(0.1):
        assert True
