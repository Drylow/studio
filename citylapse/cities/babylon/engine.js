import * as THREE from "three";
import { EffectComposer, RenderPass, EffectPass, ShaderPass, BloomEffect, ToneMappingEffect, ToneMappingMode, VignetteEffect, SMAAEffect, SMAAPreset, HueSaturationEffect, BrightnessContrastEffect } from "postprocessing";
import { N8AOPostPass } from "n8ao";

// Shared city-timelapse engine (from the approved Valmora pilot): renderer + post (AO, tilt-shift, bloom, ACES, SMAA),
// instanced buildings that grow / burn / die in the vertex shader (shadows included), ground texture raster with
// per-pixel birth times, scripted landmarks, a time-knot Hermite camera, and the fixed HUD.

// ---------------- math ----------------
export const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x);
export const lerp = (a, b, u) => a + (b - a) * u;
export const ramp = (t, a, b) => clamp((t - a) / (b - a));
export const sm = (u) => u * u * (3 - 2 * u);
export const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
export function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export const hash2 = (x, y) => { let h = Math.imul(x | 0, 374761393) + Math.imul(y | 0, 668265263); h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
export function vnoise(x, y) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = sm(x - xi), yf = sm(y - yi);
  return lerp(lerp(hash2(xi, yi), hash2(xi + 1, yi), xf), lerp(hash2(xi, yi + 1), hash2(xi + 1, yi + 1), xf), yf);
}
export const fbm = (x, y) => vnoise(x, y) * 0.5 + vnoise(x * 2.03 + 17, y * 2.03 - 9) * 0.3 + vnoise(x * 4.1 - 31, y * 4.1 + 5) * 0.2;
// piecewise curve through [t, v] keys with smoothstep between keys
export const pw = (K, t) => { if (t <= K[0][0]) return K[0][1]; for (let i = 1; i < K.length; i++) if (t <= K[i][0]) return lerp(K[i - 1][1], K[i][1], sm((t - K[i - 1][0]) / (K[i][0] - K[i - 1][0]))); return K[K.length - 1][1]; };
// piecewise linear (for the year counter)
export const pl = (K, t) => { if (t <= K[0][0]) return K[0][1]; for (let i = 1; i < K.length; i++) if (t <= K[i][0]) return lerp(K[i - 1][1], K[i][1], (t - K[i - 1][0]) / (K[i][0] - K[i - 1][0])); return K[K.length - 1][1]; };
// first time a monotonic f(t) reaches v (1e6 if never)
export const inv = (f, v, a, b) => { if (f(b) < v) return 1e6; for (let i = 0; i < 40; i++) { const m = (a + b) / 2; if (f(m) < v) a = m; else b = m; } return b; };
export const M4 = (x, y, z, ry = 0, sx = 1, sy = 1, sz = 1) => new THREE.Matrix4().compose(V(x, y, z), new THREE.Quaternion().setFromAxisAngle(V(0, 1, 0), ry), V(sx, sy, sz));
export const NEVER = 1e5;

// ---------------- growth shader ----------------
export const U = { uTime: { value: 0 } };
const GROW = /* glsl */ `
uniform float uTime;
attribute vec4 aT;            // birth, death, ignite, seed
float growK(float t0) {
  float u = clamp((uTime - t0) / 0.6, 0.0, 1.0);
  if (u <= 0.0) return 0.0;
  float c1 = 0.9, c3 = c1 + 1.0;
  float v = u - 1.0;                     // no pow() here: pow of a negative number is undefined in GLSL
  return 1.0 + c3 * v * v * v + c1 * v * v;
}
float aliveK() {
  float g = growK(aT.x);
  float d = clamp((uTime - aT.y) / 0.7, 0.0, 1.0);
  return g * (1.0 - d * d * (3.0 - 2.0 * d));
}
`;
// mode "house": local geometry in y∈[0,1], attribute aH = (base, height) in metres; mode "uniform": whole object scales
function growMaterial(base, mode) {
  const vtx = (shader, depth) => {
    shader.uniforms.uTime = U.uTime;
    const charV = depth ? "" : "vChar = aT.z < 9000.0 ? clamp((uTime - aT.z) / max(0.1, aT.y - aT.z), 0.0, 1.0) : 0.0;";
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", `#include <common>\n${GROW}\n${mode === "house" ? "attribute vec2 aH;" : ""}\n${depth ? "" : "varying float vChar;"}`)
      .replace("#include <begin_vertex>", mode === "house"
        ? `float g = aliveK(); float s = g > 0.001 ? 0.45 + 0.55 * min(g, 1.0) : 0.0;
           vec3 transformed = vec3(position.x * s, (aH.x + position.y * aH.y) * g, position.z * s); ${charV}`
        : `float g = aliveK(); vec3 transformed = position * g; ${charV}`);
    if (!depth) shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", "#include <common>\nvarying float vChar;")
      .replace("#include <color_fragment>", "#include <color_fragment>\n diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.07, 0.05, 0.04), vChar * 0.9);");
  };
  base.onBeforeCompile = (s) => vtx(s, false);
  base.customProgramCacheKey = () => "grow-" + mode;
  const depth = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking });
  depth.onBeforeCompile = (s) => vtx(s, true);
  depth.customProgramCacheKey = () => "growd-" + mode;
  return { mat: base, depth };
}
export const STD = (opts = {}) => new THREE.MeshStandardMaterial({ roughness: 0.9, metalness: 0, ...opts });

