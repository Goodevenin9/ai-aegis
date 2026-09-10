#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
/**
 * PreToolUse hook handler for the Aegis Guard plugin.
 *
 * Flow per invocation:
 *   1. Read the host's tool-call event JSON from stdin.
 *   2. Extract tool_name; normalize via lib/normalize (mcp__server__tool → candidates).
 *   3. Fetch synced overrides from the local app (100ms timeout, fail-open).
 *   4. Look up the first matching candidate. Map effect → permissionDecision:
 *        allow  → "allow"
 *        deny   → "deny"
 *        prompt → "ask"
 *   5. Print the decision JSON to stdout.
 *
 * Fail-open invariant (locked decision #5): any error path — unreachable
 * local app, timeout, malformed response, unknown effect — emits
 * `{permissionDecision: "allow"}` and the tool call proceeds. The whole
 * point of fail-open is that a broken / stopped local app cannot block
 * the host CLI.
 *
 * Both MCP and built-in (Bash / Edit / Read / etc.) tool names route
 * through `normalize()` to lookup candidates and the same synced-rule
 * lookup path. Unknown names short-circuit to allow.
 *
 * Zero npm deps. Native Node 18+.
 */

'use strict';

const { normalize } = require('../lib/normalize.js');
const {
  fetchSyncedOverrides,
  postJsonAndForget,
  evaluateEgress,
  evaluatePreToolPipeline,
} = require('../lib/client.js');
const { redactForScan } = require('../lib/redact.js');

/**
 * Tools that can reach the network. Everything else short-circuits before any
 * egress round-trip, so the overwhelmingly common Read/Edit/Glob/Grep path
 * costs one Set lookup and adds zero latency.
 *
 * Kept in sync with NETWORK_CAPABLE_BUILTINS in core/egress/destinations.py.
 * A name missing here means egress is silently not enforced for that tool, so
 * err toward including anything plausibly network-capable: the server-side
 * extractor returns `network_capable: false` for a tool it cannot route, which
 * costs one wasted round-trip and nothing else.
 */
const NETWORK_CAPABLE = new Set([
  'webfetch', 'websearch', 'bash', 'powershell',
  // Runtimes name their shell tool differently; this must stay a superset.
  // Mirrors NETWORK_CAPABLE_BUILTINS in core/egress/destinations.py.
  'shell', 'exec', 'terminal', 'run_terminal_cmd', 'runcommand', 'execute_command',
]);

function isNetworkCapable(toolName) {
  const n = String(toolName || '').toLowerCase();
  // Remote MCP servers are egress proxies: the server endpoint is the only
  // destination observable from here, and whatever it reaches downstream is
  // structurally invisible. Still worth evaluating so the endpoint is on the
  // record.
  return NETWORK_CAPABLE.has(n) || n.startsWith('mcp__');
}

const EFFECT_TO_DECISION = Object.freeze({
  allow: 'allow',
  deny: 'deny',
  prompt: 'ask',
});

const DEFAULT_BASE_URL = 'http://127.0.0.1:8741';
const ALLOW = Object.freeze({ decision: 'allow' });
const ARGS_PREVIEW_LIMIT = 200;
const RUNTIME_KIND = 'claude-code';


/**
 * Pure decision logic: given normalized tool candidates and the local app's
 * synced-overrides response, return an internal decision object. The host's
 * exact wire format is applied later by `toHookOutput`.
 *
 * @param {string[]} candidates  Output of lib/normalize.js (may be empty).
 * @param {{synced?: Array<{tool_id: string, effect: string, reason?: string}>} | null} overrides
 * @param {string|null} [sessionId]  The host session, for session-scoped JIT grants.
 * @returns {{decision: 'allow'|'deny'|'ask', reason?: string}}
 */
