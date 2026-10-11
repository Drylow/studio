// Original, deterministic Canvas2D reef projected from a looping world corridor.
// Optional textures are local crops of the existing original reef painting;
// fallback rocks/plants and sediment are drawn in code, with no network calls.
const TAU = Math.PI * 2;
const TRACK = 600;
const clamp = (x, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, x));
const smooth = (lo, hi, x) => { const q = clamp((x - lo) / (hi - lo)); return q * q * (3 - 2 * q); };
const mod = (x, n) => ((x % n) + n) % n;
const randomFor = seed => { let s = seed >>> 0; return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296); };
let active;

/** Initialise a stable reef. Its painted bounds leave world x=[-6,6] open. */
export function makeReef(seed = 713509, sourceImage = null) {
  const random = randomFor(seed);
  const nodes = [];
  // Independent shorelines: each irregular cluster contains different-size
  // shelves, fans and low rubble. Never duplicate a station across both sides.
  const add = (side, z, width, height, inner, kind, sprite) => {
    const contact = sourceImage ? .06 : 24 / (kind === 'pebbles' ? 220 : 620);
    nodes.push({ x: side * (inner + width / 2), y: -5.55 - height * contact,
      z: mod(z, TRACK), width, height, kind, sprite, mirror: random() > .5,
      phase: random() * TAU, opacity: .78 + random() * .19 });
  };
  for (const side of [-1, 1]) {
    const clusters = side < 0 ? 31 : 29;
    const sideOffset = random() * TRACK;
    for (let cluster = 0; cluster < clusters; cluster++) {
      const z = sideOffset + cluster * TRACK / clusters + (random() - .5) * 17;
      const shore = 6.7 + random() * 3.9;
      const count = 2 + Math.floor(random() * 3);
      for (let member = 0; member < count; member++) {
        const sprite = Math.floor(random() * 64), form = sprite % 4;
        const width = form === 2 ? 3.4 + random() * 5.4 : 3.0 + random() * 4.9;
        const height = form === 2 ? 2.3 + random() * 2.8 : 4.5 + random() * 4.3;
        add(side, z + (random() - .5) * 18, width, height,
          shore + (member ? random() * 5.4 : 0), 'reef', sprite);
      }
      if (random() < .70) {
        const width = 7.5 + random() * 6.0;
        add(side, z + 5 + random() * 11, width, 6.8 + random() * 5.3,
          15.0 + random() * 8.0, 'wall', Math.floor(random() * 32));
      }
      const width = 1.0 + random() * 2.5;
      add(side, z - 7 + random() * 19, width, .65 + random() * 1.2,
        6.65 + random() * 9.0, 'pebbles', Math.floor(random() * 12));
    }
  }
  if (sourceImage) {
    // Sand-coloured picture fragments read as floating islands. World-space
    // sediment already supplies little ground stones without those cutouts.
    for (let i = nodes.length - 1; i >= 0; i--) if (nodes[i].kind === 'pebbles') nodes.splice(i, 1);
  }
  nodes.forEach((node, id) => { node.id = id; });
  const sediment = Array.from({ length: 900 }, () => ({
    x: (random() - .5) * 78, z: random() * TRACK, radius: .04 + random() * .12,
    light: random() > .56, phase: random() * TAU,
  }));
  if (sourceImage && !(sourceImage.naturalWidth > 0 && sourceImage.naturalHeight > 0)) {
    throw new TypeError('The optional reef painting must be an already decoded Image.');
  }
  active = { seed: seed >>> 0, trackLength: TRACK, nodes, sediment, sourceImage, sprites: new Map() };
  return { seed: active.seed, trackLength: TRACK, objects: nodes.length,
    corridor: [-6, 6], generation: sourceImage ? 'Soft rock/coral cutouts from the existing original painting, projected in a world corridor' : 'Deterministic hand-coded Canvas2D rock and coral textures' };
}

function surface(w, h) {
  const canvas = typeof OffscreenCanvas !== 'undefined' ? new OffscreenCanvas(w, h) : document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  return { canvas, ctx: canvas.getContext('2d', { willReadFrequently: true }) };
}

