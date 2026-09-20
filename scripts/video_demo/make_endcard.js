const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const output = path.resolve(__dirname, '..', '..', 'tmp', 'full-feature-video', 'endcard.png');
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Users\\19546\\AppData\\Local\\ms-playwright\\chromium-1228\\chrome-win64\\chrome.exe',
  });
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
  await page.setContent(`<!doctype html><html><body><main>
    <div class="eyebrow">AI AEGIS · 灵盾</div>
    <h1>可运行 · 可测试 · 可解释 · 可治理</h1>
    <p>Apache 2.0 开源社区版 + 面向企业自研 Agent 的治理与审计能力</p>
    <div class="pill-row"><span>PreTool Security</span><span>Five-stage Pipeline</span><span>Auditable Governance</span><span>Open Source</span></div>
    <div class="rule"></div><small>Frozen project snapshot · 2026-09-20</small>
  </main><section id="caption"><div><b>17 · DELIVERY</b> AI Aegis：让 Agent 的每一次行动有边界、有证据、可追溯。</div><p>AI Aegis gives every agent action a boundary, evidence, and an audit trail.</p></section><style>
    html,body{width:100%;height:100%;margin:0;background:#061127;color:#fff;font-family:Inter,Segoe UI,Microsoft YaHei,sans-serif;overflow:hidden}
    body:before{content:"";position:absolute;inset:-20%;background:radial-gradient(circle at 72% 28%,rgba(42,113,255,.28),transparent 34%),radial-gradient(circle at 30% 80%,rgba(65,224,204,.18),transparent 31%)}
    body:after{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(76,120,210,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(76,120,210,.08) 1px,transparent 1px);background-size:56px 56px}
    main{position:relative;z-index:2;width:78%;margin:0 auto;padding-top:175px}.eyebrow{color:#58d8ff;font-weight:800;letter-spacing:3px;font-size:18px}
    h1{font-size:66px;line-height:1.13;margin:25px 0 20px;max-width:1200px}p{font-size:25px;line-height:1.55;color:#b9c9ed;max-width:1050px}
    .pill-row{display:flex;gap:14px;margin-top:42px}.pill-row span{border:1px solid #2e6df6;background:rgba(37,94,210,.18);border-radius:9px;padding:10px 15px;color:#dbe7ff;font-size:14px}
    .rule{height:1px;background:linear-gradient(90deg,#2e6df6,transparent);margin-top:72px}small{display:block;margin-top:15px;color:#7991bd;letter-spacing:1px}
    #caption{position:fixed;left:28px;right:28px;bottom:24px;z-index:8;padding:15px 22px;border-radius:14px;border:1px solid rgba(75,130,255,.72);background:rgba(5,14,34,.92);box-shadow:0 18px 50px rgba(0,0,0,.38)}
    #caption div{font-size:21px;font-weight:750;line-height:1.45}#caption b{display:inline-block;margin-right:12px;padding:4px 9px;border-radius:7px;background:#2e6df6;font-size:12px;letter-spacing:.8px;vertical-align:middle}
    #caption p{margin:5px 0 0;color:#b9c9ed;font-size:14px;line-height:1.35}
  </style></body></html>`);
  await page.screenshot({ path: output });
  await browser.close();
  console.log(output);
})().catch(error => { console.error(error); process.exit(1); });
