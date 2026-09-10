# 安全调查 Agent 启动和验收

## 本地启动

使用安装了 app 依赖的 Python 执行：

```powershell
D:\pyt\python.exe scripts/start_security_demo.py --key-file C:\secure\deepseek-key.txt
```

后端默认只监听 127.0.0.1:8741。已有 8088 前端代理可连接该后端。若 8741 已被占用，先确认占用服务，再安排重启。单独 smoke 验证无需占用该端口：

```powershell
D:\pyt\python.exe scripts/smoke_security_agent.py --key-file C:\secure\deepseek-key.txt
```

该检查使用临时数据库和合成证据，真实调用模型，报告落到 reports/delivery/agent-live-smoke.json。

## 服务端配置

优先级：AEGIS_DEEPSEEK_API_KEY → AEGIS_DEEPSEEK_API_KEY_FILE → DEEPSEEK_API_KEY。专用文件不会被通用旧环境变量覆盖。模型默认 deepseek-v4-flash，关闭思考模式。网页连接测试会消耗一次 API 请求。未配置显示 unconfigured；配置尚未测试显示 untested；真实成功后显示 online；调用失败显示 unavailable。

密钥可在**安全运营页直接输入并即时生效**（无需重启），也可继续用上面的环境变量或 `--key-file` 配置。网页写入的边界如下：**密钥路径永不返回网页；密钥本体永不返回网页，只返回末四位掩码**（如 `sk-****3f7a`）；写入、删除与连接测试三个端点都要求 UI 令牌，未携带返回 403。网页保存的密钥落在用户数据目录下的 `model_key` 文件（0600 权限），不进 SQLite，因此不会随备份或证据导出外泄。若密钥文件由启动参数 `--key-file` 提供，网页只读不改——删除操作会返回 409，请回到启动侧处理。同一张卡片上的“漂移提取”开关对应 `AEGIS_DRIFT_LLM_ENABLED`，默认关闭，状态以徽标形式常显，避免“以为开着其实没开”。

AEGIS_AGENT_MAX_CALLS 是每次后端进程生命周期内的请求上限，默认 200，包含重试。当前不是持久化金额预算，重启会重置。调查并发为 2，队列最多 8，单任务时限 180 秒。

Ubuntu Demo 可叠加 docker-compose.agent.yml，设置 AEGIS_AGENT_KEY_FILE 指向服务器私密文件，以只读 secret 挂载。Demo 镜像包含 LangGraph、PDF/DOCX 解析及中英文 Tesseract OCR；仍应在 768MB 限额下完成服务器实测。在现有 Nginx 登录认证之后提供服务。本地 UI token 是操作令牌，不是企业身份认证；不能仅凭这个 token 把 API 暴露到公网。

## 演示流程

1. 在安全运营页“模型凭据”卡片输入 DeepSeek 密钥（保存后自动跑一次双路连接测试），确认密钥徽标显示末四位掩码、漂移提取徽标为“已启用”。
2. 上传一份合成事件日志，保存返回的证据编号。
3. 填写证据编号，输入“看看这个智能体是不是被带偏了”。
4. 查看路由、证据收集、分析、报告节点及证据引用。
5. 查看报告中的 model_mode 和 degraded，再下载 Markdown 和 JSON。
6. 查询评测结果时，Agent 读取已有报告；不自动触发付费全量评测。
7. 提交明确策略 JSON，查看提案与模拟指标，人工批准或拒绝。

模型输出引用已知证据，只证明引用存在，不证明语义结论一定正确。假设和反证仍需复核。旧 benchmark 使用联合 Judge/标签请求，不能当独立提示词的两组试验。后续改善效果需要使用隔离验证集与独立测试集验证。
