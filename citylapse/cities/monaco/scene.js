import * as THREE from "three";
import {
  clamp, lerp, ramp, sm, V, mulberry32, hash2, vnoise, fbm, pl, inv, M4, NEVER, U, STD, growMesh, unitBox, hipRoof, facet,
  createStage, rasterGround, growPrisms, GROUND_GLSL, landmarks, cameraPath, hudDriver, puffs,
} from "./engine.js";
import { DATA } from "./data.js";

// "MONACO – 3D TIMELAPSE – 1215 to 2026". SPEC.md has the beats, FACTS.md the sources of every caption.
// Every building is a real footprint (OpenStreetMap via Overture Maps, tools/osm_data_monaco.py) on the real relief
// (Copernicus GLO-30). Years: real years for the towers and landmarks, documented development of each quarter for
// the rest (an approximate reconstruction). Fontvieille, Larvotto and Mareterra rise out of the sea on their dates.
// World metres, x east, z south, origin 43.7375 N 7.4235 E.

export const W = 1920, H = 1080, SS = 1.5, MDUR = 500, INTRO = 9, DUR = MDUR + INTRO;

// ---------------- land: the real coast and relief ----------------
const SG = DATA.S, SD = Uint8Array.from(atob(SG.b64), (c) => c.charCodeAt(0));
const EHb = Uint8Array.from(atob(SG.e64), (c) => c.charCodeAt(0)), EH = new Int16Array(EHb.buffer, 0, SG.nx * SG.nz);
const cI = (i) => clamp(i, 0, SG.nz - 1), cJ = (j) => clamp(j, 0, SG.nx - 1);
const sdRaw = (i, j) => { const v = SD[cI(i) * SG.nx + cJ(j)]; return v > 127 ? v - 256 : v; };
const ehRaw = (i, j) => EH[cI(i) * SG.nx + cJ(j)] / 10;
function bil(f, x, z) {
  const fx = (x - SG.x0) / SG.g - 0.5, fz = (z - SG.z0) / SG.g - 0.5, j = Math.floor(fx), i = Math.floor(fz), u = fx - j, v = fz - i;
  return lerp(lerp(f(i, j), f(i, j + 1), u), lerp(f(i + 1, j), f(i + 1, j + 1), u), v);
}
const shoreDist = (x, z) => bil(sdRaw, x, z);          // signed metres to the water's edge (< 0 in the sea)
const relief = (x, z) => bil(ehRaw, x, z);
// the reclaimed areas (today's land): rings in world metres, with a quick bounding box
const RC = DATA.RC.map((r) => { const xs = r.ring.map((p) => p[0]), zs = r.ring.map((p) => p[1]);
  return { ...r, x0: Math.min(...xs), x1: Math.max(...xs), z0: Math.min(...zs), z1: Math.max(...zs) }; });
const inRing = (r, px, pz) => { let c = false; for (let a = 0, b = r.length - 1; a < r.length; b = a++) if ((r[a][1] > pz) !== (r[b][1] > pz) && px < ((r[b][0] - r[a][0]) * (pz - r[a][1])) / (r[b][1] - r[a][1]) + r[a][0]) c = !c; return c; };
const rcAt = (x, z) => { for (let k = 0; k < RC.length; k++) { const r = RC[k]; if (x > r.x0 && x < r.x1 && z > r.z0 && z < r.z1 && inRing(r.ring, x, z)) return k; } return -1; };
function landH(x, z) {
  const d = shoreDist(x, z);
  if (d < 0) return Math.max(-16, d * 0.3) - 0.5;          // the sea floor drops fast off this coast
  return 0.9 + Math.max(0, relief(x, z) - 0.9) * sm(clamp(d / 22));
}
for (const r of RC) {                                       // each reclaimed area is a flat platform at its mean height
  let s = 0, n = 0; for (let k = 0; k < 400; k++) { const x = lerp(r.x0, r.x1, hash2(k, 1)), z = lerp(r.z0, r.z1, hash2(k, 2)); if (inRing(r.ring, x, z)) { s += Math.min(8, landH(x, z)); n++; } }
  r.top = n ? Math.max(1.6, s / n) : 2;
}
const heightAt = (x, z) => { const k = rcAt(x, z); return k >= 0 ? RC[k].top : landH(x, z); };
const seabed = (x, z) => (rcAt(x, z) >= 0 ? -9 : landH(x, z));   // the ground mesh: the sea where land was won later
const isWet = (x, z) => shoreDist(x, z) < 2;
const KX = DATA.k[0], KY = DATA.k[1];
const LL = (lat, lon) => [(lon - 7.4235) * KX, -(lat - 43.7375) * KY];

// ---------------- time: video seconds → year ----------------
const YK = [
  [0, 1215.44], [14, 1216], [18, 1297.0], [27, 1297.03], [40, 1346], [52, 1430], [60, 1524], [70, 1633], [78, 1641.7], [92, 1740],
  [100, 1793], [106, 1814.4], [112, 1848.2], [118, 1856.95], [124, 1861.09], [131, 1861.1], [142, 1863.6], [152, 1866.6], [160, 1868.5],
  [174, 1879.1], [194, 1899.3], [204, 1903.8], [214, 1910.3], [220, 1911.1], [238, 1926], [244, 1929.27], [251, 1929.3], [262, 1942.86],
  [268, 1944.7], [276, 1949.4], [284, 1954.5], [292, 1956.3], [300, 1961], [308, 1966], [326, 1973], [342, 1982], [352, 1985.07],
  [370, 1993.4], [384, 2000.55], [396, 2005.3], [410, 2009.8], [424, 2015.3], [432, 2017], [446, 2019.96], [462, 2024.93], [470, 2026], [MDUR, 2026],
];
const yearF = (t) => pl(YK, t);
const yearAt = (t) => Math.floor(yearF(t));
const tOf = (y) => (y <= YK[0][1] ? -1 : inv(yearF, y, 0, MDUR));

