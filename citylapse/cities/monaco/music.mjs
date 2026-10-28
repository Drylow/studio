// Babylon's own score (305 s), written sample by sample: D Hijaz (D Eb F# G A Bb C) for an ancient Near-Eastern colour.
// Voices: a cello drone, oud-like plucks (Karplus-Strong), a breathy ney flute, a frame drum (dum / tek), a strings pad,
// a choir in the golden age, timpani and gong swells on the big events, wind, fire crackle and the flood's rumble.
// Sections follow SPEC.md: growth 9-46, Hittite sack 48, Kassite calm 56-96, the destruction and flood 98-120,
// the age of Nebuchadnezzar 136-206, the fall 206-232, Alexander 232-262, the slow end 262-305.
//   node music.mjs  ->  assets/music.m4a (-14 LUFS)
import { writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { join, dirname } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const SR = 48000, DUR = 305, N = DUR * SR;
const L = new Float32Array(N), R = new Float32Array(N), SL = new Float32Array(N), SRv = new Float32Array(N);
let seed = 1792;
const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const ramp = (t, a, b) => clamp((t - a) / (b - a));
const mtof = (m) => 440 * Math.pow(2, (m - 69) / 12);
const add = (i, l, r, send = 0.35) => { if (i < 0 || i >= N) return; L[i] += l; R[i] += r; SL[i] += l * send; SRv[i] += r * send; };
const master = (t) => ramp(t, 0, 4) * (1 - ramp(t, DUR - 5, DUR - 0.3));
const sec = (t, a, b, f = 2) => ramp(t, a - f, a + f) * (1 - ramp(t, b - f, b + f));

// D Hijaz degrees, MIDI around D3 = 50
const HJ = [0, 1, 4, 5, 7, 8, 10];
const deg = (d, base = 50) => base + 12 * Math.floor(d / 7) + HJ[((d % 7) + 7) % 7];

// section intensity (0..1) and which voices play
const I = (t) => Math.max(0.25, 0.35 + 0.4 * ramp(t, 9, 46) - 0.3 * sec(t, 56, 96, 4) - 0.25 * sec(t, 104, 120, 3) + 0.55 * sec(t, 136, 206, 4) + 0.25 * sec(t, 206, 232, 3) - 0.25 * ramp(t, 262, 292));
const oudOn = (t) => sec(t, 9, 47.5, 2) + 0.6 * sec(t, 58, 96, 3) + 0.5 * sec(t, 121, 136, 3) + sec(t, 137, 206, 2) + 0.5 * sec(t, 232, 262, 3);
const drumOn = (t) => sec(t, 14, 47.5, 2) + 0.4 * sec(t, 64, 92, 3) + sec(t, 140, 206, 2) + 0.9 * sec(t, 207, 228, 2) + 0.4 * sec(t, 236, 258, 3);
const padOn = (t) => 0.5 + 0.5 * sec(t, 30, 47, 3) + 0.7 * sec(t, 136, 232, 4) + 0.6 * sec(t, 290, 305, 4);
const choirOn = (t) => sec(t, 150, 206, 4) + 0.6 * sec(t, 292, 305, 3);

// chords (root offsets in D Hijaz) per section, 6 s each
function chordAt(t) {
  const prog = t > 136 && t < 232 ? [[50, 54, 57], [51, 55, 58], [50, 54, 57], [48, 51, 55], [43, 50, 55], [50, 54, 57], [51, 55, 58], [45, 50, 54]]
    : t > 96 && t < 136 ? [[50, 57, 62], [50, 55, 58], [48, 51, 55], [50, 57, 62]]
    : [[50, 54, 57], [51, 55, 58], [50, 54, 57], [48, 51, 55]];
  return prog[Math.floor(t / 6) % prog.length];
}

// ---------- drone: cello saws on D and A, swelling ----------
{
  let l1 = 0, l2 = 0, p = [0, 0, 0, 0];
  const fr = [mtof(38), mtof(38) * 1.003, mtof(45), mtof(45) * 0.998];
  for (let i = 0; i < N; i++) {
    const t = i / SR; let s = 0;
    for (let k = 0; k < 4; k++) { p[k] += fr[k] / SR; p[k] -= Math.floor(p[k]); s += 2 * p[k] - 1; }
    const fc = 260 + 500 * I(t), k1 = 1 - Math.exp(-2 * Math.PI * fc / SR);
    l1 += k1 * (s - l1); l2 += k1 * (l1 - l2);
    const g = 0.05 * master(t) * (0.6 + 0.6 * I(t)) * (1 + 0.15 * Math.sin(t * 0.4));
    add(i, l2 * g, l2 * g * 0.95, 0.3);
  }
}

// ---------- strings pad: detuned saws on the chords ----------
{
  const pl = new Float32Array(N), pr = new Float32Array(N);
  for (let c0 = 0; c0 < DUR; c0 += 6) {
    const notes = chordAt(c0 + 0.1).map((m) => m + 12);
    for (const m of notes) for (let v = 0; v < 4; v++) {
      const f = mtof(m) * (1 + (v - 1.5) * 0.004), pan = (v - 1.5) / 2; let ph = rnd();
      const i0 = Math.max(0, Math.floor((c0 - 1.5) * SR)), i1 = Math.min(N, Math.floor((c0 + 8) * SR));
      for (let i = i0; i < i1; i++) {
        const t = i / SR, env = Math.min(ramp(t, c0 - 1.5, c0 + 0.8), 1 - ramp(t, c0 + 5.8, c0 + 8));
        ph += f / SR; ph -= Math.floor(ph);
        const s = (2 * ph - 1) * env * 0.016 * padOn(t);
        pl[i] += s * (1 - pan * 0.5); pr[i] += s * (1 + pan * 0.5);
      }
    }
  }
  let a1 = 0, a2 = 0, b1 = 0, b2 = 0;
  for (let i = 0; i < N; i++) { const t = i / SR, fc = 600 + 1800 * I(t), k = 1 - Math.exp(-2 * Math.PI * fc / SR); a1 += k * (pl[i] - a1); a2 += k * (a1 - a2); b1 += k * (pr[i] - b1); b2 += k * (b1 - b2); const g = master(t); add(i, a2 * g, b2 * g, 0.55); }
}

// ---------- choir: formant-weighted harmonics with vibrato ----------
{
  const W = [1, 0.5, 0.45, 0.22, 0.3, 0.12, 0.06];
  for (let c0 = 0; c0 < DUR; c0 += 6) {
    if (choirOn(c0 + 3) <= 0 && choirOn(c0) <= 0) continue;
    for (const m0 of chordAt(c0 + 0.1)) {
      const f0 = mtof(m0 + 24), vph = rnd() * 6, i0 = Math.max(0, Math.floor((c0 - 1) * SR)), i1 = Math.min(N, Math.floor((c0 + 7.5) * SR));
      for (let i = i0; i < i1; i++) {
        const t = i / SR, o = choirOn(t); if (o <= 0) continue;
        const env = Math.min(ramp(t, c0 - 1, c0 + 1), 1 - ramp(t, c0 + 6, c0 + 7.5)) * o * master(t);
        if (env <= 0) continue;
        const f = f0 * (1 + 0.005 * Math.sin(2 * Math.PI * 5.2 * t + vph));
        let s = 0; for (let h = 0; h < W.length; h++) s += W[h] * Math.sin(2 * Math.PI * f * (h + 1) * t);
        s *= env * 0.009; add(i, s, s, 0.85);
      }
    }
  }
}

// ---------- oud: Karplus-Strong plucks, bright and short ----------
function pluck(t0, m, vel, pan = 0, decay = 0.993) {
  const f = mtof(m), n = Math.max(2, Math.round(SR / f)), buf = new Float32Array(n);
  for (let k = 0; k < n; k++) buf[k] = rnd() * 2 - 1;
  let p = 0; const i0 = Math.floor(t0 * SR), len = Math.floor(1.6 * SR);
  for (let j = 0; j < len; j++) {
    const i = i0 + j; if (i >= N) break;
    const cur = buf[p], nxt = buf[(p + 1) % n], v = (cur * 0.6 + nxt * 0.4) * decay;
    buf[p] = v; p = (p + 1) % n;
    const s = cur * vel * master(i / SR) * Math.min(1, j / 40);
    add(i, s * (1 - pan * 0.5), s * (1 + pan * 0.5), 0.3);
  }
}
{
  const BEAT = 0.3;                                                   // 100 bpm eighths
  const PATS = [[0, 1, 2, 1, 0, -1, 0, 2], [4, 3, 2, 1, 2, 1, 0, 0], [0, 2, 4, 5, 4, 2, 1, 0], [7, 5, 4, 2, 1, 2, 1, 0]];
  for (let t = 9; t < 262; t += BEAT) {
    const o = oudOn(t); if (o <= 0.05) continue;
    const bar = Math.floor(t / (BEAT * 8)), k = Math.round((t / BEAT)) % 8, pat = PATS[bar % 4];
    if ((k === 3 || k === 7) && rnd() < 0.5) continue;
    const m = deg(pat[k], 50 + 12);
    pluck(t + (rnd() - 0.5) * 0.01, m, (0.12 + 0.05 * (k === 0)) * o * (0.6 + 0.5 * I(t)), Math.sin(t * 0.7) * 0.5);
    if (k === 0 && I(t) > 0.6) pluck(t, deg(0, 50), 0.1 * o, -0.2, 0.995);
  }
}

// ---------- ney: breathy flute melody ----------
function ney(t0, dur, m, vel) {
  const f = mtof(m), i0 = Math.floor(t0 * SR), i1 = Math.min(N, Math.floor((t0 + dur + 0.8) * SR));
  let ph = 0, nl = 0;
  for (let i = i0; i < i1; i++) {
    const t = i / SR, u = t - t0, env = Math.min(clamp(u / 0.25), 1 - ramp(u, dur, dur + 0.8)) * vel * master(t);
    const ff = f * (1 + 0.007 * Math.sin(2 * Math.PI * 5.6 * u) * clamp((u - 0.3) / 0.6)) * (1 - 0.01 * Math.exp(-u * 12));
    ph += ff / SR;
    nl += 0.15 * ((rnd() * 2 - 1) - nl);
    const s = (Math.sin(2 * Math.PI * ph) * 0.8 + Math.sin(4 * Math.PI * ph) * 0.12 + nl * 0.35) * env * 0.045;
    add(i, s, s * 1.05, 0.7);
  }
}
// phrases: [start, [[deg, beats], ...]] with a beat of 0.6 s
const PH = [
  [3, [[4, 3], [5, 1], [4, 2], [2, 2], [1, 3], [0, 4]]],
  [22, [[4, 2], [5, 2], [7, 3], [5, 1], [4, 2], [2, 2], [1, 2], [0, 4]]],
  [36, [[7, 2], [8, 2], [7, 2], [5, 2], [4, 3], [2, 1], [1, 4]]],
  [60, [[2, 3], [1, 1], [0, 4], [-1, 2], [0, 6]]],
  [76, [[4, 4], [5, 2], [4, 2], [2, 4], [1, 6]]],
  [110, [[1, 4], [0, 4], [-1, 3], [-2, 2], [-3, 6]]],
  [124, [[0, 2], [1, 2], [2, 2], [4, 4], [2, 2], [1, 4]]],
  [160, [[7, 3], [8, 1], [9, 2], [8, 2], [7, 3], [5, 1], [4, 4]]],
  [176, [[4, 2], [5, 2], [7, 2], [8, 2], [9, 3], [8, 1], [7, 4]]],
  [192, [[9, 2], [8, 2], [7, 2], [5, 2], [4, 2], [2, 2], [1, 2], [0, 6]]],
  [238, [[4, 3], [2, 1], [1, 4], [0, 6]]],
  [266, [[2, 4], [1, 4], [0, 6], [-1, 4], [0, 8]]],
  [288, [[4, 4], [5, 2], [4, 2], [2, 4], [1, 4], [0, 8]]],
];
for (const [t0, notes] of PH) { let t = t0; for (const [d, b] of notes) { ney(t, b * 0.6 * 0.92, deg(d, 62), 1); t += b * 0.6; } }

// ---------- frame drum: dum (low) and tek (slap) ----------
function dum(t0, vel) { const i0 = Math.floor(t0 * SR); for (let j = 0; j < SR * 0.5; j++) { const i = i0 + j; if (i >= N) break; const u = j / SR, f = 70 * (1 + 0.6 * Math.exp(-u * 30)); const s = Math.sin(2 * Math.PI * f * u) * Math.exp(-u * 7) * vel * 0.4 * master(i / SR); add(i, s, s, 0.15); } }
function tek(t0, vel) { const i0 = Math.floor(t0 * SR); let hp = 0, prev = 0; for (let j = 0; j < SR * 0.12; j++) { const i = i0 + j; if (i >= N) break; const n = rnd() * 2 - 1; hp = 0.85 * (hp + n - prev); prev = n; const u = j / SR, s = (hp * 0.5 + Math.sin(2 * Math.PI * 420 * u) * 0.3) * Math.exp(-u * 45) * vel * 0.22 * master(i / SR); add(i, s * 0.9, s * 1.1, 0.2); } }
{
  const BEAT = 0.3, PAT = { 0: "D", 2: "T", 3: "T", 4: "D", 6: "T" };
  for (let t = 9; t < 262; t += BEAT) {
    const o = drumOn(t); if (o <= 0.05) continue;
    const k = Math.round(t / BEAT) % 8, h = PAT[k];
    if (!h) { if (I(t) > 0.8 && rnd() < 0.35) tek(t, 0.4 * o); continue; }
    if (h === "D") dum(t, (0.7 + 0.3 * (k === 0)) * o); else tek(t, 0.7 * o);
  }
}

// ---------- timpani + gong swells on the events ----------
function timp(t0, vel, f0 = 73.4) {
  const i0 = Math.floor(t0 * SR); let lp = 0;
  for (let j = 0; j < SR * 2.2; j++) {
    const i = i0 + j; if (i >= N) break;
    const u = j / SR, f = f0 * (1 + 0.25 * Math.exp(-u * 18));
    lp += 0.08 * ((rnd() * 2 - 1) - lp);
    const s = (Math.sin(2 * Math.PI * f * u) * Math.exp(-u * 2.6) * 0.32 + Math.sin(2 * Math.PI * f * 1.5 * u) * Math.exp(-u * 4) * 0.08 + lp * 0.5 * Math.exp(-u * 30)) * vel * master(i / SR);
    add(i, s, s, 0.3);
  }
}
function gong(t0, vel) {
  const i0 = Math.floor(t0 * SR), parts = [[1, 1, 6], [1.48, 0.6, 4.5], [2.12, 0.5, 3.5], [2.77, 0.35, 2.8], [3.4, 0.25, 2.2], [4.9, 0.12, 1.5]], f0 = 82;
  for (let j = 0; j < SR * 7; j++) {
    const i = i0 + j; if (i >= N) break;
    const u = j / SR, sw = Math.min(1, u / 0.6); let s = 0;
    for (const [r, a, d] of parts) s += a * Math.sin(2 * Math.PI * f0 * r * u * (1 + 0.002 * Math.sin(u * 3))) * Math.exp(-u / d);
    s *= vel * 0.08 * sw * master(i / SR); add(i, s, s * 0.95, 0.8);
  }
}
for (const [t, v, f] of [[46.8, 0.5], [48.4, 1, 0], [50.4, 0.6], [52.4, 0.6], [96.6, 0.5], [98.2, 1], [99.6, 0.7], [101, 0.7], [102.4, 0.6], [136.4, 0.9], [138.2, 0.6], [214, 1], [216, 0.7], [218, 0.7], [253.6, 0.7], [255.2, 0.5]]) timp(t, v, f || 73.4);
for (let t = 135; t < 136.4; t += 0.09) timp(t, 0.1 + 0.35 * ramp(t, 135, 136.4));
for (const [t, v] of [[2, 0.6], [98, 1], [136.5, 0.9], [166.5, 0.8], [181, 0.8], [214, 0.9], [296, 0.9]]) gong(t, v);

// ---------- ambience: wind, fire crackle, the flood's rumble ----------
{
  let b = 0, w = 0, c1 = 0, c2 = 0, r1 = 0, r2 = 0;
  for (let i = 0; i < N; i++) {
    const t = i / SR, n = rnd() * 2 - 1;
    b = 0.995 * b + 0.02 * n; w += 0.02 * (b - w);
    const wind = w * (0.6 + 0.4 * Math.sin(t * 0.31) * Math.sin(t * 0.19 + 1)) * 0.6 * (1 - 0.5 * sec(t, 30, 250, 10) + 0.6 * ramp(t, 262, 300));
    const fire = Math.max(sec(t, 49.5, 54, 1.5), sec(t, 99.5, 104, 1.5));
    c1 += 0.25 * (n - c1); c2 += 0.25 * (c1 - c2);
    let s = wind + (c1 - c2) * 0.05 * fire;
    if (fire > 0 && rnd() < 0.0009 * fire) { const amp = 0.12 + rnd() * 0.22; for (let j = 0; j < 160; j++) add(i + j, (rnd() * 2 - 1) * amp * Math.exp(-j / 30) * fire, (rnd() * 2 - 1) * amp * Math.exp(-j / 30) * fire, 0.2); }
    const fl = sec(t, 104.5, 117, 2.5);
    r1 += 0.004 * (n - r1); r2 += 0.004 * (r1 - r2);
    s += r2 * 3.2 * fl + (c1 - c2) * 0.012 * fl;
    const g = master(t); add(i, s * g, s * g * 0.93, 0.12);
  }
}

// ---------- reverb (Freeverb-style) ----------
{
  const combs = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617].map((d) => Math.round(d * SR / 44100 * 1.6));
  const aps = [556, 441, 341, 225].map((d) => Math.round(d * SR / 44100));
  for (let ch = 0; ch < 2; ch++) {
    const inp = ch ? SRv : SL, out = new Float32Array(N), sp = ch * 23;
    for (const d0 of combs) { const d = d0 + sp, buf = new Float32Array(d); let p = 0, lp = 0; for (let i = 0; i < N; i++) { const y = buf[p]; lp = y * 0.6 + lp * 0.4; buf[p] = inp[i] * 0.03 + lp * 0.86; out[i] += y; p = (p + 1) % d; } }
    for (const d0 of aps) { const d = d0 + sp, buf = new Float32Array(d); let p = 0; for (let i = 0; i < N; i++) { const b = buf[p], y = -out[i] + b; buf[p] = out[i] + b * 0.5; out[i] = y; p = (p + 1) % d; } }
    const dst = ch ? R : L; for (let i = 0; i < N; i++) dst[i] += out[i] * 0.9;
  }
}

