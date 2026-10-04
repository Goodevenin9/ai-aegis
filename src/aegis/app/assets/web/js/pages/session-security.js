/** Session Security — causal intent/behaviour chain and deterministic drift state. */

const SessionSecurityPage = {
    sessions: [],
    selected: null,
    currentDetail: null,
    thresholds: { confirm: 40, block: 80 },
    manifests: [],
    manifestPresets: {
        readonly: ['file_read'],
        local: ['file_read', 'file_write', 'shell_exec'],
        full: ['file_read', 'file_write', 'shell_exec', 'network_outbound'],
    },

    async render(container) {
        container.textContent = '';
        Header.setPageInfo(
            'Session Security',
            'Intent flow, behaviour flow and five-stage evidence across an entire agent session.',
        );
        this._style();
        const controls = document.createElement('section');
        controls.className = 'ss-controls';
        controls.innerHTML = '<div class="ss-title">P1 policy & evaluation</div><div id="ss-policy">Loading policy…</div>';
        container.appendChild(controls);
        const shell = document.createElement('div');
        shell.className = 'ss-shell';
        shell.innerHTML = `
            <section class="ss-list"><div class="ss-title">Active sessions</div><div id="ss-sessions"></div></section>
            <section class="ss-detail" id="ss-detail"><div class="ss-empty">Loading session evidence…</div></section>`;
        container.appendChild(shell);
        const immunity = document.createElement('section');
        immunity.className = 'ss-panel ss-immunity';
        immunity.innerHTML = '<div class="ss-title">Immunity matches</div><div id="ss-immune-matches">Loading immunity matches…</div>';
        container.appendChild(immunity);
        const [data, policy, manifests, dataset, immune] = await Promise.all([
            API.getRuntimeSessions(200), API.getRuntimePipelineConfig(),
            API.getRuntimeManifests(), API.getRuntimeEvaluationDataset(), API.listImmuneMatches(),
        ]);
        this.sessions = data.sessions || [];
        if (policy && policy.config) {
            this.thresholds = {
                confirm: Number(policy.config.confirm_threshold || 40),
                block: Number(policy.config.block_threshold || 80),
            };
        }
        this._renderPolicy(policy, manifests, dataset);
        this._renderList();
        this._renderImmuneMatches(immune);
        if (this.sessions.length) await this._select(this.sessions[0]);
        else document.getElementById('ss-detail').innerHTML = '<div class="ss-empty">No session evidence yet. Connect an agent and submit a prompt to begin.</div>';
    },

    _renderList() {
        const root = document.getElementById('ss-sessions');
        root.textContent = '';
        this.sessions.forEach(session => {
            const button = document.createElement('button');
            button.className = 'ss-session' + (this.selected === session.session_key ? ' active' : '');
            const score = Number(session.drift_score || 0);
            button.innerHTML = `<span><b>${this._esc(session.runtime_kind)}</b><small>${this._esc(session.session_id)}</small></span><strong class="${this._risk(score)}">${score}</strong>`;
            button.addEventListener('click', () => this._select(session));
            root.appendChild(button);
        });
    },

    async _select(session) {
        this.selected = session.session_key;
        this._renderList();
        const detail = await API.getRuntimeSession(session.session_id, session.runtime_kind);
        this.currentDetail = detail;
        this._renderDetail(detail);
    },

    _renderDetail(data) {
        const root = document.getElementById('ss-detail');
        if (!data) { root.innerHTML = '<div class="ss-empty">Session details are unavailable.</div>'; return; }
        const state = data.state || {};
        const score = Number(state.drift_score || 0);
        const integrity = data.integrity || {};
        const stages = ['Boundary', 'Capability', 'Radius', 'Drift', 'Friction'];
        const latestDecision = [...(data.events || [])].reverse()
            .find(event => event.event_type === 'before_tool_call');
        const actualLayers = (latestDecision && latestDecision.payload && latestDecision.payload.layers) || {};
        const explanation = (latestDecision && latestDecision.payload && latestDecision.payload.explanation) || null;
        const latestAction = latestDecision && latestDecision.payload && latestDecision.payload.action;
        const latestCapability = actualLayers.capability && actualLayers.capability.value;
        root.innerHTML = `
            <div class="ss-head"><div><div class="ss-title">${this._esc(data.runtime_kind)} · ${this._esc(data.session_id)}</div><div class="ss-intent">${this._esc(state.original_intent || 'Intent baseline not captured')}</div><button class="ss-btn" id="ss-export">Export evidence JSON</button></div><div class="ss-score ${this._risk(score)}"><b>${score}</b><span>DRIFT</span></div></div>
            <div class="ss-stages">${stages.map(s => this._stage(s, actualLayers[s.toLowerCase()])).join('')}</div>
            ${explanation ? `<div class="ss-panel"><div class="ss-title">确定性裁决解释</div><p>${this._esc(explanation.conclusion || '')}</p><div class="ss-explanation">${(explanation.evidence || []).map(item => `<span><b>${this._esc(item.layer)}</b> ${this._esc(item.code)} · ${this._esc(item.description)}</span>`).join('') || '<span>无中高风险证据</span>'}</div>${latestAction === 'confirm' && latestCapability ? `<button class="ss-btn" id="ss-trust">人工确认：短期信任 ${this._esc(latestCapability)}</button>` : ''}<span id="ss-trust-status"></span></div>` : ''}
            <div class="ss-panel"><div class="ss-title">Risk curve</div>${this._curve(data.risk_curve || [])}</div>
            <div class="ss-panel"><div class="ss-title">Causal timeline <span class="ss-integrity ${integrity.valid ? 'ok' : 'bad'}">${integrity.valid ? 'HASH CHAIN VERIFIED' : 'INTEGRITY FAILURE'}</span></div><div class="ss-events">${(data.events || []).map(e => this._event(e)).join('') || '<div class="ss-empty">No events</div>'}</div></div>`;
        document.getElementById('ss-export').addEventListener('click', () => this._exportEvidence());
        const trust = document.getElementById('ss-trust');
        if (trust) trust.addEventListener('click', () => this._grantTrust(data, latestCapability));
    },

    _renderPolicy(policyData, manifestData, dataset) {
        const root = document.getElementById('ss-policy');
        const cfg = (policyData && policyData.config) || {};
        const capabilities = (manifestData && manifestData.known_capabilities) || [];
        this.manifests = (manifestData && manifestData.manifests) || [];
        const defaults = this.manifests
            .find(item => item.runtime_kind === 'default' && item.manifest_id === 'default') || {};
        root.innerHTML = `
            <div class="ss-policy-grid">
              <form id="ss-config-form"><b>Friction / Drift thresholds</b>
                <label>Confirm <input name="confirm_threshold" type="number" min="1" max="99" value="${Number(cfg.confirm_threshold || 40)}"></label>
                <label>Block <input name="block_threshold" type="number" min="2" max="100" value="${Number(cfg.block_threshold || 80)}"></label>
                <label>Theme shift <input name="theme_shift_weight" type="number" min="0" max="100" value="${Number(cfg.theme_shift_weight == null ? 20 : cfg.theme_shift_weight)}"></label>
                <label>Permission probe <input name="permission_probe_weight" type="number" min="0" max="100" value="${Number(cfg.permission_probe_weight == null ? 20 : cfg.permission_probe_weight)}"></label>
                <label>Escalation <input name="request_escalation_weight" type="number" min="0" max="100" value="${Number(cfg.request_escalation_weight == null ? 20 : cfg.request_escalation_weight)}"></label>
                <label>Explicit harm <input name="explicit_harm_weight" type="number" min="0" max="100" value="${Number(cfg.explicit_harm_weight == null ? 20 : cfg.explicit_harm_weight)}"></label>
                <label>Unauthorized target <input name="unauthorized_target_weight" type="number" min="0" max="100" value="${Number(cfg.unauthorized_target_weight == null ? 0 : cfg.unauthorized_target_weight)}"></label>
                <label>Deception / evasion <input name="deception_or_evasion_weight" type="number" min="0" max="100" value="${Number(cfg.deception_or_evasion_weight == null ? 0 : cfg.deception_or_evasion_weight)}"></label>
                <label>Irreversible impact <input name="irreversible_impact_weight" type="number" min="0" max="100" value="${Number(cfg.irreversible_impact_weight == null ? 5 : cfg.irreversible_impact_weight)}"></label>
                <label>Focused verification <input name="harm_verified_weight" type="number" min="0" max="100" value="${Number(cfg.harm_verified_weight == null ? 20 : cfg.harm_verified_weight)}"></label>
                <label>Inferred capability <input name="intent_capability_weight" type="number" min="0" max="100" value="${Number(cfg.intent_capability_weight == null ? 10 : cfg.intent_capability_weight)}"></label>
                <label>Harm + high impact <input name="harmful_high_impact_weight" type="number" min="0" max="100" value="${Number(cfg.harmful_high_impact_weight == null ? 20 : cfg.harmful_high_impact_weight)}"></label>
                <label>Harm + external write <input name="harmful_external_write_weight" type="number" min="0" max="100" value="${Number(cfg.harmful_external_write_weight == null ? 10 : cfg.harmful_external_write_weight)}"></label>
                <label>Sensitive → external <input name="sensitive_sequence_weight" type="number" min="0" max="100" value="${Number(cfg.sensitive_sequence_weight == null ? 15 : cfg.sensitive_sequence_weight)}"></label>
                <label>Retry 2+ <input name="repeated_retry_weight" type="number" min="0" max="100" value="${Number(cfg.repeated_retry_weight || 15)}"></label>
                <label>Retry 3+ <input name="third_retry_weight" type="number" min="0" max="100" value="${Number(cfg.third_retry_weight || 30)}"></label>
                <label>Safe-turn decay <input name="safe_turn_decay" type="number" min="0" max="100" value="${Number(cfg.safe_turn_decay == null ? 10 : cfg.safe_turn_decay)}"></label>
                <label>Immunity cap <input name="max_immune_session_score" type="number" min="0" max="30" value="${Number(cfg.max_immune_session_score == null ? 25 : cfg.max_immune_session_score)}"></label>
                <input name="max_drift_score" type="hidden" value="${Number(cfg.max_drift_score || 100)}">
                <button class="ss-btn" type="submit">Save configuration</button><span id="ss-config-status"></span>
              </form>
              <form id="ss-manifest-form" class="ss-manifest-card"><div class="ss-manifest-heading"><div><b>Developer capability Manifest</b><small>Declare normal project abilities without disabling the five-stage pipeline.</small></div><span class="ss-manifest-state" id="ss-manifest-state">READ ONLY</span></div>
                <div class="ss-preset-grid" role="group" aria-label="Manifest presets">
                  <button type="button" class="ss-preset active" data-manifest-preset="readonly"><b>Read only</b><small>Inspect code without changes</small></button>
                  <button type="button" class="ss-preset" data-manifest-preset="local"><b>Local development</b><small>Read, edit, test and build</small></button>
                  <button type="button" class="ss-preset" data-manifest-preset="full"><b>Full development</b><small>Add outbound network access</small></button>
                </div>
                <div class="ss-manifest-fields">
                  <label>Runtime <select name="runtime_kind"><option value="default">All supported agents</option><option value="claude-code">Claude Code</option><option value="codex">Codex</option><option value="cursor">Cursor</option><option value="copilot-cli">GitHub Copilot CLI</option></select></label>
                  <label>Manifest ID <input name="manifest_id" value="${this._esc(defaults.manifest_id || 'default')}" placeholder="default"></label>
                  <label>Session scope <input name="session_id" value="${this._esc(defaults.session_id || '*')}" placeholder="* or exact session"></label>
                  <label class="ss-project-root">Project root <input name="project_root" value="${this._esc(defaults.project_root || '')}" placeholder="C:/workspace/project"><small>Required for write, shell or network access. Use the repository root.</small></label>
                </div>
                <details class="ss-advanced"><summary>Advanced capability selection</summary><div class="ss-capabilities">${capabilities.map(cap => `<label><input type="checkbox" name="capability" value="${this._esc(cap)}" ${(defaults.allowed_capabilities || ['file_read']).includes(cap) ? 'checked' : ''}>${this._esc(cap)}</label>`).join('')}</div></details>
                <div class="ss-manifest-summary" id="ss-manifest-summary"></div>
                <div class="ss-manifest-warning" id="ss-manifest-warning"></div>
                <button class="ss-btn" type="submit">Save and activate Manifest</button><span class="ss-save-status" id="ss-manifest-status" role="status"></span>
                ${this.manifests.length ? `<div class="ss-saved-manifests"><small>Saved Manifests</small>${this.manifests.map((item, index) => `<button type="button" data-manifest-index="${index}">${this._esc(item.runtime_kind)} · ${this._esc(item.manifest_id)} · ${this._esc(item.session_id || '*')}</button>`).join('')}</div>` : ''}
              </form>
              <div class="ss-evaluation-card"><b>Chinese A/B evaluation</b><p>${dataset ? `${Number(dataset.case_count)} cases · ${Number(dataset.benign)} benign · ${Number(dataset.malicious)} malicious` : 'Dataset unavailable'}</p><button class="ss-btn" id="ss-run-eval">Run three-way evaluation</button><div id="ss-eval-result"></div></div>
            </div>`;
        document.getElementById('ss-config-form').addEventListener('submit', event => this._saveConfig(event));
        document.getElementById('ss-manifest-form').addEventListener('submit', event => this._saveManifest(event));
        document.querySelectorAll('[data-manifest-preset]').forEach(button => {
            button.addEventListener('click', () => this._applyManifestPreset(button.dataset.manifestPreset));
        });
        document.querySelectorAll('#ss-manifest-form input[name="capability"]').forEach(input => {
            input.addEventListener('change', () => this._syncManifestSummary());
        });
        document.querySelector('#ss-manifest-form input[name="project_root"]')
            .addEventListener('input', () => this._syncManifestSummary());
        document.querySelectorAll('[data-manifest-index]').forEach(button => {
            button.addEventListener('click', () => this._loadManifest(Number(button.dataset.manifestIndex)));
        });
        if (defaults.runtime_kind) {
            document.querySelector('#ss-manifest-form select[name="runtime_kind"]').value = defaults.runtime_kind;
        }
        this._syncManifestSummary();
        document.getElementById('ss-run-eval').addEventListener('click', () => this._runEvaluation());
    },

    _selectedCapabilities() {
        return [...document.querySelectorAll('#ss-manifest-form input[name="capability"]:checked')]
            .map(input => input.value);
    },

    _applyManifestPreset(preset) {
        const selected = new Set(this.manifestPresets[preset] || []);
        document.querySelectorAll('#ss-manifest-form input[name="capability"]').forEach(input => {
            input.checked = selected.has(input.value);
        });
        document.querySelectorAll('[data-manifest-preset]').forEach(button => {
            button.classList.toggle('active', button.dataset.manifestPreset === preset);
        });
        this._syncManifestSummary();
    },

    _manifestPresetFor(capabilities) {
        const selected = [...capabilities].sort().join('|');
        return Object.entries(this.manifestPresets)
            .find(([, values]) => [...values].sort().join('|') === selected)?.[0] || 'custom';
    },

    _syncManifestSummary() {
        const form = document.getElementById('ss-manifest-form');
        if (!form) return;
        const capabilities = this._selectedCapabilities();
        const preset = this._manifestPresetFor(capabilities);
        const labels = { readonly: 'READ ONLY', local: 'LOCAL DEV', full: 'FULL DEV', custom: 'CUSTOM' };
        const state = document.getElementById('ss-manifest-state');
        state.textContent = labels[preset];
        state.className = `ss-manifest-state ${preset}`;
        document.querySelectorAll('[data-manifest-preset]').forEach(button => {
            button.classList.toggle('active', button.dataset.manifestPreset === preset);
        });
        const root = form.querySelector('[name="project_root"]').value.trim();
        document.getElementById('ss-manifest-summary').innerHTML = `
            <b>Effective scope</b><span>${root ? this._esc(root) : 'Project root is not set'}</span>
            <div>${capabilities.map(cap => `<code>${this._esc(cap)}</code>`).join('') || '<em>No capabilities selected</em>'}</div>`;
        const warning = document.getElementById('ss-manifest-warning');
        if (preset === 'full') {
            warning.className = 'ss-manifest-warning high';
            warning.innerHTML = '<b>Full development is broad.</b><span>Normal coding becomes frictionless, but Git push, publishing, deployment and external writes still need action-level policies. Boundary and Drift remain active.</span>';
        } else if (preset === 'local') {
            warning.className = 'ss-manifest-warning medium';
            warning.innerHTML = '<b>Recommended starting point.</b><span>Local edits, tests and builds are allowed. Documentation and MCP network calls still request review.</span>';
        } else {
            warning.className = 'ss-manifest-warning low';
            warning.innerHTML = '<b>Lowest-friction risk.</b><span>Only project reads are declared. Writes, shell commands and network calls request review.</span>';
        }
    },

    _loadManifest(index) {
        const manifest = this.manifests[index];
        const form = document.getElementById('ss-manifest-form');
        if (!manifest || !form) return;
        form.querySelector('[name="runtime_kind"]').value = manifest.runtime_kind || 'default';
        form.querySelector('[name="manifest_id"]').value = manifest.manifest_id || 'default';
        form.querySelector('[name="session_id"]').value = manifest.session_id || '*';
        form.querySelector('[name="project_root"]').value = manifest.project_root || '';
        const selected = new Set(manifest.allowed_capabilities || []);
        form.querySelectorAll('[name="capability"]').forEach(input => {
            input.checked = selected.has(input.value);
        });
        this._syncManifestSummary();
        document.getElementById('ss-manifest-status').textContent = 'Loaded. Review and save to activate changes.';
    },

    async _saveConfig(event) {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const keys = ['confirm_threshold', 'block_threshold', 'theme_shift_weight', 'permission_probe_weight', 'request_escalation_weight', 'explicit_harm_weight', 'unauthorized_target_weight', 'deception_or_evasion_weight', 'irreversible_impact_weight', 'harm_verified_weight', 'intent_capability_weight', 'harmful_high_impact_weight', 'harmful_external_write_weight', 'sensitive_sequence_weight', 'repeated_retry_weight', 'third_retry_weight', 'safe_turn_decay', 'max_drift_score', 'max_immune_session_score'];
        const status = document.getElementById('ss-config-status');
        try {
            const run = await API.updateRuntimePipelineConfig(Object.fromEntries(keys.map(key => [key, Number(form.get(key))])));
            status.textContent = `Proposal ${run.run_id || ''} created. Review and approve it in Security Operations.`;
        } catch (error) { status.textContent = error.message; }
    },

    async _saveManifest(event) {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const status = document.getElementById('ss-manifest-status');
        const capabilities = form.getAll('capability');
        const projectRoot = String(form.get('project_root') || '').trim();
        const requiresRoot = capabilities.some(cap => cap !== 'file_read');
        if (requiresRoot && !/^(?:[a-zA-Z]:[\\/]|\/)/.test(projectRoot)) {
            status.textContent = 'Enter an absolute project root before enabling write, shell or network access.';
            event.currentTarget.querySelector('[name="project_root"]').focus();
            return;
        }
        const preset = this._manifestPresetFor(capabilities);
        if (preset === 'full' && !window.confirm('Full development also enables outbound network access. Continue with this project-scoped Manifest?')) return;
        try {
            await API.updateRuntimeManifest(form.get('runtime_kind'), form.get('manifest_id'), {
                allowed_capabilities: capabilities,
                project_root: projectRoot || null,
                description: `Developer Manifest (${preset}) configured from Session Security`,
                session_id: form.get('session_id') || '*',
            });
            status.textContent = 'Saved and active for matching sessions.';
        } catch (error) { status.textContent = error.message; }
    },

    async _runEvaluation() {
        const root = document.getElementById('ss-eval-result');
        root.textContent = 'Running…';
        try {
            const report = await API.runRuntimeEvaluation(false);
            root.innerHTML = `<table><thead><tr><th>Variant</th><th>Recall</th><th>FPR</th><th>Accuracy</th></tr></thead><tbody>${report.results.map(item => `<tr><td>${this._esc(item.variant)}</td><td>${(item.attack_recall * 100).toFixed(1)}%</td><td>${(item.benign_false_positive_rate * 100).toFixed(1)}%</td><td>${(item.accuracy * 100).toFixed(1)}%</td></tr>`).join('')}</tbody></table><small>${this._esc(report.judge_note)}</small>`;
        } catch (error) { root.textContent = error.message; }
    },

    _exportEvidence() {
        if (!this.currentDetail) return;
        const blob = new Blob([JSON.stringify(this.currentDetail, null, 2)], { type: 'application/json' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `aegis-session-${this.currentDetail.runtime_kind}-${this.currentDetail.session_id}.json`;
        link.click();
        URL.revokeObjectURL(link.href);
    },

    async _grantTrust(data, capability) {
        const status = document.getElementById('ss-trust-status');
        try {
            await API.grantRuntimeTrust({
                session_id: data.session_id,
                runtime_kind: data.runtime_kind,
                capability,
                ttl_seconds: 300,
                max_uses: 5,
            });
            status.textContent = '已由本地界面授权：5分钟或5次使用后失效';
        } catch (error) { status.textContent = error.message; }
    },

    _curve(points) {
        if (!points.length) return '<div class="ss-empty compact">No tool decision has changed drift yet.</div>';
        const w = 720, h = 150, pad = 18;
        const coords = points.map((p, i) => {
            const x = points.length === 1 ? w / 2 : pad + i * (w - pad * 2) / (points.length - 1);
            const y = h - pad - Math.max(0, Math.min(100, Number(p.drift_score))) * (h - pad * 2) / 100;
            return [x, y];
        });
        const line = coords.map(p => p.join(',')).join(' ');
        const yFor = score => h - pad - Math.max(0, Math.min(100, score)) * (h - pad * 2) / 100;
        return `<svg class="ss-curve" viewBox="0 0 ${w} ${h}" role="img" aria-label="Session drift risk curve"><line x1="${pad}" y1="${yFor(this.thresholds.confirm)}" x2="${w-pad}" y2="${yFor(this.thresholds.confirm)}" class="warn"/><line x1="${pad}" y1="${yFor(this.thresholds.block)}" x2="${w-pad}" y2="${yFor(this.thresholds.block)}" class="block"/><polyline points="${line}"/>${coords.map((p,i) => `<circle cx="${p[0]}" cy="${p[1]}" r="4"><title>${Number(points[i].drift_score)} · ${this._esc(points[i].action || 'allow')}</title></circle>`).join('')}</svg>`;
    },

    _event(event) {
        const payload = event.payload || {};
        const action = payload.action || '';
        const time = event.created_at ? new Date(event.created_at).toLocaleTimeString() : '';
        return `<article class="ss-event"><i></i><div><header><b>${this._esc(event.event_type)}</b><span>${this._esc(time)}</span>${action ? `<em class="${this._risk(Number(payload.drift_score || 0))}">${this._esc(action)}</em>` : ''}</header><p>${this._esc(event.content || payload.tool_name || this._signals(payload))}</p></div></article>`;
    },

    _signals(payload) {
        const signals = payload.signals || [];
        return signals.map(s => s.message || s.code).filter(Boolean).join(' · ');
    },

    _stage(name, layer) {
        if (!layer) return `<div><b>${name}</b><span>no evidence yet</span></div>`;
        const signals = (layer.signals || []).map(s => s.message || s.code).filter(Boolean);
        const flags = [layer.critical ? 'critical' : '', layer.requires_confirmation ? 'confirmation' : '']
            .filter(Boolean).join(' · ');
        const detail = signals.length ? signals.join(' · ') : (flags || 'no risk signal');
        return `<div><b>${name} · ${this._esc(layer.value || 'clear')}</b><span>${this._esc(detail)}</span></div>`;
    },

    _renderImmuneMatches(data) {
        const root = document.getElementById('ss-immune-matches');
        if (!root) return;
        const matches = (data && data.matches) || [];
        if (!matches.length) {
            root.innerHTML = '<div class="ss-empty compact">No antibody has matched a session yet. Approved antibodies appear here once they contribute to a drift score.</div>';
            return;
        }
        root.innerHTML = `<table><thead><tr><th>Antibody</th><th>Session</th><th>Similarity</th><th>Contribution</th><th>Applied</th><th>When</th></tr></thead><tbody>${matches.slice(0, 50).map(match => `<tr><td>${this._esc(match.antibody_id)}</td><td>${this._esc(match.session_key)}</td><td>${Number(match.similarity || 0).toFixed(2)}</td><td>+${Number(match.score_delta || 0)}</td><td>${match.effective ? 'yes' : 'no'}</td><td>${this._esc(match.created_at)}</td></tr>`).join('')}</tbody></table>`;
    },

    _risk(score) { return score >= this.thresholds.block ? 'critical' : score >= this.thresholds.confirm ? 'elevated' : score > 0 ? 'guarded' : 'clear'; },
    _esc(value) { const d = document.createElement('div'); d.textContent = String(value == null ? '' : value); return d.innerHTML; },

    _style() {
        if (document.getElementById('ss-style')) return;
        const style = document.createElement('style'); style.id = 'ss-style';
        style.textContent = `
            .ss-controls,.ss-list,.ss-detail,.ss-panel{background:var(--bg-card);border:1px solid var(--border-default);border-radius:12px}.ss-controls{padding:14px;margin-bottom:16px}.ss-policy-grid{display:grid;grid-template-columns:minmax(230px,.7fr) minmax(480px,1.3fr);grid-template-areas:"config manifest" "evaluation manifest";gap:18px;align-items:start}.ss-policy-grid form,.ss-policy-grid>div{display:flex;flex-direction:column;gap:7px}#ss-config-form{grid-area:config}.ss-manifest-card{grid-area:manifest}.ss-evaluation-card{grid-area:evaluation}.ss-policy-grid label{display:flex;justify-content:space-between;gap:8px;color:var(--text-secondary);font-size:12px}.ss-policy-grid input,.ss-policy-grid select{width:150px;background:var(--bg-primary);border:1px solid var(--border-default);border-radius:6px;color:var(--text-primary);padding:6px}.ss-manifest-card{padding:14px;border:1px solid var(--border-default);border-radius:11px;background:color-mix(in srgb,var(--bg-card) 86%,var(--accent-primary) 4%)}.ss-manifest-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}.ss-manifest-heading small{display:block;margin-top:4px;color:var(--text-muted);line-height:1.4}.ss-manifest-state{border-radius:999px;padding:4px 8px;font-size:9px;font-weight:800;letter-spacing:.7px;background:rgba(16,185,129,.12);color:#10b981;white-space:nowrap}.ss-manifest-state.local{background:rgba(96,165,250,.12);color:#60a5fa}.ss-manifest-state.full{background:rgba(245,158,11,.13);color:#f59e0b}.ss-manifest-state.custom{background:rgba(124,108,255,.13);color:var(--accent-primary)}.ss-preset-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:5px 0}.ss-preset{min-width:0;text-align:left;padding:9px;border:1px solid var(--border-default);border-radius:8px;background:var(--bg-primary);color:var(--text-primary);cursor:pointer}.ss-preset:hover,.ss-preset.active{border-color:var(--accent-primary);background:color-mix(in srgb,var(--accent-primary) 10%,var(--bg-primary))}.ss-preset b,.ss-preset small{display:block}.ss-preset small{margin-top:3px;color:var(--text-muted);font-size:9px;line-height:1.3}.ss-manifest-fields{display:grid;grid-template-columns:1fr 1fr;gap:7px}.ss-manifest-fields label{align-items:center}.ss-manifest-fields .ss-project-root{grid-column:1/-1}.ss-manifest-fields .ss-project-root input{width:58%}.ss-project-root small{max-width:145px;font-size:9px;line-height:1.3}.ss-advanced{border-top:1px solid var(--border-default);padding-top:7px}.ss-advanced summary{cursor:pointer;color:var(--text-secondary);font-size:11px}.ss-capabilities{display:grid;grid-template-columns:repeat(2,1fr);gap:4px;margin-top:8px}.ss-capabilities label{justify-content:flex-start}.ss-capabilities input{width:auto}.ss-manifest-summary{padding:9px;border-radius:8px;background:var(--bg-primary);font-size:11px;color:var(--text-secondary)}.ss-manifest-summary>b,.ss-manifest-summary>span{display:block}.ss-manifest-summary span{margin:3px 0 7px;word-break:break-all}.ss-manifest-summary code{display:inline-block;margin:2px 4px 0 0;padding:2px 5px;border-radius:4px;background:var(--bg-hover);color:var(--text-primary);font-size:9px}.ss-manifest-warning{display:flex;flex-direction:column;gap:3px;border-left:3px solid #10b981;padding:8px 10px;background:rgba(16,185,129,.07);font-size:10px;color:var(--text-secondary)}.ss-manifest-warning.medium{border-color:#60a5fa;background:rgba(96,165,250,.07)}.ss-manifest-warning.high{border-color:#f59e0b;background:rgba(245,158,11,.08)}.ss-manifest-warning b{color:var(--text-primary)}.ss-save-status{font-size:11px;color:var(--text-secondary)}.ss-saved-manifests{display:flex;flex-wrap:wrap;gap:5px;border-top:1px solid var(--border-default);padding-top:8px}.ss-saved-manifests small{width:100%;color:var(--text-muted)}.ss-saved-manifests button{border:1px solid var(--border-default);border-radius:6px;background:var(--bg-primary);color:var(--text-secondary);padding:4px 6px;font-size:9px;cursor:pointer}.ss-btn{margin-top:8px;padding:7px 10px;border:1px solid var(--border-default);border-radius:7px;background:var(--accent-primary);color:white;cursor:pointer}.ss-policy-grid table{width:100%;margin-top:9px;border-collapse:collapse;font-size:11px}.ss-policy-grid td,.ss-policy-grid th{padding:4px;border-bottom:1px solid var(--border-default);text-align:left}.ss-shell{display:grid;grid-template-columns:minmax(220px,28%) 1fr;gap:16px}.ss-list{padding:14px;align-self:start}.ss-detail{padding:18px;min-width:0}.ss-title{font-weight:700;color:var(--text-primary);margin-bottom:10px}.ss-session{width:100%;display:flex;justify-content:space-between;align-items:center;text-align:left;border:0;border-radius:9px;padding:10px;background:transparent;color:var(--text-primary);cursor:pointer}.ss-session:hover,.ss-session.active{background:var(--bg-hover)}.ss-session span{min-width:0}.ss-session small{display:block;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ss-session strong,.ss-score{color:#10b981}.ss-session .guarded,.ss-score.guarded{color:#60a5fa}.ss-session .elevated,.ss-score.elevated{color:#f59e0b}.ss-session .critical,.ss-score.critical{color:#ef4444}.ss-head{display:flex;justify-content:space-between;gap:20px}.ss-intent{color:var(--text-secondary);font-size:13px}.ss-score{text-align:center}.ss-score b{display:block;font-size:32px}.ss-score span{font-size:10px;letter-spacing:1px}.ss-stages{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:18px 0}.ss-stages div{padding:10px;border:1px solid var(--border-default);border-radius:9px}.ss-stages b,.ss-stages span{display:block}.ss-stages span{font-size:10px;color:var(--text-muted);margin-top:3px}.ss-panel{padding:14px;margin-top:12px}.ss-immunity table{width:100%;border-collapse:collapse;font-size:11px}.ss-immunity td,.ss-immunity th{padding:5px;border-bottom:1px solid var(--border-default);text-align:left}.ss-explanation{display:flex;flex-direction:column;gap:5px;color:var(--text-secondary);font-size:12px}.ss-curve{width:100%;height:150px;overflow:visible}.ss-curve polyline{fill:none;stroke:var(--accent-primary);stroke-width:3}.ss-curve circle{fill:var(--accent-primary)}.ss-curve line{stroke-width:1;stroke-dasharray:5 5}.ss-curve .warn{stroke:#f59e0b}.ss-curve .block{stroke:#ef4444}.ss-integrity{float:right;font-size:10px;letter-spacing:.7px}.ss-integrity.ok{color:#10b981}.ss-integrity.bad{color:#ef4444}.ss-event{display:grid;grid-template-columns:12px 1fr;gap:9px;padding:9px 0;border-top:1px solid var(--border-default)}.ss-event i{width:8px;height:8px;border-radius:50%;background:var(--accent-primary);margin-top:6px}.ss-event header{display:flex;gap:10px;align-items:center}.ss-event header span{color:var(--text-muted);font-size:11px}.ss-event em{margin-left:auto;font-style:normal;font-size:10px;text-transform:uppercase}.ss-event p{margin:3px 0 0;color:var(--text-secondary);font-size:12px;white-space:pre-wrap;word-break:break-word;max-height:70px;overflow:auto}.ss-empty{padding:50px 12px;text-align:center;color:var(--text-muted)}.ss-empty.compact{padding:24px}@media(max-width:900px){.ss-policy-grid{grid-template-columns:1fr;grid-template-areas:"manifest" "config" "evaluation"}.ss-manifest-fields{grid-template-columns:1fr}.ss-manifest-fields .ss-project-root{grid-column:auto}}@media(max-width:620px){.ss-preset-grid{grid-template-columns:1fr}.ss-project-root small{display:none}.ss-manifest-fields .ss-project-root input{width:150px}.ss-shell{grid-template-columns:1fr}.ss-stages{grid-template-columns:repeat(2,1fr)}}`;
        document.head.appendChild(style);
    },
};
