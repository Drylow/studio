/**
 * Check actual animated marine meshes for surface crossings at discrete poses.
 * This executes the local cinematic scene's placement declarations with its
 * model factories, without WebGL or scenery. Build the same source first.
 * Usage: node verify-sleep-animal-pairs.mjs --sample-hz 2 --out renders/pairs.json
 * A pass is not a proof of containment, self-collision or continuous avoidance.
 */
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import * as THREE from 'three';

const here = path.dirname(fileURLToPath(import.meta.url));
const options = {
  '--source': path.join(here, 'sleep-cinematic-scene.mjs'), '--dist': path.join(here, 'dist-sleep'),
  '--out': path.join(here, 'renders/sleep-animal-pairs.json'), '--sample-hz': '2', '--cell-size': '.7',
};
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i += 2) {
  if (!(args[i] in options) || !args[i + 1]) throw new Error('Use --source, --dist, --out, --sample-hz or --cell-size with a value.');
  options[args[i]] = args[i + 1];
}
const sourcePath = path.resolve(options['--source']), dist = path.resolve(options['--dist']), out = path.resolve(options['--out']);
const sampleHz = Number(options['--sample-hz']), cell = Number(options['--cell-size']);
if (!Number.isInteger(sampleHz) || sampleHz < 1 || sampleHz > 30) throw new Error('Sample rate must be an integer between 1 and 30.');
if (!Number.isFinite(cell) || cell < .1 || cell > 10) throw new Error('Grid cell size must be between 0.1 and 10 metres.');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const source = await readFile(sourcePath, 'utf8'), sourceHashes = { [sourcePath]: sha(source) };
const bundlePath = path.join(dist, 'scene.js'), bundleHash = sha(await readFile(bundlePath));
const duration = Number(source.match(/\bDURATION\s*=\s*(\d+(?:\.\d+)?)/)?.[1]);
if (!Number.isFinite(duration) || duration <= 0) throw new Error('The scene must declare a positive numeric DURATION.');
const groundMaximumMatch = source.match(/groundMaximum\s*:\s*([+-]?\d+(?:\.\d+)?)/);
const groundMaximum = groundMaximumMatch ? Number(groundMaximumMatch[1]) : null;
const factories = {};
for (const name of ['createSleepShoals', 'createSleepSharks', 'createSleepJellies']) {
  const specifier = source.match(new RegExp(`import\\s*\\{\\s*${name}\\s*\\}\\s*from\\s*['\"]([^'\"]+)['\"]`))?.[1];
  if (!specifier?.startsWith('./')) throw new Error(`The scene must import ${name} from a local relative module.`);
  const modulePath = path.resolve(path.dirname(sourcePath), specifier);
  sourceHashes[modulePath] = sha(await readFile(modulePath));
  const module = await import(pathToFileURL(modulePath).href);
  factories[name] = module[name];
  if (typeof factories[name] !== 'function') throw new Error(`The local module must export the function ${name}.`);
}
const TAU = Math.PI * 2, phaseExpression = source.match(/const\s+phase\s*=\s*([^;]+);/)?.[1];
if (!phaseExpression) throw new Error('Expected the scene-local phase expression.');
const phase = new Function('TAU', 'DURATION', `return (${phaseExpression});`)(TAU, duration);
const shoals = factories.createSleepShoals(THREE, { duration });
const sharks = factories.createSleepSharks(THREE, { duration });
const jellies = factories.createSleepJellies(THREE, { duration });
const roots = { ...shoals.roots, ...sharks.roots, ...jellies.roots }, names = Object.keys(roots);
const expectedNames = [...Array.from({ length: 12 }, (_, i) => `shoal${String(i + 1).padStart(2, '0')}`), 'shark1', 'shark2', 'shark3', 'jellyA', 'jellyB', 'jellyC'];
if (names.length !== expectedNames.length || !expectedNames.every(name => roots[name]?.isObject3D)) throw new Error('Expected the 18 cinematic animal roots; update the verifier when the scene root contract changes.');
const start = source.indexOf('function faceTangent'), end = source.indexOf('placeAnimals(0);', start);
const declarations = source.slice(start, end);
if (start < 0 || end < start || !declarations.includes('function placeAnimals')) throw new Error('Expected local placement declarations were not found; update this verifier when scene structure changes.');
const placeAnimals = new Function('THREE', 'shoals', 'sharks', 'jellies', 'roots', 'phase', 'TAU', 'DURATION', `${declarations}\nreturn placeAnimals;`)(THREE, shoals, sharks, jellies, roots, phase, TAU, duration);
function poseHash(time) {
  placeAnimals(time); const hash = createHash('sha256');
  for (const root of Object.values(roots)) {
    root.updateWorldMatrix(true, true);
    root.traverse(mesh => {
      if (!mesh.isMesh) return;
      hash.update(JSON.stringify(mesh.matrixWorld.elements));
      const array = mesh.geometry.attributes.position.array;
      hash.update(Buffer.from(array.buffer, array.byteOffset, array.byteLength));
    });
  }
  return hash.digest('hex');
}
const endpointsIdentical = poseHash(0) === poseHash(duration), probe = duration * .37, beforeSeek = poseHash(probe);
poseHash(duration * .88);
const rewindDeterministic = beforeSeek === poseHash(probe);
const overlaps = [], floorByRoot = {}, invalid = [], started = performance.now();
const frames = Math.ceil(duration * sampleHz) + 1;
for (let frame = 0; frame < frames; frame++) {
  const time = Math.min(duration, frame / sampleHz); placeAnimals(time); const bounds = {};
  for (const [name, root] of Object.entries(roots)) {
    root.updateWorldMatrix(true, true); const box = new THREE.Box3().setFromObject(root, true); bounds[name] = box;
    if (box.isEmpty() || ![...box.min.toArray(), ...box.max.toArray()].every(Number.isFinite)) { if (invalid.length < 20) invalid.push({ time, root: name, reason: 'Empty or non-finite animated bounds' }); }
    if (groundMaximum !== null) {
      const gap = box.min.y - groundMaximum;
      if (!floorByRoot[name] || gap < floorByRoot[name].minimum_conservative_gap) floorByRoot[name] = { minimum_conservative_gap: gap, time };
    }
  }
  for (let a = 0; a < names.length; a++) for (let b = a + 1; b < names.length; b++) if (bounds[names[a]].intersectsBox(bounds[names[b]])) overlaps.push({ time, pair: [names[a], names[b]] });
}
if (invalid.length) throw new Error(`Non-finite or empty geometry at sampled poses: ${JSON.stringify(invalid)}`);
const broad = {};
for (const row of overlaps) { const key = row.pair.join('/'); broad[key] ??= { start: row.time, end: row.time, poses: 0 }; broad[key].end = row.time; broad[key].poses++; }
console.log(JSON.stringify({ phase: 'Broad bounds complete', elapsed_seconds: (performance.now() - started) / 1000, overlapping_pairs: Object.keys(broad).length, overlapping_poses: overlaps.length }));
const ray = new THREE.Ray(), hit = new THREE.Vector3(), direction = new THREE.Vector3();
function triangles(root) {
  const result = []; root.updateWorldMatrix(true, true);
  root.traverse(mesh => {
    if (!mesh.isMesh) return;
    const geometry = mesh.geometry, positions = geometry.attributes.position, indices = geometry.index, world = [];
    for (let i = 0; i < positions.count; i++) world.push(new THREE.Vector3().fromBufferAttribute(positions, i).applyMatrix4(mesh.matrixWorld));
    const count = indices?.count ?? positions.count;
    for (let i = 0; i < count; i += 3) {
      const triangle = new THREE.Triangle(...[0, 1, 2].map(offset => world[indices ? indices.getX(i + offset) : i + offset]));
      result.push({ triangle, box: new THREE.Box3().setFromPoints([triangle.a, triangle.b, triangle.c]), mesh: mesh.name, index: i / 3 });
    }
  });
  return result;
}
function segmentTriangle(a, b, triangle) {
  direction.subVectors(b, a); const length = direction.length(); if (length < 1e-10) return null;
  ray.origin.copy(a); ray.direction.copy(direction).divideScalar(length);
  if (!ray.intersectTriangle(triangle.a, triangle.b, triangle.c, false, hit)) return null;
  return hit.distanceTo(a) <= length + 1e-8 ? hit.clone() : null;
}
function keys(box) {
  const result = [];
  for (let x = Math.floor(box.min.x / cell); x <= Math.floor(box.max.x / cell); x++) for (let y = Math.floor(box.min.y / cell); y <= Math.floor(box.max.y / cell); y++) for (let z = Math.floor(box.min.z / cell); z <= Math.floor(box.max.z / cell); z++) result.push(`${x},${y},${z}`);
  return result;
}
function intersect(a, b) {
  const grid = new Map();
  for (let i = 0; i < a.length; i++) for (const key of keys(a[i].box)) { if (!grid.has(key)) grid.set(key, []); grid.get(key).push(i); }
  for (const bb of b) {
    const candidates = new Set(); for (const key of keys(bb.box)) for (const index of grid.get(key) || []) candidates.add(index);
    for (const index of candidates) {
      const aa = a[index]; if (!aa.box.intersectsBox(bb.box)) continue;
      const at = aa.triangle, bt = bb.triangle;
      for (const [u, v] of [[at.a, at.b], [at.b, at.c], [at.c, at.a]]) { const point = segmentTriangle(u, v, bt); if (point) return { point: point.toArray(), meshA: aa.mesh, meshB: bb.mesh, triangleA: aa.index, triangleB: bb.index }; }
      for (const [u, v] of [[bt.a, bt.b], [bt.b, bt.c], [bt.c, bt.a]]) { const point = segmentTriangle(u, v, at); if (point) return { point: point.toArray(), meshA: aa.mesh, meshB: bb.mesh, triangleA: aa.index, triangleB: bb.index }; }
    }
  }
  return null;
}
const crossings = [], crossedPairs = new Set(); let tested = 0, cachedTime = null, cachedTriangles = new Map();
for (const row of overlaps) {
  const key = row.pair.join('/'); if (crossedPairs.has(key)) continue;
  if (row.time !== cachedTime) { placeAnimals(row.time); cachedTime = row.time; cachedTriangles = new Map(); }
  for (const name of row.pair) if (!cachedTriangles.has(name)) cachedTriangles.set(name, triangles(roots[name]));
  const result = intersect(cachedTriangles.get(row.pair[0]), cachedTriangles.get(row.pair[1])); tested++;
  if (result) { crossings.push({ ...row, ...result }); crossedPairs.add(key); console.log(JSON.stringify({ actual_mesh_crossing: crossings.at(-1) })); }
  if (tested % 100 === 0) console.log(JSON.stringify({ triangle_pairs_tested: tested, elapsed_seconds: (performance.now() - started) / 1000 }));
}
if (sha(await readFile(bundlePath)) !== bundleHash) throw new Error('Bundle changed during the animal-pair check.');
for (const [name, hash] of Object.entries(sourceHashes)) if (sha(await readFile(name)) !== hash) throw new Error(`Source changed during the animal-pair check: ${name}`);
const report = {
  schema: 'deep-sea-sleep-animal-pairs-v1', passed: crossings.length === 0 && endpointsIdentical && rewindDeterministic,
  scene_bundle_sha256: bundleHash, source_hashes: Object.fromEntries(Object.entries(sourceHashes).map(([name, hash]) => [path.relative(path.dirname(sourcePath), name), hash])),
  duration_seconds: duration, sample_hz: sampleHz, poses: frames, named_roots: names,
  endpoints_geometry_identical: endpointsIdentical, geometry_seek_deterministic: rewindDeterministic,
  method: 'Local scene placement declarations with the actual animated indexed/non-indexed model vertices; pair AABB broad phase and spatially indexed segment/triangle narrow phase.',
  limits: 'Discrete poses only. No exhaustive containment, coplanar surface, internal shoal self-intersection or continuous-time proof. Pair boxes are candidates, not physical crossings. Bundle and source hashes identify this check but do not independently prove that the existing build corresponds to these source files.',
  broad_phase: broad, first_triangle_crossing_by_pair: crossings, total_broad_overlaps: overlaps.length,
  narrow_phase_poses: tested, grid_cell_size_metres: cell, elapsed_seconds: (performance.now() - started) / 1000,
  ground_maximum: groundMaximum, conservative_floor_by_root: floorByRoot,
  conservative_floor_clearance_proven: groundMaximum === null ? null : Object.values(floorByRoot).every(root => root.minimum_conservative_gap > 0),
  floor_note: 'Animated mesh minimum Y compared with the scene-declared global ground maximum. Positive gaps prove clearance at sampled poses; nonpositive gaps are inconclusive and need the local ground/vertices checker.',
};
await mkdir(path.dirname(out), { recursive: true }); await writeFile(out, JSON.stringify(report, null, 2));
console.log(JSON.stringify({ report: out, ...report }, null, 2));
if (!report.passed) process.exitCode = 1;
