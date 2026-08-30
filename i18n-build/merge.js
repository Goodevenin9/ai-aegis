/**
 * Merge i18n-build/part{A,B,C,D}.json → js/i18n-dict.js
 * First-wins on duplicate exact keys; patterns deduped by regex string.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const BUILD = __dirname;
const OUT = path.join(ROOT, 'src', 'aegis', 'app', 'assets', 'web', 'js', 'i18n-dict.js');

const exact = {};
const patterns = [];
const seen = new Set();

// Curated overrides: exact keys override-wins, patterns prepend so the more
// specific ones (e.g. "N threats detected") are matched before generic ones
// (e.g. "N threats").
const overrides = JSON.parse(fs.readFileSync(path.join(BUILD, 'overrides.json'), 'utf8'));

const parts = ['partA', 'partB', 'partC', 'partD'];
let partCounts = {};

for (const p of parts) {
    const file = path.join(BUILD, p + '.json');
    if (!fs.existsSync(file)) { console.log('MISSING:', p); continue; }
    const data = JSON.parse(fs.readFileSync(file, 'utf8'));
    partCounts[p] = { exact: Object.keys(data.exact || {}).length, patterns: (data.patterns || []).length };
    for (const [k, v] of Object.entries(data.exact || {})) {
        if (!exact.hasOwnProperty(k)) exact[k] = v;
    }
    for (const pat of (data.patterns || [])) {
        if (!seen.has(pat.re)) { seen.add(pat.re); patterns.push(pat); }
    }
}

// Overrides last: exact keys replace (or add) anything from the parts.
for (const [k, v] of Object.entries(overrides.exact || {})) exact[k] = v;
// Override patterns go first so specific phrases win over generic ones.
for (const pat of (overrides.patterns || [])) {
    if (seen.has(pat.re)) continue;
    seen.add(pat.re);
    patterns.unshift(pat);
}

// --- emit ---
function jsString(s) {
    return JSON.stringify(s)
        .replace(/</g, '\\u003c');
}
const lines = [];
lines.push('/**');
lines.push(' * Aegis i18n dictionary — English → 中文. AUTO-GENERATED from i18n-build/.');
lines.push(' * Loaded by js/i18n.js. Do not edit by hand.');
lines.push(' */');
lines.push('window.SV_DICT = {');
for (const k of Object.keys(exact).sort((a, b) => b.length - a.length)) {
    lines.push('    ' + jsString(k) + ': ' + jsString(exact[k]) + ',');
}
lines.push('};');
lines.push('');
lines.push('/**');
lines.push(' * Dynamic string patterns: { re, zh }. Matched while lang === "zh".');
lines.push(' */');
lines.push('window.SV_PATTERNS = [');
for (const p of patterns) {
    lines.push('    { re: ' + jsString(p.re) + ', zh: ' + jsString(p.zh) + ' },');
}
lines.push('];');

fs.writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('Merged into', OUT);
console.log('exact entries:', Object.keys(exact).length);
console.log('patterns:', patterns.length);
console.log('per-part:', JSON.stringify(partCounts));
