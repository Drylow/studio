// Rendu sans carte graphique (machine cloud) : morceaux de 20 s rendus par plusieurs navigateurs en parallèle,
// chaque morceau encodé en MP4 puis ses images effacées (disque), reprise automatique après un redémarrage.
//   node tools/cloud_render.mjs <slug> [--fps 24] [--ss 0.75] [--workers 2] [--chunk 20]
// Sortie : cities/<slug>/renders/cloud/part_XXX.mp4, puis node tools/cloud_render.mjs <slug> --join
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 && args[i + 1] ? args[i + 1] : d; };
const slug = args[0], DIR = path.join(root, 'cities', slug), OUT = path.join(DIR, 'renders', 'cloud');
const FPS = +opt('fps', 24), SS = opt('ss', '0.75'), WORKERS = +opt('workers', 2), CHUNK = +opt('chunk', 20);
const DUR = +(/DUR = (\d+(\.\d+)?)/.exec(fs.readFileSync(path.join(DIR, 'scene.js'), 'utf8'))[1]);
const NCH = Math.ceil(DUR / CHUNK);
fs.mkdirSync(OUT, { recursive: true });
const ff = process.env.FFMPEG || 'ffmpeg';

if (args.includes('--join')) {
  const list = path.join(OUT, 'list.txt');
  fs.writeFileSync(list, Array.from({ length: NCH }, (_, k) => `file 'part_${String(k).padStart(3, '0')}.mp4'`).join('\n'));
  const out = path.join(DIR, 'renders', `${slug}.mp4`);
  const r = spawnSync(ff, ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list, '-i', path.join(DIR, 'assets', 'music.m4a'),
    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', String(DUR), '-movflags', '+faststart', out], { stdio: 'inherit' });
  console.log(r.status === 0 ? `-> ${out}` : 'join failed'); process.exit(r.status ?? 1);
}

const { chromium } = await import(path.join(root, '..', 'timelapse_engine', 'node_modules', 'playwright-core', 'index.mjs'));
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.woff2': 'font/woff2', '.m4a': 'audio/mp4' };
const srv = http.createServer((q, r) => { let u = decodeURIComponent(q.url.split('?')[0]); if (u === '/') u = '/index.html'; const f = path.join(DIR, u);
  if (!f.startsWith(DIR)) { r.writeHead(403); return r.end(); }
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); return r.end(); } let body = d;
    if (u === '/scene.js') body = Buffer.from(d.toString().replace(/SS = [0-9.]+/, 'SS = ' + SS));
    r.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream' }); r.end(body); }); });
await new Promise(r => srv.listen(0, '127.0.0.1', r));
const exe = process.env.CHROME || fs.readdirSync('/opt/pw-browsers').filter(d => d.startsWith('chromium_headless_shell-')).map(d => `/opt/pw-browsers/${d}/chrome-linux/headless_shell`)[0];

const done = (k) => fs.existsSync(path.join(OUT, `part_${String(k).padStart(3, '0')}.mp4`));
const mine = new Set();
function claim() {          // un morceau libre (verrou = fichier .lock avec le pid ; un verrou d'un process mort est repris)
  for (let k = 0; k < NCH; k++) {
    if (done(k) || mine.has(k)) continue;
    const lock = path.join(OUT, `part_${String(k).padStart(3, '0')}.lock`);
    if (fs.existsSync(lock)) { const pid = +fs.readFileSync(lock, 'utf8'); try { process.kill(pid, 0); if (pid !== process.pid) continue; } catch { /* mort */ } }
    fs.writeFileSync(lock, String(process.pid)); mine.add(k); return k;
  }
  return -1;
}
async function worker(w) {
  const b = await chromium.launch({ executablePath: exe, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  p.on('pageerror', e => console.error(`[w${w}] page error`, e.message));
  await p.goto(`http://127.0.0.1:${srv.address().port}/`);
  await p.waitForFunction(() => window.__video, null, { timeout: 900000 });
  for (let k = claim(); k >= 0; k = claim()) {
    const dir = path.join(OUT, `fr_${String(k).padStart(3, '0')}`); fs.mkdirSync(dir, { recursive: true });
    const t0 = k * CHUNK, n = Math.round(Math.min(CHUNK, DUR - t0) * FPS), st = Date.now();
    for (let i = 0; i < n; i++) {
      const f = path.join(dir, `${String(i).padStart(5, '0')}.jpg`);
      if (fs.existsSync(f)) continue;
      await p.evaluate(t => window.__video.renderAt(t), t0 + i / FPS);
      fs.writeFileSync(f + '.tmp', await p.screenshot({ type: 'jpeg', quality: 90 })); fs.renameSync(f + '.tmp', f);
      if (i % 120 === 0) console.log(`[w${w}] part ${k}/${NCH - 1} image ${i}/${n} ${((Date.now() - st) / (i + 1) / 1000).toFixed(2)} s/img`);
    }
    const part = path.join(OUT, `part_${String(k).padStart(3, '0')}.mp4`);
    const r = spawnSync(ff, ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(dir, '%05d.jpg'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '17',
      '-pix_fmt', 'yuv420p', '-r', String(FPS), part + '.tmp.mp4']);
    if (r.status === 0) { fs.renameSync(part + '.tmp.mp4', part); fs.rmSync(dir, { recursive: true, force: true }); console.log(`[w${w}] part ${k} OK`); }
    else console.error(`[w${w}] part ${k} encode failed`);
    fs.rmSync(path.join(OUT, `part_${String(k).padStart(3, '0')}.lock`), { force: true });
  }
  await b.close();
}
await Promise.all(Array.from({ length: WORKERS }, (_, w) => worker(w)));
srv.close();
console.log(Array.from({ length: NCH }, (_, k) => done(k)).every(Boolean) ? 'ALL PARTS DONE' : 'some parts missing');
