/** Check actual animated bounds against placed rocks, independently of placement. */
import http from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
let out = path.join(here, 'renders/clearance.json');
for (let i = 0; i < args.length; i++) {
  if (args[i] !== '--out' || !args[i + 1]) throw new Error('Usage: node verify-clearance.mjs [--out report.json]');
  out = path.resolve(args[++i]);
}
const files = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/index.html', ['index.html', 'text/html; charset=utf-8']],
  ['/scene.js', ['scene.js', 'application/javascript']],
  ['/THREE-LICENSE.txt', ['THREE-LICENSE.txt', 'text/plain; charset=utf-8']],
]);
const server = http.createServer(async (req, res) => {
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); res.end(); return; }
  const file = files.get(new URL(req.url, 'http://localhost').pathname);
  if (!file) { res.writeHead(404); res.end(); return; }
  try {
    const data = await readFile(path.join(here, 'dist', file[0]));
    res.writeHead(200, { 'Content-Type': file[1], 'Cache-Control': 'no-store' });
    res.end(req.method === 'HEAD' ? undefined : data);
  } catch {
    res.writeHead(500); res.end('Build the prototype before checking clearance.');
  }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
const errors = [];
try {
  browser = await chromium.launch({
    executablePath: process.env.DEEPSEA_CHROMIUM || '/usr/bin/chromium',
    headless: true,
    args: ['--disable-dev-shm-usage', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
  await page.addInitScript(() => {
    window.__CAPTURE_MODE__ = true;
    window.__DEEPSEA_DIAGNOSTICS__ = true;
  });
  await page.goto(origin);
  await page.waitForFunction(() => window.DeepSeaFilm?.diagnostics);
  const report = await page.evaluate(() => {
    const film = window.DeepSeaFilm, diagnostics = film.diagnostics, rocks = diagnostics.rockBoxes;
    if (!Number.isFinite(film.duration) || film.duration <= 0 || !rocks.length) throw new Error('Scene diagnostics are incomplete.');
    const validBox = box => box.min.length === 3 && box.max.length === 3
      && box.min.every(Number.isFinite) && box.max.every(Number.isFinite)
      && box.min.every((value, i) => value <= box.max[i]);
    if (!rocks.every(validBox)) throw new Error('A rock has invalid bounds.');
    // Separating-axis distance uses only observed boxes, not the terrain predicate.
    function distance(a, b) {
      return Math.hypot(...a.min.map((value, i) => Math.max(0, value - b.max[i], b.min[i] - a.max[i])));
    }
    const probe = Math.min(10, film.duration * .4);
    const first = JSON.stringify(diagnostics.sample(probe));
    diagnostics.sample(film.duration * .9);
    const repeated = JSON.stringify(diagnostics.sample(probe));
    const minimum = {}, collisions = [];
    let overlapCount = 0, finite = true, alwaysVisible = true;
    const fps = 60, samples = Math.ceil(film.duration * fps) + 1;
    for (let frame = 0; frame < samples; frame++) {
      const time = Math.min(film.duration, frame / fps), sample = diagnostics.sample(time);
      if (sample.camera.length !== 3 || !sample.camera.every(Number.isFinite)) finite = false;
      const observed = {
        ...sample.bounds,
        camera: { min: sample.camera.map(value => value - .55), max: sample.camera.map(value => value + .55) },
      };
      if (!Object.keys(sample.bounds).length) throw new Error('No creature bounds were returned.');
      for (const [name, box] of Object.entries(observed)) {
        if (!validBox(box)) { finite = false; continue; }
        if (name !== 'camera' && !box.visible) alwaysVisible = false;
        minimum[name] ??= { distance: Infinity };
        for (let rock = 0; rock < rocks.length; rock++) {
          const gap = distance(box, rocks[rock]);
          if (gap < minimum[name].distance) minimum[name] = { distance: gap, time, rock };
          if (gap === 0) {
            overlapCount++;
            if (collisions.length < 20) collisions.push({ time, name, rock });
          }
        }
      }
    }
    const rewinds = first === repeated;
    return {
      schema: 'deep-sea-clearance-check-v1',
      passed: finite && rewinds && alwaysVisible && overlapCount === 0,
      method: '60 poses per second including both endpoints; observed deformed world bounds against every retained rock box; camera box radius 0.55.',
      limits: 'Discrete poses; this check does not test the seafloor or establish continuous clearance between samples.',
      duration_seconds: film.duration, sample_hz: fps, samples, rock_count: rocks.length,
      finite, rewind_deterministic: rewinds, creatures_always_visible: alwaysVisible,
      overlap_count: overlapCount, first_overlaps: collisions, minimum_rock_distance: minimum,
      antialias: film.antialias, layout: film.layout,
    };
  });
  report.browser_errors = errors;
  report.passed &&= errors.length === 0;
  await mkdir(path.dirname(out), { recursive: true });
  await writeFile(out, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ report: out, ...report }, null, 2));
  if (!report.passed) process.exitCode = 1;
} finally {
  try {
    if (browser) await browser.close();
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
}
