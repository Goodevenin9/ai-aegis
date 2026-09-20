const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const repo = path.resolve(__dirname, '..', '..');
const work = path.join(repo, 'tmp', 'full-feature-video');
const scenes = JSON.parse(fs.readFileSync(path.join(work, 'scenes-runtime.json'), 'utf8'));
const base = 'http://127.0.0.1:8741';

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function addCaption(page, scene) {
  await page.evaluate(({ zh, en, label }) => {
    document.getElementById('aegis-demo-caption')?.remove();
    const box = document.createElement('section');
    box.id = 'aegis-demo-caption';
    box.innerHTML = `<div class="scene-label">${label}</div><div class="scene-zh">${zh}</div><div class="scene-en">${en}</div>`;
    box.style.cssText = [
      'position:fixed','left:28px','right:28px','bottom:24px','z-index:2147483647',
      'padding:15px 22px','border-radius:14px','border:1px solid rgba(75,130,255,.72)',
      'background:rgba(5,14,34,.92)','box-shadow:0 18px 50px rgba(0,0,0,.38)',
      'color:white','font-family:Inter,Segoe UI,Microsoft YaHei,sans-serif','pointer-events:none'
    ].join(';');
    const style = document.createElement('style');
    style.textContent = `
      #aegis-demo-caption .scene-label{display:inline-block;margin-right:12px;padding:4px 9px;border-radius:7px;background:#2e6df6;color:#fff;font-size:12px;font-weight:800;letter-spacing:.8px;vertical-align:middle}
      #aegis-demo-caption .scene-zh{display:inline;font-size:21px;font-weight:750;line-height:1.45;vertical-align:middle}
      #aegis-demo-caption .scene-en{margin-top:5px;color:#b9c9ed;font-size:14px;line-height:1.35}
    `;
    box.appendChild(style);
    document.body.appendChild(box);
  }, { zh: scene.zh, en: scene.en, label: scene.label });
}

async function titleCard(page, scene) {
  await page.setContent(`<!doctype html><html><body><main>
    <div class="eyebrow">AI AEGIS · 灵盾</div>
    <h1>${scene.title}</h1>
    <p>${scene.subtitle}</p>
    <div class="pill-row"><span>PreTool Security</span><span>Five-stage Pipeline</span><span>Auditable Governance</span><span>Open Source</span></div>
    <div class="rule"></div><small>Frozen project snapshot · 2026-09-20</small>
  </main><style>
    html,body{width:100%;height:100%;margin:0;background:#061127;color:#fff;font-family:Inter,Segoe UI,Microsoft YaHei,sans-serif;overflow:hidden}
    body:before{content:"";position:absolute;inset:-20%;background:radial-gradient(circle at 72% 28%,rgba(42,113,255,.28),transparent 34%),radial-gradient(circle at 30% 80%,rgba(65,224,204,.18),transparent 31%)}
    body:after{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(76,120,210,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(76,120,210,.08) 1px,transparent 1px);background-size:56px 56px}
    main{position:relative;z-index:2;width:78%;margin:0 auto;padding-top:175px}
    .eyebrow{color:#58d8ff;font-weight:800;letter-spacing:3px;font-size:18px}
    h1{font-size:66px;line-height:1.13;margin:25px 0 20px;max-width:1200px} p{font-size:25px;line-height:1.55;color:#b9c9ed;max-width:1050px}
    .pill-row{display:flex;gap:14px;margin-top:42px}.pill-row span{border:1px solid #2e6df6;background:rgba(37,94,210,.18);border-radius:9px;padding:10px 15px;color:#dbe7ff;font-size:14px}
    .rule{height:1px;background:linear-gradient(90deg,#2e6df6,transparent);margin-top:72px}small{display:block;margin-top:15px;color:#7991bd;letter-spacing:1px}
  </style></body></html>`);
  await addCaption(page, scene);
}

async function record() {
  fs.mkdirSync(work, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Users\\19546\\AppData\\Local\\ms-playwright\\chromium-1228\\chrome-win64\\chrome.exe',
  });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
    deviceScaleFactor: 1,
    locale: 'zh-CN',
    recordVideo: { dir: work, size: { width: 1600, height: 900 } },
  });
  await context.addInitScript(() => {
    localStorage.setItem('ag-lang', 'zh');
    localStorage.setItem('ag-guardian-notice-acked', '1');
    localStorage.setItem('ag-welcome-seen-v2', 'true');
  });
  const page = await context.newPage();
  const video = page.video();
  const started = Date.now();
  const timings = [];

  for (let i = 0; i < scenes.length; i++) {
    const scene = scenes[i];
    if (scene.kind === 'card') {
      await titleCard(page, scene);
    } else {
      await page.goto(base + scene.route, { waitUntil: 'networkidle', timeout: 30000 });
      await sleep(900);
      await addCaption(page, scene);
    }
    const ready = Date.now() - started;
    timings.push({ index: i + 1, ready_ms: ready, voice_start_ms: ready + 650, label: scene.label });
    const total = Math.ceil((scene.voice_duration + 1.55) * 1000);
    if (scene.scroll && scene.kind !== 'card') {
      await sleep(Math.floor(total * 0.52));
      await page.evaluate(ratio => window.scrollTo({ top: Math.max(0, document.body.scrollHeight * ratio - window.innerHeight / 2), behavior: 'smooth' }), scene.scroll);
      await sleep(total - Math.floor(total * 0.52));
    } else {
      await sleep(total);
    }
  }
  const ended = Date.now() - started;
  await context.close();
  await browser.close();
  const rawVideo = await video.path();
  fs.writeFileSync(path.join(work, 'timings.json'), JSON.stringify({ started_ms: 0, ended_ms: ended, raw_video: rawVideo, scenes: timings }, null, 2));
  console.log(rawVideo);
}

record().catch(error => { console.error(error); process.exit(1); });