const ERAS = [
  { t: 0, name: "REPUBLIC OF GENOA", flag: "genoa" },
  { t: 18, name: "THE GRIMALDIS", flag: "monaco" },
  { t: tOf(1524.5), name: "UNDER SPANISH PROTECTION", flag: "monaco" },
  { t: tOf(1641.75), name: "UNDER FRENCH PROTECTION", flag: "monaco" },
  { t: tOf(1793.1), name: "ANNEXED BY FRANCE", flag: "france" },
  { t: tOf(1814.45), name: "PRINCIPALITY OF MONACO", flag: "monaco" },
  { t: tOf(1815.9), name: "UNDER SARDINIAN PROTECTION", flag: "monaco" },
  { t: 131, name: "PRINCIPALITY OF MONACO", flag: "monaco" },
];
const FLAGS = {
  genoa: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#fff"/><rect x="58" width="24" height="84" fill="#c8102e"/><rect y="30" width="140" height="24" fill="#c8102e"/></svg>`,
  monaco: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#fff"/><rect width="140" height="42" fill="#ce1126"/></svg>`,
  france: `<svg viewBox="0 0 140 84"><rect width="47" height="84" fill="#002395"/><rect x="47" width="46" height="84" fill="#fff"/><rect x="93" width="47" height="84" fill="#ed2939"/></svg>`,
};
const TITLE = [1.2, 8];
const LANDMARKS = [
  { a: 9, b: 15.5, text: "THE ROCK OF MONACO" },
  { a: 44, b: 50, text: "PRINCE'S PALACE" },
  { a: 143, b: 149, text: "CASINO DE MONTE-CARLO" },
  { a: 198, b: 203.5, text: "SAINT NICHOLAS CATHEDRAL" },
  { a: 214.5, b: 220, text: "OCEANOGRAPHIC MUSEUM" },
  { a: 228, b: 233.5, text: "PORT HERCULE" },
  { a: 296, b: 301.5, text: "LARVOTTO" },
  { a: 318, b: 323.5, text: "FONTVIEILLE" },
  { a: 353, b: 358.5, text: "STADE LOUIS II" },
  { a: 385, b: 390.5, text: "GRIMALDI FORUM" },
  { a: 425, b: 430.5, text: "ODEON TOWER" },
  { a: 449, b: 454.5, text: "MARETERRA" },
];
const CAPTIONS = [
  { a: 2.5, b: 8.5, lines: ["On 10 June 1215, Genoese led by Fulco del Cassello", "began a fortress on the Rock of Monaco."] },
  { a: 28, b: 34.5, lines: ["On the night of 8 January 1297 François Grimaldi took the fortress,", "reportedly disguised as a monk."] },
  { a: 36, b: 42.5, lines: ["The Grimaldis acquired Menton in 1346", "and Roquebrune in 1355."] },
  { a: 60.5, b: 66.5, lines: ["In 1524 Monaco placed itself", "under the protection of Spain."] },
  { a: 70, b: 76, lines: ["In 1633 Spain recognised Honoré II", "as the Prince of Monaco."] },
  { a: 78.5, b: 84.5, lines: ["The Treaty of Péronne, on 14 September 1641,", "made Monaco a French protectorate."] },
  { a: 100.5, b: 106, lines: ["From 1793 to 1814 Monaco was annexed by France;", "the palace was looted."] },
  { a: 112.2, b: 117.8, lines: ["On 21 March 1848 Menton and Roquebrune", "broke away from Monaco."] },
  { a: 118.2, b: 123.6, lines: ["On 14 December 1856 the first casino", "opened in La Condamine."] },
  { a: 131.2, b: 138, lines: ["Monaco ceded Menton and Roquebrune to France for 4 million francs,", "losing more than 90% of its territory."] },
  { a: 149.5, b: 155.5, lines: ["In 1864 the Hôtel de Paris opened", "beside the casino."] },
  { a: 156, b: 162, lines: ["On 1 June 1866 the new quarter on the Spélugues", "was named Monte-Carlo."] },
  { a: 162.5, b: 168.5, lines: ["In 1868 the railway", "reached Monaco."] },
  { a: 172, b: 178, lines: ["On 25 January 1879 Charles Garnier's opera hall", "opened at the casino."] },
  { a: 204, b: 210, lines: ["Built from 1875 to 1903 in white La Turbie stone,", "it replaced the parish church of 1252."] },
  { a: 220.5, b: 226.5, lines: ["Founded by Prince Albert I, the museum", "opened on the cliff in 1910."] },
  { a: 234, b: 240, lines: ["The jetties of Port Hercule were built", "between 1902 and 1926."] },
  { a: 251.2, b: 258, lines: ["William Grover-Williams won the first Monaco Grand Prix,", "in a Bugatti, over 100 laps of the streets."] },
  { a: 262.5, b: 268, lines: ["Italian troops occupied Monaco in November 1942;", "German forces followed in 1943."] },
  { a: 268.5, b: 274, lines: ["Monaco was liberated", "on 3 September 1944."] },
  { a: 276.2, b: 282, lines: ["Rainier III became Prince of Monaco", "on 9 May 1949."] },
  { a: 286, b: 292, lines: ["In April 1956 Prince Rainier III married", "the American actress Grace Kelly."] },
  { a: 302, b: 308, lines: ["From 1954 to 1961 new land was won from the sea", "at Larvotto and Le Portier."] },
  { a: 324, b: 330, lines: ["From about 1966 to 1973 Fontvieille,", "some 22 hectares, was won from the sea."] },
  { a: 359, b: 365, lines: ["The new Stade Louis II opened on reclaimed land", "in Fontvieille on 25 January 1985."] },
  { a: 370.5, b: 376.5, lines: ["On 28 May 1993 Monaco joined", "the United Nations."] },
  { a: 391, b: 397, lines: ["The Grimaldi Forum, on the Larvotto seafront,", "opened on 20 July 2000."] },
  { a: 397.5, b: 403.5, lines: ["Albert II succeeded his father", "on 6 April 2005."] },
  { a: 431, b: 437, lines: ["Finished in 2015 at 170 m, the Odeon Tower", "is the tallest building in Monaco."] },
  { a: 455, b: 461, lines: ["Its 18 caissons were in place by July 2019;", "the 6-hectare Mareterra opened in December 2024."] },
  { a: 471, b: 477.5, lines: ["About a fifth of Monaco", "was won from the sea."] },
];
const MORE = [
  [1331.5, ["From 1331 the Grimaldis built two new halls", "inside the fortress."]],
  [1506.5, ["In 1506-07 the state-apartments wing", "was added to the palace."]],
  [1918.6, ["In 1918 Monaco counted 15,960 residents,", "down from 19,121 in 1908."]],
  [1962.96, ["The 1962 constitution gave women the vote", "and abolished the death penalty."]],
  [1999.93, ["In December 1999 the railway station", "moved underground."]],
];
const busy = (a, b) => [...CAPTIONS, ...LANDMARKS].some((c) => a < c.b + 0.6 && b > c.a - 0.6) || (a < TITLE[1] + 0.5);
for (const [y, lines] of MORE) { const a = tOf(y) + 0.3, b = a + 6; if (a > 0 && b < MDUR - 40 && !busy(a, b)) CAPTIONS.push({ a, b, lines }); }
CAPTIONS.sort((p, q) => p.a - q.a);
const CARDS = [
  { a: 19, b: 27, kicker: "8 JANUARY 1297", text: "FRANÇOIS GRIMALDI" },
  { a: 124.5, b: 130.8, kicker: "2 FEBRUARY 1861", text: "THE TREATY WITH FRANCE" },
  { a: 244.5, b: 250.8, kicker: "14 APRIL 1929", text: "THE FIRST GRAND PRIX" },
  { a: 480, b: 497, kicker: "1215 – 2026", text: "MONACO" },
];

