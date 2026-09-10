# Installation Guide

## Quick Installation

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
| Windows | [Aegis-v3.4.0-Windows-Setup.exe](https://github.com/Goodevenin9/ai-aegis/releases/download/v3.4.0/Aegis-v3.4.0-Windows-Setup.exe) |
| macOS | [Aegis-3.4.0-macOS.dmg](https://github.com/Goodevenin9/ai-aegis/releases/download/v3.4.0/Aegis-3.4.0-macOS.dmg) |
| Linux (AppImage) | [Aegis-3.4.0-x86_64.AppImage](https://github.com/Goodevenin9/ai-aegis/releases/download/v3.4.0/Aegis-3.4.0-x86_64.AppImage) |
| Linux (DEB) | [aegis_3.4.0_amd64.deb](https://github.com/Goodevenin9/ai-aegis/releases/download/v3.4.0/aegis_3.4.0_amd64.deb) |
| Linux (RPM) | [aegis-3.4.0-1.x86_64.rpm](https://github.com/Goodevenin9/ai-aegis/releases/download/v3.4.0/aegis-3.4.0-1.x86_64.rpm) |

[All Releases](https://github.com/Goodevenin9/ai-aegis/releases) · [SHA256 Checksums](https://github.com/Goodevenin9/ai-aegis/releases/download/v3.4.0/SHA256SUMS.txt)

> **Security:** Only download installers from this official GitHub repository. Always verify SHA256 checksums before installation.

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

For binary installers, download the latest version from [Releases](https://github.com/Goodevenin9/ai-aegis/releases/latest) and install over the existing version.

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

- **Issues:** [GitHub Issues](https://github.com/Goodevenin9/ai-aegis/issues)
- **Documentation:** [docs.](https://docs.)
