# integration 用例分析

采集时间：2026-09-10
运行者：本次会话（Claude Code），非项目原作者

## 为什么单独拿出来

`pyproject.toml` 的 `addopts` 里写着 `-m "not integration"`，所以默认的
`pytest tests/` **不会运行**这 191 条用例。日常所说的"全绿"不包含它们。
本报告为了回答"别人能不能测"，把它们单独跑了两遍。

## 两轮结果对比

| 条件 | 结果 |
|---|---|
| 无服务在跑 | 91 failed, 33 passed, 2 skipped, 65 errors（755 秒） |
| 起了服务（8741 API + 8742 代理） | **6 failed, 128 passed, 43 errors**（784 秒） |

起服务后失败数从 91 降到 6，说明**绝大多数失败的原因是"没有服务在监听"**，
而不是产品缺陷。涉及文件只有三个，且文件名自带 `_live`：

- `tests/test_tool_audit_log_live.py`
- `tests/test_tool_permissions_api_live.py`
- `tests/unit/app/test_costs_budget.py`

无服务那轮的失败原因分布：`requests.exceptions.ConnectionError` 113 次、
`json.decoder.JSONDecodeError` 43 次。

## 起服务后仍存在的 43 个 error

全部集中在 `tests/unit/app/test_costs_budget.py`，错误都是
`json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`
——即拿到了非 JSON 响应。

根因已定位：**未知的 `/api/*` 路径返回的是 SPA 的 HTML 外壳，且状态码是 200**，
而不是 404 JSON。

```bash
$ curl -o /dev/null -w '%{http_code} %{content_type}' http://127.0.0.1:8741/api/definitely-not-a-route
200 text/html; charset=utf-8
```

这本身是一个独立于测试的 API 缺陷：任何 API 消费者打错路径，都会拿到一个
200 的 HTML 页面，而不是明确的 404。它同时也是这些用例报 `JSONDecodeError`
而不是清晰 404 的原因。

需要另行确认这些用例期望的路径是否仍然有效（例如 `/api/costs/records` 在
OpenAPI 中只登记了 `GET`）。

## 起服务后仍失败的 6 条

全部在 `tests/test_tool_permissions_api_live.py`：

| 用例 | 断言 | 实测 |
|---|---|---|
| `test_no_email_tool_is_allowed` | 名称含 send/email/smtp/mail 的工具不得为 allow | 4 个被放行：`send_input`、`send_message`、`yb_send_dm`、`yb_send_sticker` |
| `test_majority_of_tools_are_blocked_by_default` | 默认应 ≥70% 被 block | 26%（54 block / 157 allow，共 211 个） |
| `test_admin_risk_tools_mostly_blocked` | admin 类工具应多数被 block | 45 个中 11 个被 block（24%） |
| `test_proxy_reachable` | 代理应可读 | `ReadTimeout`（5 秒） |
| `test_proxy_check_endpoint_blocked_tool_via_api` | 期望 200 | 405 Method Not Allowed |
| `test_proxy_live_request_blocked_tool_returns_error` | 期望特定错误 | 405 Method Not Allowed |

### 重要前提：这是监控模式

服务是用 `--mode analyze` 启动的。README 与文档明确写着默认是
**monitor by default，block mode 需显式开启**：

> Monitor by default; opt-in block mode for hard-stop.

在这个前提下，"默认只 block 26%" 与产品自述的默认行为**是一致的**，
不能据此断言存在安全缺口。

但要如实指出一点：**这三条断言表达的是一个比产品默认更严格的安全预期**。
如果对外宣传"工具权限治理"时读者理解成"默认就会拦下外发邮件"，那实际
行为会低于这个预期。这与本次刚修的"漂移开关以为开着其实没开"属于同一类
问题——**能力的实际状态与读者预期之间的落差**。

判断这三条是「测试用例过期」还是「需要调整默认策略」，是项目方的决定，
本报告不下结论。

### 代理相关的 2 条

405 与超时指向代理的启动方式。启动日志显示：

```
[aegis config] OpenClaw integration in monitor mode — plugin handles
monitoring, proxy not started. Enable block_mode in aegis.yml to start
the proxy for active blocking.
```

即代理在监控模式下并未按测试预期的方式启动。同样需要在明确模式下复验。

## 结论

- 这 191 条不是回归，它们本来就不在默认测试集内。
- 其中绝大多数需要活服务才能跑；无服务时的红色数字不代表产品坏了。
- 剩 43 + 6 条需要在**明确模式**（monitor / block）下重新界定期望值。
- 附带发现一个独立缺陷：未知 `/api/*` 返回 200 HTML 而非 404。
