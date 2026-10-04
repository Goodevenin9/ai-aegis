# AI Aegis 测试打包报告

**采集日期**：2026-09-10
**被测代码**：commit `4acffee7cd9ce74171cd6f51861b7328128bd42c`，版本 1.0.2
**运行者**：Claude Code（本次会话），**不是项目原作者**

---

## 先读这一段：本报告里三类材料的可信度不同

| 标记 | 含义 |
|---|---|
| 🟢 **本次实测** | 2026-09-10 本次会话现场跑出来的，原始输出在对应目录 |
| 🟡 **历史归档** | 从 `reports/` 原样搬来的既有报告，**不是本次产出的证据** |
| 🔴 **未验证** | 已知仍需验证、本次没能完成的项目，列在末尾 |

把 🟡 当成 🟢 是最容易犯的错，所以目录名直接标了 `preexisting/`。

---

## 目录

```
00-summary.json                    机器可读汇总
01-unit-tests/                     🟢 单元测试原始输出
  pytest-full.txt                    全量 1071 条
  pytest-credentials.txt             本次新增的凭据功能 8 条
  pytest-integration.txt             无服务时跑 integration 标记用例
  pytest-integration-with-server.txt 起服务后重跑
02-fresh-install/                  🟢 干净环境安装
  install-transcript.md              安装与启动全过程
  runtime-probes.txt                 运行时端点探针原始记录
03-benchmarks/
  offline-replay/                  🟢 本次跑的离线基准重放
  preexisting/                     🟡 历史报告归档（4 份）
04-audit/                          🟢 本次核查发现
  version-audit.md                   版本号自证错误
  rule-count-audit.md                规则数口径错误
  readme-contradictions.md           README 自相矛盾
  integration-tests.md               integration 用例分析
  live-server-startup.log            起服务时的启动日志
```

---

## 一、单元测试 🟢

```bash
pytest tests/
```

```
1071 passed, 6 skipped, 191 deselected in 136.55s
```

**注意 191 deselected**：`pyproject.toml` 的 `addopts` 含 `-m "not integration"`，
这 191 条默认不跑。日常说的"全绿"不包含它们。它们单独的结果见第四节。

本次新增的凭据功能专项：

```bash
pytest tests/unit/app/test_model_credentials_routes.py -v
```

```
8 passed in 4.24s
```

## 二、干净环境安装 🟢

方法：全新 venv（Python 3.14）→ 从公开索引装 `ai-aegis[app]==1.0.2` →
**擦掉所有密钥环境变量** → 用 README 写的 `aegis-app --web` 启动。

| 检查项 | 结果 |
|---|---|
| 安装 100 个依赖 | ✅ 无冲突、无编译失败 |
| 启动 + `/health` | ✅ `healthy` |
| 无密钥时降级 | ✅ 如实返回 `key_source: "none"` |
| 凭据写入往返 | ✅ `PUT 200 → sk-****0000 → DELETE 200` |
| 响应是否泄漏密钥本体 | ✅ 未出现 |
| 响应是否泄漏文件路径 | ✅ 未出现 |
| 无令牌写入 | ✅ 三个端点均 403 |
| 前端凭据卡与中文词条 | ✅ 完整存在 |
| 现场清理 | ✅ 无残留，服务已停 |

**结论：功能层面，陌生人可以装上、跑起来、并摸到新功能。**

唯一的阻断项是版本号（下面第三节）。

## 三、Benchmark 🟢 + 🟡

### 3.1 本次离线重放 🟢

```bash
scripts/run_external_benchmarks.py --benchmarks injecagent agentharm
```

未启用 `--live-deepseek`，不执行任何候选工具，`llm_calls: 0`。

**injecagent**（1071 例：攻击 1054 / 正常 17）

| 方案 | 攻击检出率 | 正常误报率 | F1 |
|---|---:|---:|---:|
| always_allow | 0.00% | 0.00% | 0.00% |
| always_block | 100.00% | 100.00% | 99.20% |
| aegis_single_turn_local | 4.84% | 0.00% | 9.23% |
| five_stage_rules | 0.00% | 0.00% | 0.00% |
| five_stage_semantic | 100.00% | 0.00% | 100.00% |

**agentharm_public**（352 例：攻击 176 / 正常 176）

| 方案 | 攻击检出率 | 正常误报率 | F1 |
|---|---:|---:|---:|
| always_allow | 0.00% | 0.00% | 0.00% |
| always_block | 100.00% | 100.00% | 66.67% |
| aegis_single_turn_local | 0.00% | 0.00% | 0.00% |
| five_stage_rules | 0.00% | 0.00% | 0.00% |
| five_stage_semantic | 0.00% | 0.00% | 0.00% |

