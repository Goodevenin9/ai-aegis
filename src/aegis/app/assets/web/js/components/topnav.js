/**
 * TopNav — horizontal primary navigation with hover mega-dropdowns.
 *
 * The top-of-window command row. Renders the SAME data Sidebar uses
 * (Sidebar.navItems) and drives the SAME navigation entry points
 * (Sidebar.navigate / Sidebar.navigateToSection), so the rail, the top bar,
 * the command palette and deep links can never disagree about where you are.
 *
 * Layout roles:
 *   #topnav   brand + one tab per top-level destination (FULL labels)
 *   #subnav   secondary strip for the ACTIVE section (contextual quick tabs)
 *
 * Every section tab opens a floating dropdown panel listing ALL of that
 * section's features — hover to explore, click an entry to navigate. Every
 * tab and every entry carries a native title tooltip (name + description).
 *
 * Occlusion rules (checked): the dropdown is appended to <body> and
 * position:fixed, so it can never be clipped by #topnav's horizontal
 * overflow; z-index 400 sits above the page and the topnav (60) and below
 * every modal overlay (1000+); on mobile the tabs are hidden entirely and
 * navigation falls back to the off-canvas rail, so nothing can overlap there.
 */
const TopNav = {
    _root: null,
    _tabsRoot: null,
    _tabs: [],          // { el, item } for each primary tab
    _subRoot: null,
    _dd: null,          // currently open dropdown panel (<body> child)
    _ddOpenFor: null,   // navItems item the dropdown belongs to
    _ddTimer: null,

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
            this._closeDropdown();
            this.update(e.detail && e.detail.page);
        });

        // Close the dropdown on Escape / click outside / viewport changes.
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this._closeDropdown();
        });
        document.addEventListener('click', (e) => {
            if (this._dd && !this._dd.contains(e.target)
                && !(e.target.closest && e.target.closest('.ag-tab'))) {
                this._closeDropdown();
            }
        });
        window.addEventListener('resize', () => this._closeDropdown());
        window.addEventListener('scroll', (e) => {
            // Scrolling INSIDE the dropdown (its own overflow list) must not
            // close it; scrolling the page closes it so stale coordinates
            // never leave a floating panel where it no longer belongs.
            if (this._dd && e.target && this._dd.contains(e.target)) return;
            this._closeDropdown();
        }, true);

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
            // Header is a top-level `const`, not a window property.
            if (typeof Header !== 'undefined' && Header.toggleMobileMenu) Header.toggleMobileMenu();
        });
        root.appendChild(burger);

        // Brand block — logo + wordmark, navigates home.
        const brand = document.createElement('a');
        brand.className = 'ag-brand';
        brand.href = '#';
        brand.title = 'Dashboard';
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
    },

    _renderPrimaryTabs() {
        const frag = document.createDocumentFragment();
        Sidebar.navItems.forEach((item) => {
            const el = document.createElement('button');
            el.type = 'button';
            el.className = 'ag-tab';
            el.title = item.tooltip || item.label || item.id;   // hover shows the name
            el.textContent = item.label || item.id;             // FULL label, not shortened
            el.dataset.page = item.id;

            const hasSub = !!(item.subItems && item.subItems.length);
            if (hasSub) {
                el.classList.add('ag-has-dd');
                const caret = document.createElement('span');
                caret.className = 'ag-tab-caret';
                caret.textContent = '▾';
                el.appendChild(caret);
            }

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
                el.appendChild(dot);
            }

            el.addEventListener('mouseenter', () => {
                if (hasSub) this._openDropdown(item, el);
            });
            el.addEventListener('mouseleave', () => {
                if (hasSub) this._scheduleClose(item);
            });
            el.addEventListener('focus', () => {
                if (hasSub) this._openDropdown(item, el);
            });
            el.addEventListener('blur', () => {
                if (hasSub) this._scheduleClose(item);
            });
            // One-click selection: clicking any tab navigates straight to its
            // destination. A section tab lands on the section's first feature
            // (its collapsible parent is not a route — see App.loadPage); the
            // hover dropdown remains the "explore everything" path. The
            // aegis:navigate event closes any open dropdown after the jump.
            el.addEventListener('click', () => {
                // A touch long-press (below) already opened the dropdown; the
                // release-tap that follows must NOT also navigate.
                if (el._longPressed) { el._longPressed = false; return; }
                this._go(item);
            });

            // Touchscreens have no hover, so a long-press is the touch
            // equivalent of hovering a section tab: it opens the dropdown and
            // suppresses the native context menu. A quick tap still navigates
            // (the one-click rule above).
            if (hasSub) {
                el.addEventListener('touchstart', (e) => {
                    // Reset a stale flag from a previous long-press so the
                    // next quick tap navigates normally.
                    el._longPressed = false;
                    const startX = e.touches[0].clientX;
                    const startY = e.touches[0].clientY;
                    el._lpTimer = setTimeout(() => {
                        el._longPressed = true;
                        this._openDropdown(item, el);
                    }, 450);
                    const onMove = (ev) => {
                        const dx = ev.touches[0].clientX - startX;
                        const dy = ev.touches[0].clientY - startY;
                        if (Math.abs(dx) + Math.abs(dy) > 8) clearTimeout(el._lpTimer);
                    };
                    const onEnd = () => {
                        clearTimeout(el._lpTimer);
                        el.removeEventListener('touchmove', onMove);
                        el.removeEventListener('touchend', onEnd);
                        el.removeEventListener('touchcancel', onEnd);
                    };
                    el.addEventListener('touchmove', onMove);
                    el.addEventListener('touchend', onEnd);
                    el.addEventListener('touchcancel', onEnd);
                });
                el.addEventListener('contextmenu', (e) => {
                    if (el._longPressed) e.preventDefault();
                });
            }
            el._item = item;
            this._tabs.push({ el, item });
            frag.appendChild(el);
        });
        this._tabsRoot.appendChild(frag);
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

    /* ── Dropdown ────────────────────────────────────────────────────────── */

    _openDropdown(item, anchor) {
        this._closeDropdown();
        this._ddOpenFor = item;

        const panel = document.createElement('div');
        panel.className = 'ag-dropdown';
        panel.setAttribute('role', 'menu');

        const frag = document.createDocumentFragment();
        let groupCount = 0;
        (item.subItems || []).forEach((s) => {
            if (s.header) {
                const label = document.createElement('div');
                label.className = 'ag-dd-label';
                label.textContent = s.header;
                frag.appendChild(label);
                groupCount++;
            } else if (s.id) {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'ag-dd-item';
                btn.setAttribute('role', 'menuitem');
                btn.title = s.tooltip || s.label;
                btn.dataset.page = s.id;
                const span = document.createElement('span');
                span.textContent = s.label;
                btn.appendChild(span);

                const active = s.id === this.currentPage
                    || (s.aliases && s.aliases.includes(this.currentPage));
                if (active) btn.classList.add('active');

                if (this._CLOUD_TIER.has(item.id) && Sidebar._enrolled !== true) {
                    btn.classList.add('ag-locked');
                }

                btn.addEventListener('click', () => {
                    if (s.section) Sidebar.navigateToSection(item.id, s.section, s.id);
                    else Sidebar.navigate(s.id);
                    this._closeDropdown();
                });
                frag.appendChild(btn);
            }
        });

        if (!groupCount) panel.classList.add('ag-dd-flat');
        panel.appendChild(frag);

        // Measure off-screen, then pin over the tab — fixed, on <body>, so no
        // ancestor overflow can clip it.
        panel.style.cssText = 'position:fixed; left:0; top:0; visibility:hidden; z-index:400;';
        document.body.appendChild(panel);
        const pad = 8;
        const r = anchor.getBoundingClientRect();
        const pw = panel.offsetWidth;
        const ph = panel.offsetHeight;
        let left = r.left;
        let top = r.bottom + 6;
        if (left + pw > window.innerWidth - pad) left = Math.max(pad, window.innerWidth - pad - pw);
        if (top + ph > window.innerHeight - pad) top = Math.max(pad, r.top - ph - 6);
        panel.style.left = left + 'px';
        panel.style.top = top + 'px';
        panel.style.visibility = 'visible';
        requestAnimationFrame(() => panel.classList.add('ag-dd-open'));

        panel.addEventListener('mouseenter', () => clearTimeout(this._ddTimer));
        panel.addEventListener('mouseleave', () => this._scheduleClose(item));
        this._dd = panel;
    },

    _scheduleClose(item) {
        clearTimeout(this._ddTimer);
        this._ddTimer = setTimeout(() => {
            if (this._ddOpenFor === item) this._closeDropdown();
        }, 200);
    },

    _closeDropdown() {
        clearTimeout(this._ddTimer);
        if (this._dd) {
            this._dd.remove();
            this._dd = null;
        }
        this._ddOpenFor = null;
    },

    /* ── Active state + secondary strip ──────────────────────────────────── */

    update(page) {
        if (!this._tabsRoot) return;
        this.currentPage = page;
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

// Expose on window — codebase convention (sidebar.js, header.js, etc. all do
// this). A top-level `const` lives in the global lexical scope and is NOT a
// window property, so without this line `window.TopNav` guards stay false and
// the whole command row never renders.
window.TopNav = TopNav;
