# 干净环境安装与启动验证

采集时间：2026-09-10
目的：验证"另一个人在自己的机器上，按 README 写的命令，能不能装上并跑起来"

## 方法

模拟陌生人的处境，而不是复用开发机已有的状态：

- **全新 venv**：`D:\pyt\python.exe -m venv venv`（Python 3.14.0）
- **从公开索引安装**：`pip install "ai-aegis[app]==1.0.2"`
- **擦掉全部密钥环境变量**：`DEEPSEEK_API_KEY`、`AEGIS_DEEPSEEK_API_KEY`、
  `AEGIS_DEEPSEEK_API_KEY_FILE`、`AEGIS_DRIFT_LLM_ENABLED`
- **用 README 写的命令启动**：`aegis-app --web`

## 1. 安装

```
$ pip install "ai-aegis[app]==1.0.2"
...
Successfully installed Pillow-12.3.0 PyYAML-6.0.3 ai-aegis-1.0.2 aiohappyeyeballs-2.7.1
aiohttp-3.14.3 aiosignal-1.4.0 aiosqlite-0.22.1 ... uvicorn-0.52.4 watchfiles-1.2.0
websockets-16.1.1 xxhash-4.0.1 yarl-1.24.5 zstandard-0.25.0
```

✅ 共 100 个包，无依赖冲突，无编译失败。Python 3.14 下全部有可用 wheel。

## 2. 启动

```
$ aegis-app --web --port 8917
```

✅ 正常启动。`/health` 返回：

```json
{"status":"healthy","version":"1.0.1",
 "database":{"connected":true,"record_count":28,"path":"...threat_intel.db"},
 "rules_loaded":{"community":108,"custom":0,"compiled_patterns":423}}
```

## 3. 无密钥时的降级

未提供任何 DeepSeek 密钥时，凭据端点如实返回未配置，不报错、不假装可用：

```json
{"key_configured":false,"key_masked":"","key_source":"none",
 "key_managed":true,"drift_llm_enabled":false}
```

✅ 陌生人拿到的是"明确告诉你没配"，而不是静默失败。

## 4. 凭据写入链路（本轮新增功能）

完整往返已验证（详见同目录 `runtime-probes.txt`）：

```
PUT  带 UI 令牌            → HTTP 200
GET  写入后                → {"key_masked":"sk-****0000","key_source":"file","drift_llm_enabled":true}
     响应中检索密钥本体       → 未出现 ✓
     响应中检索文件路径       → 未出现 ✓
DELETE 带 UI 令牌          → HTTP 200
GET  删除后                → {"key_configured":false,"key_source":"none"}
```

无令牌时三个写入端点均返回 403：

```
PUT           → 403
DELETE        → 403
POST /test    → 403
```

## 5. 前端资源

```
index.html 引用版本号：api.js?v=315  i18n-dict.js?v=5  pages/security-operations.js?v=3
security-operations.js 中 so-cred-* 元素：23 处
中文字典含：模型凭据 / 保存密钥 / 测试两条链路 / 启用漂移提取 / 移除已存密钥
```

✅ 新功能在干净安装中完整存在，含中文词条与缓存失效版本号。

## 6. 发现的问题：版本号

**安装的是 1.0.2，但除 `aegis.__version__` 外，所有入口自报 1.0.1。**
详见 `../04-audit/version-audit.md`。

| 入口 | 自报 |
|---|---|
| `pip` / dist-info | 1.0.2 |
| `aegis.__version__` | 1.0.2 ← 唯一正确 |
| `aegis.app.__version__` | 1.0.1 |
| `/health` | 1.0.1 |
| `aegis --version` | 1.0.1 |
| `aegis-app --version` | 1.0.1 |

## 7. 现场清理

测试用了合成密钥 `sk-synthetic-probe-...`，测完已删除。复查用户数据目录
`%LOCALAPPDATA%\Aegis\ThreatMonitor\`：

- `model_key` 文件：无残留 ✓
- `model_key_settings.json` sidecar：已删除 ✓
- 探针服务：已停止，8741 / 8742 / 8917 均无监听 ✓

## 结论

功能层面：**陌生人可以装上、可以跑起来、可以摸到新功能**。
唯一的阻断项是版本号自证错误，会让测试者怀疑自己装错了。
