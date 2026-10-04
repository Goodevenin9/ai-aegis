# README 自相矛盾核查

采集时间：2026-09-10

## 1. 下载按钮指向空的 releases 页

同一份 README 里，两处互相打脸。

**第 87 行**（引导下载）：

```
**Or download the app:** [Windows](.../releases) · [Linux](.../releases) ·
[DEB](.../releases) · [RPM](.../releases) · [macOS](.../releases)
```

**第 465-466 行**（同一文件）：

```
> **No native installers are published.** There is no `.exe`, `.dmg`, `.deb`,
> `.rpm`, or `.AppImage` to download.
```

1.0.1 的提交信息列出了「6 处文档声称可下载二进制安装包」，但第 87 行不在其中，
  至今仍在。该行现在在 Gitee 上是可点击的。

影响：README 声称的"教程、命令、URL、按钮真实性"是交付自评项之一。
答辩现场若有人点击，会落到空的 releases 页。

## 2. 版本号标注过期

**第 54 行**：

```
> **AI Aegis (灵盾) 1.0.0** — AI 智能体的安全与可观测监控平台。
```

当前版本为 1.0.2。

## 3. 规则数口径

见同目录 `rule-count-audit.md`：README 三处写 72 条，实际 108 条。

| 位置 | 内容 |
|---|---|
| README:14 | "72 rules + Guardian ML" |
| README:55 | "72 条规则 + Guardian ML 检测层" |
| README:164 | "72 rules covering the OWASP LLM Top 10" |

## 汇总

| # | 位置 | 问题 | 建议改法 |
|---|---|---|---|
| 1 | README:87 | 5 个下载按钮指向空的 releases 页 | 删除该行，或改为"源码由 Gitee 托管，安装走 pip" |
| 2 | README:54 | 版本号停留在 1.0.0 | 改为 1.0.2（或随 1.0.3 一并更新） |
| 3 | README:14 / 55 / 164 | 72 条规则 | 改为 108 条 |
