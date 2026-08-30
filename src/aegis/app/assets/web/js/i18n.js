/**
 * Aegis i18n — runtime English ⇄ Chinese translation layer.
 *
 * Design:
 *   - English is the source of truth in code. When lang === 'en' the DOM is
 *     never touched, so the original frontend renders byte-for-byte identical.
 *   - Switching to Chinese walks the DOM and translates rendered text nodes /
 *     attributes against a dictionary (window.SV_DICT) plus a pattern list
 *     (window.SV_PATTERNS) for dynamic strings like "3 threats detected".
 *   - A MutationObserver keeps newly-rendered SPA content translated without
 *     re-rendering. Translated text no longer matches dict keys, so there is
 *     no feedback loop.
 *   - Code blocks, terminals and log surfaces are skipped (data must stay
 *     machine-readable). Brand / product names stay as-is.
 *   - Choice persists in localStorage ('sv-lang').
 *
 * Zero dependencies, native browser APIs only.
 */
(function () {
    'use strict';

    var DICT = (typeof window !== 'undefined' && window.SV_DICT) || {};
    var PATTERNS = (typeof window !== 'undefined' && window.SV_PATTERNS) || [];

    var STORAGE_KEY = 'sv-lang';

    // Elements whose content must stay machine-readable English.
    var SKIP_RE = /(^|\s)(code-block|code|terminal|term|log|logs|mono|monospace|command-box|console|output|env-var|inline-code|copied|language-|json|bash|clipboard|keyboard|code-)(\s|$)/i;

    function hasSkippableAncestor(node) {
        var el = node && node.nodeType === Node.ELEMENT_NODE ? node : (node && node.parentElement);
        while (el) {
            var tag = el.nodeName;
            if (tag === 'CODE' || tag === 'PRE' || tag === 'SCRIPT' || tag === 'STYLE' || tag === 'TEXTAREA' || tag === 'INPUT') return true;
            var cls = (typeof el.className === 'string') ? el.className : '';
            if (cls && SKIP_RE.test(cls)) return true;
            if (el.hasAttribute && el.hasAttribute('data-no-translate')) return true;
            el = el.parentElement;
        }
        return false;
    }

    // Precompiled longest-first alternation over dict keys for in-node
    // word replacement. Built lazily on first Chinese apply.
    // Only multi-word keys participate here: a single-word key's meaning is
    // context-dependent (e.g. "View" = 查看 as a button but 视图 as a mode), so
    // standalone single words rely on the exact whole-node match instead. This
    // stops composites like "View all" from degrading into "视图 all".
    var _exactRe = null;
    function ensureRegex() {
        if (_exactRe) return _exactRe;
        var keys = Object.keys(DICT).filter(function (k) { return k.indexOf(' ') !== -1; })
            .sort(function (a, b) { return b.length - a.length; });
        if (keys.length === 0) {
            _exactRe = /$/; // never match
            return _exactRe;
        }
        var esc = keys.map(function (k) { return k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).join('|');
        // Allow a key to be preceded/followed by whitespace or punctuation so
        // in-node phrases like "Copy!" or "All:" still match their dict key.
        _exactRe = new RegExp('(^|[\\s(\\[{\\"\']|\\u201c|\\u2018)(' + esc + ')(?=[\\s),;:.!?)\\]}%\\u201d\\u2019\\u3002\\uff0c\\uff1b\\uff1a\\uff01\\uff1f\\u3001]|$)', 'g');
        return _exactRe;
    }

    var _patternRe = [];
    function ensurePatterns() {
        if (_patternRe.length === PATTERNS.length) return;
        _patternRe = PATTERNS.map(function (p) { return { re: new RegExp(p.re, 'g'), zh: p.zh }; });
    }

    // Only CJK marks a string as already translated (or native Chinese). Other
    // non-ASCII — · — → … “ ” — is part of the English source and must not
    // block translation, e.g. "Threats blocked · 24h".
    // Ranges: radicals+punctuation (2E80-2EFF,3000-303F), ext-A (3400-4DBF),
    // unified ideographs (4E00-9FFF), compat ideographs (F900-FAFF), fullwidth (FF00-FFEF).
    var CJK_RE = /[⺀-⻿　-〿㐀-䶿一-鿿豈-﫿＀-￯]/;
    function hasNonAscii(s) {
        return CJK_RE.test(s);
    }

    /**
     * Translate a single text node's value. Returns the new string or null.
     * Strategy per node:
     *   1. whole-trimmed exact match against DICT (fast path)
     *   2. dynamic pattern replacement
     *   3. in-node word replacement (longest-first)
     */
    function translateText(text) {
        if (typeof text !== 'string' || text.length === 0) return null;
        if (hasNonAscii(text)) return null;          // already translated (or native CJK)
        var trimmed = text.trim();
        if (trimmed.length === 0) return null;

        // 1) exact whole-node match
        if (DICT.hasOwnProperty(trimmed)) return DICT[trimmed];

        // 2) dynamic patterns
        ensurePatterns();
        for (var i = 0; i < _patternRe.length; i++) {
            var p = _patternRe[i];
            p.re.lastIndex = 0;
            if (p.re.test(text)) {
                p.re.lastIndex = 0;
                var out = text.replace(p.re, p.zh);
                if (out !== text) return out;
            }
        }

        // 3) in-node word replacement (longest-first)
        var re = ensureRegex();
        re.lastIndex = 0;
        if (re.test(text)) {
            re.lastIndex = 0;
            var out2 = text.replace(re, function (m, lead, word) { return lead + DICT[word]; });
            return out2 !== text ? out2 : null;
        }
        return null;
    }

    function translateAttribute(value) {
        if (typeof value !== 'string' || value.length === 0) return null;
        if (hasNonAscii(value)) return null;
        var trimmed = value.trim();
        if (DICT.hasOwnProperty(trimmed)) return DICT[trimmed];

        var re = ensureRegex();
        re.lastIndex = 0;
        if (re.test(value)) {
            re.lastIndex = 0;
            var out = value.replace(re, function (m, lead, word) { return lead + DICT[word]; });
            return out !== value ? out : null;
        }
        return null;
    }

    var ATTRS = ['title', 'placeholder', 'aria-label'];

    function translateNode(node) {
        if (!node) return;
        if (node.nodeType === Node.TEXT_NODE) {
            if (hasSkippableAncestor(node)) return;
            var out = translateText(node.nodeValue);
            if (out !== null && out !== node.nodeValue) node.nodeValue = out;
            return;
        }
        if (node.nodeType === Node.ELEMENT_NODE) {
            if (hasSkippableAncestor(node)) return;
            for (var a = 0; a < ATTRS.length; a++) {
                if (node.hasAttribute && node.hasAttribute(ATTRS[a])) {
                    var attrOut = translateAttribute(node.getAttribute(ATTRS[a]));
                    if (attrOut !== null) node.setAttribute(ATTRS[a], attrOut);
                }
            }
        }
    }

    // ---------------- public API ----------------
    var I18N = {
        lang: 'en',
        observer: null,

        init: function () {
            try {
                var saved = localStorage.getItem(STORAGE_KEY);
                if (saved === 'zh' || saved === 'en') this.lang = saved;
            } catch (_) { /* private mode */ }
            this._startObserver();
            if (this.lang === 'zh') this.apply();
            this._updateToggleButton();
        },

        setLang: function (lang) {
            var next = (lang === 'zh') ? 'zh' : 'en';
            this.lang = next;
            try { localStorage.setItem(STORAGE_KEY, next); } catch (_) { /* ignore */ }
            if (next === 'zh') {
                this.apply();
            } else {
                // Re-render chrome + page from source to restore original English.
                if (window.App && App.currentPage) App.loadPage(App.currentPage);
                if (window.Header) { try { Header.render(); } catch (_) { /* ignore */ } }
                if (window.Sidebar) { try { Sidebar.render(); } catch (_) { /* ignore */ } }
            }
            this._updateToggleButton();
        },

        toggle: function () {
            this.setLang(this.lang === 'zh' ? 'en' : 'zh');
        },

        apply: function () {
            if (this.lang !== 'zh') return;
            var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
            var nodes = [];
            while (walker.nextNode()) nodes.push(walker.currentNode);
            for (var i = 0; i < nodes.length; i++) translateNode(nodes[i]);
            var els = document.querySelectorAll('*');
            for (var j = 0; j < els.length; j++) translateNode(els[j]);
        },

        _updateToggleButton: function () {
            var btn = document.getElementById('lang-toggle-btn');
            if (!btn) return;
            var zh = this.lang === 'zh';
            btn.textContent = zh ? 'EN' : '中文';
            btn.title = zh ? 'Switch to English' : 'Switch to Chinese';
            btn.setAttribute('aria-label', btn.title);
        },

        _startObserver: function () {
            if (this.observer || typeof MutationObserver === 'undefined') return;
            var self = this;
            this.observer = new MutationObserver(function (mutations) {
                if (self.lang !== 'zh') return;
                for (var m = 0; m < mutations.length; m++) {
                    var mut = mutations[m];
                    if (mut.type === 'characterData') {
                        translateNode(mut.target);
                    } else if (mut.type === 'childList') {
                        mut.addedNodes.forEach(function (n) {
                            if (n.nodeType === Node.TEXT_NODE) { translateNode(n); return; }
                            if (n.nodeType !== Node.ELEMENT_NODE) return;
                            var walker = document.createTreeWalker(n, NodeFilter.SHOW_TEXT, null);
                            var ts = [];
                            while (walker.nextNode()) ts.push(walker.currentNode);
                            for (var k = 0; k < ts.length; k++) translateNode(ts[k]);
                            var attrs = n.querySelectorAll ? n.querySelectorAll('[title],[placeholder],[aria-label]') : [];
                            translateNode(n);
                            for (var q = 0; q < attrs.length; q++) translateNode(attrs[q]);
                        });
                    } else if (mut.type === 'attributes') {
                        var el = mut.target;
                        if (el && el.nodeType === Node.ELEMENT_NODE && ATTRS.indexOf(mut.attributeName) !== -1) {
                            translateNode(el);
                        }
                    }
                }
            });
            this.observer.observe(document.body, {
                childList: true,
                subtree: true,
                characterData: true,
                attributes: true,
                attributeFilter: ATTRS
            });
        }
    };

    window.I18N = I18N;

    // Init after DOM ready, before App.init() runs its async render.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { I18N.init(); });
    } else {
        I18N.init();
    }
})();
