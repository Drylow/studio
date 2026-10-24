import * as THREE from "three";
import {
  clamp, lerp, ramp, sm, V, mulberry32, hash2, vnoise, fbm, pw, pl, inv, M4, NEVER, U, STD, growMesh, unitBox, facet,
  createStage, rasterGround, GROUND_GLSL, landmarks, cameraPath, hudDriver, flames, puffs,
} from "./engine.js";

// Ep01 "BABYLON – 3D TIMELAPSE – 1900 BC to AD 200". See SPEC.md for the beats and the fact-checked captions.
// World metres, x east, z south (north = -z). The Euphrates runs N→S through the city; the camera mostly looks north.

export const W = 1920, H = 1080, SS = 1.5, DUR = 305;

// ---------------- land: a flat plain, the Euphrates, irrigation canals ----------------
const riverX = (z) => -350 + 55 * Math.sin(z / 850 + 0.6) + 25 * Math.sin(z / 310 + 1.3) + 160 * Math.sin(z / 2600 - 0.4) * sm(clamp((Math.abs(z) - 1400) / 1600));
const RIVER_HALF = 75;
const CANALS = [
  [[0, -1480], [900, -1560], [1900, -1640], [3200, -1800], [4600, -1900]],
  [[0, 1350], [800, 1450], [1700, 1620], [3000, 1900], [4600, 2100]],
  [[0, -1150], [-900, -1180], [-2000, -1300], [-3400, -1450], [-4600, -1500]],
  [[0, 1600], [-1000, 1700], [-2200, 1950], [-3500, 2200], [-4600, 2300]],
].map((pts) => pts.map(([x, z], i) => [i === 0 ? riverX(z) : x, z]));
const CANAL_HALF = 9;
function segDist(x, z, ax, az, bx, bz) { const dx = bx - ax, dz = bz - az, u = clamp(((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz || 1)); return Math.hypot(x - ax - dx * u, z - az - dz * u); }
function canalDist(x, z) { let d = 1e9; for (const c of CANALS) for (let i = 1; i < c.length; i++) d = Math.min(d, segDist(x, z, c[i - 1][0], c[i - 1][1], c[i][0], c[i][1])); return d; }
const PLAIN = 2.4;
function heightAt(x, z) {
  let h = PLAIN + (fbm(x * 0.0016 + 4, z * 0.0016 - 7) - 0.5) * 0.9;
  const dr = Math.abs(x - riverX(z));
  if (dr < RIVER_HALF + 26) h = Math.min(h, dr < RIVER_HALF ? lerp(-4.6, -0.35, (dr / RIVER_HALF) ** 2) : lerp(-0.35, h, sm((dr - RIVER_HALF) / 26)));
  const dc = canalDist(x, z);
  if (dc < CANAL_HALF + 6) h = Math.min(h, dc < CANAL_HALF ? -1.4 : lerp(-1.4, h, sm((dc - CANAL_HALF) / 6)));
  return h;
}
const isWet = (x, z) => Math.abs(x - riverX(z)) < RIVER_HALF + 30 || canalDist(x, z) < CANAL_HALF + 8;
function wetness(x, z) {                          // irrigated belt (fields and palm groves)
  const dr = Math.abs(x - riverX(z)), dc = canalDist(x, z);
  const w = Math.max(1 - sm(clamp((dr - 90) / 1300)), 1 - sm(clamp((dc - 12) / 650)));
  return clamp(w * (0.75 + 0.5 * fbm(x * 0.0012 + 9, z * 0.0012)) - 0.08);
}

// ---------------- city plan ----------------
const CORE = { x: 40, z: -90 };                 // the old town round the sanctuary of Marduk
const RECT = { x0: -1000, x1: 1000, z0: -800, z1: 800 };   // Neo-Babylonian inner city
const inRect = (x, z, pad = 0) => x > RECT.x0 + pad && x < RECT.x1 - pad && z > RECT.z0 + pad && z < RECT.z1 - pad;
const OUTER = [[riverX(-2100) + 95, -2100], [700, -2020], [1600, -950], [1760, 200], [1120, 1180], [riverX(1260) + 95, 1260]];
function inPoly(x, z, P) { let c = false; for (let i = 0, j = P.length - 1; i < P.length; j = i++) { const [xi, zi] = P[i], [xj, zj] = P[j]; if ((zi > z) !== (zj > z) && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) c = !c; } return c; }
const inOuter = (x, z) => x > riverX(z) && inPoly(x, z, OUTER);
const inCity = (x, z) => inRect(x, z) || inOuter(x, z);
// Old Babylonian walled town (east bank)
const OBW = { x1: 640, z0: -610, z1: 590 };

// sites (no houses), centres and half sizes
const ZIG = { x: -150, z: -170 };                 // Etemenanki
const ESA = { x: -150, z: 62 };                   // Esagila
const PAL = { x: -150, z: -640 };                 // Southern Palace
const NPAL = { x: -150, z: -930 };                // Northern Palace (outside the inner wall)
const SPAL = { x: -60, z: -1960 };                // Summer Palace (north tip of the outer wall)
const GATE = { x: -10, z: RECT.z0 };              // Ishtar Gate
const BRIDGE_Z = -22;
const SITES = [
  { x: ZIG.x, z: ZIG.z, hx: 140, hz: 140 }, { x: ESA.x, z: ESA.z, hx: 100, hz: 74 }, { x: PAL.x, z: PAL.z, hx: 132, hz: 112 },
  { x: NPAL.x, z: NPAL.z, hx: 120, hz: 75 }, { x: SPAL.x, z: SPAL.z, hx: 95, hz: 75 },
  { x: GATE.x, z: -980, hx: 22, hz: 190 }, { x: GATE.x, z: -420, hx: 20, hz: 390 }, { x: -150, z: BRIDGE_Z, hx: 140, hz: 15 },
];
const onSite = (x, z, pad = 0) => SITES.some((s) => Math.abs(x - s.x) < s.hx + pad && Math.abs(z - s.z) < s.hz + pad);

// ---------------- time ----------------
const RK = [[0, 240], [9, 270], [28, 560], [46, 720], [86, 760], [136, 800], [160, 1500], [200, 2900], [DUR, 2900]];
const DK = [[0, 0.4], [28, 0.66], [46, 0.8], [86, 0.82], [136, 0.82], [185, 0.97], [DUR, 1]];
const cityR = (t) => pw(RK, t), density = (t) => pw(DK, t);
const YK = [[0, -1900], [9, -1894], [28, -1792], [46, -1600], [48.4, -1595], [53, -1595], [86, -1155], [93, -729], [97, -689], [118, -689], [119.5, -681], [136, -626], [206, -562], [214, -545], [219, -539], [227, -539], [244, -331], [249, -323], [257, -323], [262, -305], [280, -141], [296, 150], [DUR, 200]];
const yearAt = (t) => { const y = Math.round(pl(YK, t)); return y === 0 ? 1 : y; };
const T = {
  obWall: [13, 19], esa1: [20, 25.5], sack: 48.4, kassiteRebuild: 56, zig1: [64, 70],
  ruin: 98.4, flood: [104, 108.5, 112, 117.5], esarhaddon: 120.5,
  walls: [138, 146.5], zig2: 150, esa2: [157, 163], palace: [167, 174], gate: [177, 181], pway: [178.5, 184], gardens: [185, 190.5], bridge: [190, 193.5], npal: [194, 197.5], outer: [194, 202.5], spal: [197, 201],
  camp: [207, 213, 226, 229], march: [219.5, 227], demolish: 253.5, decline: [262, 292],
};
const ERAS = [
  { t: 0, name: "THE EUPHRATES", flag: null },
  { t: 9, name: "AMORITE BABYLON", flag: "amorite" },
  { t: 28, name: "BABYLON OF HAMMURABI", flag: "hammurabi" },
  { t: 54, name: "KASSITE BABYLON", flag: "kassite" },
  { t: 93, name: "ASSYRIAN BABYLONIA", flag: "assyria" },
  { t: 136, name: "NEO-BABYLONIAN EMPIRE", flag: "neobab" },
  { t: 220, name: "ACHAEMENID BABYLON", flag: "persia" },
  { t: 244, name: "HELLENISTIC BABYLON", flag: "hellenic" },
  { t: 280, name: "PARTHIAN BABYLONIA", flag: "parthia" },
];
const sun16 = (cx, cy, r0, r1, n, col) => { let d = ""; for (let i = 0; i < n; i++) { const a = (i / n) * Math.PI * 2, b = a + Math.PI / n * 0.5, c = a - Math.PI / n * 0.5; d += `M${cx + Math.cos(c) * r0} ${cy + Math.sin(c) * r0} L${cx + Math.cos(a) * r1} ${cy + Math.sin(a) * r1} L${cx + Math.cos(b) * r0} ${cy + Math.sin(b) * r0}Z`; } return `<path d="${d}" fill="${col}"/>`; };
const FLAGS = {
  amorite: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#8a5a2b"/>${sun16(70, 42, 10, 26, 8, "#f0cf6a")}<circle cx="70" cy="42" r="11" fill="#f0cf6a"/></svg>`,
  hammurabi: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#23406b"/>${sun16(70, 36, 9, 22, 8, "#e9c35a")}<circle cx="70" cy="36" r="10" fill="#e9c35a"/><rect x="40" y="64" width="60" height="4" fill="#e9c35a"/><circle cx="110" cy="66" r="6" fill="none" stroke="#e9c35a" stroke-width="3"/></svg>`,
  kassite: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#8f2f24"/><circle cx="70" cy="42" r="24" fill="none" stroke="#f1e6cf" stroke-width="4"/><path d="M70 20 V64 M48 42 H92" stroke="#f1e6cf" stroke-width="7"/></svg>`,
  assyria: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#3b3f4a"/><circle cx="70" cy="40" r="10" fill="none" stroke="#d9b45c" stroke-width="4"/><path d="M58 40 L22 30 L26 36 L20 40 L28 44 L24 48 Z M82 40 L118 30 L114 36 L120 40 L112 44 L116 48 Z M64 50 L70 64 L76 50Z" fill="#d9b45c"/></svg>`,
  neobab: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#1f4f9a"/><rect x="0" y="0" width="140" height="10" fill="#e8dcc0"/><rect x="0" y="74" width="140" height="10" fill="#e8dcc0"/>${[0, 1, 2, 3, 4, 5, 6, 7].map((i) => `<ellipse cx="70" cy="42" rx="5" ry="15" transform="rotate(${i * 22.5} 70 42)" fill="#e2b54e"/>`).join("")}<circle cx="70" cy="42" r="5" fill="#f4ead4"/></svg>`,
  persia: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#9a1f2a"/><path d="M70 22 L76 34 L104 30 L80 44 L86 64 L70 54 L54 64 L60 44 L36 30 L64 34Z" fill="#e8b84a"/></svg>`,
  hellenic: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#3d2a63"/>${sun16(70, 42, 8, 30, 16, "#e8c25a")}<circle cx="70" cy="42" r="8" fill="#e8c25a"/></svg>`,
  parthia: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#2f5a3c"/><path d="M78 20 A22 22 0 1 0 78 64 A17 17 0 1 1 78 20Z" fill="#e5c15c"/>${sun16(96, 42, 4, 11, 8, "#e5c15c")}</svg>`,
};
const TITLE = [1.2, 7.5];
const LANDMARKS = [
  { a: 23.5, b: 29.5, text: "ESAGILA" },
  { a: 66, b: 72, text: "THE FIRST ZIGGURAT" },
  { a: 143, b: 148.5, text: "THE WALLS OF BABYLON" },
  { a: 156, b: 163, text: "ETEMENANKI" },
  { a: 170.5, b: 176, text: "THE SOUTHERN PALACE" },
  { a: 178, b: 182.8, text: "THE ISHTAR GATE" },
  { a: 188.5, b: 192.8, text: "THE HANGING GARDENS" },
  { a: 208, b: 213.6, text: "THE ARMY OF CYRUS" },
];
const CAPTIONS = [
  { a: 33, b: 40, lines: ["Hammurabi made Babylon the capital of an empire", "and issued one of history's best-known law codes."] },
  { a: 49.2, b: 55, lines: ["In 1595 BC the Hittite king Mursili I", "sacked Babylon."] },
  { a: 74, b: 81, lines: ["The Kassites renamed the city Karduniash", "and ruled it for over four centuries."] },
  { a: 105.5, b: 113, lines: ["In 689 BC the Assyrian king Sennacherib razed Babylon", "and threw its rubble into the canals."] },
  { a: 164, b: 170.5, lines: ["Etemenanki, “Temple of the Foundation of Heaven and Earth”,", "stood on a base about 91 m square: a likely model for the Tower of Babel."] },
  { a: 183, b: 188.3, lines: ["Faced with blue glazed bricks, the Ishtar Gate and the Processional Way", "showed lions, bulls and dragons."] },
  { a: 193.2, b: 199.5, lines: ["Later writers credited Nebuchadnezzar with the Hanging Gardens,", "but no Babylonian text mentions them."] },
  { a: 221, b: 228, lines: ["In 539 BC Cyrus the Great took Babylon", "with little or no fighting."] },
  { a: 246, b: 252.5, lines: ["Alexander the Great died here in 323 BC,", "in the palace of Nebuchadnezzar."] },
  { a: 255, b: 261.5, lines: ["Alexander had the ziggurat torn down to rebuild it,", "but he died before the work began."] },
  { a: 264, b: 271, lines: ["Seleucus I founded Seleucia on the Tigris,", "and Babylon's people slowly moved away."] },
  { a: 284, b: 291, lines: ["Its ruins lie 85 km south of Baghdad;", "UNESCO listed them as a World Heritage Site in 2019."] },
];
const CARDS = [
  { a: 98, b: 104, kicker: "BABYLON", text: "THE DESTRUCTION OF 689 BC" },
  { a: 136.5, b: 142.3, kicker: "605 – 562 BC", text: "THE AGE OF NEBUCHADNEZZAR" },
  { a: 214, b: 220.4, kicker: "539 BC", text: "THE FALL OF BABYLON" },
  { a: 296, b: 303.2, kicker: "1900 BC – AD 200", text: "BABYLON" },
];

// ---------------- build ----------------
export function buildVideo(canvas, hud) {
  const st = createStage(canvas, { W, H, SS, fog: "#d8d2c2", sunColor: "#fff1d8", sunDir: [-0.6, 0.66, -0.45], hemiSky: "#d5e4f5", hemiGround: "#9a8a68", hemiI: 1.15, sunI: 3.2, saturation: -0.04 });
  const { scene } = st;
  const { box, grow, update: updateLM } = landmarks();
  const rnd = mulberry32(2024);

  // ---------- roads: a gridded city (straight streets at right angles), plus tracks into the fields ----------
  const segs = [];
  const roadLead = (d) => inv(cityR, Math.max(0, d * 0.97 - 15), 0, DUR);
  const distCore = (x, z) => Math.hypot(x - CORE.x, z - CORE.z);
  function addLine(ax, az, bx, bz, w, extra = 0, step = 20, track = false) {
    const n = Math.max(1, Math.round(Math.hypot(bx - ax, bz - az) / step));
    for (let i = 0; i < n; i++) {
      const u0 = i / n, u1 = (i + 1) / n;
      const x0 = lerp(ax, bx, u0), z0 = lerp(az, bz, u0), x1 = lerp(ax, bx, u1), z1 = lerp(az, bz, u1);
      const mx = (x0 + x1) / 2, mz = (z0 + z1) / 2;
      if (isWet(mx, mz) || onSite(mx, mz, -4)) continue;
      const city = inCity(mx, mz) || distCore(mx, mz) < 760;
      segs.push({ track, ax: x0, az: z0, bx: x1, bz: z1, w, ba: (city ? roadLead(distCore(x0, z0)) : 4) + extra, bb: (city ? roadLead(distCore(x1, z1)) : 4) + extra });
    }
  }
  const wob = (k, s) => (hash2(k, s) - 0.5) * 8;
  for (let x = RECT.x0 + 60; x < 1760; x += 118) addLine(x + wob(1, x), -2050, x + wob(2, x), 1200, x % 236 < 118 ? 6 : 4.5);
  for (let z = -2060; z < 1200; z += 104) addLine(-1000, z + wob(3, z), 1800, z + wob(4, z), z % 208 < 104 ? 6 : 4.5);
  // main avenues to the gates
  addLine(-1000, -300, 1800, -300, 9); addLine(-1000, 320, 1800, 320, 9); addLine(420, -2050, 420, 1200, 9);
  // tracks out to the fields
  for (const [ax, az, bx, bz] of [[1000, -300, 3600, -500], [1000, 320, 3500, 800], [-1000, -300, -3600, -200], [-1000, 320, -3600, 700], [600, -800, 900, -3600], [200, 800, 600, 3600]]) addLine(ax, az, bx, bz, 5, 0, 30, true);
  // the road segments only exist where houses can be (inside the walls) or as field tracks
  const kept = segs.filter((s) => s.track ? !inCity((s.ax + s.bx) / 2, (s.az + s.bz) / 2) : inCity((s.ax + s.bx) / 2, (s.az + s.bz) / 2) || distCore((s.ax + s.bx) / 2, (s.az + s.bz) / 2) < 720);
  segs.length = 0; segs.push(...kept);
  const RH = new Map(), RC = 40;
  segs.forEach((s, i) => {
    const pad = s.w / 2 + 6;
    for (let gx = Math.floor((Math.min(s.ax, s.bx) - pad) / RC); gx <= Math.floor((Math.max(s.ax, s.bx) + pad) / RC); gx++)
      for (let gz = Math.floor((Math.min(s.az, s.bz) - pad) / RC); gz <= Math.floor((Math.max(s.az, s.bz) + pad) / RC); gz++) { const k = gx * 100003 + gz; (RH.get(k) || RH.set(k, []).get(k)).push(i); }
  });
  function nearestRoad(x, z) {
    const list = RH.get(Math.floor(x / RC) * 100003 + Math.floor(z / RC)) || [];
    let best = { d: 1e9, s: null, u: 0 };
    for (const i of list) { const s = segs[i], dx = s.bx - s.ax, dz = s.bz - s.az, u = clamp(((x - s.ax) * dx + (z - s.az) * dz) / (dx * dx + dz * dz || 1)); const d = Math.hypot(x - s.ax - dx * u, z - s.az - dz * u) - s.w / 2; if (d < best.d) best = { d, s, u }; }
    return best;
  }

  // ---------- wall lines ----------
  const rectLine = (pad) => [[RECT.x0 - pad, RECT.z0 - pad], [RECT.x1 + pad, RECT.z0 - pad], [RECT.x1 + pad, RECT.z1 + pad], [RECT.x0 - pad, RECT.z1 + pad], [RECT.x0 - pad, RECT.z0 - pad]];
  const obLine = [];
  for (let z = OBW.z0; z <= OBW.z1; z += 20) obLine.push([riverX(z) + RIVER_HALF + 30, z]);
  obLine.push([OBW.x1, OBW.z1], [OBW.x1, OBW.z0], [riverX(OBW.z0) + RIVER_HALF + 30, OBW.z0]);
  const outerLine = OUTER.map((p) => p.slice());
  const nearLine = (x, z, L, pad) => { for (let i = 1; i < L.length; i++) if (segDist(x, z, L[i - 1][0], L[i - 1][1], L[i][0], L[i][1]) < pad) return true; return false; };

  // ---------- houses: each lot lives, burns, collapses and is rebuilt across the eras ----------
  const SP = 17;
  const lots = [];
  for (let gx = -64; gx <= 112; gx++) for (let gz = -128; gz <= 82; gz++) {
    const x = gx * SP + (rnd() - 0.5) * 5, z = gz * SP + (rnd() - 0.5) * 5, rank = rnd(), r1 = rnd(), r2 = rnd(), r3 = rnd(), r4 = rnd();
    if (!(inCity(x, z) || (distCore(x, z) < 700 && x > riverX(z)))) continue;
    if (Math.abs(x - riverX(z)) < RIVER_HALF + 32 || canalDist(x, z) < 22) continue;
    if (onSite(x, z, 10)) continue;
    if (nearLine(x, z, rectLine(0), 30) || nearLine(x, z, rectLine(12), 26) || nearLine(x, z, rectLine(45), 34) || nearLine(x, z, outerLine, 24) || nearLine(x, z, obLine, 12)) continue;
    const nr = nearestRoad(x, z);
    if (!nr.s || nr.d < 2.6) continue;
    if (nr.d > 30 && fbm(x * 0.008, z * 0.008) < 0.42) continue;       // gardens
    const ang = -Math.atan2(nr.s.bz - nr.s.az, nr.s.bx - nr.s.ax);
    lots.push({ x, z, rank, r1, r2, r3, r4, ang: Math.round(ang / (Math.PI / 2)) * (Math.PI / 2) + (r4 - 0.5) * 0.05, road: lerp(nr.s.ba, nr.s.bb, nr.u), d: distCore(x, z), n: fbm(x * 0.006, z * 0.006) });
  }
  const lives = [];                                // {lot, b, d, ign, style}
  const fireRecs = [], dustCols = [];
  for (const L of lots) {
    const westBank = L.x < riverX(L.z);
    let b = Math.max(inv(cityR, L.d * (0.9 + 0.2 * L.n), 0, DUR), inv(density, L.rank * 0.97, 0, DUR), L.road + 0.3, westBank ? 58 + L.r1 * 20 : 0) + L.r2 * 1.4;
    if (!inCity(L.x, L.z) && b > 120) continue;                       // outside the later walls only in the early town
    const push = (o) => { lives.push({ lot: L, ...o }); return o; };
    let cur = b < DUR ? { b, d: NEVER, ign: NEVER, style: b < 136 ? "ob" : "nb" } : null;
    // 1595 BC: the Hittite sack (most of the town burns)
    if (cur && cur.b < T.sack - 0.5 && L.r3 < 0.72) {
      const hit = T.sack + L.d / 110 + L.n * 1.5;
      cur.ign = hit; cur.d = hit + 2.4 + L.r1 * 1.4; push(cur);
      const rb = Math.max(T.kassiteRebuild + L.d / 38 + L.r2 * 7, inv(cityR, L.d, 0, DUR));
      cur = { b: rb, d: NEVER, ign: NEVER, style: "ob" };
    }
    // 689 BC: Sennacherib razes the city; ruins, then the flood; Esarhaddon and Nabopolassar rebuild
    if (cur && cur.b < T.ruin) {
      const hit = T.ruin + L.d / 140 + L.n * 1.6 + L.r4 * 0.8;
      if (L.r1 < 0.65) cur.ign = hit;
      cur.d = hit + (L.r1 < 0.65 ? 2.2 + L.r3 : 0.4); push(cur);
      const rb = Math.max(L.rank < 0.42 ? T.esarhaddon + L.d / 32 + L.r2 * 8 : 137 + L.d / 26 + L.r2 * 10, inv(cityR, L.d, 0, DUR));
      push({ b: cur.d + 0.1, d: Math.min(rb - 0.4, T.esarhaddon + 10 + L.r3 * 14), ign: NEVER, style: "ruin" });
      if (L.r1 < 0.3) dustCols.push({ x: L.x, y: heightAt(L.x, L.z) + 3, z: L.z, t0: cur.d - 0.6, t1: cur.d + 1.8, ph: L.r2, rise: 26, spread: 18, size0: 3, speed: 0.4, wind: [30, -10] });
      cur = { b: rb, d: NEVER, ign: NEVER, style: rb < 136 ? "ob" : "nb" };
    }
    if (!cur || cur.b >= DUR) continue;
    // the slow end: from the edges inwards, a village survives round Esagila
    const village = Math.hypot(L.x - ESA.x, L.z - ESA.z) < 330 && L.rank < 0.32;
    if (!village) {
      const dd = T.decline[0] + (1 - clamp(L.d / 2600)) * (T.decline[1] - T.decline[0] - 4) + L.r3 * 4;
      if (cur.b < dd) { cur.d = dd; push(cur); push({ b: dd + 0.1, d: NEVER, ign: NEVER, style: "ruin" }); }
    } else push(cur);
  }
  // instances
  const PAL_OB = ["#cbab7f", "#d5b88c", "#c2a176", "#dcc39c", "#c8a77b"], ROOF_OB = ["#9a7e59", "#a68862", "#927652"];
  const PAL_NB = ["#e2cfac", "#ece0c6", "#d8bf96", "#f2ebdc", "#dcc39d", "#efe7d6"], ROOF_NB = ["#a8906b", "#b39a73", "#9c8564"];
  const wallR = [], roofR = [], upR = [], ruinR = [];
  const cW = new THREE.Color(), cR = new THREE.Color();
  for (const l of lives) {
    const L = l.lot, y0 = heightAt(L.x, L.z) - 0.6, t = [l.b, l.d, l.ign, L.r4];
    if (l.style === "ruin") { ruinR.push({ m: M4(L.x, y0, L.z, L.ang + 0.3, 10 + L.r1 * 6, 1, 10 + L.r2 * 6), c: new THREE.Color(["#a58c68", "#9c8463", "#ad9471"][Math.floor(L.r3 * 3)]), t, h: [0, 1.6 + L.r2 * 1.2] }); continue; }
    const nb = l.style === "nb", core = 1 - clamp(L.d / 1400);
    const w = (nb ? 10 : 8) + L.r1 * 5, d = (nb ? 10 : 8) + L.r2 * 5, hgt = (nb ? 5 : 3.8) + L.r3 * 2.4 + (nb ? core * 2 : 0);
    cW.set((nb ? PAL_NB : PAL_OB)[Math.floor(L.r1 * 5.999) % (nb ? PAL_NB : PAL_OB).length]);
    cR.set((nb ? ROOF_NB : ROOF_OB)[Math.floor(L.r2 * 2.999)]);
    wallR.push({ m: M4(L.x, y0, L.z, L.ang, w, 1, d), c: cW.clone(), t, h: [0, hgt + 0.6] });
    roofR.push({ m: M4(L.x, y0, L.z, L.ang, w - 1.2, 1, d - 1.2), c: cR.clone(), t, h: [hgt + 0.55, 0.12] });
    if (L.r4 < (nb ? 0.32 : 0.15)) upR.push({ m: M4(L.x + (L.r1 - 0.5) * 2, y0, L.z + (L.r2 - 0.5) * 2, L.ang, w * 0.42, 1, d * 0.42), c: cW.clone().multiplyScalar(1.03), t: [l.b + 0.3, l.d, l.ign, L.r4], h: [hgt + 0.5, 2.6] });
    if (l.ign < NEVER) {
      const top = y0 + hgt + 0.6;
      fireRecs.push({ m: M4(L.x, top - 1.5, L.z, L.r1 * 6, 4, 9 + L.r2 * 6, 4), t: [l.ign, l.d + 0.5, l.ign, L.r3] });
      fireRecs.push({ m: M4(L.x + 1.5, top - 1.5, L.z - 1, L.r2 * 6, 2.4, 6 + L.r3 * 4, 2.4), t: [l.ign + 0.2, l.d + 0.3, l.ign, L.r1 * 0.7 + 0.2], hot: true });
    }
  }
  scene.add(growMesh(unitBox(), STD({ roughness: 0.95 }), "house", wallR));
  scene.add(growMesh(unitBox(), STD({ roughness: 1 }), "house", roofR, { shadow: false }));
  scene.add(growMesh(unitBox(), STD({ roughness: 0.95 }), "house", upR));
  const ruinGeo = new THREE.CylinderGeometry(0.42, 0.5, 1, 7); ruinGeo.translate(0, 0.5, 0);
  scene.add(growMesh(facet(ruinGeo), STD({ roughness: 1, flatShading: true }), "house", ruinR));
  flames(scene, fireRecs.filter((r) => !r.hot), new THREE.Color(2.6, 0.95, 0.18));
  flames(scene, fireRecs.filter((r) => r.hot), new THREE.Color(3.0, 2.0, 0.5));
  // population: alive houses, scaled so the Neo-Babylonian peak reads about 200,000
  const alive = lives.filter((l) => l.style !== "ruin");
  const births = alive.map((l) => l.b).sort((a, b) => a - b), deaths = alive.map((l) => l.d).filter((d) => d < NEVER).sort((a, b) => a - b);
  const countLE = (arr, t) => { let a = 0, b = arr.length; while (a < b) { const m = (a + b) >> 1; if (arr[m] <= t) a = m + 1; else b = m; } return a; };
  const aliveAt = (t) => countLE(births, t - 0.3) - countLE(deaths, t - 0.3);
  let peak = 1; for (let t = 180; t < 250; t += 2) peak = Math.max(peak, aliveAt(t));
  const popAt = (t) => aliveAt(t) * (200000 / peak);

  // ---------- walls: Old Babylonian mud wall; the Neo-Babylonian double wall + moat; the outer wall ----------
  const wSeg = [], wTow = [], wMer = [], wRuin = [], moat = [];
  function buildWall(line, { h, th, tower, towerH, t0, t1, death = NEVER, ruinH = 0, color, skipWater = true, merlons = true, towerEvery = 40 }) {
    let total = 0; const lens = []; for (let i = 1; i < line.length; i++) { const l = Math.hypot(line[i][0] - line[i - 1][0], line[i][1] - line[i - 1][1]); lens.push(l); total += l; }
    let acc = 0, sinceTower = 0;
    const C = new THREE.Color(color), CR = new THREE.Color("#a58d69");
    for (let i = 1; i < line.length; i++) {
      const [ax, az] = line[i - 1], [bx, bz] = line[i], len = lens[i - 1], ang = -Math.atan2(bz - az, bx - ax);
      const n = Math.max(1, Math.round(len / 12));
      for (let k = 0; k < n; k++) {
        const u0 = k / n, u1 = (k + 1) / n, x0 = lerp(ax, bx, u0), z0 = lerp(az, bz, u0), x1 = lerp(ax, bx, u1), z1 = lerp(az, bz, u1);
        const mx = (x0 + x1) / 2, mz = (z0 + z1) / 2, sl = len / n;
        const f = (acc + (k + 0.5) * sl) / total, b = lerp(t0, t1, f);
        const dth = death < NEVER ? death + hash2(Math.round(mx), Math.round(mz)) * 14 : NEVER;
        sinceTower += sl;
        if (skipWater && (Math.abs(mx - riverX(mz)) < RIVER_HALF + 8 || canalDist(mx, mz) < CANAL_HALF + 2)) continue;
        const gate = nearestRoad(mx, mz).d < -1.5;
        const y0 = heightAt(mx, mz) - 1.5;
        if (!gate) {
          wSeg.push({ m: M4(mx, y0, mz, ang, sl + 0.4, 1, th), c: C, t: [b, dth, NEVER, 0], h: [0, h + 1.5] });
          if (merlons) { const nm = Math.floor(sl / 2.6); for (let j = 0; j < nm; j++) { const u = (j + 0.5) / nm; wMer.push({ m: M4(lerp(x0, x1, u), y0, lerp(z0, z1, u), ang, 1.3, 1, th + 0.1), c: C, t: [b + 0.25, dth, NEVER, 0], h: [h + 1.5, 1.5] }); } }
          if (ruinH && dth < NEVER) wRuin.push({ m: M4(mx, y0, mz, ang, sl + 2, 1, th * 1.8), c: CR, t: [dth + 0.2, NEVER, NEVER, 0], h: [0, ruinH + 1.5] });
        }
        if (tower && (sinceTower >= towerEvery || gate)) { sinceTower = 0; wTow.push({ m: M4(mx, y0, mz, ang, tower, 1, tower), c: C.clone().multiplyScalar(1.04), t: [b + 0.2, dth, NEVER, 0], h: [0, towerH + 1.5] }); if (ruinH && dth < NEVER) wRuin.push({ m: M4(mx, y0, mz, ang, tower * 1.3, 1, tower * 1.3), c: CR, t: [dth + 0.2, NEVER, NEVER, 0], h: [0, ruinH + 3] }); }
      }
      acc += len;
    }
  }
  buildWall(obLine, { h: 8, th: 6, tower: 9, towerH: 11, t0: T.obWall[0], t1: T.obWall[1], death: T.ruin + 0.6, color: "#a8895f", towerEvery: 50 });
  buildWall(rectLine(0), { h: 14, th: 6.5, tower: 11, towerH: 19, t0: T.walls[0], t1: T.walls[1], death: 270, ruinH: 3, color: "#cdb48a", towerEvery: 36 });
  buildWall(rectLine(12), { h: 10, th: 3.8, tower: 7, towerH: 13, t0: T.walls[0] + 0.6, t1: T.walls[1] + 0.6, death: 268, ruinH: 2, color: "#d6bf98", towerEvery: 36 });
  buildWall(outerLine, { h: 13, th: 7, tower: 10, towerH: 17, t0: T.outer[0], t1: T.outer[1], death: 266, ruinH: 3, color: "#c9b089", skipWater: true, towerEvery: 50 });
  scene.add(growMesh(unitBox(), STD(), "house", wSeg));
  scene.add(growMesh(unitBox(), STD(), "house", wTow));
  scene.add(growMesh(unitBox(), STD(), "house", wMer, { shadow: false }));
  scene.add(growMesh(facet(ruinGeo), STD({ flatShading: true, roughness: 1 }), "house", wRuin));
  // the moat: flat water strips outside the double wall, dug as the walls rise, dry at the end
  {
    const L = rectLine(45);
    for (let i = 1; i < L.length; i++) {
      const [ax, az] = L[i - 1], [bx, bz] = L[i], len = Math.hypot(bx - ax, bz - az), ang = -Math.atan2(bz - az, bx - ax), n = Math.round(len / 20);
      for (let k = 0; k < n; k++) {
        const u = (k + 0.5) / n, mx = lerp(ax, bx, u), mz = lerp(az, bz, u);
        if (Math.abs(mx - riverX(mz)) < RIVER_HALF + 4) continue;
        const f = (i - 1 + u) / 4, b = lerp(T.walls[0] + 0.5, T.walls[1] + 1, f);
        moat.push({ m: M4(mx, PLAIN - 0.25, mz, ang, len / n + 0.5, 1, 40), c: new THREE.Color("#2f7f88"), t: [b, 282 + hash2(i, k) * 8, NEVER, 0], h: [0, 0.3] });
      }
    }
  }
  scene.add(growMesh(unitBox(), STD({ roughness: 0.2, metalness: 0.05 }), "house", moat, { shadow: false }));

  // ---------- palms and trees (cleared by the city, dying back as the land dries) ----------
  const HC = new Map(), HCS = 18;
  for (const l of lives) if (l.style !== "ruin") { const k = Math.floor(l.lot.x / HCS) * 100003 + Math.floor(l.lot.z / HCS); const v = HC.get(k); if (v === undefined || v > l.b) HC.set(k, l.b); }
  const clearAt = (x, z) => {
    let t = NEVER;
    for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) { const v = HC.get((Math.floor(x / HCS) + dx) * 100003 + Math.floor(z / HCS) + dz); if (v !== undefined) t = Math.min(t, v - 0.35); }
    const nr = nearestRoad(x, z); if (nr.s && nr.d < 4) t = Math.min(t, lerp(nr.s.ba, nr.s.bb, nr.u) - 0.2);
    if (nearLine(x, z, rectLine(0), 32) || nearLine(x, z, rectLine(12), 28) || nearLine(x, z, rectLine(45), 36)) t = Math.min(t, T.walls[0] + 1);
    if (nearLine(x, z, outerLine, 26)) t = Math.min(t, T.outer[0] + 2);
    if (nearLine(x, z, obLine, 14)) t = Math.min(t, T.obWall[0]);
    const siteT = [T.zig1[0] - 0.5, T.esa1[0] - 0.5, T.palace[0] - 0.5, T.npal[0] - 0.5, T.spal[0] - 0.5, T.pway[0] - 0.5, T.pway[0] - 0.5, T.bridge[0] - 0.5];
    SITES.forEach((st2, i) => { if (Math.abs(x - st2.x) < st2.hx + 15 && Math.abs(z - st2.z) < st2.hz + 15) t = Math.min(t, siteT[i]); });
    return t;
  };
  const trunkR = [], crownR = [], bushR = [];
  const rt = mulberry32(7);
  for (let gx = -380; gx <= 380; gx++) for (let gz = -380; gz <= 380; gz++) {
    const x = gx * 11 + (rt() - 0.5) * 8, z = gz * 11 - 300 + (rt() - 0.5) * 8, r1 = rt(), r2 = rt(), r3 = rt();
    const w = wetness(x, z); if (w < 0.42) continue;
    if (isWet(x, z) || Math.abs(x - riverX(z)) < RIVER_HALF + 14) continue;
    const grove = fbm(x * 0.0035 + 2, z * 0.0035 + 11);
    if (grove < 0.55 && r3 > 0.04) continue;
    const y = heightAt(x, z) - 0.3;
    let death = clearAt(x, z);
    if (r2 < 0.72) death = Math.min(death, T.decline[0] + 6 + r1 * 30 + (1 - w) * 10);
    if (death < 0) continue;
    const birth = death < NEVER && death < 0 ? 0 : -1;
    if (r3 < 0.08) { bushR.push({ m: M4(x, y + 2, z, r1 * 6, 3 + r1 * 2, 2.6 + r2, 3 + r1 * 2), c: new THREE.Color(["#5d7a3a", "#6b8442"][r1 < 0.5 ? 0 : 1]), t: [birth, death, NEVER, r1] }); continue; }
    const hgt = 9 + r1 * 6, lean = (r2 - 0.5) * 0.12;
    trunkR.push({ m: M4(x, y, z, r2 * 6, 0.55, hgt, 0.55), c: new THREE.Color("#7a6347"), t: [birth, death, NEVER, r1] });
    crownR.push({ m: M4(x + lean * hgt, y + hgt, z, r1 * 6.28, 4.2 + r2 * 1.6, 2.4, 4.2 + r2 * 1.6), c: new THREE.Color(["#3f6a2f", "#4a7535", "#38612b", "#52783a"][Math.floor(r3 * 4)]), t: [birth, death, NEVER, r1] });
  }
  for (let gx = -110; gx <= 200; gx++) for (let gz = -230; gz <= 150; gz++) {
    const x = gx * 9 + (rt() - 0.5) * 6, z = gz * 9 + (rt() - 0.5) * 6, r1 = rt(), r2 = rt(), r3 = rt();
    if (!inCity(x, z) || fbm(x * 0.008, z * 0.008) > 0.4 || r3 > 0.55) continue;
    if (isWet(x, z) || Math.abs(x - riverX(z)) < RIVER_HALF + 14 || onSite(x, z, 12)) continue;
    const birth = inv(cityR, distCore(x, z) * 0.95, 0, DUR) + r1 * 3;
    let death = clearAt(x, z); if (death <= birth + 1) continue;
    death = Math.min(death, T.decline[0] + 2 + r2 * 26);
    const y = heightAt(x, z) - 0.3, hgt = 8 + r1 * 5;
    trunkR.push({ m: M4(x, y, z, r2 * 6, 0.5, hgt, 0.5), c: new THREE.Color("#7a6347"), t: [birth, death, NEVER, r1] });
    crownR.push({ m: M4(x, y + hgt, z, r1 * 6.28, 3.8 + r2 * 1.4, 2.2, 3.8 + r2 * 1.4), c: new THREE.Color(["#3f6a2f", "#4a7535", "#38612b"][Math.floor(r3 * 5.4) % 3]), t: [birth, death, NEVER, r1] });
  }
  const trunkGeo = new THREE.CylinderGeometry(0.5, 0.7, 1, 5); trunkGeo.translate(0, 0.5, 0);
  const crownGeo = new THREE.ConeGeometry(1, 1, 7, 1, true); crownGeo.translate(0, -0.45, 0);   // a drooping umbrella of fronds
  { const p = crownGeo.attributes.position; for (let i = 0; i < p.count; i++) if (p.getY(i) < 0) p.setY(i, p.getY(i) + (i % 2 ? 0.25 : -0.1)); }
  const crownG = facet(crownGeo);
  scene.add(growMesh(trunkGeo, STD({ roughness: 1 }), "uniform", trunkR, { shadow: false }));
  scene.add(growMesh(crownG, STD({ flatShading: true, roughness: 0.95, side: THREE.DoubleSide }), "uniform", crownR));
  scene.add(growMesh(facet(new THREE.IcosahedronGeometry(1, 0)), STD({ flatShading: true }), "uniform", bushR));

  // ---------- ground texture: streets, the Processional Way, plazas, fields ----------
  const GX = { X0: -3200, Z0: -3500, EXT: 6400, TEX: 4096 };
  const plazas = [
    { x: ZIG.x, z: ZIG.z, rx: 128, rz: 128, b: T.zig2 - 2 }, { x: ESA.x, z: ESA.z, rx: 92, rz: 66, b: T.esa1[0] },
    { x: GATE.x, z: -470, rx: 9, rz: 330, b: T.pway[0] }, { x: GATE.x, z: -990, rx: 10, rz: 190, b: T.pway[0] },
    { x: -150, z: BRIDGE_Z, rx: 140, rz: 8, b: T.pway[0] + 1 }, { x: CORE.x + 120, z: -310, rx: 40, rz: 30, b: 8 },
  ];
  const fields = [];
  const rf = mulberry32(31);
  for (let k = 0; k < 2600; k++) {
    const x = (rf() - 0.5) * 6200, z = -300 + (rf() - 0.5) * 6200, wl = 30 + rf() * 40, ll = 80 + rf() * 140, tone = 1 + Math.floor(rf() * 4), a = (rf() < 0.5 ? 0 : Math.PI / 2) + (rf() - 0.5) * 0.15;
    if (wetness(x, z) < 0.5 || fbm(x * 0.0035 + 2, z * 0.0035 + 11) > 0.53 || inCity(x, z) || isWet(x, z)) continue;
    fields.push({ x, z, w: wl, l: ll, a, tone });
  }
  const groundTex = rasterGround(GX, segs, plazas, fields);

  // ---------- terrain ----------
  const TW = 9000, TN = 900;
  const tGeo = new THREE.PlaneGeometry(TW, TW, TN, TN); tGeo.rotateX(-Math.PI / 2); tGeo.translate(0, 0, -300);
  const tp = tGeo.attributes.position, aWet = new Float32Array(tp.count), aIn = new Float32Array(tp.count), aRiv = new Float32Array(tp.count);
  for (let i = 0; i < tp.count; i++) {
    const x = tp.getX(i), z = tp.getZ(i);
    tp.setY(i, heightAt(x, z));
    aWet[i] = wetness(x, z); aIn[i] = inCity(x, z) ? 1 : 0;
    aRiv[i] = 1 - sm(clamp((Math.min(Math.abs(x - riverX(z)) - RIVER_HALF, canalDist(x, z) - CANAL_HALF) - 4) / 60));
  }
  tGeo.setAttribute("aWet", new THREE.BufferAttribute(aWet, 1)); tGeo.setAttribute("aIn", new THREE.BufferAttribute(aIn, 1)); tGeo.setAttribute("aRiv", new THREE.BufferAttribute(aRiv, 1));
  tGeo.computeVertexNormals();
  const UT = { uGround: { value: groundTex }, uOrig: { value: new THREE.Vector4(GX.X0, GX.Z0, GX.EXT, GX.TEX) }, uCityR: { value: 0 }, uRect: { value: 0 }, uDry: { value: 0 }, uMud: { value: 0 } };
  const tMat = STD({ color: "#ffffff", roughness: 1 });
  tMat.onBeforeCompile = (s) => {
    Object.assign(s.uniforms, UT, { uTime: U.uTime });
    s.vertexShader = s.vertexShader.replace("#include <common>", "#include <common>\nattribute float aWet, aIn, aRiv; varying float vWet, vIn, vRiv; varying vec3 vW;")
      .replace("#include <worldpos_vertex>", "#include <worldpos_vertex>\nvW = (modelMatrix * vec4(transformed, 1.0)).xyz; vWet = aWet; vIn = aIn; vRiv = aRiv;");
    s.fragmentShader = s.fragmentShader.replace("#include <common>", `#include <common>
      varying float vWet, vIn, vRiv; varying vec3 vW; uniform sampler2D uGround; uniform vec4 uOrig; uniform float uCityR, uRect, uDry, uMud, uTime;
      ${GROUND_GLSL}`)
      .replace("#include <color_fragment>", /* glsl */ `#include <color_fragment>
      {
        float nz = n21(vW.xz * 0.004), nf = n21(vW.xz * 0.03);
        vec3 sand = mix(Ls(vec3(0.80, 0.70, 0.52)), Ls(vec3(0.74, 0.63, 0.46)), nz);
        sand = mix(sand, Ls(vec3(0.84, 0.75, 0.58)), nf * 0.4);
        vec3 green = mix(Ls(vec3(0.42, 0.54, 0.25)), Ls(vec3(0.50, 0.58, 0.30)), nz);
        green = mix(green, Ls(vec3(0.37, 0.49, 0.21)), nf * 0.5);
        float wet = smoothstep(0.25, 0.7, vWet) * (1.0 - uDry * 0.85);
        vec3 col = mix(sand, green, wet);
        col = mix(col, Ls(vec3(0.48, 0.60, 0.30)), vRiv * 0.6 * (1.0 - uDry * 0.5));               // reeds along the water
        col = mix(col, Ls(vec3(0.66, 0.62, 0.50)), smoothstep(0.4, -2.0, vW.y));                    // wet mud at the banks
        float dC = length(vW.xz - vec2(${CORE.x.toFixed(1)}, ${CORE.z.toFixed(1)}));
        float city = smoothstep(uCityR, uCityR - 70.0, dC) * mix(1.0, vIn, uRect);
        vec3 dirt = mix(Ls(vec3(0.66, 0.56, 0.42)), Ls(vec3(0.61, 0.52, 0.39)), nf);
        vec2 uv = (vW.xz - uOrig.xy) / uOrig.z;
        if (uv.x > 0.0 && uv.y > 0.0 && uv.x < 1.0 && uv.y < 1.0) {
          vec4 g = texture2D(uGround, uv);
          vec4 gn = texelFetch(uGround, ivec2(uv * uOrig.w), 0);
          float birth = (gn.g * 255.0 * 256.0 + gn.b * 255.0) / 100.0;
          float field = gn.a * 255.0;
          if (field > 5.0) {
            float tone = floor((field - 10.0) / 50.0), stripe = step(15.0, mod(field - 10.0, 50.0));
            vec3 fc = Ls(tone < 1.5 ? vec3(0.74, 0.67, 0.38) : tone < 2.5 ? vec3(0.45, 0.57, 0.24) : tone < 3.5 ? vec3(0.58, 0.50, 0.33) : vec3(0.57, 0.62, 0.29));
            fc *= mix(1.0, 0.87, stripe);
            col = mix(col, fc, 0.85 * (1.0 - city) * (1.0 - uDry));
          }
          col = mix(col, dirt, city * 0.9);
          float road = g.r * smoothstep(birth, birth + 0.5, uTime) * (1.0 - uDry * 0.75);
          vec3 rc = Ls(mix(vec3(0.82, 0.75, 0.60), vec3(0.86, 0.80, 0.67), n21(vW.xz * 0.2) * 0.5));
          col = mix(col, rc, road * 0.85);
        } else col = mix(col, dirt, city * 0.9);
        col = mix(col, col * vec3(0.62, 0.58, 0.50), uMud * smoothstep(3600.0, 1800.0, dC));        // silt after the flood
        diffuseColor.rgb = col;
      }`);
  };
  const terrain = new THREE.Mesh(tGeo, tMat); terrain.receiveShadow = true; scene.add(terrain);
  const farGround = new THREE.Mesh(new THREE.RingGeometry(4300, 60000, 96, 1).rotateX(-Math.PI / 2), STD({ color: "#c4ae86", roughness: 1 }));
  farGround.position.set(0, PLAIN - 0.5, -300); scene.add(farGround);

  // ---------- river + canals ----------
  const wGeo = new THREE.PlaneGeometry(TW, TW, 600, 600); wGeo.rotateX(-Math.PI / 2); wGeo.translate(0, 0, -300);
  const wp = wGeo.attributes.position, wDepth = new Float32Array(wp.count);
  for (let i = 0; i < wp.count; i++) wDepth[i] = -heightAt(wp.getX(i), wp.getZ(i));
  wGeo.setAttribute("aDepth", new THREE.BufferAttribute(wDepth, 1));
  const UW = { uLevel: { value: 0 } };
  const wMat = new THREE.MeshStandardMaterial({ color: "#ffffff", roughness: 0.5 });
  wMat.onBeforeCompile = (s) => {
    s.uniforms.uTime = U.uTime; s.uniforms.uLevel = UW.uLevel;
    s.vertexShader = s.vertexShader.replace("#include <common>", "#include <common>\nattribute float aDepth; varying float vDepth; varying vec3 vWp; uniform float uLevel;")
      .replace("#include <begin_vertex>", "vec3 transformed = vec3(position.x, position.y + uLevel, position.z);")
      .replace("#include <worldpos_vertex>", "#include <worldpos_vertex>\nvDepth = aDepth + uLevel; vWp = (modelMatrix * vec4(transformed, 1.0)).xyz;");
    s.fragmentShader = s.fragmentShader.replace("#include <common>", `#include <common>
      varying float vDepth; varying vec3 vWp; uniform float uTime;
      float wh(vec2 p){ return fract(sin(dot(p, vec2(41.3, 289.1))) * 15731.743); }
      float wn(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f); return mix(mix(wh(i), wh(i+vec2(1,0)), f.x), mix(wh(i+vec2(0,1)), wh(i+vec2(1,1)), f.x), f.y); }
      vec3 Lw(vec3 c){ return pow(c, vec3(2.2)); }`)
      .replace("#include <color_fragment>", /* glsl */ `#include <color_fragment>
        if (vDepth < 0.0) discard;
        vec3 wc = mix(Lw(vec3(0.33, 0.62, 0.60)), Lw(vec3(0.17, 0.45, 0.50)), smoothstep(0.3, 4.0, vDepth));
        float foam = (1.0 - smoothstep(0.08, 0.5, vDepth)) * (0.55 + 0.45 * wn(vWp.xz * 0.25 + uTime * 0.6));
        wc = mix(wc, Lw(vec3(0.86, 0.88, 0.82)), foam * 0.6);
        diffuseColor.rgb = wc;`)
      .replace("#include <normal_fragment_maps>", /* glsl */ `#include <normal_fragment_maps>
        vec2 q = vWp.xz * 0.08 + vec2(0.0, uTime * 0.6);
        float e = 0.6;
        float h0 = wn(q + uTime * 0.2) + 0.5 * wn(q * 2.3 - uTime * 0.3);
        float hx = wn(q + vec2(e, 0.0) + uTime * 0.2) + 0.5 * wn((q + vec2(e, 0.0)) * 2.3 - uTime * 0.3);
        float hz = wn(q + vec2(0.0, e) + uTime * 0.2) + 0.5 * wn((q + vec2(0.0, e)) * 2.3 - uTime * 0.3);
        normal = normalize(normal + (mat3(viewMatrix) * vec3(-(hx - h0), 0.0, -(hz - h0))) * 0.16);`);
  };
  const water = new THREE.Mesh(wGeo, wMat); water.receiveShadow = true; scene.add(water);

  // ---------- the flood of 689 BC: a sheet of silty water over the plain ----------
  const floodMat = new THREE.MeshStandardMaterial({ color: "#7f7d62", roughness: 0.7, transparent: true, opacity: 0 });
  floodMat.onBeforeCompile = (s) => {
    s.vertexShader = s.vertexShader.replace("#include <common>", "#include <common>\nvarying vec3 vFw;").replace("#include <worldpos_vertex>", "#include <worldpos_vertex>\nvFw = (modelMatrix * vec4(transformed, 1.0)).xyz;");
    s.fragmentShader = s.fragmentShader.replace("#include <common>", "#include <common>\nvarying vec3 vFw;").replace("#include <alphamap_fragment>", "#include <alphamap_fragment>\n diffuseColor.a *= smoothstep(2900.0, 1700.0, length(vFw.xz - vec2(-150.0, -200.0)));");
  };
  const flood = new THREE.Mesh(new THREE.PlaneGeometry(6400, 6400, 1, 1).rotateX(-Math.PI / 2), floodMat); flood.position.set(-150, 0, -200); flood.visible = false; flood.renderOrder = 2; scene.add(flood);

  // ---------- landmarks ----------
  const MUD = "#b09068", BRICK = "#c9a87a", BRICK2 = "#d4b68a", WASH = "#e8dfcb", LAPIS = "#1f4f9a", GOLD = "#d9a93e", DARK = "#3a3029";
  const groupAt = (x, z, ry = 0, yOff = -1) => { const g = new THREE.Group(); g.position.set(x, heightAt(x, z) + yOff, z); g.rotation.y = ry; scene.add(g); return g; };
  // a walled courtyard compound: ring of rooms round an open court
  function compound(parent, cx, cz, w, d, th, h, color, a, b, o = {}) {
    const parts = [box(w, h, th, color, cx, 0, cz - d / 2 + th / 2, parent), box(w, h, th, color, cx, 0, cz + d / 2 - th / 2, parent), box(th, h, d - 2 * th, color, cx - w / 2 + th / 2, 0, cz, parent), box(th, h, d - 2 * th, color, cx + w / 2 - th / 2, 0, cz, parent)];
    parts.forEach((p, i) => grow(p, a + i * 0.15, b + i * 0.15, "y", o));
    return parts;
  }
  // Esagila (first temple, 2nd millennium): razed in 689
  const esa1 = groupAt(ESA.x, ESA.z);
  compound(esa1, 0, 0, 130, 96, 12, 9, MUD, T.esa1[0], T.esa1[0] + 2.2, { off: T.ruin + 0.2, offB: T.ruin + 1.6 });
  grow(box(46, 15, 36, BRICK, -20, 0, 0, esa1), T.esa1[0] + 1.6, T.esa1[1], "y", { off: T.ruin + 0.4, offB: T.ruin + 1.8 });
  grow(box(22, 9, 16, BRICK2, 30, 0, -10, esa1), T.esa1[0] + 2.5, T.esa1[1], "y", { off: T.ruin + 0.4, offB: T.ruin + 1.8 });
  // first ziggurat (Kassite era): three stages, razed in 689 (a rubble mound until Nabopolassar clears it)
  const zig1 = groupAt(ZIG.x, ZIG.z);
  [[62, 12], [46, 10], [32, 9], [16, 7]].reduce((y, [s, h], i) => { grow(box(s, h, s, i === 3 ? WASH : MUD, 0, y, 0, zig1), T.zig1[0] + i * 1.4, T.zig1[0] + i * 1.4 + 1.6, "y", { off: T.ruin + 0.3 + (3 - i) * 0.3, offB: T.ruin + 1.2 + (3 - i) * 0.3 }); return y + h; }, 0);
  const rubble = new THREE.Mesh(new THREE.CylinderGeometry(26, 42, 12, 8).translate(0, 6, 0), STD({ color: "#a58b67", flatShading: true })); zig1.add(rubble); rubble.castShadow = rubble.receiveShadow = true;
  grow(rubble, T.ruin + 1, T.ruin + 2.4, "y", { off: T.zig2 - 2.2, offB: T.zig2 - 0.6 });
  // Etemenanki (Neo-Babylonian): 91 m base, built tier by tier with a scaffold, then torn down by Alexander
  const zig = groupAt(ZIG.x, ZIG.z);
  const TIERS = [[91, 33, BRICK], [78, 18, BRICK2], [60, 6, BRICK], [51, 6, BRICK2], [42, 6, BRICK], [33, 6, BRICK2]];
  let zy = 0;
  TIERS.forEach(([s, h, c], i) => {
    const a = T.zig2 + (i === 0 ? 0 : 4 + i * 1.7), b = a + (i === 0 ? 4.5 : 1.6);
    const tier = box(s, h, s, c, 0, zy, 0, zig);
    // recessed niches on each face of the first two tiers
    if (i < 2) for (let k = -3; k <= 3; k++) for (const sgn of [-1, 1]) { box(4, h * 0.8, 0.6, "#b39064", k * (s / 8), h * 0.1, sgn * (s / 2 + 0.05), tier); box(0.6, h * 0.8, 4, "#b39064", sgn * (s / 2 + 0.05), h * 0.1, k * (s / 8), tier); }
    const demo = T.demolish + (TIERS.length - i) * 1.1;
    grow(tier, a, b, "y", { off: demo, offB: demo + 1.4, offTo: i === 0 ? 0.32 : 0 });
    zy += h;
  });
  const shrine = box(24, 15, 21, LAPIS, 0, zy, 0, zig);
  box(24.6, 1.4, 21.6, GOLD, 0, 13.6, 0, shrine); box(6, 9, 0.8, DARK, 0, 0, 10.7, shrine);
  grow(shrine, T.zig2 + 15.5, T.zig2 + 17.2, "y", { off: T.demolish, offB: T.demolish + 1.2 });
  // the grand south stair and two side stairs
  const stair = (run, rise, x, z, ry, a, b) => { const len = Math.hypot(run, rise), g = new THREE.BoxGeometry(9, 1.2, len); g.translate(0, 0, -len / 2); const m = new THREE.Mesh(g, STD({ color: BRICK2 })); m.position.set(x, 0.6, z); m.rotation.set(Math.atan2(rise, run), ry, 0, "YXZ"); m.castShadow = m.receiveShadow = true; zig.add(m); grow(m, a, b, "all", { off: T.demolish + 6, offB: T.demolish + 7.4 }); return m; };
  stair(72, 51, 0, 45.5 + 72, 0, T.zig2 + 7, T.zig2 + 9);                       // the grand stair, straight up the south face
  stair(40, 33, 45, 50.5, Math.PI / 2, T.zig2 + 5, T.zig2 + 6.5);                // two side stairs climbing along the face
  stair(40, 33, -45, 50.5, -Math.PI / 2, T.zig2 + 5, T.zig2 + 6.5);
  // scaffold climbs with the tiers
  const scaf = new THREE.Group(); zig.add(scaf);
  {
    const poles = []; for (let k = -6; k <= 6; k++) for (const sgn of [-1, 1]) { poles.push([k * 8, sgn * 50]); poles.push([sgn * 50, k * 8]); }
    const pg = new THREE.CylinderGeometry(0.35, 0.35, 1, 4); pg.translate(0, 0.5, 0);
    const pm = new THREE.InstancedMesh(pg, STD({ color: "#7a5a3a" }), poles.length); poles.forEach(([x, z], i) => pm.setMatrixAt(i, M4(x, 0, z, 0, 1, 78, 1))); pm.castShadow = true; scaf.add(pm);
    const ledg = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 0.5, 0.5), STD({ color: "#8a6844" }), 64); let k = 0;
    for (let y = 6; y <= 76; y += 10) for (const [cx, cz, lx, lz] of [[0, -50, 100, 0], [0, 50, 100, 0], [-50, 0, 0, 100], [50, 0, 0, 100]]) ledg.setMatrixAt(k++, M4(cx, y, cz, lx ? 0 : Math.PI / 2, lx || lz, 1, 1));
    ledg.count = k; ledg.castShadow = true; scaf.add(ledg);
  }
  grow(scaf, T.zig2 + 0.5, T.zig2 + 14, "y", { off: T.zig2 + 17, offB: T.zig2 + 18.5 });
  // the precinct wall round Etemenanki (rooms along a square enclosure)
  const peri = groupAt(ZIG.x, ZIG.z);
  compound(peri, 0, 0, 256, 256, 16, 10, WASH, T.zig2 + 1, T.zig2 + 4, { off: 276, offB: 288, offTo: 0.22 });
  // Esagila rebuilt (Neo-Babylonian)
  const esa2 = groupAt(ESA.x, ESA.z);
  compound(esa2, 0, 0, 180, 128, 14, 12, WASH, T.esa2[0], T.esa2[0] + 2.4, { off: 278, offB: 290, offTo: 0.25 });
  grow(box(70, 20, 52, BRICK2, -30, 0, 0, esa2), T.esa2[0] + 1.8, T.esa2[1], "y", { off: 278, offB: 290, offTo: 0.3 });
  grow(box(34, 14, 26, WASH, 46, 0, -16, esa2), T.esa2[0] + 2.6, T.esa2[1], "y", { off: 280, offB: 290, offTo: 0.2 });
  const esaRoof = box(30, 1.4, 22, GOLD, -30, 20, 0, esa2); grow(esaRoof, T.esa2[1] - 0.8, T.esa2[1], "y", { off: 278, offB: 284 });
  // Southern Palace: five courts from east to west, the throne room on the south side
  const pal = groupAt(PAL.x, PAL.z);
  [[100, 0, 56, 110], [45, 0, 52, 120], [-8, 10, 50, 132], [-58, 10, 46, 130], [-104, 0, 44, 110]].forEach(([cx, cz, w, d], i) => {
    compound(pal, cx, cz, w, d, 9, 13 - i * 0.5, i % 2 ? WASH : BRICK2, T.palace[0] + i * 1.1, T.palace[0] + i * 1.1 + 1.8, { off: 268 + i, offB: 284 + i, offTo: 0.22 });
  });
  grow(box(52, 20, 26, BRICK2, -8, 0, 52, pal), T.palace[0] + 3, T.palace[1], "y", { off: 270, offB: 286, offTo: 0.25 });
  grow(box(53, 1.2, 27, LAPIS, -8, 20, 52, pal), T.palace[1] - 0.6, T.palace[1] + 0.4, "y", { off: 266, offB: 272 });
  // the "Hanging Gardens": stepped green terraces on the palace's north-east corner
  const gard = groupAt(PAL.x + 95, PAL.z - 80);
  [[60, 9, 0], [46, 7, 9], [32, 6, 16], [18, 5, 22]].forEach(([s, h, y], i) => {
    grow(box(s, h, s * 0.8, BRICK2, 0, y, 0, gard), T.gardens[0] + i * 0.9, T.gardens[0] + i * 0.9 + 1.2, "y", { off: 272, offB: 286, offTo: 0.2 });
    grow(box(s - 3, 0.8, s * 0.8 - 3, "#4f7a37", 0, y + h, 0, gard), T.gardens[0] + i * 0.9 + 1.0, T.gardens[0] + i * 0.9 + 1.6, "xz", { off: 262, offB: 270 });
  });
  const gTrees = new THREE.InstancedMesh(facet(new THREE.IcosahedronGeometry(1, 0)), STD({ color: "#3f6c2c", flatShading: true }), 40);
  for (let k = 0; k < 40; k++) { const tier = k % 4, s = [60, 46, 32, 18][tier] - 6, y = [9, 16, 22, 27][tier] + 2; gTrees.setMatrixAt(k, M4((hash2(k, 1) - 0.5) * s, y, (hash2(k, 2) - 0.5) * s * 0.75, 0, 2.6, 2.4, 2.6)); }
  gTrees.castShadow = true; gard.add(gTrees); grow(gTrees, T.gardens[1] - 1.2, T.gardens[1] + 0.6, "all", { off: 262, offB: 270 });
  // Ishtar Gate: blue glazed towers with gold animal rows; the Processional Way walls run north from it
  const gate = groupAt(GATE.x, GATE.z - 6);
  const animals = (parent, w, h, zf, rows) => { rows.forEach((y) => { for (let x = -w / 2 + 2; x < w / 2 - 1; x += 3.4) box(1.8, 1.2, 0.4, GOLD, x, y, zf, parent); }); };
  const gb = box(26, 22, 30, LAPIS, 0, 0, 0, gate); animals(gb, 26, 22, -15.1, [5, 9.5, 14]); animals(gb, 26, 22, 15.1, [5, 9.5, 14]);
  box(9, 13, 0.6, DARK, 0, 0, -15.2, gb); box(9, 13, 0.6, DARK, 0, 0, 15.2, gb);
  for (const sx of [-1, 1]) { const tw = box(9, 28, 12, LAPIS, sx * 17, 0, -10, gate); animals(tw, 9, 28, -6.1, [6, 11, 16, 21]); box(9.4, 1.2, 12.4, "#e9dfc6", 0, 27, 0, tw); grow(tw, T.gate[0] + 0.6, T.gate[1], "y", { off: 286, offB: 296, offTo: 0.4 }); }
  box(26.6, 1.3, 30.6, "#e9dfc6", 0, 21, 0, gb);
  grow(gb, T.gate[0], T.gate[1] - 0.5, "y", { off: 286, offB: 296, offTo: 0.45 });
  const pway = groupAt(GATE.x, GATE.z - 30);
  for (const sx of [-1, 1]) { const wl = box(4, 8, 330, LAPIS, sx * 13, 0, -165, pway); for (let z = -320; z < -6; z += 6.5) box(0.4, 1.4, 3.4, GOLD, -sx * 2.05, 3.6, z + 165, wl); grow(wl, T.pway[0], T.pway[1], "y", { off: 280, offB: 292, offTo: 0.3 }); }
  // the Euphrates bridge: brick piers and a timber deck
  const bridge = new THREE.Group(); scene.add(bridge);
  for (let k = -4; k <= 4; k++) { const x = riverX(BRIDGE_Z) + k * 19; const p = box(9, 6.5, 14, BRICK, x, -3.5, BRIDGE_Z, bridge); grow(p, T.bridge[0] + (k + 4) * 0.18, T.bridge[0] + (k + 4) * 0.18 + 0.8, "y", { off: 286, offB: 292 }); }
  const deck = box(190, 1, 10, "#8a6a48", riverX(BRIDGE_Z), 3, BRIDGE_Z, bridge); grow(deck, T.bridge[1] - 1.2, T.bridge[1], "x", { off: 282, offB: 288 });
  // Northern and Summer palaces
  const npal = groupAt(NPAL.x, NPAL.z);
  compound(npal, 0, 0, 230, 140, 12, 13, BRICK2, T.npal[0], T.npal[0] + 2, { off: 270, offB: 286, offTo: 0.22 });
  grow(box(80, 16, 50, WASH, 20, 0, 0, npal), T.npal[0] + 1.5, T.npal[1], "y", { off: 270, offB: 286, offTo: 0.25 });
  const spal = groupAt(SPAL.x, SPAL.z);
  grow(box(180, 8, 140, "#b99a72", 0, 0, 0, spal), T.spal[0], T.spal[0] + 1.6, "y", { off: 274, offB: 290, offTo: 0.5 });
  compound(spal, 0, 0, 150, 110, 11, 12, WASH, T.spal[0] + 1.2, T.spal[1], { off: 270, offB: 286, offTo: 0.2 });
  spal.children.slice(1).forEach((c) => (c.position.y += 8));

  // ---------- the Persian camp and Cyrus's army ----------
  const tentR = [], troopsPts = [];
  const rc = mulberry32(99);
  for (let k = 0; k < 900; k++) {
    const a = rc() * Math.PI * 2, r = Math.sqrt(rc()) * 330, x = 2350 + Math.cos(a) * r * 1.4, z = -700 + Math.sin(a) * r;
    const royal = k < 18, s = royal ? 14 + rc() * 5 : 6.5 + rc() * 2.5;
    tentR.push({ m: M4(x, heightAt(x, z) - 0.2, z, rc() * 3, s, s * (royal ? 0.9 : 1.0), s), c: new THREE.Color(royal ? ["#a3262f", "#c79a3a"][k % 2] : ["#efe6d2", "#e3d6bd", "#d9caa8"][k % 3]), t: [T.camp[0] + (r / 330) * (T.camp[1] - T.camp[0]) + rc(), T.camp[2] + rc() * (T.camp[3] - T.camp[2]), NEVER, rc()] });
  }
  const tentGeo = new THREE.ConeGeometry(1, 1.4, 4); tentGeo.translate(0, 0.7, 0);
  scene.add(growMesh(facet(tentGeo), STD({ flatShading: true }), "uniform", tentR));
  const TROOPS = 1200, troops = new THREE.InstancedMesh(new THREE.BoxGeometry(2.4, 3.2, 2.4).translate(0, 1.6, 0), STD({ color: "#7a2b26" }), TROOPS); troops.frustumCulled = false; scene.add(troops);
  for (let k = 0; k < TROOPS; k++) troopsPts.push({ lane: (k % 16) - 7.5, row: Math.floor(k / 16), j: hash2(k, 3) });
  const marchPath = [[2100, -620], [1700, -420], [1100, -320], [700, -305], [300, -305]];   // along the avenue into the city
  const pathAt = (u) => { const n = marchPath.length - 1, f = clamp(u) * n, i = Math.min(n - 1, Math.floor(f)), w = f - i; return [lerp(marchPath[i][0], marchPath[i + 1][0], w), lerp(marchPath[i][1], marchPath[i + 1][1], w)]; };

  // ---------- boats on the river ----------
  const boats = [];
  const hullG = new THREE.BoxGeometry(12, 2.2, 3.8); { const p = hullG.attributes.position; for (let i = 0; i < p.count; i++) { if (Math.abs(p.getX(i)) > 3) p.setZ(i, p.getZ(i) * 0.35); if (p.getY(i) < 0) p.setZ(i, p.getZ(i) * 0.6); } hullG.computeVertexNormals(); }
  const hullM = STD({ color: "#6a4d33" }), sailM = STD({ color: "#efe6d2", side: THREE.DoubleSide }), roundM = STD({ color: "#4f3c2a" });
  const rb2 = mulberry32(5);
  for (let k = 0; k < 46; k++) {
    const g = new THREE.Group(), round = rb2() < 0.4;
    if (round) { const q = new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.2, 1.4, 10), roundM); q.position.y = 0.5; g.add(q); }
    else { const h = new THREE.Mesh(hullG, hullM); h.position.y = 0.5; h.castShadow = true; g.add(h); const s = new THREE.Mesh(new THREE.PlaneGeometry(6, 8).translate(0, 6, 0), sailM); s.rotation.y = Math.PI / 2; s.castShadow = true; g.add(s); const m = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 11, 4).translate(0, 5.5, 0), hullM); g.add(m); }
    scene.add(g);
    boats.push({ g, z0: (rb2() - 0.5) * 7000, v: (rb2() < 0.5 ? -1 : 1) * (6 + rb2() * 10), lane: (rb2() - 0.5) * 80, born: 6 + rb2() * 150, died: rb2() < 0.75 ? 262 + rb2() * 25 : NEVER, s: round ? 1 : 0.9 + rb2() * 0.4 });
  }

  // ---------- smoke, dust ----------
  const smoke = [];
  const rs = mulberry32(17);
  for (const [t0, R, n] of [[T.sack, 600, 18], [T.ruin, 900, 26]]) for (let k = 0; k < n; k++) {
    const a = rs() * Math.PI * 2, r = Math.sqrt(rs()) * R, x = CORE.x + Math.cos(a) * r, z = CORE.z + Math.sin(a) * r;
    if (isWet(x, z)) continue;
    const s0 = t0 + r / 130 + 0.6; smoke.push({ x, y: PLAIN + 8, z, t0: s0, t1: s0 + 3.5 + rs() * 2.5, ph: rs(), wind: [130, -40] });
  }
  const updSmoke = puffs(scene, smoke, { color: "#4a4541", opacity: 0.3, perCol: 22 });
  const demoDust = [];
  for (let k = 0; k < 10; k++) demoDust.push({ x: ZIG.x + (hash2(k, 1) - 0.5) * 70, y: PLAIN + 20, z: ZIG.z + (hash2(k, 2) - 0.5) * 70, t0: T.demolish + k * 0.7, t1: T.demolish + 6 + k * 0.4, ph: hash2(k, 3), rise: 70, spread: 30, speed: 0.22, wind: [60, -20] });
  const updDust = puffs(scene, dustCols.concat(demoDust), { color: "#bba886", opacity: 0.32, perCol: 10 });

  // ---------- camera: one flight ----------
  const cam = cameraPath([
    [0, [-560, 560, 960], [-260, 0, -60]],
    [9, [-300, 430, 620], [-170, 0, -60]],
    [18, [170, 380, 440], [-90, 0, -90]],
    [26, [70, 210, 230], [-150, 8, 50]],
    [36, [-80, 680, 930], [-110, 0, -60]],
    [46, [380, 720, 760], [0, 0, -100]],
    [55, [620, 620, 520], [-40, 0, -110]],
    [66, [90, 250, 60], [-150, 14, -170]],
    [79, [-720, 720, 520], [-210, 0, -110]],
    [92, [-420, 950, 1250], [-150, 0, 0]],
    [101, [320, 720, 720], [-60, 0, -60]],
    [110, [760, 980, 1080], [0, 0, -40]],
    [122, [420, 820, 960], [-100, 0, -100]],
    [137, [1500, 950, 700], [650, 0, -300]],
    [149, [520, 420, 300], [80, 0, -300]],
    [158, [130, 250, 110], [-150, 40, -170]],
    [166, [-280, 230, 80], [-150, 52, -170]],
    [174, [-360, 330, -330], [-150, 10, -620]],
    [182, [170, 150, -640], [-10, 12, -810]],
    [190, [-10, 270, -400], [-60, 12, -700]],
    [199, [450, 1150, 950], [250, 0, -480]],
    [210, [2950, 720, 380], [2250, 0, -660]],
    [222, [1850, 620, 260], [1100, 0, -400]],
    [233, [820, 920, 820], [0, 0, -220]],
    [245, [-40, 330, -330], [-150, 10, -620]],
    [257, [170, 300, 60], [-150, 30, -170]],
    [268, [950, 1250, 1350], [0, 0, -300]],
    [282, [-650, 1350, 1550], [-100, 0, -300]],
    [294, [-220, 1750, 2350], [0, 0, -400]],
    [DUR, [-120, 2050, 2750], [0, 0, -460]],
  ]);
  const drawHud = hudDriver(hud, { ERAS, FLAGS, TITLE, LANDMARKS, CAPTIONS, CARDS, yearAt, popAt, DUR });

  const ready = Promise.resolve();
  const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = V(1, 1, 1), _p = V();
  function renderAt(time) {
    const t = clamp(time, 0, DUR);
    U.uTime.value = t;
    UT.uCityR.value = cityR(t);
    UT.uRect.value = sm(ramp(t, T.walls[0], T.walls[1] + 6));
    UT.uDry.value = sm(ramp(t, T.decline[0] + 4, T.decline[1] + 6)) * 0.85;
    UT.uMud.value = ramp(t, T.flood[2], T.flood[3]) * (1 - ramp(t, T.flood[3] + 6, T.flood[3] + 22));
    // flood sheet + the river during the Persian conquest (the level drops a little)
    const fl = sm(ramp(t, T.flood[0], T.flood[1])) * (1 - sm(ramp(t, T.flood[2], T.flood[3])));
    flood.visible = fl > 0.001; flood.position.y = PLAIN - 0.9 + fl * 2.3; floodMat.opacity = Math.min(0.82, fl * 3);
    UW.uLevel.value = -1.3 * sm(ramp(t, 215, 219)) * (1 - sm(ramp(t, 229, 236)));
    updateLM(t);
    // boats
    for (const b of boats) {
      const on = sm(ramp(t, b.born, b.born + 1)) * (1 - sm(ramp(t, b.died, b.died + 1)));
      b.g.visible = on > 0.01; if (!b.g.visible) continue;
      let z = b.z0 + b.v * t; z = ((z + 3500) % 7000 + 7000) % 7000 - 3500;
      if (Math.abs(z - BRIDGE_Z) < 12) z += 24 * Math.sign(b.v);
      b.g.position.set(riverX(z) + b.lane, UW.uLevel.value + 0.1 + Math.sin(t * 1.3 + b.lane) * 0.12, z);
      b.g.rotation.set(0, b.v > 0 ? -Math.PI / 2 : Math.PI / 2, Math.sin(t + b.lane) * 0.03);
      b.g.scale.setScalar(on * b.s);
    }
    // the army: marches from the camp along the avenue, then thins out
    const mu = ramp(t, T.march[0], T.march[1]), mOn = mu > 0 && t < T.march[1] + 2.5;
    let k = 0;
    if (mOn) for (const p of troopsPts) {
      const u = clamp(mu * 1.4 - p.row * 0.0055), [x, z] = pathAt(u), [x2, z2] = pathAt(Math.min(1, u + 0.01)), dx = x2 - x, dz = z2 - z, ln = Math.hypot(dx, dz) || 1;
      if (u <= 0.001 || u >= 0.999) continue;
      const nx = -dz / ln, nz = dx / ln, bob = Math.abs(Math.sin(t * 9 + p.j * 6)) * 0.3;
      _p.set(x + nx * p.lane * 2.4, heightAt(x, z) + bob, z + nz * p.lane * 2.4);
      troops.setMatrixAt(k++, _m.compose(_p, _q, _s));
    }
    troops.count = k; troops.instanceMatrix.needsUpdate = true;
    updSmoke(t); updDust(t);
    // light: warmer and dimmer in the fires, hazy at the end
    const fireMood = Math.max(sm(ramp(t, T.sack, T.sack + 2)) * (1 - sm(ramp(t, T.sack + 6, T.sack + 9))), sm(ramp(t, T.ruin, T.ruin + 2)) * (1 - sm(ramp(t, T.flood[0], T.flood[1] + 2))));
    st.sun.color.set("#fff1d8").lerp(new THREE.Color("#ffc68c"), fireMood * 0.6);
    st.sun.intensity = 3.2 - fireMood * 0.7; st.hemi.intensity = 1.15 - fireMood * 0.25;
    const { pos, tgt } = cam(t);
    st.frame(pos, tgt);
    st.scene.fog.near *= 0.65; st.scene.fog.far *= 0.6;
    drawHud(t);
    st.render();
  }
  return { ready, renderAt, DUR, stats: { lots: lots.length, lives: lives.length, houses: wallR.length, ruins: ruinR.length, palms: crownR.length, roads: segs.length, fields: fields.length, walls: wSeg.length, fires: fireRecs.length, peak } };
}
