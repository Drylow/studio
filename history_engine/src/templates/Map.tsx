import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, useCurrentFrame} from 'remotion';
import parchment from '../assets/parchment.jpg';
import {clamp, outFade, ramp} from '../components/common';
import type {MapSeg} from '../schema';
import {C, F} from '../theme';

type P = [number, number];

/** Courbe lisse (Catmull-Rom → Bézier) passant par les points, + échantillons pour mesurer / suivre la tête. */
const smooth = (pts: P[]) => {
  if (pts.length < 2) return {d: '', samples: pts};
  let d = `M ${pts[0][0]} ${pts[0][1]}`;
  const samples: P[] = [pts[0]];
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const c1: P = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2: P = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += ` C ${c1[0]} ${c1[1]} ${c2[0]} ${c2[1]} ${p2[0]} ${p2[1]}`;
    for (let k = 1; k <= 24; k++) {
      const t = k / 24;
      const u = 1 - t;
      samples.push([
        u * u * u * p1[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t * t * t * p2[0],
        u * u * u * p1[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t * t * t * p2[1],
      ]);
    }
  }
  return {d, samples};
};

const lengthOf = (s: P[]) => s.slice(1).reduce((acc, p, i) => acc + Math.hypot(p[0] - s[i][0], p[1] - s[i][1]), 0);

const pointAt = (s: P[], dist: number): {p: P; a: number} => {
  let acc = 0;
  for (let i = 1; i < s.length; i++) {
    const seg = Math.hypot(s[i][0] - s[i - 1][0], s[i][1] - s[i - 1][1]);
    if (acc + seg >= dist) {
      const t = seg ? (dist - acc) / seg : 0;
      return {
        p: [s[i - 1][0] + (s[i][0] - s[i - 1][0]) * t, s[i - 1][1] + (s[i][1] - s[i - 1][1]) * t],
        a: Math.atan2(s[i][1] - s[i - 1][1], s[i][0] - s[i - 1][0]),
      };
    }
    acc += seg;
  }
  const n = s.length;
  return {p: s[n - 1], a: Math.atan2(s[n - 1][1] - s[n - 2][1], s[n - 1][0] - s[n - 2][0])};
};

const SWORDS = 'M -22 -22 L 22 22 M 22 -22 L -22 22 M -27 -13 L -13 -27 M 13 -27 L 27 -13';

/**
 * Carte de mouvements : vraie géographie (côtes, fleuves) à l'encre sur parchemin, villes, flèches d'armées
 * tracées de A vers B avec leur tête, marqueur de bataille (épées croisées) et lent zoom vers l'action.
 */
export const MapCard: React.FC<MapSeg & {dur: number}> = ({title, subtitle, land, rivers, places, moves, battle, focus, dur}) => {
  const frame = useCurrentFrame();
  const paper = C.paper;
  const sea = paper ? 'rgba(120,140,140,0.30)' : '#121619';
  const landFill = paper ? 'rgba(236,222,192,0.92)' : '#2a251f';
  const ink = paper ? '#2a1f16' : '#cbb68a';
  const side = (s?: string) => (s === 'b' ? C.redBlock : s === 'neutral' ? C.gold : C.blue);
  const fx = focus ? focus[0] : 960;
  const fy = focus ? focus[1] : 540;
  const zoom = interpolate(frame, [0, dur], [1.0, 1.1], {...clamp, easing: Easing.inOut(Easing.quad)});

  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur, 8), background: paper ? C.bg : '#0d1012'}}>
      <AbsoluteFill style={{transform: `scale(${zoom})`, transformOrigin: `${(fx / 1920) * 100}% ${(fy / 1080) * 100}%`}}>
        {paper ? <Img src={parchment} style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}} /> : null}
        <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0}}>
          <defs>
            <pattern id="hatch" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(-20)">
              <line x1="0" y1="7" x2="14" y2="7" stroke={paper ? 'rgba(42,31,22,0.10)' : 'rgba(203,182,138,0.06)'} strokeWidth="1" />
            </pattern>
          </defs>
          <rect x={0} y={0} width={1920} height={1080} fill={sea} />
          <rect x={0} y={0} width={1920} height={1080} fill="url(#hatch)" />
          {/* trait de côte doublé (halo clair + encre), comme une carte gravée */}
          {land.map((d, i) => (
            <path key={`h${i}`} d={d} fill="none" stroke={paper ? 'rgba(90,120,130,0.35)' : 'rgba(203,182,138,0.12)'} strokeWidth={9} strokeLinejoin="round" />
          ))}
          {land.map((d, i) => (
            <path key={`l${i}`} d={d} fill={landFill} stroke={ink} strokeWidth={1.8} strokeLinejoin="round" />
          ))}
          {(rivers ?? []).map((d, i) => (
            <path key={`r${i}`} d={d} fill="none" stroke={paper ? 'rgba(52,86,120,0.65)' : 'rgba(120,150,180,0.5)'} strokeWidth={1.6} strokeLinecap="round" />
          ))}
          {moves.map((m, i) => {
            const {d, samples} = smooth(m.path as P[]);
            const L = lengthOf(samples) || 1;
            const p = interpolate(frame, [m.start * dur, m.end * dur], [0, 1], {...clamp, easing: Easing.inOut(Easing.cubic)});
            if (p <= 0) return null;
            const head = pointAt(samples, L * p);
            const col = side(m.side);
            const deg = (head.a * 180) / Math.PI;
            return (
              <g key={`m${i}`}>
                <path d={d} fill="none" stroke={paper ? 'rgba(42,31,22,0.85)' : 'rgba(0,0,0,0.8)'} strokeWidth={15} strokeLinecap="round" strokeDasharray={`${L} ${L}`} strokeDashoffset={L * (1 - p)} />
                <path d={d} fill="none" stroke={col} strokeWidth={9} strokeLinecap="round" strokeDasharray={`${L} ${L}`} strokeDashoffset={L * (1 - p)} />
                <g transform={`translate(${head.p[0]} ${head.p[1]}) rotate(${deg})`}>
                  <path d="M 26 0 L -14 -20 L -6 0 L -14 20 Z" fill={col} stroke={paper ? '#2a1f16' : '#000'} strokeWidth={3} strokeLinejoin="round" />
                </g>
              </g>
            );
          })}
          {battle ? (() => {
            const t = frame - battle.at * dur;
            if (t < 0) return null;
            const pop = interpolate(t, [0, 10], [0.4, 1], {...clamp, easing: Easing.out(Easing.back(2))});
            const ring = interpolate(t % 40, [0, 40], [0, 1], clamp);
            return (
              <g transform={`translate(${battle.x} ${battle.y})`}>
                <circle r={30 + 40 * ring} fill="none" stroke={C.red} strokeWidth={3} opacity={1 - ring} />
                <circle r={32} fill={paper ? 'rgba(244,234,210,0.9)' : 'rgba(20,16,12,0.85)'} stroke={C.red} strokeWidth={3} transform={`scale(${pop})`} />
                <path d={SWORDS} stroke={C.red} strokeWidth={5} strokeLinecap="round" transform={`scale(${pop * 0.62})`} />
              </g>
            );
          })() : null}
        </svg>
        {places.map((pl, i) => {
          const o = ramp(frame, pl.at !== undefined ? pl.at * dur : 6 + i * 3, 10);
          return (
            <div key={`p${i}`} style={{position: 'absolute', left: pl.x, top: pl.y, opacity: o}}>
              <div
                style={{
                  position: 'absolute',
                  left: -7,
                  top: -7,
                  width: 14,
                  height: 14,
                  borderRadius: 7,
                  background: pl.kind === 'battle' ? C.red : ink,
                  border: `2.5px solid ${paper ? '#f4ead2' : '#0d1012'}`,
                }}
              />
              <div
                style={{
                  position: 'absolute',
                  left: pl.dx ?? 16,
                  top: pl.dy ?? -16,
                  whiteSpace: 'nowrap',
                  fontFamily: pl.kind === 'battle' ? F.title : F.serif,
                  fontWeight: 700,
                  fontSize: pl.kind === 'battle' ? 30 : 27,
                  letterSpacing: '0.14em',
                  textTransform: 'uppercase',
                  color: pl.kind === 'battle' ? C.red : ink,
                  textShadow: paper ? '0 0 6px rgba(244,234,210,0.95), 0 0 2px rgba(244,234,210,1)' : '0 0 8px rgba(0,0,0,0.9)',
                }}
              >
                {pl.name}
              </div>
            </div>
          );
        })}
        {moves.map((m, i) =>
          m.label ? (
            <div
              key={`ml${i}`}
              style={{
                position: 'absolute',
                left: m.labelAt ? m.labelAt[0] : m.path[0][0],
                top: m.labelAt ? m.labelAt[1] : m.path[0][1] + 26,
                transform: 'translateX(-50%)',
                opacity: ramp(frame, m.start * dur + 6, 12),
                fontFamily: F.label,
                fontSize: 24,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: '#fff',
                background: side(m.side),
                padding: '3px 12px',
                border: `2px solid ${paper ? '#2a1f16' : '#000'}`,
                whiteSpace: 'nowrap',
              }}
            >
              {m.label}
            </div>
          ) : null,
        )}
      </AbsoluteFill>
      {/* cartouche titre (fixe, hors zoom) */}
      <div
        style={{
          position: 'absolute',
          left: 60,
          top: 56,
          padding: '18px 30px 16px',
          background: paper ? 'rgba(244,234,210,0.92)' : 'rgba(12,10,8,0.8)',
          border: `2px solid ${paper ? '#2a1f16' : C.goldDim}`,
          boxShadow: paper ? '4px 4px 0 rgba(42,31,22,0.25)' : '0 10px 30px rgba(0,0,0,0.5)',
          opacity: ramp(frame, 2, 12),
        }}
      >
        <div style={{fontFamily: F.title, fontWeight: 700, fontSize: 44, letterSpacing: '0.05em', color: C.cream, textTransform: 'uppercase'}}>{title}</div>
        {subtitle ? (
          <div style={{fontFamily: F.serif, fontWeight: 600, fontSize: 24, letterSpacing: '0.28em', color: C.gold, textTransform: 'uppercase', marginTop: 4}}>
            {subtitle}
          </div>
        ) : null}
      </div>
      {/* rose des vents */}
      <svg width={120} height={120} viewBox="-60 -60 120 120" style={{position: 'absolute', right: 70, top: 60, opacity: ramp(frame, 6, 14)}}>
        <circle r={42} fill="none" stroke={ink} strokeWidth={1.5} opacity={0.7} />
        <path d="M 0 -52 L 9 0 L 0 52 L -9 0 Z" fill={ink} opacity={0.85} />
        <path d="M -52 0 L 0 7 L 52 0 L 0 -7 Z" fill={ink} opacity={0.45} />
        <text x={0} y={-56} textAnchor="middle" fontFamily="Cinzel" fontSize={18} fill={ink}>
          N
        </text>
      </svg>
    </AbsoluteFill>
  );
};
