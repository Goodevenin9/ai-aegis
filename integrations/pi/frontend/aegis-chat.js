/* 小瑷（Aeg）—— Aegis 安全助手 · 浏览器端聊天应用（纯 JS，无依赖）
 *
 * 会话记录由服务端提供：
 *   GET    /api/aegis-guide/conversations          列出 pi 会话
 *   DELETE /api/aegis-guide/conversations/{name}    删除会话文件
 * 当前会话通过 pi RPC 管理：
 *   get_state / get_messages / new_session / switch_session / prompt / abort
 * 内嵌在 Aegis SPA 时，用 postMessage 把当前会话标题同步给父页顶栏。
 */
(function () {
  "use strict";

  var THEME_KEY = "aegis-chat.theme";

  // ------------------------------------------------------------------ utils
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function $(id) { return document.getElementById(id); }
  function textOf(content) {
    if (typeof content === "string") return content;
    if (Array.isArray(content)) {
      return content.filter(function (p) { return p && p.type === "text"; })
        .map(function (p) { return p.text || ""; }).join("");
    }
    return "";
  }

  function inline(s) {
    var t = esc(s);
    t = t.replace(/`([^`]+)`/g, function (_, c) { return "<code>" + c + "</code>"; });
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    t = t.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, function (_, a, b) {
      return '<a href="' + b + '" target="_blank" rel="noopener">' + a + "</a>";
    });
    return t;
  }
  function splitRow(line) {
    return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(function (s) { return s.trim(); });
  }
  function isTableSep(line) { return /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(line) && /-/.test(line); }

  function md(src) {
    var lines = String(src == null ? "" : src).replace(/\r\n?/g, "\n").split("\n");
    var out = [], i = 0;
    while (i < lines.length) {
      var line = lines[i];
      var fence = line.match(/^\s*```(\w*)\s*$/);
      if (fence) {
        i++; var buf = [];
        while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) { buf.push(lines[i]); i++; }
        i++;
        out.push("<pre><code>" + esc(buf.join("\n")) + "</code></pre>");
        continue;
      }
      if (line.indexOf("|") >= 0 && i + 1 < lines.length && isTableSep(lines[i + 1])) {
        var header = splitRow(line); i += 2; var rows = [];
        while (i < lines.length && lines[i].indexOf("|") >= 0 && lines[i].trim() !== "") { rows.push(splitRow(lines[i])); i++; }
        out.push(
          "<table><thead><tr>" + header.map(function (h) { return "<th>" + inline(h) + "</th>"; }).join("") +
          "</tr></thead><tbody>" + rows.map(function (r) {
            return "<tr>" + r.map(function (c) { return "<td>" + inline(c) + "</td>"; }).join("") + "</tr>";
          }).join("") + "</tbody></table>"
        );
        continue;
      }
      var h = line.match(/^(#{1,6})\s+(.*)$/);
      if (h) { var n = h[1].length; out.push("<h" + n + ">" + inline(h[2]) + "</h" + n + ">"); i++; continue; }
      if (/^\s*([-*_])\1{2,}\s*$/.test(line)) { out.push("<hr>"); i++; continue; }
      if (/^\s*>\s?/.test(line)) {
        var qb = [];
        while (i < lines.length && /^\s*>\s?/.test(lines[i])) { qb.push(lines[i].replace(/^\s*>\s?/, "")); i++; }
        out.push("<blockquote>" + md(qb.join("\n")) + "</blockquote>");
        continue;
      }
      if (/^\s*[-*+]\s+/.test(line)) {
        var ub = [];
        while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) { ub.push(lines[i].replace(/^\s*[-*+]\s+/, "")); i++; }
        out.push("<ul>" + ub.map(function (x) { return "<li>" + inline(x) + "</li>"; }).join("") + "</ul>");
        continue;
      }
      if (/^\s*\d+[.)]\s+/.test(line)) {
        var ob = [];
        while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) { ob.push(lines[i].replace(/^\s*\d+[.)]\s+/, "")); i++; }
        out.push("<ol>" + ob.map(function (x) { return "<li>" + inline(x) + "</li>"; }).join("") + "</ol>");
        continue;
      }
      if (line.trim() === "") { i++; continue; }
      var pb = [line]; i++;
      while (i < lines.length && lines[i].trim() !== "" &&
        !/^\s*(```|#{1,6}\s|>\s?|[-*+]\s|\d+[.)]\s)/.test(lines[i]) && !isTableSep(lines[i])) {
        pb.push(lines[i]); i++;
      }
      out.push("<p>" + pb.map(inline).join("<br>") + "</p>");
    }
    return out.join("");
  }

  function dataTable(columns, rows) {
    columns = columns || []; rows = rows || [];
    return "<table><thead><tr>" + columns.map(function (c) { return "<th>" + esc(c) + "</th>"; }).join("") +
      "</tr></thead><tbody>" + rows.map(function (r) {
        return "<tr>" + (r || []).map(function (v) { return "<td>" + esc(v) + "</td>"; }).join("") + "</tr>";
      }).join("") + "</tbody></table>";
  }

  // ------------------------------------------------------------------ app
  function AegisChat() {
    this.convs = [];             // 服务端会话列表
    this.activeName = null;      // 当前会话文件名
    this.activeTitle = "新对话";
    this.messages = [];          // 当前会话展示块
    this.ws = null;
    this.streaming = false;
    this.currentSessionFile = null;
    this.stream = null;
    this._toolMap = {};
    this._toolEls = {};
    this._flushTimer = null;
    this._refreshTimer = null;
    this._bind();
    this._renderSidebar();
    this._renderWelcome(true);
    this._connect();
  }

  AegisChat.prototype = {
    // ---------- sidebar ----------
    _renderSidebar: function () {
      var self = this, list = $("conv-list");
      list.innerHTML = "";
      if (!this.convs.length) {
        var e = document.createElement("div");
        e.className = "conv-group"; e.textContent = "还没有会话";
        list.appendChild(e); return;
      }
      this.convs.forEach(function (c) {
        var item = document.createElement("div");
        item.className = "conv-item" + (c.name === self.activeName ? " active" : "");
        item.title = c.title;
        var title = document.createElement("span");
        title.className = "ci-title"; title.textContent = c.title || "新对话";
        var del = document.createElement("button");
        del.className = "ci-del"; del.textContent = "×"; del.title = "删除";
        del.addEventListener("click", function (ev) { ev.stopPropagation(); self.deleteConv(c.name); });
        item.appendChild(title); item.appendChild(del);
        item.addEventListener("click", function () { self.openConv(c.name); });
        list.appendChild(item);
      });
    },
    _loadConversations: function () {
      var self = this;
      fetch("/api/aegis-guide/conversations").then(function (r) { return r.json(); }).then(function (data) {
        self.convs = (data && data.conversations) || [];
        // 用 sessionFile 匹配当前会话
        var match = self.convs.filter(function (c) { return c.sessionPath === self.currentSessionFile; })[0];
        if (match) { self.activeName = match.name; self.activeTitle = match.title; }
        self._renderSidebar();
        self._notifyTitle();
      }).catch(function () { /* 静默 */ });
    },
    _notifyTitle: function () {
      try {
        if (window.parent && window.parent !== window) {
          window.parent.postMessage({ type: "xiaoai:title", title: this.activeTitle || "新对话" }, "*");
        }
      } catch (e) {}
    },

    // ---------- dom ----------
    _bind: function () {
      var self = this;
      try {
        if (new URLSearchParams(location.search).get("embed") === "1") document.body.classList.add("embed");
      } catch (e) {}
      try { document.documentElement.setAttribute("data-theme", localStorage.getItem(THEME_KEY) || "dark"); } catch (e) {}

      $("btn-new").addEventListener("click", function () { self.newChat(); });
      $("btn-send").addEventListener("click", function () { self.submit(); });
      $("btn-stop").addEventListener("click", function () { self._send({ type: "abort" }); });
      $("btn-theme").addEventListener("click", function () { self.toggleTheme(); });
      $("btn-menu").addEventListener("click", function () { $("app").classList.toggle("side-open"); });
      $("chips").addEventListener("click", function (e) {
        var b = e.target.closest(".chip"); if (!b) return;
        $("input").value = b.textContent; self.submit();
      });
      var input = $("input");
      input.addEventListener("input", function () { self._autoGrow(); });
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); self.submit(); }
      });
    },
    _autoGrow: function () {
      var el = $("input");
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 200) + "px";
    },
    toggleTheme: function () {
      var cur = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
      var next = cur === "light" ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    },
    toast: function (msg, kind) {
      var t = document.createElement("div");
      t.className = "toast" + (kind ? " " + kind : "");
      t.textContent = msg;
      $("toasts").appendChild(t);
      setTimeout(function () { t.remove(); }, 4200);
    },
    _renderWelcome: function (show) { $("welcome").style.display = show ? "" : "none"; },
    _clearThread: function () { $("thread").innerHTML = ""; },
    _scrollDown: function () { var s = $("scroller"); s.scrollTop = s.scrollHeight; },

    // ---------- thread rendering ----------
    _renderThread: function () {
      var self = this;
      this._clearThread();
      this.messages.forEach(function (b) { self._renderBlock(b); });
      this._renderWelcome(this.messages.length === 0);
      this._scrollDown();
    },
    _renderBlock: function (b) {
      if (b.role === "user") this._domUser(b.text);
      else if (b.role === "assistant") this._domAssistant(b.text, false);
      else if (b.role === "tool") this._domTool(b, false);
      else if (b.role === "notice") this._domNotice(b.text);
    },
    _addBlock: function (b) {
      this.messages.push(b);
      if (b.role === "user" && (this.activeTitle === "新对话" || !this.activeTitle)) {
        this.activeTitle = String(b.text).replace(/\s+/g, " ").slice(0, 26);
        this._notifyTitle();
      }
      return b;
    },
    _domUser: function (text) {
      var row = document.createElement("div");
      row.className = "row user";
      var b = document.createElement("div"); b.className = "bubble"; b.textContent = text;
      row.appendChild(b); $("thread").appendChild(row);
      this._renderWelcome(false);
      return row;
    },
    _domAssistant: function (text, streaming) {
      var row = document.createElement("div");
      row.className = "row assistant";
      var av = document.createElement("div"); av.className = "avatar"; av.textContent = "瑷";
      var b = document.createElement("div"); b.className = "bubble";
      var mdEl = document.createElement("div"); mdEl.className = "md";
      mdEl.innerHTML = md(text) + (streaming ? '<span class="cursor"></span>' : "");
      b.appendChild(mdEl); row.appendChild(av); row.appendChild(b);
      $("thread").appendChild(row);
      this._renderWelcome(false);
      return mdEl;
    },
    _domTool: function (t, pending) {
      var d = document.createElement("details");
      d.className = "tool";
      var state = pending
        ? '<span class="t-spin"></span>'
        : (t.ok === false ? '<span class="t-state err">失败</span>' : '<span class="t-state ok">完成</span>');
      var s = document.createElement("summary");
      s.innerHTML = "🔧 <span class=\"t-name\">" + esc(t.name) + "</span>" + state;
      d.appendChild(s);
      var body = document.createElement("div"); body.className = "t-body";
      if (t.text) { var tx = document.createElement("div"); tx.className = "t-text"; tx.textContent = t.text; body.appendChild(tx); }
      if (t.table && t.table.columns) body.innerHTML += dataTable(t.table.columns, t.table.rows);
      d.appendChild(body);
      $("thread").appendChild(d);
      return d;
    },
    _domNotice: function (text) {
      var el = document.createElement("div");
      el.className = "notice"; el.textContent = text;
      $("thread").appendChild(el);
    },

    // ---------- websocket ----------
    _connect: function () {
      var self = this;
      var base = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/api/aegis-guide/ws";
      this._setConn("connecting");
      try { this.ws = new WebSocket(base); }
      catch (e) { this._setConn("bad", "无法连接"); return; }
      this.ws.onopen = function () {
        self._setConn("ok", "已连接");
        self._send({ type: "get_state" });
      };
      this.ws.onclose = function () {
        self.streaming = false; self._setStreaming(false);
        self._setConn("bad", "连接已断开");
      };
      this.ws.onerror = function () { self._setConn("bad", "连接错误"); };
      this.ws.onmessage = function (ev) {
        var msg; try { msg = JSON.parse(ev.data); } catch (e) { return; }
        self._onEvent(msg);
      };
    },
    _send: function (obj) {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(obj));
    },
    _setConn: function (state, text) {
      var el = $("conn");
      el.className = "conn" + (state === "ok" ? " ok" : state === "bad" ? " bad" : "");
      el.querySelector("span").textContent = text || (state === "ok" ? "已连接" : "连接中…");
    },
    _setStreaming: function (on) {
      this.streaming = on;
      $("btn-send").hidden = on;
      $("btn-stop").hidden = !on;
      $("hint").textContent = on ? "生成中…" : "";
    },
    _onEvent: function (ev) {
      var t = ev.type;
      if (t === "response") return this._onResponse(ev);
      if (t === "message_update") {
        var d = ev.assistantMessageEvent || {};
        if (d.type === "text_delta") return this._onDelta(d.delta || "");
        if (d.type === "text_end") return this._onTextEnd(d.content || "");
        if (d.type === "thinking_start") { $("hint").textContent = "思考中…"; return; }
        if (d.type === "thinking_end") { if (this.streaming) $("hint").textContent = "生成中…"; return; }
        return;
      }
      if (t === "tool_execution_start") return this._toolStart(ev);
      if (t === "tool_execution_end") return this._toolEnd(ev);
      if (t === "extension_ui_request") return this._onUiRequest(ev);
      if (t === "agent_start") { this._setStreaming(true); return; }
      if (t === "agent_end" || t === "agent_settled") {
        this._finishStream(); this._setStreaming(false);
        this._scheduleConversationRefresh();
        return;
      }
      if (t === "bridge_error") {
        this.toast("桥接错误：" + (ev.error || ""), "err");
        this._finishStream(); this._setStreaming(false);
        return;
      }
    },
    _scheduleConversationRefresh: function () {
      var self = this;
      clearTimeout(this._refreshTimer);
      this._refreshTimer = setTimeout(function () { self._loadConversations(); }, 400);
    },
    _onResponse: function (ev) {
      var data = ev.data || {};
      if (!ev.success) {
        if (ev.command === "switch_session" || ev.command === "new_session") {
          this.toast("会话操作失败：" + (ev.error || ""), "warn");
        }
        return;
      }
      if (ev.command === "get_state") {
        this.currentSessionFile = data.sessionFile || null;
        if (data.model) $("topbar-meta").textContent = data.model.id || data.model.name || "";
        this._loadConversations();
      } else if (ev.command === "get_messages") {
        this.messages = this._rebuild(data.messages || []);
        this._renderThread();
      } else if (ev.command === "new_session") {
        this.activeName = null; this.activeTitle = "新对话";
        this.messages = []; this._renderThread(); this._notifyTitle();
        this._send({ type: "get_state" });
      } else if (ev.command === "switch_session") {
        this._send({ type: "get_messages" });
      }
    },
    _rebuild: function (msgs) {
      var blocks = [], byId = {};
      (msgs || []).forEach(function (m) {
        if (!m || !m.role) return;
        if (m.role === "user") {
          blocks.push({ role: "user", text: textOf(m.content) });
        } else if (m.role === "assistant") {
          (m.content || []).forEach(function (p) {
            if (!p || !p.type) return;
            if (p.type === "text" && p.text) blocks.push({ role: "assistant", text: p.text });
            else if (p.type === "toolCall") {
              var b = { role: "tool", name: p.name, ok: null, text: "", table: null, toolCallId: p.id };
              blocks.push(b); byId[p.id] = b;
            }
          });
        } else if (m.role === "toolResult") {
          var b = byId[m.toolCallId];
          if (b) {
            b.ok = !m.isError;
            var t = (m.content || []).filter(function (c) { return c && c.type === "text"; })[0];
            b.text = t ? t.text : "";
            if (m.details && m.details.table) b.table = m.details.table;
          }
        }
      });
      return blocks;
    },

    // ---------- streaming ----------
    _onDelta: function (delta) {
      if (!this.stream) {
        var block = { role: "assistant", text: "" };
        this.messages.push(block);
        var mdEl = this._domAssistant("", true);
        this.stream = { block: block, el: mdEl, text: "" };
      }
      this.stream.text += delta;
      this.stream.block.text = this.stream.text;
      var self = this;
      if (!this._flushTimer) {
        this._flushTimer = setTimeout(function () {
          self._flushTimer = null;
          if (self.stream) {
            self.stream.el.innerHTML = md(self.stream.text) + '<span class="cursor"></span>';
            self._scrollDown();
          }
        }, 60);
      }
    },
    _onTextEnd: function (content) {
      if (this.stream && content) { this.stream.text = content; this.stream.block.text = content; }
      this._finishStream();
    },
    _finishStream: function () {
      if (!this.stream) return;
      clearTimeout(this._flushTimer); this._flushTimer = null;
      this.stream.el.innerHTML = md(this.stream.text);
      this.stream.block.text = this.stream.text;
      this.stream = null;
      this._scrollDown();
    },

    // ---------- tools ----------
    _toolStart: function (ev) {
      if (this.stream) this._finishStream();
      var t = { role: "tool", name: ev.toolName, ok: null, text: "", table: null, toolCallId: ev.toolCallId };
      this.messages.push(t);
      this._toolMap[ev.toolCallId] = t;
      this._toolEls[ev.toolCallId] = this._domTool(t, true);
      this._scrollDown();
    },
    _toolEnd: function (ev) {
      var t = this._toolMap[ev.toolCallId];
      if (!t) return;
      var res = ev.result || {};
      var det = res.details || {};
      var block = (res.content || []).filter(function (c) { return c.type === "text"; })[0];
      t.ok = !ev.isError;
      t.text = block ? block.text : "";
      if (det.table && det.table.columns) t.table = { columns: det.table.columns, rows: det.table.rows };
      var el = this._toolEls[ev.toolCallId];
      if (el) { el.replaceWith(this._domTool(t, false)); delete this._toolEls[ev.toolCallId]; }
      this._scrollDown();
    },

    // ---------- extension UI ----------
    _onUiRequest: function (ev) {
      var self = this;
      if (ev.method === "notify") { this.toast(ev.message, ev.notifyType === "warning" ? "warn" : ev.notifyType === "error" ? "err" : ""); return; }
      if (ev.method === "setTitle" && ev.title) { this.activeTitle = ev.title; this._notifyTitle(); return; }
      if (ev.method === "setStatus" && ev.statusText) { $("hint").textContent = ev.statusText; return; }
      if (ev.method === "set_editor_text" && typeof ev.text === "string") { $("input").value = ev.text; this._autoGrow(); return; }
      if (ev.method === "setWidget") return;

      var card = document.createElement("div");
      card.className = "approval";
      var html = '<div class="a-title">' + esc(ev.title || "需要确认") + "</div>";
      if (ev.message) html += '<div class="a-msg">' + esc(ev.message) + "</div>";
      if (ev.method === "select" || ev.method === "input") {
        html += '<input class="a-input" style="width:100%;padding:8px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);margin-bottom:10px" ' +
          (ev.method === "input" ? 'placeholder="' + esc(ev.placeholder || "") + '"' : 'placeholder="' + esc((ev.options || []).join(" / ")) + '"') + ">";
      }
      html += '<div class="a-actions"></div>';
      card.innerHTML = html;
      var actions = card.querySelector(".a-actions");
      function respond(payload) {
        self._send(Object.assign({ type: "extension_ui_response", id: ev.id }, payload));
        card.classList.add("done");
        var tag = document.createElement("div"); tag.className = "a-msg"; tag.textContent = "已响应。";
        actions.replaceWith(tag);
      }
      function mk(label, primary, payload) {
        var b = document.createElement("button");
        b.textContent = label; if (primary) b.className = "primary";
        b.addEventListener("click", function () {
          if (ev.method === "input" || ev.method === "select") {
            var v = card.querySelector(".a-input");
            respond({ value: v ? v.value : (ev.method === "select" ? (ev.options || [])[0] : "") });
          } else respond(payload);
        });
        actions.appendChild(b);
      }
      if (ev.method === "select") { mk("确定", true); mk("取消", false, { cancelled: true }); }
      else if (ev.method === "input") { mk("提交", true); mk("取消", false, { cancelled: true }); }
      else { mk("允许", true, { confirmed: true }); mk("拒绝", false, { confirmed: false }); }
      $("thread").appendChild(card);
      this._scrollDown();
    },

    // ---------- public ----------
    newChat: function () {
      this._finishStream();
      this._send({ type: "new_session" });
    },
    openConv: function (name) {
      if (name === this.activeName) { $("app").classList.remove("side-open"); return; }
      var conv = this.convs.filter(function (c) { return c.name === name; })[0];
      if (!conv) return;
      this._finishStream();
      this.activeName = name;
      this.activeTitle = conv.title || "新对话";
      this._renderSidebar();
      this._notifyTitle();
      this._send({ type: "switch_session", sessionPath: conv.sessionPath });
      $("app").classList.remove("side-open");
    },
    deleteConv: function (name) {
      var self = this;
      fetch("/api/aegis-guide/conversations/" + encodeURIComponent(name), { method: "DELETE" })
        .then(function (r) {
          if (!r.ok) throw new Error("HTTP " + r.status);
          if (name === self.activeName) self.newChat();
          self._loadConversations();
        })
        .catch(function (e) { self.toast("删除失败：" + e.message, "err"); });
    },
    submit: function () {
      var el = $("input");
      var text = el.value.trim();
      if (!text || this.streaming) return;
      el.value = ""; this._autoGrow();
      this._addBlock({ role: "user", text: text });
      this._domUser(text);
      this._setStreaming(true);
      this._send({ type: "prompt", message: text });
      this._scrollDown();
    },
  };

  window.AegisChat = AegisChat;
  document.addEventListener("DOMContentLoaded", function () {
    window.__aegisChat = new AegisChat();
  });
})();
