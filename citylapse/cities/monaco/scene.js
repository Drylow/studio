import * as THREE from "three";
import {
  clamp, lerp, ramp, sm, V, mulberry32, hash2, vnoise, fbm, pl, inv, M4, NEVER, U, STD, growMesh, unitBox, hipRoof, facet,
  createStage, rasterGround, growPrisms, GROUND_GLSL, landmarks, cameraPath, hudDriver, puffs, fmtYear, fmtPop,
} from "./engine.js";
import { storyFx } from "./fx.js";
import { DATA } from "./data.js";

// "MONACO – 3D TIMELAPSE – 1215 to 2026". SPEC.md has the beats, FACTS.md the sources of every caption.
// Every building is a real footprint (OpenStreetMap via Overture Maps, tools/osm_data_monaco.py) on the real relief
// (Copernicus GLO-30). Years: real years for the towers and landmarks, documented development of each quarter for
// the rest (an approximate reconstruction). Fontvieille, Larvotto and Mareterra rise out of the sea on their dates.
// World metres, x east, z south, origin 43.7375 N 7.4235 E.

export const W = 1920, H = 1080, SS = 1.5, INTRO = 9;

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

// ---------------- the story: dated events (title + one line, FACTS.md has the sources) ----------------
// Each event gets a slot of about 11 s: the camera flies to its focus, the year slows down while the title shows,
// and its effect plays. The year → time mapping is built from the events, so the titles never crowd each other.
const SPOT = {
  rock: LL(43.7308, 7.4235), palace: LL(43.7314, 7.4200), condamine: LL(43.7352, 7.4195), port: LL(43.7355, 7.4245),
  casino: LL(43.7394, 7.4276), mc: LL(43.7405, 7.4262), museum: LL(43.7307, 7.4253), cathedral: LL(43.7303, 7.4232),
  fv: LL(43.7268, 7.4165), stadium: LL(43.7276, 7.4156), lv: LL(43.7470, 7.4345), mt: LL(43.7420, 7.4322),
  odeon: LL(43.7465, 7.4330), forum: LL(43.7432, 7.4312), fort: LL(43.7322, 7.4270), center: LL(43.7372, 7.4245),
};
// view: [distance, height, azimuth°] of the camera from the focus (azimuth 0 = from the south, 90 = from the east)
const EVENTS = [
  { y: 1215.44, title: "THE ROCK", line: "10 June 1215: Genoese led by Fulco del Cassello begin a fortress on the Rock.", at: "palace", view: [520, 260, 35] },
  { y: 1297.02, title: "THE MONK AT THE GATE", line: "8 January 1297: François Grimaldi, reportedly disguised as a monk, takes the fortress.", at: "palace", view: [380, 170, 20] },
  { y: 1346.5, title: "MENTON AND ROQUEBRUNE", line: "The Grimaldis acquire Menton in 1346 and Roquebrune in 1355.", at: "rock", view: [900, 520, 40] },
  { y: 1506.5, title: "THE PALACE GROWS", line: "1506-07: a wing of state apartments is added to the palace.", at: "palace", view: [420, 200, 340] },
  { y: 1524.5, title: "UNDER SPAIN'S WING", line: "1524: Monaco places itself under the protection of Spain.", at: "rock", view: [700, 380, 15] },
  { y: 1633.5, title: "THE FIRST PRINCE", line: "1633: Spain recognises Honoré II as Prince of Monaco.", at: "palace", view: [460, 220, 50] },
  { y: 1641.7, title: "FRANCE TAKES OVER", line: "14 September 1641: the Treaty of Péronne makes Monaco a French protectorate.", at: "rock", view: [760, 420, 330] },
  { y: 1793.1, title: "THE REVOLUTION", line: "1793: revolutionary France annexes Monaco; the palace is looted.", at: "palace", view: [420, 210, 30], fx: "revolution" },
  { y: 1814.4, title: "THE PRINCE RETURNS", line: "1814: the Treaty of Paris restores the principality.", at: "rock", view: [640, 330, 10] },
  { y: 1815.9, title: "UNDER SARDINIA", line: "20 November 1815: Monaco becomes a protectorate of the Kingdom of Sardinia.", at: "condamine", view: [800, 420, 25] },
  { y: 1848.2, title: "MENTON BREAKS AWAY", line: "21 March 1848: Menton and Roquebrune declare themselves free cities.", at: "center", view: [1500, 900, 60] },
  { y: 1856.95, title: "THE FIRST CASINO", line: "14 December 1856: a first casino opens at Villa Bellevue, in La Condamine.", at: "condamine", view: [520, 260, 30] },
  { y: 1861.09, title: "SOLD TO FRANCE", line: "2 February 1861: Menton and Roquebrune are ceded to France for 4 million francs.", at: "center", view: [2200, 1500, 45] },
  { y: 1861.3, title: "WHAT IS LEFT", line: "Monaco keeps less than a tenth of its land, and about 1,200 people.", at: "rock", view: [1100, 620, 20] },
  { y: 1863.5, title: "THE SPÉLUGUES", line: "1863: the casino opens on the bare plateau of the Spélugues.", at: "casino", view: [520, 260, 40], fx: "build" },
  { y: 1864.5, title: "HÔTEL DE PARIS", line: "1864: the Hôtel de Paris opens beside the casino.", at: "casino", view: [380, 190, 20] },
  { y: 1866.42, title: "MONTE-CARLO", line: "1 June 1866: the new quarter on the Spélugues is named Monte-Carlo.", at: "mc", view: [720, 380, 50] },
  { y: 1868.5, title: "THE RAILWAY ARRIVES", line: "1868: the Nice-Ventimiglia line reaches Monaco.", at: "condamine", view: [700, 360, 70], fx: "train" },
  { y: 1879.07, title: "THE OPERA", line: "25 January 1879: Charles Garnier's opera hall opens, built in about eight months.", at: "casino", view: [420, 210, 60] },
  { y: 1899.3, title: "A MUSEUM ON THE CLIFF", line: "1899: Prince Albert I lays the first stone of the Oceanographic Museum.", at: "museum", view: [460, 200, 15], fx: "build" },
  { y: 1902.2, title: "THE PORT", line: "1902: work starts on the jetties of Port Hercule.", at: "port", view: [700, 380, 40] },
  { y: 1903.8, title: "THE CATHEDRAL", line: "1903: Saint Nicholas Cathedral is finished in white La Turbie stone.", at: "cathedral", view: [380, 190, 330] },
  { y: 1910.24, title: "THE MUSEUM OPENS", line: "29 March 1910: the Oceanographic Museum opens on the cliff.", at: "museum", view: [400, 160, 20] },
  { y: 1911.01, title: "A CONSTITUTION", line: "5 January 1911: Monaco's first constitution, after the revolution of 1910.", at: "palace", view: [500, 240, 40], fx: "crowd" },
  { y: 1918.6, title: "THE WAR YEARS", line: "1918: Monaco counts 15,960 residents, down from 19,121 in 1908.", at: "center", view: [1300, 800, 30] },
  { y: 1926.5, title: "A HARBOUR OF STONE", line: "1926: the jetties of Port Hercule are finished.", at: "port", view: [800, 460, 55] },
  { y: 1929.28, title: "THE FIRST GRAND PRIX", line: "14 April 1929: William Grover-Williams wins in a Bugatti, 100 laps of the streets.", at: "port", view: [520, 260, 60], fx: "gp1929" },
  { y: 1942.86, title: "OCCUPIED", line: "11 November 1942: the Italian army occupies Monaco; German troops follow in 1943.", at: "condamine", view: [600, 320, 20], fx: "occupation" },
  { y: 1944.55, title: "FORT ANTOINE", line: "July 1944: Allied bombing destroys Fort Antoine.", at: "fort", view: [520, 280, 40], fx: "bombing" },
  { y: 1944.67, title: "LIBERATED", line: "3 September 1944: Monaco is liberated.", at: "condamine", view: [520, 260, 30], fx: "liberation" },
  { y: 1949.35, title: "RAINIER III", line: "9 May 1949: Rainier III becomes Prince of Monaco.", at: "palace", view: [440, 210, 20] },
  { y: 1954.6, title: "LAND FROM THE SEA", line: "From 1954 to 1961, new land is won from the sea at Larvotto and Le Portier.", at: "lv", view: [800, 460, 50] },
  { y: 1956.3, title: "THE WEDDING", line: "April 1956: Prince Rainier III marries the American actress Grace Kelly.", at: "port", view: [900, 380, 35], fx: "wedding" },
  { y: 1962.96, title: "WOMEN VOTE", line: "1962: the new constitution gives women the vote and ends the death penalty.", at: "center", view: [1100, 680, 40] },
  { y: 1966.3, title: "FONTVIEILLE", line: "About 1966-1973: some 22 hectares are won from the sea at Fontvieille.", at: "fv", view: [900, 520, 20], fx: "reclaim" },
  { y: 1969.5, title: "THE FIRST TOWER", line: "1969: Le Millefiori, 111 m, rises over Monte-Carlo.", at: "mc", view: [720, 330, 60] },
  { y: 1980.5, title: "THE CITY GOES UP", line: "1980-1982: L'Annonciade and Parc Saint Roman pass 100 m.", at: "odeon", view: [820, 420, 70] },
  { y: 1985.07, title: "STADE LOUIS II", line: "25 January 1985: the new stadium opens on reclaimed land in Fontvieille.", at: "stadium", view: [520, 260, 10], fx: "stadium" },
  { y: 1993.4, title: "A SEAT AT THE UN", line: "28 May 1993: Monaco joins the United Nations.", at: "palace", view: [600, 300, 30] },
  { y: 2000.55, title: "GRIMALDI FORUM", line: "20 July 2000: the Grimaldi Forum opens on the Larvotto seafront.", at: "forum", view: [480, 230, 60] },
  { y: 2002.4, title: "THE FLOATING DIKE", line: "About 2002: a new outer dike closes the bay of Port Hercule.", at: "port", view: [900, 480, 50] },
  { y: 2005.26, title: "ALBERT II", line: "6 April 2005: Albert II succeeds his father.", at: "palace", view: [460, 220, 25] },
  { y: 2015.3, title: "THE ODEON TOWER", line: "2015: the Odeon Tower, 170 m, becomes Monaco's tallest building.", at: "odeon", view: [560, 300, 50] },
  { y: 2017.5, title: "BUILDING IN THE SEA", line: "About 2017: work begins on a 6-hectare extension at Le Portier.", at: "mt", view: [620, 320, 40], fx: "build" },
  { y: 2019.55, title: "18 CAISSONS", line: "18 July 2019: the last of the 18 caissons is set in place.", at: "mt", view: [460, 230, 70] },
  { y: 2024.93, title: "MARETERRA", line: "4 December 2024: the new district of Mareterra opens.", at: "mt", view: [520, 260, 40], fx: "fireworks" },
  { y: 2025.99, title: "38,857 PEOPLE", line: "End of 2025: 38,857 residents, from 144 nationalities, on about 2 km².", at: "center", view: [2600, 1900, 40] },
];
const SLOT = 10.5, TAIL = 34;
const YK = []; {
  let t = 0, prev = 1215.4;
  YK.push([0, 1215.4]);
  for (const e of EVENTS) {
    const gap = e.y - prev;
    t += Math.max(3, Math.min(9, gap * (prev < 1800 ? 0.03 : 0.25)));   // the quiet centuries go fast
    e.t = t; YK.push([t, e.y]);
    t += SLOT - 3; YK.push([t, e.y + Math.min(0.2, gap * 0.02)]);   // the year almost stops while the title shows
    prev = e.y;
  }
  YK.push([t + 6, 2026]);
}
export const MDUR = Math.ceil(YK[YK.length - 1][0] + TAIL), DUR = MDUR + INTRO;
YK.push([MDUR, 2026]);
const yearF = (t) => pl(YK, t);
const yearAt = (t) => Math.floor(yearF(t));
const tOf = (y) => (y <= YK[0][1] ? -1 : inv(yearF, y, 0, MDUR));

