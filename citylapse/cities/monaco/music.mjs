// Monaco's own score, written sample by sample, with the sound effects of every event mixed underneath.
// It reads timeline.json (written by tools/stills.mjs from scene.js: duration, events, sound cues), so the music
// follows the story wherever the events fall. Four colours, one per era:
//   the Rock (1215-1641)      D Dorian: cello drone, lute plucks, a recorder, a frame drum on the sieges
//   the princes (1641-1861)   G major: harpsichord arpeggios over strings
//   Monte-Carlo (1861-1944)   a Belle Époque waltz in F: pizzicato bass, strings on 2 and 3, a celesta tune
//   modern Monaco (1944-2026) A major: strings, choir, a bright pluck ostinato and a soft pulse
// Dark moments (night, plague, gloom, sieges) thin the music; timpani and gong mark the big events.
//   node music.mjs  ->  assets/music.m4a (-14 LUFS)
import { writeFileSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { join, dirname } from "node:path";
import { renderSfx } from "../../tools/sfx.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const TL = JSON.parse(readFileSync(join(here, "timeline.json"), "utf8"));
const SR = 48000, DUR = Math.ceil(TL.DUR), N = DUR * SR;
const L = new Float32Array(N), R = new Float32Array(N), SL = new Float32Array(N), SRv = new Float32Array(N);
let seed = 1297;
const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const ramp = (t, a, b) => clamp((t - a) / (b - a));
const mtof = (m) => 440 * Math.pow(2, (m - 69) / 12);
const add = (i, l, r, send = 0.35) => { if (i < 0 || i >= N) return; L[i] += l; R[i] += r; SL[i] += l * send; SRv[i] += r * send; };
const master = (t) => ramp(t, 0, 3) * (1 - ramp(t, DUR - 6, DUR - 0.3));
const sec = (t, a, b, f = 2) => ramp(t, a - f, a + f) * (1 - ramp(t, b - f, b + f));

// ---------- the story, from the timeline ----------
const EV = TL.events, at = (title) => (EV.find((e) => e.title === title) || { t: 0 }).t;
const T_PRINCES = at("FRANCE TAKES OVER"), T_MC = at("THE SPÉLUGUES") - 2, T_MODERN = at("LIBERATED"), T_END = DUR - 34;
const SLOT = 10.5;
const DARK = new Set(["night", "plague", "mourning", "empty", "siege", "greatsiege", "retake", "occupation", "bombing", "expel"]);
const tab = (f) => { const a = new Float32Array(DUR * 100 + 2); for (let k = 0; k < a.length; k++) a[k] = f(k / 100); return (t) => { const x = clamp(t * 100, 0, a.length - 2), k = Math.floor(x); return a[k] + (a[k + 1] - a[k]) * (x - k); }; };
const darkAt = tab((t) => EV.reduce((m, e) => (DARK.has(e.fx) ? Math.max(m, sec(t, e.t + 0.8, e.t + SLOT - 0.5, 1.2)) : m), 0));
const era = (t) => (t < T_PRINCES ? 0 : t < T_MC ? 1 : t < T_MODERN ? 2 : 3);
const SC = [[0, 2, 3, 5, 7, 9, 10], [0, 2, 4, 5, 7, 9, 11], [0, 2, 4, 5, 7, 9, 10], [0, 2, 4, 5, 7, 9, 11]];
const ROOT = [50, 55, 53, 57];                 // D, G, F, A
const deg = (d, t, oct = 0) => { const e = era(t); return ROOT[e] + 12 * (oct + Math.floor(d / 7)) + SC[e][((d % 7) + 7) % 7]; };
const I = tab((t) => clamp(0.32 + 0.12 * ramp(t, 8, 60) + 0.1 * sec(t, T_PRINCES, T_MC, 4) + 0.22 * sec(t, T_MC, T_MODERN, 4) + 0.3 * ramp(t, T_MODERN, T_MODERN + 120) + 0.15 * ramp(t, T_END - 120, T_END) - 0.35 * darkAt(t), 0.15, 1));

// chords: 4 per era, each as degrees of the era's scale (6 s each, 3 bars of the waltz)
const PROG = [[[0, 2, 4], [6, 1, 3], [3, 5, 0], [0, 2, 4]], [[0, 2, 4], [3, 5, 0], [4, 6, 1], [0, 2, 4]], [[0, 2, 4], [5, 0, 2], [1, 3, 5], [4, 6, 1]], [[0, 2, 4], [5, 0, 2], [3, 5, 0], [4, 6, 1]]];
const chordAt = (t) => PROG[era(t)][Math.floor(t / 6) % 4].map((d) => deg(d, t, -1));

// ---------- drone: low saws on the root and fifth, darker in the dark moments ----------
{
  let l1 = 0, l2 = 0; const p = [0, 0, 0, 0];
  for (let i = 0; i < N; i += 1) {
    const t = i / SR, e = era(t), r = ROOT[e] - 24, fr = [mtof(r), mtof(r) * 1.003, mtof(r + 7), mtof(r + 7) * 0.998];
    let s = 0; for (let k = 0; k < 4; k++) { p[k] += fr[k] / SR; p[k] -= Math.floor(p[k]); s += 2 * p[k] - 1; }
    const fc = 220 + 420 * I(t), k1 = 1 - Math.exp(-2 * Math.PI * fc / SR);
    l1 += k1 * (s - l1); l2 += k1 * (l1 - l2);
    const g = 0.045 * master(t) * (0.5 + 0.5 * I(t) + 0.5 * darkAt(t)) * (1 - 0.6 * sec(t, T_MC, T_MODERN, 6));
    add(i, l2 * g, l2 * g * 0.95, 0.3);
  }
}

// ---------- strings pad on the chords ----------
{
  const pl = new Float32Array(N), pr = new Float32Array(N);
  for (let c0 = 0; c0 < DUR; c0 += 6) {
    for (const m of chordAt(c0 + 0.1).map((m) => m + 12)) for (let v = 0; v < 4; v++) {
      const f = mtof(m) * (1 + (v - 1.5) * 0.004), pan = (v - 1.5) / 2; let ph = rnd();
      const i0 = Math.max(0, Math.floor((c0 - 1.5) * SR)), i1 = Math.min(N, Math.floor((c0 + 8) * SR));
      for (let i = i0; i < i1; i++) {
        const t = i / SR, env = Math.min(ramp(t, c0 - 1.5, c0 + 0.8), 1 - ramp(t, c0 + 5.8, c0 + 8));
        ph += f / SR; ph -= Math.floor(ph);
        const s = (2 * ph - 1) * env * 0.014 * (0.5 + 0.6 * I(t));
        pl[i] += s * (1 - pan * 0.5); pr[i] += s * (1 + pan * 0.5);
      }
    }
  }
  let a1 = 0, a2 = 0, b1 = 0, b2 = 0;
  for (let i = 0; i < N; i++) { const t = i / SR, fc = 500 + 1900 * I(t), k = 1 - Math.exp(-2 * Math.PI * fc / SR); a1 += k * (pl[i] - a1); a2 += k * (a1 - a2); b1 += k * (pr[i] - b1); b2 += k * (b1 - b2); add(i, a2 * master(t), b2 * master(t), 0.55); }
}

// ---------- choir in the modern era and the finale ----------
{
  const W = [1, 0.5, 0.45, 0.22, 0.3, 0.12, 0.06], on = (t) => 0.6 * sec(t, T_MODERN + 60, T_END - 60, 6) + sec(t, T_END - 60, DUR, 4);
  for (let c0 = 0; c0 < DUR; c0 += 6) {
    if (on(c0) <= 0 && on(c0 + 6) <= 0) continue;
    for (const m0 of chordAt(c0 + 0.1)) {
      const f0 = mtof(m0 + 24), vph = rnd() * 6, i0 = Math.max(0, Math.floor((c0 - 1) * SR)), i1 = Math.min(N, Math.floor((c0 + 7.5) * SR));
      for (let i = i0; i < i1; i++) {
        const t = i / SR, o = on(t) * (1 - darkAt(t) * 0.7); if (o <= 0) continue;
        const env = Math.min(ramp(t, c0 - 1, c0 + 1), 1 - ramp(t, c0 + 6, c0 + 7.5)) * o * master(t); if (env <= 0) continue;
        const f = f0 * (1 + 0.005 * Math.sin(2 * Math.PI * 5.2 * t + vph));
        let s = 0; for (let h = 0; h < W.length; h++) s += W[h] * Math.sin(2 * Math.PI * f * (h + 1) * t);
        add(i, s * env * 0.008, s * env * 0.008, 0.85);
      }
    }
  }
}

// ---------- plucks: lute (era 0), harpsichord (1), pizzicato and harp (2), bright guitar (3) ----------
function pluck(t0, m, vel, pan = 0, decay = 0.993, bright = 0.4) {
  const f = mtof(m), n = Math.max(2, Math.round(SR / f)), buf = new Float32Array(n);
  for (let k = 0; k < n; k++) buf[k] = rnd() * 2 - 1;
  for (let q = 0; q < (bright < 0.3 ? 0 : 3); q++) for (let k = 0; k < n; k++) buf[k] = (buf[k] + buf[(k + 1) % n]) * 0.5;   // a softer attack, no click
  let p = 0; const i0 = Math.floor(t0 * SR), len = Math.floor(1.6 * SR);
  for (let j = 0; j < len; j++) {
    const i = i0 + j; if (i >= N) break;
    const cur = buf[p], nxt = buf[(p + 1) % n], v = (cur * (1 - bright) + nxt * bright) * decay;
    buf[p] = v; p = (p + 1) % n;
    const s = cur * vel * master(i / SR) * Math.min(1, j / 40);
    add(i, s * (1 - pan * 0.5), s * (1 + pan * 0.5), 0.3);
  }
}
{
  const PATS = [[0, 2, 4, 2, 5, 4, 2, 1], [0, 4, 7, 4, 9, 7, 4, 2], [0, 2, 4, 7, 4, 2, 4, 2], [3, 2, 0, 2, 4, 2, 1, 2]];
  for (let t = 6; t < T_END + 20; ) {
    const e = era(t), o = (1 - 0.7 * darkAt(t)) * master(t);
    if (e === 2) {                                   // waltz: bass on 1, chord on 2 and 3, 0.42 s a beat
      const B = 0.42, k = Math.round(t / B) % 3, ch = chordAt(t);
      if (k === 0) pluck(t, ch[0] - 12, 0.22 * o, -0.1, 0.99, 0.5);
      else for (const m of ch) pluck(t + rnd() * 0.01, m + 12, 0.07 * o, 0.3, 0.985, 0.5);
      t += B; continue;
    }
    const B = e === 0 ? 0.32 : e === 1 ? 0.24 : 0.26, bar = Math.floor(t / (B * 8)), k = Math.round(t / B) % 8;
    if (!(e === 0 && (k === 3 || k === 7) && rnd() < 0.5) && I(t) > 0.2) {
      const m = deg(PATS[(bar + e) % 4][k], t, 1);
      pluck(t + (rnd() - 0.5) * 0.008, m, (e === 1 ? 0.09 : 0.12) * o * (0.6 + 0.5 * I(t)), Math.sin(t * 0.7) * 0.5, e === 1 ? 0.985 : 0.993, e === 1 ? 0.15 : 0.4);
      if (e === 3 && k === 0) pluck(t, chordAt(t)[0], 0.1 * o, -0.2, 0.995);
    }
    t += B;
  }
}

// ---------- melodies: recorder (eras 0-1), celesta (2), strings lead (3) ----------
function lead(t0, dur, m, vel, kind) {
  const f = mtof(m), i0 = Math.floor(t0 * SR), i1 = Math.min(N, Math.floor((t0 + dur + (kind === 1 ? 1.6 : 0.8)) * SR));
  let ph = 0, nl = 0;
  for (let i = i0; i < i1; i++) {
    const t = i / SR, u = t - t0; let s;
    if (kind === 1) { s = (Math.sin(2 * Math.PI * f * u) + 0.25 * Math.sin(2 * Math.PI * f * 4 * u) * Math.exp(-u * 6)) * Math.exp(-u * 2.4) * Math.min(1, u / 0.004) * 0.05; }
    else {
      const env = Math.min(clamp(u / (kind === 2 ? 0.35 : 0.08)), 1 - ramp(u, dur, dur + 0.8));
      const ff = f * (1 + 0.006 * Math.sin(2 * Math.PI * 5.4 * u) * clamp((u - 0.3) / 0.6)); ph += ff / SR; nl += 0.15 * ((rnd() * 2 - 1) - nl);
      s = kind === 0 ? (Math.sin(2 * Math.PI * ph) * 0.8 + Math.sin(4 * Math.PI * ph) * 0.2 + nl * 0.2) * env * 0.04 : (2 * (ph - Math.floor(ph)) - 1) * env * 0.03;
    }
    s *= vel * master(t) * (1 - 0.6 * darkAt(t)); add(i, s, s * 1.05, kind === 1 ? 0.6 : 0.7);
  }
}
{
  const MOT = [[[4, 2], [5, 1], [4, 1], [2, 2], [0, 4]], [[0, 1], [2, 1], [4, 2], [7, 2], [5, 1], [4, 1], [2, 4]], [[7, 2], [5, 1], [4, 1], [5, 2], [4, 1], [2, 1], [0, 4]], [[2, 2], [4, 2], [5, 2], [7, 4], [4, 2], [2, 4]]];
  let k = 0;
  for (let t0 = 4; t0 < T_END + 10; ) {
    const e = era(t0), beat = e === 2 ? 0.42 : 0.6, kind = e === 2 ? 1 : e === 3 ? 2 : 0, mot = MOT[k++ % 4];
    if (darkAt(t0) < 0.5) { let t = t0; for (const [d, b] of mot) { lead(t, b * beat * 0.9, deg(d, t, 1 + (kind === 1 ? 1 : 0)), 1, kind); t += b * beat; } }
    t0 += mot.reduce((s, [, b]) => s + b, 0) * beat + (e === 2 ? 2.52 : 4.8);
  }
}

// ---------- percussion: frame drum on the sieges, a soft pulse in the modern era ----------
function dum(t0, vel) { const i0 = Math.floor(t0 * SR); for (let j = 0; j < SR * 0.5; j++) { const i = i0 + j; if (i >= N) break; const u = j / SR, f = 68 * (1 + 0.6 * Math.exp(-u * 30)); const s = Math.sin(2 * Math.PI * f * u) * Math.exp(-u * 7) * vel * 0.4 * master(i / SR); add(i, s, s, 0.15); } }
{
  const war = tab((t) => EV.reduce((m, e) => (["siege", "greatsiege", "retake", "return", "revolution", "occupation"].includes(e.fx) ? Math.max(m, sec(t, e.t, e.t + SLOT, 1)) : m), 0));
  for (let t = 4; t < DUR - 4; t += 0.3) { const w = war(t), k = Math.round(t / 0.3) % 4; if (w > 0.05 && (k === 0 || k === 3)) dum(t, (k === 0 ? 0.9 : 0.5) * w); }
  for (let t = T_MODERN + 20; t < T_END + 10; t += 0.52) { const o = ramp(t, T_MODERN + 20, T_MODERN + 80) * (1 - darkAt(t)) * (1 - ramp(t, T_END - 10, T_END + 10)); if (o > 0.05) dum(t, 0.35 * o * I(t)); }
}

// ---------- timpani + gong on the big events ----------
function timp(t0, vel, f0 = 73.4) {
  const i0 = Math.floor(t0 * SR); let lp = 0;
  for (let j = 0; j < SR * 2.2; j++) {
    const i = i0 + j; if (i >= N) break;
    const u = j / SR, f = f0 * (1 + 0.25 * Math.exp(-u * 18)); lp += 0.08 * ((rnd() * 2 - 1) - lp);
    add(i, (Math.sin(2 * Math.PI * f * u) * Math.exp(-u * 2.6) * 0.32 + lp * 0.5 * Math.exp(-u * 30)) * vel * master(i / SR), (Math.sin(2 * Math.PI * f * u) * Math.exp(-u * 2.6) * 0.32) * vel * master(i / SR), 0.3);
  }
}
function gong(t0, vel) {
  const i0 = Math.floor(t0 * SR), parts = [[1, 1, 6], [1.48, 0.6, 4.5], [2.12, 0.5, 3.5], [2.77, 0.35, 2.8], [3.4, 0.25, 2.2], [4.9, 0.12, 1.5]];
  for (let j = 0; j < SR * 7; j++) { const i = i0 + j; if (i >= N) break; const u = j / SR; let s = 0; for (const [r, a, d] of parts) s += a * Math.sin(2 * Math.PI * 82 * r * u) * Math.exp(-u / d); s *= vel * 0.08 * Math.min(1, u / 0.6) * master(i / SR); add(i, s, s * 0.95, 0.8); }
}
const BIG = { greatsiege: 1, siege: 0.8, retake: 0.7, revolution: 0.9, quake: 1, bombing: 1, liberation: 0.8, wedding: 0.6, reclaim: 0.5, storm: 0.8, gp: 0.5, pope: 0.6, wedding2011: 0.6, occupation: 0.8 };
for (const e of EV) { const v = BIG[e.fx]; if (!v) continue; for (const [o, k] of [[0, 1], [0.6, 0.6], [1.2, 0.5]]) timp(e.t + o, v * k); gong(e.t + 0.1, v * 0.8); }
for (const t of [T_PRINCES, T_MC, T_MODERN, T_END]) gong(t, 0.7);
gong(1, 0.5);

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

// ---------- the effects, under the music: the music ducks a little when an effect is loud ----------
let mpk = 0; for (let i = 0; i < N; i++) mpk = Math.max(mpk, Math.abs(L[i]), Math.abs(R[i]));
const fx = renderSfx(TL.sfx, { SR, N, seed: 1215 });
let fpk = 0; for (let i = 0; i < N; i++) fpk = Math.max(fpk, Math.abs(fx.L[i]), Math.abs(fx.R[i]));
let epk = 0; for (let i = 0; i < N; i++) epk = Math.max(epk, fx.env[i]);
const FXG = 0.55 * mpk / (fpk || 1);                 // effects peak a little under the music's peak
for (let i = 0; i < N; i++) { const d = 1 - 0.35 * clamp(fx.env[i] / (epk * 0.5)); L[i] = L[i] * d + fx.L[i] * FXG; R[i] = R[i] * d + fx.R[i] * FXG; }

// ---------- write ----------
let peak = 0; for (let i = 0; i < N; i++) peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
const g = 0.89 / peak, buf = Buffer.alloc(44 + N * 4);
buf.write("RIFF", 0); buf.writeUInt32LE(36 + N * 4, 4); buf.write("WAVE", 8); buf.write("fmt ", 12); buf.writeUInt32LE(16, 16);
buf.writeUInt16LE(1, 20); buf.writeUInt16LE(2, 22); buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(SR * 4, 28); buf.writeUInt16LE(4, 32); buf.writeUInt16LE(16, 34);
buf.write("data", 36); buf.writeUInt32LE(N * 4, 40);
for (let i = 0; i < N; i++) { buf.writeInt16LE(Math.round(clamp(L[i] * g, -1, 1) * 32767), 44 + i * 4); buf.writeInt16LE(Math.round(clamp(R[i] * g, -1, 1) * 32767), 46 + i * 4); }
const wav = join(here, "assets/music.wav"), m4a = join(here, "assets/music.m4a");
writeFileSync(wav, buf);
const ff = process.env.FFMPEG || "ffmpeg";
const r = spawnSync(ff, ["-y", "-loglevel", "error", "-i", wav, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000", "-c:a", "aac", "-b:a", "256k", m4a], { stdio: "inherit" });
console.log(`peak ${peak.toFixed(3)}, ${TL.sfx.length} effects -> ${r.status === 0 ? "assets/music.m4a" : "ffmpeg failed"}`);