function rockShape(ctx, random, x, y, w, h, bright = false) {
  const light = ctx.createLinearGradient(x - w / 2, y - h, x + w / 2, y + h * .16);
  light.addColorStop(0, bright ? '#4b6970' : '#334f58');
  light.addColorStop(.33, bright ? '#23424c' : '#193540');
  light.addColorStop(1, '#081c2a');
  ctx.fillStyle = light; ctx.beginPath();
  ctx.moveTo(x - w * .50, y);
  ctx.bezierCurveTo(x - w * .57, y - h * .37, x - w * .46, y - h * .58, x - w * .30, y - h * .68);
  ctx.bezierCurveTo(x - w * .20, y - h * .88, x - w * .08, y - h * (1 + random() * .08), x + w * .07, y - h * .96);
  ctx.bezierCurveTo(x + w * .34, y - h * .97, x + w * .50, y - h * .70, x + w * .49, y - h * .47);
  ctx.bezierCurveTo(x + w * .63, y - h * .31, x + w * .53, y - h * .06, x + w * .45, y);
  ctx.quadraticCurveTo(x, y + h * .12, x - w * .50, y);
  ctx.closePath(); ctx.fill();
  ctx.save(); ctx.clip();
  // Curved sediment strata and small fissures, never large faceted polygons.
  for (let k = 0; k < 20; k++) {
    const yy = y - h * (.12 + k * .040);
    ctx.strokeStyle = k % 3 ? 'rgba(106,143,141,.18)' : 'rgba(8,28,39,.40)';
    ctx.lineWidth = .6 + random() * 1.3;
    ctx.beginPath(); ctx.moveTo(x - w * .7, yy + random() * 9);
    ctx.bezierCurveTo(x - w * .15, yy - 9, x + w * .08, yy + 13, x + w * .62, yy - random() * 10); ctx.stroke();
  }
  for (let k = 0; k < 130; k++) {
    const xx = x + (random() - .5) * w, yy = y - random() * h;
    ctx.fillStyle = k % 5 ? 'rgba(121,156,146,.20)' : 'rgba(7,24,34,.42)';
    ctx.beginPath(); ctx.ellipse(xx, yy, .7 + random() * 2.9, .5 + random() * 1.4, -.22, 0, TAU); ctx.fill();
  }
  ctx.restore();
}

function branchingCoral(ctx, random, x, y, height, width, phase, fan = false) {
  ctx.strokeStyle = fan ? 'rgba(84,117,122,.77)' : 'rgba(78,118,109,.90)';
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  const arms = fan ? 12 : 9;
  for (let j = 0; j < arms; j++) {
    const s = j / (arms - 1), dx = (s - .5) * width;
    const top = y - height * (.58 + .40 * Math.sin(s * Math.PI));
    const mx = x + dx * .38 + 3 * Math.sin(phase + j);
    ctx.lineWidth = fan ? .8 : 1.2 + random() * .8;
    ctx.beginPath(); ctx.moveTo(x, y);
    ctx.bezierCurveTo(x + dx * .04, y - height * .30, mx, top + height * .21, x + dx, top); ctx.stroke();
    for (let k = 1; k <= 5; k++) {
      const u = k / 6, px = x + dx * u * u, py = y + (top - y) * u;
      const twig = height * .13 * (1 - u * .48);
      ctx.lineWidth = .65 + .65 * (1 - u);
      for (const sign of [-1, 1]) {
        ctx.beginPath(); ctx.moveTo(px, py);
        ctx.quadraticCurveTo(px + sign * twig * .45, py - twig * .16, px + sign * twig, py - twig * .72); ctx.stroke();
        if (!fan) {
          ctx.fillStyle = 'rgba(147,169,148,.34)';
          ctx.beginPath(); ctx.arc(px + sign * twig, py - twig * .72, 1.3, 0, TAU); ctx.fill();
        }
      }
    }
  }
}

function frond(ctx, random, x, y, height, direction) {
  const bend = direction * height * .20;
  ctx.strokeStyle = 'rgba(106,153,139,.79)'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(x, y); ctx.quadraticCurveTo(x + bend * 1.6, y - height * .5, x + bend, y - height); ctx.stroke();
  for (let k = 2; k < 23; k++) {
    const u = k / 24, xx = x + bend * Math.sin(u * Math.PI / 2), yy = y - u * height;
    const leaf = Math.sin(u * Math.PI) * height * (.105 + random() * .025);
    for (const sign of [-1, 1]) {
      ctx.fillStyle = k % 4 ? 'rgba(71,122,110,.75)' : 'rgba(111,157,138,.67)';
      ctx.beginPath(); ctx.moveTo(xx, yy + 3);
      ctx.quadraticCurveTo(xx + sign * leaf * .63, yy - leaf * .06, xx + sign * leaf, yy - leaf * .43);
      ctx.quadraticCurveTo(xx + sign * leaf * .48, yy - leaf * .02, xx, yy + 3); ctx.fill();
    }
  }
}

