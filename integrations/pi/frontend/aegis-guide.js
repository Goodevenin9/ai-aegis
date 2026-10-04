/* Aegis Guide —— pi RPC 的浏览器客户端（纯 JS，无依赖）
 *
 * 用法：
 *   <link rel="stylesheet" href="aegis-guide.css">
 *   <script src="aegis-guide.js"></script>
 *   <script>
 *     const guide = new AegisGuide({ mount: "#aegis-guide", ws: "ws://127.0.0.1:8741/api/aegis-guide/ws" });
 *     // guide.prompt("介绍一下 Aegis 怎么接入 LangChain");
 *   </script>
 *
 * 它直接说 pi RPC 协议：
 *   发送 {"type":"prompt","message":...}
 *   接收 message_update / tool_execution_end / extension_ui_request ...
 */
(function () {
  "use strict";

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function renderTable(table) {
    const cols = table.columns || [];
    const rows = table.rows || [];
    const head = `<tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>`;
    const body = rows
      .map((r) => `<tr>${(r || []).map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`)
      .join("");
    return `<table class="ag-table"><thead>${head}</thead><tbody>${body}</tbody></table>`;
  }

  class AegisGuide {
    constructor(opts) {
      this.mount = typeof opts.mount === "string" ? document.querySelector(opts.mount) : opts.mount;
      this.wsUrl = opts.token
        ? `${opts.ws}?token=${encodeURIComponent(opts.token)}`
        : opts.ws;
      this.ws = null;
      this.busy = false;
      this.currentAssistant = null;
      this.toolCards = new Map();
      this._buildDom();
      this._connect();
    }

    // ---------------- DOM ----------------
    _buildDom() {
      this.mount.classList.add("ag-root");
      this.mount.innerHTML = `
        <div class="ag-log" role="log" aria-live="polite"></div>
        <div class="ag-composer">
          <textarea class="ag-input" rows="2" placeholder="问 Aegis……（Enter 发送 / Shift+Enter 换行）"></textarea>
          <div class="ag-actions">
            <button class="ag-send" type="button">发送</button>
            <span class="ag-hint"></span>
          </div>
        </div>
        <div class="ag-modal" hidden>
          <div class="ag-modal-card">
            <h3 class="ag-modal-title"></h3>
            <p class="ag-modal-message"></p>
            <div class="ag-modal-body"></div>
            <div class="ag-modal-actions"></div>
          </div>
        </div>`;
      this.log = this.mount.querySelector(".ag-log");
      this.input = this.mount.querySelector(".ag-input");
      this.sendBtn = this.mount.querySelector(".ag-send");
      this.hint = this.mount.querySelector(".ag-hint");
      this.modal = this.mount.querySelector(".ag-modal");

      this.sendBtn.addEventListener("click", () => this._submit());
      this.input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this._submit();
        }
      });
    }

    _submit() {
      const text = this.input.value.trim();
      if (!text) return;
      this.input.value = "";
      this.prompt(text);
    }

    _append(html, cls) {
      const el = document.createElement("div");
      el.className = `ag-msg ${cls || ""}`;
      el.innerHTML = html;
      this.log.appendChild(el);
      this.log.scrollTop = this.log.scrollHeight;
      return el;
    }

    // ---------------- 连接 ----------------
    _connect() {
      this.ws = new WebSocket(this.wsUrl);
      this.ws.onopen = () => { this.hint.textContent = "已连接"; };
      this.ws.onclose = () => {
        this.hint.textContent = "连接已断开（刷新重连）";
        this.busy = false;
      };
      this.ws.onerror = () => { this.hint.textContent = "连接错误"; };
      this.ws.onmessage = (ev) => {
        let msg;
        try { msg = JSON.parse(ev.data); } catch { return; }
        this._onEvent(msg);
      };
    }

    send(obj) {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(obj));
      }
    }

    prompt(text) {
      this._append(esc(text), "ag-user");
      const payload = { type: "prompt", message: text };
      if (this.busy) payload.streamingBehavior = "steer"; // 流式中排队插话
      this.send(payload);
    }

    // ---------------- 事件分发 ----------------
    _onEvent(ev) {
      switch (ev.type) {
        case "message_update": {
          const d = ev.assistantMessageEvent || {};
          if (d.type === "text_delta") {
            if (!this.currentAssistant) this.currentAssistant = this._append("", "ag-assistant");
            this.currentAssistant.dataset.text = (this.currentAssistant.dataset.text || "") + d.delta;
            this.currentAssistant.innerHTML = esc(this.currentAssistant.dataset.text).replace(/\n/g, "<br>");
            this.log.scrollTop = this.log.scrollHeight;
          } else if (d.type === "text_end" && this.currentAssistant && d.content) {
            this.currentAssistant.dataset.text = d.content;
            this.currentAssistant.innerHTML = esc(d.content).replace(/\n/g, "<br>");
          }
          break;
        }
        case "tool_execution_start": {
          const card = this._append(
            `<div class="ag-tool-head">🔧 ${esc(ev.toolName)} 执行中…</div>`,
            "ag-tool"
          );
          this.toolCards.set(ev.toolCallId, card);
          break;
        }
        case "tool_execution_end": {
          const card = this.toolCards.get(ev.toolCallId);
          const res = ev.result || {};
          const details = res.details || {};
          const textBlock = (res.content || []).find((c) => c.type === "text");
          let html = `<div class="ag-tool-head">${ev.isError ? "⚠️" : "✅"} ${esc(ev.toolName)}</div>`;
          if (textBlock) html += `<div class="ag-tool-text">${esc(textBlock.text)}</div>`;
          if (details.table) html += renderTable(details.table); // ← 结构化表格
          const target = card || this._append("", "ag-tool");
          target.innerHTML = html;
          this.toolCards.delete(ev.toolCallId);
          break;
        }
        case "extension_ui_request":
          this._onUiRequest(ev);
          break;
        case "agent_start":
          this.busy = true;
          this.hint.textContent = "思考中…";
          break;
        case "agent_settled":
          this.busy = false;
          this.currentAssistant = null;
          this.hint.textContent = "";
          break;
        case "turn_end":
          this.currentAssistant = null;
          break;
        case "extension_error":
          this._append(`扩展错误（${esc(ev.event)}）：${esc(ev.error)}`, "ag-error");
          break;
        case "bridge_error":
        case "bridge_stderr":
          this._append(esc(ev.error || ev.text), "ag-error");
          break;
        default:
          break; // 其他事件按需扩展
      }
    }

    // ---------------- 扩展 UI（审批弹窗 / 通知） ----------------
    _onUiRequest(req) {
      const method = req.method;
      if (method === "notify") {
        this._append(`ℹ️ ${esc(req.message || req.text || "")}`, "ag-note");
        return;
      }
      if (method === "confirm") {
        this._modal({
          title: req.title || "确认",
          message: req.message || "",
          actions: [
            { label: "拒绝", value: false, primary: false },
            { label: "同意", value: true, primary: true },
          ],
          onPick: (val) => this.send({ type: "extension_ui_response", id: req.id, confirmed: !!val }),
        });
        return;
      }
      if (method === "select") {
        this._modal({
          title: req.title || "请选择",
          message: req.message || "",
          actions: (req.options || []).map((o) => ({ label: o, value: o, primary: false })),
          onPick: (val) => this.send({ type: "extension_ui_response", id: req.id, value: val }),
        });
        return;
      }
      if (method === "input") {
        this._modal({
          title: req.title || "请输入",
          message: req.message || "",
          input: { placeholder: req.placeholder || "" },
          actions: [{ label: "提交", value: "__INPUT__", primary: true }],
          onPick: (val, inputEl) =>
            this.send({ type: "extension_ui_response", id: req.id, value: inputEl ? inputEl.value : val }),
        });
        return;
      }
      // setStatus / setWidget / setTitle 等忽略
    }

    _modal({ title, message, actions, input, onPick }) {
      const card = this.modal.querySelector(".ag-modal-card");
      this.modal.querySelector(".ag-modal-title").textContent = title;
      this.modal.querySelector(".ag-modal-message").textContent = message || "";
      const body = this.modal.querySelector(".ag-modal-body");
      body.innerHTML = "";
      let inputEl = null;
      if (input) {
        inputEl = document.createElement("input");
        inputEl.className = "ag-modal-input";
        inputEl.placeholder = input.placeholder || "";
        body.appendChild(inputEl);
      }
      const actionsEl = this.modal.querySelector(".ag-modal-actions");
      actionsEl.innerHTML = "";
      (actions || []).forEach((a) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "ag-btn" + (a.primary ? " ag-btn-primary" : "");
        btn.textContent = a.label;
        btn.addEventListener("click", () => {
          this.modal.hidden = true;
          onPick(a.value, inputEl);
        });
        actionsEl.appendChild(btn);
      });
      this.modal.hidden = false;
      if (inputEl) inputEl.focus();
    }
  }

  window.AegisGuide = AegisGuide;
})();
