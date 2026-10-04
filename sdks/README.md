# Aegis Framework SDKs

Tool-call security for the four framework targets the Integrations wizard
lists. Each package intercepts **tool calls** (not just LLM traffic), routes
them through the local Aegis engine over loopback, and writes decisions to the
same tamper-evident audit chain the CLI plugins use — tagged `runtime_kind`.

| Package | Import | Runtime kind | Entry point |
|---|---|---|---|
| `aegis-sdk-langchain` | `aegis_sdk_langchain` | `langchain` | `secure_middleware`, `AegisCallbackHandler` |
| `aegis-sdk-langgraph` | `aegis_sdk_langgraph` | `langgraph` | `secure_middleware`, `AegisCallbackHandler` |
| `aegis-sdk-crewai` | `aegis_sdk_crewai` | `crewai` | `secure_tools`, `install` |
| `aegis-sdk-hermes` | `aegis_sdk_hermes` | `hermes` | `hermes_agent.plugins` entry point, `install` |

## Install

From this repo (pre-publish):

```bash
pip install ./sdks/aegis-sdk-langchain          # or -langgraph / -crewai / -hermes
# adapter only against a self-hosted engine (framework + ai-aegis already present):
pip install ./sdks/aegis-sdk-langchain --no-deps
```

Each package is self-contained: the shared core is **vendored** as
`aegis_sdk_<framework>/_core.py` so `--no-deps` never breaks the import.

## Point it at an engine

```bash
export AEGIS_ENGINE_ENDPOINT=http://127.0.0.1:8741   # default: loopback
export AEGIS_API_KEY=<ingress token>                 # only for a public/gated endpoint
export AEGIS_SDK_MODE=enforce                         # default: observe
```

## Posture

| Mode | Engine reachable | Engine unreachable |
|---|---|---|
| `observe` (default) | log + advisory verdict; tool always runs | tool runs (fail-open) |
| `enforce` | tool runs only if the verdict ≠ `block` | tool denied (fail-closed) |

`AEGIS_HEADLESS=1` (or `CI`) escalates a `confirm` verdict to `block`
server-side, so enforce mode does not silently run a call that wanted a human.

## The vendored core

`_core/aegis_sdk_core.py` is the single source of truth. It is copied into each
package; do **not** edit the copies.

```bash
python sdks/sync_core.py          # write the copies
python sdks/sync_core.py --check   # CI: fail if a copy drifted
```

`tests/test_core_lockstep.py` enforces the same thing under pytest.

## Verified against real frameworks

Verified end-to-end against a live engine (`127.0.0.1:8741`); each run's
decision landed on the audit chain with the right `runtime_kind`:

| SDK | Framework tested | Result |
|---|---|---|
| langchain | `langchain 1.4.2` | `create_agent(..., middleware=[...])` → enforce blocked (`run_shell rm -rf /` never executed), observe ran; audit `runtime_kind=langchain` |
| langgraph | `langgraph 1.2.12` | same via the langgraph-backed `create_agent`; audit `runtime_kind=langgraph` |
| crewai | `crewai 1.15.22` | `secure_tools` enforce raised before `_run`; `install()` patched `BaseTool.run`; observe ran |
| hermes | `hermes-agent 0.19.0` | entry point discovered by Hermes' `PluginManager`; `resolve_pre_tool_block('terminal', …)` returned the Aegis block message |

Three contract bugs were caught only by running the real frameworks (all fixed):

1. **Audit rows were dropped on process exit** — `_post_async` used a *daemon*
   thread, so a short agent run terminated before the POST flushed. Now uses a
   non-daemon thread (the interpreter joins it at exit; bounded by
   `timeout_s`).
2. **CrewAI `install()` was a no-op** — it patched `BaseTool._run`, which tools
   routinely override. Now patches the public `BaseTool.run`.
3. **Hermes block directive shape** — Hermes reads `{"action": "block",
   "message": ...}` (not `reason`). `pre_tool_call` now returns `message`, and
   `register(ctx)` wires `ctx.register_hook("pre_tool_call", …)`.

## Tests

```bash
python -m pytest sdks/tests -q
```

The core is tested behaviourally (fake transport); the framework adapters are
tested against fakes (no `langchain` / `crewai` / `hermes_agent` required),
because the adapters import their framework lazily.
