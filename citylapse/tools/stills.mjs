// Still frames of a city without a GPU (SwiftShader): node tools/stills.mjs <slug> 12,60,140 [--ss 0.75] [--out dir] [--nohud]
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('..', import.meta.url));
const args = process.argv.slice(2), opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 && args[i + 1] ? args[i + 1] : d; };
const slug = args[0], DIR = path.join(root, 'cities', slug), OUT = opt('out', path.join(DIR, 'snaps')), SS = opt('ss', '0.75');
const times = args[1].split(',').map(Number); fs.mkdirSync(OUT, { recursive: true });
const { chromium } = await import(path.join(root, '..', 'timelapse_engine', 'node_modules', 'playwright-core', 'index.mjs'));
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.woff2': 'font/woff2', '.m4a': 'audio/mp4' };
const srv = http.createServer((q, r) => { let u = decodeURIComponent(q.url.split('?')[0]); if (u === '/') u = '/index.html'; const f = path.join(DIR, u);
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); return r.end(); } let body = d;
    if (u === '/scene.js') body = Buffer.from(d.toString().replace(/SS = [0-9.]+/, 'SS = ' + SS));
    r.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream' }); r.end(body); }); });
await new Promise(r => srv.listen(0, '127.0.0.1', r));
const exe = process.env.CHROME || fs.readdirSync('/opt/pw-browsers').filter(d => d.startsWith('chromium_headless_shell-')).map(d => `/opt/pw-browsers/${d}/chrome-linux/headless_shell`)[0];
const b = await chromium.launch({ executablePath: exe, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
p.on('pageerror', e => console.error('page error', e.message)); p.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.log('console', m.text().slice(0, 300)); });
const t0 = Date.now();
await p.goto(`http://127.0.0.1:${srv.address().port}/`);
await p.waitForFunction(() => window.__video, null, { timeout: 900000 });
console.log(`ready in ${((Date.now() - t0) / 1000).toFixed(0)} s`);
const info = await p.evaluate(() => ({ DUR: window.__video.DUR, sfx: window.__video.sfx || [], events: window.__video.events || [] }));
fs.writeFileSync(path.join(DIR, 'timeline.json'), JSON.stringify(info));
console.log('DUR', info.DUR, 'events', info.events.length, 'cues', info.sfx.length);
const NOHUD = args.includes('--nohud');   // clean frames for thumbnails
for (const t of times) { await p.evaluate(([t, h]) => { window.__video.renderAt(t); if (h) for (const id of ['ui', 'black', 'title', 'card']) { const e = document.getElementById(id); if (e) e.style.visibility = 'hidden'; } }, [t, NOHUD]); await p.screenshot({ path: path.join(OUT, `s_${String(t).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 85 }); console.log('still', t); }
await b.close(); srv.close();
