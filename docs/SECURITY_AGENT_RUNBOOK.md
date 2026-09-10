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

优先级：AEGIS_DEEPSEEK_API_KEY → AEGIS_DEEPSEEK_API_KEY_FILE → DEEPSEEK_API_KEY。专用文件不会被通用旧环境变量覆盖。模型默认 deepseek-v4-flash，关闭思考模式。网页连接测试会消耗一次 API 请求。未配置显示 unconfigured；配置尚未测试显示 untested；真实成功后显示 online；调用失败显示 unavailable。配置文件路径和密钥不返回网页。

AEGIS_AGENT_MAX_CALLS 是每次后端进程生命周期内的请求上限，默认 200，包含重试。当前不是持久化金额预算，重启会重置。调查并发为 2，队列最多 8，单任务时限 180 秒。

Ubuntu Demo 可叠加 docker-compose.agent.yml，设置 AEGIS_AGENT_KEY_FILE 指向服务器私密文件，以只读 secret 挂载。Demo 镜像包含 LangGraph、PDF/DOCX 解析及中英文 Tesseract OCR；仍应在 768MB 限额下完成服务器实测。在现有 Nginx 登录认证之后提供服务。本地 UI token 是操作令牌，不是企业身份认证；不能仅凭这个 token 把 API 暴露到公网。

## 演示流程

1. 在安全运营页检查模型状态并点击连接测试。
2. 上传一份合成事件日志，保存返回的证据编号。
3. 填写证据编号，输入“看看这个智能体是不是被带偏了”。
4. 查看路由、证据收集、分析、报告节点及证据引用。
5. 查看报告中的 model_mode 和 degraded，再下载 Markdown 和 JSON。
6. 查询评测结果时，Agent 读取已有报告；不自动触发付费全量评测。
7. 提交明确策略 JSON，查看提案与模拟指标，人工批准或拒绝。

模型输出引用已知证据，只证明引用存在，不证明语义结论一定正确。假设和反证仍需复核。旧 benchmark 使用联合 Judge/标签请求，不能当独立提示词的两组试验。后续改善效果需要使用隔离验证集与独立测试集验证。
