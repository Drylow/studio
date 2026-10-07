// Adapted from HyperFrames registry camera-shake: deterministic sampler and rig profile.
// Applied to the 3D camera before palette conversion, keeping titles fixed.
        function csHash(i, seed) {
          var h = Math.imul(i | 0, 374761393) + Math.imul(seed | 0, 668265263);
          h = (h ^ (h >>> 13)) >>> 0;
          h = Math.imul(h, 1274126177) >>> 0;
          return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
        }
        function csNoise(x, seed) {
          var i = Math.floor(x);
          var f = x - i;
          var u = f * f * f * (f * (f * 6 - 15) + 10);
          return csHash(i, seed) * (1 - u) + csHash(i + 1, seed) * u;
        }

        /* One channel of one octave. `constant` picks the cosine form.
           Each channel gets its own seed AND its own time offset: sharing
           offsets correlates the axes and the shake collapses into a diagonal
           line, which is the classic tell of fake handheld. */
        function csChannel(amp, freq, t, seed, constant) {
          var u = freq * t + seed * 7.13;
          if (constant) return Math.cos(u * 2 * Math.PI) * amp * 0.5;
          return (csNoise(u, seed) - 0.5) * amp;
        }

        function csSample(profile, t, intensity, freqScale) {
          var rot = [0, 0, 0];
          var pos = [0, 0, 0];
          var o, a, ch;
          for (o = 0; o < profile.rot.length; o++) {
            for (a = 0; a < 3; a++) {
              ch = profile.rot[o][a];
              if (!ch) continue;
              rot[a] += csChannel(ch[0] * intensity, ch[1] * freqScale, t, o * 3 + a, 0);
            }
          }
          if (profile.pos) {
            for (o = 0; o < profile.pos.length; o++) {
              for (a = 0; a < 3; a++) {
                ch = profile.pos[o][a];
                if (!ch) continue;
                pos[a] += csChannel(ch[0] * intensity, ch[1] * freqScale, t, 32 + o * 3 + a, ch[2]);
              }
            }
          }
          return { pitch: rot[0], yaw: rot[1], roll: rot[2], px: pos[0], py: pos[1], pz: pos[2] };
        }

const profile={rot:[[[.09,5.83],[.059,1.8],[.017,2.38]],[[.14,9.17],[.041,11.35],[.009,10.52]],[[.15,57.17],[.048,54.17],[.016,63.76]]],pos:[[[.011,3.2,1],[.059,1.9,1],[.021,3.33,1]],[[.009,7.7,1],[.04,9.1,0],[.009,9.22,1]],[[.002,51.51,1],[.05,55.54,1],[.017,58.55,1]]]};
export function impactMotion(t,intensity){return csSample(profile,t,intensity,1);}
