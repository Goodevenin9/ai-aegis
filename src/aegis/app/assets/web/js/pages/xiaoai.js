/**
 * 小瑷（Aeg）—— Aegis 安全助手页面。
 *
 * 复用 `integrations/pi/frontend` 的完整聊天应用，通过同源 iframe 内嵌：
 * 会话记录、流式输出、工具卡片、内联审批与原应用完全一致。
 * 后端 WebSocket 桥挂在 `/api/aegis-guide/*`（见 app.py 的挂载）。
 *
 * 聊天页会通过 postMessage 汇报「当前会话标题」，本页把它同步到 Aegis 顶栏。
 */
const XiaoaiPage = {
    _subtitle: 'Aegis 安全助手（Aeg）· 由 pi 驱动，工具调用受五阶段管线治理',

    _style() {
        if (document.getElementById('xiaoai-style')) return;
        const style = document.createElement('style');
        style.id = 'xiaoai-style';
        style.textContent = `
            .xiaoai-host { position: relative; }
            .xiaoai-frame {
                position: absolute; inset: 0;
                width: 100%; height: 100%;
                border: 0; display: block;
                background: var(--bg-primary);
            }
        `;
        document.head.appendChild(style);
    },

    _listen() {
        if (this._listening) return;
        this._listening = true;
        window.addEventListener('message', (event) => {
            // 只接受同源 iframe 的标题汇报
            if (event.origin !== window.location.origin) return;
            const data = event.data || {};
            if (data.type !== 'xiaoai:title') return;
            const title = data.title && data.title !== '新对话'
                ? `小瑷 · ${data.title}`
                : '小瑷';
            if (window.Header) Header.setPageInfo(title, this._subtitle);
        });
    },

    async render(container) {
        this._style();
        this._listen();
        if (window.Header) Header.setPageInfo('小瑷', this._subtitle);
        container.classList.add('xiaoai-host');
        container.style.position = 'relative';

        // 小瑷 依赖可选的 pi 集成：桥只从源码仓库挂载，且需要本机安装 `pi` CLI。
        // 安装版（pip）或未装 pi 时不要把 iframe 指向一个死页面，改为诚实的空状态。
        let available = false;
        try {
            const response = await fetch('/api/aegis-guide/status');
            const data = response.ok ? await response.json() : null;
            available = !!(data && data.pi_available && data.extension_exists);
        } catch (error) { /* 失败即隐藏，不放行 */ }

        if (!available) {
            container.innerHTML =
                '<div style="padding:40px;max-width:640px;color:var(--text-secondary);line-height:1.7">' +
                '<h3 style="color:var(--text-primary);margin:0 0 8px">小瑷 需要可选的 pi 集成</h3>' +
                '<p>该助手由 <code>pi</code> CLI 驱动，仅在从源码仓库运行、且本机已安装 <code>pi</code> 时可用。安装版（pip）不包含该集成，因此这里不会挂载。</p>' +
                '<p>启用方式：从源码仓库启动应用，安装 <code>pi</code> CLI 后重新打开本页。</p>' +
                '</div>';
            return;
        }

        container.innerHTML =
            '<iframe class="xiaoai-frame" title="小瑷 安全助手" ' +
            'src="/api/aegis-guide/chat?embed=1"></iframe>';
    },
};
