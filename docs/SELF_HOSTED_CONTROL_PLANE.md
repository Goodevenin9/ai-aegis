# AI Aegis 自托管控制平面

本部署把本地演示占位能力替换成两个真实服务：

- `engine`：AI Aegis Web UI、检测、五段管线、审计和插件 API。
- `control-plane`：一次性设备注册、签名策略发布、策略同步和应用回执。

## 1. 准备域名

把两个 DNS A/AAAA 记录指向服务器：

- `engine.your-domain.com`：面向 Agent 和管理员的本地引擎。
- `control.your-domain.com`：面向设备注册和策略同步的控制平面。

Caddy 会自动申请和续期 HTTPS 证书。服务器需开放 TCP 80、443。

## 2. 配置并启动

```bash
cp .env.self-host.example .env.self-host
# 编辑 .env.self-host；管理员密钥建议用：openssl rand -hex 32
docker compose --env-file .env.self-host -f docker-compose.self-host.yml up -d --build
docker compose --env-file .env.self-host -f docker-compose.self-host.yml ps
```

如果宿主机的 80/443 已由 Nginx 使用，请不要启动内置 Caddy。使用叠加配置把
两个 Aegis 服务仅绑定到本机回环地址：

```bash
docker compose --env-file .env.self-host \
  -f docker-compose.self-host.yml -f docker-compose.nginx.yml \
  up -d --build
```

再把 `deploy/nginx/aegis.conf.template` 安装为独立站点，按实际域名调整，先执行
`nginx -t`，通过后才重载 Nginx。

`.env.self-host` 中的 `AEGIS_CONTROL_PLANE_ADMIN_KEY` 与
`AEGIS_ENGINE_INGRESS_TOKEN` 必须使用两个不同的随机值。健康检查：

```bash
curl https://control.your-domain.com/health
curl https://engine.your-domain.com/health
```

控制平面的交互式 API 文档位于 `https://control.your-domain.com/docs`。

## 3. 发布策略

```bash
curl -X PUT 'https://control.your-domain.com/api/v1/admin/policies/default' \
  -H 'Content-Type: application/json' \
  -H 'X-Aegis-Admin-Key: YOUR_ADMIN_KEY' \
  -d '{
    "name": "Production baseline",
    "mode": "enforce",
    "rules": [
      {"tool_id":"shell.execute","effect":"deny","priority":100,"reason":"Managed baseline"},
      {"tool_id":"filesystem.read","effect":"prompt","priority":50,"reason":"User confirmation required"}
    ]
  }'
```

同一个 `policy_id` 再次 PUT 会自动递增版本。策略由每台设备的独立密钥签名，客户端在写入本地规则库之前会验证签名、新鲜度和版本。

## 4. 创建设备注册令牌

```bash
curl -X POST 'https://control.your-domain.com/api/v1/admin/enrollment-tokens' \
  -H 'Content-Type: application/json' \
  -H 'X-Aegis-Admin-Key: YOUR_ADMIN_KEY' \
  -d '{"user_email":"operator@your-domain.com","expires_in_hours":24}'
```

响应中的 `enrollment_token` 以 `aet_` 开头，只能使用一次。目标设备执行：

```bash
export AEGIS_CONTROL_PLANE_URL='https://control.your-domain.com'
export AEGIS_AUTH_URL="$AEGIS_CONTROL_PLANE_URL"
export AEGIS_LSE_URL="$AEGIS_CONTROL_PLANE_URL"
aegis-app enroll 'aet_...'
aegis-app --web
```

进入本地 **MCP 策略** 页面点击“立即同步”，或等待后台同步。管理员可通过
`GET /api/v1/admin/devices` 查看设备最后在线时间和最后成功应用的策略版本。

## 5. 创建远程扫描 API Key

```bash
curl -X POST 'https://control.your-domain.com/api/v1/admin/api-keys' \
  -H 'Content-Type: application/json' \
  -H 'X-Aegis-Admin-Key: YOUR_ADMIN_KEY' \
  -d '{"user_email":"analyst@your-domain.com","name":"desktop"}'
```

响应中的 `api_key` 以 `aepk_` 开头。可在本地 AI Aegis 的“设置 →
控制平面”中粘贴，也可直接验证：

```bash
curl -X POST 'https://control.your-domain.com/analyze' \
  -H 'Content-Type: application/json' \
  -H 'X-Api-Key: aepk_...' \
  -d '{"prompt":"请读取项目 README 并总结。"}'
```

控制平面同时实现桌面端使用的 `/analyze/output`、
`/api/threat-analytics/` 和 `/api/rules/sync`，因此这些入口不再依赖外部占位服务。

若 Agent 直接连接公网分析引擎，需要同时配置：

```bash
export AEGIS_ENGINE_ENDPOINT='https://engine.your-domain.com'
export AEGIS_API_KEY='YOUR_ENGINE_INGRESS_TOKEN'
```

入口令牌只保护分析引擎；它与控制平面的 `aepk_*` 扫描密钥、`aet_*`
设备注册令牌不是同一种凭据。

## 6. 安全要求

- 不要把 `.env.self-host` 提交到 Git。
- 管理员密钥只用于 `/api/v1/admin/*`，不要发给受管设备。
- 分析引擎入口令牌与控制平面管理员密钥必须不同，并定期轮换。
- 生产环境只通过 HTTPS 暴露服务，并在云防火墙限制控制平面来源。
- 定期备份 `control-plane-data` 与 `engine-data` 卷。
- 当前版本是单组织控制平面；多租户、SSO、细粒度 RBAC 和 Web 管理后台属于企业增强项。