// recs: {m: Matrix4, c?: Color, t: [birth, death, ign, seed], h?: [base, height]}
export function growMesh(geo, mat, mode, recs, { shadow = true, receive = true } = {}) {
  const g = geo.clone(), n = recs.length;
  const aT = new Float32Array(Math.max(1, n) * 4), aH = new Float32Array(Math.max(1, n) * 2);
  recs.forEach((r, i) => { aT.set(r.t, i * 4); if (r.h) aH.set(r.h, i * 2); });
  g.setAttribute("aT", new THREE.InstancedBufferAttribute(aT, 4));
  if (mode === "house") g.setAttribute("aH", new THREE.InstancedBufferAttribute(aH, 2));
  const { mat: m, depth } = growMaterial(mat, mode);
  const mesh = new THREE.InstancedMesh(g, m, Math.max(1, n));
  mesh.count = n;
  recs.forEach((r, i) => { mesh.setMatrixAt(i, r.m); if (r.c) mesh.setColorAt(i, r.c); });
  mesh.customDepthMaterial = depth;
  mesh.castShadow = shadow; mesh.receiveShadow = receive; mesh.frustumCulled = false;
  return mesh;
}

// ---------------- geometry kit ----------------
export function unitBox() { const g = new THREE.BoxGeometry(1, 1, 1); g.translate(0, 0.5, 0); return g; }
export function hipRoof() {
  const p = [[-0.5, 0, -0.5], [0.5, 0, -0.5], [0.5, 0, 0.5], [-0.5, 0, 0.5], [-0.22, 1, 0], [0.22, 1, 0]];
  const f = [[0, 4, 5], [0, 5, 1], [1, 5, 2], [2, 5, 4], [2, 4, 3], [3, 4, 0]];
  const pos = [];
  for (const [a, b, c] of f) pos.push(...p[a], ...p[b], ...p[c]);
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.computeVertexNormals();
  return g;
}
export function facet(g) { const n = g.toNonIndexed(); n.computeVertexNormals(); return n; }

