/** Inspect a periodic film independently of its terrain-placement predicate. */
import http from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { chromium } from 'playwright';

const here = path.dirname(fileURLToPath(import.meta.url));
const options = { '--dist': path.join(here, 'dist-sleep'), '--out': path.join(here, 'renders/sleep-loop-check.json'), '--sample-hz': '30' };
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i += 2) {
  if (!(args[i] in options) || !args[i + 1]) throw new Error('Usage: node verify-sleep-loop.mjs [--dist directory] [--out report.json] [--sample-hz 30]');
  options[args[i]] = args[i + 1];
}
const dist = path.resolve(options['--dist']), out = path.resolve(options['--out']);
const sampleHz = Number(options['--sample-hz']);
if (!Number.isInteger(sampleHz) || sampleHz < 1 || sampleHz > 60) throw new Error('Sample rate must be an integer between 1 and 60.');
const allowed = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/index.html', ['index.html', 'text/html; charset=utf-8']],
  ['/scene.js', ['scene.js', 'application/javascript']],
  ['/THREE-LICENSE.txt', ['THREE-LICENSE.txt', 'text/plain; charset=utf-8']],
]);
const servedHashes = new Map();
const server = http.createServer(async (req, res) => {
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); res.end(); return; }
  const file = allowed.get(new URL(req.url, 'http://localhost').pathname);
  if (!file) { res.writeHead(404); res.end(); return; }
  try {
    const bytes = await readFile(path.join(dist, file[0]));
    servedHashes.set(file[0], createHash('sha256').update(bytes).digest('hex'));
    res.writeHead(200, { 'Content-Type': file[1], 'Cache-Control': 'no-store' });
    res.end(req.method === 'HEAD' ? undefined : bytes);
  } catch {
    res.writeHead(500); res.end('Build the selected film before checking its loop.');
  }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
