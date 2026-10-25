import * as THREE from "three";
import {
  clamp, lerp, ramp, sm, V, mulberry32, hash2, fbm, pw, pl, inv, M4, NEVER, U, STD, growMesh, unitBox, hipRoof, facet,
  createStage, rasterGround, growPrisms, GROUND_GLSL, landmarks, cameraPath, hudDriver, puffs,
} from "./engine.js";
import { DATA } from "./data.js";

// "TEL AVIV – 3D TIMELAPSE – 1880 to 2026". See SPEC.md for the beats and the fact-checked captions.
// Unlike the procedural cities, every building here is a real footprint (OpenStreetMap via Overture Maps,
// tools/osm_data.py): its rectangle, its height, and an approximate year (satellite GHSL epochs after 1975,
// documented founding dates of each quarter before, real years for the towers). World metres, x east, z south.

export const W = 1920, H = 1080, SS = 1.5, MDUR = 560, INTRO = 9, DUR = MDUR + INTRO;   // 9 s intro: today, rewound to 1880

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
  [470, 2023.63], [478, 2023.64], [505, 2026], [MDUR, 2026],
];
const yearF = (t) => pl(YK, t);
const yearAt = (t) => Math.floor(yearF(t));
const tOf = (y) => (y <= YK[0][1] ? -1 : inv(yearF, y, 0, MDUR));   // first video time that reaches a year
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
const MORE = [
  [1891.5, ["1891: Jaffa's railway station opens;", "the line to Jerusalem is finished the next year."]],
  [1906.5, ["July 1906: Jaffa families form a society", "to build a new garden suburb on the dunes."]],
  [1909.57, ["28 July 1909: the cornerstone of the Herzliya Hebrew Gymnasium,", "the first Hebrew high school, is laid on Herzl Street."]],
  [1917.88, ["17 November 1917:", "British forces take Tel Aviv."]],
  [1921.35, ["May 1921: riots in Jaffa leave 47 Jews and 48 Arabs dead;", "many Jewish residents move to Tel Aviv."]],
  [1922.8, ["October 1922: the British census", "counts 15,185 residents in Tel Aviv."]],
  [1932.3, ["1932: the Tel Aviv Museum of Art opens", "in Meir Dizengoff's house on Rothschild Boulevard."]],
  [1934.33, ["April 1934: the Levant Fair opens in north Tel Aviv;", "about 600,000 visitors come from 30 countries."]],
  [1938.3, ["1938: Dizengoff Square is inaugurated", "and the Reading Power Station starts up."]],
  [1940.69, ["9 September 1940: Italian aircraft", "bomb Tel Aviv; 137 people are killed."]],
  [1945.5, ["1945: the Habima national theatre", "moves into its new building."]],
  [1956.5, ["1956: Tel Aviv University is founded", "from three institutes in the city."]],
  [1965.82, ["25 October 1965: Tel Aviv Port closes to cargo;", "shipping moves south to Ashdod."]],
  [1966.5, ["1966: the new City Hall is completed", "on Kings of Israel Square."]],
  [1971.5, ["1971: the Tel Aviv Museum of Art moves", "to its new building on Shaul HaMelech Boulevard."]],
  [1977.5, ["1977: the first stores open in Dizengoff Center,", "Israel's first shopping mall."]],
  [1982.5, ["1982: the first section of the Ayalon Highway opens;", "the central section with the railway follows in 1991."]],
  [1991.05, ["January-February 1991: Iraq fires about 42 Scud missiles at Israel,", "aimed mainly at Tel Aviv and Haifa."]],
  [2007.45, ["June 2007: the Azrieli Square Tower is completed,", "154 m and 42 floors."]],
  [2014.5, ["2014: the old Templer colony of Sarona", "reopens after an eight-year restoration."]],
  [2019.37, ["May 2019: Tel Aviv hosts", "the Eurovision Song Contest."]],
  [2025.8, ["2026: ToHA 2 tops out at about 300 m,", "set to become the tallest tower in the city."]],
];
const busy = (a, b) => [...CAPTIONS, ...LANDMARKS].some((c) => a < c.b + 0.6 && b > c.a - 0.6) || (a < TITLE[1] + 0.5);
for (const [y, lines] of MORE) { const a = tOf(y) + 0.3, b = a + 6; if (a > 0 && b < MDUR - 40 && !busy(a, b)) CAPTIONS.push({ a, b, lines }); }
CAPTIONS.sort((p, q) => p.a - q.a);
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
  const st = createStage(canvas, { W, H, SS, fog: "#cfe0ec", skyTop: "#5c9bd6", sunColor: "#fff1d6", sunDir: [-0.5, 0.7, 0.5], hemiSky: "#d6e9fb", hemiGround: "#9c8f6e", hemiI: 1.2, sunI: 3.3, saturation: 0.12, contrast: 0.15, tilt: 0.15, bloom: 0.3 });
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
  const GLASS = ["#b9d0de", "#a9c4d6", "#c6d8e2", "#9fbdd0", "#cfdde6", "#8fb3c8", "#5f86a3", "#3f5d74", "#7fa7a4", "#9ab0bd", "#4d6b80", "#6b8f9e"];
  // the later city mixes concrete greys, sand, ochre, salmon and a little brick with the white plaster
  const ACCENT = ["#cfd3d6", "#b8bcbf", "#a9a59c", "#d9b99b", "#e8c9a0", "#c98f6b", "#b5704f", "#d7a98c", "#c4cfd6", "#e6dba0", "#9aa3a8", "#8e7f6e", "#d2c4b2", "#bfa58a"];
  const ROOFS = ["#a8a49c", "#9b978f", "#b7b2a8", "#8f8b84", "#c2bdb2", "#7d7a74"];
  const BR = DATA.BR, rings = [];
  for (let i = 0; i < BR.length;) { const n = BR[i++], r = []; for (let q = 0; q < n; q++, i += 2) r.push([BR[i] / 10, BR[i + 1] / 10]); rings.push(r); }
  const inRing = (r, px, pz) => { let c = false; for (let a = 0, b = r.length - 1; a < r.length; b = a++) if ((r[a][1] > pz) !== (r[b][1] > pz) && px < ((r[b][0] - r[a][0]) * (pz - r[a][1])) / (r[b][1] - r[a][1]) + r[a][0]) c = !c; return c; };
  const prismR = [], prismB = [], prismG = [];
  const SOLAR = [], solarDark = new THREE.Color("#3a4a5a"), solarTank = new THREE.Color("#e8e8e4");
  const wallR = [], wallB = [], roofR = [], hipR = [], glassR = [], capR = [];
  const cW = new THREE.Color();
  const B = DATA.B;
  const houseAt = new Map(), HCS = 16, [portX, portZ] = LL(32.0975, 34.774), [ahX, ahZ] = LL(32.0633, 34.7714), bBirth = new Float32Array(B.length / 9).fill(NEVER);
  for (let i = 0; i < B.length; i += 9) {
    const x = B[i] / 10, z = B[i + 1] / 10, w = B[i + 2] / 10, d = B[i + 3] / 10, ang = B[i + 4] / 1000, h = Math.max(3.5, B[i + 5] / 10), kind = B[i + 7], ci = B[i + 8];
    if (isWet(x, z)) continue;
    let y = B[i + 6] / 100;
    // the port's hangars and sheds went up in 1936-38 (most still stand, restored): date the low port buildings so
    if (y > 1938 && h < 20 && Math.hypot(x - portX, z - portZ) < 330) y = 1936.3 + hash2(i, 12) * 2.4;
    const r1 = hash2(i, 1), r2 = hash2(i, 2);
    const b = Math.max(0.2, tOf(y) + r1 * 0.6); bBirth[i / 9] = b;
    const y0 = heightAt(x, z) - 0.8, t = [b, NEVER, NEVER, r2];
    const k = Math.floor(x / HCS) * 100003 + Math.floor(z / HCS); const v = houseAt.get(k); if (v === undefined || v > b) houseAt.set(k, b);
    const ring = rings[i / 9].map(([dx, dz]) => [x + dx, z + dz]);
    // Ahuzat Bayit: the 60-odd one- and two-storey houses of 1909-10 were almost all replaced later; put one back on
    // about every other lot, standing until today's building takes its place
    if (y > 1911 && kind !== 2 && Math.hypot(x - ahX, z - ahZ) < 260 && hash2(i, 13) < 0.6) {
      const eb = tOf(1909.35 + hash2(i, 14) * 1.1), hs = 4.5 + r1 * 3, sw = Math.min(w, 13), sd = Math.min(d, 11);
      wallR.push({ m: M4(x, y0, z, ang, sw, 1, sd), c: new THREE.Color(WHITE[Math.floor(hash2(i, 15) * 12)]), t: [eb, b - 0.3, NEVER, r2], h: [0, hs] });
      hipR.push({ m: M4(x, y0 + hs, z, ang, sw + 0.6, Math.min(4, Math.min(sw, sd) * 0.34), sd + 0.6), c: new THREE.Color(ROOF[Math.floor(r1 * 3.99)]), t: [eb + 0.15, b - 0.3, NEVER, r2] });
      if (eb < houseAt.get(k)) houseAt.set(k, eb);
    }
    if (kind === 2 || h >= 45) {                    // towers: glass shafts on their real footprint, a set-back crown
      cW.set(GLASS[(ci * 2 + Math.floor(r1 * 12)) % 12]);
      const top = r2 < 0.55 ? h * (0.84 + r1 * 0.08) : h;
      prismG.push({ ring, y0, c: cW.clone(), rc: cW.clone().multiplyScalar(0.75), t, h: [0, top] });
      if (top < h) glassR.push({ m: M4(x, y0, z, ang, w * 0.78, 1, d * 0.78), c: cW.clone().multiplyScalar(1.05), t: [b + 0.3, NEVER, NEVER, r2], h: [top, h - top] });
      capR.push({ m: M4(x, y0, z, ang, w * 0.86, 1, d * 0.86), c: new THREE.Color("#dfe6ea"), t: [b + 0.4, NEVER, NEVER, r2], h: [h, 2.5] });
      continue;
    }
    // a building dated before 1930 but taller than 3 floors is a later rebuild: first a small house, then today's block
    if (y < 1930 && (h > 12 || w * d > 450)) {
      const rb = tOf(1950 + hash2(i, 11) * 45), hs = 5 + r1 * 4, sw = Math.min(w, 12), sd = Math.min(d, 11);
      cW.set(y < 1906 ? OLD[ci % 6] : WHITE[Math.floor(hash2(i, 5) * 12)]);
      wallR.push({ m: M4(x, y0, z, ang, sw, 1, sd), c: cW.clone(), t: [b, rb, NEVER, r2], h: [0, hs] });
      if (y < 1925) hipR.push({ m: M4(x, y0 + hs, z, ang, sw + 0.6, Math.min(4, Math.min(sw, sd) * 0.32), sd + 0.6), c: new THREE.Color(ROOF[Math.floor(r1 * 3.99)]), t: [b + 0.15, rb, NEVER, r2] });
      else roofR.push({ m: M4(x, y0, z, ang, sw - 1, 1, sd - 1), c: cW.clone().multiplyScalar(0.86), t: [b, rb, NEVER, r2], h: [hs - 0.05, 0.25] });
      t[0] = rb + 0.6;
    }
    const old = h < 14 && (y < 1912 || (y < 1925 && r1 < 0.3));
    const pick = Math.floor(hash2(i, 5) * 12), mx = hash2(i, 6);
    cW.set(old && y < 1906 ? OLD[ci % 6] : mx < (y > 1960 ? 0.55 : y > 1935 ? 0.3 : 0.12) ? ACCENT[Math.floor(hash2(i, 4) * ACCENT.length)] : kind === 1 ? MID[pick] : WHITE[pick]);
    // 1930s-60s plaster blocks: often the Bauhaus look (ribbon windows, long balconies); the rest: punched windows
    const bau = !old && y > 1929 && y < 1970 && h < 30 && hash2(i, 9) < 0.55;
    const hip = old && w < 14 && d < 14;             // bigger old buildings (khans, warehouses) have flat roofs
    if (hip) wallR.push({ m: M4(x, y0, z, ang, w, 1, d), c: cW.clone(), t, h: [0, h + 0.8] });
    else {
      const rc = new THREE.Color(ROOFS[Math.floor(hash2(i, 3) * 5.99)]).lerp(cW, 0.3);
      (bau ? prismB : prismR).push({ ring, y0, c: cW.clone(), rc, t, h: [0, h + 0.8] });
    }
    if (hip) hipR.push({ m: M4(x, y0 + h + 0.8, z, ang, w + 0.6, Math.min(4, Math.min(w, d) * 0.32), d + 0.6), c: new THREE.Color(ROOF[Math.floor(r1 * 3.99)]), t: [t[0] + 0.15, NEVER, NEVER, r2] });
    else {
      // rooftop solar water heaters, a Tel Aviv signature (panel + white tank), from the 1950s on
      if (y > 1950 && h < 40 && w > 7 && d > 7 && r2 < 0.75) {
        const n = 1 + Math.floor(r1 * 3), ca = Math.cos(ang), sa = Math.sin(ang);
        for (let q = 0; q < n; q++) {
          const ox = (hash2(i, 20 + q) - 0.5) * (w - 4), oz = (hash2(i, 30 + q) - 0.5) * (d - 4);
          const px = x + ox * ca + oz * sa, pz = z - ox * sa + oz * ca;
          if (!inRing(ring, px, pz) || !inRing(ring, px, pz + 1.6)) continue;
          SOLAR.push({ m: M4(px, y0, pz, ang, 2.2, 1, 1.4), c: solarDark, t: [t[0] + 0.5, NEVER, NEVER, r2], h: [h + 1.0, 0.5] });
          SOLAR.push({ m: M4(px, y0, pz + 1.2, ang, 2.0, 1, 0.8), c: solarTank, t: [t[0] + 0.5, NEVER, NEVER, r2], h: [h + 1.0, 1.0] });
        }
      }
    }
  }
  // a street is laid out when the houses along it go up, not years before across empty land
  for (const sg of segs) {
    let hb = NEVER;
    for (const [qx, qz] of [[sg.ax, sg.az], [(sg.ax + sg.bx) / 2, (sg.az + sg.bz) / 2], [sg.bx, sg.bz]])
      for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) { const v = houseAt.get((Math.floor(qx / HCS) + dx) * 100003 + Math.floor(qz / HCS) + dz); if (v !== undefined) hb = Math.min(hb, v); }
    if (hb < NEVER) sg.ba = sg.bb = Math.max(sg.ba, hb - 1.0);
  }
  scene.add(growMesh(unitBox(), STD({ roughness: 0.92 }), "house", wallR, { facade: 1 }));
  scene.add(growMesh(unitBox(), STD({ roughness: 0.9 }), "house", wallB, { facade: 3 }));
  scene.add(growMesh(unitBox(), STD({ roughness: 0.6 }), "house", SOLAR, { shadow: false }));
  scene.add(growMesh(unitBox(), STD({ roughness: 1 }), "house", roofR, { shadow: false }));
  scene.add(growMesh(facet(hipRoof()), STD({ roughness: 0.9, flatShading: true }), "uniform", hipR));
  scene.add(growMesh(unitBox(), STD({ roughness: 0.28, metalness: 0.08 }), "house", glassR, { facade: 2 }));
  scene.add(growMesh(unitBox(), STD({ roughness: 0.6 }), "house", capR, { shadow: false }));
  scene.add(growPrisms(prismR, STD({ roughness: 0.92 }), { facade: 1 }));
  scene.add(growPrisms(prismB, STD({ roughness: 0.9 }), { facade: 3 }));
  scene.add(growPrisms(prismG, STD({ roughness: 0.28, metalness: 0.08 }), { facade: 2 }));

  // ---------- trees: parks, boulevards (cleared nowhere: they come with the streets) ----------
  const trunkR = [], crownR = [];
  const GREENS = ["#5a9a3c", "#4f8f36", "#68a844", "#43822f", "#72b04a", "#5f9e3f"];
  for (let i = 0; i < DATA.T.length; i += 4) {
    const [y0t, x, z, s] = DATA.T.slice(i, i + 4), y = Math.max(y0t, 1935 + hash2(i, 9) * 8);
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
      if (yearF(Math.min(MDUR, b)) < 1915) continue;
      trunkR.push({ m: M4(x, gy, z, r1 * 6, 0.4, hgt, 0.4), c: new THREE.Color("#7a6347"), t: [b, NEVER, NEVER, r1] });
      crownR.push({ m: M4(x, gy + hgt, z, r1 * 6.28, 3.4 * s, 3.0 * s, 3.4 * s), c: new THREE.Color(GREENS[Math.floor(r1 * 5.99)]), t: [b, NEVER, NEVER, r1] });
    }
  }
  // garden trees: Tel Aviv's yards and courtyards are full of ficus, jacaranda and palms. An occupancy grid (2 m) keeps
  // them off every building and street; they fill the gaps a few years after the houses around them
  const OX = -3400, OZ = -4200, OC = 2, ON = 3900, occ = new Uint8Array(ON * ON);
  const mark = (cx, cz, hx, hz, a) => {                  // a rotated rectangle (half sizes) into the grid
    const ca = Math.cos(a), sa = Math.sin(a), R = Math.hypot(hx, hz);
    for (let gz = Math.max(0, Math.floor((cz - R - OZ) / OC)); gz <= Math.min(ON - 1, Math.floor((cz + R - OZ) / OC)); gz++)
      for (let gx = Math.max(0, Math.floor((cx - R - OX) / OC)); gx <= Math.min(ON - 1, Math.floor((cx + R - OX) / OC)); gx++) {
        const px = OX + (gx + 0.5) * OC - cx, pz = OZ + (gz + 0.5) * OC - cz;
        if (Math.abs(px * ca - pz * sa) <= hx && Math.abs(px * sa + pz * ca) <= hz) occ[gz * ON + gx] = 1;
      }
  };
  for (let i = 0; i < B.length; i += 9) mark(B[i] / 10, B[i + 1] / 10, B[i + 2] / 20 * 1.15 + 1.5, B[i + 3] / 20 * 1.15 + 1.5, B[i + 4] / 1000);
  for (const sg of segs) { const L = Math.hypot(sg.bx - sg.ax, sg.bz - sg.az); if (L > 0.5) mark((sg.ax + sg.bx) / 2, (sg.az + sg.bz) / 2, L / 2 + 1, sg.w / 2 + 1.5, -Math.atan2(sg.bz - sg.az, sg.bx - sg.ax)); }
  const free = (x, z) => { const gx = Math.floor((x - OX) / OC), gz = Math.floor((z - OZ) / OC); if (gx < 1 || gz < 1 || gx >= ON - 1 || gz >= ON - 1) return false;
    for (let dz = -1; dz <= 1; dz++) for (let dx = -1; dx <= 1; dx++) if (occ[(gz + dz) * ON + gx + dx]) return false; return true; };
  const DEEP = ["#3f7a2e", "#356b28", "#4a8834", "#2f6326"];
  let nGarden = 0;
  for (let gx = -380; gx <= 420; gx++) for (let gz = -420; gz <= 360; gz++) {
    const x = gx * 9.5 + (hash2(gx, gz) - 0.5) * 7, z = gz * 9.5 + (hash2(gz, gx + 7) - 0.5) * 7, r1 = hash2(gx * 3 + 1, gz * 5 + 2);
    if (r1 < 0.32 + 0.3 * fbm(x * 0.004 - 11, z * 0.004 + 5) - 0.15) continue;
    let hb = NEVER; for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) { const v = houseAt.get((Math.floor(x / HCS) + dx) * 100003 + Math.floor(z / HCS) + dz); if (v !== undefined) hb = Math.min(hb, v); }
    if (hb >= NEVER || !free(x, z) || shoreDist(x, z) < 25) continue;
    const b = Math.max(hb + 1.5 + r1 * 4, tOf(1911)), gy = heightAt(x, z) - 0.3, q = hash2(gx * 7, gz * 11);
    if (b > MDUR) continue;
    if (q < 0.12 && yearF(Math.min(MDUR, b)) > 1925) {           // a Washingtonia palm: tall bare trunk, a flat star of fronds
      const ph = 8 + q * 40;
      trunkR.push({ m: M4(x, gy, z, 0, 0.3, ph, 0.3), c: new THREE.Color("#8a7458"), t: [b, NEVER, NEVER, r1] });
      crownR.push({ m: M4(x, gy + ph, z, q * 60, 3.0, 1.0, 3.0), c: new THREE.Color("#4e7f33"), t: [b, NEVER, NEVER, r1] });
    } else {
      const sc = 0.7 + q * 0.75, hgt = (3.2 + q * 2.5) * sc;
      trunkR.push({ m: M4(x, gy, z, q * 6, 0.42, hgt, 0.42), c: new THREE.Color("#7a6347"), t: [b, NEVER, NEVER, r1] });
      crownR.push({ m: M4(x, gy + hgt, z, r1 * 6.28, 3.6 * sc, 3.1 * sc, 3.6 * sc), c: new THREE.Color(q < 0.55 ? GREENS[Math.floor(r1 * 5.99)] : DEEP[Math.floor(r1 * 3.99)]), t: [b, NEVER, NEVER, r1] });
    }
    nGarden++;
  }
  // lone trees across the open land (carob, sycamore, eucalyptus windbreaks) as it greens up; they stay in the gaps later
  for (let gx = -160; gx <= 180; gx++) for (let gz = -175; gz <= 150; gz++) {
    const x = gx * 24 + (hash2(gx + 5, gz) - 0.5) * 18, z = gz * 24 + (hash2(gz, gx - 5) - 0.5) * 18, r1 = hash2(gx * 13, gz * 17);
    if (r1 > 0.12 + 0.22 * fbm(x * 0.002 + 3, z * 0.002 - 8) || shoreDist(x, z) < 60 || !free(x, z)) continue;
    const b = tOf(1914 + hash2(gx, gz * 3) * 30), gy = heightAt(x, z) - 0.3, q = hash2(gx * 5, gz * 7), sc = 0.8 + q * 0.7, hgt = (3.4 + q * 2.4) * sc;
    trunkR.push({ m: M4(x, gy, z, q * 6, 0.45, hgt, 0.45), c: new THREE.Color("#6e5a40"), t: [b, NEVER, NEVER, r1] });
    crownR.push({ m: M4(x, gy + hgt, z, r1 * 6.28, 3.8 * sc, 3.2 * sc, 3.8 * sc), c: new THREE.Color(DEEP[Math.floor(q * 3.99)]), t: [b, NEVER, NEVER, r1] });
  }
  // orchards round Jaffa and Sarona before the city (the land of the citrus groves), cleared as houses arrive
  const clearAt = (x, z) => { let t = NEVER; for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) { const v = houseAt.get((Math.floor(x / HCS) + dx) * 100003 + Math.floor(z / HCS) + dz); if (v !== undefined) t = Math.min(t, v - 0.4); } return t; };
  // each grove (pardes) is a walled rectangular plot with its trees in rows and a cactus hedge round it
  const [jx, jz] = LL(32.0535, 34.7525), [sx, sz] = LL(32.0718, 34.7865);
  const groves = [], hedgeR = [], [ax0, az0] = LL(32.0635, 34.7715);
  for (let gx = -40; gx <= 40; gx++) for (let gz = -40; gz <= 40; gz++) {
    // plots tile a slightly rotated grid, separated by narrow sandy tracks, in clusters along the old roads
    const G0 = -0.12, gc = Math.cos(G0), gs = Math.sin(G0), cu = gx * 98 + (gz % 2) * 31, cv = gz * 92;
    const x = cu * gc + cv * gs, z = -cu * gs + cv * gc, r1 = rnd(), r2 = rnd();
    const near = Math.min(Math.hypot(x - jx - 1000, z - jz + 250) / 1700, Math.hypot(x - sx - 400, z - sz + 300) / 1500);
    if (near > 1 || fbm(x * 0.003 + 7, z * 0.003 - 3) < 0.4 + near * 0.1 || shoreDist(x, z) < 115) continue;   // shoreDist is clamped at ±120 m
    if (Math.hypot(x - ax0, z - az0) < 650) continue;      // Ahuzat Bayit was bought on bare dunes (the 1909 lottery photo)
    const w = r1 < 0.25 ? 50 + r2 * 25 : 84 + r1 * 10, d = 78 + r2 * 10, ang = G0 + (r2 - 0.5) * 0.06, ca = Math.cos(ang), sa = Math.sin(ang);
    let death = clearAt(x, z);
    for (const [u, v] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) death = Math.min(death, clearAt(x + (u * w / 2) * ca + (v * d / 2) * sa, z - (u * w / 2) * sa + (v * d / 2) * ca));
    if (death < 2) continue;
    death = Math.min(death, tOf(1952 + r1 * 16));          // the last groves inside the city were gone by the late 1960s
    groves.push({ x, z, rx: w / 2 - 2, rz: d / 2 - 2, ry: -ang, b: death });
    const gy = heightAt(x, z) - 0.3, dark = r1 < 0.5;
    for (let u = -w / 2 + 5; u < w / 2 - 3; u += 7.5) for (let v = -d / 2 + 5; v < d / 2 - 3; v += 7.5) {
      const tx = x + u * ca + v * sa, tz = z - u * sa + v * ca, q = hash2(Math.round(tx * 7), Math.round(tz * 7));
      if (q < 0.04) continue;
      const td = death - q * 0.5, hgt = 1.8 + q * 0.7, s = 2.7 + q * 0.6;
      trunkR.push({ m: M4(tx, gy, tz, q * 6, 0.35, hgt, 0.35), c: new THREE.Color("#6e5a40"), t: [-1, td, NEVER, q] });
      crownR.push({ m: M4(tx, gy + hgt, tz, q * 6.28, s, s * 0.85, s), c: new THREE.Color(dark ? ["#2f5e27", "#3a6b2e", "#2c5524"][Math.floor(q * 2.99)] : ["#467a31", "#3f7130", "#4f8236"][Math.floor(q * 2.99)]), t: [-1, td, NEVER, q] });
    }
    for (const [u, v, a, l] of [[0, -d / 2, 0, w], [0, d / 2, 0, w], [-w / 2, 0, 1, d], [w / 2, 0, 1, d]]) {
      const hx = x + u * ca + v * sa, hz = z - u * sa + v * ca;
      hedgeR.push({ m: M4(hx, gy, hz, ang + a * Math.PI / 2, l, 1, 1.4), c: new THREE.Color(r2 < 0.5 ? "#5f7a3c" : "#c9b48c"), t: [-1, death - 0.3, NEVER, r1], h: [0, r2 < 0.5 ? 1.8 : 1.3] });
    }
  }
  scene.add(growMesh(unitBox(), STD({ roughness: 1 }), "house", hedgeR, { shadow: false }));
  const groveTex = rasterGround({ X0: -3400, Z0: -4200, EXT: 7800, TEX: 2048 }, [], groves, []);
  const trunkGeo = new THREE.CylinderGeometry(0.5, 0.7, 1, 5); trunkGeo.translate(0, 0.5, 0);
  scene.add(growMesh(trunkGeo, STD({ roughness: 1 }), "uniform", trunkR, { shadow: false }));
  scene.add(growMesh(facet(new THREE.IcosahedronGeometry(1, 0)), STD({ flatShading: true, roughness: 0.95 }), "uniform", crownR));

  // ---------- ground texture: streets (with birth times) and the built-up paving round houses ----------
  const GX = { X0: -3400, Z0: -4200, EXT: 7800, TEX: 4096 };
  const groundTex = rasterGround(GX, segs, [], []);
  // paving: a narrow apron round each building plus the pavements along every street
  const paving = [];
  for (let i = 0; i < B.length; i += 9) {
    const x = B[i] / 10, z = B[i + 1] / 10, w = B[i + 2] / 10 * 1.12, d = B[i + 3] / 10 * 1.12, ry = -B[i + 4] / 1000, b = Math.max(0, bBirth[i / 9] - 0.8);
    if (b >= NEVER - 1) continue;
    paving.push({ x, z, rx: w / 2 + 1.2, rz: d / 2 + 1.2, ry, b });
  }
  const walks = segs.map((sg) => ({ ...sg, w: sg.w + 3.5 }));
  const urbanTex = rasterGround(GX, walks, paving, []);
  // the city's final footprint, blurred (about 150 m): open fields only start well outside it, with a soft edge
  const cm = document.createElement("canvas"); cm.width = cm.height = 512;
  const c0 = document.createElement("canvas"); c0.width = c0.height = 512;
  const g0 = c0.getContext("2d"); g0.fillStyle = "#000"; g0.fillRect(0, 0, 512, 512); g0.fillStyle = "#fff";
  for (let i = 0; i < B.length; i += 9) { const px = (B[i] / 10 - GX.X0) / GX.EXT * 512, pz = (B[i + 1] / 10 - GX.Z0) / GX.EXT * 512; g0.fillRect(px - 1.5, pz - 1.5, 3, 3); }
  const cg = cm.getContext("2d"); cg.filter = "blur(10px)"; cg.drawImage(c0, 0, 0);
  const cityTex = new THREE.CanvasTexture(cm); cityTex.flipY = false;
  const PK = DATA.P, pkRaw = Uint8Array.from(atob(PK.b64), (c) => c.charCodeAt(0));
  const parkTex = new THREE.DataTexture(pkRaw, PK.n, PK.n, THREE.RGFormat); parkTex.flipY = false; parkTex.needsUpdate = true;

  // ---------- terrain ----------
  const TWD = 13000, TN = 1000;
  const tGeo = new THREE.PlaneGeometry(TWD, TWD, TN, TN); tGeo.rotateX(-Math.PI / 2); tGeo.translate(-1000, 0, 0);
  const tp = tGeo.attributes.position;
  for (let i = 0; i < tp.count; i++) tp.setY(i, heightAt(tp.getX(i), tp.getZ(i)));
  tGeo.computeVertexNormals();
  const UT = { uGround: { value: groundTex }, uUrban: { value: urbanTex }, uOrig: { value: new THREE.Vector4(GX.X0, GX.Z0, GX.EXT, GX.TEX) }, uPave: { value: 0 }, uPark: { value: parkTex }, uPorig: { value: new THREE.Vector4(PK.x0, PK.z0, PK.ext, PK.n) }, uYear: { value: 1880 }, uGreen: { value: 0 }, uGrove: { value: groveTex }, uCity: { value: cityTex } };
  const tMat = STD({ color: "#ffffff", roughness: 1 });
  tMat.onBeforeCompile = (s) => {
    Object.assign(s.uniforms, UT, { uTime: U.uTime });
    s.vertexShader = s.vertexShader.replace("#include <common>", "#include <common>\nvarying vec3 vW;")
      .replace("#include <worldpos_vertex>", "#include <worldpos_vertex>\nvW = (modelMatrix * vec4(transformed, 1.0)).xyz;");
    s.fragmentShader = s.fragmentShader.replace("#include <common>", `#include <common>
      varying vec3 vW; uniform sampler2D uGround, uUrban, uPark, uGrove, uCity; uniform vec4 uOrig, uPorig; uniform float uTime, uPave, uYear, uGreen;
      ${GROUND_GLSL}`)
      .replace("#include <color_fragment>", /* glsl */ `#include <color_fragment>
      {
        float nz = n21(vW.xz * 0.004), nf = n21(vW.xz * 0.03);
        // smooth, even ground (no speckle): broad tone changes only, like a painted model
        vec3 sand = mix(Ls(vec3(0.89, 0.81, 0.63)), Ls(vec3(0.86, 0.77, 0.59)), nz);
        vec3 col = mix(sand, Ls(vec3(0.70, 0.69, 0.47)), smoothstep(0.5, 0.85, n21(vW.xz * 0.0012 + 4.0)) * 0.35);
        // the land greens up as the city grows (gardens, orchards, parks, lawns): sand stays on the coastal strip
        // open country: a patchwork of fields (wheat, stubble, ploughed earth, vegetables, fallow) on a tilted grid
        vec2 fr = mat2(0.993, -0.12, 0.12, 0.993) * vW.xz, fc = floor(fr / vec2(150.0, 100.0)), fl = fract(fr / vec2(150.0, 100.0));
        float sp = 0.3 + 0.4 * h21(fc - 9.0), sx = h21(fc + 2.0), hf = sx < 0.5 ? step(sp, fl.x) : 2.0 + step(sp, fl.y);   // split each plot in two
        fl = sx < 0.5 ? vec2(fl.x < sp ? fl.x / sp : (fl.x - sp) / (1.0 - sp), fl.y) : vec2(fl.x, fl.y < sp ? fl.y / sp : (fl.y - sp) / (1.0 - sp));
        fc = fc * 4.0 + hf;
        float fh = h21(fc + 31.0), fh2 = h21(fc * 1.7 - 5.0);
        vec3 field = fh < 0.3 ? Ls(vec3(0.40, 0.56, 0.22)) : fh < 0.45 ? Ls(vec3(0.52, 0.60, 0.28)) : fh < 0.56 ? Ls(vec3(0.66, 0.64, 0.38))
                   : fh < 0.64 ? Ls(vec3(0.55, 0.49, 0.34)) : fh < 0.85 ? Ls(vec3(0.35, 0.51, 0.20)) : Ls(vec3(0.46, 0.58, 0.26));
        field *= mix(0.94, 1.04, step(0.5, fract((fh2 < 0.5 ? fr.x : fr.y) / 5.0)));          // furrows
        float edge = min(min(fl.x, 1.0 - fl.x) * 70.0, min(fl.y, 1.0 - fl.y) * 50.0);
        field = mix(Ls(vec3(0.33, 0.45, 0.19)), field, smoothstep(0.8, 2.2, edge));          // hedgerows and tracks
        vec3 grass = mix(Ls(vec3(0.41, 0.57, 0.24)), Ls(vec3(0.45, 0.60, 0.26)), n21(vW.xz * 0.0011 + 9.0)) * mix(0.96, 1.03, n21(vW.xz * 0.006 - 4.0));
        vec2 cu = (vW.xz - uOrig.xy) / uOrig.z;
        float city = (cu.x > 0.0 && cu.y > 0.0 && cu.x < 1.0 && cu.y < 1.0) ? texture2D(uCity, cu).r : 0.0;
        grass = mix(grass, field, smoothstep(0.12, 0.02, city) * 0.75);
        float inland = smoothstep(1.75, 2.0, vW.y);           // the land is 2 m up at 120 m from the shore (the clamp of the shore grid)
        col = mix(col, grass, uGreen * inland);
        col = mix(col, Ls(vec3(0.95, 0.90, 0.78)), smoothstep(1.6, 0.5, vW.y) * 0.8);             // the beach
        vec2 uv = (vW.xz - uOrig.xy) / uOrig.z;
        if (uv.x > 0.0 && uv.y > 0.0 && uv.x < 1.0 && uv.y < 1.0) {
          // the citrus groves: dark irrigated earth under the rows, gone when the plot is cleared
          vec4 gv = texture2D(uGrove, uv); vec4 gvn = texelFetch(uGrove, ivec2(uv * 2048.0), 0);
          float gd = (gvn.g * 255.0 * 256.0 + gvn.b * 255.0) / 100.0;
          vec3 earth = Ls(vec3(0.43, 0.45, 0.27));
          col = mix(col, earth, gv.r * (1.0 - smoothstep(gd - 0.4, gd + 0.4, uTime)) * 0.9);
          vec4 ur = texture2D(uUrban, uv); vec4 un = texelFetch(uUrban, ivec2(uv * uOrig.w), 0);
          float ub = (un.g * 255.0 * 256.0 + un.b * 255.0) / 100.0;
          vec3 lot = mix(Ls(vec3(0.80, 0.75, 0.64)), Ls(vec3(0.76, 0.75, 0.72)), uPave);
          col = mix(col, lot, ur.r * smoothstep(ub, ub + 0.8, uTime) * 0.92);
          vec4 g = texture2D(uGround, uv); vec4 gn = texelFetch(uGround, ivec2(uv * uOrig.w), 0);
          float birth = (gn.g * 255.0 * 256.0 + gn.b * 255.0) / 100.0;
          float road = g.r * smoothstep(birth, birth + 0.6, uTime);
          vec3 dirt = Ls(vec3(0.76, 0.66, 0.50)), asph = mix(Ls(vec3(0.30, 0.31, 0.33)), Ls(vec3(0.36, 0.37, 0.39)), nf);
          col = mix(col, mix(dirt, asph, uPave), road * 0.95);
        }
        vec2 pv = (vW.xz - uPorig.xy) / uPorig.z;
        if (pv.x > 0.0 && pv.y > 0.0 && pv.x < 1.0 && pv.y < 1.0) {
          // bilinear over the 4 nearest park cells, so lawns have smooth edges instead of stair steps
          vec2 pc = pv * uPorig.w - 0.5, pf = fract(pc); ivec2 p0 = ivec2(floor(pc));
          float on[4];
          for (int k = 0; k < 4; k++) {
            vec2 pk = texelFetch(uPark, p0 + ivec2(k & 1, k >> 1), 0).rg;
            float py = max((pk.r * 255.0 + pk.g * 255.0 * 256.0) / 100.0 + 1800.0, 1935.0);   // no public lawns before the 1930s
            on[k] = pk.r + pk.g > 0.0 ? smoothstep(py, py + 1.5, uYear) : 0.0;
          }
          float pm = smoothstep(0.35, 0.65, mix(mix(on[0], on[1], pf.x), mix(on[2], on[3], pf.x), pf.y));
          vec3 grass = Ls(vec3(0.37, 0.56, 0.21)) * mix(0.97, 1.03, nz);
          col = mix(col, grass, pm * 0.95);
        }
        diffuseColor.rgb = col;
      }`);
  };
  const terrain = new THREE.Mesh(tGeo, tMat); terrain.receiveShadow = true; scene.add(terrain);
  const ringG = new THREE.RingGeometry(6300, 60000, 192, 1).rotateX(-Math.PI / 2), rp = ringG.attributes.position, rc = new Float32Array(rp.count * 3);
  for (let i = 0; i < rp.count; i++) {                  // the far ring: the Mediterranean to the west, land to the east
    const ax = rp.getX(i), az = rp.getZ(i), a = Math.atan2(az, ax), sea = sm(clamp((Math.cos(a) * -1 - 0.05) / 0.25));
    const c = new THREE.Color("#7f9455").lerp(new THREE.Color("#4f8fb4"), sea); rc[i * 3] = c.r; rc[i * 3 + 1] = c.g; rc[i * 3 + 2] = c.b;
    rp.setY(i, lerp(-0.4, -1.6, sea));                  // just under the land (and under the water level at sea)
  }
  ringG.setAttribute("color", new THREE.BufferAttribute(rc, 3));
  const farGround = new THREE.Mesh(ringG, STD({ vertexColors: true, roughness: 0.8 }));
  farGround.position.set(-1000, 0, 0); scene.add(farGround);

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

  // ---------- life: sailboats offshore, cars on the main roads from the 1950s ----------
  const boats = [];
  const hullM = STD({ color: "#f4f1ea" }), sailM = STD({ color: "#ffffff", side: THREE.DoubleSide }), deckM = STD({ color: "#8a6a48" });
  const rb = mulberry32(77);
  for (let k = 0; k < 46; k++) {
    let x = 0, z = 0; for (let tries = 0; tries < 40; tries++) { x = -4200 + rb() * 3600; z = -4200 + rb() * 8400; if (shoreDist(x, z) < -110) break; }
    const g = new THREE.Group(), big = k < 6, L = big ? 60 : 9 + rb() * 6;
    const hull = new THREE.Mesh(new THREE.BoxGeometry(L, big ? 6 : 1.6, big ? 11 : 3).translate(0, big ? 2 : 0.6, 0), big ? STD({ color: "#c94a3a" }) : hullM); hull.castShadow = true; g.add(hull);
    if (big) { const b2 = new THREE.Mesh(new THREE.BoxGeometry(L * 0.3, 8, 9).translate(-L * 0.28, 9, 0), hullM); b2.castShadow = true; g.add(b2); }
    else { const s = new THREE.Mesh(new THREE.ConeGeometry(L * 0.32, L * 1.05, 3).translate(0, L * 0.6 + 1, 0), sailM); s.scale.z = 0.12; s.castShadow = true; g.add(s); }
    scene.add(g);
    boats.push({ g, x0: x, z0: z, v: (rb() < 0.5 ? -1 : 1) * (big ? 4 : 2 + rb() * 3), born: big ? tOf(1950 + rb() * 50) : rb() * 120, ph: rb() * 6 });
  }
  const mains = segs.filter((sg) => sg.w >= 9 && Math.hypot(sg.bx - sg.ax, sg.bz - sg.az) > 25);
  const NC = Math.min(2200, mains.length * 2), cars = new THREE.InstancedMesh(new THREE.BoxGeometry(4.2, 1.6, 2).translate(0, 0.8, 0), STD({ roughness: 0.4 }), NC);
  cars.frustumCulled = false; cars.castShadow = false; scene.add(cars);
  const carP = [], CC = ["#f2f2f0", "#c8ccd2", "#222428", "#b8302a", "#f2c230", "#3a5f9a", "#f2f2f0"];
  for (let k = 0; k < NC; k++) { const sg = mains[Math.floor(hash2(k, 41) * mains.length)]; carP.push({ sg, u: hash2(k, 42), dir: hash2(k, 43) < 0.5 ? 1 : -1, sp: 9 + hash2(k, 44) * 6, on: hash2(k, 45) }); cars.setColorAt(k, new THREE.Color(CC[k % CC.length])); }
  const _cm = new THREE.Matrix4(), _cq = new THREE.Quaternion(), _cs = V(1, 1, 1), _cp = V(), _up = V(0, 1, 0);
  function updateLife(t) {
    for (const b of boats) {
      const on = sm(ramp(t, b.born, b.born + 1)); b.g.visible = on > 0.01; if (!b.g.visible) continue;
      let z = b.z0 + b.v * t; z = ((z + 4200) % 8400 + 8400) % 8400 - 4200;
      b.g.position.set(b.x0, 0.2 + Math.sin(t * 1.1 + b.ph) * 0.15, z); b.g.rotation.set(0, b.v > 0 ? -Math.PI / 2 : Math.PI / 2, Math.sin(t * 0.9 + b.ph) * 0.03); b.g.scale.setScalar(on);
    }
    const share = sm(ramp(yearF(t), 1948, 2005)); let n = 0;
    for (const c of carP) {
      if (c.on > share || t < c.sg.ba + 3) continue;
      const L = Math.hypot(c.sg.bx - c.sg.ax, c.sg.bz - c.sg.az), f = ((c.u + c.dir * t * c.sp / L) % 1 + 1) % 1;
      const ux = (c.sg.bx - c.sg.ax) / L, uz = (c.sg.bz - c.sg.az) / L, lane = c.sg.w * 0.22 * c.dir;
      _cp.set(c.sg.ax + (c.sg.bx - c.sg.ax) * f - uz * lane, heightAt(c.sg.ax, c.sg.az) - 0.3, c.sg.az + (c.sg.bz - c.sg.az) * f + ux * lane);
      _cq.setFromAxisAngle(_up, -Math.atan2(uz, ux) + (c.dir < 0 ? Math.PI : 0));
      cars.setMatrixAt(n++, _cm.compose(_cp, _cq, _cs));
    }
    cars.count = n; cars.instanceMatrix.needsUpdate = true; if (cars.instanceColor) cars.instanceColor.needsUpdate = true;
  }

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
    [177, [wx - 650, 950, wz + 1250], [px + 120, 0, pz + 850]],
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
    [MDUR, [wx - 2900, 3300, wz + 2700], [wx + 700, 0, wz - 200]],
  ]);
  const drawHud = hudDriver(hud, { ERAS, FLAGS, TITLE, LANDMARKS, CAPTIONS, CARDS, yearAt, popAt, DUR: MDUR });

  const ready = Promise.resolve();
  const introPose = { pos: V(wx - 3200, 2300, wz + 2600), tgt: V(wx + 500, 0, wz - 300) };
  function renderAt(time) {
    time = clamp(time, 0, DUR);
    // intro: the city today, then a fast rewind to 1880 (the main timeline runs backwards), then the flight starts
    const intro = time < INTRO;
    const mainT = intro ? (time < 2.5 ? 500 : time < 8 ? 500 * (1 - sm(sm(ramp(time, 2.5, 8)))) : 0) : time - INTRO;
    const t = clamp(mainT, 0, MDUR);
    U.uTime.value = t;
    UT.uPave.value = sm(ramp(yearF(t), 1925, 1960)); UT.uYear.value = yearF(t); UT.uGreen.value = sm(ramp(yearF(t), 1906, 1928));
    updateLM(t); updDust(t); updateLife(t);
    let { pos, tgt } = cam(t);
    if (intro) { const k = sm(ramp(time, 5.5, 9)); pos = introPose.pos.clone().lerp(pos, k); tgt = introPose.tgt.clone().lerp(tgt, k); }
    const dist = st.frame(pos, tgt), haze = sm(clamp((dist - 1400) / 2600)); st.scene.fog.near *= lerp(1.3, 0.55, haze); st.scene.fog.far *= lerp(1.4, 0.42, haze);
    // golden hour over the last minute
    const dusk = intro ? 0 : sm(ramp(t, 505, 535));
    st.sun.color.set("#fff1d6").lerp(new THREE.Color("#ffc890"), dusk * 0.7); st.sun.intensity = 3.3 - 0.4 * dusk; st.hemi.intensity = 1.2 - 0.1 * dusk;
    drawHud(t);
    if (intro) {
      hud.black.style.opacity = 1 - clamp(time / 1.2); hud.ui.style.opacity = clamp((time - 0.4) / 0.8);
      for (const el of [hud.title, hud.lm, hud.cap, hud.card]) el.style.opacity = 0;
    } else {
      hud.black.style.opacity = clamp((t - (MDUR - 1.8)) / 1.6); hud.ui.style.opacity = 1 - clamp((t - (MDUR - 2.4)) / 1.2);
    }
    st.render();
  }
  return { ready, renderAt, DUR, stats: { houses: wallR.length, towers: glassR.length, roofs: hipR.length, trees: crownR.length, roads: segs.length } };
}