// ---------------- renderer + post ----------------
export function createStage(canvas, { W, H, SS, fog = "#c9d2d4", sunColor = "#fff0d6", sunDir = [-0.62, 0.62, -0.48], hemiSky = "#cfe3ff", hemiGround = "#7a7a5a", hemiI = 1.1, sunI = 3.1, saturation = -0.06 }) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, stencil: false, depth: false, preserveDrawingBuffer: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(SS); renderer.setSize(W, H, false); renderer.toneMapping = THREE.NoToneMapping;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const scene = new THREE.Scene();
  const FOG = new THREE.Color(fog);
  scene.background = FOG; scene.fog = new THREE.Fog(FOG, 2000, 9000);
  const camera = new THREE.PerspectiveCamera(36, W / H, 2, 20000);
  const hemi = new THREE.HemisphereLight(hemiSky, hemiGround, hemiI); scene.add(hemi);
  const sun = new THREE.DirectionalLight(sunColor, sunI); sun.castShadow = true;
  sun.shadow.mapSize.set(4096, 4096); sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.8; sun.shadow.radius = 3;
  scene.add(sun, sun.target);
  const SUN_DIR = V(...sunDir).normalize();

  const composer = new EffectComposer(renderer, { frameBufferType: THREE.HalfFloatType });
  composer.addPass(new RenderPass(scene, camera));
  const ao = new N8AOPostPass(scene, camera, W * SS, H * SS);
  ao.configuration.aoRadius = 6; ao.configuration.distanceFalloff = 1.5; ao.configuration.intensity = 2.4; ao.setQualityMode("Medium");
  composer.addPass(ao);
  // tilt-shift: a two-pass blur whose radius grows away from a horizontal focus band (the miniature look)
  const tiltMat = (dir) => new THREE.ShaderMaterial({
    uniforms: { inputBuffer: { value: null }, uRes: { value: new THREE.Vector2(W * SS, H * SS) }, uDir: { value: dir }, uFocus: { value: 0.52 }, uBand: { value: 0.14 }, uMax: { value: 12 * SS }, uMaxTop: { value: 8 * SS } },
    vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }",
    fragmentShader: /* glsl */ `
      uniform sampler2D inputBuffer; uniform vec2 uRes; uniform vec2 uDir; uniform float uFocus, uBand, uMax, uMaxTop; varying vec2 vUv;
      void main() {
        float dy = vUv.y - uFocus;
        float k = smoothstep(uBand, uBand + 0.3, abs(dy));
        float r = k * (dy < 0.0 ? uMax : uMaxTop);
        if (r < 0.3) { gl_FragColor = texture2D(inputBuffer, vUv); return; }
        vec4 acc = vec4(0.0); float wsum = 0.0;
        for (int i = -7; i <= 7; i++) {
          float fi = float(i); float w = exp(-fi * fi / 18.0);
          acc += texture2D(inputBuffer, vUv + uDir * fi * (r / 7.0) / uRes) * w; wsum += w;
        }
        gl_FragColor = acc / wsum;
      }`,
    depthWrite: false, depthTest: false,
  });
  composer.addPass(new ShaderPass(tiltMat(new THREE.Vector2(1, 0)), "inputBuffer"));
  composer.addPass(new ShaderPass(tiltMat(new THREE.Vector2(0, 1)), "inputBuffer"));
  composer.addPass(new EffectPass(camera, new BloomEffect({ intensity: 0.55, luminanceThreshold: 0.92, luminanceSmoothing: 0.1, mipmapBlur: true }), new ToneMappingEffect({ mode: ToneMappingMode.ACES_FILMIC }),
    new BrightnessContrastEffect({ brightness: 0.0, contrast: 0.06 }), new HueSaturationEffect({ saturation }), new VignetteEffect({ darkness: 0.38, offset: 0.32 })));
  composer.addPass(new EffectPass(camera, new SMAAEffect({ preset: SMAAPreset.HIGH })));

  // place the camera; fit fog, clip planes, AO radius and the sun's shadow frustum to what we see
  function frame(pos, tgt) {
    camera.position.copy(pos); camera.lookAt(tgt);
    const dist = pos.distanceTo(tgt);
    camera.near = Math.max(2, dist * 0.05); camera.far = dist * 14; camera.updateProjectionMatrix();
    scene.fog.near = dist * 2.2; scene.fog.far = dist * 9;
    const span = clamp(dist * 1.25, 260, 3400);
    sun.target.position.copy(tgt);
    sun.position.copy(tgt).addScaledVector(SUN_DIR, span * 1.5);
    const sc = sun.shadow.camera; sc.left = -span; sc.right = span; sc.top = span; sc.bottom = -span; sc.near = 1; sc.far = span * 4; sc.updateProjectionMatrix();
    ao.configuration.aoRadius = clamp(dist * 0.012, 3, 16);
    return dist;
  }
  return { renderer, scene, camera, composer, ao, sun, hemi, frame, render: () => composer.render(1 / 60) };
}