// ---------- write ----------
let peak = 0; for (let i = 0; i < N; i++) peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
const g = 0.89 / peak, buf = Buffer.alloc(44 + N * 4);
buf.write("RIFF", 0); buf.writeUInt32LE(36 + N * 4, 4); buf.write("WAVE", 8); buf.write("fmt ", 12); buf.writeUInt32LE(16, 16);
buf.writeUInt16LE(1, 20); buf.writeUInt16LE(2, 22); buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(SR * 4, 28); buf.writeUInt16LE(4, 32); buf.writeUInt16LE(16, 34);
buf.write("data", 36); buf.writeUInt32LE(N * 4, 40);
for (let i = 0; i < N; i++) { buf.writeInt16LE(Math.round(clamp(L[i] * g, -1, 1) * 32767), 44 + i * 4); buf.writeInt16LE(Math.round(clamp(R[i] * g, -1, 1) * 32767), 46 + i * 4); }
const wav = join(here, "assets/music.wav"), m4a = join(here, "assets/music.m4a");
writeFileSync(wav, buf);
const r = spawnSync("ffmpeg", ["-y", "-loglevel", "error", "-i", wav, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000", "-c:a", "aac", "-b:a", "256k", m4a], { stdio: "inherit" });
console.log(`peak ${peak.toFixed(3)} -> ${r.status === 0 ? "assets/music.m4a" : "ffmpeg failed"}`);