function paintedTexture(reef, node) {
  const random = randomFor(reef.seed + node.sprite * 7919 + (node.kind === 'wall' ? 41011 : 78091));
  const source = reef.sourceImage, SW = source.naturalWidth, SH = source.naturalHeight;
  const W = 620, H = node.kind === 'pebbles' ? 260 : node.kind === 'wall' ? 760 : 620;
  const output = surface(W, H), plants = surface(W, H), ctx = output.ctx;
  const left = random() > .5, form = node.sprite % 4;
  let sx, sy, sw, sh;
  if (node.kind === 'pebbles') {
    sx = SW * (.26 + random() * .45); sy = SH * (.86 + random() * .02);
    sw = SW * .14; sh = SH * .12;
  } else if (node.kind === 'wall') {
    sx = left ? SW * (.008 + random() * .13) : SW * (.67 + random() * .07);
    sy = SH * (.27 + random() * .16); sw = SW * (.22 + random() * .055); sh = SH * (.50 + random() * .12);
  } else {
    sx = left ? SW * (.006 + random() * .18) : SW * (.63 + random() * .14);
    sy = SH * (form === 2 ? .64 + random() * .10 : .32 + random() * .23);
    sw = SW * (.15 + random() * .14);
    sh = SH * (form === 2 ? .24 + random() * .10 : .38 + random() * .17);
  }
  sw = Math.min(sw, SW - sx); sh = Math.min(sh, SH - sy);
  ctx.drawImage(source, sx, sy, sw, sh, 0, 0, W, H);
  const pixels = ctx.getImageData(0, 0, W, H), rgba = pixels.data;
  // The painting is opaque. Separate its pale coral/rock tissue from blue water
  // and feather every cutout boundary; never carry a rectangular patch of ocean.
  // Two uneven lower masses retain dark crevices, with a buried feathered foot.
  // They differ across crops, rather than imposing the same island silhouette.
  const center = .45 + random() * .12, bulge = .25 + random() * .14;
  const lowCenter = .76 + random() * .09, topShape = random() * TAU;
  const exposure = .94 + random() * .12;
  for (let y = 0; y < H; y++) {
    const v = y / (H - 1);
    for (let x = 0; x < W; x++) {
      const u = x / (W - 1), i = (y * W + x) * 4;
      const r = rgba[i], g = rgba[i + 1], b = rgba[i + 2];
      const ratio = r / Math.max(1, b), brightness = (r + g + b) / 3;
      const tissue = smooth(.30, .54, ratio) * smooth(16, 50, brightness);
      const leftFeather = .025 + .065 * Math.sin(v * 8.1 + topShape) ** 2;
      const rightFeather = .025 + .065 * Math.cos(v * 6.3 + topShape * .7) ** 2;
      const boundary = smooth(0, leftFeather, u) * smooth(0, rightFeather, 1 - u)
        * smooth(0, .04 + .025 * Math.sin(u * 8 + topShape) ** 2, v)
        * (1 - smooth(.89, 1, v));
      const xx = (u - center) / .48, yy = (v - lowCenter) / (node.kind === 'wall' ? .39 : .30);
      const first = 1 - smooth(.74, 1.03, Math.hypot(xx, yy));
      const second = 1 - smooth(.77, 1.02, Math.hypot((u - bulge) / .33, (v - .86) / .22));
      const body = Math.max(first, second);
      const rockMask = Math.max(tissue, body);
      const mask = node.kind === 'pebbles' ? (1 - smooth(.66, 1.0, Math.hypot((u - .5) / .50, (v - .58) / .57))) : rockMask;
      rgba[i + 3] = Math.round(255 * clamp(mask * boundary));
      // Fine sediment settles over the lowest crevices; the last pixels blend
      // into the same cool sand as the projected floor instead of a cut edge.
      const sand = smooth(.84, 1, v) * .60;
      rgba[i] = Math.round(r * .83 * exposure * (1 - sand) + 20 * sand);
      rgba[i + 1] = Math.round(g * .88 * exposure * (1 - sand) + 44 * sand);
      rgba[i + 2] = Math.round(b * .93 * exposure * (1 - sand) + 55 * sand);
    }
  }
  ctx.putImageData(pixels, 0, 0);
  return { base: output.canvas, plants: plants.canvas, width: W, height: H, painted: true };
}

