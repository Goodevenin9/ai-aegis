/**
 * TopNav — horizontal primary navigation + per-section secondary strip.
 *
 * The top-of-window command row. Renders the SAME data Sidebar uses
 * (Sidebar.navItems) and drives the SAME navigation entry points
 * (Sidebar.navigate / Sidebar.navigateToSection), so the rail, the command
 * palette, deep links and this bar can never disagree about where you are.
 *
 * Layout roles:
 *   #topnav   brand + primary tabs (one per top-level destination)
 *   #subnav   secondary tabs (the active section's sub-items, e.g.
 *             Threat Monitor → Threats | Blocked Actions | Secret Detections)
 *
 * Active state is driven by Sidebar.setActive() broadcasting the
 * `aegis:navigate` event — the same hook App.loadPage already calls on every
 * page change (deep links, back/forward, wizard auto-launch included).
 */
const TopNav = {
    _root: null,
    _tabsRoot: null,
    _tabs: [],          // { el, item } for each primary tab
    _subRoot: null,

    // Compact display labels so 13 top-level destinations stay scannable in
    // one horizontal row. Anything not listed falls back to the nav label.
    _LABELS: {
        dashboard: 'Dashboard',
        'threat-monitor': 'Threat Monitor',
        'instant-audit': 'Audit',
        'agent-activity': 'Observability',
        'policies-controls': 'Policies',
        governance: 'Governance',
        'mcp-policies': 'MCP',
        'guide-connect-agents': 'Connect',
        integrations: 'Integrations',
        'siem-export': 'SIEM',
        'cloud-activity': 'Cloud',
        guide: 'Guide',
        settings: 'Settings',
    },

    // Destinations that need a Aegis cloud account — dimmed/locked on
    // personal-mode installs, mirroring the rail's treatment.
    _CLOUD_TIER: new Set(['mcp-policies', 'cloud-activity']),

    // First-visit orange badge dot, same semantics as the rail.
    _CORE_BADGE: new Set(['threat-monitor']),

    init() {
        this._root = document.getElementById('topnav');
        if (!this._root) return;

        this._renderChrome();
        this._tabsRoot = this._root.querySelector('.ag-tabs');

        this._renderPrimaryTabs();

        // Secondary strip lives in #subnav, right above the page content.
        this._subRoot = document.getElementById('subnav');

        document.addEventListener('aegis:navigate', (e) => {
            this.update(e.detail && e.detail.page);
        });

        // Reflect the current page (setActive fired before init ran).
        this.update(Sidebar.currentPage);
    },

    _renderChrome() {
        const root = this._root;
        root.textContent = '';

        // Mobile hamburger — shows the rail as an overlay on small screens.
        const burger = document.createElement('button');
        burger.className = 'ag-burger';
        burger.type = 'button';
        burger.setAttribute('aria-label', 'Toggle navigation menu');
        for (let i = 0; i < 3; i++) {
            const line = document.createElement('span');
            line.className = 'ag-burger-line';
            burger.appendChild(line);
        }
        burger.addEventListener('click', () => {
            if (window.Header && Header.toggleMobileMenu) Header.toggleMobileMenu();
        });
        root.appendChild(burger);

        // Brand block — logo + wordmark, navigates home.
        const brand = document.createElement('a');
        brand.className = 'ag-brand';
        brand.href = '#';
        brand.title = 'Go to Dashboard';
        const logo = document.createElement('img');
        logo.src = '/images/favicon.png';
        logo.alt = 'Aegis';
        logo.className = 'ag-brand-logo';
        const word = document.createElement('span');
        word.className = 'ag-brand-word';
        word.textContent = 'Aegis';
        brand.appendChild(logo);
        brand.appendChild(word);
        brand.addEventListener('click', (e) => {
            e.preventDefault();
            Sidebar.navigate('dashboard');
        });
        root.appendChild(brand);

        // Primary tabs row (scrolls horizontally when it overflows).
        const tabs = document.createElement('div');
        tabs.className = 'ag-tabs';
        root.appendChild(tabs);

        // Right spacer + subtle "identity" chip keeps the row balanced.
        const spacer = document.createElement('div');
        spacer.className = 'ag-topnav-spacer';
        root.appendChild(spacer);
    },

    _renderPrimaryTabs() {
        const frag = document.createDocumentFragment();
        Sidebar.navItems.forEach((item) => {
            const el = document.createElement('button');
            el.type = 'button';
            el.className = 'ag-tab';
            el.title = item.tooltip || this._label(item);
            el.textContent = this._label(item);
            el.dataset.page = item.id;

            if (this._CLOUD_TIER.has(item.id)) {
                el.classList.add('ag-cloud');
                if (Sidebar._enrolled !== true) el.classList.add('ag-locked');
                const tag = document.createElement('span');
                tag.className = 'ag-cloud-tag';
                tag.textContent = 'Cloud';
                el.appendChild(tag);
            }

            // First-visit orange dot for a core feature.
            if (this._CORE_BADGE.has(item.id) && !localStorage.getItem('ag-visited-core-' + item.id)) {
                const dot = document.createElement('span');
                dot.className = 'ag-core-dot';
                dot.dataset.agCoreDot = item.id;
                el.appendChild(dot);
            }

            el.addEventListener('click', () => this._go(item));
            el._item = item;
            this._tabs.push({ el, item });
            frag.appendChild(el);
        });
        this._tabsRoot.appendChild(frag);
    },

    _label(item) {
        return this._LABELS[item.id] || item.label || item.id;
    },

    _firstSubId(item) {
        const sub = item.subItems || [];
        const first = sub.find((s) => s.id) || sub[0];
        return first ? first.id : null;
    },

    _go(item) {
        if (item.subItems && item.subItems.length) {
            const firstId = this._firstSubId(item);
            if (firstId) Sidebar.navigate(firstId);
            else Sidebar.navigate(item.id);
        } else {
            Sidebar.navigate(item.id);
        }
    },

    _isTabActive(item, page) {
        if (item.subItems && item.subItems.length) {
            if (page === item.id) return true;
            return item.subItems.some((s) =>
                s.id === page || (s.aliases && s.aliases.includes(page)));
        }
        return page === item.id || (item.aliases && item.aliases.includes(page));
    },

    _sectionOf(page) {
        for (const item of Sidebar.navItems) {
            if (this._isTabActive(item, page)) return item;
        }
        return null;
    },

    update(page) {
        if (!this._tabsRoot) return;
        this._tabs.forEach(({ el, item }) => {
            el.classList.toggle('active', this._isTabActive(item, page));
            const dot = el.querySelector('.ag-core-dot');
            if (dot && el.classList.contains('active')) {
                dot.style.transition = 'opacity 0.3s';
                dot.style.opacity = '0';
                setTimeout(() => dot.remove(), 300);
            }
        });
        this._renderSubnav(this._sectionOf(page), page);
    },

    _renderSubnav(section, page) {
        if (!this._subRoot) return;
        const sub = this._subRoot;
        sub.textContent = '';

        if (!section || !section.subItems || !section.subItems.length) {
            sub.classList.remove('active');
            return;
        }
        sub.classList.add('active');

        section.subItems.forEach((s) => {
            if (s.header) {
                const label = document.createElement('span');
                label.className = 'ag-subnav-label';
                label.textContent = s.header;
                sub.appendChild(label);
            } else if (s.id) {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'ag-subnav-tab';
                btn.textContent = s.label;
                btn.title = s.tooltip || s.label;
                btn.dataset.page = s.id;
                const active = s.id === page || (s.aliases && s.aliases.includes(page));
                btn.classList.toggle('active', active);
                btn.addEventListener('click', () => {
                    if (s.section) Sidebar.navigateToSection(section.id, s.section, s.id);
                    else Sidebar.navigate(s.id);
                });
                sub.appendChild(btn);
            }
        });
    },
};
