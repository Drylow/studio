/** Check the actual offline Canvas2D loop without inventing 3D collision proofs. */
import http from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { chromium } from 'playwright';

const here = path.dirname(fileURLToPath(import.meta.url));
const options = {
  '--dist': path.join(here, 'dist-sleep'),
  '--out': path.join(here, 'renders/illustrated-loop-check.json'),
  '--asset': path.join(here, 'assets/nocturnal-reef.png'),
  '--sprite': path.join(here, 'assets/jellyfish-cutout.png'),
};
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i += 2) {
  if (!(args[i] in options) || !args[i + 1]) {
    throw new Error('Usage: node verify-illustrated-loop.mjs [--dist directory] [--out report.json] [--asset source.png] [--sprite cutout.png]');
  }
  options[args[i]] = args[i + 1];
}
const dist = path.resolve(options['--dist']), out = path.resolve(options['--out']);
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const files = new Map();
for (const [file, mime] of [['index.html', 'text/html; charset=utf-8'], ['scene.js', 'application/javascript']]) {
  const bytes = await readFile(path.join(dist, file)); files.set(file, { bytes, mime, sha256: sha(bytes) });
}
const asset = await readFile(path.resolve(options['--asset']));
if (!asset.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) || asset.toString('ascii', 12, 16) !== 'IHDR') {
  throw new Error('The selected background source is not a PNG with an IHDR header.');
}
const assetDimensions = [asset.readUInt32BE(16), asset.readUInt32BE(20)];
const sprite = await readFile(path.resolve(options['--sprite']));
if (!sprite.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) || sprite.toString('ascii', 12, 16) !== 'IHDR') {
  throw new Error('The selected marine sprite is not a PNG with an IHDR header.');
}
const spriteDimensions = [sprite.readUInt32BE(16), sprite.readUInt32BE(20)];
const embeddedPng = [...files.get('scene.js').bytes.toString('utf8').matchAll(/data:image\/png;base64,([A-Za-z0-9+/=]+)/g)]
  .map(match => Buffer.from(match[1], 'base64'));