function texture(reef, node) {
  const key = `${node.kind}:${node.sprite}`;
  if (reef.sprites.has(key)) return reef.sprites.get(key);
  if (reef.sourceImage) {
    const result = paintedTexture(reef, node); reef.sprites.set(key, result); return result;
  }
  const random = randomFor(reef.seed + node.sprite * 7919 + (node.kind === 'wall' ? 41011 : node.kind === 'pebbles' ? 78091 : 0));
  const W = 420, H = node.kind === 'pebbles' ? 220 : 620;
  const base = surface(W, H), plants = surface(W, H);
  const ctx = base.ctx, vegetation = plants.ctx;
  const baseY = H - 24;
  if (node.kind === 'pebbles') {
    for (let k = 0; k < 10; k++) rockShape(ctx, random, 52 + random() * 316, baseY - random() * 24,
      25 + random() * 81, 13 + random() * 48, k % 3 === 0);
  } else {
    const wall = node.kind === 'wall';
    if (wall) rockShape(ctx, random, 215, baseY, 356, 393, true);
    for (let k = 0; k < (wall ? 8 : 10); k++) {
      const xx = 74 + random() * 272, yy = baseY - random() * (wall ? 150 : 82);
      rockShape(ctx, random, xx, yy, 57 + random() * 130, 47 + random() * (wall ? 116 : 98), k % 3 === 0);
    }
    for (let k = 0; k < (wall ? 8 : 13); k++) {
      const xx = 58 + random() * 304, yy = baseY - 18 - random() * (wall ? 286 : 155);
      const height = 83 + random() * (wall ? 110 : 235), width = 42 + random() * 90;
      if (k % 3 === 0) frond(vegetation, random, xx, yy, height, xx < W / 2 ? .7 : -.7);
      else branchingCoral(vegetation, random, xx, yy, height, width, random() * TAU, k % 3 === 1);
    }
    // Encrusting cool-toned sponge colonies add texture around the lower reef.
    for (let k = 0; k < 38; k++) {
      const x = 55 + random() * 310, y = baseY - 7 - random() * (wall ? 240 : 100), r = 2 + random() * 7;
      vegetation.fillStyle = k % 4 ? 'rgba(102,148,134,.49)' : 'rgba(115,133,160,.53)';
      vegetation.beginPath(); vegetation.ellipse(x, y, r, r * .57, -.13, 0, TAU); vegetation.fill();
      vegetation.strokeStyle = 'rgba(174,188,167,.29)'; vegetation.lineWidth = .75; vegetation.stroke();
    }
  }
  const result = { base: base.canvas, plants: plants.canvas, width: W, height: H };
  reef.sprites.set(key, result); return result;
}

function projected(node, camera) {
  const length = camera.trackLength ?? TRACK;
  const depth = mod(node.z - camera.z, length);
  const near = camera.near ?? 2, far = camera.far ?? 160;
  if (depth <= near || depth >= far) return null;
  const scale = (camera.focal ?? 950) / depth;
  const w = node.width * scale, h = node.height * scale;
  const x = camera.width / 2 + (node.x - camera.x) * scale;
  const y = camera.height * .45 - (node.y - camera.y) * scale;
  if (x + w * .55 < -32 || x - w * .55 > camera.width + 32 || y - h > camera.height + 32 || y < -32) return null;
  const alpha = smooth(near, Math.max(5, near + 2), depth)
    * (1 - smooth(far * .76, far, depth)) * (1 - .30 * smooth(55, far, depth));
  return { node, depth, scale, x, y, width: w, height: h, alpha };
}

