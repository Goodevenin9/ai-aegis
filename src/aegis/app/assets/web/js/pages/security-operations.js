/** P2 Security Operations — evidence, retrieval, memory, immunity and Agent workflows. */

const SecurityOperationsPage = {
    async render(container) {
        Header.setPageInfo('Security Copilot', 'Investigate evidence, retrieve policy and govern learned defenses.');
        this._style();
        container.innerHTML = `
          <div class="so-hero"><div><span class="so-kicker">P2 · HUMAN-GOVERNED</span><h2>Security operations, not another chatbot</h2><p>Evidence stays untrusted. The five-stage pipeline remains the enforcement authority.</p></div><div class="so-status"><i></i> LangGraph workflow ready</div></div>
          <div class="so-grid">
            <section class="so-card so-credentials"><header><span>00</span><div><h3>Model credentials</h3><p>DeepSeek key and drift extraction · write-only, the key is never echoed back</p></div></header>
              <div id="so-cred-status" class="so-cred-badge"></div>
              <form id="so-cred-form">
                <div class="so-row"><input type="password" name="api_key" id="so-cred-key" autocomplete="off" placeholder="Paste a DeepSeek API key, for example sk-..."><button>Save key</button></div>
                <div class="so-row">
                  <label class="so-cred-toggle"><input type="checkbox" name="drift_llm_enabled" id="so-cred-drift"> Enable drift extraction</label>
                  <button type="button" id="so-cred-test" class="ghost">Test both paths</button>
                  <button type="button" id="so-cred-delete" class="ghost">Remove stored key</button>
                </div>
              </form>
              <div id="so-cred-result" class="so-output">No credential check yet.</div>
            </section>
            <section class="so-card so-agent"><header><span>01</span><div><h3>Security Analyst Agent</h3><p>Dynamic routing · investigation · evaluation · approval</p></div></header>
              <form id="so-agent-form"><textarea name="query" required placeholder="For example: investigate permission drift in a Codex session or find policy 17"></textarea><div class="so-row"><select name="requested_task"><option value="auto">Auto route</option><option value="incident_investigation">Incident investigation</option><option value="knowledge_query">Knowledge query</option><option value="dataset_evaluation">Dataset evaluation</option><option value="policy_change">Policy change</option></select><input name="session_keys" placeholder="session keys, comma separated"><button>Run Agent</button></div><input name="policy_changes" placeholder='Policy JSON, e.g. {"confirm_threshold":45}'></form><div id="so-agent-result" class="so-output">No run yet.</div>
            </section>
            <section class="so-card"><header><span>02</span><div><h3>Evidence & multimodal intake</h3><p>Logs · CSV · PDF · Word · screenshots</p></div></header>
              <form id="so-upload-form"><input type="file" name="file" required accept=".txt,.md,.log,.json,.jsonl,.csv,.tsv,.pdf,.docx,.png,.jpg,.jpeg,.webp,.bmp"><input name="title" placeholder="Evidence title"><select name="document_type"><option value="security_policy">Security policy</option><option value="incident">Incident</option><option value="rule">Rule</option><option value="security_knowledge">Security knowledge</option></select><button>Upload & index</button></form><div id="so-evidence" class="so-list"></div>
            </section>
            <section class="so-card"><header><span>03</span><div><h3>Evidence-grounded RAG</h3><p>Hybrid retrieval · reranking · citations</p></div></header>
              <form id="so-rag-form" class="so-inline"><input name="query" required placeholder="Search policies and confirmed incidents"><button>Search</button></form><div id="so-rag-result" class="so-output">No retrieval yet.</div>
              <form id="so-rageval-form"><textarea name="cases" placeholder='Evaluation cases JSON, for example [{"query":"...","relevant_chunk_ids":["..."]}]'></textarea><div class="so-row"><input name="k" type="number" min="1" max="20" placeholder="k (default 5)"><button type="button" id="so-rageval-run" class="ghost">Evaluate retrieval</button></div></form><div id="so-rageval-result" class="so-output">No retrieval evaluation yet.</div>
            </section>
            <section class="so-card"><header><span>04</span><div><h3>Session immunity</h3><p>Candidate → shadow → approved activation</p></div></header>
              <form id="so-immune-form"><div class="so-row"><input name="runtime_kind" value="codex" placeholder="runtime"><input name="session_id" required placeholder="confirmed session ID"></div><input name="name" required placeholder="Antibody name"><button>Learn candidate</button></form><div id="so-antibodies" class="so-list"></div>
            </section>
            <section class="so-card so-memory"><header><span>05</span><div><h3>Governed memory</h3><p>Explicit preference and confirmed incident memory</p></div></header>
              <form id="so-memory-form"><select name="memory_type"><option value="preference">Preference</option><option value="incident">Confirmed incident</option><option value="session">Session</option></select><input name="subject_key" required placeholder="Subject key"><input name="evidence_ids" placeholder="Evidence IDs for incident"><textarea name="summary" required placeholder="Memory summary"></textarea><button>Save memory</button></form><div id="so-memories" class="so-list"></div>
            </section>
            <section class="so-card"><header><span>06</span><div><h3>Agent tools</h3><p>Closed read-only registry · timeout- and role-bound</p></div></header><div id="so-agent-tools" class="so-list"></div></section>
            <section class="so-card so-wide"><header><span>07</span><div><h3>External benchmarks</h3><p>Offline oracle replay · published with its limitations</p></div></header><div id="so-benchmarks" class="so-output">Loading benchmark report…</div></section>
          </div>`;
        this._bind();
        const agentForm = document.getElementById('so-agent-form');
        const evidenceInput = document.createElement('input');
        evidenceInput.name = 'evidence_ids';
        evidenceInput.placeholder = 'Evidence IDs, comma separated';
        agentForm.appendChild(evidenceInput);
        const modelPanel = document.createElement('div');
        modelPanel.id = 'so-model-status';
        modelPanel.textContent = 'Checking model';
        agentForm.before(modelPanel);
        document.getElementById('so-cred-form').addEventListener('submit', event => this._saveCredentials(event));
        document.getElementById('so-cred-test').addEventListener('click', () => this._testCredentials());
        document.getElementById('so-cred-delete').addEventListener('click', () => this._deleteCredentials());
        // The drift toggle is the single most dangerous silent failure in this
        // pipeline, so it applies and reports immediately rather than waiting
        // for a separate save.
        document.getElementById('so-cred-drift').addEventListener('change', event => this._saveDrift(event.currentTarget.checked));
        const historyPanel = document.createElement('div');
        historyPanel.id = 'so-run-history';
        agentForm.after(historyPanel);
        const historyButton = document.createElement('button');
        historyButton.type = 'button';
        historyButton.textContent = 'Refresh investigation history';
        historyButton.addEventListener('click', () => this._history());
        historyPanel.before(historyButton);
        await this._credentialStatus();
        await this._modelStatus();
        await this._refresh();
    },

    async _credentialStatus() {
        const badge = document.getElementById('so-cred-status');
        if (!badge) return null;
        try {
            const status = await API.getModelCredentials();
            const keyText = status.key_configured
                ? `${status.key_masked} · from ${status.key_source}`
                : 'not configured';
            badge.innerHTML =
                `<span class="so-cred-chip ${status.key_configured ? 'ok' : 'warn'}">Key: ${this._esc(keyText)}</span>` +
                `<span class="so-cred-chip ${status.drift_llm_enabled ? 'ok' : 'warn'}">Drift extraction: ${status.drift_llm_enabled ? 'enabled' : 'disabled'}</span>`;
            const drift = document.getElementById('so-cred-drift');
            if (drift) drift.checked = !!status.drift_llm_enabled;
            const remove = document.getElementById('so-cred-delete');
            if (remove) remove.disabled = !status.key_managed;
            return status;
        } catch (error) { badge.textContent = error.message; return null; }
    },

    async _saveCredentials(event) {
        event.preventDefault();
        const out = document.getElementById('so-cred-result');
        const key = String(new FormData(event.currentTarget).get('api_key') || '').trim();
        if (!key) { out.textContent = 'Paste a key before saving.'; return; }
        out.textContent = 'Saving…';
        try {
            await API.updateModelCredentials({ api_key: key });
            // Never leave the secret sitting in the DOM.
            document.getElementById('so-cred-key').value = '';
            await this._credentialStatus();
            await this._testCredentials();
            await this._modelStatus();
        } catch (error) { out.textContent = error.message; }
    },

    async _saveDrift(enabled) {
        const out = document.getElementById('so-cred-result');
        try {
            await API.updateModelCredentials({ drift_llm_enabled: enabled });
            await this._credentialStatus();
        } catch (error) {
            out.textContent = error.message;
            await this._credentialStatus();  // reflect what actually stuck
        }
    },

    async _testCredentials() {
        const out = document.getElementById('so-cred-result');
        out.textContent = 'Testing both paths…';
        try {
            const result = await API.testModelCredentials();
            // Separate chips keep each state its own text node, which is what
            // the i18n pattern pass matches on. Technical details such as
            // "online" or "HTTP 401" stay untranslated on purpose.
            const chip = (label, item) => `<span class="so-cred-chip ${item.ok ? 'ok' : 'warn'}">${label}: ${item.ok ? 'ok' : 'failed'} (${this._esc(item.detail)})</span>`;
            out.innerHTML = `${chip('Agent model', result.agent)} ${chip('Drift extraction', result.drift)}`;
        } catch (error) { out.textContent = error.message; }
    },

    async _deleteCredentials() {
        const out = document.getElementById('so-cred-result');
        try {
            await API.deleteModelCredentials();
            await this._credentialStatus();
            out.textContent = 'Stored key removed.';
        } catch (error) { out.textContent = error.message; }
    },

    async _modelStatus() {
        const panel = document.getElementById('so-model-status');
        try {
            const status = await API.request('/api/security-operations/agent/model');
            panel.textContent = `${status.model} · ${status.connection_status} · API ${status.calls || 0} · tokens ${(status.input_tokens || 0) + (status.output_tokens || 0)}`;
            if (!status.configured) panel.textContent += ' · Offline workflow';
        } catch (error) { panel.textContent = error.message; }
    },

    async _history() {
        const panel = document.getElementById('so-run-history');
        try {
            const data = await API.listSecurityAgentRuns();
            panel.innerHTML = (data.runs || []).map(run => `<p><button type="button" data-run="${this._esc(run.run_id)}">${this._esc(run.created_at)} · ${this._esc(run.status)}</button></p>`).join('');
            panel.querySelectorAll('[data-run]').forEach(button => button.addEventListener('click', async () => {
                const run = await API.getSecurityAgentRun(button.dataset.run);
                const output = document.getElementById('so-agent-result');
                output.innerHTML = this._runResult(run);
                this._bindRunActions(run, output);
            }));
        } catch (error) { panel.textContent = error.message; }
    },

    _bindRunActions(run, output) {
        const approve = output.querySelector('[data-approve]');
        const reject = output.querySelector('[data-reject]');
        const cancel = output.querySelector('[data-cancel]');
        if (approve) approve.addEventListener('click', () => this._resume(run, 'approve'));
        if (reject) reject.addEventListener('click', () => this._resume(run, 'reject'));
        if (cancel) cancel.addEventListener('click', async () => {
            try {
                const stopped = await API.cancelSecurityAgent(run.run_id);
                output.innerHTML = this._runResult(stopped);
            } catch (error) { output.textContent = error.message; }
        });
        output.querySelectorAll('[data-export]').forEach(button => button.addEventListener('click', async () => {
            button.disabled = true;
            try { await API.downloadSecurityAgentRun(run.run_id, button.dataset.export); }
            catch (error) { output.textContent = error.message; }
            finally { button.disabled = false; }
        }));
    },

    _bind() {
        document.getElementById('so-agent-form').addEventListener('submit', e => this._runAgent(e));
        document.getElementById('so-upload-form').addEventListener('submit', e => this._upload(e));
        document.getElementById('so-rag-form').addEventListener('submit', e => this._search(e));
        document.getElementById('so-immune-form').addEventListener('submit', e => this._learn(e));
        document.getElementById('so-memory-form').addEventListener('submit', e => this._remember(e));
        document.getElementById('so-rageval-run').addEventListener('click', () => this._evaluateRag());
    },

    async _refresh() {
        const [evidence, antibodies, memories, tools, benchmarks] = await Promise.all([
            API.listSecurityEvidence(), API.listAntibodies(), API.listAgentMemories(),
            API.listSecurityAgentTools(), API.listSecurityBenchmarks(),
        ]);
        this._renderEvidence(evidence.evidence || []);
        this._renderAntibodies(antibodies.antibodies || []);
        this._renderMemories(memories.memories || []);
        this._renderAgentTools(tools.tools || []);
        this._renderBenchmarks(benchmarks);
    },

    async _runAgent(event) {
        event.preventDefault(); const form = new FormData(event.currentTarget);
        const output = document.getElementById('so-agent-result'); output.textContent = 'Running bounded workflow…';
        try {
            let policyChanges = {}; const raw = String(form.get('policy_changes') || '').trim();
            if (raw) policyChanges = JSON.parse(raw);
            let run = await API.startSecurityAgent({
                query: form.get('query'), requested_task: form.get('requested_task'),
                session_keys: String(form.get('session_keys') || '').split(',').map(v => v.trim()).filter(Boolean),
                evidence_ids: String(form.get('evidence_ids') || '').split(',').map(v => v.trim()).filter(Boolean), document_types: [], policy_changes: policyChanges,
            });
            run = await this._pollRun(run, output);
            output.innerHTML = this._runResult(run);
            await this._modelStatus();
            this._bindRunActions(run, output);
        } catch (error) { output.textContent = error.message; }
    },

    async _pollRun(run, output) {
        for (let attempt = 0; attempt < 80 && ['queued', 'running'].includes(run.status); attempt += 1) {
            output.innerHTML = this._runResult(run);
            this._bindRunActions(run, output);
            await new Promise(resolve => setTimeout(resolve, 750));
            run = await API.getSecurityAgentRun(run.run_id);
        }
        return run;
    },

    async _resume(run, decision) {
        const output = document.getElementById('so-agent-result');
        try {
            const result = await API.resumeSecurityAgent(run.run_id, {
                decision, proposal_hash: run.approval_hash, approved_by: 'local-security-admin',
            });
            output.innerHTML = this._runResult(result);
        } catch (error) { output.textContent = error.message; }
    },

    _runResult(run) {
        const result = run.result || {}; const state = run.state || {};
        const approval = (run.status === 'awaiting_approval' ? `<div class="so-approval"><b>Human approval required</b><code>${this._esc(run.approval_hash)}</code><button data-approve>Approve exact proposal</button><button class="ghost" data-reject>Reject</button></div>` : '') + (['queued', 'running', 'awaiting_approval'].includes(run.status) ? '<button type="button" data-cancel>Cancel investigation</button>' : '');
        const steps = (run.events || []).map(e => `<article><b>${this._esc(e.node_name)}</b><small>${this._esc(e.created_at)} · ${this._esc(e.event_type)}</small><details><summary>Execution details</summary><pre>${this._esc(JSON.stringify(e.payload, null, 2))}</pre></details></article>`).join('');
        const details = result.analysis || result.evaluation ? `<details><summary>Findings and evaluation</summary><pre>${this._esc(JSON.stringify({analysis: result.analysis, evaluation: result.evaluation}, null, 2))}</pre></details>` : '';
        const proposal = state.policy_proposal ? `<details open><summary>Proposed policy and simulation</summary><pre>${this._esc(JSON.stringify({proposal: state.policy_proposal, simulation: state.evaluation}, null, 2))}</pre></details>` : '';
        const exports = run.status === 'completed' ? '<p><button type="button" data-export="markdown">Download Markdown report</button> · <button type="button" data-export="json">Download evidence JSON</button></p>' : '';
        return `<div class="so-run-head"><b>${this._esc(state.task_type || run.task_type)}</b><span class="so-pill ${this._esc(run.status)}">${this._esc(run.status)}</span></div><p>${this._esc(result.summary || run.error || 'Workflow state persisted.')}</p><small>${this._esc(result.model_mode || '')}${result.degraded ? ' · Offline fallback' : ''}</small>${(result.citations || []).map(c => `<small>↳ ${this._esc(c)}</small>`).join('')}${details}${proposal}${steps}${exports}${approval}`;
    },

    async _upload(event) {
        event.preventDefault(); const form = new FormData(event.currentTarget); const file = form.get('file');
        try {
            const evidence = await API.uploadSecurityEvidence(file);
            await API.indexSecurityEvidence(evidence.evidence_id, {
                title: form.get('title') || file.name, document_type: form.get('document_type'), metadata: {},
            });
            event.currentTarget.reset(); await this._refresh();
        } catch (error) { document.getElementById('so-evidence').textContent = error.message; }
    },

    async _search(event) {
        event.preventDefault(); const form = new FormData(event.currentTarget); const root = document.getElementById('so-rag-result');
        root.textContent = 'Searching…';
        try {
            const data = await API.searchSecurityKnowledge(form.get('query'));
            root.innerHTML = (data.results || []).map(item => `<article><b>${this._esc(item.citation)}</b><span>${this._esc(item.text)}</span><small><span>hybrid score</span> ${Number(item.score).toFixed(3)}</small></article>`).join('') || 'No grounded evidence found.';
        } catch (error) { root.textContent = error.message; }
    },

    async _learn(event) {
        event.preventDefault(); const form = new FormData(event.currentTarget);
        try {
            await API.learnAntibodyFromSession({ runtime_kind: form.get('runtime_kind'), session_id: form.get('session_id'), name: form.get('name'), description: 'Created from confirmed local session', source_evidence_ids: [], similarity_threshold: .75, max_score_delta: 20 });
            await this._refresh();
        } catch (error) { document.getElementById('so-antibodies').textContent = error.message; }
    },

    async _transition(id, target) {
        try { await API.transitionAntibody(id, target, target === 'active' ? 'local-security-admin' : null); await this._refresh(); }
        catch (error) { document.getElementById('so-antibodies').textContent = error.message; }
    },

    async _remember(event) {
        event.preventDefault(); const form = new FormData(event.currentTarget);
        try {
            const ids = String(form.get('evidence_ids') || '').split(',').map(v => v.trim()).filter(Boolean);
            await API.createAgentMemory({ memory_type: form.get('memory_type'), subject_key: form.get('subject_key'), summary: form.get('summary'), evidence_ids: ids, confirmed: true, confidence: 1, ttl_days: 365 });
            event.currentTarget.reset(); await this._refresh();
        } catch (error) { document.getElementById('so-memories').textContent = error.message; }
    },

    _renderEvidence(items) { document.getElementById('so-evidence').innerHTML = items.slice(0, 8).map(item => `<article><b>${this._esc(item.source_name)}</b><span>${this._esc(item.evidence_type)}</span><small>${this._esc(item.evidence_id)}</small></article>`).join('') || '<p>No evidence uploaded.</p>'; },
    _renderMemories(items) {
        const root = document.getElementById('so-memories');
        root.innerHTML = items.slice(0, 8).map(item => `<article><div><b>${this._esc(item.subject_key)}</b><span>${this._esc(item.summary)}</span><small>${this._esc(item.memory_type)} · <span>${item.confirmed ? 'confirmed' : 'ephemeral'}</span></small></div><button class="ghost" data-memory="${this._esc(item.memory_id)}">Delete</button></article>`).join('') || '<p>No governed memory.</p>';
        root.querySelectorAll('[data-memory]').forEach(button => button.addEventListener('click', () => this._deleteMemory(button.dataset.memory)));
    },

    async _deleteMemory(memoryId) {
        try { await API.deleteAgentMemory(memoryId); await this._refresh(); }
        catch (error) { document.getElementById('so-memories').textContent = error.message; }
    },

    async _evaluateRag() {
        const root = document.getElementById('so-rageval-result');
        const form = new FormData(document.getElementById('so-rageval-form'));
        let cases;
        try { cases = JSON.parse(String(form.get('cases') || '').trim()); }
        catch (error) { root.textContent = 'Evaluation cases must be valid JSON.'; return; }
        if (!Array.isArray(cases) || !cases.length) { root.textContent = 'Add at least one evaluation case.'; return; }
        root.textContent = 'Evaluating retrieval…';
        try {
            const result = await API.evaluateSecurityRag(cases, Number(form.get('k')) || 5);
            root.innerHTML = `<span class="so-cred-chip ok">Recall@k: ${this._num(result.recall_at_k)}</span> <span class="so-cred-chip ok">MRR: ${this._num(result.mrr)}</span> <span class="so-cred-chip">Cases: ${this._esc(result.queries)}</span>`;
        } catch (error) { root.textContent = error.message; }
    },

    _renderAgentTools(items) {
        const root = document.getElementById('so-agent-tools');
        root.innerHTML = items.map(tool => `<article><div><b>${this._esc(tool.name)}</b><small>${this._esc(tool.required_role)} · ${this._esc(tool.timeout_seconds)}s</small></div><span class="so-pill">${tool.read_only ? 'read-only' : 'write'}</span></article>`).join('') || '<p>No Agent tools registered.</p>';
    },

    _renderBenchmarks(data) {
        const root = document.getElementById('so-benchmarks');
        if (!data || data.status !== 'available') {
            root.textContent = (data && data.reason) || 'Benchmark report is unavailable.';
            return;
        }
        const rows = (data.benchmarks || []).map(bench => {
            const variants = (bench.results || []).map(r => `<article><b>${this._esc(r.variant)}</b><span>recall ${this._num(r.attack_detection_recall)} · FPR ${this._num(r.benign_false_positive_rate)} · ${this._esc(r.cases)} cases</span></article>`).join('');
            return `<details><summary>${this._esc(bench.benchmark)} · ${this._esc(bench.case_count)} cases (${this._esc(bench.malicious_count)} malicious)</summary>${variants}</details>`;
        }).join('');
        const limits = (data.limitations || []).map(l => `<small>↳ ${this._esc(l)}</small>`).join('');
        root.innerHTML = rows + limits + `<small>report ${this._esc(String(data.report_sha256 || '').slice(0, 16))}…</small>`;
    },

    _num(value, digits = 3) { const n = Number(value); return Number.isFinite(n) ? n.toFixed(digits) : '—'; },
    _renderAntibodies(items) {
        const root = document.getElementById('so-antibodies');
        root.innerHTML = items.map(item => `<article><div><b>${this._esc(item.name)}</b><small><span>${this._esc(item.status)}</span> · <span>maximum contribution</span> +${Number(item.max_score_delta)}</small></div><div>${item.status === 'candidate' ? `<button data-id="${this._esc(item.antibody_id)}" data-target="shadow">Start shadow</button>` : ''}${item.status === 'shadow' ? `<button data-id="${this._esc(item.antibody_id)}" data-target="active">Approve active</button>` : ''}${['active','decaying'].includes(item.status) ? `<button data-id="${this._esc(item.antibody_id)}" data-target="retired" class="ghost">Retire</button>` : ''}</div></article>`).join('') || '<p>No learned antibodies.</p>';
        root.querySelectorAll('[data-target]').forEach(button => button.addEventListener('click', () => this._transition(button.dataset.id, button.dataset.target)));
    },

    _esc(value) { const node = document.createElement('div'); node.textContent = String(value == null ? '' : value); return node.innerHTML; },
    _style() {
        if (document.getElementById('so-style')) return; const style = document.createElement('style'); style.id = 'so-style';
        style.textContent = `.so-hero{display:flex;justify-content:space-between;gap:20px;padding:24px;border:1px solid rgba(124,108,255,.35);border-radius:18px;background:radial-gradient(circle at 85% 10%,rgba(124,108,255,.18),transparent 38%),var(--bg-card);margin-bottom:16px}.so-hero h2{margin:5px 0;color:var(--text-primary)}.so-hero p,.so-card header p{margin:0;color:var(--text-muted);font-size:12px}.so-kicker{font-size:10px;letter-spacing:1.5px;color:#9f94ff}.so-status{align-self:center;color:#9ee7c1;font-size:12px}.so-status i{display:inline-block;width:7px;height:7px;background:#10b981;border-radius:50%;margin-right:7px}.so-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.so-card{padding:17px;border:1px solid var(--border-default);border-radius:14px;background:var(--bg-card);min-width:0}.so-agent{grid-column:span 2}.so-wide{grid-column:span 2}.so-card header{display:flex;gap:11px;margin-bottom:13px}.so-card header>span{font-size:10px;color:#9f94ff;border:1px solid rgba(124,108,255,.35);height:22px;padding:3px 6px;border-radius:6px}.so-card h3{margin:0 0 2px;color:var(--text-primary)}.so-card form{display:flex;flex-direction:column;gap:8px}.so-card input,.so-card textarea,.so-card select{background:var(--bg-primary);border:1px solid var(--border-default);color:var(--text-primary);padding:9px;border-radius:8px}.so-card textarea{min-height:70px;resize:vertical}.so-card button{border:0;border-radius:8px;background:var(--accent-primary);color:white;padding:9px 12px;cursor:pointer}.so-card button.ghost{background:transparent;border:1px solid var(--border-default);color:var(--text-secondary)}.so-row,.so-inline{display:flex!important;flex-direction:row!important;gap:8px}.so-row>*:not(button),.so-inline input{flex:1}.so-output,.so-list{margin-top:12px;color:var(--text-secondary);font-size:12px}.so-output article,.so-list article{padding:9px 0;border-top:1px solid var(--border-default);display:flex;flex-direction:column;gap:3px}.so-list article{flex-direction:row;justify-content:space-between;align-items:center}.so-list small,.so-output small{display:block;color:var(--text-muted)}.so-run-head{display:flex;justify-content:space-between}.so-pill{padding:2px 7px;border-radius:999px;background:rgba(96,165,250,.14);color:#60a5fa}.so-pill.completed{color:#10b981;background:rgba(16,185,129,.14)}.so-pill.failed{color:#ef4444}.so-approval{margin-top:10px;padding:10px;border:1px solid #f59e0b;border-radius:9px}.so-approval code{display:block;word-break:break-all;margin:6px 0;color:var(--text-muted)}.so-credentials{grid-column:span 2}.so-cred-badge{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:11px}.so-cred-chip{font-size:11px;padding:3px 9px;border-radius:999px;border:1px solid var(--border-default);color:var(--text-secondary)}.so-cred-chip.ok{color:#10b981;border-color:rgba(16,185,129,.4);background:rgba(16,185,129,.12)}.so-cred-chip.warn{color:#f59e0b;border-color:rgba(245,158,11,.45);background:rgba(245,158,11,.12)}.so-cred-toggle{display:flex;align-items:center;gap:7px;color:var(--text-secondary);font-size:12px}.so-cred-toggle input{width:auto}.so-card button[disabled]{opacity:.45;cursor:not-allowed}@media(max-width:900px){.so-grid{grid-template-columns:1fr}.so-agent,.so-credentials,.so-wide{grid-column:auto}.so-row,.so-inline{flex-direction:column!important}.so-hero{flex-direction:column}}`;
        document.head.appendChild(style);
    },
};