function decideFromOverrides(candidates, overrides, sessionId = null) {
  if (!Array.isArray(candidates) || candidates.length === 0) return ALLOW;
  if (!overrides || !Array.isArray(overrides.synced) || overrides.synced.length === 0) {
    return ALLOW;
  }

  // Case-insensitive index. Cloud-pushed and local-UI rules may store
  // `tool_id` in any casing (e.g. lowercase `read`) while normalize()
  // emits canonical PascalCase built-ins (`Read`). Keying by lowercase
  // stops a deny rule from silently failing open on a casing mismatch.
  // First-seen-wins is preserved per lowercased key.
  const byToolId = new Map();
  for (const row of overrides.synced) {
    if (row && typeof row.tool_id === 'string') {
      // A session-scoped JIT grant only applies inside the session it was
      // approved for. Skipping the row here (rather than at match time)
      // matters: grants are emitted first, so an unskipped non-matching
      // grant would win the first-seen-wins slot and shadow the very deny
      // it was meant to override — silently allowing other sessions.
      if (row.source === 'jit_grant' && row.session_id
          && row.session_id !== sessionId) continue;
      const key = row.tool_id.toLowerCase();
      if (!byToolId.has(key)) byToolId.set(key, row);
    }
  }

  // Candidates are ordered most-specific-first (prefixed before bare).
  for (const cand of candidates) {
    const match = byToolId.get(cand.toLowerCase());
    if (!match) continue;
    const mapped = EFFECT_TO_DECISION[match.effect];
    if (!mapped) return ALLOW; // unknown effect → fail-open
    if (mapped === 'allow') return ALLOW;
    return {
      decision: mapped,
      reason: typeof match.reason === 'string' && match.reason.length > 0
        ? match.reason
        : `Tool ${cand} matched policy with effect ${match.effect}`,
      // toolId is the matched candidate (most-specific). Exposed on the
      // non-allow path so the entry-point can audit the deny with the
      // canonical tool_id without re-running normalize().
      toolId: cand,
      // Policy-marked requestable deny → the entry-point files a JIT
      // access request and tells the agent a human can approve it.
      requestable: match.requestable === true,
    };
  }
  return ALLOW;
}


/**
 * Map a PreToolUse decision to the audit-row `action` value. Mirrors
 * effectToAction in post-tool-use.js so block-from-PreToolUse and
 * block-from-PostToolUse hash-chain rows are indistinguishable when
 * filtering the audit log by `action`.
 */
function decisionToAuditAction(decision) {
  switch (decision) {
    case 'deny': return 'block';
    case 'ask':  return 'log_only';
    default:     return 'allow';
  }
}


/**
 * Build the fire-and-forget audit payload for a denied (or asked) call.
 *
 * Why this exists: PostToolUse only fires after a successful tool
 * execution. When PreToolUse denies, the tool never runs and PostToolUse
 * never fires — so without auditing here, blocked attempts leave NO
 * audit trail. That's a real observability gap (denied calls are the
 * highest-value security events). This closes it by writing the row
 * before returning the deny decision.
 *
 * Args preview uses the same shared redactForScan + 200-char cap as
 * post-tool-use, so block rows and allow rows look identical apart from
 * the action.
 */
function buildAuditBody(
  toolName,
  toolId,
  toolInput,
  decision,
  reason,
  sessionId,
  riskScore = null,
  pipeline = null,
) {
  let argsPreview = null;
  try {
    if (toolInput !== undefined && toolInput !== null) {
      const raw = typeof toolInput === 'string' ? toolInput : JSON.stringify(toolInput);
      argsPreview = redactForScan(raw).slice(0, ARGS_PREVIEW_LIMIT);
    }
  } catch { /* swallow — empty preview is acceptable */ }
  let auditReason = typeof reason === 'string' && reason.length > 0 ? reason : null;
  if (pipeline && typeof pipeline === 'object') {
    const layers = {};
    if (pipeline.layers && typeof pipeline.layers === 'object') {
      for (const [name, value] of Object.entries(pipeline.layers)) {
        layers[name] = value && typeof value.value === 'string' ? value.value : null;
      }
    }
    auditReason = JSON.stringify({
      schema: 'aegis.pretool-pipeline.v1',
      summary: auditReason,
      risk_score: typeof pipeline.risk_score === 'number' ? pipeline.risk_score : null,
      drift_score: typeof pipeline.drift_score === 'number' ? pipeline.drift_score : null,
      drift_level: pipeline.drift_level || null,
      base_decision: pipeline.base_decision || null,
      final_action: pipeline.action || null,
      headless_escalated: pipeline.headless_escalated === true,
      layers,
      signals: Array.isArray(pipeline.signals)
        ? pipeline.signals.map((signal) => ({
          layer: signal.layer,
          code: signal.code,
          severity: signal.severity,
          score: signal.score,
        }))
        : [],
    });
  }
  return {
    tool_id: toolId,
    function_name: toolName,
    action: decisionToAuditAction(decision),
    // Existing audit consumers expect read/write/delete/admin categories.
    // Keep the exact numeric score in the reason generated by Friction.
    risk: typeof riskScore !== 'number' ? null
      : riskScore >= 80 ? 'admin'
        : riskScore >= 60 ? 'delete'
          : riskScore >= 40 ? 'write'
            : 'read',
    reason: auditReason,
    is_essential: false,
    args_preview: argsPreview,
    runtime_kind: RUNTIME_KIND,
    session_id: sessionId || null,
  };
}


/**
 * Wrap an internal decision in Claude Code's PreToolUse output format.
 *
 *   { hookSpecificOutput: { hookEventName: "PreToolUse",
 *                           permissionDecision: "...",
 *                           permissionDecisionReason: "..."? } }
 *
 * See: https://code.claude.com/docs/en/hooks#pretooluse-hook-decision-control
 *
 * @param {{decision: 'allow'|'deny'|'ask', reason?: string}} d
 */