function drawSediment(ctx, camera) {
  const focal = camera.focal ?? 950, far = camera.far ?? 160, near = camera.near ?? 2;
  const horizon = camera.height * .45;
  const floorY = horizon + (5.55 + camera.y) * focal / far;
  // A continuous sandy plane anchors the moving side reefs to one world floor.
  // It overlays only the lower, nearer part of the distant painted background.
  const gradient = ctx.createLinearGradient(0, floorY, 0, camera.height);
  gradient.addColorStop(0, 'rgba(7,27,41,0)');
  gradient.addColorStop(.16, 'rgba(10,33,46,.96)');
  gradient.addColorStop(.38, '#112d3a');
  gradient.addColorStop(1, '#173541');
  ctx.fillStyle = gradient; ctx.fillRect(0, floorY, camera.width, camera.height - floorY);
  let groundImages = 0, grainPaths = 0;
  if (active.sourceImage) {
    if (!active.floorTexture) {
      // Grain only: picture fragments contain coral and form obvious tiles.
      // This low-contrast periodic sand texture is entirely original code.
      const sample = surface(1024, 256), data = sample.ctx.createImageData(1024, 256);
      const random = randomFor(active.seed + 399731);
      for (let y = 0; y < 256; y++) for (let x = 0; x < 1024; x++) {
        const i = (y * 1024 + x) * 4;
        const fine = (random() + random() + random() - 1.5) * 4;
        const cloud = 1.0 * Math.sin(TAU * (x / 1024 * 3 + y / 256 * 2))
          + .7 * Math.sin(TAU * (x / 1024 * 7 - y / 256 * 3));
        data.data[i] = 24 + fine + cloud; data.data[i + 1] = 45 + fine + cloud;
        data.data[i + 2] = 56 + fine + cloud; data.data[i + 3] = 255;
      }
      sample.ctx.putImageData(data, 0, 0); active.floorTexture = sample.canvas;
    }
    const slices = [];
    for (let i = 0; i < 240; i++) {
      const d = mod((i + .5) * 2.5 - camera.z, camera.trackLength ?? TRACK);
      if (d > 110 || d < near + 1.25) continue;
      const yNear = horizon + (5.55 + camera.y) * focal / (d - 1.25);
      const yFar = horizon + (5.55 + camera.y) * focal / (d + 1.25);
      if (yFar > camera.height || yNear < floorY) continue;
      slices.push({ i, depth: d, yNear, yFar });
    }
    slices.sort((a, b) => b.depth - a.depth);
    ctx.save();
    for (const s of slices) {
      const scale = focal / s.depth;
      ctx.globalAlpha = .74 * (1 - smooth(60, 110, s.depth));
      const tileWidth = 12.5 * scale;
      const start = Math.floor((camera.x - camera.width / (2 * scale)) / 12.5) - 1;
      const end = Math.ceil((camera.x + camera.width / (2 * scale)) / 12.5) + 1;
      for (let col = start; col <= end; col++) {
        const x = camera.width / 2 + (col * 12.5 - camera.x) * scale;
        const x0 = Math.floor(x), x1 = Math.floor(x + tileWidth);
        const y0 = Math.floor(s.yFar), y1 = Math.floor(s.yNear);
        ctx.drawImage(active.floorTexture, 0, (s.i % 4) * 64, 1024, 64,
          x0, y0, x1 - x0, y1 - y0);
        groundImages++;
      }
    }
    ctx.restore();
  }
  for (const speck of active.sediment) {
    const depth = mod(speck.z - camera.z, camera.trackLength ?? TRACK);
    if (depth < near || depth > far) continue;
    const scale = focal / depth, x = camera.width / 2 + (speck.x - camera.x) * scale;
    const y = horizon + (5.55 + camera.y) * scale;
    if (x < -5 || x > camera.width + 5 || y > camera.height + 5) continue;
    ctx.fillStyle = speck.light ? 'rgba(126,151,144,.20)' : 'rgba(2,17,28,.27)';
    ctx.beginPath(); ctx.ellipse(x, y, Math.max(.4, speck.radius * scale), Math.max(.25, speck.radius * scale * .26), -.05, 0, TAU); ctx.fill();
    grainPaths++;
  }
  return { images: groundImages, paths: grainPaths };
}

