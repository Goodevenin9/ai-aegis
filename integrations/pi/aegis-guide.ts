/**
 * Aegis × pi —— 上层层集成扩展（完整版）
 * ------------------------------------------------------------------
 * 作用：
 *  1) 把 Aegis 的 /security-operations 与 /runtime 能力暴露成 pi 工具
 *  2) 把 pi 的每一轮输入 / 每一次工具调用，喂回 Aegis 的运行时治理与审计：
 *       - input      → POST /runtime/intent            （意图基线）
 *       - tool_call  → POST /runtime/pretool/decide    （五阶段裁决 + before_tool_call 落库）
 *       - tool_result→ POST /runtime/events            （after_tool_call 落库）
 *
 * 运行方式（禁用内置工具，避免模型碰文件系统）：
 *   export AEGIS_BASE_URL=http://127.0.0.1:8741
 *   export AEGIS_UI_TOKEN=<UI token>          # 写操作需要
 *   export AEGIS_APPROVER=<操作人标识>         # 审批人，绝不来自模型
 *   pi --no-builtin-tools -e ./aegis-guide.ts --model deepseek/deepseek-chat
 *
 * 对应 Aegis 源码：
 *   src/aegis/app/server/routes/security_operations.py
 *   src/aegis/app/server/routes/runtime_pipeline.py
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

// ---------------------------------------------------------------------------
// 配置
// ---------------------------------------------------------------------------
const CFG = {
  base: (process.env.AEGIS_BASE_URL ?? "http://127.0.0.1:8741").replace(/\/$/, ""),
  // Aegis 的应用级挂载前缀（app.py 里 include_router(..., prefix="/api")）
  api: (process.env.AEGIS_API_PREFIX ?? "/api").replace(/\/$/, ""),
  token: process.env.AEGIS_UI_TOKEN ?? "",
  approver: process.env.AEGIS_APPROVER ?? "pi-operator",
  runtimeKind: process.env.AEGIS_RUNTIME_KIND ?? "pi",
  // 本会话声明的能力 → decide 的 allowed_capabilities。与 Aegis Claude Code
  // 插件的 AEGIS_SESSION_CAPABILITIES 同义。例："file_read,unknown_tool"。
  // 留空 = 安全默认（只信任 file_read；未知工具一律确认）。
  capabilities: (process.env.AEGIS_SESSION_CAPABILITIES ?? "")
    .split(/[,\s]+/)
    .filter(Boolean),
  // 自托管：若 Aegis 设了 AEGIS_INGRESS_TOKEN，则所有请求带上 X-Api-Key
  ingress: process.env.AEGIS_INGRESS_TOKEN ?? "",
  // Aegis 不可达时的行为：open=放行(与 Aegis 插件 fail-open 一致) / closed=拦截
  failMode: (process.env.AEGIS_PI_FAIL_MODE ?? "open") as "open" | "closed",
};

/** 这些工具自己做“强确认”，因此 tool_call 钩子不再重复弹窗（但仍服从 block） */
const SELF_GATED = new Set([
  "aegis_submit_run",
  "aegis_resume_run",
  "aegis_cancel_run",
  "aegis_run_evaluation",
  "aegis_grant_trust",
  "aegis_transition_antibody",
  "aegis_create_memory",
]);

// ---------------------------------------------------------------------------
// HTTP 帮助函数
// ---------------------------------------------------------------------------
type AegisReq = { path: string; method?: string; body?: unknown; token?: boolean };

