// Sound effects for the timelapses, synthesised from the cues that shared/fx.js records ({t, kind, dur, gain}).
// Nothing is sampled: each kind is built from filtered noise, sines and envelopes, sample by sample, so the track is
// 100% code like the rest of the video. A city's music.mjs imports it and mixes the result under its score:
//
//   import { renderSfx } from "../../tools/sfx.mjs";
//   const fx = renderSfx(timeline.sfx, { SR, N, seed: 7 });   // -> { L, R, env } Float32Arrays (env = loudness, for ducking)
//
// Kinds: title fire boom smoke crowd cheer chant march battle clash cannon rumble waves splash storm wind firework engines
// oldcars planes heli bells toll drums construction train tram crash horn siren night.

export function renderSfx(cues, { SR = 48000, N, seed = 7 }) {
  const L = new Float32Array(N), R = new Float32Array(N), env = new Float32Array(N);
  let s0 = seed >>> 0;
  const rnd = () => ((s0 = (s0 * 1664525 + 1013904223) >>> 0) / 4294967296);
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const TAU = 2 * Math.PI;

  // a voice writes into the bus with a pan; `fadeIn/fadeOut` shape the cue as a whole
  function voice(t0, dur, gain, pan, fn, fade = 0.25) {
    const i0 = Math.max(0, Math.floor(t0 * SR)), i1 = Math.min(N, Math.floor((t0 + dur) * SR));
    const gl = gain * (1 - pan * 0.6), gr = gain * (1 + pan * 0.6);
    for (let i = i0; i < i1; i++) {
      const u = (i - i0) / SR, f = Math.min(1, u / fade, (dur - u) / fade);
      const s = fn(u, i) * Math.max(0, f);
      L[i] += s * gl; R[i] += s * gr; env[i] += Math.abs(s) * gain;
    }
  }
  // filters as small closures: lowpass, highpass, bandpass (state variable)
  const lp = (fc) => { let y = 0; const k = 1 - Math.exp(-TAU * fc / SR); return (x) => (y += k * (x - y)); };
  const hp = (fc) => { const l = lp(fc); return (x) => x - l(x); };
  const bp = (fc, q = 1) => { let lo = 0, ba = 0; const f = 2 * Math.sin(Math.PI * Math.min(fc, SR / 6) / SR); return (x) => { lo += f * ba; const hi = x - lo - ba / q; ba += f * hi; return ba; }; };
  const noise = () => rnd() * 2 - 1;

  // ---------- building blocks ----------
  const boom = (t0, g = 1, f0 = 55, len = 2.6) => { const n = lp(400), n2 = lp(90);
    voice(t0, len, g, (rnd() - 0.5) * 0.4, (u) => Math.sin(TAU * f0 * u * (1 + 0.8 * Math.exp(-u * 9))) * Math.exp(-u * 2.2) * 0.9 + n(noise()) * Math.exp(-u * 6) * 1.6 + n2(noise()) * Math.exp(-u * 1.2) * 2.5, 0.01); };
  const clang = (t0, g = 0.5) => { const fs = [1, 2.76, 5.4, 8.93].map((r) => r * (420 + rnd() * 500)), ph = rnd() * 6;
    voice(t0, 0.9, g, (rnd() - 0.5) * 1.2, (u) => fs.reduce((s, f, k) => s + Math.sin(TAU * f * u + ph * k) * Math.exp(-u * (5 + k * 4)) / (k + 1), 0) * 0.5, 0.003); };
  const bell = (t0, f0, g = 0.5, len = 5) => { const P = [[0.5, 0.6, 1.4], [1, 1, 0.9], [1.19, 0.6, 0.8], [1.5, 0.4, 0.6], [2, 0.35, 0.45], [2.51, 0.2, 0.35], [3, 0.12, 0.3]];
    voice(t0, len, g, (rnd() - 0.5) * 0.8, (u) => P.reduce((s, [r, a, d]) => s + a * Math.sin(TAU * f0 * r * u) * Math.exp(-u / (d * len * 0.5)), 0) * 0.35, 0.003); };
  const crackle = (t0, dur, rate, g) => { for (let t = t0; t < t0 + dur; t += -Math.log(1 - rnd() * 0.999) / rate) { const h = hp(1800), a = 0.3 + rnd() * 0.7; voice(t, 0.04, g * a, (rnd() - 0.5) * 1.4, (u) => h(noise()) * Math.exp(-u * 160), 0.001); } };
  const crowdBed = (t0, dur, g, bright = 0) => {   // many voices: band-limited noise with slow syllabic swells
    const b1 = bp(520 + bright * 300, 0.8), b2 = bp(1300 + bright * 500, 1.2), l = lp(3), ph = rnd() * 9;
    voice(t0, dur, g, (rnd() - 0.5) * 0.3, (u) => { const n = noise(), m = 0.65 + 0.35 * Math.sin(u * 2.1 + ph) * Math.sin(u * 3.3) + 0.4 * l(noise()) * 8; return (b1(n) * 1.3 + b2(n) * 0.8) * m * 0.9; }, 0.8);
    for (let t = t0 + 0.2; t < t0 + dur - 0.3; t += 0.08 + rnd() * 0.25) {   // individual shouts: short formant sweeps
      const f0 = 160 + rnd() * 180, form = bp(700 + rnd() * 900, 3), len = 0.15 + rnd() * 0.3;
      voice(t, len, g * (0.15 + bright * 0.25) * rnd(), (rnd() - 0.5) * 1.6, (u) => form(Math.sign(Math.sin(TAU * f0 * u * (1 + u)))) * Math.sin(Math.PI * u / len), 0.02);
    }
  };
  const windBed = (t0, dur, g, fc = 500) => { const b = bp(fc, 0.6), l = lp(0.4); voice(t0, dur, g, 0, (u) => b(noise()) * (0.5 + 0.5 * Math.abs(l(noise()) * 30)) * 1.6, 1.5); };
  const whistleUp = (t0, g) => { const f0 = 900 + rnd() * 700; let p = 0; voice(t0, 0.7, g, (rnd() - 0.5) * 1.2, (u) => { p += f0 * (1 + u * 1.8) / SR; return Math.sin(TAU * p) * 0.25 * (1 - u / 0.7); }, 0.05); };

  // ---------- the kinds ----------
  const K = {
    title(t, d, g) { const b = bp(900, 0.7); let fc = 0; voice(t - 0.25, 1.1, g * 0.55, 0.15, (u) => { fc = 400 + 2600 * Math.sin(Math.PI * Math.min(1, u / 1.1)); return b(noise()) * Math.sin(Math.PI * u / 1.1) * 0.9; }, 0.05);
      for (const [f, a] of [[1318.5, 0.5], [1975.5, 0.3], [2637, 0.15]]) voice(t + 0.1, 2.4, g * a * 0.32, -0.1, (u) => Math.sin(TAU * f * u) * Math.exp(-u * 2.2), 0.004); },
    fire(t, d, g) { const l = lp(700), h = hp(200); voice(t, d, g * 0.8, 0.1, (u) => h(l(noise())) * (0.7 + 0.3 * Math.sin(u * 5.1) * Math.sin(u * 2.3)) * 1.2, 1); crackle(t, d, 26, g * 0.55); },
    boom(t, d, g) { boom(t, g); }, smoke(t, d, g) { boom(t, g * 0.8); },
    cannon(t, d, g) { boom(t, g * 0.9, 62, 2.2); },
    rumble(t, d, g) { const l = lp(60), l2 = lp(140); voice(t, d, g * 1.3, 0, (u) => (l(noise()) * 9 + l2(noise()) * 2.5) * (0.6 + 0.4 * Math.sin(u * 7)), 0.6); crackle(t + 0.3, d - 1, 14, g * 0.35); boom(t + 0.1, g * 0.6, 38, 3); },
    crowd(t, d, g) { crowdBed(t, d, g * 0.55); },
    cheer(t, d, g) { crowdBed(t, d, g * 0.8, 1); for (let k = 0; k < 4; k++) whistleUp(t + 0.3 + rnd() * (d - 1), g * 0.35); },
    chant(t, d, g) { crowdBed(t, d, g * 0.45, 0.4); for (let x = t + 0.5; x < t + d - 0.5; x += 0.95) { const b = bp(450, 1.5); voice(x, 0.45, g * 0.5, 0, (u) => b(noise()) * Math.sin(Math.PI * u / 0.45) * 1.4, 0.02); } },
    march(t, d, g) { for (let x = t; x < t + d; x += 0.52) { const l = lp(160), h = hp(900); voice(x, 0.18, g * 0.55, (rnd() - 0.5) * 0.4, (u) => (l(noise()) * 6 + h(noise()) * 0.3) * Math.exp(-u * 26), 0.002); }
      for (let x = t; x < t + d; x += 2.08) for (const o of [0, 0.13, 0.26]) { const h = hp(1500); voice(x + o, 0.12, g * 0.25, 0.2, (u) => h(noise()) * Math.exp(-u * 40), 0.001); } },
    battle(t, d, g) { crowdBed(t, d, g * 0.45, 0.6); for (let x = t + 0.3; x < t + d; x += 0.2 + rnd() * 0.5) clang(x, g * 0.25); for (let x = t + 1; x < t + d - 1; x += 1.5 + rnd() * 2) boom(x, g * 0.35, 70, 1.6); },
    clash(t, d, g) { for (let x = t; x < t + d; x += 0.15 + rnd() * 0.35) clang(x, g * 0.35); },
    waves(t, d, g) { const l = lp(500), l2 = lp(90); voice(t, d, g * 0.7, -0.1, (u) => { const sw = 0.5 + 0.5 * Math.sin(TAU * u / 6.5); return (l(noise()) * sw * sw * 1.6 + l2(noise()) * 2); }, 1.5); },
    splash(t, d, g) { for (let x = t; x < t + Math.max(0.5, d - 0.8); x += 0.25 + rnd() * 0.5) { const b = bp(1200 + rnd() * 1500, 0.7), l = lp(300); voice(x, 0.9, g * (0.4 + rnd() * 0.3), (rnd() - 0.5), (u) => (b(noise()) * 1.4 + l(noise()) * 1.5) * Math.exp(-u * 4.5), 0.01); } },
    storm(t, d, g) { windBed(t, d, g * 0.8, 380); const h = hp(3000); voice(t, d, g * 0.35, 0.2, (u) => h(noise()) * 0.8, 1.2); for (let x = t + 1.5; x < t + d - 1; x += 2.5 + rnd() * 2.5) boom(x, g * 0.5, 40, 3.5); K.waves(t, d, g); },
    wind(t, d, g) { windBed(t, d, g * 0.6, 520); },
    firework(t, d, g) { whistleUp(t - 0.65, g * 0.5); boom(t, g * 0.45, 90, 1.2); crackle(t + 0.15, 1.2, 60, g * 0.3); },
    engines(t, d, g) { // several cars passing: buzzy saws whose pitch and level rise and fall (Doppler)
      for (let k = 0; k < 9; k++) { const f0 = 150 + rnd() * 80, T = 1.4 + rnd() * 1.2, ph0 = rnd() * T, l = lp(1800); let p = 0;
        voice(t, d, g * 0.12, Math.sin(k), (u) => { const c = ((u + ph0) % T) / T - 0.5, dop = 1 + 0.18 * Math.tanh(-c * 6); p += f0 * dop / SR; p -= Math.floor(p); return l(2 * p - 1 + 0.4 * Math.sign(Math.sin(TAU * p * 2))) * Math.exp(-c * c * 14) * 1.3; }, 0.6); } },
    oldcars(t, d, g) { for (let k = 0; k < 5; k++) { const f0 = 24 + rnd() * 14, l = lp(700); voice(t + rnd() * 2, d - 2, g * 0.25, (rnd() - 0.5), (u) => l(Math.pow(Math.max(0, Math.sin(TAU * f0 * u)), 8) * 2 - 0.3 + noise() * 0.1), 0.8); }
      for (let x = t + 1; x < t + d - 1; x += 2 + rnd() * 3) { const f = 330 + rnd() * 60; voice(x, 0.45, g * 0.22, (rnd() - 0.5), (u) => (Math.sin(TAU * f * u) + 0.6 * Math.sin(TAU * f * 1.26 * u)) * 0.4, 0.02); } },
    planes(t, d, g) { const fs = [86, 87.3, 109, 110.8, 131]; const l = lp(900); const ph = fs.map(() => rnd());
      voice(t, d, g * 0.6, 0, (u) => { let s = 0; for (let k = 0; k < fs.length; k++) { ph[k] += fs[k] * (1 - 0.04 * u / d) / SR; ph[k] -= Math.floor(ph[k]); s += 2 * ph[k] - 1; } return l(s) * 0.35 * Math.sin(Math.PI * u / d); }, 1.5); },
    heli(t, d, g) { const l = lp(400), b = bp(90, 1); voice(t, d, g * 0.7, 0.2, (u) => (l(noise()) * 4 * Math.pow(Math.max(0, Math.sin(TAU * 11 * u)), 6) + b(noise()) * 0.6) * Math.sin(Math.PI * u / d), 1); },
    bells(t, d, g) { const P = [392, 523.25, 440, 587.3, 349.2]; let k = 0; for (let x = t; x < t + d; x += 0.75) bell(x, P[(k++ * 3) % P.length], g * 0.35, 4); },
    toll(t, d, g) { for (let x = t; x < t + d; x += 3.2) bell(x, 174.6, g * 0.6, 7); },
    drums(t, d, g) { for (let x = t; x < t + d; x += 0.13) { const acc = Math.round((x - t) / 0.13) % 4 === 0, h = hp(700); voice(x, 0.12, g * (acc ? 0.4 : 0.18), 0, (u) => (h(noise()) + Math.sin(TAU * 190 * u) * 0.4) * Math.exp(-u * 35), 0.001); } },
    construction(t, d, g) { for (let x = t + 0.2; x < t + d; x += 0.25 + rnd() * 0.55) { const f = 900 + rnd() * 900, h = hp(600); voice(x, 0.12, g * 0.3, (rnd() - 0.5) * 1.4, (u) => (h(noise()) * 0.6 + Math.sin(TAU * f * u) * 0.5) * Math.exp(-u * 45), 0.001); }
      const l = lp(200); voice(t, d, g * 0.3, 0, (u) => l(noise()) * 3, 1); },
    train(t, d, g) { for (let x = t; x < t + d; x += Math.max(0.16, 0.42 - (x - t) * 0.05)) { const b = bp(300, 0.8); voice(x, 0.22, g * 0.4, 0.3, (u) => b(noise()) * Math.exp(-u * 14) * 2, 0.003); }
      for (const o of [0.6, d - 1.8]) voice(t + o, 1.2, g * 0.25, 0.3, (u) => (Math.sin(TAU * 740 * u) + Math.sin(TAU * 932 * u) * 0.7 + noise() * 0.15) * 0.5, 0.05); },
    tram(t, d, g) { for (const o of [0.4, d - 1.4]) for (const k of [0, 0.22]) voice(t + o + k, 1.4, g * 0.3, 0.2, (u) => (Math.sin(TAU * 1560 * u) + Math.sin(TAU * 2350 * u) * 0.4) * Math.exp(-u * 4) * 0.6, 0.002);
      voice(t, d, g * 0.12, -0.1, (u) => Math.sin(TAU * 100 * u) * 0.5 + Math.sin(TAU * 200 * u) * 0.2, 1); for (let x = t; x < t + d; x += 0.9) { const h = hp(1200); voice(x, 0.05, g * 0.25, 0, (u) => h(noise()) * Math.exp(-u * 90), 0.001); } },
    crash(t, d, g) { boom(t, g * 0.6, 80, 1.4); for (let k = 0; k < 5; k++) clang(t + rnd() * 0.5, g * 0.5); K.splash(t + 0.3, 1.2, g * 0.6); },
    horn(t, d, g) { const l = lp(600); let p = 0; voice(t, Math.min(d, 2.6), g * 0.5, 0, (u) => { p += 98 / SR; p -= Math.floor(p); return l(2 * p - 1) * 1.4; }, 0.25); },
    siren(t, d, g) { let p = 0; voice(t, d, g * 0.12, 0.3, (u) => { p += (Math.floor(u / 0.5) % 2 ? 440 : 587) / SR; return Math.sin(TAU * p) + 0.3 * Math.sin(2 * TAU * p); }, 0.5); },
    night(t, d, g) { for (let k = 0; k < 6; k++) { const f = 4200 + rnd() * 900, r = 14 + rnd() * 8, ph = rnd() * 9; voice(t, d, g * 0.05, (rnd() - 0.5) * 1.6, (u) => Math.sin(TAU * f * u) * Math.pow(Math.max(0, Math.sin(TAU * r * u)), 4) * (Math.sin(u * 1.7 + ph) > 0 ? 1 : 0), 1); } windBed(t, d, g * 0.25, 300); },
  };

  for (const c of cues) { const f = K[c.kind]; if (f) f(c.t, Math.max(0.3, c.dur || 2), c.gain ?? 1); }
  // smooth the loudness envelope (for ducking the music under big effects)
  { let y = 0; const k = 1 - Math.exp(-1 / (0.25 * SR)); for (let i = 0; i < N; i++) env[i] = (y += k * (env[i] - y)); }
  return { L, R, env };
}