/** Draw over distant water/background. camera coordinates are in world units. */
export function drawReef(ctx, camera, t = 0) {
  if (!active) makeReef();
  if (![camera.x, camera.y, camera.z, camera.width, camera.height, t].every(Number.isFinite)) throw new TypeError('Reef requires finite camera coordinates and time.');
  const visible = active.nodes.map(node => projected(node, camera)).filter(Boolean).sort((a, b) => b.depth - a.depth);
  const phase = mod(t, 300) / 300 * TAU;
  ctx.save(); ctx.globalCompositeOperation = 'source-over';
  const ground = drawSediment(ctx, camera);
  for (const p of visible) {
    const sprite = texture(active, p.node);
    if (sprite.painted) {
      const foot = camera.height * .45 + (5.55 + camera.y) * p.scale;
      const shadow = ctx.createRadialGradient(p.x, foot, 0, p.x, foot, p.width * .51);
      shadow.addColorStop(0, `rgba(1,13,24,${(.36 * p.alpha).toFixed(3)})`);
      shadow.addColorStop(1, 'rgba(1,13,24,0)');
      ctx.save(); ctx.translate(p.x, foot); ctx.scale(1, .16); ctx.translate(-p.x, -foot);
      ctx.fillStyle = shadow; ctx.fillRect(p.x - p.width * .55, foot - p.width * .55, p.width * 1.10, p.width * 1.10); ctx.restore();
    }
    ctx.save(); ctx.translate(p.x, p.y); if (p.node.mirror) ctx.scale(-1, 1);
    ctx.globalAlpha = p.alpha * p.node.opacity;
    ctx.drawImage(sprite.base, -p.width / 2, -p.height, p.width, p.height);
    if (p.node.kind !== 'pebbles' && !sprite.painted) {
      // A continuous, tiny shear bends fronds at their roots; rocks stay fixed.
      const shear = .005 * Math.sin(phase * 9 + p.node.phase);
      ctx.transform(1, 0, shear, 1, 0, 0);
      ctx.drawImage(sprite.plants, -p.width / 2, -p.height, p.width, p.height);
    }
    ctx.restore();
  }
  ctx.restore();
  return { visible_objects: visible.length, draw_images: ground.images + visible.reduce((n, p) => n + (active.sourceImage || p.node.kind === 'pebbles' ? 1 : 2), 0),
    ground_images: ground.images, ground_grain_paths: ground.paths };
}

/** Source-space diagnostics; this is a projected illustration, not a 3D mesh. */
export function reefDiagnostics(camera, t = 0) {
  if (!active) makeReef();
  const visible = active.nodes.map(node => projected(node, camera)).filter(Boolean);
  return { renderer: 'Canvas2D deterministic textured billboards in a perspective world corridor',
    texture_source: active.sourceImage ? 'Existing original reef painting; no new image asset' : 'Procedural paths and gradients',
    seed: active.seed, track_length: active.trackLength, total_objects: active.nodes.length,
    visible_objects: visible.length,
    visible_rocks: visible.filter(p => p.node.kind !== 'pebbles').length,
    nearest_depth: visible.length ? Math.min(...visible.map(p => p.depth)) : null,
    farthest_depth: visible.length ? Math.max(...visible.map(p => p.depth)) : null,
    projected_reef_images: visible.reduce((n, p) => n + (active.sourceImage || p.node.kind === 'pebbles' ? 1 : 2), 0),
    ground_draw_images_upper_bound: active.sourceImage ? 700 : 0,
    clear_corridor: [-6, 6], minimum_inner_bound: Math.min(...active.nodes.map(n => Math.abs(n.x) - n.width / 2)),
    camera_z: mod(camera.z, camera.trackLength ?? TRACK), time_phase: mod(t, 300) / 300 * TAU,
    landmarks: active.nodes.map(n => { const depth = mod(n.z - camera.z, camera.trackLength ?? TRACK);
      const p = projected(n, camera), scale = (camera.focal ?? 950) / Math.max(depth, .0001);
      return { id: n.id, world: [n.x, n.y, n.z], depth, scale,
        screen: [camera.width / 2 + (n.x - camera.x) * scale, camera.height * .45 - (n.y - camera.y) * scale],
        visible: Boolean(p), alpha: p?.alpha ?? 0 }; }),
    projected: visible.map(p => ({ x: p.x, y: p.y, depth: p.depth, width: p.width,
      height: p.height, alpha: p.alpha, kind: p.node.kind })) };
}
