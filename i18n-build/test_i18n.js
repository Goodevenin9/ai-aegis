// Functional test of the translateText logic against REAL strings taken from
// the v1.0 frontend source (pages/*.js, components/*.js).
global.window = {};
require('../src/aegis/app/assets/web/js/i18n-dict.js');
const DICT = window.AEGIS_DICT;
const PATTERNS = window.AEGIS_PATTERNS;
const hasNonAscii = s => /[⺀-⻿　-〿㐀-䶿一-鿿豈-﫿＀-￯]/.test(s);
function translateText(text) {
    if (typeof text !== 'string' || !text.length) return null;
    if (hasNonAscii(text)) return null;
    const trimmed = text.trim();
    if (!trimmed.length) return null;
    if (DICT.hasOwnProperty(trimmed)) return DICT[trimmed];
    for (const p of PATTERNS) {
        const re = new RegExp(p.re, 'g');
        if (re.test(text)) { re.lastIndex = 0; const out = text.replace(re, p.zh); if (out !== text) return out; }
    }
    const keys = Object.keys(DICT).filter(k => k.includes(' ')).sort((a, b) => b.length - a.length);
    const esc = keys.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const re = new RegExp('(^|[\\s(\\[{\\"\']|\\u201c|\\u2018)(' + esc + ')(?=[\\s),;:.!?)\\]}%\\u201d\\u2019\\u3002\\uff0c\\uff1b\\uff1a\\uff01\\uff1f\\u3001]|$)', 'g');
    const out = text.replace(re, (m, lead, word) => lead + DICT[word]);
    return out !== text ? out : null;
}
// Real text nodes from the source:
const tests = [
    'Threat Monitor',            // sidebar
    'Dashboard',                 // sidebar
    'Blocked Actions',           // sidebar
    'Tool Permissions',          // sidebar
    'Settings',                  // sidebar
    'No threats detected.',      // threats.js empty state
    'threats detected in this trace',  // agent-runs title attr
    "threats detected across this runtime's agents", // agent-runs title attr
    'threat detected',           // agent-map status label
    '12 detected',               // agent-runs `${det} detected`
    'Threats blocked · 24h',     // dashboard stat
    'Critical · 7d',             // dashboard stat
    '3 of 12 rules enabled',     // rules.js stat
    'No threat detected in this exchange.', // storylines
    'You have 5 of 12 local custom rules. Upgrade to Cloud for unlimited rules with ML-powered detection.', // rules.js banner
    'Copy',                      // copy button
    'Aegis',              // brand — must NOT translate
];
let pass = 0, fail = 0;
for (const t of tests) {
    const r = translateText(t);
    const ok = r !== null && r !== t;
    console.log((ok ? '✓' : '✗').padEnd(3), JSON.stringify(t).padEnd(44), '=>', ok ? JSON.stringify(r) : '(未翻译)');
    ok ? pass++ : fail++;
}
console.log('\n' + pass + '/' + tests.length + ' 命中' + (fail ? '，' + fail + ' 未命中' : ''));
