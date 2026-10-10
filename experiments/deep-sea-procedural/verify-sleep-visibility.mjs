/** Measure camera coverage estimates; bounding boxes do not judge artwork. */
import http from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { chromium } from 'playwright';

const here = path.dirname(fileURLToPath(import.meta.url));
const options = {
  '--dist': path.join(here, 'dist-sleep'), '--out': path.join(here, 'renders/sleep-visibility.json'),
  '--sample-hz': '2', '--min-fish-groups': '2', '--min-projected-individuals': '35',
  '--min-projected-area': '.005', '--min-group-area': '.00005',
};
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i += 2) {
  if (!(args[i] in options) || !args[i + 1]) throw new Error('Unknown or incomplete option; use --dist, --out, --sample-hz or coverage thresholds.');
  options[args[i]] = args[i + 1];
}
const dist = path.resolve(options['--dist']), out = path.resolve(options['--out']);
const sampleHz = Number(options['--sample-hz']);
const thresholds = {
  fish_groups: Number(options['--min-fish-groups']), projected_individuals: Number(options['--min-projected-individuals']),
  projected_area_fraction: Number(options['--min-projected-area']), group_area_fraction: Number(options['--min-group-area']),
};
if (!Number.isInteger(sampleHz) || sampleHz < 1 || sampleHz > 10) throw new Error('Sample rate must be an integer between 1 and 10.');
if (![thresholds.fish_groups, thresholds.projected_individuals].every(n => Number.isInteger(n) && n >= 0)
  || ![thresholds.projected_area_fraction, thresholds.group_area_fraction].every(n => Number.isFinite(n) && n >= 0 && n <= 1)) {
  throw new Error('Coverage count thresholds must be nonnegative integers; areas must be between zero and one.');
}
const files = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/index.html', ['index.html', 'text/html; charset=utf-8']],
  ['/scene.js', ['scene.js', 'application/javascript']],
  ['/THREE-LICENSE.txt', ['THREE-LICENSE.txt', 'text/plain; charset=utf-8']],
]);
const hashes = new Map();
const server = http.createServer(async (req, res) => {
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); res.end(); return; }
  const file = files.get(new URL(req.url, 'http://localhost').pathname);
  if (!file) { res.writeHead(404); res.end(); return; }
  try {
    const bytes = await readFile(path.join(dist, file[0]));
    hashes.set(file[0], createHash('sha256').update(bytes).digest('hex'));
    res.writeHead(200, { 'Content-Type': file[1], 'Cache-Control': 'no-store' });
    res.end(req.method === 'HEAD' ? undefined : bytes);
  } catch { res.writeHead(500); res.end('Build the selected film before checking camera coverage.'); }
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
  page.on('console', message => { const text = message.text(); if (text.startsWith('COVERAGE_CHECK ')) console.log(text); });
  await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
  await page.addInitScript(() => { window.__CAPTURE_MODE__ = true; window.__DEEPSEA_DIAGNOSTICS__ = true; });
  await page.goto(origin, { timeout: 120000 });
  await page.waitForFunction(() => window.DeepSeaFilm?.diagnostics?.screenCoverage, null, { timeout: 120000 });
  const report = await page.evaluate(({ sampleHz, thresholds }) => {
    const started = performance.now(), film = window.DeepSeaFilm, coverage = time => film.diagnostics.screenCoverage(time);
    const duration = film.duration;
    if (!Number.isFinite(duration) || duration <= 0) throw new Error('Film duration must be positive and finite.');
    const normalize = sample => ({
      camera: sample.camera,
      groups: [...sample.groups].sort((a, b) => a.name.localeCompare(b.name)).map(group => ({
        name: group.name, kind: group.kind, visible: group.visible, visibleAreaFraction: group.visibleAreaFraction,
        distance: group.distance, individuals: group.individuals, visibleIndividuals: group.visibleIndividuals,
        countMethod: group.countMethod, centerVisible: group.centerVisible, projection: group.projection,
      })),
    });
    const first = coverage(0), last = coverage(duration);
    if (!Array.isArray(first.groups) || !first.groups.length) throw new Error('No named camera-coverage groups were returned.');
    const names = first.groups.map(group => group.name).sort();
    const endpointsIdentical = JSON.stringify(normalize(first)) === JSON.stringify(normalize(last));
    const probe = duration * .37, originalProbe = JSON.stringify(normalize(coverage(probe)));
    coverage(duration * .88);
    const rewind = originalProbe === JSON.stringify(normalize(coverage(probe)));
    const rows = [], byGroup = {}, methods = new Set(), bad = [], insufficient = [];
    const frames = Math.ceil(duration * sampleHz) + 1;
    let valid = true, stableNames = true, individualCountsAvailable = false, individualCountsComplete = true;
    function invalid(time, name, reason) { valid = false; if (bad.length < 20) bad.push({ time, name, reason }); }
    const isFish = kind => /fish|shoal|school/i.test(kind) && !/jelly|shark/i.test(kind);
    for (let frame = 0; frame < frames; frame++) {
      const time = Math.min(duration, frame / sampleHz), sample = coverage(time);
      if (!Array.isArray(sample.camera) || sample.camera.length !== 3 || !sample.camera.every(Number.isFinite)) invalid(time, 'camera', 'non-finite position');
      if (!Array.isArray(sample.groups)) throw new Error('Camera coverage must return a groups array.');
      const currentNames = sample.groups.map(group => group.name).sort();
      if (new Set(currentNames).size !== currentNames.length || JSON.stringify(currentNames) !== JSON.stringify(names)) stableNames = false;
      let visibleGroups = 0, fishGroups = 0, fishIndividuals = 0, visibleIndividuals = 0, areaSum = 0, fishAreaSum = 0;
      const kinds = {};
      for (const group of sample.groups) {
        if (typeof group.name !== 'string' || !group.name || typeof group.kind !== 'string') { invalid(time, String(group.name), 'missing name or kind'); continue; }
        if (typeof group.visible !== 'boolean') invalid(time, group.name, 'visibility is not boolean');
        if (!Number.isFinite(group.visibleAreaFraction) || group.visibleAreaFraction < 0 || group.visibleAreaFraction > 1) invalid(time, group.name, 'area outside zero-to-one range');
        if (!Number.isFinite(group.distance) || group.distance < 0) invalid(time, group.name, 'non-finite or negative distance');
        if (!Number.isInteger(group.individuals) || group.individuals < 1) invalid(time, group.name, 'invalid total individual count');
        const countAvailable = Number.isInteger(group.visibleIndividuals) && group.visibleIndividuals >= 0 && group.visibleIndividuals <= group.individuals;
        if (group.visibleIndividuals !== undefined && !countAvailable) invalid(time, group.name, 'invalid projected individual count');
        if (isFish(group.kind)) { if (countAvailable) individualCountsAvailable = true; else individualCountsComplete = false; }
        if (group.projection !== undefined && (!Array.isArray(group.projection) || !group.projection.every(Number.isFinite))) invalid(time, group.name, 'non-finite centre projection');
        if (group.centerVisible !== undefined && typeof group.centerVisible !== 'boolean') invalid(time, group.name, 'invalid centre visibility');
        if (group.countMethod) methods.add(group.countMethod);
        byGroup[group.name] ??= { kind: group.kind, individuals: group.individuals, visible_samples: 0, minimum_area_fraction: Infinity, maximum_area_fraction: 0, minimum_distance: Infinity, maximum_distance: 0, minimum_projected_individuals: Infinity, maximum_projected_individuals: 0 };
        const stats = byGroup[group.name];
        stats.minimum_area_fraction = Math.min(stats.minimum_area_fraction, group.visibleAreaFraction);
        stats.maximum_area_fraction = Math.max(stats.maximum_area_fraction, group.visibleAreaFraction);
        stats.minimum_distance = Math.min(stats.minimum_distance, group.distance);
        stats.maximum_distance = Math.max(stats.maximum_distance, group.distance);
        if (countAvailable) { stats.minimum_projected_individuals = Math.min(stats.minimum_projected_individuals, group.visibleIndividuals); stats.maximum_projected_individuals = Math.max(stats.maximum_projected_individuals, group.visibleIndividuals); }
        // Ignore tiny clipped boxes while retaining them in the per-group stats.
        const counted = group.visible && group.visibleAreaFraction >= thresholds.group_area_fraction;
        if (!counted) continue;
        visibleGroups++; stats.visible_samples++; kinds[group.kind] = (kinds[group.kind] || 0) + 1;
        areaSum += group.visibleAreaFraction;
        if (countAvailable) visibleIndividuals += group.visibleIndividuals;
        if (isFish(group.kind)) { fishGroups++; fishAreaSum += group.visibleAreaFraction; if (countAvailable) fishIndividuals += group.visibleIndividuals; }
      }
      const row = { time, groups: visibleGroups, fish_groups: fishGroups, projected_individuals: visibleIndividuals, projected_fish_individuals: fishIndividuals, projected_area_sum: areaSum, fish_projected_area_sum: fishAreaSum, kinds };
      rows.push(row);
      if (fishGroups < thresholds.fish_groups || fishAreaSum < thresholds.projected_area_fraction || fishIndividuals < thresholds.projected_individuals) insufficient.push(row);
      if (frame % 150 === 0 || frame === frames - 1) console.info(`COVERAGE_CHECK ${JSON.stringify({ pose: frame + 1, samples: frames, time_seconds: time, fish_groups: fishGroups, projected_fish_centres: fishIndividuals })}`);
    }
    const distribution = values => {
      const sorted = [...values].sort((a, b) => a - b), at = q => sorted[Math.floor(q * (sorted.length - 1))];
      return { minimum: sorted[0], p10: at(.1), median: at(.5), p90: at(.9), maximum: sorted.at(-1), mean: sorted.reduce((sum, value) => sum + value, 0) / sorted.length };
    };
    const empty = rows.filter(row => row.fish_groups === 0), runs = [];
    for (const row of insufficient) {
      const previous = runs.at(-1);
      if (previous && row.time - previous.end <= 1 / sampleHz + 1e-8) { previous.end = row.time; previous.samples++; }
      else runs.push({ start: row.time, end: row.time, samples: 1 });
    }
    for (const stats of Object.values(byGroup)) {
      stats.visible_sample_fraction = stats.visible_samples / frames;
      if (stats.minimum_projected_individuals === Infinity) stats.minimum_projected_individuals = null;
    }
    const targetsPassed = insufficient.length === 0 && (thresholds.projected_individuals === 0 || individualCountsAvailable);
    return {
      schema: 'deep-sea-sleep-visibility-check-v1',
      passed: valid && stableNames && endpointsIdentical && rewind && targetsPassed,
      duration_seconds: duration, sample_hz: sampleHz, samples: frames, groups_in_scene: names.length,
      finite_valid_estimates: valid, stable_group_names: stableNames, endpoint_estimates_identical: endpointsIdentical,
      rewind_estimates_deterministic: rewind, configured_thresholds: thresholds, coverage_targets_passed: targetsPassed,
      projected_individual_counts_available: individualCountsAvailable, projected_individual_counts_complete: individualCountsComplete,
      projected_individual_metric: 'Projected fish centres in groups exposing visibleIndividuals; groups without individual counts are excluded, so this is a lower bound.', count_methods: [...methods],
      visible_group_distribution: distribution(rows.map(row => row.groups)),
      visible_fish_group_distribution: distribution(rows.map(row => row.fish_groups)),
      projected_fish_individual_distribution: individualCountsAvailable ? distribution(rows.map(row => row.projected_fish_individuals)) : null,
      projected_area_sum_distribution: distribution(rows.map(row => row.projected_area_sum)),
      fish_projected_area_sum_distribution: distribution(rows.map(row => row.fish_projected_area_sum)),
      zero_fish_group_samples: empty.length, first_zero_fish_group_times: empty.slice(0, 20).map(row => row.time),
      insufficient_coverage_samples: insufficient.length, insufficient_coverage_runs: runs,
      worst_samples: [...rows].sort((a, b) => a.fish_groups - b.fish_groups || a.projected_fish_individuals - b.projected_fish_individuals || a.fish_projected_area_sum - b.fish_projected_area_sum).slice(0, 12),
      per_group: byGroup, invalid_estimates: bad, elapsed_seconds: (performance.now() - started) / 1000,
      limits: 'Camera projection estimates, not a test of artwork quality or visible pixels. Summed boxes overlap and are not a screen union; projected centres can be occluded, tiny or dark. Groups without individual counts are excluded from individual totals. Discrete poses do not prove continuous coverage between samples. No collision test is performed here.',
    };
  }, { sampleHz, thresholds });
  report.browser_errors = browserErrors;
  report.scene_bundle_sha256 = hashes.get('scene.js');
  report.passed &&= browserErrors.length === 0;
  await mkdir(path.dirname(out), { recursive: true });
  await writeFile(out, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ report: out, ...report }, null, 2));
  if (!report.passed) process.exitCode = 1;
} finally {
  try { if (browser) await browser.close(); }
  finally { await new Promise(resolve => server.close(resolve)); }
}
