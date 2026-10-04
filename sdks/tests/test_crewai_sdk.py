"""Adapter tests for aegis-sdk-crewai (crewai itself is not required)."""
import pytest

import aegis_sdk_crewai as sdk


class Tool:
    name = "terminal"
    description = "Run a shell command"

    def _run(self, command):
        return f"ran:{command}"


def test_enforce_raises_before_run(fake_client):
    fc = fake_client(action="block", reason="danger")
    (wrapped,) = sdk.secure_tools([Tool()], mode="enforce", client=fc)
    assert wrapped.name == "terminal" and wrapped.description == "Run a shell command"
    with pytest.raises(PermissionError) as exc:
        wrapped._run("rm -rf /")
    assert "Aegis Guard" in str(exc.value)
    assert fc.audits and fc.audits[0][1]["action"] == "block"


def test_observe_runs_and_audits(fake_client):
    fc = fake_client(action="block", reason="would block")
    (wrapped,) = sdk.secure_tools([Tool()], mode="observe", client=fc)
    assert wrapped.run("ls") == "ran:ls"
    assert fc.audits, "observe still logs non-allow calls"


def test_allow_passes_through(fake_client):
    (wrapped,) = sdk.secure_tools([Tool()], mode="enforce", client=fake_client(action="allow"))
    assert wrapped("echo hi") == "ran:echo hi"


def test_install_without_crewai_returns_false(fake_client):
    # crewai is not installed in this test environment
    assert sdk.install(mode="observe", client=fake_client(action="allow")) is False


def test_guard_call_returns_reason(fake_client):
    fc = fake_client(action="block", reason="blocked!")
    run, reason, verdict = sdk.guard_call(fc, "enforce", True, "terminal", {"command": "x"}, None)
    assert run is False and reason == "blocked!" and verdict.blocked