// population of today's territory (IMSEE censuses; 1757 = Monaco without Menton and Roquebrune). FACTS.md §3.
const POP = [[1756.99, 0], [1757, 1350], [1792, 1192], [1861, 1200], [1868, 3443], [1873, 5741], [1878, 6049], [1883, 9108], [1888, 10864],
  [1893, 13001], [1898, 15102], [1903, 15543], [1908, 19121], [1918, 15960], [1928, 24927], [1938, 23956], [1951, 20202], [1956, 20422],
  [1962, 21783], [1968, 23035], [1975, 25029], [1982, 27063], [1990, 29972], [2000, 32020], [2008, 35352], [2016.4, 37308], [2023.99, 38367],
  [2025.99, 38857], [2026.5, 38857]];
const popAt = (t) => { const y = yearF(t); return y < 1757 ? 0 : pl(POP, y); };

// ---------------- build ----------------
export function buildVideo(canvas, hud) {
  const st = createStage(canvas, { W, H, SS, fog: "#d6e2ea", sunColor: "#fff1d8", sunDir: [-0.45, 0.72, 0.55], hemiSky: "#d4e7fa", hemiGround: "#8a8466", hemiI: 1.2, sunI: 3.3, saturation: 0.14, contrast: 0.15, tilt: 0.15, bloom: 0.28 });
  const { scene } = st;
  const { box, grow, update: updateLM } = landmarks();
  const TW = DATA.towers.reduce((o, t) => ((o[t.label] = o[t.label] || t), o), {});
  const [rockX, rockZ] = LL(43.7308, 7.4235), [palX, palZ] = TW["Prince's Palace"] ? [TW["Prince's Palace"].x, TW["Prince's Palace"].z] : LL(43.7314, 7.4200);
  const [casX, casZ] = LL(43.7394, 7.4276), [hdpX, hdpZ] = LL(43.7388, 7.4268), [porX, porZ] = LL(43.7350, 7.4230);
  const [stX, stZ] = LL(43.7276, 7.4156);
  const rcTo = (k) => tOf(RC[k].to);

  // ---------- roads ----------
  const segs = [];
  for (let i = 0; i < DATA.R.length; i += 6) {
    const [ax, az, bx, bz, w, y] = DATA.R.slice(i, i + 6);
    const mx = (ax + bx) / 2, mz = (az + bz) / 2;
    if (isWet(mx, mz) && rcAt(mx, mz) < 0) continue;
    const k = rcAt(mx, mz);
    const b = Math.max(k >= 0 ? rcTo(k) + 0.5 : 0, tOf(Math.max(y, 1700)) - 1.2);
    segs.push({ ax, az, bx, bz, w: Math.max(3.5, w * 0.9), ba: b, bb: b });
  }

  // ---------- buildings ----------
  // pastel plasters of the Riviera (cream, ochre, salmon, pink, yellow, pale blue), terracotta tiles, white stone
  const FACADES = [["#f2e6cf", 5], ["#efd7a8", 4], ["#e9c08a", 3], ["#f0c4a2", 3], ["#e8a98f", 3], ["#f3d6c8", 3], ["#e9b9b1", 2],
    ["#f1e3a6", 2], ["#d9925f", 2], ["#c97a55", 1], ["#f4efe6", 4], ["#d6dfe1", 2], ["#bfd0d8", 1], ["#e0d3c0", 3], ["#cbb79b", 2]];
  const FW = FACADES.reduce((a, f) => a + f[1], 0);
  const facadeAt = (h) => { let u = h * FW; for (const [c, w] of FACADES) { if ((u -= w) < 0) return c; } return FACADES[0][0]; };
  const ROOF = ["#b85c3c", "#c46a45", "#a9553a", "#cf7650", "#b9643f"];
  const MODERN = ["#f1eee7", "#e7e2d8", "#ddd6c8", "#efe6d2", "#d8d4cc", "#e9dcc6", "#cfd6da", "#f3ead9"];
  const GLASS = ["#a9c4d6", "#9fbdd0", "#8fb3c8", "#5f86a3", "#7fa7a4", "#b9d0de", "#4d6b80", "#6b8f9e"];
  const ROOFTOP = [["#b4b0a8", 4], ["#9a968f", 3], ["#d9d6cf", 3], ["#c2ab8c", 2], ["#b8644a", 3], ["#6f8c55", 1], ["#e9e6df", 2]];
  const RW = ROOFTOP.reduce((a, f) => a + f[1], 0);
  const roofAt = (h) => { let u = h * RW; for (const [c, w] of ROOFTOP) { if ((u -= w) < 0) return c; } return ROOFTOP[0][0]; };
  const BR = DATA.BR, rings = [];
  for (let i = 0; i < BR.length;) { const n = BR[i++], r = []; for (let q = 0; q < n; q++, i += 2) r.push([BR[i] / 10, BR[i + 1] / 10]); rings.push(r); }
  const prismR = [], prismG = [], wallR = [], hipR = [], glassR = [], capR = [];
  const cW = new THREE.Color();
  const B = DATA.B;
  const houseAt = new Map(), HCS = 16;
  const paving = [], cityPts = [];
  for (let i = 0; i < B.length; i += 9) {
    const x = B[i] / 10, z = B[i + 1] / 10, w = B[i + 2] / 10, d = B[i + 3] / 10, ang = B[i + 4] / 1000, h = Math.max(3.5, B[i + 5] / 10), kind = B[i + 7], ci = B[i + 8];
    const k = rcAt(x, z);
    if (isWet(x, z) && k < 0) continue;
    let y = B[i + 6] / 100;
    if (k >= 0) y = Math.max(y, RC[k].to + 0.6 + hash2(i, 17) * 4);
    // the casino and the Hôtel de Paris: the first buildings of Monte-Carlo
    if (Math.hypot(x - casX, z - casZ) < 45) y = 1863.2 + hash2(i, 18) * 0.4;
    else if (Math.hypot(x - hdpX, z - hdpZ) < 35) y = 1864.1 + hash2(i, 18) * 0.5;
    const r1 = hash2(i, 1), r2 = hash2(i, 2);
    const b = Math.max(0.2, tOf(y) + r1 * 0.6);
    // the lowest corner of the footprint, so houses on the steep slopes never float
    const ca = Math.cos(ang), sa = Math.sin(ang);
    let y0 = Infinity; for (const [ox, oz] of [[-w / 2, -d / 2], [w / 2, -d / 2], [-w / 2, d / 2], [w / 2, d / 2], [0, 0]]) y0 = Math.min(y0, heightAt(x + ox * ca + oz * sa, z - ox * sa + oz * ca));
    y0 -= 0.8;
    const hh = h + (heightAt(x, z) - 0.8 - y0) * 0.6;   // the uphill side still shows its full height
    const t = [b, NEVER, NEVER, r2];
    const key = Math.floor(x / HCS) * 100003 + Math.floor(z / HCS); const v = houseAt.get(key); if (v === undefined || v > b) houseAt.set(key, b);
    const ring = rings[i / 9].map(([dx, dz]) => [x + dx, z + dz]);
    paving.push({ x, z, rx: w * 0.56 + 1.2, rz: d * 0.56 + 1.2, ry: -ang, b: b - 0.5 }); cityPts.push(x, z, b);
    if (kind === 2 || h >= 45) {                       // towers
      cW.set(y > 1995 ? GLASS[(ci * 2 + Math.floor(r1 * 8)) % 8] : MODERN[Math.floor(r1 * 8)]);
      prismG.push({ ring, y0, c: cW.clone(), rc: new THREE.Color(roofAt(r2)), t, h: [0, hh] });
      capR.push({ m: M4(x, y0, z, ang, w * 0.86, 1, d * 0.86), c: new THREE.Color("#dfe2e2"), t: [b + 0.4, NEVER, NEVER, r2], h: [hh, 2.5] });
      continue;
    }
    // an old building that is taller than four floors today was rebuilt: first a small house, then today's block
    if (y < 1900 && h > 15) {
      const rb = tOf(Math.max(y + 30, 1905 + hash2(i, 11) * 70)), hs = 6 + r1 * 5, sw = Math.min(w, 13), sd = Math.min(d, 12);
      wallR.push({ m: M4(x, y0, z, ang, sw, 1, sd), c: new THREE.Color(facadeAt(hash2(i, 5))), t: [b, rb, NEVER, r2], h: [0, hs] });
      hipR.push({ m: M4(x, y0 + hs, z, ang, sw + 0.6, Math.min(4, Math.min(sw, sd) * 0.32), sd + 0.6), c: new THREE.Color(ROOF[Math.floor(r1 * 4.99)]), t: [b + 0.15, rb, NEVER, r2] });
      t[0] = rb + 0.6;
    }
    const modern = y > 1955 && h > 14;
    cW.set(modern && hash2(i, 6) < 0.55 ? MODERN[Math.floor(hash2(i, 4) * 8)] : facadeAt(hash2(i, 4))).multiplyScalar(0.94 + 0.1 * hash2(i, 7));
    const hip = !modern && w < 26 && d < 26 && (y < 1950 || hash2(i, 8) < 0.45);   // the Riviera's tiled hip roofs
    if (hip) {
      wallR.push({ m: M4(x, y0, z, ang, w, 1, d), c: cW.clone(), t, h: [0, hh + 0.8] });
      hipR.push({ m: M4(x, y0 + hh + 0.8, z, ang, w + 0.6, Math.min(5, Math.min(w, d) * 0.3), d + 0.6), c: new THREE.Color(ROOF[Math.floor(r1 * 4.99)]), t: [t[0] + 0.15, NEVER, NEVER, r2] });
    } else {
      prismR.push({ ring, y0, c: cW.clone(), rc: new THREE.Color(roofAt(hash2(i, 3))).lerp(cW, 0.15), t, h: [0, hh + 0.8] });
    }
  }
  for (const sg of segs) {                          // a street is laid out when its houses go up
    let hb = NEVER;
    for (const [qx, qz] of [[sg.ax, sg.az], [(sg.ax + sg.bx) / 2, (sg.az + sg.bz) / 2], [sg.bx, sg.bz]])
      for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) { const v = houseAt.get((Math.floor(qx / HCS) + dx) * 100003 + Math.floor(qz / HCS) + dz); if (v !== undefined) hb = Math.min(hb, v); }
    if (hb < NEVER) sg.ba = sg.bb = Math.max(sg.ba, hb - 1.0);
  }
  scene.add(growMesh(unitBox(), STD({ roughness: 0.92 }), "house", wallR, { facade: 1 }));
  scene.add(growMesh(facet(hipRoof()), STD({ roughness: 0.9, flatShading: true }), "uniform", hipR));
  scene.add(growMesh(unitBox(), STD({ roughness: 0.28, metalness: 0.08 }), "house", glassR, { facade: 2 }));
  scene.add(growMesh(unitBox(), STD({ roughness: 0.6 }), "house", capR, { shadow: false }));
  scene.add(growPrisms(prismR, STD({ roughness: 0.92 }), { facade: 1 }));
  scene.add(growPrisms(prismG, STD({ roughness: 0.35, metalness: 0.06 }), { facade: 2 }));

  // ---------- trees: parks and gardens with the houses, pines and maquis on the open slopes ----------
  const trunkR = [], crownR = [];
  const GREENS = ["#4b6f34", "#557a3d", "#43662f", "#5c8042", "#3d612c", "#507438"];
  const PINE = ["#3d5f2c", "#456a31", "#36582a"], OLIVE = ["#7d8f5a", "#8a9a66", "#74865a"];
  for (let i = 0; i < DATA.T.length; i += 4) {
    const [y0t, x, z, s] = DATA.T.slice(i, i + 4);
    if (isWet(x, z) && rcAt(x, z) < 0) continue;
    const k = rcAt(x, z), y = Math.max(y0t, k >= 0 ? RC[k].to + 2 : 1860);
    const r1 = hash2(i, 7), r2 = hash2(i, 8), b = tOf(y) + 0.5 + r1;
    if (b > MDUR) continue;
    const gy = heightAt(x, z) - 0.3, hgt = (4.5 + r1 * 3) * s;
    if (r2 < 0.18) {                                     // palms along the Riviera
      const ph = 7 + r1 * 8;
      trunkR.push({ m: M4(x, gy, z, 0, 0.3, ph, 0.3), c: new THREE.Color("#8a7458"), t: [b, NEVER, NEVER, r1] });
      crownR.push({ m: M4(x, gy + ph, z, r1 * 60, 3.0, 1.0, 3.0), c: new THREE.Color("#5a8a3a"), t: [b, NEVER, NEVER, r1] });
      continue;
    }
    trunkR.push({ m: M4(x, gy, z, r2 * 6, 0.45, hgt, 0.45), c: new THREE.Color("#7a6347"), t: [b, NEVER, NEVER, r1] });
    crownR.push({ m: M4(x, gy + hgt, z, r1 * 6.28, 3.8 * s, 3.2 * s, 3.8 * s), c: new THREE.Color(GREENS[Math.floor(r2 * 5.99)]), t: [b, NEVER, NEVER, r1] });
  }
  const clearAt = (x, z) => { let t = NEVER; for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) { const v = houseAt.get((Math.floor(x / HCS) + dx) * 100003 + Math.floor(z / HCS) + dz); if (v !== undefined) t = Math.min(t, v - 0.4); } return t; };
  // the wild hillsides: Aleppo pines and olive-grey maquis in soft clumps, thin on the steep rock, cleared by the city
  const roadT = new Map(), RCS = 8;
  for (const sg of segs) {
    const L = Math.hypot(sg.bx - sg.ax, sg.bz - sg.az); for (let d0 = 0; d0 <= L; d0 += 4) {
      const f = L ? d0 / L : 0, qx = sg.ax + (sg.bx - sg.ax) * f, qz = sg.az + (sg.bz - sg.az) * f;
      const kk = Math.floor(qx / RCS) * 100003 + Math.floor(qz / RCS), v = roadT.get(kk); if (v === undefined || v > sg.ba) roadT.set(kk, sg.ba);
    }
  }
  const roadAt = (x, z) => { let t = NEVER; for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) { const v = roadT.get((Math.floor(x / RCS) + dx) * 100003 + Math.floor(z / RCS) + dz); if (v !== undefined) t = Math.min(t, v); } return t; };
  const slope = (x, z) => Math.hypot(landH(x + 6, z) - landH(x - 6, z), landH(x, z + 6) - landH(x, z - 6)) / 12;
  for (let gx = -230; gx <= 210; gx++) for (let gz = -240; gz <= 240; gz++) {
    const x = gx * 9 + (hash2(gx + 11, gz) - 0.5) * 7, z = gz * 9 + (hash2(gz, gx + 13) - 0.5) * 7, r1 = hash2(gx * 17 + 3, gz * 19 + 5);
    if (shoreDist(x, z) < 12 || rcAt(x, z) >= 0) continue;
    const sl = slope(x, z), wd = fbm(x * 0.003 + 21, z * 0.003 - 13);
    const keep = (wd > 0.5 ? 0.5 : 0.16) * (sl > 1.1 ? 0.15 : 1);
    if (r1 > keep) continue;
    const death = Math.min(clearAt(x, z), roadAt(x, z) - 0.6); if (death < 2) continue;
    const q = hash2(gx * 5 + 1, gz * 7 + 2), gy = landH(x, z) - 0.3;
    if (q < 0.35) {                                       // an umbrella pine
      const ph = 6 + q * 14;
      trunkR.push({ m: M4(x, gy, z, q * 6, 0.4, ph, 0.4), c: new THREE.Color("#6e5a40"), t: [-1, death - q * 0.4, NEVER, r1] });
      crownR.push({ m: M4(x, gy + ph, z, r1 * 6.28, 4.6, 2.2, 4.6), c: new THREE.Color(PINE[Math.floor(q * 8.5) % 3]), t: [-1, death - q * 0.4, NEVER, r1] });
    } else {                                              // maquis and olives
      const sc = 0.7 + q * 0.7;
      crownR.push({ m: M4(x, gy, z, r1 * 6.28, 3.4 * sc, 2.4 * sc, 3.4 * sc), c: new THREE.Color(OLIVE[Math.floor(q * 9) % 3]), t: [-1, death - q * 0.4, NEVER, r1] });
    }
  }
  const trunkGeo = new THREE.CylinderGeometry(0.5, 0.7, 1, 5); trunkGeo.translate(0, 0.5, 0);
  scene.add(growMesh(trunkGeo, STD({ roughness: 1 }), "uniform", trunkR, { shadow: false }));
  scene.add(growMesh(facet(new THREE.IcosahedronGeometry(1, 0)), STD({ flatShading: true, roughness: 0.95 }), "uniform", crownR));

  // ---------- ground texture: streets and the paving round the houses ----------
  const GX = { X0: SG.x0, Z0: SG.z0, EXT: Math.max(SG.nx, SG.nz) * SG.g, TEX: 4096 };
  const groundTex = rasterGround(GX, segs, [], []);
  const urbanTex = rasterGround(GX, segs.map((sg) => ({ ...sg, w: sg.w + 3 })), paving, []);
  const PK = DATA.P, pkRaw = Uint8Array.from(atob(PK.b64), (c) => c.charCodeAt(0));
  const parkTex = new THREE.DataTexture(pkRaw, PK.n, PK.n, THREE.RGFormat); parkTex.flipY = false; parkTex.needsUpdate = true;

  // ---------- terrain: the real relief, cliffs in grey stone, maquis in olive green ----------
  const CX = (SG.x0 + SG.x0 + SG.nx * SG.g) / 2, CZ = (SG.z0 + SG.z0 + SG.nz * SG.g) / 2;
  const TWD = 9000, TN = 700;
  const tGeo = new THREE.PlaneGeometry(TWD, TWD, TN, TN); tGeo.rotateX(-Math.PI / 2); tGeo.translate(CX, 0, CZ);
  const tp = tGeo.attributes.position;
  for (let i = 0; i < tp.count; i++) tp.setY(i, seabed(tp.getX(i), tp.getZ(i)));
  tGeo.computeVertexNormals();
  const UT = { uGround: { value: groundTex }, uUrban: { value: urbanTex }, uOrig: { value: new THREE.Vector4(GX.X0, GX.Z0, GX.EXT, GX.TEX) }, uPave: { value: 0 }, uPark: { value: parkTex }, uPorig: { value: new THREE.Vector4(PK.x0, PK.z0, PK.ext, PK.n) }, uYear: { value: 1215 } };
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
        vec3 nW = normalize(cross(dFdx(vW), dFdy(vW))); float stp = 1.0 - abs(nW.y);
        float m1 = n21(vW.xz * 0.0016 + 9.0), m2 = n21(vW.xz * 0.006 - 4.0);
        vec3 maquis = mix(Ls(vec3(0.40, 0.45, 0.30)), Ls(vec3(0.49, 0.51, 0.35)), smoothstep(0.25, 0.75, m1));
        maquis = mix(maquis, Ls(vec3(0.62, 0.60, 0.48)), smoothstep(0.55, 0.9, m2) * 0.5);
        vec3 rock = mix(Ls(vec3(0.70, 0.67, 0.60)), Ls(vec3(0.80, 0.77, 0.70)), nz);
        vec3 col = mix(maquis, rock, smoothstep(0.30, 0.52, stp + (nf - 0.5) * 0.14));
        col = mix(col, rock * 0.95, smoothstep(1.5, 0.7, vW.y) * 0.8);                 // rocky shore
        vec2 uv = (vW.xz - uOrig.xy) / uOrig.z;
        if (uv.x > 0.0 && uv.y > 0.0 && uv.x < 1.0 && uv.y < 1.0) {
          vec4 ur = texture2D(uUrban, uv); vec4 un = texelFetch(uUrban, ivec2(uv * uOrig.w), 0);
          float ub = (un.g * 255.0 * 256.0 + un.b * 255.0) / 100.0;
          vec3 lot = mix(Ls(vec3(0.78, 0.72, 0.62)), Ls(vec3(0.78, 0.77, 0.74)), uPave);
          col = mix(col, lot, ur.r * smoothstep(ub, ub + 0.8, uTime) * 0.9);
          vec4 g = texture2D(uGround, uv); vec4 gn = texelFetch(uGround, ivec2(uv * uOrig.w), 0);
          float birth = (gn.g * 255.0 * 256.0 + gn.b * 255.0) / 100.0;
          float road = g.r * smoothstep(birth, birth + 0.6, uTime);
          vec3 dirt = Ls(vec3(0.72, 0.64, 0.50)), asph = mix(Ls(vec3(0.30, 0.31, 0.33)), Ls(vec3(0.36, 0.37, 0.39)), nf);
          col = mix(col, mix(dirt, asph, uPave), road * 0.95);
        }
        vec2 pv = (vW.xz - uPorig.xy) / uPorig.z;
        if (pv.x > 0.0 && pv.y > 0.0 && pv.x < 1.0 && pv.y < 1.0) {
          vec2 pc = pv * uPorig.w - 0.5, pf = fract(pc); ivec2 p0 = ivec2(floor(pc));
          float on[4];
          for (int k = 0; k < 4; k++) {
            vec2 pk = texelFetch(uPark, p0 + ivec2(k & 1, k >> 1), 0).rg;
            float py = max((pk.r * 255.0 + pk.g * 255.0 * 256.0) / 100.0 + 1800.0, 1870.0);
            on[k] = pk.r + pk.g > 0.0 ? smoothstep(py, py + 1.5, uYear) : 0.0;
          }
          float pm = smoothstep(0.35, 0.65, mix(mix(on[0], on[1], pf.x), mix(on[2], on[3], pf.x), pf.y));
          col = mix(col, Ls(vec3(0.36, 0.52, 0.24)) * mix(0.97, 1.03, nz), pm * 0.95);
        }
        diffuseColor.rgb = col;
      }`);
  };
  const terrain = new THREE.Mesh(tGeo, tMat); terrain.receiveShadow = true; scene.add(terrain);
  // the far land and sea beyond the terrain square: the mountains carry on (edge relief), the sea stays sea
  const farG = new THREE.PlaneGeometry(90000, 90000, 300, 300).rotateX(-Math.PI / 2), fp = farG.attributes.position;
  for (let i = 0; i < fp.count; i++) {
    const x = fp.getX(i) + CX, z = fp.getZ(i) + CZ, inside = Math.abs(x - CX) < TWD / 2 - 200 && Math.abs(z - CZ) < TWD / 2 - 200;
    fp.setY(i, inside ? -30 : seabed(x, z));
  }
  farG.computeVertexNormals();
  const farGround = new THREE.Mesh(farG, tMat); farGround.position.set(CX, 0, CZ); farGround.receiveShadow = true; scene.add(farGround);

  // ---------- the land won from the sea: each platform rises out of the water between its dates ----------
  for (const r of RC) {
    const sh = new THREE.Shape(r.ring.map(([x, z]) => new THREE.Vector2(x, -z)));
    const D = r.top + 9, geo = new THREE.ExtrudeGeometry(sh, { depth: D, bevelEnabled: false }); geo.rotateX(-Math.PI / 2);
    const m = new THREE.Mesh(geo, tMat); m.receiveShadow = true; m.castShadow = true;
    const g = new THREE.Group(); g.position.y = -9; g.add(m); scene.add(g);
    grow(g, tOf(r.from), tOf(r.to), "y");
  }

  // ---------- the sea ----------
  const wGeo = new THREE.PlaneGeometry(TWD, TWD, 350, 350); wGeo.rotateX(-Math.PI / 2); wGeo.translate(CX, 0, CZ);
  const wp = wGeo.attributes.position, wDepth = new Float32Array(wp.count);
  for (let i = 0; i < wp.count; i++) wDepth[i] = -seabed(wp.getX(i), wp.getZ(i));
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
        vec3 wc = mix(Lw(vec3(0.22, 0.70, 0.74)), Lw(vec3(0.07, 0.36, 0.58)), smoothstep(0.4, 9.0, vDepth));
        float foam = (1.0 - smoothstep(0.05, 0.45, vDepth)) * (0.55 + 0.45 * wn(vWp.xz * 0.25 + uTime * 0.5));
        wc = mix(wc, Lw(vec3(0.92, 0.94, 0.90)), foam * 0.7);
        diffuseColor.rgb = wc;`)
      .replace("#include <normal_fragment_maps>", /* glsl */ `#include <normal_fragment_maps>
        vec2 q = vWp.xz * 0.05 + vec2(0.0, uTime * 0.4);
        float e = 0.6, h0 = wn(q + uTime * 0.15) + 0.5 * wn(q * 2.3 - uTime * 0.2);
        float hx = wn(q + vec2(e, 0.0) + uTime * 0.15) + 0.5 * wn((q + vec2(e, 0.0)) * 2.3 - uTime * 0.2);
        float hz = wn(q + vec2(0.0, e) + uTime * 0.15) + 0.5 * wn((q + vec2(0.0, e)) * 2.3 - uTime * 0.2);
        normal = normalize(normal + (mat3(viewMatrix) * vec3(-(hx - h0), 0.0, -(hz - h0))) * 0.12);`)
      .replace("#include <lights_fragment_end>", "#include <lights_fragment_end>\n reflectedLight.directSpecular *= 0.12; reflectedLight.indirectSpecular *= 0.3;");
  };
  scene.add(new THREE.Mesh(wGeo, wMat));
  const fwGeo = new THREE.PlaneGeometry(90000, 90000, 1, 1).rotateX(-Math.PI / 2); fwGeo.translate(CX, -0.35, CZ);
  fwGeo.setAttribute("aDepth", new THREE.BufferAttribute(new Float32Array(fwGeo.attributes.position.count).fill(20), 1));
  scene.add(new THREE.Mesh(fwGeo, wMat));

  // ---------- landmarks: the Genoese fortress of 1215 (four towers and ramparts), the core of the palace ----------
  {
    const g = new THREE.Group(); g.position.set(palX, heightAt(palX, palZ) - 0.6, palZ); g.rotation.y = 0.35; scene.add(g);
    const STONE = "#cdbfa4", t0 = 1.5;
    grow(box(70, 9, 46, STONE, 0, 0, 0, g), t0, t0 + 3, "y");
    for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
      const tw = box(10, 17, 10, "#c4b597", sx * 34, 0, sz * 22, g);
      for (let c = 0; c < 4; c++) box(2.4, 2, 2.4, "#c4b597", (c % 2 ? 1 : -1) * 3.6, 17, (c < 2 ? 1 : -1) * 3.6, tw);
      grow(tw, t0 + 2 + (sx + 1) * 0.6 + (sz + 1) * 0.3, t0 + 6 + (sx + 1) * 0.5, "y");
    }
  }
  // ---------- life: boats in the port and offshore, cars on the main roads ----------
  const boats = [], hullM = STD({ color: "#f4f1ea" }), sailM = STD({ color: "#ffffff", side: THREE.DoubleSide });
  const rb = mulberry32(1297);
  for (let k = 0; k < 60; k++) {
    let x = 0, z = 0; for (let tries = 0; tries < 60; tries++) { x = -1800 + rb() * 4200; z = -1600 + rb() * 3800; if (shoreDist(x, z) < -60 && rcAt(x, z) < 0) break; }
    const g = new THREE.Group(), yacht = k < 22, L = yacht ? 22 + rb() * 40 : 9 + rb() * 6;
    const hull = new THREE.Mesh(new THREE.BoxGeometry(L, yacht ? 4 : 1.6, yacht ? L * 0.2 : 3).translate(0, yacht ? 1.4 : 0.6, 0), hullM); hull.castShadow = true; g.add(hull);
    if (yacht) { const b2 = new THREE.Mesh(new THREE.BoxGeometry(L * 0.5, 3.5, L * 0.16).translate(-L * 0.05, 4.6, 0), hullM); b2.castShadow = true; g.add(b2); }
    else { const s = new THREE.Mesh(new THREE.ConeGeometry(L * 0.32, L * 1.05, 3).translate(0, L * 0.6 + 1, 0), sailM); s.scale.z = 0.12; s.castShadow = true; g.add(s); }
    scene.add(g);
    boats.push({ g, x0: x, z0: z, v: (rb() < 0.5 ? -1 : 1) * (yacht ? 3 : 2 + rb() * 3), born: yacht ? tOf(1955 + rb() * 60) : tOf(1300 + rb() * 600), ph: rb() * 6 });
  }
  const mains = segs.filter((sg) => sg.w >= 6.5 && Math.hypot(sg.bx - sg.ax, sg.bz - sg.az) > 18);
  const NC = Math.min(1600, mains.length * 2), cars = new THREE.InstancedMesh(new THREE.BoxGeometry(4.2, 1.6, 2).translate(0, 0.8, 0), STD({ roughness: 0.4 }), NC);
  cars.frustumCulled = false; scene.add(cars);
  const carP = [], CC = ["#f2f2f0", "#c8ccd2", "#222428", "#b8302a", "#f2c230", "#3a5f9a", "#f2f2f0"];
  for (let k = 0; k < NC; k++) { const sg = mains[Math.floor(hash2(k, 41) * mains.length)]; carP.push({ sg, u: hash2(k, 42), dir: hash2(k, 43) < 0.5 ? 1 : -1, sp: 8 + hash2(k, 44) * 6, on: hash2(k, 45) }); cars.setColorAt(k, new THREE.Color(CC[k % CC.length])); }
  const _cm = new THREE.Matrix4(), _cq = new THREE.Quaternion(), _cs = V(1, 1, 1), _cp = V(), _up = V(0, 1, 0);
  function updateLife(t) {
    for (const b of boats) {
      const on = sm(ramp(t, b.born, b.born + 1)); b.g.visible = on > 0.01; if (!b.g.visible) continue;
      let x = b.x0 + b.v * t * 0.6; x = ((x + 1800) % 4200 + 4200) % 4200 - 1800;
      if (shoreDist(x, b.z0) > -40) { b.g.visible = false; continue; }
      b.g.position.set(x, 0.2 + Math.sin(t * 1.1 + b.ph) * 0.15, b.z0); b.g.rotation.set(0, b.v > 0 ? 0 : Math.PI, Math.sin(t * 0.9 + b.ph) * 0.03); b.g.scale.setScalar(on);
    }
    const share = sm(ramp(yearF(t), 1910, 1990)); let n = 0;
    for (const c of carP) {
      if (c.on > share || t < c.sg.ba + 3) continue;
      const L = Math.hypot(c.sg.bx - c.sg.ax, c.sg.bz - c.sg.az), f = ((c.u + c.dir * t * c.sp / L) % 1 + 1) % 1;
      const ux = (c.sg.bx - c.sg.ax) / L, uz = (c.sg.bz - c.sg.az) / L, lane = c.sg.w * 0.22 * c.dir;
      const px = c.sg.ax + (c.sg.bx - c.sg.ax) * f - uz * lane, pz = c.sg.az + (c.sg.bz - c.sg.az) * f + ux * lane;
      _cp.set(px, heightAt(px, pz) - 0.3, pz);
      _cq.setFromAxisAngle(_up, -Math.atan2(uz, ux) + (c.dir < 0 ? Math.PI : 0));
      cars.setMatrixAt(n++, _cm.compose(_cp, _cq, _cs));
    }
    cars.count = n; cars.instanceMatrix.needsUpdate = true; if (cars.instanceColor) cars.instanceColor.needsUpdate = true;
  }

  // ---------- dust: the fortress, the casino, Fontvieille's seawall ----------
  const dust = [];
  for (const [t0, x, z] of [[2, palX, palZ], [tOf(1863.25), casX, casZ], [tOf(1966.3), stX, stZ + 200], [tOf(2017.2), ...LL(43.7420, 7.4325)]])
    for (let k = 0; k < 6; k++) dust.push({ x: x + (hash2(k, 1) - 0.5) * 60, y: 6, z: z + (hash2(k, 2) - 0.5) * 50, t0: t0 + k * 0.3, t1: t0 + 3.5 + k * 0.2, ph: hash2(k, 3), rise: 40, spread: 20, size0: 3, speed: 0.3, wind: [20, -10] });
  const updDust = puffs(scene, dust, { color: "#d8ccb4", opacity: 0.3, perCol: 10 });

  // ---------- camera: one flight, mostly from over the sea (south-east) looking at the mountains ----------
  const OD = TW["Odeon Tower"] || { x: 542, z: -1158 }, [mtX, mtZ] = LL(43.7420, 7.4325), [lvX, lvZ] = LL(43.7470, 7.4350);
  const [mcX, mcZ] = LL(43.7405, 7.4255), [fvX, fvZ] = LL(43.7265, 7.4165), [muX, muZ] = TW["Oceanographic Museum"] ? [TW["Oceanographic Museum"].x, TW["Oceanographic Museum"].z] : LL(43.7307, 7.4253);
  const cam = cameraPath([
    [0, [rockX + 700, 380, rockZ + 760], [rockX - 160, 20, rockZ - 40]],
    [12, [palX + 330, 170, palZ + 330], [palX, 30, palZ]],
    [26, [palX + 420, 230, palZ + 420], [palX + 40, 30, palZ - 20]],
    [42, [rockX - 520, 320, rockZ + 640], [rockX + 40, 30, rockZ - 40]],
    [62, [rockX - 300, 420, rockZ + 900], [rockX, 30, rockZ - 160]],
    [84, [rockX + 640, 400, rockZ + 720], [rockX - 80, 30, rockZ - 140]],
    [104, [porX + 900, 700, porZ + 1500], [porX - 100, 40, porZ - 200]],
    [124, [mcX + 1700, 1300, mcZ + 2200], [mcX - 200, 80, mcZ - 200]],
    [140, [casX + 560, 300, casZ + 520], [casX, 30, casZ]],
    [152, [casX + 380, 210, casZ + 380], [casX - 30, 30, casZ - 20]],
    [170, [mcX + 900, 560, mcZ + 900], [mcX - 80, 50, mcZ - 120]],
    [196, [muX + 460, 260, muZ + 420], [muX - 120, 40, muZ - 40]],
    [214, [muX + 320, 170, muZ + 340], [muX, 50, muZ]],
    [232, [porX + 560, 460, porZ + 900], [porX, 10, porZ - 60]],
    [250, [porX + 1500, 1100, porZ + 1800], [porX + 100, 40, porZ - 300]],
    [274, [lvX + 900, 600, lvZ + 1000], [lvX - 100, 30, lvZ - 100]],
    [294, [lvX + 620, 420, lvZ + 700], [lvX - 60, 20, lvZ]],
    [312, [fvX + 700, 480, fvZ + 860], [fvX - 60, 20, fvZ - 60]],
    [330, [fvX + 500, 360, fvZ + 640], [fvX - 40, 20, fvZ - 40]],
    [348, [stX + 420, 300, stZ + 500], [stX, 15, stZ]],
    [366, [mcX + 1500, 1000, mcZ + 1400], [mcX - 100, 60, mcZ - 400]],
    [386, [OD.x + 700, 420, OD.z + 900], [OD.x - 100, 40, OD.z + 300]],
    [412, [OD.x + 620, 360, OD.z + 640], [OD.x, 80, OD.z]],
    [428, [OD.x + 420, 260, OD.z + 460], [OD.x, 100, OD.z]],
    [444, [mtX + 560, 330, mtZ + 600], [mtX - 30, 15, mtZ - 20]],
    [462, [mtX + 1200, 800, mtZ + 1300], [mtX - 200, 30, mtZ - 200]],
    [480, [CX + 2400, 1900, CZ + 2800], [CX - 200, 40, CZ - 300]],
    [MDUR, [CX + 3100, 2600, CZ + 3500], [CX - 300, 40, CZ - 300]],
  ]);
  const drawHud = hudDriver(hud, { ERAS, FLAGS, TITLE, LANDMARKS, CAPTIONS, CARDS, yearAt, popAt, DUR: MDUR });

  const ready = Promise.resolve();
  const introPose = { pos: V(CX + 2900, 2200, CZ + 3300), tgt: V(CX - 200, 40, CZ - 300) };
  function renderAt(time) {
    time = clamp(time, 0, DUR);
    // intro: Monaco today, then a fast rewind to 1215, then the flight starts
    const intro = time < INTRO;
    const mainT = intro ? (time < 2.5 ? 470 : time < 8 ? 470 * (1 - sm(sm(ramp(time, 2.5, 8)))) : 0) : time - INTRO;
    const t = clamp(mainT, 0, MDUR);
    U.uTime.value = t;
    UT.uPave.value = sm(ramp(yearF(t), 1900, 1955)); UT.uYear.value = yearF(t);
    updateLM(t); updDust(t); updateLife(t);
    let { pos, tgt } = cam(t);
    if (intro) { const k = sm(ramp(time, 5.5, 9)); pos = introPose.pos.clone().lerp(pos, k); tgt = introPose.tgt.clone().lerp(tgt, k); }
    const dist = st.frame(pos, tgt), haze = sm(clamp((dist - 1400) / 2600)); st.scene.fog.near *= lerp(1.3, 0.5, haze); st.scene.fog.far *= lerp(1.4, 0.4, haze);
    const dusk = intro ? 0 : sm(ramp(t, 470, 495));
    st.sun.color.set("#fff1d8").lerp(new THREE.Color("#ffc890"), dusk * 0.7); st.sun.intensity = 3.3 - 0.4 * dusk; st.hemi.intensity = 1.2 - 0.1 * dusk;
    drawHud(t);
    if (intro) {
      hud.black.style.opacity = 1 - clamp(time / 1.2); hud.ui.style.opacity = clamp((time - 0.4) / 0.8);
      for (const el of [hud.title, hud.lm, hud.cap, hud.card]) el.style.opacity = 0;
    } else {
      hud.black.style.opacity = clamp((t - (MDUR - 1.8)) / 1.6); hud.ui.style.opacity = 1 - clamp((t - (MDUR - 2.4)) / 1.2);
    }
    st.render();
  }
  return { ready, renderAt, DUR, stats: { houses: wallR.length + prismR.length, towers: prismG.length, roofs: hipR.length, trees: crownR.length, roads: segs.length } };
}
