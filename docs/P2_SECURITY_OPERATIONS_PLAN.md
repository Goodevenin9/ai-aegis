# P2 Security Operations Plan

## Product outcome

P2 turns AI Aegis from an online tool-call gate into a local-first security
operations system.  The existing Boundary → Capability → Radius → Drift →
Friction pipeline remains the only online enforcement authority.  P2 consumes
its evidence asynchronously to investigate incidents, retrieve policy, evaluate
changes and learn bounded attack patterns.

## Architecture invariants

- LLMs extract or explain evidence; deterministic code owns scores and policy application.
- The security Agent is never on the PreTool hot path.
- Uploaded files, retrieved passages and historic model output are untrusted data.
- Every factual Agent finding carries evidence references.
- A learned antibody cannot directly return allow/block and its session contribution is capped.
- Candidate antibodies must pass shadow mode and explicit approval before activation.
- An Agent-originated policy proposal is simulated, hashed and approved by exact hash before application. Direct local configuration is a separate human UI operation protected by the per-run UI token.
- Model failure degrades to a deterministic report and never weakens P0/P1 enforcement.
- Long-term incident memory requires explicit confirmation, provenance, expiry and deletion.

## Delivery slices

### P2-A — governed session immunity

- [x] Explainable behavior profiles: tool, capability and radius sequences plus risk features.
- [x] Candidate → shadow → active → decaying → retired lifecycle.
- [x] Active-state approval and UI-token protection.
- [x] Shadow observations contribute zero risk.
- [x] Active matches feed Drift with a configurable session cap (default 25).
- [x] Session cap is validated below the Friction block threshold.
- [x] Generate candidates from intact hash-chained sessions without storing raw prompts.
- [x] Persist match history and counters.
- [ ] Add a labelled shadow-mode evaluation set and automatic false-positive feedback.
- [ ] Add scheduled decay/review jobs and signed antibody import/export.

### P2-B — multimodal security evidence

- [x] Bounded TXT/Markdown/log/YAML ingestion.
- [x] Structured JSON/JSONL and CSV/TSV extraction.
- [x] PDF and DOCX extraction.
- [x] Local screenshot OCR adapter with pixel and execution timeout limits.
- [x] Canonical secret redaction, content hashing and deduplication.
- [x] Reject arbitrary binary uploads and avoid storing original executable content.
- [x] Evidence upload/list/index API and workbench.
- [ ] Add configurable malware scanning before enterprise object-store persistence.
- [ ] Add pluggable vision-model adapters for diagrams and non-OCR visual evidence.

### P2-C — evaluated security RAG

- [x] Section-aware chunks and parent-path citations.
- [x] Offline BM25 and hashed-vector hybrid retrieval.
- [x] Security-policy reranking and document-type filtering.
- [x] Tenant-scoped document/chunk storage.
- [x] Recall@K and MRR evaluation API.
- [x] Agent knowledge-query route with grounded citations.
- [ ] Add a neural embedding adapter and cross-encoder reranker behind replaceable interfaces.
- [ ] Build and publish the Chinese security-RAG benchmark and ablation report.
- [ ] Add explicit no-answer calibration and citation-groundedness scoring.

### P2-D — bounded LangGraph Agent and specialist collaboration

- [x] Public `start / submit / inspect / resume` service boundary.
- [x] Dynamic routing for knowledge, evidence, incidents, datasets and policy changes.
- [x] Evidence Investigator, Dataset Evaluator, Policy Analyst and Report Composer nodes.
- [x] Structured hand-offs rather than free-form multi-Agent conversation.
- [x] DeepSeek adapter with timeout, retry and local deterministic fallback.
- [x] Durable run state and per-node event trail.
- [x] Policy simulation, exact proposal hash, human approval and idempotent application.
- [x] Agent workbench beyond a chat-only UI.
- [x] Non-blocking background submission with durable status/event polling.
- [ ] Add a separate worker queue and push-based progress streaming for enterprise scale.
- [ ] Add durable LangGraph checkpoint adapter for mid-node process recovery.
- [ ] Add per-role token budgets, circuit-breaker metrics and concurrency quotas.

### P2-E — governed memory

- [x] Separate workflow, session, incident and explicit-preference memory types.
- [x] Confirmed incident memory requires evidence references.
- [x] TTL-aware reads and deletion API.
- [x] Tenant isolation and secret redaction before persistence.
- [x] Agent consumes governed memory as bounded context.
- [ ] Add user-visible edit, retention and provenance controls.
- [ ] Add semantic incident-memory retrieval instead of recent-N context.

## Verification gates

1. Safe commands remain `allow` without independent risk evidence.
2. Shadow antibodies never change Drift or Friction.
3. Repeated active antibody matches stay within the configured session cap.
4. Tampered session chains cannot produce learned candidates.
5. Unsupported/oversized evidence is rejected before persistence.
6. Secrets in extracted evidence and Agent state are redacted.
7. RAG evaluation reports reproducible retrieval metrics and citations.
8. Policy changes cannot apply without an exact proposal-hash approval.
9. Repeated approval is idempotent.
10. DeepSeek or Agent failure does not affect online P0/P1 enforcement.

## Community / enterprise seam

The graph, local evidence processing, hybrid retrieval, memory controls and
immunity core remain in Community. Enterprise adds PostgreSQL/object storage,
RBAC/SSO, multi-tenant fleet correlation, multi-level approval, SIEM/work-ticket
integrations, signed antibody distribution, grey release and central retention.
