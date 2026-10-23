// Rendu d'un timelapse 3D : scène (prep.py) + plan (années, caméra, textes) -> images ou vidéo.
//   node timelapse_engine/render.mjs --scene work/timelapse/tel_aviv/scene.json --plan plan.json --stills 0,5,12 --out dir
//   node timelapse_engine/render.mjs --scene ... --plan ... --video out.mp4 [--fps 30] [--from 0 --to 40]
// Le navigateur (Chromium du système) rend en WebGL logiciel ; ffmpeg vient d'imageio_ffmpeg.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn, execSync } from 'node:child_process';
import { chromium } from 'playwright-core';

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, all) => (v.startsWith('--') ? [...a, [v.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]] : a), []));
const ENGINE = path.dirname(new URL(import.meta.url).pathname);
const files = { '/scene.json': path.resolve(args.scene), '/plan.json': path.resolve(args.plan) };
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.woff2': 'font/woff2' };

const server = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  const f = files[u] || path.join(ENGINE, u === '/' ? 'scene.html' : u);
  if (!f.startsWith(ENGINE) && !Object.values(files).includes(f)) { res.writeHead(403); return res.end(); }
  fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); return res.end(); } res.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream' }); res.end(d); });
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const port = server.address().port;

const exe = fs.readdirSync('/opt/pw-browsers').filter(d => d.startsWith('chromium_headless_shell-')).map(d => `/opt/pw-browsers/${d}/chrome-linux/headless_shell`).find(fs.existsSync);
const browser = await chromium.launch({ executablePath: process.env.CHROME || exe, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
page.on('console', m => { if (m.type() === 'error') console.error('page:', m.text()); });
page.on('pageerror', e => console.error('page error:', e.message));
await page.goto(`http://127.0.0.1:${port}/?scene=/scene.json&plan=/plan.json${args.noshadow ? '&noshadow=1' : ''}`);
await page.waitForFunction(() => window.ready === true, null, { timeout: 300000 });
await page.evaluate(() => document.fonts.ready);

const shot = () => page.screenshot({ type: 'jpeg', quality: 93 });
if (args.stills) {
  fs.mkdirSync(args.out, { recursive: true });
  for (const t of String(args.stills).split(',').map(Number)) {
    const t0 = Date.now();
    const y = await page.evaluate(t => window.renderAt(t), t);
    fs.writeFileSync(path.join(args.out, `still_${String(t).padStart(6, '0')}.jpg`), await shot());
    console.log(`t=${t}s année ${y.toFixed(1)} (${Date.now() - t0} ms)`);
  }
} else if (args.video) {
  const fps = Number(args.fps || 30), from = Number(args.from || 0);
  const plan = JSON.parse(fs.readFileSync(args.plan));
  const to = Number(args.to || plan.duration);
  const ff = execSync(`python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"`).toString().trim();
  const enc = spawn(ff, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', args.video], { stdio: ['pipe', 'inherit', 'inherit'] });
  const pops = []; let prevYear = null; const T0 = Date.now();
  const n = Math.round((to - from) * fps);
  for (let i = 0; i < n; i++) {
    const t = from + i / fps;
    const y = await page.evaluate(t => window.renderAt(t), t);
    if (prevYear !== null && y > prevYear) pops.push([+(t - from).toFixed(3), await page.evaluate(([a, b]) => window.births(a, b), [prevYear, y])]);
    prevYear = y;
    if (!enc.stdin.write(await shot())) await new Promise(r => enc.stdin.once('drain', r));
    if (i % 60 === 0) console.log(`image ${i}/${n} année ${y.toFixed(1)} — ${((Date.now() - T0) / (i + 1)).toFixed(0)} ms/image`);
  }
  enc.stdin.end(); await new Promise(r => enc.on('close', r));
  fs.writeFileSync(args.video.replace(/\.mp4$/, '.pops.json'), JSON.stringify(pops));
}
await browser.close(); server.close();
