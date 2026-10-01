import React from 'react';
import {AbsoluteFill, Easing, useCurrentFrame} from 'remotion';
import {CardBg, outFade, ramp} from '../components/common';
import type {ChartSeg} from '../schema';
import {C, F, sideColor} from '../theme';

/* ───────────── Graphique en barres (effectifs, pertes, sources) ───────────── */
export const Chart: React.FC<ChartSeg & {dur: number}> = ({title, subtitle, bars, dur}) => {
  const frame = useCurrentFrame();
  const max = Math.max(...bars.map((b) => b.value), 1);
  const H = 470;
  const bw = Math.min(170, 900 / Math.max(1, bars.length));
  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur)}}>
      <CardBg tint="rgba(40,58,66,0.55)" />
      <div style={{position: 'absolute', top: 120, width: '100%', textAlign: 'center'}}>
        <div
          style={{
            fontFamily: F.title,
            fontSize: 54,
            letterSpacing: '0.08em',
            color: C.gold,
            textTransform: 'uppercase',
            opacity: ramp(frame, 2, 12),
          }}
        >
          {title}
        </div>
        {subtitle ? (
          <div
            style={{
              fontFamily: F.serif,
              fontSize: 28,
              letterSpacing: '0.28em',
              color: C.creamDim,
              textTransform: 'uppercase',
              marginTop: 8,
              opacity: ramp(frame, 8, 12),
            }}
          >
            {subtitle}
          </div>
        ) : null}
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 250,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-end',
          gap: 70,
        }}
      >
        {bars.map((b, i) => {
          const g = ramp(frame, 14 + i * 8, 34, Easing.out(Easing.cubic));
          const h = (b.value / max) * H * g;
          const shown = b.display && g >= 0.999 ? b.display : Math.round(b.value * g).toLocaleString('en-US');
          return (
            <div key={i} style={{display: 'flex', flexDirection: 'column', alignItems: 'center', width: bw}}>
              <div style={{fontFamily: F.label, fontSize: 36, color: C.cream, marginBottom: 12, opacity: g > 0.02 ? 1 : 0}}>
                {shown}
              </div>
              <div
                style={{
                  width: bw,
                  height: h,
                  background: `linear-gradient(180deg, ${sideColor(b.side)} 0%, ${sideColor(b.side)}cc 100%)`,
                  boxShadow: `0 0 24px ${sideColor(b.side)}66`,
                }}
              />
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', left: '18%', right: '18%', bottom: 248, height: 2, background: C.goldDim}} />
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 180, display: 'flex', justifyContent: 'center', gap: 70}}>
        {bars.map((b, i) => (
          <div
            key={i}
            style={{
              width: bw,
              textAlign: 'center',
              fontFamily: F.label,
              fontSize: 23,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: C.creamDim,
              opacity: ramp(frame, 18 + i * 8, 10),
            }}
          >
            {b.label}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