**必须同时读的四条口径**：

1. `five_stage_semantic` 用**上游标签**当语义信号，代表"语义提取完全正确时的
   上界"，**不是真实模型表现**。injecagent 的 100% 不能当作实际检出率宣传。
2. 本次 `deepseek_judge_live` 与 `five_stage_immunity` **未运行**（无付费 API 授权）。
3. `agentharm_public` 与历史报告里的 `v2-explicit-harm` 是**不同变体**，
   两边数字不可互相引用。本次 agentharm_public 全部 Aegis 方案为 0%。
4. 本轮跑在 **dirty worktree** 上，commit 不能唯一标识代码，
   以报告里的 `implementation_sha256` 为准。

### 3.2 历史归档 🟡

`preexisting/` 下 4 份，均为既有报告原样拷贝，**非本次产出**：

| 目录 | 生成时间 | commit | dirty |
|---|---|---|---|
| external-benchmarks | 2026-09-09 15:27 | 9f27ae10 | 是 |
| external-benchmarks-explicit-harm | 2026-09-10 03:54 | ef38b510 | 是 |
| external-benchmarks-smoke | 2026-09-09 15:12 | 9f27ae10 | 是 |
| external-benchmarks-smoke-nonthinking | 2026-09-09 15:14 | 9f27ae10 | 是 |

两个 commit 均可在本仓库历史中查到。但四份都标记 `dirty=True`，
即运行时工作区有未提交改动。

## 四、integration 用例 🟢（含未决项）

默认测试集不含这 191 条，为回答问题单独跑了两遍：

| 条件 | 结果 |
|---|---|
| 无服务在跑 | 91 failed, 33 passed, 65 errors |
| 起了服务 | **6 failed, 128 passed, 43 errors** |

起服务后失败从 91 降到 6，说明绝大多数失败原因是"没有服务监听"，
不是产品缺陷。

**但仍剩 6 + 43 条需要项目方在明确模式下重新界定期望值**，
详见 `04-audit/integration-tests.md`。其中包含 3 条比产品默认更严格的
安全不变量断言（如"默认应 ≥70% 工具被 block"，实测 26%）。

⚠️ 但要注意：服务是用 `--mode analyze` 启动的，而产品文档明确写着
**monitor by default、block mode 需显式开启**。在这个前提下，
26% 与产品自述的默认行为是一致的，**不能据此断言存在安全缺口**。

## 五、本次核查发现的四个问题 🟢

| # | 严重度 | 问题 | 证据 |
|---|---|---|---|
| 1 | **高** | 1.0.2 版本号只改了 5 处中的 1 处，`/health` 与两个 CLI 仍自报 1.0.1 | `04-audit/version-audit.md` |
| 2 | 中 | README 三处写 72 条规则，实际 108 条 | `04-audit/rule-count-audit.md` |
| 3 | 中 | README:87 下载按钮指向空 releases 页，同文件 465 行又说不存在二进制包 | `04-audit/readme-contradictions.md` |
| 4 | 中 | 未知 `/api/*` 路径返回 HTTP 200 HTML 而非 404 JSON | `04-audit/integration-tests.md` |

问题 1 的修复代价需要单独说明：**PyPI 同版本内容不可修改，
修正版本号必须发布 1.0.3**。

## 六、未验证项 🔴

以下是已知仍未验证的，**不要在答辩中当作已完成**：

- **chain-a 的 `allow → confirm → block`** —— 需要真实有效的 DeepSeek 密钥。
  本机密钥返回 HTTP 401，语义标签累积不起来，本次未能确认。
- **Docker 容器启动** —— 本机无 Docker CLI，需在 Ubuntu 主机执行。
- **agentdojo 数据集重放** —— 需要 `--agentdojo-root` 参数，本机未配置。
- **`deepseek_judge_live` / `five_stage_immunity` 基线** —— 本次未运行。
- **README 声称的二进制安装包** —— 未实际下载验证，但 releases 页为空。

## 七、可复现性说明

本报告中 🟢 部分均可复现，但有两个环境依赖：

1. **benchmark 需要 `raw.githubusercontent.com`**。本机网络对它的访问是
   **间歇性**的：本次探测请求成功、随后一次请求失败。命中
   `03-benchmarks/offline-replay/source-cache/` 中的缓存后可完全离线复现。
   更换机器时需先预热该缓存。
2. **integration 用例需要服务在跑**。启动方式：
   ```bash
   PYTHONPATH=src python -m aegis.app.main --web --port 8741 --proxy --mode analyze
   ```
   注意 `PYTHONPATH=src`——直接 `python -m aegis.app.main` 在未安装的
   工作区会报 `No module named 'aegis'`。
