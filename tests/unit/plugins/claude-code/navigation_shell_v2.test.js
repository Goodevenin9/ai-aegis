'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..', '..', '..', '..');
const WEB = path.join(ROOT, 'src', 'aegis', 'app', 'assets', 'web');
const read = (...parts) => fs.readFileSync(path.join(WEB, ...parts), 'utf8');

test('desktop shell uses the left navigation instead of the crowded top command row', () => {
  const html = read('index.html');
  const app = read('js', 'app.js');
  const shell = read('css', 'shell-v2.css');

  assert.match(html, /class="app-container ag-sidebar-shell"/);
  assert.doesNotMatch(html, /id="topnav"/);
  assert.doesNotMatch(html, /components\/topnav\.js/);
  assert.doesNotMatch(app, /TopNav\.init\(\)/);
  assert.match(html, /css\/shell-v2\.css/);
  assert.match(shell, /\.ag-sidebar-shell \.sidebar\.collapsed\s*\{[^}]*width:\s*64px/s,
    'the legacy icon-rail collapse must still reduce the shell width');
  assert.ok(app.indexOf('Sidebar.currentPage = initialPage') < app.indexOf('Sidebar.render()'),
    'the deep-linked page must be known before grouped navigation renders');
});

test('left navigation promotes P2 security operations and groups the product by user task', () => {
  const sidebar = read('js', 'components', 'sidebar.js');
  const palette = read('js', 'components', 'command-palette.js');

  assert.match(sidebar, /id:\s*'security-operations',\s*label:\s*'Security Copilot',\s*icon:/);
  for (const section of ['Overview', 'Protection', 'Observability', 'Operations', 'Governance', 'Connections', 'Support']) {
    assert.match(sidebar, new RegExp(`'${section}'`), `missing ${section} navigation section`);
  }
  assert.match(sidebar, /savedState === null \? !sec\.containsActive/,
    'inactive sections should start collapsed to keep the rail scannable');
  assert.match(sidebar, /setActive\(page\)[\s\S]*this\.revealPage\(page\)/,
    'history navigation must reveal an active item inside collapsed groups');
  assert.match(palette, /Sidebar\.sectionFor\(id\)/,
    'the command palette should consume the sidebar information architecture');
  assert.doesNotMatch(palette, /return 'Visibility'|return 'Govern'|return 'Connect'/,
    'the command palette must not retain a second, stale section taxonomy');
});

test('language control stays in the right header and exposes an explicit bilingual label', () => {
  const header = read('js', 'components', 'header.js');
  const i18n = read('js', 'i18n.js');

  assert.match(header, /className\s*=\s*'lang-toggle-btn'/);
  assert.match(header, /lang-toggle-icon/);
  assert.match(header, /lang-toggle-label/);
  assert.match(i18n, /document\.documentElement\.lang\s*=/);
  assert.match(i18n, /localStorage\.setItem\(STORAGE_KEY, next\)/);
  assert.match(i18n, /hasSkippableAncestor\(node, true\)/,
    'form placeholders and accessibility labels should participate in translation');
});

test('Chinese dictionary covers the new shell and P2 security workspace', () => {
  global.window = {};
  const dictPath = path.join(WEB, 'js', 'i18n-dict.js');
  delete require.cache[require.resolve(dictPath)];
  require(dictPath);

  const expected = {
    'Security Copilot': '安全运营助手',
    'Security operations, not another chatbot': '安全运营工作台，而不只是聊天机器人',
    'Evidence & multimodal intake': '证据与多模态接入',
    'Evidence-grounded RAG': '基于证据的 RAG',
    'Session immunity': '会话免疫',
    'Governed memory': '受治理记忆',
  };
  for (const [english, chinese] of Object.entries(expected)) {
    assert.equal(window.AEGIS_DICT[english], chinese, `missing translation for ${english}`);
  }
});

test('English mode does not ship a Chinese-only Agent prompt', () => {
  const operations = read('js', 'pages', 'security-operations.js');
  assert.doesNotMatch(operations, /placeholder="例如：/);
  assert.match(operations, /placeholder="For example: investigate permission drift/);
});
