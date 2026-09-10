<div align="center">

<h1><img src="https://gitee.com/wan-xianghao/ai-aegis/raw/master/docs/favicon.png" alt="Aegis" width="40" height="40"> Aegis</h1>

<h3>Security &amp; Observability for AI Agents</h3>

<p><em>Audit every tool. Catch the threats. All locally.</em></p>

</div>

- **See everything — Traces.** Every agent session replays as a stepped waterfall: verdict per tool call, tokens + estimated cost per model call. Live follow, redacted replay, audit PDF.
- **Control everything — permissions + JIT.** Allow / deny / ask at agent runtime. Blocked tools become just-in-time requests: approve for 15 minutes, an hour, or one session — grants expire on their own.
- **Audit the past — Instant Agent Audit.** Opt-in scan of session history already on disk: destructive commands, plaintext secrets, estimated spend.
- **Catch the threats — 72 rules + Guardian ML.** OWASP LLM Top 10 + 28 agent-attack chains, detected while the agent is still running. Offline ML catches what regex misses. [Details ↓](#optional-ml-detection-layer--aegis-guardian)
- **Prove it** — every tool call in a SHA-256 hash-chained log; blocked actions get a per-rule evidence ledger.
- **Apache 2.0, no signup, 100% local** — `pip install` and you're covered in 60 seconds. Nothing leaves your machine.

### Works with every agent

| Agent / runtime | How to add | Audit `runtime_kind` |
|---|---|---|
| **Claude Code** | Native plugin — inline hooks, zero proxy | `claude-code` |
| **OpenAI Codex** *(CLI 0.133+)* | Native plugin | `codex` |
| **GitHub Copilot CLI** | Native plugin | `copilot-cli` |
| **Cursor** | Native plugin | `cursor` |
| **OpenClaw / ClawdBot** | Native plugin | `openclaw` |
| **LangChain / LangGraph / CrewAI / Hermes** | LLM Proxy 集成，详见 [USECASES](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/USECASES.md) | 见各用例 |

<div align="center">

<br>

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![PyPI](https://img.shields.io/pypi/v/ai-aegis.svg?style=for-the-badge)](https://pypi.org/project/ai-aegis)
[![Python](https://img.shields.io/pypi/pyversions/ai-aegis.svg?style=for-the-badge)](https://pypi.org/project/ai-aegis)
[![Downloads/month](https://img.shields.io/pypi/dm/ai-aegis?style=for-the-badge&label=downloads%2Fmonth&color=orange)](https://pypistats.org/packages/ai-aegis)
[![Downloads total](https://img.shields.io/pepy/dt/ai-aegis?style=for-the-badge&label=downloads%20total&color=orange)](https://pepy.tech/project/ai-aegis)
[Getting Started](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/GETTING_STARTED.md) · [Verify your install](https://gitee.com/wan-xianghao/ai-aegis/blob/master/SECURITY.md#verifying-your-download) · [Dashboard Screenshots](#screenshots)

</div>

> **开源与归属**：AI Aegis 采用 Apache License 2.0。项目包含经许可演进的
> 上游代码和模型资产，法定版权、来源与变更说明统一记录在 [NOTICE](https://gitee.com/wan-xianghao/ai-aegis/blob/master/NOTICE)
> 与 [LICENSE](https://gitee.com/wan-xianghao/ai-aegis/blob/master/LICENSE) 中；产品界面、命令、配置和插件均使用 AI Aegis 标识。

<br>

<div align="center">
  <p><em>Threat detection, tool permissions, and cost tracking — running locally in real time.</em></p>
</div>

<br>

> **AI Aegis (灵盾) 1.0.0** — AI 智能体的安全与可观测监控平台。
> - **威胁检测**：72 条规则 + Guardian ML 检测层，覆盖提示注入、数据泄露、越狱攻击等 OWASP LLM Top 10 威胁
> - **工具权限治理**：Allow / Deny / JIT 授权，为每个工具调用实时裁决
> - **全链路审计**：每次工具调用的 SHA-256 哈希链日志、事件回放、审计 PDF
> - **Agent 可观测**：Trace 瀑布流、Agent 拓扑地图、成本追踪、规则与权限明细
> - **中英文界面**：一键切换，满足不同使用者习惯
> - 支持 Claude Code / Codex / Copilot CLI / Cursor / OpenClaw 等主流 Agent
>
> 本版本基于 Apache-2.0 开源项目二次开发，版本历史见 [CHANGELOG](https://gitee.com/wan-xianghao/ai-aegis/blob/master/CHANGELOG.md)。

## How It Works

<img src="https://gitee.com/wan-xianghao/ai-aegis/raw/master/docs/aegis-architecture.svg" alt="Aegis Architecture" width="100%">

**Aegis** protects your AI agents at three layers:

- **Pre-install** — the Skill Scanner checks agent skill packages for shell access, network calls, and hidden risks before you install them.
- **Runtime** — every tool call lands in a SHA-256 hash-chained audit log; prompts, responses, and natural-language tool inputs are scanned for injection, data leaks, and unauthorized access.
- **Observe** — the SIEM Forwarder ships threats + audits to your SOC in OCSF 1.3.0 (Splunk, Datadog, Sentinel, Chronicle, QRadar, OTLP, webhook, NDJSON). Metadata-only by default.

100% local — events only leave the machine when you configure a SIEM destination you control.

<br>

## Quick Start

**Step 1 — Install or download**

```bash
pip install ai-aegis[app]
aegis-app --web
```

**Or download the app:** [Windows](https://gitee.com/wan-xianghao/ai-aegis/releases) · [Linux](https://gitee.com/wan-xianghao/ai-aegis/releases) · [DEB](https://gitee.com/wan-xianghao/ai-aegis/releases) · [RPM](https://gitee.com/wan-xianghao/ai-aegis/releases) · [macOS](https://gitee.com/wan-xianghao/ai-aegis/releases)

**Step 2 — Open the app**

Open [http://localhost:8741](http://localhost:8741) in your browser, or double-click the installed binary.

**Step 3 — Connect your agent**

<table>
<tr>
<th align="left" width="50%">OpenClaw / ClawdBot (plugin, zero latency)</th>
<th align="left" width="50%">LangChain, CrewAI, Ollama, n8n (proxy)</th>
</tr>
<tr>
<td valign="top">

**Observability & Monitoring** — Go to **Integrations → OpenClaw**, click **Install Plugin**, restart OpenClaw. Done. No proxy, no env vars.

</td>
<td valign="top">

**Observability & Monitoring** — Go to **Integrations**, pick your framework, click **Start Proxy**, and set the env var shown on the page.

</td>
</tr>
</table>

> **Block Mode (only if you want to enforce blocking)** — Toggle **Block Mode** on the dashboard. The proxy starts automatically and blocks threats before they reach the LLM. Adds ~10–50ms latency per request. Applies to both plugin and proxy integrations.

If the app fails to launch because ports 8741/8742 are already in use, use `--port <port>` of your choice — the proxy starts automatically on port+1.
See [Configuration](#configuration) for proxy or web/api port settings.

> **Open-source. 100% local by default. No API keys required.**

<br>

## Screenshots

*All screenshots are from a local app instance.*

**🗺️ Agent Map & Traces**

<table>
<tr>
<td width="58%"><img src="https://gitee.com/wan-xianghao/ai-aegis/raw/master/docs/screenshots/agent-map.png" alt="Agent Map" width="100%"><br><em>Agent Map — your whole fleet at a glance: device → harness → agent → tool, across tree / radial / mesh / Sankey views. Blocked calls pop red, secret-touching agents wear a lock. Click any node to drill into its trace.</em></td>
<td width="42%"><img src="https://gitee.com/wan-xianghao/ai-aegis/raw/master/docs/screenshots/agent-runs.png" alt="Traces" width="100%"><br><em>Traces — a turn-by-turn waterfall of every tool call with its allow / block verdict, risk, and reason. Here a prompt-injection and a credential-exfiltration attempt are both caught and blocked.</em></td>
</tr>
</table>

<br>

<table>
<tr>
<td width="25%"><img src="https://gitee.com/wan-xianghao/ai-aegis/raw/master/docs/screenshots/tool-call-history.png" alt="Tool Call History" width="100%"><br><em>Tool Call History — 305 calls, 158 blocked: bash rm -rf, gmail_send to attacker, use_aws_cli stopped</em></td>
<td width="25%"><img src="https://gitee.com/wan-xianghao/ai-aegis/raw/master/docs/screenshots/dashboard.png" alt="Dashboard" width="100%"><br><em>Dashboard — threat counts, cost metrics, and tool permission status</em></td>
<td width="25%"><img src="https://gitee.com/wan-xianghao/ai-aegis/raw/master/docs/screenshots/costs-light.png" alt="LLM Cost Tracker" width="100%"><br><em>LLM Cost Tracker — per-agent spend, budgets, and token breakdown</em></td>
<td width="25%"><img src="https://gitee.com/wan-xianghao/ai-aegis/raw/master/docs/screenshots/skill-scanner.png" alt="Skill Scanner" width="100%"><br><em>Skill Scanner — static security analysis for AI agent skills</em></td>
</tr>
</table>

<br>

## What You Get

<table>
<tr>
<th align="left" width="50%">Tool Audit & Permissions</th>
<th align="left" width="50%">Threat Detection</th>
</tr>
<tr>
<td valign="top">

Every tool call is recorded to a SHA-256-linked, tamper-evident audit log (re-verify in one click). Inputs are stored as a 200-char preview *after* secret redaction — raw payloads never persisted. Allow / deny / ask rules per tool, enforced at the agent runtime via PreToolUse hooks or the multi-provider proxy.

</td>
<td valign="top">

Scans every prompt, response, and natural-language tool input for prompt injection (direct + indirect), jailbreaks, PII leaks, credential exfiltration, and tool-result injection. 72 rules covering the OWASP LLM Top 10 + 28 agent-attack chains. Monitor by default; opt-in block mode for hard-stop.

</td>
</tr>
<tr>
<th align="left">Skill Scanner</th>
<th align="left">Cost & Token Tracking</th>
</tr>
<tr>
<td valign="top">

Scan agent skills and tool packages before installing. Static analysis across 10 categories detects shell access, network calls, env var reads, code exec, base64 payloads, symlink escapes, and more. Optional AI review filters false positives automatically.

</td>
<td valign="top">

Per-agent, per-model token and USD spend in real time, with daily budget auto-stop. Plugins read session transcripts locally for a 7-day input/output/cache trend per runtime — no cloud round-trip, no token data leaves your machine.

</td>
</tr>
<tr>
<th align="left">SIEM Forwarder</th>
<th align="left">Full Visibility</th>
</tr>
<tr>
<td valign="top">

Forward every threat + tool-call audit to your SOC in OCSF 1.3.0. Supports Splunk HEC, Datadog, Microsoft Sentinel, Google Chronicle, IBM QRadar, OpenTelemetry/OTLP, generic webhook, or a local NDJSON file. Metadata-only by default; raw data is opt-in per destination.

</td>
<td valign="top">

Live dashboard showing every LLM request, tool call, token count, and threat event. Per-agent Replay timeline merges threat scans + tool audits + cost into one feed.

</td>
</tr>
<tr>
<th align="left" colspan="2">100% Local by Default</th>
</tr>
<tr>
<td valign="top" colspan="2">

Runs entirely on your machine. No accounts required. No data leaves your infrastructure unless you configure a SIEM destination. Open source under Apache 2.0.

</td>
</tr>
</table>

<br>

**Performance:** Rule-based analysis (default) adds ~10–50ms per request. Optional AI analysis adds 1–3s depending on the model and provider — shown on the dashboard so you can measure it against your actual traffic. Tool-permission decisions (`allow` / `block` / `log_only`): see the [Tool Permissions guide](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/TOOL_PERMISSIONS.md).

<br>

## Works With Everything

**Your AI Stack** — LangChain · LlamaIndex · CrewAI · AutoGen · LangGraph · n8n · Dify · OpenClaw/ClawdBot — or any framework that makes HTTP calls to an LLM provider.

**LLM Providers** — OpenAI · Anthropic · Ollama · Groq · and any OpenAI-compatible API.

**Run Anywhere** — macOS / Linux / Windows · Docker & Kubernetes · AWS / GCP / Azure · VMs · Lambda / Workers / Vercel.

## Agent Integrations

| Agent/Framework | Integration |
|-----------------|-------------|
| **LangChain** | [**`aegis-sdk-langchain`**](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/USECASES.md#langchain) (tool-call SDK, recommended) or LLM Proxy |
| **LangGraph** | [**`aegis-sdk-langgraph`**](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/USECASES.md#langgraph) (tool-call SDK, recommended) or LLM Proxy |
| **CrewAI** | [**`aegis-sdk-crewai`**](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/USECASES.md#crewai) (tool-call SDK, recommended) or LLM Proxy |
| **Hermes (hermes-agent)** | [**`aegis-sdk-hermes`**](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/USECASES.md#hermes) (zero-config tool-call SDK, recommended) |
| **Any OpenAI-compatible** | LLM Proxy — see Integrations in UI |
| **OpenClaw / ClawdBot** *(LLM gateway agent)* | Native plugin (zero latency) — proxy only for block mode |
| **n8n** | [Community Node](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/USECASES.md#n8n) |
| **Claude Desktop** | [MCP Server Guide](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/MCP_GUIDE.md) |
| **Any OpenAI-compatible app** | LLM Proxy — set `OPENAI_BASE_URL` to proxy |
| **Any HTTP Client** | `POST http://localhost:8741/analyze` with `{"text": "..."}` |

### OpenClaw / ClawdBot

Native plugin with **ZERO latency** — runs inside the agent, no proxy needed. Install from the Integrations tab or `curl -X POST http://localhost:8741/api/hooks/install`. Enable block mode from the dashboard when you want to actively stop threats via proxy.

[Full setup guide](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/OPENCLAW.md)

### Claude Code

First-class plugin for Anthropic's Claude Code CLI — `PreToolUse` enforces tool-permission rules (allow / deny / ask, cloud-syncable), `PostToolUse` writes a tamper-evident audit row + scans prose tool inputs, `UserPromptSubmit` catches direct prompt-injection. Optional one-line statusline emitter surfaces live findings next to model / cwd / git state. Loopback-only, fail-open.

**Install — two options:**

```bash
# Option A: via the app UI
# Open http://127.0.0.1:8741 → Integrations → Claude Code → Install Plugin

# Option B: via CLI
aegis-app --install-plugin claude-code
# Uninstall: aegis-app --uninstall-plugin claude-code

# Then, in your Claude Code session:
/reload-plugins
```

[Full setup guide](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/CLAUDE_CODE.md)

<br>

## What It Detects

| Input Threats (User to LLM) | Output Threats (LLM to User) |
|-----------------------------|------------------------------|
| Prompt injection | Credential leakage (API keys, tokens) |
| Jailbreak attempts | System prompt exposure |
| Data exfiltration requests | PII disclosure (SSN, credit cards) |
| Social engineering | Jailbreak success indicators |
| SQL injection patterns | Encoded malicious content |
| Tool result injection (MCP) | — |
| Multi-agent authority spoofing | — |
| Permission scope escalation | — |

Full coverage: [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)

### AI Agent Attack Protection (28 new rules · 72 total)

Built from real attack chains observed against production agent frameworks:

- **Tool Result Injection** — injected instructions hidden inside MCP tool responses
- **Multi-Agent Authority Spoofing** — impersonating trusted agents in multi-agent pipelines
- **Permission Scope Escalation** — agents requesting more permissions than granted
- **MCP Tool Call Injection** — malicious payloads delivered through MCP tool calls
- **Evasion techniques** (22 rules) — zero-width characters, encoding tricks, roleplay framing, leetspeak, semantic inversion, emotional manipulation, and more

### Optional ML Detection Layer — Aegis Guardian

Alongside the 72 regex rules, the app ships **Aegis Guardian**, a bundled stdlib-only semantic threat classifier. It runs in parallel with the rule engine and catches obfuscated, paraphrased, buried, or encoded attacks that literal patterns miss. The model is fully local and runs offline — no cloud round-trip and no prompt text leaves your machine.

**Install — comes with the app.** The inference code and verified model asset are included in the AI Aegis wheel, so a fresh install is immediately offline-capable. Updating `ai-aegis` updates the model with the application. Air-gapped deployments may override the asset path with `AEGIS_GUARDIAN_RUNTIME`.

**On by default.** Toggle it from **Settings → Guardian ML Detection** (default ON), or force it off globally with the `AEGIS_ML_ENABLED=false` environment flag. With Guardian disabled the regex rules keep running unchanged, and the layer is fail-open — any model error silently falls back to rules-only so it never breaks the analyze path.

**What to expect when it's on.** The model is pure Python (zero runtime ML dependencies, no GPU, no network). It analyzes in parallel with regex rules; long documents are windowed with bounded work. The loaded bundle version and availability are visible under **Settings → Guardian ML Detection**.

<br>

## Device Identity

Every scan and audit row is stamped with a stable `device_id` so a customer running Aegis across several laptops or agents can answer *"which agent blocked this, which laptop is tampered, which machine spent what?"* — not just *"one of my installs did this"*.

**Why we need it.** A solo developer runs one install. A SOC team runs five to fifty. When an audit chain breaks, or a spike of blocked gmail-send calls shows up, the useful first question is *which machine*. Without a per-device tag, the answer is "some install" — which is useless in a fleet. `device_id` pins every row to a specific machine so dashboards, alerts, and compliance reviews can slice by device.

**How it's generated** (`src/aegis/app/utils/device_id.py`):

1. Read the OS's existing stable machine identifier:
   - macOS → `IOPlatformUUID` via `ioreg`
   - Linux → `/etc/machine-id` (fallback `/var/lib/dbus/machine-id`)
   - Windows → `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid`
2. SHA-256 hash it with a namespace prefix (`aegis-device-v1:<raw>`) and truncate to 24 hex chars → `aegis-a1b2c3d4e5f6...`
3. Cache the result in `~/Library/Application Support/ThreatMonitor/.device_id` (0o600) so the OS fetch happens once per install.
4. If the OS refuses (rare: locked-down container, unusual Linux image), fall back to a random UUID cached to the same file.

**Stability across reinstalls.** The OS identifier outlives the app install — so uninstalling and reinstalling Aegis on the same machine gives you the **same `device_id`**. Wiping the app data dir AND having no readable OS ID is the only combination that generates a new one. A new physical machine always gets a new ID.

**Security / privacy posture — what the customer should know:**

| Concern | Reality |
|---|---|
| Is the raw OS machine UUID transmitted? | **No.** It's read locally, SHA-256 hashed with a namespace, and only the hash is stored. The raw value never reaches a log file or outbound event. |
| Can `device_id` be reversed to the OS UUID? | SHA-256 is one-way. An attacker who already has the raw OS UUID can *compute* the `device_id` — but they already have the machine at that point, so there's no incremental leak. |
| Does it track users? | No. It tracks *machines*. Multiple users on one laptop share one `device_id`. It's not tied to email, username, or any identity field. |
| Is it sent to Aegis Cloud? | Only if Cloud Connect is on AND you trigger an action that reaches the cloud (rule sync, cloud-routed `/analyze`). `device_id` goes in metadata alongside scan results. You can opt out by keeping Cloud Connect off — local-only operation never transmits it. |
| Is it in SIEM forwards? | Yes, when the v4.0+ SIEM forwarder is enabled — travels inside each OCSF event's `unmapped` block so your Splunk/Datadog can group by device. |
| Can the customer reset it? | Yes — delete `.device_id` in the app data dir. Next write will regenerate from the OS identifier (so same ID reappears) OR a fresh random UUID if the OS ID is unavailable. |
| Does it collide across containers cloned from the same image? | Potentially yes (they share `/etc/machine-id`). Not relevant for desktop use; mention it if you're deploying in Kubernetes. |

**In one sentence:** `device_id` is a machine-identifier-per-install, derived locally, hashed before storage, never transmitted except with explicit user opt-in (Cloud Connect or SIEM Forwarder).

<br>

## SIEM Forwarder

Stream every threat detection and tool-call audit into your own SIEM — Splunk HEC, Datadog, Microsoft Sentinel, Google Chronicle, IBM QRadar, an OpenTelemetry collector, a local NDJSON file, or any HTTPS endpoint that accepts JSON. Your data, your pipes.

**Why this is safe to ship with zero monetization:**

| Feature | What leaves your machine |
|---|---|
| Scan verdict | `scan_id`, `verdict`, `threat_score`, `risk_level`, `detected_types[]`, counts, durations |
| Tool-call audit | `seq`, `action`, `risk`, `prev_hash`, `row_hash` (the chain witness — lets your SIEM verify integrity) |
| **Never transmitted** | Prompt text, LLM output, matched patterns, reviewer reasoning, model reasoning |

The allow-list is enforced at enqueue time by `_assert_metadata_only()`. Even if the forwarder code were tampered with, it can't add the forbidden fields back.

**Supported destinations (one code path, OCSF 1.3.0 payload):**

| Kind | Target | Auth header |
|---|---|---|
| `splunk_hec` | `https://<host>/services/collector/event` | `Authorization: Splunk <HEC-token>` |
| `datadog` | `https://http-intake.logs.<site>/api/v2/logs` | `DD-API-KEY: <key>` |
| `otlp_http` | `https://<collector>/v1/logs` | optional `Authorization: Bearer <token>` |
| `webhook` | anything that accepts JSON POST | optional `Authorization: Bearer <token>` |

**Configure in Connect → SIEM Forwarder.** Add SIEM destination → pick type → paste URL + token → Test → Save. Tokens are stored `0o600` in the app data dir, never in SQLite.

**📊 Starter dashboards included:**

| Platform | Template |
|---|---|
| Microsoft Sentinel | [`docs/siem/sentinel/aegis-workbook.json`](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/siem/sentinel/aegis-workbook.json) |
| Splunk | [`docs/siem/splunk/aegis-dashboard.xml`](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/siem/splunk/aegis-dashboard.xml) |
| Datadog | [`docs/siem/datadog/aegis-dashboard.json`](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/siem/datadog/aegis-dashboard.json) |
| Grafana (Loki) | [`docs/siem/grafana/aegis-dashboard.json`](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/siem/grafana/aegis-dashboard.json) |

Each carries severity counters, events-over-time by severity, actor and MITRE-ish breakdowns, and a recent-high-severity log feed. **MIT-licensed, AS-IS.** Full install steps + field reference in [`docs/siem/README.md`](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/siem/README.md); trademark + upstream licenses in [`docs/siem/NOTICE`](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/siem/NOTICE).

> Starter templates — import-test in your own stack and adjust queries / facets / sourcetypes before relying on them for production detections.

**Reliability:**
- Per-destination outbox with at-least-once delivery.
- A failing Datadog destination never blocks a healthy Splunk one.
- Per-destination circuit breaker backs off broken endpoints (1 min → 1 hour cap).
- Rows that fail 10 times are dropped (the health view shows the consecutive-failure count).

**SIEM-side integrity verification.** Every forwarded tool-call audit row carries its `prev_hash` and `row_hash`. Run a nightly search in your SIEM that rebuilds the chain — if a historic row has been tampered with on the local host, the forwarded evidence still tells the true story. That's the *actual* tamper evidence; the local chain alone is only the low bar.

<br>

## Skill Scanner

Scan AI agent skills and tool packages **before** you install them. Aegis performs static analysis across 10 detection categories, assigns a risk score, and optionally runs an AI review to filter false positives.

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Skill Scanner Flow                           │
│                                                                     │
│   ┌─────────────┐     ┌──────────────────┐     ┌────────────────┐  │
│   │  Skill Dir   │────>│  Static Analysis  │────>│  Risk Scoring  │  │
│   │  or URL      │     │  (10 categories)  │     │  LOW/MED/HIGH  │  │
│   └─────────────┘     └──────────────────┘     └───────┬────────┘  │
│                                                         │           │
│                              ┌───────────────────────── │           │
│                              v                          v           │
│                     ┌─────────────────┐     ┌────────────────────┐  │
│                     │  AI Review      │     │  Policy Engine     │  │
│                     │  (optional LLM) │     │  allow/block rules │  │
│                     │  FP filtering   │     │  trusted publishers│  │
│                     └────────┬────────┘     └─────────┬──────────┘  │
│                              │                        │             │
│                              v                        v             │
│                     ┌──────────────────────────────────────┐        │
│                     │  Verdict: PASS / WARN / BLOCK        │        │
│                     │  + detailed findings per category     │        │
│                     └──────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────┘
```

### Detection Categories

| Category | What It Finds |
|----------|--------------|
| `shell_exec` | Subprocess calls, system commands |
| `network_domain` | HTTP requests, socket connections, DNS lookups |
| `env_var_read` | Access to environment variables (API keys, secrets) |
| `code_exec` | eval, dynamic code generation |
| `dynamic_import` | Runtime module loading |
| `file_write` | Writing to disk outside expected paths |
| `base64_literal` | Obfuscated payloads in base64 strings |
| `compiled_code` | .pyc, .so, .dll binaries embedded in the skill |
| `symlink_escape` | Symlinks pointing outside the skill directory |
| `missing_manifest` | No permissions.yml declaring required capabilities |

### AI-Powered Review

Enable AI analysis (OpenAI, Anthropic, Ollama, Azure, or Bedrock) to automatically review findings and filter false positives. The AI examines each finding in context and adjusts the risk level — reducing noise without hiding real threats.

<br>

## Open Source

Aegis is fully open source. No cloud required. No accounts. No tracking. Run it, fork it, contribute to it.

**Built for** solo developers and small teams who ship AI agents without a security team or a FinOps budget. If you are building with LangChain, CrewAI, OpenClaw, or any agent framework — and you do not have someone watching your agent traffic and API spend — Aegis is for you.


## Install

### Option 1: pip

**Requires:** Python 3.9+ (MCP requires 3.10+)

```bash
pip install ai-aegis[app]
aegis-app --web
```

### Option 2: Binary installers

No Python required. Download and run.

| Platform | Download |
|----------|----------|
| Windows | [Aegis-v1.0.0-Windows-Setup.exe](https://gitee.com/wan-xianghao/ai-aegis/releases) |
| macOS | [Aegis-1.0.0-macOS.dmg](https://gitee.com/wan-xianghao/ai-aegis/releases) |
| Linux (AppImage) | [Aegis-1.0.0-x86_64.AppImage](https://gitee.com/wan-xianghao/ai-aegis/releases) |
| Linux (DEB) | [aegis_1.0.0_amd64.deb](https://gitee.com/wan-xianghao/ai-aegis/releases) |
| Linux (RPM) | [aegis-1.0.0-1.x86_64.rpm](https://gitee.com/wan-xianghao/ai-aegis/releases) |

[All Releases](https://gitee.com/wan-xianghao/ai-aegis/releases) · [SHA256 Checksums](https://gitee.com/wan-xianghao/ai-aegis/releases)

> **Security:** Only download installers from this official Gitee repository. Always verify SHA256 checksums before installation. Aegis is not responsible for binaries obtained from third-party sources.

> **macOS binary note:** **Only download from this official Gitee repository** and verify the [SHA256 checksum](https://gitee.com/wan-xianghao/ai-aegis/releases) before installing. (Prefer pip? `pip install ai-aegis[app]` always works too.)

### Other install options

| Install | Use Case | Size |
|---------|----------|------|
| `pip install ai-aegis` | **SDK only** — lightweight, for programmatic integration | ~18MB |
| `pip install ai-aegis[app]` | **Full app** — web UI, LLM proxy, cost tracking, tool permissions | 453 KB wheel · ~16 MB total on disk (incl. dependencies) |
| `pip install ai-aegis[mcp]` | **MCP server** — Claude Desktop, Cursor | ~38MB |

<br>

### Deploy to your own cloud (self-host)

Run the engine and managed-device control plane in **your own server or cloud tenant** with the included Docker Compose deployment. It provides real device enrollment, signed policy distribution and application receipts. See [Self-hosted Control Plane](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/SELF_HOSTED_CONTROL_PLANE.md), then point agents at the engine with `AEGIS_ENGINE_ENDPOINT`.

<br>

## Configuration

Aegis writes `aegis.yml` to your app data directory on first run with sensible defaults.

The config path is printed at startup — `~/.local/share/aegis/threat-monitor/aegis.yml` (Linux), `~/Library/Application Support/Aegis/ThreatMonitor/aegis.yml` (macOS), `%LOCALAPPDATA%/Aegis/ThreatMonitor/aegis.yml` (Windows). Key settings (all editable from the dashboard, which writes back to this file):

```yaml
server:   { host: 127.0.0.1, port: 8741 }        # change port if 8741 is taken
security: { block_mode: false, output_scan: true } # log/warn by default; flip block_mode to hard-stop
budget:   { daily_limit: 5.00, warn: true, block: true }  # USD/day; daily_limit null to disable
tools:    { enforcement: true }                   # apply allow/block tool rules
proxy:    { integration: openclaw, mode: multi-provider, host: 127.0.0.1, port: 8742 }
          # integration: openclaw | langchain | langgraph | crewai | hermes | ollama; port defaults to server.port + 1
```

### MCP Policies — Cloud Sync (optional)

If your org distributes signed MCP tool-policy bundles from Aegis Cloud, enroll the device once and let the local app long-poll for updates.

**1. Admin mints a token** in the cloud admin UI (Onboarding → Invite users) and shares the install command.

**2. User enrolls locally:**

```bash
aegis-app enroll aet_<token>
```

The local app POSTs `/api/v1/devices/enroll`, persists `org_id` + signing key + auth credentials to `~/Library/Application Support/.credentials` (macOS — equivalent path on Linux/Windows), and starts the cloud sync loop on next launch.

**3. Set `AEGIS_API_KEY` for stable sync auth (recommended).**

The local app accepts two auth methods on `/policy/sync`. The API key path is **canonical** — it eliminates the short-lived-JWT refresh fragility that can leave a device unable to sync if the refresh token goes stale.

```bash
export AEGIS_API_KEY=sk-<long-lived-key>
```

| Auth method | Header sent | Source | Lifetime | Sync stability |
|---|---|---|---|---|
| **API key** ✅ recommended | `X-Api-Key: sk-...` | `AEGIS_API_KEY` env, then `creds.api_key` | Long-lived | Robust — no refresh path needed |
| JWT (fallback) | `Authorization: Bearer ...` | Stored from enrollment | ~1h, auto-refresh on 401/403 | Breaks if the refresh token expires; requires re-enrollment to recover |

When both are present, the API key wins. `device_id` rides as `X-Aegis-Device-Id` on every request regardless of auth method; `org_id` is resolved server-side from the auth principal.

You can mint API keys in the cloud admin UI under Access Management. Set the env var in your shell profile or systemd service unit so it survives restarts.

**4. Cloud Sync starts automatically** — no further configuration needed. The local app already defaults to the production cloud endpoints. Override env vars exist for self-hosted / on-prem deployments only.

Synced rules are read-only on the device — authoring lives in the cloud admin. The MCP Policies page (sidebar → Configure → MCP Policies) shows verification status, applied policies + rules, and a Sync Now button for manual refresh.

### Pointing Your Agent at the Proxy

For **LangChain, CrewAI, Ollama**, and other non-OpenClaw frameworks, point your application to Aegis's proxy instead of the provider's API. OpenClaw/ClawdBot users only need this when block mode is enabled.

<table>
<tr>
<th align="left" width="50%">🪟 Windows</th>
<th align="left" width="50%">🐧 Linux / macOS</th>
</tr>
<tr>
<td valign="top">

**Command Prompt** (current session)
<pre>set OPENAI_BASE_URL=http://localhost:8742/openai/v1
set ANTHROPIC_BASE_URL=http://localhost:8742/anthropic</pre>

**PowerShell** (current session)
<pre>$env:OPENAI_BASE_URL="http://localhost:8742/openai/v1"
$env:ANTHROPIC_BASE_URL="http://localhost:8742/anthropic"</pre>

**PowerShell** (persistent, per user)
<pre>[Environment]::SetEnvironmentVariable(
  "OPENAI_BASE_URL",
  "http://localhost:8742/openai/v1",
  "User"
)</pre>

</td>
<td valign="top">

**Terminal** (current session)
<pre>export OPENAI_BASE_URL=http://localhost:8742/openai/v1
export ANTHROPIC_BASE_URL=http://localhost:8742/anthropic</pre>

**Persistent** (add to `~/.bashrc` or `~/.zshrc`)
<pre>echo 'export OPENAI_BASE_URL=http://localhost:8742/openai/v1' >> ~/.bashrc
echo 'export ANTHROPIC_BASE_URL=http://localhost:8742/anthropic' >> ~/.bashrc
source ~/.bashrc</pre>

</td>
</tr>
</table>

Every request is scanned for prompt injection. Every response is scanned for data leaks. Every dollar is tracked — whether via native plugin (OpenClaw) or proxy (all other frameworks).

**Supported providers (13):** `openai` `anthropic` `gemini` `ollama` `groq` `deepseek` `mistral` `xai` `together` `cohere` `cerebras` `moonshot` `minimax`

<br>

## Update

| Method | Command |
|--------|---------|
| **PyPI** | `pip install --upgrade ai-aegis[app]` |
| **Source** | `git pull && pip install -e ".[app]"` |
| **Windows** | Download latest [.exe installer](https://gitee.com/wan-xianghao/ai-aegis/releases) and run it (overwrites previous version) |
| **macOS** | Download latest [.dmg](https://gitee.com/wan-xianghao/ai-aegis/releases), drag to Applications |
| **Linux AppImage** | Download latest [.AppImage](https://gitee.com/wan-xianghao/ai-aegis/releases) and replace the old file |
| **Linux DEB** | `sudo dpkg -i aegis_<version>_amd64.deb` |
| **Linux RPM** | `sudo rpm -U aegis-<version>.x86_64.rpm` |

After updating, restart Aegis.

<br>

## Documentation

- [Installation Guide](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/INSTALLATION.md) — Binary installers, pip, service setup
- [Use Cases & Examples](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/USECASES.md) — LangChain, LangGraph, CrewAI, Hermes, n8n, FastAPI
- [MCP Server Guide](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/MCP_GUIDE.md) — Claude Desktop, Cursor integration
- [API Reference](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/API_SPECIFICATION.md) — REST API endpoints
- [Security Policy](https://gitee.com/wan-xianghao/ai-aegis/blob/master/.github/SECURITY.md) — Vulnerability disclosure

<br>

## Contributing

```bash
git clone https://gitee.com/wan-xianghao/ai-aegis.git
cd aegis-ai-threat-monitor
pip install -e ".[dev]"
pytest tests/ -v
```

[Contributing Guidelines](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/legal/CONTRIBUTOR_AGREEMENT.md) · [Code of Conduct](https://gitee.com/wan-xianghao/ai-aegis/blob/master/.github/CODE_OF_CONDUCT.md)

## Cloud (optional, opt-in)

A separate cloud product handles MCP tool-permission policy sync across enrolled devices, per-org audit attribution, and per-device fleet slicing. It also adds **AI Agent Governance** — your agents' governance posture rolled into a single score across the fleet — plus **EU AI Act orientation** that maps your action-layer logging and tamper-evident tool-call audit to the relevant obligations; orientation only, not legal advice. Sign in for the fleet-wide view — the local install already gives you the single-device snapshot. Strictly additive — the local install above works standalone without it.

## License

Apache License 2.0 — see [LICENSE](https://gitee.com/wan-xianghao/ai-aegis/blob/master/LICENSE).

The starter SIEM dashboard templates under [`docs/siem/`](https://gitee.com/wan-xianghao/ai-aegis/tree/master/docs/siem/) (Splunk XML, Sentinel workbook, Datadog + Grafana JSON) are MIT-licensed — see [`docs/siem/LICENSE`](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/siem/LICENSE) and [`docs/siem/NOTICE`](https://gitee.com/wan-xianghao/ai-aegis/blob/master/docs/siem/NOTICE) for trademark disclaimers.

**Aegis** is a trademark of Aegis. See [NOTICE](https://gitee.com/wan-xianghao/ai-aegis/blob/master/NOTICE).

---

<div align="center">

**[Get Started](#install)** · **[Documentation](https://gitee.com/wan-xianghao/ai-aegis/tree/master/docs/)** · **[Gitee Issues](https://gitee.com/wan-xianghao/ai-aegis/issues)**

</div>