// ---------------- ground raster: road coverage (linear) + 16-bit birth + field code (texelFetch) ----------------
// segs: {ax, az, bx, bz, w, ba, bb}; plazas: {x, z, r (half size), b, ry?}; fields: {x, z, w, l, a, tone}
export function rasterGround({ X0, Z0, EXT, TEX }, segs, plazas = [], fields = []) {
  const PX = EXT / TEX, data = new Uint8Array(TEX * TEX * 4);
  for (let i = 0; i < TEX * TEX; i++) { data[i * 4 + 1] = 255; data[i * 4 + 2] = 255; }
  const put = (px, pz, alpha, birth) => {
    if (px < 0 || pz < 0 || px >= TEX || pz >= TEX) return;
    const i = (pz * TEX + px) * 4, b = Math.min(65535, Math.max(0, Math.round(birth * 100)));
    if (alpha > data[i]) data[i] = alpha;
    const old = data[i + 1] * 256 + data[i + 2];
    if (b < old) { data[i + 1] = b >> 8; data[i + 2] = b & 255; }
  };
  for (const s of segs) {
    const pad = s.w / 2 + 2;
    const minx = Math.floor((Math.min(s.ax, s.bx) - pad - X0) / PX), maxx = Math.ceil((Math.max(s.ax, s.bx) + pad - X0) / PX);
    const minz = Math.floor((Math.min(s.az, s.bz) - pad - Z0) / PX), maxz = Math.ceil((Math.max(s.az, s.bz) + pad - Z0) / PX);
    const dx = s.bx - s.ax, dz = s.bz - s.az, ll = dx * dx + dz * dz || 1;
    for (let pz = Math.max(0, minz); pz <= Math.min(TEX - 1, maxz); pz++) for (let px = Math.max(0, minx); px <= Math.min(TEX - 1, maxx); px++) {
      const x = X0 + (px + 0.5) * PX, z = Z0 + (pz + 0.5) * PX, u = clamp(((x - s.ax) * dx + (z - s.az) * dz) / ll);
      const d = Math.hypot(x - s.ax - dx * u, z - s.az - dz * u);
      if (d > pad) continue;
      put(px, pz, Math.round(255 * clamp((s.w / 2 + 0.6 - d) / 1.2)), lerp(s.ba, s.bb, u) + (d / s.w) * 0.25);
    }
  }
  for (const p of plazas) {
    const ca = Math.cos(p.ry || 0), sa = Math.sin(p.ry || 0);
    const c = Math.round((p.x - X0) / PX), r = Math.round((p.z - Z0) / PX), R = Math.ceil((Math.max(p.rx || p.r, p.rz || p.r) * 1.5 + 2) / PX);
    for (let pz = r - R; pz <= r + R; pz++) for (let px = c - R; px <= c + R; px++) {
      const x = X0 + (px + 0.5) * PX - p.x, z = Z0 + (pz + 0.5) * PX - p.z;
      const u = Math.abs(x * ca + z * sa) - (p.rx || p.r), v = Math.abs(-x * sa + z * ca) - (p.rz || p.r);
      const d = Math.max(u, v);
      if (d < 1) put(px, pz, Math.round(255 * clamp(-d / 1.2 + 0.5)), p.b + (d + (p.r || 0)) * 0.005);
    }
  }
  for (const f of fields) {
    const ca = Math.cos(f.a), sa = Math.sin(f.a), R = Math.ceil(Math.hypot(f.w, f.l) / 2 / PX);
    const c = Math.round((f.x - X0) / PX), r = Math.round((f.z - Z0) / PX);
    for (let pz = r - R; pz <= r + R; pz++) for (let px = c - R; px <= c + R; px++) {
      if (px < 0 || pz < 0 || px >= TEX || pz >= TEX) continue;
      const x = X0 + (px + 0.5) * PX - f.x, z = Z0 + (pz + 0.5) * PX - f.z;
      const u = x * ca + z * sa, v = -x * sa + z * ca;
      if (Math.abs(u) > f.l / 2 || Math.abs(v) > f.w / 2) continue;
      const i = (pz * TEX + px) * 4;
      if (data[i + 3]) continue;
      data[i + 3] = f.tone * 50 + (Math.floor((v + f.w) / 4.5) % 2) * 20 + 10;
    }
  }
  const tex = new THREE.DataTexture(data, TEX, TEX, THREE.RGBAFormat);
  tex.magFilter = THREE.LinearFilter; tex.minFilter = THREE.LinearFilter; tex.generateMipmaps = false; tex.flipY = false; tex.needsUpdate = true;
  return tex;
}
// GLSL to decode it (birth in seconds = 16-bit / 100)
export const GROUND_GLSL = /* glsl */ `
  float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float n21(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f); return mix(mix(h21(i), h21(i+vec2(1,0)), f.x), mix(h21(i+vec2(0,1)), h21(i+vec2(1,1)), f.x), f.y); }
  vec3 Ls(vec3 c){ return pow(c, vec3(2.2)); }
`;