const ERAS = [
  { y: 1215, name: "Republic of Genoa", flag: "genoa" },
  { y: 1297, name: "Lordship of Monaco", flag: "monaco" },
  { y: 1524.5, name: "Monaco, under Spanish protection", flag: "monaco" },
  { y: 1633.5, name: "Principality of Monaco", flag: "monaco" },
  { y: 1641.75, name: "Monaco, under French protection", flag: "monaco" },
  { y: 1793.1, name: "French Republic", flag: "france" },
  { y: 1814.45, name: "Principality of Monaco", flag: "monaco" },
  { y: 1815.9, name: "Monaco, under Sardinian protection", flag: "monaco" },
  { y: 1861.1, name: "Principality of Monaco", flag: "monaco" },
].map((e) => ({ ...e, t: e.y <= 1215.4 ? 0 : tOf(e.y) }));
const FLAGS = {
  genoa: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#fff"/><rect x="58" width="24" height="84" fill="#c8102e"/><rect y="30" width="140" height="24" fill="#c8102e"/></svg>`,
  monaco: `<svg viewBox="0 0 140 84"><rect width="140" height="84" fill="#fff"/><rect width="140" height="42" fill="#ce1126"/></svg>`,
  france: `<svg viewBox="0 0 140 84"><rect width="47" height="84" fill="#002395"/><rect x="47" width="46" height="84" fill="#fff"/><rect x="93" width="47" height="84" fill="#ed2939"/></svg>`,
};
const TITLE = [1.2, 8];

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

  // ---------- the events' effects ----------
  const fx = storyFx(scene, heightAt);
  const P = (k) => SPOT[k];
  const square = [palX + 90, palZ + 10];                       // Place du Palais, east of the palace
  const CIRCUIT = [[43.7348, 7.4205], [43.7364, 7.4230], [43.7380, 7.4255], [43.7392, 7.4266], [43.7395, 7.4278], [43.7405, 7.4290],
    [43.7412, 7.4296], [43.7400, 7.4306], [43.7385, 7.4300], [43.7372, 7.4285], [43.7362, 7.4260], [43.7355, 7.4245], [43.7344, 7.4222],
    [43.7343, 7.4210], [43.7348, 7.4205]].map(([a, b]) => LL(a, b));
  for (const e of EVENTS) {
    const t = e.t, [x, z] = P(e.at);
    fx.cue(t + 0.3, "title", 1.5, 0.5);
    switch (e.fx) {
      case "revolution": fx.crowd({ x: square[0], z: square[1], r: 45, n: 500, t0: t, t1: t + 8 }); fx.smoke({ x: palX, z: palZ, t0: t + 2, t1: t + 7, sound: false }); fx.cue(t + 1, "drums", 6, 0.7); break;
      case "build": fx.dust({ x, z, t0: t, t1: t + 6 }); fx.cue(t, "construction", 6, 0.8); break;
      case "train": fx.cue(t + 1, "train", 5, 0.8); break;
      case "crowd": fx.crowd({ x: square[0], z: square[1], r: 50, n: 650, t0: t, t1: t + 8 }); break;
      case "gp1929": fx.race({ path: CIRCUIT, t0: t - 1, t1: t + SLOT, n: 14, speed: 48, colors: ["#2b55a8", "#2b55a8", "#c8102e", "#1f6b3a", "#2b55a8", "#e6e2d6"] });
        fx.crowd({ x: x - 40, z: z + 40, r: 70, sx: 2.2, n: 900, t0: t - 1, t1: t + SLOT, gain: 0.7 }); fx.cue(t + SLOT - 3, "cheer", 3, 0.9); break;
      case "occupation": { const [ax, az] = LL(43.7330, 7.4110); fx.army({ path: [[ax, az], [x - 200, z + 60], [x, z]], t0: t - 1, t1: t + SLOT, n: 300, color: "#5a5b44", flag: "#2f7d32" }); break; }
      case "bombing": { const [fx0, fz0] = P("fort"); fx.planes({ from: [fx0 + 400, fz0 + 2600], to: [fx0 - 600, fz0 - 2600], t0: t - 1, t1: t + 7, n: 9, alt: 320 });
        for (let k = 0; k < 4; k++) fx.smoke({ x: fx0 + (k - 1.5) * 30, z: fz0 + (k % 2) * 25, t0: t + 2 + k * 0.5, t1: t + 9, big: k === 0, gain: 0.8 });
        fx.fire({ x: fx0, z: fz0, r: 35, t0: t + 2.4, t1: t + 9 }); break; }
      case "liberation": fx.crowd({ x, z, r: 60, n: 800, t0: t, t1: t + 8 }); fx.cue(t + 0.5, "bells", 7, 0.8); fx.cue(t + 2, "cheer", 5, 0.9); break;
      case "wedding": fx.sky({ t0: t + 3, t1: t + SLOT + 1.5, kind: "night", fade: 1.6 }); fx.crowd({ x: x - 60, z: z + 30, r: 80, sx: 2, n: 900, t0: t, t1: t + SLOT });
        fx.fireworks({ x: x + 150, z: z + 350, t0: t + 4.2, t1: t + SLOT + 0.5, w: 600, d: 250 }); fx.cue(t, "bells", 4, 0.7); break;
      case "reclaim": fx.dust({ x, z: z + 150, t0: t, t1: t + 9 }); fx.dust({ x: x + 200, z: z + 250, t0: t + 1, t1: t + 9 }); fx.cue(t, "construction", 9, 0.9); fx.cue(t, "waves", 9, 0.5); break;
      case "stadium": fx.cue(t + 2, "cheer", 4, 0.8); break;
      case "fireworks": fx.sky({ t0: t + 2, t1: t + SLOT + 1.5, kind: "night", fade: 1.6 }); fx.fireworks({ x: x + 200, z: z + 400, t0: t + 3.5, t1: t + SLOT + 0.5, w: 700, d: 300 }); break;
    }
  }
  // construction dust where the big works start
  const dust = [];
  for (const [t0, x, z] of [[2, palX, palZ], [tOf(1863.25), casX, casZ]])
    for (let k = 0; k < 6; k++) dust.push({ x: x + (hash2(k, 1) - 0.5) * 60, y: 6, z: z + (hash2(k, 2) - 0.5) * 50, t0: t0 + k * 0.3, t1: t0 + 3.5 + k * 0.2, ph: hash2(k, 3), rise: 40, spread: 20, size0: 3, speed: 0.3, wind: [20, -10] });
  const updDust = puffs(scene, dust, { color: "#d8ccb4", opacity: 0.3, perCol: 10 });

  // ---------- camera: it flies to each event's focus and holds there while the title shows ----------
  const view = (e) => { const [x, z] = P(e.at), [d, h, az] = e.view, a = (az * Math.PI) / 180, gy = heightAt(x, z);
    return [[x + Math.sin(a) * d, gy + h, z + Math.cos(a) * d], [x, gy + 10, z]]; };
  const KEYS = [];
  for (const e of EVENTS) { const [p, q] = view(e); KEYS.push([Math.max(0, e.t - 0.5), p, q]); KEYS.push([e.t + SLOT - 3.5, [p[0] * 0.98 + q[0] * 0.02, p[1] * 0.97, p[2] * 0.98 + q[2] * 0.02], q]); }
  KEYS.sort((a, b) => a[0] - b[0]);
  const last = EVENTS[EVENTS.length - 1].t + SLOT;
  KEYS.push([last + 10, [CX + 2400, 1900, CZ + 2800], [CX - 200, 40, CZ - 300]], [MDUR, [CX + 3100, 2600, CZ + 3500], [CX - 300, 40, CZ - 300]]);
  for (let i = 1; i < KEYS.length; i++) if (KEYS[i][0] <= KEYS[i - 1][0] + 0.3) KEYS[i][0] = KEYS[i - 1][0] + 0.3;
  const cam = cameraPath(KEYS);

  // ---------- HUD: state top-left, population top-right, year bottom-left, the event bottom-right ----------
  const env = (t, a, b, f = 0.9) => clamp(Math.min((t - a) / f, (b - t) / f));
  let lastEra = -1;
  for (const el of [hud.lm, hud.cap]) el.style.opacity = 0;
  function drawHud(t) {
    hud.year.textContent = fmtYear(yearAt(t));
    const p = popAt(t); hud.pop.style.opacity = p > 0 ? 1 : 0; hud.popN.textContent = `${fmtPop(p)}`;
    let e = 0; for (let i = 0; i < ERAS.length; i++) if (t >= ERAS[i].t) e = i;
    if (e !== lastEra) { hud.eraName.textContent = ERAS[e].name; hud.flag.innerHTML = FLAGS[ERAS[e].flag]; lastEra = e; }
    hud.era.style.opacity = e === 0 ? 1 : clamp((t - ERAS[e].t) / 0.7);
    hud.title.style.opacity = env(t, TITLE[0], TITLE[1], 1.2);
    const ev = EVENTS.find((x) => t >= x.t + 0.2 && t <= x.t + SLOT - 1);
    hud.ev.style.opacity = ev ? env(t, ev.t + 0.2, ev.t + SLOT - 1, 0.7) : 0;
    if (ev) { hud.evT.textContent = ev.title; hud.evS.textContent = ev.line; }
    hud.card.style.opacity = env(t, MDUR - 26, MDUR - 3, 1.4); hud.cardK.textContent = "1215 – 2026"; hud.cardT.textContent = "MONACO";
  }

  const ready = Promise.resolve();
  const introPose = { pos: V(CX + 2900, 2200, CZ + 3300), tgt: V(CX - 200, 40, CZ - 300) };
  const now = tOf(2025.5);
  function renderAt(time) {
    time = clamp(time, 0, DUR);
    // intro: Monaco today, then a fast rewind to 1215, then the flight starts
    const intro = time < INTRO;
    const mainT = intro ? (time < 2.5 ? now : time < 8 ? now * (1 - sm(sm(ramp(time, 2.5, 8)))) : 0) : time - INTRO;
    const t = clamp(mainT, 0, MDUR);
    U.uTime.value = t;
    UT.uPave.value = sm(ramp(yearF(t), 1900, 1955)); UT.uYear.value = yearF(t);
    updateLM(t); updDust(t); updateLife(t);
    let { pos, tgt } = cam(t);
    if (intro) { const k = sm(ramp(time, 5.5, 9)); pos = introPose.pos.clone().lerp(pos, k); tgt = introPose.tgt.clone().lerp(tgt, k); }
    const dusk = intro ? 0 : sm(ramp(t, MDUR - 30, MDUR - 6));
    st.sun.color.set("#fff1d8").lerp(new THREE.Color("#ffc890"), dusk * 0.7); st.sun.intensity = 3.3 - 0.4 * dusk; st.hemi.intensity = 1.2 - 0.1 * dusk;
    const dist = st.frame(pos, tgt), haze = sm(clamp((dist - 1400) / 2600)); st.scene.fog.near *= lerp(1.3, 0.5, haze); st.scene.fog.far *= lerp(1.4, 0.4, haze);
    const fs = fx.update(intro ? -100 : t, st, { tgt, dist });
    if (fs.shake.lengthSq() > 0) { st.camera.position.add(fs.shake); }
    drawHud(t);
    if (intro) {
      hud.black.style.opacity = 1 - clamp(time / 1.2); hud.ui.style.opacity = clamp((time - 0.4) / 0.8);
      for (const el of [hud.title, hud.ev, hud.card]) el.style.opacity = 0;
    } else {
      hud.black.style.opacity = clamp((t - (MDUR - 1.8)) / 1.6); hud.ui.style.opacity = 1 - clamp((t - (MDUR - 2.4)) / 1.2);
    }
    st.render();
  }
  // sound cues for tools/sfx.mjs, in video seconds (the intro shifts everything by INTRO)
  const sfx = fx.cues.map((c) => ({ ...c, t: c.t + INTRO })).sort((a, b) => a.t - b.t);
  return { ready, renderAt, DUR, sfx, events: EVENTS.map((e) => ({ t: e.t + INTRO, y: e.y, title: e.title })), stats: { houses: wallR.length + prismR.length, towers: prismG.length, roofs: hipR.length, trees: crownR.length, roads: segs.length } };
}
