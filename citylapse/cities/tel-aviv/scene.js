import * as THREE from "three";
import {
  clamp, lerp, ramp, sm, V, mulberry32, hash2, fbm, pw, pl, inv, M4, NEVER, U, STD, growMesh, unitBox, hipRoof, facet,
  createStage, rasterGround, GROUND_GLSL, landmarks, cameraPath, hudDriver, puffs,
} from "./engine.js";
import { DATA } from "./data.js";

// "TEL AVIV – 3D TIMELAPSE – 1880 to 2026". See SPEC.md for the beats and the fact-checked captions.
// Unlike the procedural cities, every building here is a real footprint (OpenStreetMap via Overture Maps,
// tools/osm_data.py): its rectangle, its height, and an approximate year (satellite GHSL epochs after 1975,
// documented founding dates of each quarter before, real years for the towers). World metres, x east, z south.

export const W = 1920, H = 1080, SS = 1.5, DUR = 560;

// ---------------- land: the coast, the Yarkon, low sand dunes ----------------
const SG = DATA.S, SD = Uint8Array.from(atob(SG.b64), (c) => c.charCodeAt(0));
const sdRaw = (i, j) => { i = clamp(i, 0, SG.nz - 1); j = clamp(j, 0, SG.nx - 1); const v = SD[i * SG.nx + j]; return v > 127 ? v - 256 : v; };
function shoreDist(x, z) {                       // signed metres to the water's edge (< 0 in the water), bilinear
  const fx = (x - SG.x0) / SG.g - 0.5, fz = (z - SG.z0) / SG.g - 0.5, j = Math.floor(fx), i = Math.floor(fz), u = fx - j, v = fz - i;
  return lerp(lerp(sdRaw(i, j), sdRaw(i, j + 1), u), lerp(sdRaw(i + 1, j), sdRaw(i + 1, j + 1), u), v);
}
function heightAt(x, z) {
  const d = shoreDist(x, z);
  if (d < 0) return Math.max(-7, d * 0.12) - 0.4;           // shelving sea floor
  const dune = (fbm(x * 0.0022 + 3, z * 0.0022 - 5) - 0.5) * 6 * sm(clamp(d / 260));
  return 0.6 + Math.min(d, 400) * 0.012 + Math.max(0, dune);
}
const isWet = (x, z) => shoreDist(x, z) < 6;
const LL = (lat, lon) => [(lon - 34.775) * 94226, -(lat - 32.07) * 111195];

// ---------------- time: video seconds → year ----------------
const YK = [
  [0, 1880], [14, 1887], [30, 1902], [41, 1909.27], [49, 1909.3], [62, 1913], [72, 1917.25], [79, 1917.3], [88, 1921.3],
  [104, 1925.5], [109, 1925.6], [150, 1934.4], [172, 1938.5], [190, 1946], [202, 1948.37], [214, 1948.38], [226, 1950.31], [233, 1950.32],
  [262, 1959], [282, 1965.5], [312, 1975], [340, 1990], [352, 1995.84], [360, 1995.85], [384, 1999.6], [412, 2007], [444, 2017],
  [470, 2023.63], [478, 2023.64], [505, 2026], [DUR, 2026],
];
const yearF = (t) => pl(YK, t);
const yearAt = (t) => Math.floor(yearF(t));
const tOf = (y) => (y <= YK[0][1] ? -1 : inv(yearF, y, 0, DUR));   // first video time that reaches a year
const T = { lottery: 41, gym: [47, 58], expel: 72, geddes: 104, indep: 202, merger: 226, gymDown: tOf(1959.5), azrieli: tOf(1998.6), end: 505 };