// ---------------- scripted landmarks ----------------
// grow(obj, a, b, mode, {off, offB, offTo}) : scale in over [a,b]; optionally decay to offTo over [off, offB]
export function landmarks() {
  const LM = [];
  const box = (w, h, d, color, x, y, z, parent, ry = 0, mat) => {
    const g = new THREE.BoxGeometry(w, h, d); g.translate(0, h / 2, 0);
    const m = new THREE.Mesh(g, mat || STD({ color })); m.position.set(x, y, z); m.rotation.y = ry; m.castShadow = m.receiveShadow = true; parent.add(m); return m;
  };
  const grow = (obj, a, b, mode = "y", o = {}) => { LM.push({ obj, a, b, mode, ...o }); obj.visible = false; return obj; };
  function update(t) {
    for (const L of LM) {
      let u = sm(ramp(t, L.a, L.b));
      if (L.off !== undefined) u *= 1 - (1 - (L.offTo || 0)) * sm(ramp(t, L.off, L.offB));
      L.obj.visible = u > 0.001;
      if (!L.obj.visible) continue;
      if (L.mode === "y") L.obj.scale.set(1, u, 1);
      else if (L.mode === "xz") L.obj.scale.set(u, 1, u);
      else if (L.mode === "x") L.obj.scale.set(u, 1, 1);
      else { const k = u < 1 ? 1 - Math.pow(1 - u, 3) * (1 - 1.2 * u) : 1; L.obj.scale.setScalar(Math.max(0.001, k)); }
    }
  }
  return { LM, box, grow, update };
}

// ---------------- camera: time-knot Hermite (C1 in time: one unbroken flight) ----------------
export function cameraPath(keys) {
  const KEYS = keys.map(([t, p, q]) => ({ t, p: V(...p), q: V(...q) }));
  function at(t, key) {
    let i = 0; while (i < KEYS.length - 2 && t > KEYS[i + 1].t) i++;
    const k0 = KEYS[i], k1 = KEYS[i + 1], dt = k1.t - k0.t, u = clamp((t - k0.t) / dt);
    const tan = (j) => { if (j <= 0 || j >= KEYS.length - 1) return V(); const a = KEYS[j - 1], b = KEYS[j + 1]; return b[key].clone().sub(a[key]).divideScalar(b.t - a.t); };
    const m0 = tan(i).multiplyScalar(dt), m1 = tan(i + 1).multiplyScalar(dt);
    const u2 = u * u, u3 = u2 * u;
    return k0[key].clone().multiplyScalar(2 * u3 - 3 * u2 + 1).add(m0.multiplyScalar(u3 - 2 * u2 + u)).add(k1[key].clone().multiplyScalar(-2 * u3 + 3 * u2)).add(m1.multiplyScalar(u3 - u2));
  }
  return (t) => ({ pos: at(t, "p"), tgt: at(t, "q") });
}

// ---------------- HUD ----------------
export const fmtYear = (y) => (y < 0 ? `${-y} BC` : y < 1000 ? `AD ${y}` : `${y}`);
export const fmtPop = (n) => { const r = n < 1000 ? 10 : n < 10000 ? 100 : 1000; return (Math.round(n / r) * r).toLocaleString("en-US"); };
// cfg: {ERAS:[{t,name,flag}], FLAGS, TITLE:[a,b], LANDMARKS:[{a,b,text}], CAPTIONS:[{a,b,lines}], CARDS:[{a,b,kicker,text}], yearAt, popAt, DUR}
export function hudDriver(hud, cfg) {
  const env = (t, a, b, f = 0.9) => clamp(Math.min((t - a) / f, (b - t) / f));
  let lastEra = -1;
  return function draw(t) {
    hud.year.textContent = fmtYear(cfg.yearAt(t));
    const p = cfg.popAt(t);
    hud.pop.style.opacity = p > 0 ? 1 : 0;
    hud.popN.textContent = `c. ${fmtPop(p)}`;
    let e = 0; for (let i = 0; i < cfg.ERAS.length; i++) if (t >= cfg.ERAS[i].t) e = i;
    if (e !== lastEra) { hud.eraName.textContent = cfg.ERAS[e].name; hud.flag.innerHTML = cfg.ERAS[e].flag ? cfg.FLAGS[cfg.ERAS[e].flag] : ""; lastEra = e; }
    hud.era.style.opacity = e === 0 ? 1 : clamp((t - cfg.ERAS[e].t) / 0.7);
    hud.flag.style.opacity = cfg.ERAS[e].flag ? 1 : 0;
    hud.title.style.opacity = env(t, cfg.TITLE[0], cfg.TITLE[1], 1.2);
    const lm = cfg.LANDMARKS.find((l) => t >= l.a && t <= l.b);
    hud.lm.style.opacity = lm ? env(t, lm.a, lm.b, 1.0) * 0.92 : 0; if (lm) hud.lmText.textContent = lm.text;
    const cp = cfg.CAPTIONS.find((c) => t >= c.a && t <= c.b);
    hud.cap.style.opacity = cp ? env(t, cp.a, cp.b, 0.8) : 0; if (cp) { hud.capL1.textContent = cp.lines[0]; hud.capL2.textContent = cp.lines[1]; }
    const cd = cfg.CARDS.find((c) => t >= c.a && t <= c.b);
    hud.card.style.opacity = cd ? env(t, cd.a, cd.b, 1.1) : 0; if (cd) { hud.cardK.textContent = cd.kicker; hud.cardT.textContent = cd.text; }
    hud.black.style.opacity = Math.max(1 - clamp(t / 1.6), clamp((t - (cfg.DUR - 1.8)) / 1.6));
    hud.ui.style.opacity = clamp((t - 0.8) / 1.2) * (1 - clamp((t - (cfg.DUR - 2.4)) / 1.2));
  };
}

