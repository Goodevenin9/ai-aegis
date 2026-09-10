# Aegis MCP Server - Complete Guide

Complete guide for setting up and using the Aegis MCP server with Claude Desktop, Claude Code, and Cursor IDE.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Available Tools](#available-tools)
3. [Platform Integration](#platform-integration)
   - [Claude Desktop](#claude-desktop)
   - [Claude Code (CLI)](#claude-code-cli)
   - [Cursor IDE](#cursor-ide)
4. [Docker Deployment](#docker-deployment)
5. [Direct Installation](#direct-installation)
6. [Configuration](#configuration)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Topics](#advanced-topics)

---

## Quick Start

### Prerequisites
- Docker installed and running
- Claude Desktop, Claude Code, or Cursor IDE installed

### Start the MCP Server

No pre-built image is published to any registry. Build it locally from the
`Dockerfile.mcp` in this repository:

```bash
git clone https://gitee.com/wan-xianghao/ai-aegis.git
cd ai-aegis
docker build -f Dockerfile.mcp -t aegis-mcp-server:latest .
```

Then point your MCP client at `docker run --rm -i aegis-mcp-server:latest`. The
server speaks MCP over **stdio**, so `-i` is required and `-d` must not be used
— see [Running It](#running-it).

Docker-free alternative: `pip install ai-aegis[mcp]` and use `python -m aegis.mcp`.

---

## Available Tools

The server exposes four MCP tools. All run locally against the Aegis
engine — no prompt or tool argument leaves the machine unless you explicitly
enable cloud/hybrid mode with an API key.

| Tool | Purpose |
|------|---------|
| `analyze_prompt` | Analyze a single prompt for prompt-injection, jailbreaks, data-exfiltration and other threats. Returns `is_threat`, `risk_score` (0-100), `threat_types`, and a recommended action (`allow` / `warn` / `review` / `block`). |
| `batch_analyze` | Analyze many prompts in one call; same verdict shape per item, with aggregate statistics. |
| `get_threat_statistics` | Summary of detections over a time window (counts by threat type, action, and trend). |
| `check_tool_permission` | Decide whether a tool/function call is permitted **before it runs**, and record the decision to the tamper-evident audit chain. |

### Standalone vs companion — does this need the local app?

| Capability | App **not** running | App running (companion) |
|---|---|---|
| **Threat + secret detection** (`analyze_prompt`, `batch_analyze`) | ✅ Works. The detection engine (195+ patterns) is bundled in the MCP package and runs **in-process, offline, no API key**. | ✅ Routed through the app's `/analyze`, so detections respect the app's Cloud Connect state and land in its timeline (and, when enrolled, the cloud fleet view). |
| `get_threat_statistics` | ✅ Local stats | ✅ |
| **Tool permissions** (`check_tool_permission`) | ⚠️ Fails open (allow-all) — the policy registry + audit chain live in the app. | ✅ Real allow/deny enforcement + tamper-evident audit. |

In short: **detection works MCP-alone, offline and keyless; allow/deny governance needs the app.** Over **stdio** (Claude Desktop and other local hosts) the server needs no API key — authentication is for the HTTP/SSE transports. Set `AEGIS_API_KEY` only when you want standalone *cloud* detection without the app; when the app is running it decides cloud-vs-local for you.

### `check_tool_permission`

This brings Aegis's **tool-permission governance** to MCP hosts. Before an
agent runs a sensitive tool (a shell command, a file write, a web fetch), the
host can ask Aegis whether the call is allowed — and every call is logged
for replay and audit, attributed to `runtime_kind="mcp"` so MCP traffic is
distinguishable from SDK and plugin traffic on the Tool Permissions and Agent
Map views.

The decision is resolved against the running local app exactly the way the
Aegis SDKs and the OpenClaw hook resolve it, with this precedence:

```
cloud-synced policy  >  local user override  >  essential-tool registry  >  default-allow
```

**Arguments:**

| Arg | Required | Description |
|-----|----------|-------------|
| `tool_id` | yes | Canonical tool identifier to check (e.g. `WebFetch`, `filesystem.write`, `shell.exec`). |
| `function_name` | no | Human-facing function name for the audit row (defaults to `tool_id`). |
| `args_preview` | no | Short, redaction-safe preview of the call arguments (truncated to 2 KB — never pass secrets). |
| `session_id` | no | Conversation/session id used to group calls on the Agent Map. |
| `record` | no | `true` (default) appends an audit row; set `false` for a dry-run policy lookup. |

**Returns:** `allowed` (bool), `action` (`allow` / `block`), `tier`
(`synced` / `override` / `essential` / `default`), `risk`, `reason`,
`is_essential`, `audited`, and `app_reachable`.

> **Fail-open by design:** if the local app is not reachable, the tool returns
> `allowed: true` with `app_reachable: false` rather than hard-failing the host —
> so a stopped app never blocks your agent. Start the app to enforce policy.

This tool needs the local Aegis app running (it serves the policy and the
audit chain). Point the server at a non-default app URL with
`AEGIS_SDK_APP_URL` (see [Configuration](#configuration)).

---

## Platform Integration

### Required Flags Reference

| Platform | Flags Required | Mode Options |
|----------|----------------|--------------|
| **Claude Desktop** | None | Default |
| **Claude Code** | `--direct-mode`, `--mode` | `production`, `development` |
| **Cursor IDE** | `--direct-mode`, `--mode` | `production`, `development` |

**⚠️ CRITICAL:** The `--mode` flag is **required** for Claude Code/Cursor. Without it, you'll get a `'str' object has no attribute 'value'` error.

---

### Claude Desktop

**Step 1:** Start the MCP server container
```bash
docker-compose up -d
```

**Step 2:** Configure Claude Desktop

Add to your config file:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "aegis": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "aegis-mcp",
        "python",
        "-m",
        "aegis.mcp"
      ]
    }
  }
}
```

**Step 3:** Restart Claude Desktop

---

### Claude Code (CLI)

**Configuration Location:** `.claude/mcp.json` in project root or `~/.claude.json` globally

```json
{
  "mcpServers": {
    "aegis": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "aegis-mcp",
        "python",
        "-m",
        "aegis.mcp",
        "--direct-mode",
        "--mode",
        "production"
      ],
      "env": {
        "AEGIS_MCP_TRANSPORT": "stdio",
        "AEGIS_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

---

### Cursor IDE

Use the same JSON configuration as Claude Code above. The config file location for Cursor is:
- Settings → MCP Servers
- Or `.cursor/mcp.json` in project root

---

## Docker Deployment

Docker is optional here. The MCP server is a **stdio** process, so the container
is a way to run it without installing Python — not a service you keep running.

### Building the Image

The image is not published to any registry. Build it from source:

```bash
git clone https://gitee.com/wan-xianghao/ai-aegis.git
cd ai-aegis
docker build -f Dockerfile.mcp -t aegis-mcp-server:latest .
```

Tag it whatever you like; `aegis-mcp-server:latest` is the name used below.

### Running It

```bash
docker run --rm -i aegis-mcp-server:latest
```

`-i` is required — the server reads JSON-RPC from stdin and writes to stdout, so
without it the container exits immediately. Do not use `-d`.

### Managing the Image

Because the container is started per session and exits with it, there is no
daemon to inspect: `docker ps`, `docker logs -f`, and `docker-compose` do not
apply. Use one-shot runs instead:

```bash
# Confirm the MCP module works inside the image
docker run --rm aegis-mcp-server:latest python -m aegis.mcp --health-check

# Open a shell
docker run --rm -it --entrypoint bash aegis-mcp-server:latest
```

### Multi-platform Build (for publishing)

If you publish this image to your own registry, build both architectures and
push under your own namespace — not one you do not control:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f Dockerfile.mcp \
  -t <your-registry>/aegis-mcp-server:latest \
  --push \
  .
```

---

## Direct Installation

### Install Without Docker

```bash
# Install the package
pip install ai-aegis[mcp]

# Or install from source
git clone https://gitee.com/wan-xianghao/ai-aegis.git
cd ai-aegis
pip install -e ".[mcp]"
```

### Configuration

With a direct (non-Docker) install you can launch the server two equivalent
ways:

- `aegis-mcp` — the installed console command, or
- `python -m aegis.mcp` — the module form (handy when several Python
  environments are on PATH and you want to pin the interpreter).

Both run the same server; use whichever your host config prefers.

**Claude Desktop:**
```json
{
  "mcpServers": {
    "aegis": {
      "command": "aegis-mcp"
    }
  }
}
```

**Claude Code/Cursor:**
```json
{
  "mcpServers": {
    "aegis": {
      "command": "aegis-mcp",
      "args": ["--direct-mode", "--mode", "production"]
    }
  }
}
```

> Prefer to pin the interpreter? Swap `"command": "aegis-mcp"` for
> `"command": "python", "args": ["-m", "aegis.mcp", ...]` — the module
> form is equivalent.

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AEGIS_API_KEY` | - | API key for cloud/hybrid mode |
| `AEGIS_MCP_MODE` | `balanced` | Server mode: `development`, `balanced`, `production` |
| `AEGIS_MCP_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `AEGIS_MCP_TRANSPORT` | `stdio` | Transport: `stdio`, `http`, `sse` |
| `AEGIS_SDK_APP_URL` | `http://127.0.0.1:8741` | Local Aegis app URL used by `check_tool_permission` to resolve policy and write audit rows. Point this at a remote/self-hosted instance if the app runs elsewhere. |

### Using .env File

Create `.env` file:
```bash
AEGIS_API_KEY=your_api_key_here
AEGIS_MCP_MODE=balanced
AEGIS_MCP_LOG_LEVEL=INFO
```

Reference in `docker-compose.yml`:
```yaml
services:
  aegis-mcp:
    env_file:
      - .env
```

---

## Troubleshooting

### Container Not Running

```bash
# Check if container exists
docker ps -a | grep aegis-mcp

# Start the container
docker-compose up -d

# Check logs for errors
docker logs aegis-mcp
```

### Connection Issues

**Claude Code timeout (30 seconds)?**
- Ensure `--direct-mode` and `--mode` flags are present
- Check container is running: `docker ps`
- Verify config file syntax (valid JSON)

### Module Not Found Errors

```bash
# Verify package is installed in container
docker exec -i aegis-mcp pip list | grep aegis

# Test module import
docker exec -i aegis-mcp python -c "import aegis.mcp; print('OK')"

# If failing, rebuild the image
docker-compose build --no-cache
```

### 'str' object has no attribute 'value' Error

**Cause:** Missing `--mode` flag in Claude Code/Cursor configuration

**Solution:** Add `--direct-mode` and `--mode production` (or `--mode development`) to your args:
```json
{
  "mcpServers": {
    "aegis": {
      "command": "aegis-mcp",
      "args": ["--direct-mode", "--mode", "production"]
    }
  }
}
```

### Configuration Not Loading

**Claude Desktop:**
1. Validate JSON syntax: `python -m json.tool < config.json`
2. Check file permissions
3. View logs in `~/Library/Logs/Claude/` (macOS) or equivalent

**Claude Code:**
1. Ensure `.claude/mcp.json` exists (or check `~/.claude.json`)
2. Restart Claude Code completely
3. Check for syntax errors in JSON

---

## Advanced Topics

### Resource Limits

Set limits in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 512M
    reservations:
      cpus: '0.25'
      memory: 128M
```

### Custom Configuration

Create `docker-compose.override.yml`:
```yaml
services:
  aegis-mcp:
    environment:
      - AEGIS_API_KEY=${MY_API_KEY}
    volumes:
      - ./my_config:/app/config
```

### Platform-Specific Notes

**macOS:**
- Docker Desktop must be running
- Check not in "Paused" state

**Windows:**
- Use Docker Desktop with WSL2 backend
- Use Windows paths for config: `%APPDATA%\Claude\claude_desktop_config.json`

**Linux:**
- Add user to docker group:
  ```bash
  sudo usermod -aG docker $USER
  newgrp docker
  ```

---

## Support

**Issues?**
1. Check container logs: `docker logs aegis-mcp`
2. Verify Docker status: `docker info`
3. Test server: `docker exec -i aegis-mcp python -m aegis.mcp --validate-only`
4. Check config file syntax
5. See platform-specific logs (Claude Desktop/Code)

**Key Files:**
- Docker: `docker-compose.yml`, `Dockerfile.mcp`
- Config: `.claude/mcp.json` (Claude Code), `.cursor/mcp.json` (Cursor), `claude_desktop_config.json` (Claude Desktop)
- Examples: `examples/mcp/.env.example`

---

## Summary

✅ **Quick Setup:** `docker-compose up -d` + configure IDE
✅ **Claude Desktop:** No special flags needed
✅ **Claude Code/Cursor:** Requires `--direct-mode --mode production`
✅ **Critical:** `--mode` flag prevents `'str' object` errors
✅ **Images:** Available on Docker Hub

For more details, see the [main README](../README.md) or [SDK documentation](SDK_USAGE.md).