const ERAS = [
  { t: 0, name: "OTTOMAN JAFFA", flag: "ottoman" },
  { t: tOf(1917.9), name: "BRITISH MANDATE", flag: "mandate" },
  { t: T.indep + 1, name: "STATE OF ISRAEL", flag: "israel" },
];
const FLAGS = {
  ottoman: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#c8102e"/><circle cx="62" cy="42" r="21" fill="#fff"/><circle cx="68" cy="42" r="17" fill="#c8102e"/><path d="M88 42 l-12.6 4.1 7.8-10.7 v13.2 l-7.8-10.7z" fill="#fff"/></svg>`,
  mandate: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#012169"/><path d="M0 0 L140 84 M140 0 L0 84" stroke="#fff" stroke-width="17"/><path d="M0 0 L140 84 M140 0 L0 84" stroke="#c8102e" stroke-width="6"/><path d="M70 0 V84 M0 42 H140" stroke="#fff" stroke-width="27"/><path d="M70 0 V84 M0 42 H140" stroke="#c8102e" stroke-width="15"/></svg>`,
  israel: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#fff"/><rect y="8" width="140" height="13" fill="#0038b8"/><rect y="63" width="140" height="13" fill="#0038b8"/><path d="M70 27 L82 48 H58Z M70 57 L58 36 H82Z" fill="none" stroke="#0038b8" stroke-width="3.6"/></svg>`,
};
const TITLE = [1.2, 8];
const LANDMARKS = [
  { a: 4, b: 11, text: "JAFFA" },
  { a: 18, b: 24, text: "NEVE TZEDEK" },
  { a: 51, b: 57, text: "AHUZAT BAYIT" },
  { a: 59, b: 65, text: "HERZLIYA GYMNASIUM" },
  { a: 158, b: 164, text: "THE WHITE CITY" },
  { a: 174, b: 180, text: "TEL AVIV PORT" },
  { a: 206, b: 212.5, text: "INDEPENDENCE HALL" },
  { a: 283, b: 289, text: "SHALOM MEIR TOWER" },
  { a: 387, b: 393, text: "AZRIELI CENTER" },
  { a: 446, b: 452, text: "AZRIELI SARONA TOWER" },
];
const CAPTIONS = [
  { a: 26, b: 33, lines: ["Neve Tzedek, officially founded in 1887, was the first", "Jewish neighbourhood built outside old Jaffa."] },
  { a: 42, b: 48.5, lines: ["On 11 April 1909, 66 families drew lots", "for plots on the sand dunes north of Jaffa."] },
  { a: 66, b: 71.5, lines: ["On 21 May 1910 the new neighbourhood", "took the name Tel Aviv."] },
  { a: 73, b: 79, lines: ["In April 1917 the Ottoman authorities expelled", "the residents of Tel Aviv and Jaffa."] },
  { a: 89, b: 95, lines: ["In 1921 Tel Aviv became a township", "within the Jaffa municipality."] },
  { a: 104, b: 110, lines: ["In 1925 the Scottish planner Patrick Geddes", "drew up the master plan for the city."] },
  { a: 125, b: 131.5, lines: ["In January 1934 Tel Aviv", "was declared a city."] },
  { a: 165, b: 171.5, lines: ["Some 3,000 buildings went up in the Bauhaus style between 1931 and 1939;", "UNESCO listed the White City in 2003."] },
  { a: 181, b: 187, lines: ["Tel Aviv Port opened in 1936", "and was inaugurated in full in 1938."] },
  { a: 214.5, b: 221, lines: ["On 14 May 1948 the State of Israel was declared here,", "in Dizengoff House at 16 Rothschild Boulevard."] },
  { a: 222, b: 228.5, lines: ["In 1948 Jaffa's population fell from about 50,000 to about 4,000,", "as most of its Arab residents fled or were expelled."] },
  { a: 233.5, b: 240, lines: ["On 24 April 1950 Tel Aviv and Jaffa were merged;", "the city was renamed Tel Aviv-Yafo that August."] },
  { a: 290, b: 296.5, lines: ["Built on the site of the Herzliya Gymnasium,", "it was Israel's first skyscraper (129 m)."] },
  { a: 359, b: 365.5, lines: ["Prime Minister Yitzhak Rabin was assassinated here at a peace rally;", "the square was renamed Rabin Square."] },
  { a: 394, b: 400.5, lines: ["The round tower, 187 m tall,", "was Israel's tallest building from 1999."] },
  { a: 453, b: 459.5, lines: ["Finished in 2017 at 238.5 m, it was", "Israel's tallest building until 2024."] },
  { a: 478.5, b: 485, lines: ["On 18 August 2023 the Red Line opened,", "Tel Aviv's first light-rail line."] },
];
const CARDS = [
  { a: T.lottery - 0.2, b: T.lottery + 1, kicker: "", text: "" },
  { a: T.indep - 5, b: T.indep + 0.8, kicker: "14 MAY 1948", text: "INDEPENDENCE" },
  { a: 352, b: 358.5, kicker: "4 NOVEMBER 1995", text: "KINGS OF ISRAEL SQUARE" },
  { a: 520, b: 552, kicker: "1909 – 2026", text: "TEL AVIV-YAFO" },
].filter((c) => c.text);

// population (city of Tel Aviv; Tel Aviv-Yafo after 1950). SPEC.md lists the sources.
const POP = [[1914.99, 0], [1915, 2679], [1922.8, 15185], [1925.5, 34200], [1931.9, 46101], [1937, 150000], [1944, 166660], [1948, 248500],
  [1950.3, 335000], [1955, 359700], [1961.4, 386070], [1972.4, 363750], [1983.5, 327265], [1986, 320258], [1995.9, 348245], [2008.9, 402600],
  [2013, 418600], [2017, 443940], [2020, 463810], [2024, 494900], [2026, 494900]];
const popAt = (t) => { const y = yearF(t); return y < 1915 ? 0 : pl(POP, y); };