// Branded prefix on every deny / ask reason so the host CLI's deny
// banner identifies Aegis Guard as the enforcer. Without this,
// users see e.g. "User-set local override" with no indication of which
// hook produced it. Idempotent — won't double-prefix.
const REASON_PREFIX = 'Aegis Guard';
function _brand(reason) {
  return reason.startsWith(REASON_PREFIX + ':')
    ? reason
    : `${REASON_PREFIX}: ${reason}`;
}

function toHookOutput(d) {
  const out = {
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: d.decision,
    },
  };
  if (typeof d.reason === 'string' && d.reason.length > 0) {
    // Only brand on non-allow paths — Claude Code's allow path doesn't
    // surface the reason to the user, so the prefix would just be
    // noise in any inadvertent log line.
    out.hookSpecificOutput.permissionDecisionReason =
      d.decision === 'allow' ? d.reason : _brand(d.reason);
  }
  return out;
}


/**
 * Async decision: normalize → fetch overrides → decide.
 *
 * @param {string} toolName  Host-supplied tool name (mcp__server__tool or built-in).
 * @param {string} baseUrl   Local app base URL.
 * @returns {Promise<{permissionDecision: 'allow'|'deny'|'ask', message?: string}>}
 */
async function decide(toolName, baseUrl, sessionId = null, toolInput = null, runtimeContext = {}) {
  const candidates = normalize(toolName);
  // Tool-permission rules key off the tool NAME. Egress rules key off the
  // DESTINATION, so a tool with no name-based rule can still be denied for
  // where it points — which means the egress check must run even when
  // normalize() yields no candidates.
  let baseDecision = ALLOW;
  if (candidates.length > 0) {
    const overrides = await fetchSyncedOverrides(baseUrl, RUNTIME_KIND);
    const decision = decideFromOverrides(candidates, overrides, sessionId);
    // A name-based deny already stops the call; evaluating egress on top would
    // add latency and a duplicate audit row for a call that never happens.
    if (decision.decision !== 'allow') baseDecision = decision;
  }
  if (baseDecision.decision === 'allow') {
    baseDecision = await decideEgress(toolName, toolInput, baseUrl, sessionId);
  }

  let pipeline = {};
  try {
    pipeline = await evaluatePreToolPipeline(baseUrl, {
      tool_name: toolName,
      tool_input: toolInput || {},
      runtime_kind: RUNTIME_KIND,
      session_id: sessionId || '__anonymous__',
      base_decision: baseDecision.decision,
      allowed_capabilities: Array.isArray(runtimeContext.allowedCapabilities)
        ? runtimeContext.allowedCapabilities
        : [],
      project_root: runtimeContext.projectRoot || null,
      headless: runtimeContext.headless === true,
    });
  } catch {
    return baseDecision;
  }

  const pipelineDecision = pipeline && pipeline.action;
  const mapped = pipelineDecision === 'block'
    ? 'deny'
    : pipelineDecision === 'confirm'
      ? 'ask'
      : pipelineDecision === 'allow'
        ? 'allow'
        : null;
  if (!mapped) return baseDecision;
  // A defense-in-depth layer may strengthen the existing verdict, never
  // weaken a deny/ask already produced by AI Aegis rules or egress.
  if (mapped === 'allow' && baseDecision.decision !== 'allow') return baseDecision;
  if (mapped === 'ask' && baseDecision.decision === 'deny') return baseDecision;
  const hasSignals = Array.isArray(pipeline.signals) && pipeline.signals.length > 0;
  if (mapped === baseDecision.decision && mapped === 'allow' && !hasSignals) return baseDecision;

  const pipelineReason = typeof pipeline.reason === 'string' && pipeline.reason.length > 0
    ? pipeline.reason
    : null;
  const reason = baseDecision.decision !== 'allow' && baseDecision.reason
    ? pipelineReason ? `${baseDecision.reason}; ${pipelineReason}` : baseDecision.reason
    : pipelineReason || baseDecision.reason;

  return {
    ...baseDecision,
    decision: mapped,
    reason,
    toolId: baseDecision.toolId || candidates[0] || toolName,
    requestable: baseDecision.requestable === true,
    riskScore: typeof pipeline.risk_score === 'number' ? pipeline.risk_score : null,
    pipeline,
  };
}


/**
 * Second gate: does this call's network destination violate the egress policy?
 *
 * Extraction and evaluation live server-side so there is one implementation of
 * shell-command parsing rather than one per runtime plugin. This function only
 * decides whether the round-trip is worth making.
 *
 * Fail-open on every error path, consistent with locked decision #5. When the
 * policy is fail-closed the server returns `block` itself; an unreachable
 * server cannot convey that intent, and wedging every agent on the machine
 * because the local app stopped is the wrong failure mode.
 */
