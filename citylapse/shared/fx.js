import * as THREE from "three";
import { clamp, lerp, ramp, sm, V, hash2, mulberry32 } from "./engine.js";

// Story effects for the timelapses (Latos-style events): fires, crowds, armies, fleets, fireworks, race cars,
// aircraft, an earthquake shake, weather and light changes. Every effect is a pure function of the video time t
// (frame-exact, so any frame can be rendered alone). Each one also returns sound cues {t, kind, dur, gain} that
// tools/sfx.mjs turns into the effects track.
//
//   const fx = storyFx(scene, heightAt);
//   fx.fire({ x, z, r, t0, t1 })                 flames + a smoke column (sound: fire)
//   fx.smoke({ x, z, t0, t1, big })              a dark column (bombing, battle)
//   fx.crowd({ x, z, r, n, t0, t1 })             a dense gathering (sound: crowd)
//   fx.army({ path:[[x,z],...], t0, t1, n, color })   a column of soldiers marching along a path (sound: march)
//   fx.fleet({ path, t0, t1, n, sail })          ships sailing along a sea path (sound: waves)
//   fx.fireworks({ x, z, t0, t1 })               bursts over the sea (sound: fireworks)
//   fx.race({ path, t0, t1, n, colors })         race cars lapping a circuit (sound: engines)
//   fx.planes({ from:[x,z], to:[x,z], t0, t1, n, alt })   aircraft crossing (sound: planes)
//   fx.quake({ t0, t1 })                         camera shake + dust (sound: rumble)
//   fx.sky({ t0, t1, kind })                     kind: night | storm | eclipse | winter (light, fog, snow)
//   fx.cue(t, kind, dur, gain)                   a sound with no picture (bells, cannon, cheer, whoosh)
// Per frame: fx.update(t, stage) → { shake: Vector3, snow: 0..1 }.

const BOX = new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0);
const along = (path, u) => {                       // a point (and heading) at fraction u of a polyline
  let L = 0; const seg = [];
  for (let i = 1; i < path.length; i++) { const d = Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]); seg.push(d); L += d; }
  let s = ((u % 1) + 1) % 1 * L;
  for (let i = 0; i < seg.length; i++) {
    if (s <= seg[i] || i === seg.length - 1) { const f = seg[i] ? s / seg[i] : 0, a = path[i], b = path[i + 1];
      return [lerp(a[0], b[0], f), lerp(a[1], b[1], f), Math.atan2(b[1] - a[1], b[0] - a[0]), L]; }
    s -= seg[i];
  }
  return [path[0][0], path[0][1], 0, L];
};