// ---------------- build ----------------
export function buildVideo(canvas, hud) {
  const st = createStage(canvas, { W, H, SS, fog: "#dbe8f0", skyTop: "#6fa8dc", sunColor: "#fff1d6", sunDir: [-0.5, 0.7, 0.5], hemiSky: "#d6e9fb", hemiGround: "#9c8f6e", hemiI: 1.2, sunI: 3.3, saturation: 0.14, contrast: 0.12, tilt: 0.4, bloom: 0.35 });
  const { scene } = st;
  const { box, grow, update: updateLM } = landmarks();
  const rnd = mulberry32(1909);
  const TW = DATA.towers.reduce((o, t) => ((o[t.label] = o[t.label] || t), o), {});

  // ---------- roads: real streets, dirt tracks first, paved later ----------
  const segs = [];
  for (let i = 0; i < DATA.R.length; i += 6) {
    const [ax, az, bx, bz, w, y] = DATA.R.slice(i, i + 6);
    if (isWet((ax + bx) / 2, (az + bz) / 2)) continue;
    const b = Math.max(0, tOf(y) - 1.2);
    segs.push({ ax, az, bx, bz, w: Math.max(4, w * 0.9), ba: b, bb: b });
  }

  // ---------- buildings ----------
  const OLD = ["#d9c29a", "#cfb48a", "#e2cda6", "#c8ad83", "#d6c29e", "#c2a67c"];           // Jaffa sandstone
  const ROOF = ["#c0603d", "#b25a3a", "#cc6d48", "#a9553a"];                                  // tile roofs
  // plaster in many tones (white, cream, sand, ochre, pale stone, salmon): the "White City" is far from uniform
  const WHITE = ["#f1ebdf", "#e9dcc2", "#e3cfa8", "#f3e6cc", "#dcc6a0", "#efe1c9", "#e8d2b4", "#f2d9c4", "#e6e0d2", "#d9c09a", "#f0e4b8", "#e2c7ae"];
  const MID = ["#d8cfc0", "#cbbfae", "#e0d2bb", "#c9b79c", "#d5cbbd", "#bfb5a6", "#e2d6c2", "#cdbb9f", "#b9ad9b", "#d7c2a2", "#c4b8a8", "#e5d8c0"];
  const GLASS = ["#b9d0de", "#a9c4d6", "#c6d8e2", "#9fbdd0", "#cfdde6", "#8fb3c8"];
  const SOLAR = [], solarDark = new THREE.Color("#3a4a5a"), solarTank = new THREE.Color("#e8e8e4");
  const wallR = [], roofR = [], hipR = [], glassR = [], capR = [];
  const cW = new THREE.Color();
  const B = DATA.B;
  const houseAt = new Map(), HCS = 16;
  for (let i = 0; i < B.length; i += 9) {
    const x = B[i] / 10, z = B[i + 1] / 10, w = B[i + 2] / 10, d = B[i + 3] / 10, ang = B[i + 4] / 1000, h = Math.max(3.5, B[i + 5] / 10), y = B[i + 6] / 100, kind = B[i + 7], ci = B[i + 8];
    if (isWet(x, z)) continue;
    const r1 = hash2(i, 1), r2 = hash2(i, 2);
    const b = Math.max(0.2, tOf(y) + r1 * 0.6);
    const y0 = heightAt(x, z) - 0.8, t = [b, NEVER, NEVER, r2];
    const k = Math.floor(x / HCS) * 100003 + Math.floor(z / HCS); const v = houseAt.get(k); if (v === undefined || v > b) houseAt.set(k, b);
    if (kind === 2 || h >= 45) {                    // towers: glass shafts, a lighter crown
      cW.set(GLASS[(ci + Math.floor(r1 * 6)) % 6]);
      glassR.push({ m: M4(x, y0, z, ang, w, 1, d), c: cW.clone(), t, h: [0, h] });
      capR.push({ m: M4(x, y0, z, ang, w * 0.86, 1, d * 0.86), c: new THREE.Color("#dfe6ea"), t: [b + 0.4, NEVER, NEVER, r2], h: [h, 2.5] });
      continue;
    }
    const old = h < 14 && (y < 1912 || (y < 1925 && r1 < 0.3));
    const pick = Math.floor(hash2(i, 5) * 12);
    cW.set(old && y < 1906 ? OLD[ci % 6] : kind === 1 ? MID[pick] : WHITE[pick]);
    wallR.push({ m: M4(x, y0, z, ang, w, 1, d), c: cW.clone(), t, h: [0, h + 0.8] });
    if (old && w < 30 && d < 30) hipR.push({ m: M4(x, y0 + h + 0.8, z, ang, w + 0.6, Math.min(w, d) * 0.32, d + 0.6), c: new THREE.Color(ROOF[Math.floor(r1 * 3.99)]), t: [b + 0.15, NEVER, NEVER, r2] });
    else {
      roofR.push({ m: M4(x, y0, z, ang, Math.max(1, w - 1), 1, Math.max(1, d - 1)), c: cW.clone().multiplyScalar(0.86), t, h: [h + 0.75, 0.25] });
      // rooftop solar water heaters, a Tel Aviv signature (panel + white tank), from the 1950s on
      if (y > 1950 && h < 40 && w > 7 && d > 7 && r2 < 0.75) {
        const n = 1 + Math.floor(r1 * 3), ca = Math.cos(ang), sa = Math.sin(ang);
        for (let q = 0; q < n; q++) {
          const ox = (hash2(i, 20 + q) - 0.5) * (w - 4), oz = (hash2(i, 30 + q) - 0.5) * (d - 4);
          const px = x + ox * ca + oz * sa, pz = z - ox * sa + oz * ca;
          SOLAR.push({ m: M4(px, y0, pz, ang, 2.2, 1, 1.4), c: solarDark, t: [b + 0.5, NEVER, NEVER, r2], h: [h + 1.0, 0.5] });
          SOLAR.push({ m: M4(px, y0, pz + 1.2, ang, 2.0, 1, 0.8), c: solarTank, t: [b + 0.5, NEVER, NEVER, r2], h: [h + 1.0, 1.0] });
        }
      }
    }
  }
  scene.add(growMesh(unitBox(), STD({ roughness: 0.92 }), "house", wallR, { facade: 1 }));
  scene.add(growMesh(unitBox(), STD({ roughness: 0.6 }), "house", SOLAR, { shadow: false }));
  scene.add(growMesh(unitBox(), STD({ roughness: 1 }), "house", roofR, { shadow: false }));
  scene.add(growMesh(facet(hipRoof()), STD({ roughness: 0.9, flatShading: true }), "uniform", hipR));
  scene.add(growMesh(unitBox(), STD({ roughness: 0.28, metalness: 0.08 }), "house", glassR, { facade: 2 }));
  scene.add(growMesh(unitBox(), STD({ roughness: 0.6 }), "house", capR, { shadow: false }));

  // ---------- trees: parks, boulevards (cleared nowhere: they come with the streets) ----------
  const trunkR = [], crownR = [];
  const GREENS = ["#5a9a3c", "#4f8f36", "#68a844", "#43822f", "#72b04a", "#5f9e3f"];
  for (let i = 0; i < DATA.T.length; i += 4) {
    const [y, x, z, s] = DATA.T.slice(i, i + 4);
    if (isWet(x, z)) continue;
    const r1 = hash2(i, 7), r2 = hash2(i, 8), b = tOf(y) + 0.5 + r1;
    const gy = heightAt(x, z) - 0.3, hgt = (4.5 + r1 * 3) * s;
    trunkR.push({ m: M4(x, gy, z, r2 * 6, 0.45, hgt, 0.45), c: new THREE.Color("#7a6347"), t: [b, NEVER, NEVER, r1] });
    crownR.push({ m: M4(x, gy + hgt, z, r1 * 6.28, 3.8 * s, 3.4 * s, 3.8 * s), c: new THREE.Color(GREENS[Math.floor(r2 * 5.99)]), t: [b, NEVER, NEVER, r1] });
  }
  // street trees on every street (Tel Aviv's ficus and plane trees), planted a few years after the street
  for (const sg of segs) {
    if (sg.w < 4.5) continue;
    const L = Math.hypot(sg.bx - sg.ax, sg.bz - sg.az); if (L < 6) continue;
    const ux = (sg.bx - sg.ax) / L, uz = (sg.bz - sg.az) / L, off = sg.w / 2 + 2.2;
    for (let d0 = 4; d0 < L; d0 += 11) for (const sgn of [-1, 1]) {
      const x = sg.ax + ux * d0 - uz * off * sgn, z = sg.az + uz * d0 + ux * off * sgn, r1 = hash2(Math.round(x * 3), Math.round(z * 3));
      if (r1 < 0.18 || isWet(x, z)) continue;
      let hb = NEVER; for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) { const v = houseAt.get((Math.floor(x / HCS) + dx) * 100003 + Math.floor(z / HCS) + dz); if (v !== undefined) hb = Math.min(hb, v); }
      if (hb >= NEVER) continue;                      // no houses on this street yet: no street trees either
      const b = Math.max(sg.ba + 4, hb + 1.5) + r1 * 3, gy = heightAt(x, z) - 0.3, s = 0.75 + r1 * 0.4, hgt = 4.2 * s;
      if (yearF(Math.min(DUR, b)) < 1915) continue;
      trunkR.push({ m: M4(x, gy, z, r1 * 6, 0.4, hgt, 0.4), c: new THREE.Color("#7a6347"), t: [b, NEVER, NEVER, r1] });
      crownR.push({ m: M4(x, gy + hgt, z, r1 * 6.28, 3.4 * s, 3.0 * s, 3.4 * s), c: new THREE.Color(GREENS[Math.floor(r1 * 5.99)]), t: [b, NEVER, NEVER, r1] });
    }
  }
  // orchards round Jaffa and Sarona before the city (the land of the citrus groves), cleared as houses arrive
  const clearAt = (x, z) => { let t = NEVER; for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) { const v = houseAt.get((Math.floor(x / HCS) + dx) * 100003 + Math.floor(z / HCS) + dz); if (v !== undefined) t = Math.min(t, v - 0.4); } return t; };
  const [jx, jz] = LL(32.0535, 34.7525), [sx, sz] = LL(32.0718, 34.7865);
  for (let gx = -260; gx <= 260; gx++) for (let gz = -260; gz <= 260; gz++) {
    const x = gx * 12 + (rnd() - 0.5) * 6, z = gz * 12 + (rnd() - 0.5) * 6, r1 = rnd(), r2 = rnd();
    const near = Math.min(Math.hypot(x - jx - 900, z - jz + 200) / 1400, Math.hypot(x - sx - 500, z - sz) / 1300);
    if (near > 1 || fbm(x * 0.004 + 7, z * 0.004 - 3) < 0.5 + near * 0.12 || shoreDist(x, z) < 160) continue;
    const death = clearAt(x, z); if (death < 2) continue;
    const gy = heightAt(x, z) - 0.3, hgt = 2.4 + r1 * 1.2;
    trunkR.push({ m: M4(x, gy, z, r2 * 6, 0.35, hgt, 0.35), c: new THREE.Color("#6e5a40"), t: [-1, death, NEVER, r1] });
    crownR.push({ m: M4(x, gy + hgt, z, r1 * 6.28, 2.6, 2.4, 2.6), c: new THREE.Color(["#3f6a2f", "#4a7535", "#38612b"][Math.floor(r2 * 2.99)]), t: [-1, death, NEVER, r1] });
  }
  const trunkGeo = new THREE.CylinderGeometry(0.5, 0.7, 1, 5); trunkGeo.translate(0, 0.5, 0);
  scene.add(growMesh(trunkGeo, STD({ roughness: 1 }), "uniform", trunkR, { shadow: false }));
  scene.add(growMesh(facet(new THREE.IcosahedronGeometry(1, 0)), STD({ flatShading: true, roughness: 0.95 }), "uniform", crownR));

  // ---------- ground texture: streets (with birth times) and the built-up paving round houses ----------
  const GX = { X0: -3400, Z0: -4200, EXT: 7800, TEX: 4096 };
  const groundTex = rasterGround(GX, segs, [], []);
  const paving = [];
  for (let i = 0; i < B.length; i += 9) { const x = B[i] / 10, z = B[i + 1] / 10, w = B[i + 2] / 10, d = B[i + 3] / 10; paving.push({ x, z, rx: w / 2 + 13, rz: d / 2 + 13, ry: -B[i + 4] / 1000, b: Math.max(0, tOf(B[i + 6] / 100) - 0.5) }); }
  const urbanTex = rasterGround(GX, [], paving, []);
  const PK = DATA.P, pkRaw = Uint8Array.from(atob(PK.b64), (c) => c.charCodeAt(0));
  const parkTex = new THREE.DataTexture(pkRaw, PK.n, PK.n, THREE.RGFormat); parkTex.flipY = false; parkTex.needsUpdate = true;

  // ---------- terrain ----------
  const TWD = 13000, TN = 1000;
  const tGeo = new THREE.PlaneGeometry(TWD, TWD, TN, TN); tGeo.rotateX(-Math.PI / 2); tGeo.translate(-1000, 0, 0);
  const tp = tGeo.attributes.position;
  for (let i = 0; i < tp.count; i++) tp.setY(i, heightAt(tp.getX(i), tp.getZ(i)));
  tGeo.computeVertexNormals();
  const UT = { uGround: { value: groundTex }, uUrban: { value: urbanTex }, uOrig: { value: new THREE.Vector4(GX.X0, GX.Z0, GX.EXT, GX.TEX) }, uPave: { value: 0 }, uPark: { value: parkTex }, uPorig: { value: new THREE.Vector4(PK.x0, PK.z0, PK.ext, PK.n) }, uYear: { value: 1880 } };
  const tMat = STD({ color: "#ffffff", roughness: 1 });
  tMat.onBeforeCompile = (s) => {
    Object.assign(s.uniforms, UT, { uTime: U.uTime });
    s.vertexShader = s.vertexShader.replace("#include <common>", "#include <common>\nvarying vec3 vW;")
      .replace("#include <worldpos_vertex>", "#include <worldpos_vertex>\nvW = (modelMatrix * vec4(transformed, 1.0)).xyz;");
    s.fragmentShader = s.fragmentShader.replace("#include <common>", `#include <common>
      varying vec3 vW; uniform sampler2D uGround, uUrban, uPark; uniform vec4 uOrig, uPorig; uniform float uTime, uPave, uYear;
      ${GROUND_GLSL}`)
      .replace("#include <color_fragment>", /* glsl */ `#include <color_fragment>
      {
        float nz = n21(vW.xz * 0.004), nf = n21(vW.xz * 0.03);
        vec3 sand = mix(Ls(vec3(0.89, 0.80, 0.62)), Ls(vec3(0.84, 0.74, 0.56)), nz);
        sand = mix(sand, Ls(vec3(0.93, 0.86, 0.70)), nf * 0.35);
        vec3 scrub = mix(Ls(vec3(0.66, 0.66, 0.44)), Ls(vec3(0.58, 0.60, 0.38)), nf);
        vec3 col = mix(sand, scrub, smoothstep(0.55, 0.8, n21(vW.xz * 0.0016 + 4.0)) * 0.55);
        col = mix(col, Ls(vec3(0.95, 0.90, 0.78)), smoothstep(1.6, 0.5, vW.y) * 0.8);             // the beach
        vec2 uv = (vW.xz - uOrig.xy) / uOrig.z;
        if (uv.x > 0.0 && uv.y > 0.0 && uv.x < 1.0 && uv.y < 1.0) {
          vec4 ur = texture2D(uUrban, uv); vec4 un = texelFetch(uUrban, ivec2(uv * uOrig.w), 0);
          float ub = (un.g * 255.0 * 256.0 + un.b * 255.0) / 100.0;
          vec3 lot = mix(Ls(vec3(0.80, 0.75, 0.64)), Ls(vec3(0.70, 0.69, 0.66)), uPave);
          col = mix(col, lot * mix(0.95, 1.05, nf), ur.r * smoothstep(ub, ub + 0.8, uTime) * 0.85);
          vec4 g = texture2D(uGround, uv); vec4 gn = texelFetch(uGround, ivec2(uv * uOrig.w), 0);
          float birth = (gn.g * 255.0 * 256.0 + gn.b * 255.0) / 100.0;
          float road = g.r * smoothstep(birth, birth + 0.6, uTime);
          vec3 dirt = Ls(vec3(0.76, 0.66, 0.50)), asph = mix(Ls(vec3(0.33, 0.34, 0.36)), Ls(vec3(0.39, 0.40, 0.42)), nf);
          col = mix(col, mix(dirt, asph, uPave), road * 0.95);
        }
        vec2 pv = (vW.xz - uPorig.xy) / uPorig.z;
        if (pv.x > 0.0 && pv.y > 0.0 && pv.x < 1.0 && pv.y < 1.0) {
          vec2 pk = texelFetch(uPark, ivec2(pv * uPorig.w), 0).rg;
          float py = (pk.r * 255.0 + pk.g * 255.0 * 256.0) / 100.0 + 1800.0;
          if (py > 1800.5) {
            vec3 grass = mix(Ls(vec3(0.42, 0.66, 0.26)), Ls(vec3(0.50, 0.72, 0.30)), nf) * mix(0.92, 1.06, nz);
            col = mix(col, grass, smoothstep(py, py + 1.5, uYear) * 0.95);
          }
        }
        diffuseColor.rgb = col;
      }`);
  };
  const terrain = new THREE.Mesh(tGeo, tMat); terrain.receiveShadow = true; scene.add(terrain);
  const ringG = new THREE.RingGeometry(9000, 60000, 192, 1).rotateX(-Math.PI / 2), rp = ringG.attributes.position, rc = new Float32Array(rp.count * 3);
  for (let i = 0; i < rp.count; i++) {                  // the far ring: the Mediterranean to the west, land to the east
    const ax = rp.getX(i), az = rp.getZ(i), a = Math.atan2(az, ax), sea = sm(clamp((Math.cos(a) * -1 - 0.05) / 0.25));
    const c = new THREE.Color("#c9b98e").lerp(new THREE.Color("#1f6f9a"), sea); rc[i * 3] = c.r; rc[i * 3 + 1] = c.g; rc[i * 3 + 2] = c.b;
  }
  ringG.setAttribute("color", new THREE.BufferAttribute(rc, 3));
  const farGround = new THREE.Mesh(ringG, STD({ vertexColors: true, roughness: 0.8 }));
  farGround.position.set(-1000, 1, 0); scene.add(farGround);

  // ---------- the sea and the Yarkon: two tones, foam at the shore ----------
  const wGeo = new THREE.PlaneGeometry(TWD, TWD, 500, 500); wGeo.rotateX(-Math.PI / 2); wGeo.translate(-1000, 0, 0);
  const wp = wGeo.attributes.position, wDepth = new Float32Array(wp.count);
  for (let i = 0; i < wp.count; i++) wDepth[i] = -heightAt(wp.getX(i), wp.getZ(i));
  wGeo.setAttribute("aDepth", new THREE.BufferAttribute(wDepth, 1));
  const wMat = new THREE.MeshStandardMaterial({ color: "#ffffff", roughness: 0.55 });
  wMat.onBeforeCompile = (s) => {
    s.uniforms.uTime = U.uTime;
    s.vertexShader = s.vertexShader.replace("#include <common>", "#include <common>\nattribute float aDepth; varying float vDepth; varying vec3 vWp;")
      .replace("#include <worldpos_vertex>", "#include <worldpos_vertex>\nvDepth = aDepth; vWp = (modelMatrix * vec4(transformed, 1.0)).xyz;");
    s.fragmentShader = s.fragmentShader.replace("#include <common>", `#include <common>
      varying float vDepth; varying vec3 vWp; uniform float uTime;
      float wh(vec2 p){ return fract(sin(dot(p, vec2(41.3, 289.1))) * 15731.743); }
      float wn(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f); return mix(mix(wh(i), wh(i+vec2(1,0)), f.x), mix(wh(i+vec2(0,1)), wh(i+vec2(1,1)), f.x), f.y); }
      vec3 Lw(vec3 c){ return pow(c, vec3(2.2)); }`)
      .replace("#include <color_fragment>", /* glsl */ `#include <color_fragment>
        if (vDepth < 0.0) discard;
        vec3 wc = mix(Lw(vec3(0.25, 0.72, 0.76)), Lw(vec3(0.12, 0.43, 0.62)), smoothstep(0.4, 6.0, vDepth));
        float foam = (1.0 - smoothstep(0.05, 0.45, vDepth)) * (0.55 + 0.45 * wn(vWp.xz * 0.25 + uTime * 0.5));
        wc = mix(wc, Lw(vec3(0.92, 0.94, 0.90)), foam * 0.7);
        diffuseColor.rgb = wc;`)
      .replace("#include <normal_fragment_maps>", /* glsl */ `#include <normal_fragment_maps>
        vec2 q = vWp.xz * 0.05 + vec2(0.0, uTime * 0.4);
        float e = 0.6, h0 = wn(q + uTime * 0.15) + 0.5 * wn(q * 2.3 - uTime * 0.2);
        float hx = wn(q + vec2(e, 0.0) + uTime * 0.15) + 0.5 * wn((q + vec2(e, 0.0)) * 2.3 - uTime * 0.2);
        float hz = wn(q + vec2(0.0, e) + uTime * 0.15) + 0.5 * wn((q + vec2(0.0, e)) * 2.3 - uTime * 0.2);
        normal = normalize(normal + (mat3(viewMatrix) * vec3(-(hx - h0), 0.0, -(hz - h0))) * 0.12);`);
  };
  const water = new THREE.Mesh(wGeo, wMat); water.receiveShadow = true; scene.add(water);

  // ---------- landmarks ----------
  const groupAt = (x, z, ry = 0) => { const g = new THREE.Group(); g.position.set(x, heightAt(x, z) - 0.6, z); g.rotation.y = ry; scene.add(g); return g; };
  // the Herzliya Hebrew Gymnasium (1909-10, demolished 1962): a castle-like front with two towers
  const SM = TW["Shalom Meir Tower"] || { x: -300, z: 700 };
  const gym = groupAt(SM.x, SM.z, 0.12);
  const STONE = "#e6d6b4", DARKW = "#5a4a3a";
  grow(box(44, 3, 30, "#cdbb95", 0, 0, 0, gym), T.gym[0], T.gym[0] + 1.5, "y", { off: T.gymDown, offB: T.gymDown + 1.5 });
  grow(box(36, 11, 22, STONE, 0, 3, 0, gym), T.gym[0] + 1.5, T.gym[0] + 5, "y", { off: T.gymDown, offB: T.gymDown + 1.5 });
  for (const sx of [-1, 1]) { const tw = box(7, 20, 7, STONE, sx * 9, 3, -9, gym); box(7.8, 1.2, 7.8, "#c7a372", 0, 20, 0, tw); grow(tw, T.gym[0] + 4, T.gym[1], "y", { off: T.gymDown, offB: T.gymDown + 1.4 }); }
  grow(box(6, 7, 0.6, DARKW, 0, 3, -11.2, gym), T.gym[1] - 2, T.gym[1], "y", { off: T.gymDown, offB: T.gymDown + 1.2 });
  // the Azrieli Center: data gives the towers; a cylinder crown on the round one reads better
  const AZ = TW["Azrieli Circular Tower"];
  if (AZ) { const g = groupAt(AZ.x, AZ.z); const c = new THREE.Mesh(new THREE.CylinderGeometry(24, 24, AZ.h, 28).translate(0, AZ.h / 2, 0), STD({ color: "#8eaec6", roughness: 0.3, metalness: 0.3 })); c.castShadow = c.receiveShadow = true; g.add(c); grow(c, T.azrieli, T.azrieli + 3, "y"); }

  // ---------- smoke: the 1940 air raid is too small to show; the only puffs are construction dust on the big beats ----------
  const dust = [];
  for (const [t0, x, z] of [[T.gym[0], SM.x, SM.z], [T.gymDown, SM.x, SM.z]]) for (let k = 0; k < 6; k++) dust.push({ x: x + (hash2(k, 1) - 0.5) * 40, y: 6, z: z + (hash2(k, 2) - 0.5) * 30, t0: t0 + k * 0.3, t1: t0 + 3 + k * 0.2, ph: hash2(k, 3), rise: 40, spread: 18, size0: 3, speed: 0.3, wind: [30, -10] });
  const updDust = puffs(scene, dust, { color: "#d8ccb4", opacity: 0.3, perCol: 10 });

  // ---------- camera: one flight, mostly from over the sea looking east ----------
  const P = (lat, lon) => LL(lat, lon);
  const [ax, az] = P(32.0545, 34.754), [nx, nz] = P(32.0607, 34.7655), [bx, bz] = P(32.0636, 34.7718), [wx, wz] = P(32.0800, 34.7770);
  const [px, pz] = P(32.0975, 34.7740), [ix, iz] = P(32.0628, 34.7708), [zx, zz] = AZ ? [AZ.x, AZ.z] : P(32.0744, 34.7922);
  const [rx, rz] = P(32.0808, 34.7806);
  const SR = TW["Azrieli Sarona Tower"] || { x: zx + 150, z: zz - 300 };
  const cam = cameraPath([
    [0, [ax - 900, 520, az + 700], [ax + 50, 0, az - 60]],
    [12, [ax - 520, 330, az + 360], [ax + 120, 0, az - 140]],
    [24, [nx - 620, 380, nz + 520], [nx + 40, 0, nz - 40]],
    [38, [bx - 900, 560, bz + 650], [bx, 0, bz - 80]],
    [52, [bx - 380, 230, bz + 300], [bx + 40, 0, bz]],
    [62, [SM.x - 210, 140, SM.z + 170], [SM.x, 10, SM.z]],
    [76, [bx - 1400, 900, bz + 1100], [bx + 200, 0, bz - 300]],
    [96, [bx - 1500, 1000, bz + 600], [bx + 300, 0, bz - 600]],
    [118, [bx - 1300, 850, bz + 700], [bx + 250, 0, bz - 350]],
    [140, [wx - 1100, 700, wz + 1300], [wx + 60, 0, wz + 600]],
    [160, [wx - 640, 400, wz + 800], [wx + 40, 0, wz + 280]],
    [177, [px - 620, 380, pz + 520], [px + 40, 0, pz + 80]],
    [190, [wx - 1900, 1300, wz + 1600], [wx + 200, 0, wz - 200]],
    [204, [ix - 330, 180, iz + 260], [ix, 8, iz]],
    [224, [ax - 700, 420, az + 520], [ax + 100, 0, az - 100]],
    [246, [wx - 2400, 1600, wz + 2200], [wx + 400, 0, wz - 200]],
    [270, [SM.x - 700, 420, SM.z + 600], [SM.x, 40, SM.z]],
    [288, [SM.x - 300, 230, SM.z + 260], [SM.x, 60, SM.z]],
    [312, [wx - 2200, 1500, wz + 1900], [wx + 500, 0, wz - 300]],
    [340, [zx - 1800, 1100, zz + 1500], [zx - 300, 0, zz]],
    [355, [rx - 520, 320, rz + 420], [rx, 0, rz]],
    [366, [rx - 700, 420, rz + 600], [rx + 80, 0, rz - 40]],
    [384, [zx - 520, 330, zz + 420], [zx, 80, zz]],
    [412, [zx - 1500, 900, zz + 1300], [zx - 200, 40, zz - 200]],
    [444, [SR.x - 600, 360, SR.z + 520], [SR.x, 90, SR.z]],
    [470, [wx - 2000, 1200, wz + 1700], [wx + 500, 40, wz - 300]],
    [492, [ix - 1600, 900, iz + 1500], [ix + 600, 30, iz - 400]],
    [515, [wx - 2400, 2500, wz + 2200], [wx + 600, 0, wz - 200]],
    [DUR, [wx - 2900, 3300, wz + 2700], [wx + 700, 0, wz - 200]],
  ]);
  const drawHud = hudDriver(hud, { ERAS, FLAGS, TITLE, LANDMARKS, CAPTIONS, CARDS, yearAt, popAt, DUR });

  const ready = Promise.resolve();
  function renderAt(time) {
    const t = clamp(time, 0, DUR);
    U.uTime.value = t;
    UT.uPave.value = sm(ramp(yearF(t), 1925, 1960)); UT.uYear.value = yearF(t);
    updateLM(t); updDust(t);
    const { pos, tgt } = cam(t);
    st.frame(pos, tgt);
    const wide = sm(ramp(t, 500, 530)); st.scene.fog.near *= lerp(1.3, 1.0, wide); st.scene.fog.far *= lerp(1.4, 1.1, wide);
    drawHud(t);
    st.render();
  }
  return { ready, renderAt, DUR, stats: { houses: wallR.length, towers: glassR.length, roofs: hipR.length, trees: crownR.length, roads: segs.length } };
}