async function aegis({ path, method = "GET", body, token = false }: AegisReq): Promise<any> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (CFG.ingress) headers["X-Api-Key"] = CFG.ingress;
  if (token) {
    if (!CFG.token) throw new Error("AEGIS_UI_TOKEN 未设置，无法执行写操作");
    headers["X-Aegis-UI-Token"] = CFG.token;
  }
  const res = await fetch(`${CFG.base}${CFG.api}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let data: any;
  try {
    data = JSON.parse(text);
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : JSON.stringify(data).slice(0, 300);
    throw new Error(`Aegis ${method} ${path} → ${res.status} ${detail}`);
  }
  return data;
}

async function aegisText(path: string, token = false): Promise<string> {
  const headers: Record<string, string> = {};
  if (CFG.ingress) headers["X-Api-Key"] = CFG.ingress;
  if (token && CFG.token) headers["X-Aegis-UI-Token"] = CFG.token;
  const res = await fetch(`${CFG.base}${CFG.api}${path}`, { headers });
  const text = await res.text();
  if (!res.ok) throw new Error(`Aegis GET ${path} → ${res.status}`);
  return text;
}

const table = (columns: string[], rows: unknown[][]) => ({ columns, rows });

function sid(ctx: any): string {
  try {
    return String(ctx?.sessionManager?.getSessionId?.() ?? "pi-local").slice(0, 128);
  } catch {
    return "pi-local";
  }
}

// ---------------------------------------------------------------------------
// 扩展主体
// ---------------------------------------------------------------------------
export default function (pi: ExtensionAPI) {
  // ========== 工具注册用的极简工厂 ==========
  type ToolDef = {
    name: string;
    label: string;
    description: string;
    parameters: any;
    token?: boolean;
    run: (p: any, ctx: any) => Promise<{ content: any[]; details: any }>;
  };
  const reg = (def: ToolDef) =>
    pi.registerTool({
      name: def.name,
      label: def.label,
      description: def.description,
      parameters: def.parameters,
      async execute(_id: string, p: any, _signal: any, _onUpdate: any, ctx: any) {
        const result = await def.run(p, ctx);
        // details.table 只给前端渲染；模型只能看到 content。
        // 因此把表格行以文本形式追加进 content，否则模型看不见明细。
        const tbl = (result as any)?.details?.table;
        if (tbl && Array.isArray(tbl.columns) && Array.isArray(tbl.rows) && tbl.rows.length) {
          const CAP = 100;
          const shown = tbl.rows.slice(0, CAP);
          const head = tbl.columns.join(" | ");
          const body = shown
            .map((row: unknown[]) => row.map((v) => (v === null || v === undefined ? "" : String(v))).join(" | "))
            .join("\n");
          const more = tbl.rows.length > CAP ? `\n…（另有 ${tbl.rows.length - CAP} 行未展示）` : "";
          const block = (result.content || []).find((c: any) => c.type === "text");
          if (block) block.text += `\n\n${head}\n${body}${more}`;
        }
        return result;
      },
    });

  const text = (s: string, details: any = {}) => ({ content: [{ type: "text" as const, text: s }], details });

  // =====================================================================
  // 一、只读工具
  // =====================================================================

  reg({
    name: "aegis_search_knowledge",
    label: "Aegis 知识检索",
    description: "检索 Aegis 本地知识库（安全制度 / 事件 / 规则 / 安全知识），返回带引用的片段。",
    parameters: Type.Object({
      query: Type.String({ description: "检索问题" }),
      document_types: Type.Optional(
        Type.Array(Type.String(), {
          description: "security_policy / incident / rule / security_knowledge",
        }),
      ),
      limit: Type.Optional(Type.Number({ description: "返回条数 1-20，默认 5" })),
    }),
    async run(p) {
      const r = await aegis({
        path: "/security-operations/rag/search",
        method: "POST",
        body: { query: p.query, document_types: p.document_types ?? [], limit: p.limit ?? 5 },
      });
      const rows = (r.results ?? []).map((x: any) => [
        x.chunk_id,
        typeof x.score === "number" ? x.score.toFixed(3) : x.score,
        x.document_type,
        x.citation,
      ]);
      // 检索片段正文必须进 content，模型才能据此回答（表格只给 UI）。
      const snippets = (r.results ?? [])
        .map((x: any, i: number) => `[${i + 1}] ${x.citation}\n${String(x.text ?? "").slice(0, 800)}`)
        .join("\n\n");
      return {
        content: [{ type: "text" as const, text: `命中 ${r.total} 条。\n\n${snippets || "（无片段）"}` }],
        details: { table: table(["chunk_id", "score", "type", "citation"], rows), raw: r },
      };
    },
  });

  reg({
    name: "aegis_list_evidence",
    label: "Aegis 证据列表",
    description: "列出已上传的证据条目（含 500 字预览）。",
    parameters: Type.Object({ limit: Type.Optional(Type.Number({ description: "默认 100" })) }),
    async run(p) {
      const r = await aegis({ path: `/security-operations/evidence?limit=${p.limit ?? 100}` });
      const rows = (r.evidence ?? []).map((x: any) => [
        x.evidence_id,
        x.evidence_type,
        x.source_name,
        String(x.text_preview ?? "").slice(0, 80),
      ]);
      return {
        ...text(`共 ${r.total} 条证据。`),
        details: { table: table(["id", "type", "source", "preview"], rows) },
      };
    },
  });

  reg({
    name: "aegis_list_runs",
    label: "Aegis 运行列表",
    description: "列出所有安全分析 Agent 运行。",
    parameters: Type.Object({}),
    async run() {
      const r = await aegis({ path: "/security-operations/agent/runs" });
      const rows = (r.runs ?? []).map((x: any) => [
        x.run_id,
        x.task_type ?? x.requested_task ?? "",
        x.status,
        x.created_at ?? "",
      ]);
      return {
        ...text(`${rows.length} 次运行。`),
        details: { table: table(["run_id", "task", "status", "created_at"], rows) },
      };
    },
  });

  reg({
    name: "aegis_inspect_run",
    label: "Aegis 运行详情",
    description: "查询某个安全分析 Agent 运行的状态、结果与审批哈希。",
    parameters: Type.Object({ run_id: Type.String() }),
    async run(p) {
      const r = await aegis({ path: `/security-operations/agent/runs/${encodeURIComponent(p.run_id)}` });
      // 运行详情也要给模型看（截断），否则只能拿到状态。
      const body = JSON.stringify(r, null, 2).slice(0, 4000);
      return { content: [{ type: "text" as const, text: `状态：${r.status}。\n\n${body}` }], details: { run: r } };
    },
  });

  reg({
    name: "aegis_export_run",
    label: "Aegis 导出报告",
    description: "把某次 Agent 运行导出为 Markdown 或 JSON 报告全文。",
    parameters: Type.Object({
      run_id: Type.String(),
      format: Type.Optional(Type.String({ description: "markdown | json，默认 markdown" })),
    }),
    token: true,
    async run(p) {
      const fmt = p.format === "json" ? "json" : "markdown";
      const body = await aegisText(
        `/security-operations/agent/runs/${encodeURIComponent(p.run_id)}/export?format=${fmt}`,
        true,
      );
      return text(body, { format: fmt });
    },
  });

  reg({
    name: "aegis_tool_catalog",
    label: "Aegis 只读工具目录",
    description: "列出安全分析 Agent 可用的只读工具及其参数 schema。",
    parameters: Type.Object({}),
    async run() {
      const r = await aegis({ path: "/security-operations/agent/tools" });
      const rows = (r.tools ?? []).map((x: any) => [x.name, x.read_only, x.timeout_seconds, x.required_role]);
      return {
        ...text(`${rows.length} 个工具。`),
        details: { table: table(["name", "read_only", "timeout_s", "role"], rows), raw: r },
      };
    },
  });

  reg({
    name: "aegis_model_status",
    label: "Aegis 模型状态",
    description: "查看安全分析 Agent 所用语言模型的连接状态与调用预算。",
    parameters: Type.Object({}),
    async run() {
      const r = await aegis({ path: "/security-operations/agent/model" });
      return text(`模型：${r.model ?? "?"}（${r.connection_status ?? "?"}）`, { status: r });
    },
  });

  reg({
    name: "aegis_list_memories",
    label: "Aegis 记忆列表",
    description: "列出 Agent 记忆（workflow / session / incident / preference）。",
    parameters: Type.Object({
      memory_type: Type.Optional(Type.String()),
      subject_key: Type.Optional(Type.String()),
      limit: Type.Optional(Type.Number()),
    }),
    async run(p) {
      const qs = new URLSearchParams();
      if (p.memory_type) qs.set("memory_type", p.memory_type);
      if (p.subject_key) qs.set("subject_key", p.subject_key);
      qs.set("limit", String(p.limit ?? 100));
      const r = await aegis({ path: `/security-operations/memories?${qs}` });
      const rows = (r.memories ?? []).map((x: any) => [
        x.memory_id,
        x.memory_type,
        x.subject_key,
        x.confirmed,
        String(x.summary ?? "").slice(0, 80),
      ]);
      return {
        ...text(`共 ${r.total} 条记忆。`),
        details: { table: table(["memory_id", "type", "subject", "confirmed", "summary"], rows) },
      };
    },
  });

  reg({
    name: "aegis_benchmarks",
    label: "Aegis 外部基准",
    description: "读取已导入的真实外部评测报告结果。",
    parameters: Type.Object({}),
    async run() {
      const r = await aegis({ path: "/security-operations/benchmarks" });
      return text("已读取外部基准。", { benchmarks: r });
    },
  });

  reg({
    name: "aegis_runtime_config",
    label: "Aegis 五阶段配置",
    description: "读取 PreTool 五阶段管线的确定性阈值与权重配置。",
    parameters: Type.Object({}),
    async run() {
      const r = await aegis({ path: "/runtime/config" });
      const rows = Object.entries(r.config ?? {}).map(([k, v]) => [k, String(v)]);
      return {
        ...text(`persistent=${r.persistent}`),
        details: { table: table(["key", "value"], rows), raw: r },
      };
    },
  });

  reg({
    name: "aegis_list_sessions",
    label: "Aegis 运行时会话",
    description: "列出 Aegis 运行时会话安全摘要（含风险曲线来源）。",
    parameters: Type.Object({ limit: Type.Optional(Type.Number()) }),
    async run(p) {
      const r = await aegis({ path: `/runtime/sessions?limit=${p.limit ?? 100}` });
      const rows = (r.sessions ?? []).map((x: any) => [
        x.session_id ?? x.session_key,
        x.runtime_kind,
        x.drift_score ?? "",
        x.risk_level ?? "",
      ]);
      return {
        ...text(`共 ${r.total} 个会话。`),
        details: { table: table(["session", "runtime_kind", "drift", "risk"], rows), raw: r },
      };
    },
  });

  reg({
    name: "aegis_get_session",
    label: "Aegis 会话详情",
    description: "返回单个运行时会话的风险曲线、因果时间线与哈希链完整性。",
    parameters: Type.Object({
      session_id: Type.String(),
      runtime_kind: Type.Optional(Type.String({ description: "默认 pi" })),
      limit: Type.Optional(Type.Number()),
    }),
    async run(p) {
      const rk = p.runtime_kind ?? CFG.runtimeKind;
      const r = await aegis({
        path: `/runtime/sessions/${encodeURIComponent(p.session_id)}?runtime_kind=${encodeURIComponent(rk)}&limit=${p.limit ?? 500}`,
      });
      const rows = (r.risk_curve ?? []).map((x: any) => [x.seq, x.turn_index, x.drift_score, x.action ?? ""]);
      return {
        ...text(`会话完整性：${r.integrity?.valid ? "完整" : "损坏"}`),
        details: { table: table(["seq", "turn", "drift", "action"], rows), raw: r },
      };
    },
  });

  reg({
    name: "aegis_list_antibodies",
    label: "Aegis 免疫抗体列表",
    description: "列出免疫学习产生的抗体（shadow / active / decaying / retired）。",
    parameters: Type.Object({ status: Type.Optional(Type.String()) }),
    async run(p) {
      const qs = p.status ? `?status=${encodeURIComponent(p.status)}` : "";
      const r = await aegis({ path: `/runtime/immunity/antibodies${qs}` });
      const rows = (r.antibodies ?? []).map((x: any) => [
        x.antibody_id ?? x.id,
        x.name,
        x.status,
        x.similarity_threshold ?? "",
      ]);
      return {
        ...text(`共 ${r.total} 个抗体。`),
        details: { table: table(["id", "name", "status", "threshold"], rows), raw: r },
      };
    },
  });

  reg({
    name: "aegis_list_manifests",
    label: "Aegis 能力清单",
    description: "列出按 runtime_kind 配置的能力清单（allowed_capabilities）。",
    parameters: Type.Object({}),
    async run() {
      const r = await aegis({ path: "/runtime/manifests" });
      const rows = (r.manifests ?? []).map((x: any) => [
        x.runtime_kind,
        x.manifest_id,
        Array.isArray(x.allowed_capabilities) ? x.allowed_capabilities.join(",") : "",
        x.version ?? "",
      ]);
      return {
        ...text(`已知能力：${(r.known_capabilities ?? []).join(", ")}`),
        details: { table: table(["runtime_kind", "manifest", "capabilities", "version"], rows), raw: r },
      };
    },
  });

  reg({
    name: "aegis_evaluation_dataset",
    label: "Aegis 评测数据集",
    description: "查看评测数据集概览（中文 Agent 安全 P1）。",
    parameters: Type.Object({}),
    async run() {
      const r = await aegis({ path: "/runtime/evaluations/dataset" });
      return text(`数据集 ${r.dataset}：${r.case_count} 例（恶意 ${r.malicious} / 良性 ${r.benign}）`, {
        dataset: r,
      });
    },
  });

  reg({
    name: "aegis_list_immune_matches",
    label: "Aegis 免疫命中记录",
    description: "列出免疫学习的历史命中记录（session_key / limit）。",
    parameters: Type.Object({
      session_key: Type.Optional(Type.String()),
      limit: Type.Optional(Type.Number()),
    }),
    async run(p) {
      const qs = new URLSearchParams();
      if (p.session_key) qs.set("session_key", p.session_key);
      qs.set("limit", String(p.limit ?? 100));
      const r = await aegis({ path: `/runtime/immunity/matches?${qs}` });
      const rows = (r.matches ?? []).map((x: any) => [
        x.session_key,
        x.name ?? x.antibody_id ?? "",
        x.similarity ?? "",
        x.score_delta ?? "",
      ]);
      return {
        ...text(`共 ${r.total} 条命中。`),
        details: { table: table(["session", "antibody", "similarity", "delta"], rows), raw: r },
      };
    },
  });

  // =====================================================================
  // 二、有副作用工具（均需 UI token；高风险者强确认）
  // =====================================================================

  reg({
    name: "aegis_submit_run",
    label: "Aegis 提交分析",
    description:
      "向 Aegis 安全分析 Agent 提交一次任务。requested_task=policy_change 时会进入人工审批流程。",
    token: true,
    parameters: Type.Object({
      query: Type.String(),
      requested_task: Type.Optional(
        Type.String({
          description:
            "auto / general_explanation / knowledge_query / incident_investigation / evidence_analysis / dataset_evaluation / policy_change",
        }),
      ),
      evidence_ids: Type.Optional(Type.Array(Type.String())),
      session_keys: Type.Optional(Type.Array(Type.String())),
      document_types: Type.Optional(Type.Array(Type.String())),
      policy_changes: Type.Optional(
        Type.Record(Type.String(), Type.Number(), {
          description:
            '仅 requested_task=policy_change 时需要，例如 {"confirm_threshold": 35, "block_threshold": 85}',
        }),
      ),
    }),
    async run(p, ctx) {
      const ok = await ctx.ui.confirm(
        "提交安全分析",
        `任务：${p.requested_task ?? "auto"}\n问题：${String(p.query).slice(0, 300)}`,
      );
      if (!ok) return text("已取消。");
      const r = await aegis({
        path: "/security-operations/agent/runs",
        method: "POST",
        token: true,
        body: {
          query: p.query,
          requested_task: p.requested_task ?? "auto",
          evidence_ids: p.evidence_ids ?? [],
          session_keys: p.session_keys ?? [],
          document_types: p.document_types ?? [],
          policy_changes: p.policy_changes ?? {},
        },
      });
      return text(`已提交，run_id=${r.run_id}（状态 ${r.status}）。`, { run: r });
    },
  });

  reg({
    name: "aegis_resume_run",
    label: "Aegis 审批策略",
    description:
      "对 awaiting_approval 的策略提案做 approve/reject。批准后由 Aegis 的确定性代码应用策略。",
    token: true,
    parameters: Type.Object({
      run_id: Type.String(),
      decision: Type.String({ description: "approve 或 reject" }),
      proposal_hash: Type.String({ description: "提案 SHA-256（64 位）" }),
    }),
    async run(p, ctx) {
      const decision = p.decision === "reject" ? "reject" : "approve";
      // 红线：approved_by 来自环境，绝不来自模型
      const ok = await ctx.ui.confirm(
        "⚠️ 策略审批",
        `run: ${p.run_id}\n决定: ${decision}\n提案哈希: ${p.proposal_hash}\n审批人: ${CFG.approver}`,
      );
      if (!ok) return text("审批已取消。");
      const r = await aegis({
        path: `/security-operations/agent/runs/${encodeURIComponent(p.run_id)}/resume`,
        method: "POST",
        token: true,
        body: { decision, proposal_hash: p.proposal_hash, approved_by: CFG.approver },
      });
      return text(`审批已执行：${decision}。`, { run: r });
    },
  });

  reg({
    name: "aegis_cancel_run",
    label: "Aegis 取消运行",
    description: "取消一个 queued / running / awaiting_approval 的 Agent 运行。",
    token: true,
    parameters: Type.Object({ run_id: Type.String() }),
    async run(p, ctx) {
      const ok = await ctx.ui.confirm("取消运行", `确认取消 run ${p.run_id}？`);
      if (!ok) return text("已取消操作。");
      const r = await aegis({
        path: `/security-operations/agent/runs/${encodeURIComponent(p.run_id)}/cancel`,
        method: "POST",
        token: true,
      });
      return text(`运行状态：${r.status}。`, { run: r });
    },
  });

  reg({
    name: "aegis_run_evaluation",
    label: "Aegis 评测管线",
    description: "在本地数据集上运行五阶段管线评测变体。",
    parameters: Type.Object({
      variants: Type.Optional(Type.Array(Type.String())),
      include_details: Type.Optional(Type.Boolean()),
    }),
    async run(p, ctx) {
      const ok = await ctx.ui.confirm("运行评测", `变体：${(p.variants ?? ["默认"]).join(", ")}`);
      if (!ok) return text("已取消。");
      const r = await aegis({
        path: "/runtime/evaluations",
        method: "POST",
        body: {
          variants: p.variants ?? ["aegis_single_turn", "deepseek_judge_recorded", "five_stage"],
          include_details: !!p.include_details,
        },
      });
      return text("评测完成。", { evaluation: r });
    },
  });

  reg({
    name: "aegis_grant_trust",
    label: "Aegis JIT 授权",
    description: "为当前会话的某个能力授予有限时/限次的信任（Just-In-Time）。",
    token: true,
    parameters: Type.Object({
      capability: Type.Union([
        Type.Literal("file_read"),
        Type.Literal("file_write"),
        Type.Literal("shell_exec"),
        Type.Literal("network_outbound"),
        Type.Literal("unknown_tool"),
      ]),
      ttl_seconds: Type.Optional(Type.Number({ description: "1-3600，默认 300" })),
      max_uses: Type.Optional(Type.Number({ description: "1-100，默认 5" })),
    }),
    async run(p, ctx) {
      const ok = await ctx.ui.confirm(
        "⚠️ JIT 授权",
        `能力：${p.capability}\n有效期：${p.ttl_seconds ?? 300}s，次数：${p.max_uses ?? 5}\n会话：${sid(ctx)}`,
      );
      if (!ok) return text("授权已取消。");
      const r = await aegis({
        path: "/runtime/trust/grants",
        method: "POST",
        token: true,
        body: {
          session_id: sid(ctx),
          runtime_kind: CFG.runtimeKind,
          capability: p.capability,
          ttl_seconds: p.ttl_seconds ?? 300,
          max_uses: p.max_uses ?? 5,
        },
      });
      return text(`已授权 ${r.capability}（${r.max_uses} 次 / ${r.ttl_seconds}s）。`, { grant: r });
    },
  });

  reg({
    name: "aegis_transition_antibody",
    label: "Aegis 抗体状态流转",
    description: "把抗体在 shadow / active / decaying / retired 之间流转。",
    token: true,
    parameters: Type.Object({
      antibody_id: Type.String(),
      target: Type.Union([
        Type.Literal("shadow"),
        Type.Literal("active"),
        Type.Literal("decaying"),
        Type.Literal("retired"),
      ]),
    }),
    async run(p, ctx) {
      const ok = await ctx.ui.confirm(
        "⚠️ 抗体状态变更",
        `抗体：${p.antibody_id}\n目标状态：${p.target}\n审批人：${CFG.approver}`,
      );
      if (!ok) return text("已取消。");
      const r = await aegis({
        path: `/runtime/immunity/antibodies/${encodeURIComponent(p.antibody_id)}/transition`,
        method: "POST",
        token: true,
        body: { target: p.target, approved_by: CFG.approver },
      });
      return text("抗体状态已更新。", { antibody: r });
    },
  });

  reg({
    name: "aegis_create_memory",
    label: "Aegis 新增记忆",
    description: "为 Agent 新增一条记忆（workflow / session / incident / preference）。",
    token: true,
    parameters: Type.Object({
      memory_type: Type.Union([
        Type.Literal("workflow"),
        Type.Literal("session"),
        Type.Literal("incident"),
        Type.Literal("preference"),
      ]),
      subject_key: Type.String(),
      summary: Type.String(),
      evidence_ids: Type.Optional(Type.Array(Type.String())),
      confirmed: Type.Optional(Type.Boolean()),
    }),
    async run(p, ctx) {
      const ok = await ctx.ui.confirm("新增记忆", `类型：${p.memory_type}\n摘要：${String(p.summary).slice(0, 200)}`);
      if (!ok) return text("已取消。");
      const r = await aegis({
        path: "/security-operations/memories",
        method: "POST",
        token: true,
        body: {
          memory_type: p.memory_type,
          subject_key: p.subject_key,
          summary: p.summary,
          evidence_ids: p.evidence_ids ?? [],
          confirmed: !!p.confirmed,
        },
      });
      return text("记忆已保存。", { memory: r });
    },
  });

  // =====================================================================
  // 三、运行时治理钩子 —— 把 pi 变成一个被 Aegis 治理的 runtime_kind
  // =====================================================================

  // 1) 每一轮用户输入 → 意图基线
  pi.on("input", async (event, ctx) => {
    const t = (event.text ?? "").trim();
    if (!t) return;
    try {
      await aegis({
        path: "/runtime/intent",
        method: "POST",
        body: {
          session_id: sid(ctx),
          runtime_kind: CFG.runtimeKind,
          text: t.slice(0, 16000),
          allowed_capabilities: CFG.capabilities,
        },
      });
    } catch {
      /* 意图观测失败不阻断对话 */
    }
  });

  // 2) 每次工具调用 → 五阶段裁决（decide 内部会落 before_tool_call 事件）
  pi.on("tool_call", async (event, ctx) => {
    let decision: any;
    try {
      decision = await aegis({
        path: "/runtime/pretool/decide",
        method: "POST",
        body: {
          tool_name: event.toolName,
          tool_input: (event.input as Record<string, unknown>) ?? {},
          session_id: sid(ctx),
          runtime_kind: CFG.runtimeKind,
          base_decision: "allow",
          allowed_capabilities: CFG.capabilities,
          headless: false,
          manifest_id: "default",
        },
      });
    } catch (err: any) {
      if (CFG.failMode === "closed") {
        return { block: true, reason: `Aegis 不可达，已拦截（fail-closed）：${err?.message ?? err}` };
      }
      try {
        ctx.ui?.notify?.(`Aegis 不可达，放行（fail-open）：${err?.message ?? err}`, "warning");
      } catch {
        /* ignore */
      }
      return;
    }

    const action = decision?.action;
    if (action === "block") {
      return { block: true, reason: decision?.reason || "Aegis 策略拦截" };
    }
    if (action === "confirm" && !SELF_GATED.has(event.toolName)) {
      const ok = await ctx.ui.confirm(
        "Aegis 风险确认",
        `工具：${event.toolName}\n${decision?.reason ?? ""}\n${decision?.explanation ?? ""}`,
      );
      if (!ok) return { block: true, reason: "用户拒绝（Aegis confirm）" };
    }
    return;
  });

  // 3) 工具执行结束 → after_tool_call 落库（只记元数据，不记内容）
  pi.on("tool_result", async (event, ctx) => {
    try {
      await aegis({
        path: "/runtime/events",
        method: "POST",
        body: {
          session_id: sid(ctx),
          runtime_kind: CFG.runtimeKind,
          event_type: "after_tool_call",
          metadata: { tool_name: event.toolName, is_error: !!event.isError },
        },
      });
    } catch {
      /* 审计失败不影响主流程 */
    }
  });

  // 4) 启动时提示连接状态
  pi.on("session_start", async (_event, ctx) => {
    try {
      await aegis({ path: "/runtime/config" });
      ctx.ui.notify(`Aegis 已连接：${CFG.base}（runtime_kind=${CFG.runtimeKind}）`, "info");
    } catch (err: any) {
      ctx.ui.notify(`Aegis 未连接：${CFG.base} —— ${err?.message ?? err}`, "warning");
    }
  });

  // =====================================================================
  // 四、便捷命令
  // =====================================================================
  pi.registerCommand("aegis", {
    description: "查看 Aegis 连接与运行时配置",
    handler: async (_args, ctx) => {
      const lines = [
        `base:         ${CFG.base}`,
        `runtime_kind: ${CFG.runtimeKind}`,
        `capabilities: ${CFG.capabilities.join(",") || "（默认 file_read）"}`,
        `approver:     ${CFG.approver}`,
        `fail_mode:    ${CFG.failMode}`,
        `ingress:      ${CFG.ingress ? "已设置" : "未设置"}`,
        `ui_token:     ${CFG.token ? "已设置" : "未设置（写操作不可用）"}`,
        `session:      ${sid(ctx)}`,
      ];
      ctx.ui.notify(lines.join("\n"), "info");
    },
  });
}