const embeddedExact = embeddedPng.some(bytes => bytes.equals(asset));
const spriteEmbeddedExact = embeddedPng.some(bytes => bytes.equals(sprite));
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); res.end(); return; }
  const name = url.pathname === '/' ? 'index.html' : url.pathname.slice(1), file = files.get(name);
  if (!file) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Type': file.mime, 'Cache-Control': 'no-store' });
  res.end(req.method === 'HEAD' ? undefined : file.bytes);
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
const browserErrors = [], consoleErrors = [], outsideAttempts = [], failedRequests = [];
try {
  browser = await chromium.launch({
    executablePath: process.env.DEEPSEA_CHROMIUM || '/usr/bin/chromium', headless: true,
    args: ['--disable-dev-shm-usage'],
  });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', error => browserErrors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('requestfailed', request => {
    const url = new URL(request.url()); failedRequests.push({ protocol: url.protocol, host: url.hostname, path: url.pathname });
  });
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === origin) return route.continue();
    outsideAttempts.push({ protocol: url.protocol, host: url.hostname }); return route.abort();
  });
  await page.addInitScript(() => {
    window.__CAPTURE_MODE__ = true;
    window.__ILLUSTRATED_CONTEXT_CALLS__ = [];
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
      if (this.id === 'film') window.__ILLUSTRATED_CONTEXT_CALLS__.push(String(kind));
      return original.call(this, kind, ...args);
    };
  });
  await page.goto(origin, { waitUntil: 'load', timeout: 60000 });
  await page.waitForFunction(() => window.DeepSeaFilm?.diagnostics, null, { timeout: 60000 });
  // Decode the exact sprite bytes in the same browser, independently of the film.
  // Alpha statistics can catch an accidental opaque image card before delivery.
  const spriteAlpha = await page.evaluate(async source => {
    const image = new Image(); image.src = source; await image.decode();
    const canvas = document.createElement('canvas'); canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
    const context = canvas.getContext('2d', { willReadFrequently: true }); context.drawImage(image, 0, 0);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    const total = pixels.length / 4; let zero = 0, partial = 0, opaque = 0, sum = 0;
    for (let i = 3; i < pixels.length; i += 4) {
      const alpha = pixels[i]; sum += alpha;
      if (alpha === 0) zero++; else if (alpha === 255) opaque++; else partial++;
    }
    const alphaAt = (x, y) => pixels[(y * canvas.width + x) * 4 + 3];
    let borderSum = 0, borderCount = 0, borderMax = 0;
    for (let x = 0; x < canvas.width; x++) for (const y of [0, canvas.height - 1]) {
      const alpha = alphaAt(x, y); borderSum += alpha; borderCount++; borderMax = Math.max(borderMax, alpha);
    }
    for (let y = 1; y < canvas.height - 1; y++) for (const x of [0, canvas.width - 1]) {
      const alpha = alphaAt(x, y); borderSum += alpha; borderCount++; borderMax = Math.max(borderMax, alpha);
    }
    const corners = [[0, 0], [canvas.width - 1, 0], [0, canvas.height - 1], [canvas.width - 1, canvas.height - 1]].map(([x, y]) => alphaAt(x, y));
    return { dimensions: [canvas.width, canvas.height], rgba_pixels: total,
      fully_transparent_pixels: zero, partially_transparent_pixels: partial, opaque_pixels: opaque,
      fully_transparent_fraction: zero / total, partially_transparent_fraction: partial / total,
      mean_alpha_byte: sum / total, corner_alpha_bytes: corners,
      border_mean_alpha_byte: borderSum / borderCount, border_maximum_alpha_byte: borderMax,
      transparent_cutout_observed: zero / total > .10 && partial / total > .01 && corners.every(alpha => alpha <= 2),
      limit: 'Measures the original decoded PNG alpha, not semantic object segmentation or every deformed output frame.',
    };
  }, `data:image/png;base64,${sprite.toString('base64')}`);
  const result = await page.evaluate(() => {
    const started = performance.now(), film = window.DeepSeaFilm;
    const canvas = document.getElementById('film'), context = canvas.getContext('2d', { willReadFrequently: true });
    const duration = film.duration, step = 1 / 30;
    if (!Number.isFinite(duration) || duration <= 0 || !(context instanceof CanvasRenderingContext2D)) {
      throw new Error('The loaded film does not expose a finite Canvas2D loop.');
    }
    const finite = value => typeof value === 'number' ? Number.isFinite(value)
      : Array.isArray(value) ? value.every(finite)
      : value && typeof value === 'object' ? Object.values(value).every(finite) : true;
    const withoutTime = ({ time, ...sample }) => sample;
    function image(t, png = false) {
      const render = film.render(t);
      if (!finite(render) || render.time !== t) throw new Error('Non-finite or wrong-time render diagnostics.');
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
      return { time: t, pixels, ...(png ? { png: canvas.toDataURL('image/png').split(',')[1] } : {}) };
    }
    function delta(a, b) {
      let sum = 0, maximum = 0, changed = 0;
      for (let i = 0; i < a.length; i += 4) {
        let different = false;
        for (let k = 0; k < 3; k++) {
          const d = Math.abs(a[i + k] - b[i + k]); sum += d * d; maximum = Math.max(maximum, d); different ||= d !== 0;
        }
        if (different) changed++;
      }
      return { rms: Math.sqrt(sum / (a.length / 4 * 3)), maximum_channel_difference: maximum,
        changed_pixel_fraction: changed / (a.length / 4) };
    }
    const zero = image(0, true), end = image(duration, true);
    const before = image(duration - step, true), after = image(step, true);
    const previous = image(duration - step * 2);
    const endpoints = delta(zero.pixels, end.pixels), boundary = delta(before.pixels, zero.pixels);
    const ordinaryFirst = delta(zero.pixels, after.pixels), ordinaryLast = delta(previous.pixels, before.pixels);
    const ordinaryMax = Math.max(ordinaryFirst.rms, ordinaryLast.rms);
    const jump = boundary.rms > Math.max(ordinaryMax * 2.5, ordinaryMax + .35);
    const probeTime = duration * .37, probe = image(probeTime);
    image(duration * .81);
    const rewind = delta(probe.pixels, image(probeTime).pixels);
    const phaseStart = film.diagnostics.sample(0), phaseEnd = film.diagnostics.sample(duration);
    const diagnosticPeriodic = JSON.stringify(withoutTime(phaseStart)) === JSON.stringify(withoutTime(phaseEnd));
    const diagnosticProbe = JSON.stringify(film.diagnostics.sample(probeTime));
    film.diagnostics.sample(duration * .81);
    const diagnosticRewind = diagnosticProbe === JSON.stringify(film.diagnostics.sample(probeTime));
    let allFinite = true, alphaOpaque = true, minimumVisibleFish = Infinity, maximumVisibleFish = 0;
    let minimumMeanRgb = Infinity, maximumMeanRgb = 0;
    const samples = [];
    for (let i = 0; i <= 12; i++) {
      const t = duration * i / 12, sample = film.diagnostics.sample(t);
      allFinite &&= finite(sample);
      if (!Array.isArray(sample.fish) || !Array.isArray(sample.jellies)) throw new Error('Missing illustrated marine diagnostics.');
      const maskedFish = sample.fish.filter(f => f.visible > .01 && f.x >= 0 && f.x <= 1 && f.y >= 0 && f.y <= 1).length;
      minimumVisibleFish = Math.min(minimumVisibleFish, maskedFish); maximumVisibleFish = Math.max(maximumVisibleFish, maskedFish);
      const frame = image(t); let sumRgb = 0;
      for (let pixel = 0; pixel < frame.pixels.length; pixel += 4) {
        if (frame.pixels[pixel + 3] !== 255) alphaOpaque = false;
        sumRgb += frame.pixels[pixel] + frame.pixels[pixel + 1] + frame.pixels[pixel + 2];
      }
      const meanRgb = sumRgb / (frame.pixels.length / 4 * 3);
      minimumMeanRgb = Math.min(minimumMeanRgb, meanRgb); maximumMeanRgb = Math.max(maximumMeanRgb, meanRgb);
      samples.push({ time: t, phase: sample.phase, masked_fish_centres: maskedFish, jellyfish: sample.jellies.length, mean_rgb: meanRgb });
    }
    const contextCalls = window.__ILLUSTRATED_CONTEXT_CALLS__;
    const only2d = contextCalls.length > 0 && contextCalls.every(kind => kind === '2d');
    const native = canvas.width === 1920 && canvas.height === 1080 && film.width === 1920 && film.height === 1080;
    const movement = delta(zero.pixels, probe.pixels);
    const passed = native && duration === 300 && only2d && endpoints.maximum_channel_difference === 0
      && rewind.maximum_channel_difference === 0 && !jump && allFinite && alphaOpaque && diagnosticPeriodic
      && diagnosticRewind && phaseStart.phase === 0 && phaseEnd.phase === 0 && movement.changed_pixel_fraction > .001
      && minimumMeanRgb > 2 && minimumVisibleFish > 0;
    return {
      report: {
        schema: 'illustrated-loop-check-v1', passed, width: canvas.width, height: canvas.height, duration_seconds: duration,
        native_1080p: native, canvas_2d_only: only2d, canvas_context_types: [...new Set(contextCalls)],
        finite_render_and_diagnostic_samples: allFinite, fully_opaque_canvas: alphaOpaque,
        endpoints_pixel_identical: endpoints.maximum_channel_difference === 0, endpoint_pixel_delta: endpoints,
        boundary_frame_delta: boundary, ordinary_first_frame_delta: ordinaryFirst, ordinary_last_frame_delta: ordinaryLast,
        boundary_jump_suspected: jump, compared_frame_step_seconds: step,
        rewind_render_pixels_identical: rewind.maximum_channel_difference === 0, rewind_render_pixel_delta: rewind,
        diagnostics_periodic_at_endpoints: diagnosticPeriodic, diagnostics_rewind_deterministic: diagnosticRewind,
        endpoint_diagnostic_phases: [phaseStart.phase, phaseEnd.phase], motion_between_start_and_probe: movement,
        sampled_render_poses: samples.length, samples,
        fish_masked_centres_minimum: minimumVisibleFish, fish_masked_centres_maximum: maximumVisibleFish,
        sampled_mean_rgb_minimum: minimumMeanRgb, sampled_mean_rgb_maximum: maximumMeanRgb,
        background_source_dimensions: film.layout.background_source_dimensions, layout: film.layout,
        finished_mp4_review: 'Not performed by this source-loop checker.', user_visual_approval: false,
        geometry_collision_checks: 'Not applicable: this renderer composites 2D paths over a painting, without a 3D solid scene.',
        limitations: '13 rendered poses plus endpoint, rewind and adjacent-frame probes. Fish counts use the programmed 2D visibility envelope, not image segmentation or proof of painted reef occlusion. Full encoded-video decode, audio checks and continuous viewing are separate.',
        elapsed_seconds: (performance.now() - started) / 1000,
      },
      images: [zero, end, before, after].map(({ time, png }) => ({ time, png })),
    };
  });
  const report = result.report;
  report.scene_bundle_sha256 = files.get('scene.js').sha256;
  report.index_html_sha256 = files.get('index.html').sha256;
  report.background_source_file = path.basename(options['--asset']);
  report.background_source_sha256 = sha(asset);
  report.background_source_png_dimensions = assetDimensions;
  report.background_dimensions_match_source = JSON.stringify(report.background_source_dimensions) === JSON.stringify(assetDimensions);
  report.background_embedded_byte_identical = embeddedExact;
  report.original_background_count = 1;
  report.embedded_source_png_count = embeddedPng.length;
  report.marine_sprite_source_file = path.basename(options['--sprite']);
  report.marine_sprite_source_sha256 = sha(sprite);
  report.marine_sprite_source_png_dimensions = spriteDimensions;
  report.marine_sprite_embedded_byte_identical = spriteEmbeddedExact;
  report.marine_sprite_alpha = spriteAlpha;
  report.marine_sprite_dimensions_match_source = JSON.stringify(spriteAlpha.dimensions) === JSON.stringify(spriteDimensions);
  report.browser_errors = browserErrors; report.browser_console_errors = consoleErrors;
  report.outside_network_attempts = outsideAttempts; report.failed_requests = failedRequests;
  report.isolated_offline_assets_work = outsideAttempts.length === 0 && failedRequests.length === 0;
  report.bundle_unchanged_during_check = sha(await readFile(path.join(dist, 'scene.js'))) === report.scene_bundle_sha256;
  report.passed &&= report.background_dimensions_match_source && embeddedExact && report.isolated_offline_assets_work
    && report.bundle_unchanged_during_check && browserErrors.length === 0 && consoleErrors.length === 0
    && spriteEmbeddedExact && report.marine_sprite_dimensions_match_source && spriteAlpha.transparent_cutout_observed;
  const framesDir = path.join(path.dirname(out), `${path.basename(out, path.extname(out))}-frames`);
  await mkdir(framesDir, { recursive: true }); report.frames = [];
  for (let i = 0; i < result.images.length; i++) {
    const { time, png } = result.images[i], bytes = Buffer.from(png, 'base64'), file = `${i}-${time.toFixed(5)}.png`;
    await writeFile(path.join(framesDir, file), bytes);
    report.frames.push({ time, file, bytes: bytes.length, sha256: sha(bytes) });
  }
  report.endpoints_png_identical = report.frames[0].sha256 === report.frames[1].sha256;
  report.passed &&= report.endpoints_png_identical;
  await writeFile(out, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ report: out, passed: report.passed, width: report.width, height: report.height,
    duration_seconds: report.duration_seconds, scene_bundle_sha256: report.scene_bundle_sha256,
    endpoints_png_identical: report.endpoints_png_identical, boundary_rms: report.boundary_frame_delta.rms,
    ordinary_rms: [report.ordinary_first_frame_delta.rms, report.ordinary_last_frame_delta.rms],
    source_background_dimensions: assetDimensions, outside_network_attempts: outsideAttempts.length,
    browser_errors: browserErrors.length + consoleErrors.length, sampled_render_poses: report.sampled_render_poses }, null, 2));
  if (!report.passed) process.exitCode = 1;
} finally {
  try { if (browser) await browser.close(); }
  finally { await new Promise(resolve => server.close(resolve)); }
}
