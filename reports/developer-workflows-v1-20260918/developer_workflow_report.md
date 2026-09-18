# AI Aegis 真实开发工作流基准报告

- 数据集：`developer_workflows_v1`
- 样本：370（日常开发 300、合法敏感 40、危险控制 30）
- SHA256：`e820d34f42dbe25d045d52c1e59f77c27358cd8402e963a5f3435fd680ed2a6e`
- 方法：仅离线回放工具调用，不执行任何命令，不调用 LLM。

## 总体结果

| 策略配置 | 日常干扰率 | 日常硬阻断率 | 敏感操作复核率 | 危险行为保护率 |
|---|---:|---:|---:|---:|
| current_no_manifest | 75.00% | 21.67% | 80.00% | 100.00% |
| local_developer_manifest | 16.67% | 3.33% | 10.00% | 70.00% |
| recommended_developer_manifest | 0.00% | 0.00% | 0.00% | 70.00% |

## 宿主解释

Claude Code 将 `confirm` 显示为询问；当前 Codex 适配器和 Headless 模式会将 `confirm` 视为阻断。
因此表中的日常干扰率，在 Codex/Headless 上等同于有效阻断率。

## 每种配置的动作分布

### current_no_manifest

Current secure default: only file_read is implicitly allowed.

| 样本层级 | Allow | Confirm | Block |
|---|---:|---:|---:|
| routine | 75 | 160 | 65 |
| sensitive | 8 | 32 | 0 |
| dangerous | 0 | 9 | 21 |

### local_developer_manifest

Project read/write and local shell are declared; network remains reviewable.

| 样本层级 | Allow | Confirm | Block |
|---|---:|---:|---:|
| routine | 250 | 40 | 10 |
| sensitive | 36 | 4 | 0 |
| dangerous | 9 | 0 | 21 |

### recommended_developer_manifest

Project development capabilities are declared; egress policy must scope destinations.

| 样本层级 | Allow | Confirm | Block |
|---|---:|---:|---:|
| routine | 300 | 0 | 0 |
| sensitive | 40 | 0 | 0 |
| dangerous | 9 | 0 | 21 |

## 本轮发现

1. 无 Manifest 时，300 个日常步骤中有 225 个被 Confirm/Block，真实开发干扰过高。
2. 推荐开发 Manifest 可消除本集合中的日常管线干扰，但它只是能力级放行，不能替代命令、目标和外联范围策略。
3. 推荐 Manifest 下仍有 40 个合法敏感动作未触发复核，包括发布、推送、集群、基础设施和项目外写入。
4. 推荐 Manifest 下有 9 个高风险混淆执行控制样本未触发干预；确定性 Critical 规则仍被保留。
5. 下一步应增加真正的 Audit 模式，并为 shell/network 增加动作级与目标级策略，而不是继续扩大 Capability 白名单。

## 解释边界

这是一套项目内工程回归集，不是第三方公共 Benchmark，也不是生产环境误报率证明。
它用于回答常见开发工具调用在不同 Manifest 下是否会被干预，并为后续采集真实匿名开发轨迹提供固定基线。
