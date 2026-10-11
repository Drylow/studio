/**
 * Inspect a coded forward-moving 2.5D film, not 3D mesh collisions or artwork.
 * Diagnostics may expose camera/trackLength/worldCounts/creatures directly,
 * or the forward scene's camera object, forward metadata, reef.landmarks and
 * fish/sharks/jellies arrays. Fish halfWidth/halfHeight and reef.clear_corridor
 * permit an independent coordinate/extent corridor check. Screens may use any fixed
 * units; perspective checks compare scale/depth ratios, not image coordinates.
 */
import http from 'node:http';
import { readdir, readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { chromium } from 'playwright';

const here = path.dirname(fileURLToPath(import.meta.url));
const options = { '--dist': path.join(here, 'dist-forward'), '--out': path.join(here, 'renders/forward-loop-check.json'), '--sample-hz': '2', '--min-visible-fish': '1' };
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i += 2) {
  if (!(args[i] in options) || !args[i + 1]) throw new Error('Use --dist, --out, --sample-hz or --min-visible-fish with a value.');
  options[args[i]] = args[i + 1];
}
const dist = path.resolve(options['--dist']), out = path.resolve(options['--out']);
const sampleHz = Number(options['--sample-hz']), minimumFish = Number(options['--min-visible-fish']);
if (!Number.isInteger(sampleHz) || sampleHz < 1 || sampleHz > 30) throw new Error('Sample rate must be between 1 and 30 Hz.');
if (!Number.isInteger(minimumFish) || minimumFish < 0) throw new Error('Minimum visible fish must be a nonnegative integer.');
const mime = new Map([['.html', 'text/html; charset=utf-8'], ['.js', 'application/javascript'], ['.txt', 'text/plain; charset=utf-8'], ['.png', 'image/png'], ['.jpg', 'image/jpeg'], ['.jpeg', 'image/jpeg'], ['.webp', 'image/webp'], ['.avif', 'image/avif'], ['.svg', 'image/svg+xml']]);
const allowed = new Map(), hashes = new Map();
async function collect(relative = '') {
  for (const file of await readdir(path.join(dist, relative), { withFileTypes: true })) {
    const next = path.join(relative, file.name);
    if (file.isDirectory()) await collect(next);
    else if (file.isFile() && mime.has(path.extname(file.name))) allowed.set(`/${next.split(path.sep).join('/')}`, { file: path.join(dist, next), mime: mime.get(path.extname(file.name)), relative: next });
  }
}
await collect();
if (!allowed.has('/index.html') || !allowed.has('/scene.js')) throw new Error('Build the selected film before checking its loop.');
allowed.set('/', allowed.get('/index.html'));
const initialHashes = new Map();
for (const entry of allowed.values()) initialHashes.set(entry.relative, createHash('sha256').update(await readFile(entry.file)).digest('hex'));
const server = http.createServer(async (request, response) => {
  if (!['GET', 'HEAD'].includes(request.method)) { response.writeHead(405); response.end(); return; }
  const pathname = new URL(request.url, 'http://localhost').pathname;
  if (pathname === '/favicon.ico') { response.writeHead(204); response.end(); return; }
  const entry = allowed.get(pathname);
  if (!entry) { response.writeHead(404); response.end(); return; }
  try {
    const bytes = await readFile(entry.file); hashes.set(entry.relative, createHash('sha256').update(bytes).digest('hex'));
    response.writeHead(200, { 'Content-Type': entry.mime, 'Cache-Control': 'no-store' }); response.end(request.method === 'HEAD' ? undefined : bytes);
  } catch { response.writeHead(500); response.end('Selected film asset unavailable.'); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
let browser, blockedExternal = 0;
const browserErrors = [], localHttpErrors = [];
try {
  browser = await chromium.launch({ executablePath: process.env.DEEPSEA_CHROMIUM || '/usr/bin/chromium', headless: true,
    args: ['--disable-dev-shm-usage', '--disable-gpu'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', error => browserErrors.push(error.message));
  page.on('response', response => { if (response.status() >= 400) localHttpErrors.push({ path: new URL(response.url()).pathname, status: response.status() }); });
  await page.route('**/*', route => { if (new URL(route.request().url()).origin === origin) return route.continue(); blockedExternal++; return route.abort(); });
  await page.addInitScript(() => { window.__CAPTURE_MODE__ = true; window.__DEEPSEA_DIAGNOSTICS__ = true; });
  await page.goto(origin, { waitUntil: 'domcontentloaded', timeout: 120000 });
  await page.waitForFunction(() => window.DeepSeaFilm?.diagnostics?.sample, null, { timeout: 120000 });
  await page.evaluate(async () => { if (window.DeepSeaFilm.ready) await window.DeepSeaFilm.ready; });
  const result = await page.evaluate(({ sampleHz, minimumFish }) => {
    const film = window.DeepSeaFilm, diagnostics = film.diagnostics, duration = film.duration, started = performance.now();
    if (!Number.isFinite(duration) || duration <= 0) throw new Error('Film duration must be positive and finite.');
    const vector = value => Array.isArray(value) ? value : [value?.x, value?.y, value?.z];
    const isFish = kind => /fish|shoal|school/i.test(kind) && !/jelly|shark/i.test(kind);
    function sample(time) {
      const raw = diagnostics.sample(time), reef = raw.reef || {};
      const collections = raw.creatures ? [raw.creatures] : ['fish', 'sharks', 'jellies'].map(kind => (raw[kind] || []).map((creature, index) => ({ ...creature, kind: kind === 'jellies' ? 'jelly' : kind === 'sharks' ? 'shark' : 'fish', id: creature.id ?? `${kind}-${index}` })));
      let fishCursor = 0;
      const creatures = collections.flat().map(creature => {
        const screen = creature.screen || [creature.x, creature.y], alpha = typeof creature.visible === 'number' ? creature.visible : creature.alpha;
        const onScreen = Number.isFinite(screen[0]) && Number.isFinite(screen[1]) && screen[0] > 0 && screen[0] < 1 && screen[1] > 0 && screen[1] < 1;
        const separateFish = raw.creatures && isFish(creature.kind) ? raw.fish?.[fishCursor++] : null;
        const world = vector(creature.world), separateWorld = separateFish ? vector(separateFish.world) : null;
        const matchingFish = separateWorld && world.every((value, axis) => Math.abs(value - separateWorld[axis]) < 1e-9) ? separateFish : null;
        return { id: creature.id, kind: creature.kind, world: vector(creature.world), visible: typeof creature.visible === 'boolean' ? creature.visible : alpha > .01 && onScreen,
          halfWidth: creature.halfWidth ?? matchingFish?.halfWidth, halfHeight: creature.halfHeight ?? matchingFish?.halfHeight,
          waterClearance: creature.waterClearance, screen, depth: creature.depth, scale: creature.scale };
      });
      const worldCounts = raw.worldCounts || { reef: reef.total_objects, fish: raw.fish?.length ?? creatures.filter(creature => isFish(creature.kind)).length,
        sharks: raw.sharks?.length ?? creatures.filter(creature => creature.kind === 'shark').length, jellies: raw.jellies?.length ?? creatures.filter(creature => creature.kind === 'jelly').length, marine_snow: film.layout?.marine_snow ?? 0 };
      return { time: raw.time, camera: vector(raw.camera), cameraProgress: raw.cameraProgress, trackLength: raw.trackLength ?? raw.forward?.track_length ?? raw.camera?.trackLength,
        worldCounts, creatures, landmarks: raw.landmarks ?? reef.landmarks,
        waterCorridor: raw.waterCorridor ?? { left: reef.clear_corridor?.[0], right: reef.clear_corridor?.[1], floor: reef.water_floor }, globalZoom: raw.forward?.global_zoom };
    }
    const zero = sample(0), ending = sample(duration);
    const trackLength = zero.trackLength;
    if (!Number.isFinite(trackLength) || trackLength <= 0 || !Number.isFinite(zero.cameraProgress) || !Number.isFinite(ending.cameraProgress)) throw new Error('Forward diagnostics need positive trackLength and unwrapped cameraProgress.');
    const mod = value => ((value % trackLength) + trackLength) % trackLength;
    function canonical(value, key = '') {
      if (Array.isArray(value)) return key === 'camera' || key === 'world' ? value.map((number, axis) => axis === 2 ? mod(number) : number) : value.map(item => canonical(item));
      if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().filter(name => !['time', 'cameraProgress'].includes(name)).map(name => [name, canonical(value[name], name)]));
      return value;
    }
    const endpointDiagnosticsEqual = JSON.stringify(canonical(zero)) === JSON.stringify(canonical(ending));
    const probe = duration * .37, beforeSeek = JSON.stringify(sample(probe)); sample(duration * .88);
    const rewindDiagnosticsEqual = beforeSeek === JSON.stringify(sample(probe));
    const canvas = document.getElementById('film'), copy = document.createElement('canvas'); copy.width = canvas.width; copy.height = canvas.height;
    const context = copy.getContext('2d', { willReadFrequently: true });
    function image(time) { film.render(time); context.clearRect(0, 0, copy.width, copy.height); context.drawImage(canvas, 0, 0); return { time, png: canvas.toDataURL('image/png').split(',')[1], pixels: context.getImageData(0, 0, copy.width, copy.height).data }; }
    function delta(a, b) {
      let sum = 0, max = 0, changed = 0;
      for (let i = 0; i < a.length; i += 4) { let different = false; for (let j = 0; j < 3; j++) { const n = Math.abs(a[i + j] - b[i + j]); sum += n * n; max = Math.max(max, n); different ||= n > 0; } if (different) changed++; }
      return { rms: Math.sqrt(sum / (a.length / 4 * 3)), maximum_channel_difference: max, changed_pixel_fraction: changed / (a.length / 4) };
    }
    const step = Math.min(1 / 30, duration / 4), first = image(0), last = image(duration), before = image(duration - step), after = image(step);
    const endpointDelta = delta(first.pixels, last.pixels), seamDelta = delta(before.pixels, first.pixels), nextDelta = delta(first.pixels, after.pixels);
    const suspectedJump = seamDelta.rms > Math.max(nextDelta.rms * 2.5, nextDelta.rms + 1);
    const probeImage = image(probe); image(duration * .88); const rewindPixelDelta = delta(probeImage.pixels, image(probe).pixels);
    const images = [first, last, before, after, probeImage];
    for (const time of [...new Set([6, 12, 18, 24, 65, 100, 220].filter(time => time < duration))]) images.push(image(time));
    const meanRgb = pixels => { let sum = 0; for (let i = 0; i < pixels.length; i += 4) sum += (pixels[i] + pixels[i + 1] + pixels[i + 2]) / 3; return sum / (pixels.length / 4); };
    const stats = values => { const sorted = [...values].sort((a, b) => a - b); return { minimum: sorted[0], median: sorted[Math.floor(sorted.length / 2)], maximum: sorted.at(-1) }; };
    const rows = [], invalid = [], waterFailures = [], worldCountVariants = new Set();
    const frames = Math.ceil(duration * sampleHz) + 1, direction = Math.sign(ending.cameraProgress - zero.cameraProgress), expectedSpeed = trackLength / duration;
    let lastProgress = null, lastTime = null, monotone = direction !== 0, constantSpeed = true, finite = true, cameraZMatchesProgress = true, landmarkDepthConsistent = true, corridorAvailable = true, checkedFish = 0, minimumWaterMargin = Infinity;
    const finiteTree = value => typeof value === 'number' ? Number.isFinite(value) : Array.isArray(value) ? value.every(finiteTree) : value && typeof value === 'object' ? Object.values(value).every(finiteTree) : true;
    for (let frame = 0; frame < frames; frame++) {
      const time = Math.min(duration, frame / sampleHz), state = sample(time);
      if (!finiteTree(state) || !Array.isArray(state.camera) || state.camera.length !== 3 || !Number.isFinite(state.cameraProgress)) { finite = false; if (invalid.length < 20) invalid.push({ time, reason: 'Non-finite diagnostic or missing camera' }); }
      const expectedCameraZ = mod(zero.camera[2] + state.cameraProgress - zero.cameraProgress);
      cameraZMatchesProgress &&= Math.abs(mod(state.camera[2] - expectedCameraZ + trackLength / 2) - trackLength / 2) < 1e-7;
      if (lastProgress !== null && time > lastTime) {
        const speed = (state.cameraProgress - lastProgress) / (time - lastTime); monotone &&= speed * direction > 0;
        constantSpeed &&= Math.abs(Math.abs(speed) - expectedSpeed) <= Math.max(1e-6, expectedSpeed * .001);
      }
      lastProgress = state.cameraProgress; lastTime = time;
      const counts = state.worldCounts;
      if (!counts || !Object.keys(counts).length || !Object.values(counts).every(count => Number.isInteger(count) && count >= 0)) { finite = false; if (invalid.length < 20) invalid.push({ time, reason: 'Missing or invalid world counts' }); }
      else worldCountVariants.add(JSON.stringify(Object.fromEntries(Object.entries(counts).sort(([a], [b]) => a.localeCompare(b)))));
      if (!Array.isArray(state.creatures) || !Array.isArray(state.landmarks)) throw new Error('Forward diagnostics must return creatures and static landmarks arrays.');
      const landmarkIds = state.landmarks.map(marker => marker.id);
      if (!landmarkIds.length || landmarkIds.some(id => typeof id !== 'string' && typeof id !== 'number') || new Set(landmarkIds).size !== landmarkIds.length) { finite = false; if (invalid.length < 20) invalid.push({ time, reason: 'Missing or duplicated static landmark ids' }); }
      for (const marker of state.landmarks) {
        if (!Array.isArray(marker.world) || marker.world.length !== 3 || !marker.world.every(Number.isFinite) || !Number.isFinite(marker.depth)) { finite = false; continue; }
        landmarkDepthConsistent &&= Math.abs(marker.depth - mod(marker.world[2] - state.camera[2])) < 1e-7;
      }
      let fish = 0, life = 0;
      for (const creature of state.creatures) {
        if (!Array.isArray(creature.world) || creature.world.length !== 3 || !creature.world.every(Number.isFinite) || typeof creature.visible !== 'boolean') finite = false;
        if (isFish(creature.kind)) {
          const corridor = state.waterCorridor;
          if (!(Number.isFinite(creature.halfWidth) && creature.halfWidth >= 0 && Number.isFinite(corridor.left) && Number.isFinite(corridor.right) && corridor.left < corridor.right)) corridorAvailable = false;
          else {
            const margins = [creature.world[0] - creature.halfWidth - corridor.left, corridor.right - creature.world[0] - creature.halfWidth];
            if (Number.isFinite(corridor.floor)) {
              if (!Number.isFinite(creature.halfHeight) || creature.halfHeight < 0) corridorAvailable = false;
              else margins.push(creature.world[1] - creature.halfHeight - corridor.floor);
            }
            const clearance = Math.min(...margins); checkedFish++; minimumWaterMargin = Math.min(minimumWaterMargin, clearance);
            if (clearance < 0 && waterFailures.length < 20) waterFailures.push({ time, id: creature.id, kind: creature.kind, clearance });
          }
        }
        if (creature.visible) { life++; if (isFish(creature.kind)) fish++; }
      }
      rows.push({ time, visible_fish: fish, visible_life: life });
    }
    const perspectivePairs = [], badProjection = [];
    for (const time of [0, 24, duration * .37, duration * .73].filter(time => time + 1 < duration)) {
      const a = sample(time), b = sample(time + 1), second = new Map(b.landmarks.map(marker => [marker.id, marker]));
      for (const marker of a.landmarks) {
        const next = second.get(marker.id);
        if (!marker.visible || !next?.visible) continue;
        if (!Array.isArray(marker.screen) || marker.screen.length !== 2 || !marker.screen.every(Number.isFinite) || !Array.isArray(next.screen) || next.screen.length !== 2 || !next.screen.every(Number.isFinite) || !(marker.scale > 0 && next.scale > 0 && marker.depth > 0 && next.depth > 0)) { badProjection.push({ time, id: marker.id }); continue; }
        if (Math.abs(next.depth - marker.depth) > trackLength / 2) continue; // Recycled world tile, not the same near-to-far pass.
        const staticWorld = marker.world.every((value, axis) => Math.abs(axis === 2 ? mod(value - next.world[axis] + trackLength / 2) - trackLength / 2 : value - next.world[axis]) < 1e-7);
        const expectedDepthChange = -expectedSpeed, depthChange = next.depth - marker.depth, scaleRatio = next.scale / marker.scale, expectedScaleRatio = marker.depth / next.depth;
        perspectivePairs.push({ time, id: marker.id, depth: marker.depth, depth_change: depthChange, scale_ratio: scaleRatio, expected_scale_ratio: expectedScaleRatio,
          consistent_depth: staticWorld && Math.abs(depthChange - expectedDepthChange) <= Math.max(.001, expectedSpeed * .01), consistent_scale: Math.abs(scaleRatio - expectedScaleRatio) <= Math.max(1e-5, expectedScaleRatio * 1e-4),
          screen_displacement: Math.hypot(...next.screen.map((value, axis) => value - marker.screen[axis])) });
      }
    }
    const ordered = [...perspectivePairs].sort((a, b) => a.depth - b.depth), quarter = Math.max(1, Math.floor(ordered.length / 4));
    const near = ordered.slice(0, quarter), far = ordered.slice(-quarter), nearGrowth = near.length ? stats(near.map(row => row.scale_ratio - 1)).median : null, farGrowth = far.length ? stats(far.map(row => row.scale_ratio - 1)).median : null;
    const parallaxProven = perspectivePairs.length >= 4 && perspectivePairs.every(row => row.consistent_depth && row.consistent_scale) && nearGrowth > farGrowth + 1e-4;
    const projectedFish = stats(rows.map(row => row.visible_fish)), trackCompleted = Math.abs(Math.abs(ending.cameraProgress - zero.cameraProgress) - trackLength) <= 1e-6;
    corridorAvailable &&= checkedFish > 0;
    const report = {
      schema: 'deep-sea-forward-loop-v1', passed: finite && endpointDiagnosticsEqual && rewindDiagnosticsEqual && endpointDelta.maximum_channel_difference === 0 && rewindPixelDelta.maximum_channel_difference === 0
        && !suspectedJump && meanRgb(first.pixels) > 2 && canvas.width === 1920 && canvas.height === 1080 && monotone && constantSpeed && trackCompleted
        && cameraZMatchesProgress && landmarkDepthConsistent && zero.globalZoom !== true && parallaxProven && corridorAvailable && waterFailures.length === 0 && projectedFish.minimum >= minimumFish && worldCountVariants.size === 1 && badProjection.length === 0,
      duration_seconds: duration, width: canvas.width, height: canvas.height, sample_hz: sampleHz, samples: frames,
      endpoint_diagnostics_periodic: endpointDiagnosticsEqual, rewind_diagnostics_deterministic: rewindDiagnosticsEqual,
      endpoints_pixels_identical: endpointDelta.maximum_channel_difference === 0, endpoint_pixel_delta: endpointDelta,
      boundary_pixel_delta: seamDelta, ordinary_next_frame_delta: nextDelta, boundary_jump_suspected: suspectedJump,
      rewind_pixels_identical: rewindPixelDelta.maximum_channel_difference === 0, boundary_mean_rgb: meanRgb(first.pixels),
      track_length: trackLength, camera_progress_delta: ending.cameraProgress - zero.cameraProgress, monotone_camera_progress: monotone, constant_forward_speed: constantSpeed,
      expected_forward_speed: expectedSpeed, track_completed: trackCompleted, static_projection_pairs: perspectivePairs.length, perspective_depth_scale_consistent: parallaxProven,
      camera_z_matches_unwrapped_progress: cameraZMatchesProgress, landmark_depth_matches_world_camera: landmarkDepthConsistent, reported_global_zoom: zero.globalZoom ?? null,
      near_median_normalized_scale_growth: nearGrowth, far_median_normalized_scale_growth: farGrowth, projection_examples: [...near.slice(0, 3), ...far.slice(-3)],
      finite_diagnostics: finite, invalid_diagnostics: invalid, invalid_projections: badProjection, world_counts_stable: worldCountVariants.size === 1,
      world_counts: zero.worldCounts, visible_fish: projectedFish, visible_life: stats(rows.map(row => row.visible_life)), minimum_visible_fish_target: minimumFish,
      independent_fish_corridor_check_available: corridorAvailable, checked_fish_poses: checkedFish, minimum_fish_extent_corridor_margin: Number.isFinite(minimumWaterMargin) ? minimumWaterMargin : null, fish_extent_corridor_violations: waterFailures,
      water_corridor: zero.waterCorridor, fish_vertical_corridor_checked: Number.isFinite(zero.waterCorridor?.floor),
      elapsed_seconds: (performance.now() - started) / 1000,
      limits: 'Discrete diagnostics and exact captured pixels. Perspective tests use scene-reported static landmarks and camera progress; this is not 3D collision testing, occlusion proof, continuous-time proof or artwork approval. Fish corridor margins are calculated from reported world positions, sprite half-extents and corridor bounds. No independent painted-rock pixel mask test or shark/jelly collision proof is claimed.',
    };
    return { report, images: images.map(({ time, png }) => ({ time, png })) };
  }, { sampleHz, minimumFish });
  const frames = path.join(path.dirname(out), `${path.basename(out, path.extname(out))}-frames`); await mkdir(frames, { recursive: true });
  result.report.frames = [];
  for (let i = 0; i < result.images.length; i++) {
    const frame = result.images[i], bytes = Buffer.from(frame.png, 'base64'), file = path.join(frames, `${i}-${frame.time.toFixed(5)}.png`);
    await writeFile(file, bytes); result.report.frames.push({ time: frame.time, file, sha256: createHash('sha256').update(bytes).digest('hex') });
  }
  const changedAssets = [];
  for (const [relative, hash] of initialHashes) if (createHash('sha256').update(await readFile(path.join(dist, relative))).digest('hex') !== hash) changedAssets.push(relative);
  result.report.scene_bundle_sha256 = hashes.get('scene.js'); result.report.served_asset_hashes = Object.fromEntries(hashes);
  result.report.browser_errors = browserErrors; result.report.local_http_errors = localHttpErrors; result.report.blocked_external_requests = blockedExternal;
  result.report.assets_changed_during_check = changedAssets;
  result.report.passed &&= browserErrors.length === 0 && localHttpErrors.length === 0 && blockedExternal === 0 && changedAssets.length === 0;
  await writeFile(out, JSON.stringify(result.report, null, 2)); console.log(JSON.stringify({ report: out, ...result.report }, null, 2));
  if (!result.report.passed) process.exitCode = 1;
} finally {
  try { if (browser) await browser.close(); } finally { await new Promise(resolve => server.close(resolve)); }
}