const browserErrors = [];
try {
  browser = await chromium.launch({
    executablePath: process.env.DEEPSEA_CHROMIUM || '/usr/bin/chromium', headless: true,
    args: ['--disable-dev-shm-usage', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', error => browserErrors.push(error.message));
  page.on('console', message => {
    const line = message.text();
    if (line.startsWith('SLEEP_CHECK ')) console.log(line);
  });
  await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
  await page.addInitScript(() => { window.__CAPTURE_MODE__ = true; window.__DEEPSEA_DIAGNOSTICS__ = true; });
  await page.goto(origin, { waitUntil: 'domcontentloaded', timeout: 120000 });
  await page.waitForFunction(() => window.DeepSeaFilm?.diagnostics, null, { timeout: 120000 });
  const result = await page.evaluate(({ sampleHz }) => {
    const started = performance.now(), film = window.DeepSeaFilm, d = film.diagnostics, duration = film.duration;
    if (!Number.isFinite(duration) || duration <= 0 || !d.rockBoxes?.length) throw new Error('Incomplete film diagnostics.');
    const canvas = document.getElementById('film'), copy = document.createElement('canvas');
    copy.width = canvas.width; copy.height = canvas.height;
    const context = copy.getContext('2d', { willReadFrequently: true });
    function image(t) {
      film.render(t); context.drawImage(canvas, 0, 0);
      return { time: t, png: canvas.toDataURL('image/png').split(',')[1], pixels: context.getImageData(0, 0, copy.width, copy.height).data };
    }
    function delta(a, b) {
      let sum = 0, max = 0, changed = 0;
      for (let i = 0; i < a.length; i += 4) {
        let different = false;
        for (let j = 0; j < 3; j++) { const value = Math.abs(a[i + j] - b[i + j]); sum += value * value; max = Math.max(max, value); different ||= value !== 0; }
        if (different) changed++;
      }
      return { rms: Math.sqrt(sum / (a.length / 4 * 3)), maximum_channel_difference: max, changed_pixel_fraction: changed / (a.length / 4) };
    }
    const step = Math.min(1 / 30, duration / 4);
    const start = image(0), end = image(duration), before = image(duration - step), after = image(step);
    const seam = delta(before.pixels, start.pixels), forward = delta(start.pixels, after.pixels), endpoints = delta(start.pixels, end.pixels);
    let brightness = 0;
    for (let i = 0; i < start.pixels.length; i += 4) brightness += (start.pixels[i] + start.pixels[i + 1] + start.pixels[i + 2]) / 3;
    brightness /= start.pixels.length / 4;
    const endpointEqual = endpoints.maximum_channel_difference === 0;
    const nativeResolution = canvas.width === 1920 && canvas.height === 1080;
    const suspectedJump = seam.rms > Math.max(forward.rms * 2.5, forward.rms + 1);
    const validBox = box => box.min.length === 3 && box.max.length === 3
      && box.min.every(Number.isFinite) && box.max.every(Number.isFinite)
      && box.min.every((value, i) => value <= box.max[i]);
    if (!d.rockBoxes.every(validBox)) throw new Error('Non-finite or inverted rock bounds.');
    const rockGap = (a, b) => Math.hypot(...a.min.map((value, i) => Math.max(0, value - b.max[i], b.min[i] - a.max[i])));
    const probe = duration * .37, first = JSON.stringify(d.sample(probe));
    d.sample(duration * .88);
    const rewind = first === JSON.stringify(d.sample(probe));
    function renderedPixels(t) {
      film.render(t); context.drawImage(canvas, 0, 0);
      return context.getImageData(0, 0, copy.width, copy.height).data;
    }
    const probePixels = renderedPixels(probe);
    renderedPixels(duration * .88);
    const rewindPixelDelta = delta(probePixels, renderedPixels(probe));
    const rewindPixelsIdentical = rewindPixelDelta.maximum_channel_difference === 0;
    const epsilon = Math.min(.001, duration / 1000), left = d.sample(duration - epsilon), zero = d.sample(0), right = d.sample(epsilon);
    const centre = box => box.min.map((value, i) => (value + box.max[i]) / 2);
    const centres = sample => ({ camera: sample.camera, ...Object.fromEntries(Object.entries(sample.bounds).map(([name, box]) => [name, centre(box)])) });
    const lc = centres(left), zc = centres(zero), rc = centres(right), velocity = {};
    for (const name of Object.keys(zc)) {
      const incoming = zc[name].map((value, i) => (value - lc[name][i]) / epsilon);
      const outgoing = rc[name].map((value, i) => (value - zc[name][i]) / epsilon);
      const difference = Math.hypot(...incoming.map((value, i) => value - outgoing[i]));
      const tolerance = .1 + .05 * Math.max(Math.hypot(...incoming), Math.hypot(...outgoing));
      velocity[name] = { incoming, outgoing, difference, tolerance, continuous: difference <= tolerance };
    }
    const names = Object.keys(zero.bounds).sort();
    if (!names.length) throw new Error('No named animal bounds.');
    const minimum = {}, minimumGroundBound = {}, firstOverlaps = [], warnings = [];
    let overlaps = 0, finite = true, visible = true, stableNames = true;
    const hasGroundMaximum = Number.isFinite(d.groundMaximum), groundMaximum = d.groundMaximum;
    const floorProbeTimes = new Set([0, duration]);
    const samples = Math.ceil(duration * sampleHz) + 1;
    for (let frame = 0; frame < samples; frame++) {
      const time = Math.min(duration, frame / sampleHz), sample = d.sample(time);
      if (JSON.stringify(Object.keys(sample.bounds).sort()) !== JSON.stringify(names)) stableNames = false;
      if (sample.camera.length !== 3 || !sample.camera.every(Number.isFinite)) finite = false;
      const bounds = { ...sample.bounds, camera: { min: sample.camera.map(v => v - .55), max: sample.camera.map(v => v + .55) } };
      for (const [name, box] of Object.entries(bounds)) {
        if (!validBox(box)) { finite = false; continue; }
        if (name !== 'camera' && !box.visible) visible = false;
        minimum[name] ??= { distance: Infinity };
        for (let rock = 0; rock < d.rockBoxes.length; rock++) {
          const distance = rockGap(box, d.rockBoxes[rock]);
          if (distance < minimum[name].distance) minimum[name] = { distance, time, rock };
          if (distance === 0) { overlaps++; if (firstOverlaps.length < 20) firstOverlaps.push({ name, time, rock }); }
        }
        if (hasGroundMaximum) {
          const lowerBound = box.min[1] - groundMaximum;
          minimumGroundBound[name] ??= { distance: Infinity };
          if (lowerBound < minimumGroundBound[name].distance) minimumGroundBound[name] = { distance: lowerBound, time };
        }
      }
      if (frame % 1500 === 0 || frame === samples - 1) {
        console.info(`SLEEP_CHECK ${JSON.stringify({ phase: 'clearance', pose: frame + 1, samples, time_seconds: time })}`);
      }
    }
    for (const value of Object.values(minimumGroundBound)) floorProbeTimes.add(value.time);
    for (let t = 0; t <= duration; t++) floorProbeTimes.add(t);
    const exactFloor = {}, hasVertices = typeof d.vertices === 'function' && typeof d.ground === 'function';
    let checkedVertices = 0, exactFloorFinite = true, observedGroundMaximum = -Infinity;
    if (hasVertices) for (const time of floorProbeTimes) {
      for (const [name, points] of Object.entries(d.vertices(time))) {
        exactFloor[name] ??= { distance: Infinity };
        const nested = Array.isArray(points[0]);
        const count = nested ? points.length : points.length / 3;
        if (!Number.isInteger(count) || count === 0) exactFloorFinite = false;
        for (let i = 0; i < count; i++) {
          const p = nested ? points[i] : [points[i * 3], points[i * 3 + 1], points[i * 3 + 2]];
          const ground = d.ground(p[0], p[2]), clearance = p[1] - ground;
          if (!p.every(Number.isFinite) || !Number.isFinite(ground)) exactFloorFinite = false;
          observedGroundMaximum = Math.max(observedGroundMaximum, ground);
          if (clearance < exactFloor[name].distance) exactFloor[name] = { distance: clearance, time, vertex: [...p] };
          checkedVertices++;
        }
      }
    }
    const floorSafeByBound = hasGroundMaximum && Object.values(minimumGroundBound).every(v => v.distance > 0);
    const floorSamplesSafe = hasVertices && exactFloorFinite && Object.values(exactFloor).every(v => v.distance > 0);
    const declaredGroundBoundConsistent = !hasVertices || (hasGroundMaximum && observedGroundMaximum <= groundMaximum + 1e-8);
    if (!floorSafeByBound) warnings.push('A positive global seafloor clearance bound was not established for all sampled poses.');
    if (!hasVertices) warnings.push('Exact floor checks are unavailable: diagnostics.vertices or ground missing.');
    const velocitiesContinuous = Object.values(velocity).every(v => v.continuous);
    return {
      report: {
        schema: 'deep-sea-sleep-loop-check-v1',
        passed: nativeResolution && film.antialias === true && endpointEqual
          && brightness > 2 && !suspectedJump && velocitiesContinuous && rewind && rewindPixelsIdentical
          && finite && stableNames && visible && overlaps === 0 && floorSafeByBound
          && declaredGroundBoundConsistent && (!hasVertices || floorSamplesSafe),
        duration_seconds: duration, width: canvas.width, height: canvas.height,
        native_1080p: nativeResolution,
        endpoints_pixel_identical: endpointEqual, endpoint_pixel_delta: endpoints,
        boundary_mean_rgb: brightness, boundary_frame_delta: seam, ordinary_next_frame_delta: forward,
        boundary_jump_suspected: suspectedJump, velocity_epsilon_seconds: epsilon,
        boundary_velocity: velocity, velocities_continuous: velocitiesContinuous,
        sample_hz: sampleHz, samples, rock_count: d.rockBoxes.length, animal_names: names,
        finite_bounds: finite, stable_animal_names: stableNames, creatures_always_visible: visible,
        rewind_deterministic: rewind, rewind_render_pixels_identical: rewindPixelsIdentical,
        rewind_render_pixel_delta: rewindPixelDelta,
        rock_overlap_count: overlaps, first_rock_overlaps: firstOverlaps,
        minimum_rock_distance: minimum, ground_global_maximum: hasGroundMaximum ? groundMaximum : null,
        minimum_global_floor_clearance_bound: minimumGroundBound, floor_safe_by_bound: floorSafeByBound,
        exact_floor_checked_poses: hasVertices ? floorProbeTimes.size : 0, exact_floor_checked_vertices: checkedVertices,
        minimum_exact_analytic_floor_clearance: exactFloor, exact_floor_vertices_finite: exactFloorFinite,
        maximum_observed_ground: hasVertices ? observedGroundMaximum : null,
        declared_ground_bound_consistent: declaredGroundBoundConsistent,
        warnings, antialias: film.antialias, layout: film.layout,
        elapsed_seconds: (performance.now() - started) / 1000,
        limits: 'Discrete time samples; rock checks use conservative world boxes. Global analytic ground bound proves vertical separation at those poses; exact vertex floor checks supplement it once per second and at minimum-bound poses. Boundary velocities use centres of observed boxes, not every vertex.',
      },
      images: [start, end, before, after].map(({ time, png }) => ({ time, png })),
    };
  }, { sampleHz });
  result.report.browser_errors = browserErrors;
  result.report.scene_bundle_sha256 = servedHashes.get('scene.js');
  result.report.passed &&= browserErrors.length === 0;
  const stills = path.join(path.dirname(out), `${path.basename(out, path.extname(out))}-frames`);
  await mkdir(stills, { recursive: true });
  result.report.frames = [];
  for (let i = 0; i < result.images.length; i++) {
    const { time, png } = result.images[i], bytes = Buffer.from(png, 'base64'), file = path.join(stills, `${i}-${time.toFixed(5)}.png`);
    await writeFile(file, bytes);
    result.report.frames.push({ time, file, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') });
  }
  result.report.endpoints_png_identical = result.report.frames[0].sha256 === result.report.frames[1].sha256;
  await writeFile(out, JSON.stringify(result.report, null, 2));
  console.log(JSON.stringify({ report: out, ...result.report }, null, 2));
  if (!result.report.passed) process.exitCode = 1;
} finally {
  try { if (browser) await browser.close(); }
  finally { await new Promise(resolve => server.close(resolve)); }
}
