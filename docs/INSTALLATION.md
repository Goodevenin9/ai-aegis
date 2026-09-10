# Installation Guide

## Quick Installation

### Option 1: pip

**Requires:** Python 3.9+ (MCP requires 3.10+)

```bash
pip install ai-aegis[app]
aegis-app --web
```

### Option 2: From source

```bash
git clone https://gitee.com/wan-xianghao/ai-aegis.git
cd ai-aegis
pip install -e ".[app]"
aegis-app --web
```

> **No native installers are published.** There is no `.exe`, `.dmg`, `.deb`,
> `.rpm`, or `.AppImage` to download. They are produced by
> [`build-installers.yml`](https://gitee.com/wan-xianghao/ai-aegis/blob/master/.github/workflows/build-installers.yml),
> which runs on GitHub Actions — and this project is hosted on Gitee, which does
> not execute them. `pip install ai-aegis[app]` is the supported path on every
> platform and needs nothing beyond Python.

---

## Other install options

| Install | Use Case | Size |
|---------|----------|------|
| `pip install ai-aegis[app]` | **Local app** — dashboard, LLM proxy, self-hosted | ~60MB |
| `pip install ai-aegis` | **SDK only** — lightweight, for programmatic integration | ~18MB |
| `pip install ai-aegis[mcp]` | **MCP server** — Claude Desktop, Cursor | ~38MB |

---

## Verifying Installation

### Local app

After installing with `[app]`, launch the dashboard:

```bash
aegis-app --web
```

The app opens at `http://localhost:8741` with the dashboard, integrations, and threat analytics.

### SDK only

```python
from aegis import AegisClient

client = AegisClient()
result = client.analyze("Hello, how are you?")

print(f"Is threat: {result.is_threat}")
print(f"Risk score: {result.risk_score}")
```

### MCP server

```bash
python -m aegis.mcp --health-check
```

Expected output:
```
Overall Status: HEALTHY
   Analyzer: HEALTHY
   Performance: OK
   Rules: 15 files loaded with 518 patterns
```

---

## System Requirements

- **Python:**
  - SDK and Local app: 3.9 or higher
  - **MCP Server: 3.10 or higher** (required for `[mcp]` extra)
  - Tested on: 3.9, 3.10, 3.11, 3.12
- **OS:** Linux, macOS, Windows
- **Memory:** Minimum 512MB RAM (1GB+ recommended for MCP server)

---

## Dependencies

### Core Dependencies (always installed)
- `PyYAML>=5.1` - YAML parsing for threat detection rules
- `requests>=2.25.0` - HTTP client for API mode
- `aiohttp>=3.12.14` - Async HTTP client
- `typing-extensions>=4.0.0` - Type hints support

### App Dependencies (`[app]`)
- `pywebview>=5.0` - Cross-platform webview
- `FastAPI>=0.100.0` - Local API server
- `uvicorn>=0.20.0` - ASGI server
- `SQLAlchemy>=2.0.0` - Database ORM
- `aiosqlite>=0.19.0` - Async SQLite
- `httpx>=0.24.0` - Async HTTP client

### MCP Dependencies (`[mcp]`)
- `mcp>=0.1.0` - Model Context Protocol library
- `fastmcp>=0.1.0` - FastMCP server framework

---

## Troubleshooting

### Issue: Import errors after installation

**Symptom:**
```python
ImportError: No module named 'aegis'
```

**Solutions:**
1. Ensure you're in the correct Python environment:
   ```bash
   which python
   pip list | grep aegis
   ```

2. Reinstall the package:
   ```bash
   pip install --force-reinstall ai-aegis[app]
   ```

3. Check Python version:
   ```bash
   python --version  # Should be 3.9 or higher
   ```

### Issue: MCP dependencies not found

**Symptom:**
```python
ImportError: No module named 'mcp'
```

**Solution:**
```bash
pip install ai-aegis[mcp]
```

### Issue: Permission errors during installation

**Symptom:**
```
ERROR: Could not install packages due to an OSError: [Errno 13] Permission denied
```

**Solutions:**
```bash
# Option 1: Use --user flag
pip install --user ai-aegis[app]

# Option 2: Use virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install ai-aegis[app]
```

---

## Virtual Environment Setup (Recommended)

```bash
# Create virtual environment
python -m venv aegis-env

# Activate it
source aegis-env/bin/activate  # On Linux/macOS
# OR
aegis-env\Scripts\activate  # On Windows

# Install
pip install ai-aegis[app]

# Launch
aegis-app --web
```

---

## Upgrading

```bash
# pip
pip install --upgrade ai-aegis[app]

# Source
git pull && pip install -e ".[app]"
```

One of the two commands above is the whole update. There are no binary
installers to download — see [Option 2](#option-2-from-source).

After updating, restart Aegis.

---

## Uninstallation

```bash
pip uninstall ai-aegis
```

---

## Next Steps

1. **Getting Started:** See [GETTING_STARTED.md](GETTING_STARTED.md) for setup and configuration
2. **Use Cases:** See [USECASES.md](USECASES.md) for LangChain, CrewAI, n8n integration examples
3. **MCP Setup:** See [MCP_GUIDE.md](MCP_GUIDE.md) for Claude Desktop and Cursor configuration
4. **API Reference:** See [API_SPECIFICATION.md](API_SPECIFICATION.md) for REST API endpoints

## Support

- **Issues:** [Gitee Issues](https://gitee.com/wan-xianghao/ai-aegis/issues)
- **Documentation:** [docs.](https://docs.)
