# Changelog

本项目包含基于 Apache License 2.0 上游项目演进的代码，完整来源与版权归属见
[NOTICE](NOTICE) 与 [LICENSE](LICENSE)。

## 1.0.0 — 2026-08-31

**初始发布：AI Aegis（灵盾）**

### 新增（本团队二次开发增量）
- 前端中英文切换（i18n）：运行时 DOM 翻译引擎 + 中文字典，英文界面与原版逐字节一致
- 品牌重塑：AI Aegis（灵盾），包名 `ai-aegis`，CLI `aegis` / `aegis-monitor` / `aegis-mcp` / `aegis-app` / `aegis-proxy`

### 保留（上游功能，全量迁移）
- 72 条规则 + Guardian ML 检测层（`bundled AI Aegis Guardian`，Apache-2.0）
- 本地 / API / 混合三种检测模式
- 桌面应用（FastAPI + Web 前端）：威胁/规则/工具权限/成本/Agent 地图等全部页面
- Claude Code / Codex / Copilot CLI / Cursor / OpenClaw 插件 hook
- MCP 服务、SIEM 导出、实时监控与事件回放