// ---------------- fire (flames on burning instances) + smoke/dust puffs ----------------
export function flames(scene, recs, color) {
  const geo = new THREE.ConeGeometry(1, 1, 5); geo.translate(0, 0.5, 0);
  const n = recs.length, aT = new Float32Array(Math.max(1, n) * 4);
  recs.forEach((r, i) => aT.set(r.t, i * 4));
  geo.setAttribute("aT", new THREE.InstancedBufferAttribute(aT, 4));
  const mat = new THREE.MeshBasicMaterial({ color });
  mat.onBeforeCompile = (s) => {
    s.uniforms.uTime = U.uTime;
    s.vertexShader = s.vertexShader.replace("#include <common>", "#include <common>\nuniform float uTime; attribute vec4 aT;")
      .replace("#include <begin_vertex>", `float on = smoothstep(aT.x, aT.x + 0.5, uTime) * (1.0 - smoothstep(aT.y - 0.6, aT.y, uTime));
        float fl = 0.72 + 0.28 * sin(uTime * 13.0 + aT.w * 40.0) * sin(uTime * 7.3 + aT.w * 17.0);
        vec3 transformed = position * vec3(on * (0.9 + 0.12 * fl), on * fl, on * (0.9 + 0.12 * fl));`);
  };
  const m = new THREE.InstancedMesh(geo, mat, Math.max(1, n)); m.count = n;
  recs.forEach((r, i) => m.setMatrixAt(i, r.m)); m.frustumCulled = false; scene.add(m);
  return m;
}
// columns: {x, y, z, t0, t1, ph, rise, spread, wind:[x,z]}; returns update(t)
export function puffs(scene, columns, { color = "#4a4541", opacity = 0.3, perCol = 22 } = {}) {
  const mesh = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 1), new THREE.MeshLambertMaterial({ color, transparent: true, opacity, depthWrite: false }), Math.max(1, columns.length * perCol));
  mesh.frustumCulled = false; scene.add(mesh);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = V(), p = V();
  return function update(t) {
    let k = 0;
    for (const c of columns) {
      const life = ramp(t, c.t0, c.t0 + 1.2) * (1 - ramp(t, c.t1, c.t1 + 2.6));
      if (life <= 0) continue;
      for (let j = 0; j < perCol; j++) {
        const ph = ((t - c.t0) * (c.speed || 0.13) + j / perCol + c.ph) % 1;
        const sc = (c.size0 || 4) + ph * (c.spread || 22);
        const k2 = sc * life * (1 - Math.pow(ph, 4)) * Math.min(1, ph * 6);
        p.set(c.x + ph * (c.wind ? c.wind[0] : 110) + Math.sin(j * 2.1 + t * 0.4) * 5, c.y + ph * (c.rise || 200), c.z + ph * (c.wind ? c.wind[1] : -40) + Math.cos(j * 1.7) * 5);
        s.set(k2, k2 * 0.9, k2);
        mesh.setMatrixAt(k++, m.compose(p, q, s));
      }
    }
    mesh.count = k; mesh.instanceMatrix.needsUpdate = true;
  };
}
