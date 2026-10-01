import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {Brackets, CardBg, Diamond, clamp, outFade, ramp} from '../components/common';
import type {RouteSeg} from '../schema';
import {C, F} from '../theme';

/** Carte d'itinéraire : une ligne dorée se trace de ville en ville sur un grand plan sombre,
 * la caméra suit la tête du tracé, chaque étape apparaît avec son losange et son nom. */
export const Route: React.FC<RouteSeg & {dur: number}> = ({title, subtitle, stops, dur}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  // plan virtuel 2x l'écran ; x, y des étapes en % de ce plan
  const PW = width * 1.6;
  const PH = height * 1.6;
  const pts = stops.map((s) => [(s.x / 100) * PW, (s.y / 100) * PH] as const);
  const lens = pts.slice(1).map((p, i) => Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]));
  const total = lens.reduce((a, b) => a + b, 0) || 1;
  const drawStart = 14;
  const drawEnd = Math.max(drawStart + 30, dur * 0.82);
  const prog = interpolate(frame, [drawStart, drawEnd], [0, 1], {...clamp, easing: Easing.inOut(Easing.quad)});
  let remaining = prog * total;
  let head: [number, number] = [pts[0][0], pts[0][1]];
  let reached = 0;
  for (let i = 0; i < lens.length; i++) {
    if (remaining >= lens[i]) {
      remaining -= lens[i];
      head = [pts[i + 1][0], pts[i + 1][1]];
      reached = i + 1;
    } else {
      const t = remaining / lens[i];
      head = [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t];
      break;
    }
  }
  const camX = Math.min(0, Math.max(width - PW, width * 0.5 - head[0]));
  const camY = Math.min(0, Math.max(height - PH, height * 0.52 - head[1]));
  const d = pts.map((p, i) => `${i ? 'L' : 'M'} ${p[0]} ${p[1]}`).join(' ');
  const cur = stops[reached];

  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur)}}>
      <CardBg brackets={false} tint="rgba(50,44,34,0.35)" />
      <AbsoluteFill style={{transform: `translate(${camX}px, ${camY}px)`, width: PW, height: PH}}>
        <svg width={PW} height={PH} style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
          <defs>
            <filter id="glow">
              <feGaussianBlur stdDeviation="4" result="b" />
              <feMerge>
                <feMergeNode in="b" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <path d={d} stroke="rgba(201,164,90,0.12)" strokeWidth={2} fill="none" strokeDasharray="4 10" />
          <path
            d={d}
            stroke="#d6a640"
            strokeWidth={3.2}
            fill="none"
            filter="url(#glow)"
            strokeDasharray={total}
            strokeDashoffset={total * (1 - prog)}
          />
        </svg>
        {stops.map((s, i) => {
          const on = i <= reached || i === 0;
          const o = on ? 1 : 0;
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: pts[i][0] - 7,
                top: pts[i][1] - 7,
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                opacity: o,
              }}
            >
              <Diamond size={14} color="#e6c47a" filled={i === reached} />
              <div style={{fontFamily: F.serif, fontWeight: 600, fontSize: 26, letterSpacing: '0.22em', color: C.cream, textTransform: 'uppercase'}}>
                {s.name}
              </div>
            </div>
          );
        })}
      </AbsoluteFill>
      <Brackets />
      <div style={{position: 'absolute', left: 64, top: 64, opacity: ramp(frame, 0, 12)}}>
        <div style={{fontFamily: F.title, fontSize: 50, letterSpacing: '0.07em', color: C.cream, textTransform: 'uppercase'}}>{title}</div>
        {subtitle ? (
          <div style={{fontFamily: F.serif, fontWeight: 600, fontSize: 22, letterSpacing: '0.3em', color: C.gold, textTransform: 'uppercase', marginTop: 4}}>
            {subtitle}
          </div>
        ) : null}
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 110,
          textAlign: 'center',
          fontFamily: F.serif,
          fontWeight: 600,
          fontSize: 30,
          letterSpacing: '0.34em',
          color: C.creamDim,
          textTransform: 'uppercase',
        }}
      >
        {cur?.name}
      </div>
      {cur?.coords ? (
        <div style={{position: 'absolute', left: 70, bottom: 70, fontFamily: F.serif, fontSize: 18, letterSpacing: '0.2em', color: 'rgba(236,227,207,0.35)'}}>
          {cur.coords}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