async function decideEgress(toolName, toolInput, baseUrl, sessionId) {
  if (!isNetworkCapable(toolName)) return ALLOW;
  try {
    const result = await evaluateEgress(baseUrl, {
      tool_name: toolName,
      tool_input: toolInput || {},
      runtime_kind: RUNTIME_KIND,
      session_id: sessionId,
    });
    if (!result || result.action !== 'block') return ALLOW;
    const top = Array.isArray(result.verdicts)
      ? result.verdicts.find((v) => v && v.action === 'block')
      : null;
    let reason = (top && top.reason) || result.reason || 'Blocked by egress policy';
    if (top && top.remediation) reason += ` ${top.remediation}`;
    return {
      decision: 'deny',
      reason,
      toolId: toolName,
      // Egress denies are not JIT-requestable in v1. The JIT flow grants access
      // to a TOOL; egress denies are about a DESTINATION, and a grant keyed on
      // tool_id would open the tool for every host, not the one under review.
      requestable: false,
      egress: true,
    };
  } catch {
    return ALLOW;
  }
}


// --- stdin/stdout adapter (entry point) ---------------------------------

async function readAllStdin() {
  let buf = '';
  for await (const chunk of process.stdin) buf += chunk;
  return buf;
}

async function main() {
  let event = {};
  try {
    const raw = await readAllStdin();
    event = raw ? JSON.parse(raw) : {};
  } catch {
    process.stdout.write(JSON.stringify(toHookOutput(ALLOW)));
    return;
  }
  const toolName = (event && (event.tool_name || event.toolName)) || '';
  const baseUrl = process.env.AEGIS_ENGINE_ENDPOINT || DEFAULT_BASE_URL;
  const sessionId = (event && (event.session_id || event.sessionId)) || null;
  const toolInput = (event && (event.tool_input || event.toolInput)) || null;
  const allowedCapabilities = (process.env.AEGIS_SESSION_CAPABILITIES || '')
    .split(',').map((value) => value.trim()).filter(Boolean);
  const truthy = new Set(['1', 'true', 'yes', 'on']);
  const headless = truthy.has(String(process.env.AEGIS_HEADLESS || '').toLowerCase())
    || truthy.has(String(process.env.CI || '').toLowerCase());
  let decision = ALLOW;
  try {
    decision = await decide(toolName, baseUrl, sessionId, toolInput, {
      allowedCapabilities,
      projectRoot: event && event.cwd,
      headless,
    });
  } catch {
    decision = ALLOW;
  }
  // Audit blocked attempts here — PostToolUse never fires on deny so
  // without this the chain has no record of the highest-value events.
  // Fire-and-forget: a slow / unreachable local app cannot delay the
  // decision return below. The enforcement decision was already
  // computed above; this is purely the audit row.
  // Egress denies are already persisted server-side (one row per destination
  // in egress_audit, written by /api/egress/evaluate before it answered).
  // Posting here too would double-count the same block in two audit surfaces.
  const hasPipelineEvidence = decision.pipeline
    && Array.isArray(decision.pipeline.signals)
    && decision.pipeline.signals.length > 0;
  if ((decision.decision === 'deny' || decision.decision === 'ask' || hasPipelineEvidence)
      && decision.toolId && !decision.egress) {
    postJsonAndForget(
      `${baseUrl}/api/tool-permissions/call-audit`,
      buildAuditBody(
        toolName,
        decision.toolId,
        toolInput,
        decision.decision,
        decision.reason,
        sessionId,
        decision.riskScore,
        decision.pipeline,
      ),
    );
    // Requestable deny → file a JIT access request (fire-and-forget; the
    // server dedupes per tool+runtime+session and caps the queue) and tell
    // the agent a human can approve it. The deny itself stands — access
    // only opens after approval flips a time-boxed grant into the
    // overrides this hook reads on its next call.
    if (decision.decision === 'deny' && decision.requestable) {
      postJsonAndForget(`${baseUrl}/api/jit/requests`, {
        tool_id: decision.toolId,
        function_name: toolName,
        runtime_kind: RUNTIME_KIND,
        session_id: sessionId,
      });
      decision = {
        ...decision,
        reason: `${decision.reason} — an access request was filed; a human can approve ` +
          'time-boxed access in Aegis → Tool Permissions.',
      };
    }
  }
  process.stdout.write(JSON.stringify(toHookOutput(decision)));
}

if (require.main === module) {
  main();
}

module.exports = {
  decide,
  decideFromOverrides,
  toHookOutput,
  decisionToAuditAction,
  buildAuditBody,
  EFFECT_TO_DECISION,
  ARGS_PREVIEW_LIMIT,
  RUNTIME_KIND,
};