export function storyFx(scene, heightAt) {
  const cues = [], parts = [];
  const life = (t, a, b, f = 1.2) => clamp(Math.min((t - a) / f, (b - t) / f));
  const inst = (geo, mat, n, shadow = false) => { const m = new THREE.InstancedMesh(geo, mat, Math.max(1, n)); m.frustumCulled = false; m.castShadow = shadow; m.count = 0; scene.add(m); return m; };
  const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = V(1, 1, 1), _p = V(), _up = V(0, 1, 0), _c = new THREE.Color();

  // ---------- fire + smoke ----------
  const FLAME = inst(new THREE.ConeGeometry(1, 1, 5).translate(0, 0.5, 0), new THREE.MeshBasicMaterial({ color: "#ff8a2a", toneMapped: false }), 1800);
  const FLAME2 = inst(new THREE.ConeGeometry(1, 1, 5).translate(0, 0.5, 0), new THREE.MeshBasicMaterial({ color: "#ffd25a", toneMapped: false }), 1800);
  const SMOKE = inst(new THREE.IcosahedronGeometry(1, 1), new THREE.MeshLambertMaterial({ color: "#3d3936", transparent: true, opacity: 0.42, depthWrite: false }), 4000);
  const LSMOKE = inst(new THREE.IcosahedronGeometry(1, 1), new THREE.MeshLambertMaterial({ color: "#d8d0c2", transparent: true, opacity: 0.35, depthWrite: false }), 1500);
  const fires = [], smokes = [], dusts = [];
  function fire(o) {
    const r = o.r || 60, n = o.n || Math.round(r * 0.9), rnd = mulberry32(fires.length * 977 + 13);
    const pts = []; for (let k = 0; k < n; k++) { const a = rnd() * 6.283, d = Math.sqrt(rnd()) * r, x = o.x + Math.cos(a) * d, z = o.z + Math.sin(a) * d; pts.push([x, heightAt(x, z) + 3 + rnd() * 6, z, rnd(), 4 + rnd() * 7]); }
    fires.push({ ...o, pts }); smokes.push({ x: o.x, z: o.z, t0: o.t0, t1: o.t1 + 3, big: r > 90 });
    cues.push({ t: o.t0, kind: "fire", dur: o.t1 - o.t0 + 2, gain: o.gain || 1 });
  }
  function smoke(o) { smokes.push(o); if (o.sound !== false) cues.push({ t: o.t0, kind: o.kind || "boom", dur: 2.5, gain: o.gain || 0.9 }); }
  function dust(o) { dusts.push(o); }

  // ---------- people: crowds and marching columns ----------
  const PEOPLE = inst(BOX, new THREE.MeshLambertMaterial({ color: "#ffffff" }), 9000);
  const crowds = [], armies = [];
  const PC = ["#2a2622", "#3b342c", "#4a3f35", "#5a4b3e", "#2f2b33", "#6b5a48", "#7a2e2a", "#2d3c55"];
  function crowd(o) {
    const n = o.n || 600, rnd = mulberry32(crowds.length * 31 + 7), pts = [];
    for (let k = 0; k < n; k++) { const a = rnd() * 6.283, d = Math.sqrt(rnd()) * (o.r || 50), x = o.x + Math.cos(a) * d * (o.sx || 1), z = o.z + Math.sin(a) * d; pts.push([x, heightAt(x, z), z, rnd()]); }
    crowds.push({ ...o, pts }); cues.push({ t: o.t0, kind: "crowd", dur: o.t1 - o.t0, gain: o.gain || 1 });
  }
  function army(o) { armies.push({ n: 240, color: "#3a3f4a", ...o }); cues.push({ t: o.t0, kind: "march", dur: o.t1 - o.t0, gain: o.gain || 0.8 }); }

  // ---------- ships ----------
  const HULL = inst(new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0), new THREE.MeshLambertMaterial({ color: "#6b4a30" }), 300, true);
  const SAIL = inst(new THREE.BoxGeometry(1, 1, 0.08).translate(0, 0.5, 0), new THREE.MeshLambertMaterial({ color: "#efe8d6", side: THREE.DoubleSide }), 300, true);
  const fleets = [];
  function fleet(o) { fleets.push({ n: 8, len: 28, ...o }); cues.push({ t: o.t0, kind: "waves", dur: o.t1 - o.t0, gain: 0.6 }); }

  // ---------- fireworks ----------
  const SPARK = inst(new THREE.IcosahedronGeometry(1, 0), new THREE.MeshBasicMaterial({ color: "#ffffff", toneMapped: false }), 6000);
  const shows = [];
  const FWC = ["#ff4d4d", "#ffd84d", "#5dd2ff", "#ffffff", "#ff7ae0", "#7dff8a", "#ffb04d"];
  function fireworks(o) {
    const rnd = mulberry32(shows.length * 101 + 3), bursts = [];
    for (let t = o.t0; t < o.t1; t += 0.35 + rnd() * 0.5) bursts.push({ t, x: o.x + (rnd() - 0.5) * (o.w || 500), z: o.z + (rnd() - 0.5) * (o.d || 200), y: 120 + rnd() * 120, c: FWC[Math.floor(rnd() * FWC.length)], r: 40 + rnd() * 45, seed: Math.floor(rnd() * 1e6) });
    shows.push({ ...o, bursts }); for (const b of bursts) cues.push({ t: b.t, kind: "firework", dur: 1.6, gain: 0.55 + rnd() * 0.4 });
  }

  // ---------- race cars ----------
  const CAR = inst(new THREE.BoxGeometry(5, 1.4, 2.2).translate(0, 0.7, 0), new THREE.MeshLambertMaterial({ color: "#ffffff" }), 60, true);
  const races = [];
  function race(o) { races.push({ n: 14, speed: 55, ...o }); cues.push({ t: o.t0, kind: "engines", dur: o.t1 - o.t0, gain: o.gain || 1 }); }

  // ---------- aircraft ----------
  const PLANE = new THREE.Group();
  const planeGeo = (() => { const g = new THREE.BoxGeometry(14, 2, 2.4); const w = new THREE.BoxGeometry(3, 0.5, 22); const t = new THREE.BoxGeometry(1.6, 0.4, 8).translate(-6, 0.6, 0); const geo = new THREE.BufferGeometry(); return [g, w, t]; })();
  const PL = planeGeo.map((g) => inst(g, new THREE.MeshLambertMaterial({ color: "#5d6166" }), 60, true));
  scene.add(PLANE);
  const flights = [];
  function planes(o) { flights.push({ n: 6, alt: 260, ...o }); cues.push({ t: o.t0, kind: "planes", dur: o.t1 - o.t0, gain: o.gain || 1 }); }

  // ---------- earthquake / sky ----------
  const quakes = [], skies = [];
  function quake(o) { quakes.push(o); cues.push({ t: o.t0, kind: "rumble", dur: o.t1 - o.t0 + 1.5, gain: 1 }); }
  function sky(o) { skies.push(o); if (o.kind === "storm") cues.push({ t: o.t0, kind: "storm", dur: o.t1 - o.t0, gain: 0.9 }); if (o.kind === "winter") cues.push({ t: o.t0, kind: "wind", dur: o.t1 - o.t0, gain: 0.6 }); }
  const SNOWF = inst(new THREE.BoxGeometry(0.9, 0.9, 0.9), new THREE.MeshBasicMaterial({ color: "#ffffff", transparent: true, opacity: 0.85 }), 2500);
  const RAIN = inst(new THREE.BoxGeometry(0.25, 14, 0.25), new THREE.MeshBasicMaterial({ color: "#c9d6e2", transparent: true, opacity: 0.5 }), 2500);
  const cue = (t, kind, dur = 2, gain = 1) => cues.push({ t, kind, dur, gain });

  const baseFog = new THREE.Color(), tmpC = new THREE.Color();
  function update(t, st, cam) {
    // fire
    let nf = 0, nf2 = 0;
    for (const f of fires) {
      const on = life(t, f.t0, f.t1, 1.5); if (on <= 0) continue;
      for (const [x, y, z, ph, h] of f.pts) {
        const fl = 0.7 + 0.3 * Math.sin(t * 13 + ph * 40) * Math.sin(t * 7.3 + ph * 17), s = on * (0.6 + ph * 0.6);
        _p.set(x, y - 2, z); _s.set(2.6 * s, h * fl * s, 2.6 * s); FLAME.setMatrixAt(nf++, _m.compose(_p, _q, _s));
        if (ph < 0.6) { _s.set(1.4 * s, h * 0.6 * fl * s, 1.4 * s); FLAME2.setMatrixAt(nf2++, _m.compose(_p, _q, _s)); }
      }
    }
    FLAME.count = nf; FLAME2.count = nf2; FLAME.instanceMatrix.needsUpdate = FLAME2.instanceMatrix.needsUpdate = true;
    // smoke columns (dark) and dust (pale)
    const column = (mesh, list, perCol, k0) => {
      let k = k0;
      for (const c of list) {
        const lf = ramp(t, c.t0, c.t0 + 1.2) * (1 - ramp(t, c.t1, c.t1 + 3)); if (lf <= 0) continue;
        const big = c.big ? 1.8 : 1, y0 = heightAt(c.x, c.z);
        for (let j = 0; j < perCol; j++) {
          const ph = ((t - c.t0) * (c.speed || 0.12) + j / perCol + (c.ph || 0)) % 1, sc = (6 + ph * 38) * big;
          const k2 = sc * lf * (1 - Math.pow(ph, 3)) * Math.min(1, ph * 5);
          _p.set(c.x + ph * 160 * big + Math.sin(j * 2.1 + t * 0.4) * 6, y0 + 8 + ph * 260 * big, c.z - ph * 70 * big + Math.cos(j * 1.7) * 6);
          _s.set(k2, k2 * 0.85, k2); mesh.setMatrixAt(k++, _m.compose(_p, _q, _s));
        }
      }
      return k;
    };
    SMOKE.count = column(SMOKE, smokes, 26, 0); SMOKE.instanceMatrix.needsUpdate = true;
    LSMOKE.count = column(LSMOKE, dusts, 18, 0); LSMOKE.instanceMatrix.needsUpdate = true;
    // people
    let np = 0;
    for (const c of crowds) {
      const on = life(t, c.t0, c.t1, 1.6); if (on <= 0) continue;
      for (const [x, y, z, ph] of c.pts) {
        if (ph > on) continue;
        const bob = Math.abs(Math.sin(t * 6 + ph * 50)) * 0.3;
        _p.set(x + Math.sin(t * 0.7 + ph * 9) * 0.8, y + bob, z); _s.set(1.3, 2.2, 1.3);
        PEOPLE.setMatrixAt(np, _m.compose(_p, _q, _s)); PEOPLE.setColorAt(np++, _c.set(PC[Math.floor(ph * 997) % PC.length]));
      }
    }
    for (const a of armies) {
      const on = life(t, a.t0, a.t1, 1.5); if (on <= 0) continue;
      const u = sm(ramp(t, a.t0, a.t1)) * 0.85, cols = 6;
      for (let k = 0; k < a.n; k++) {
        const row = Math.floor(k / cols), col = k % cols, [x, z, h, L] = along(a.path, clamp(u - row * 3.2 / Math.max(1, along(a.path, 0)[3])));
        const ox = Math.cos(h + Math.PI / 2) * (col - cols / 2) * 2.6, oz = Math.sin(h + Math.PI / 2) * (col - cols / 2) * 2.6;
        if (k / a.n > on) continue;
        _p.set(x + ox, heightAt(x + ox, z + oz) + Math.abs(Math.sin(t * 7 + k)) * 0.4, z + oz); _s.set(1.4, 2.3, 1.4);
        PEOPLE.setMatrixAt(np, _m.compose(_p, _q, _s)); PEOPLE.setColorAt(np++, _c.set(k % 37 === 0 ? (a.flag || "#c8102e") : a.color));
      }
    }
    PEOPLE.count = np; PEOPLE.instanceMatrix.needsUpdate = true; if (PEOPLE.instanceColor) PEOPLE.instanceColor.needsUpdate = true;
    // ships
    let ns = 0;
    for (const f of fleets) {
      const on = life(t, f.t0, f.t1, 1.5); if (on <= 0) continue;
      const u = ramp(t, f.t0, f.t1);
      for (let k = 0; k < f.n; k++) {
        const [x, z, h] = along(f.path, clamp(u - k * 0.035)), L = f.len * (0.8 + hash2(k, 3) * 0.4) * on, ox = ((k % 3) - 1) * 26, ry = -h;
        _q.setFromAxisAngle(_up, ry); _p.set(x + Math.sin(h) * ox, -0.6 + Math.sin(t * 1.3 + k) * 0.3, z - Math.cos(h) * ox);
        _s.set(L, 3.2 * on, L * 0.26); HULL.setMatrixAt(ns, _m.compose(_p, _q, _s));
        _p.y += 3; _s.set(L * 0.55, (f.sail === false ? 0.01 : L * 0.75) * on, 1); SAIL.setMatrixAt(ns++, _m.compose(_p, _q, _s));
      }
    }
    HULL.count = SAIL.count = ns; HULL.instanceMatrix.needsUpdate = SAIL.instanceMatrix.needsUpdate = true; _q.identity();
    // fireworks: each burst is a sphere of sparks that expands, falls and fades
    let nk = 0;
    for (const s of shows) for (const b of s.bursts) {
      const a = t - b.t; if (a < 0 || a > 2.2) continue;
      const rnd = mulberry32(b.seed), ex = sm(clamp(a / 0.9)), fade = 1 - clamp((a - 1.1) / 1.1);
      for (let k = 0; k < 70; k++) {
        const th = rnd() * 6.283, ph = Math.acos(2 * rnd() - 1), r = b.r * ex * (0.8 + rnd() * 0.3);
        _p.set(b.x + Math.sin(ph) * Math.cos(th) * r, b.y + Math.cos(ph) * r - a * a * 9, b.z + Math.sin(ph) * Math.sin(th) * r);
        const sz = 1.8 * fade + 0.2; _s.set(sz, sz, sz); SPARK.setMatrixAt(nk, _m.compose(_p, _q, _s)); SPARK.setColorAt(nk++, _c.set(b.c));
      }
    }
    SPARK.count = nk; SPARK.instanceMatrix.needsUpdate = true; if (SPARK.instanceColor) SPARK.instanceColor.needsUpdate = true;
    // race cars
    let nc = 0;
    for (const r of races) {
      const on = life(t, r.t0, r.t1, 0.8); if (on <= 0) continue;
      const L = along(r.path, 0)[3];
      for (let k = 0; k < r.n; k++) {
        const u = ((t - r.t0) * r.speed * (1 - k * 0.012)) / L - k * 0.018, [x, z, h] = along(r.path, u);
        _q.setFromAxisAngle(_up, -h); _p.set(x, heightAt(x, z) - 0.2, z); _s.set(on, on, on);
        CAR.setMatrixAt(nc, _m.compose(_p, _q, _s)); CAR.setColorAt(nc++, _c.set(r.colors ? r.colors[k % r.colors.length] : "#c8102e"));
      }
    }
    CAR.count = nc; CAR.instanceMatrix.needsUpdate = true; if (CAR.instanceColor) CAR.instanceColor.needsUpdate = true; _q.identity();
    // aircraft
    let na = 0;
    for (const f of flights) {
      const u = ramp(t, f.t0, f.t1); if (u <= 0 || u >= 1) continue;
      const h = Math.atan2(f.to[1] - f.from[1], f.to[0] - f.from[0]);
      for (let k = 0; k < f.n; k++) {
        const ox = ((k % 3) - 1) * 40 - Math.floor(k / 3) * 30, x = lerp(f.from[0], f.to[0], u) + Math.cos(h) * ox, z = lerp(f.from[1], f.to[1], u) + Math.sin(h) * ox + ((k % 3) - 1) * 35;
        _q.setFromAxisAngle(_up, -h); _p.set(x, f.alt + (k % 2) * 15, z); _s.set(2.4, 2.4, 2.4); _m.compose(_p, _q, _s);
        for (const pm of PL) pm.setMatrixAt(na, _m); na++;
      }
    }
    for (const pm of PL) { pm.count = na; pm.instanceMatrix.needsUpdate = true; } _q.identity();
    // sky: light, fog, rain and snow
    let dark = 0, storm = 0, snow = 0;
    for (const s of skies) {
      const v = life(t, s.t0, s.t1, s.fade || 1.5);
      if (s.kind === "night" || s.kind === "eclipse") dark = Math.max(dark, v * (s.kind === "eclipse" ? 0.9 : 0.75));
      if (s.kind === "storm") { storm = Math.max(storm, v); dark = Math.max(dark, v * 0.45); }
      if (s.kind === "winter") snow = Math.max(snow, v);
    }
    st.sun.intensity *= 1 - dark * 0.9; st.hemi.intensity *= 1 - dark * 0.75;
    if (dark > 0 || storm > 0) { tmpC.copy(st.scene.fog.color); st.scene.fog.color.lerp(tmpC.set(storm > dark ? "#5c6470" : "#141a2a"), Math.max(dark, storm) * 0.8); if (st.scene.background && st.scene.background.isColor) st.scene.background.copy(st.scene.fog.color); }
    let nr = 0, nsn = 0;
    if ((storm > 0 || snow > 0) && cam) {
      const rnd = mulberry32(7), cx = cam.tgt.x, cz = cam.tgt.z, R = Math.min(900, cam.dist * 0.7);
      for (let k = 0; k < 2400; k++) {
        const x = cx + (rnd() - 0.5) * 2 * R, z = cz + (rnd() - 0.5) * 2 * R, ph = rnd();
        if (storm > 0 && k < 2400 * storm) { const y = ((ph * 400 - t * 260) % 400 + 400) % 400; _p.set(x, y, z); _s.set(1, 1, 1); RAIN.setMatrixAt(nr++, _m.compose(_p, _q, _s)); }
        if (snow > 0 && k < 2400 * snow) { const y = ((ph * 300 - t * 30) % 300 + 300) % 300; _p.set(x + Math.sin(t + k) * 4, y, z); _s.set(1, 1, 1); SNOWF.setMatrixAt(nsn++, _m.compose(_p, _q, _s)); }
      }
    }
    RAIN.count = nr; SNOWF.count = nsn; RAIN.instanceMatrix.needsUpdate = SNOWF.instanceMatrix.needsUpdate = true;
    // earthquake shake
    const shake = V();
    for (const q of quakes) { const v = life(t, q.t0, q.t1, 0.4); if (v > 0) shake.set(Math.sin(t * 61) * 4, Math.sin(t * 47 + 1) * 3, Math.cos(t * 53) * 4).multiplyScalar(v * (q.amp || 1)); }
    return { shake, snow, dark, storm };
  }
  return { fire, smoke, dust, crowd, army, fleet, fireworks, race, planes, quake, sky, cue, update, cues };
}
