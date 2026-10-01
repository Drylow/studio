import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {clamp, outFade, ramp} from '../components/common';
import type {BattleSeg, Unit} from '../schema';
import {C, F, sideColor, sideText} from '../theme';

/** Symbole d'unité façon carte militaire (X = infanterie, / = cavalerie…). */
const Symbol: React.FC<{kind?: Unit['kind']; w: number; h: number}> = ({kind = 'infantry', w, h}) => {
  const st = {stroke: '#fff', strokeWidth: 2, fill: 'none', opacity: 0.92};
  const p = 6;
  switch (kind) {
    case 'cavalry':
      return <line x1={p} y1={h - p} x2={w - p} y2={p} {...st} />;
    case 'archers':
      return <path d={`M ${w * 0.38} ${p} Q ${w * 0.66} ${h / 2} ${w * 0.38} ${h - p}`} {...st} />;
    case 'chariots':
      return (
        <g {...st}>
          <circle cx={w * 0.34} cy={h / 2} r={h * 0.22} />
          <circle cx={w * 0.66} cy={h / 2} r={h * 0.22} />
        </g>
      );
    case 'elephants':
      return <path d={`M ${w * 0.3} ${h - p} L ${w * 0.3} ${h * 0.4} Q ${w / 2} ${p} ${w * 0.7} ${h * 0.4} L ${w * 0.7} ${h - p}`} {...st} />;
    case 'command':
      return <path d={`M ${w / 2} ${p} L ${w - p * 1.6} ${h / 2} L ${w / 2} ${h - p} L ${p * 1.6} ${h / 2} Z`} {...st} />;
    default:
      return (
        <g {...st}>
          <line x1={p} y1={p} x2={w - p} y2={h - p} />
          <line x1={p} y1={h - p} x2={w - p} y2={p} />
        </g>
      );
  }
};

/** Schéma de bataille : terrain topo gris, blocs d'unités qui manœuvrent, étiquettes,
 * ligne de front dorée graduée, titre serif + date en bas à gauche. Coordonnées en %. */
export const Battle: React.FC<BattleSeg & {dur: number}> = ({title, subtitle, terrain, units, labels, line, dur}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const X = (v: number) => (v / 100) * width;
  const Y = (v: number) => (v / 100) * height;
  const cam = interpolate(frame, [0, dur], [1.0, 1.06], clamp);
  const bgIn = ramp(frame, 0, 8);

  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur, 6) * bgIn, background: '#4a4741'}}>
      <AbsoluteFill style={{transform: `scale(${cam})`}}>
        {terrain ? (
          <Img
            src={staticFile(terrain)}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              filter: 'grayscale(0.85) sepia(0.18) brightness(0.72) contrast(1.08)',
            }}
          />
        ) : (
          <AbsoluteFill style={{background: 'radial-gradient(ellipse at 40% 40%, #6b665c 0%, #45423c 70%)'}} />
        )}
        {/* quadrillage discret */}
        <AbsoluteFill
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)',
            backgroundSize: '48px 48px',
          }}
        />
        <svg width={width} height={height} style={{position: 'absolute', inset: 0}}>
          {line ? (
            <g opacity={ramp(frame, 6, 14)}>
              <line x1={X(line.x1)} y1={Y(line.y)} x2={X(line.x2)} y2={Y(line.y)} stroke={C.gold} strokeWidth={2} />
              {Array.from({length: 15}).map((_, i) => {
                const x = X(line.x1 + ((line.x2 - line.x1) * i) / 14);
                return <line key={i} x1={x} y1={Y(line.y) - 6} x2={x} y2={Y(line.y) + 6} stroke={C.gold} strokeWidth={1.5} />;
              })}
            </g>
          ) : null}
          {units.map((u, i) => {
            if (!u.to || !u.trail) return null;
            const [m0, m1] = u.move ?? [0.25, 0.75];
            const p = interpolate(frame, [m0 * dur, m1 * dur], [0, 1], {...clamp, easing: Easing.inOut(Easing.cubic)});
            if (p <= 0) return null;
            const cx = X(u.x + (u.to[0] - u.x) * p);
            const cy = Y(u.y + (u.to[1] - u.y) * p);
            return (
              <line
                key={`t${i}`}
                x1={X(u.x)}
                y1={Y(u.y)}
                x2={cx}
                y2={cy}
                stroke={sideColor(u.side)}
                strokeWidth={3}
                strokeDasharray="10 7"
                opacity={0.75}
              />
            );
          })}
        </svg>
        {units.map((u, i) => {
          const w = u.w ?? 54;
          const h = u.h ?? 30;
          const [m0, m1] = u.move ?? [0.25, 0.75];
          const p = u.to
            ? interpolate(frame, [m0 * dur, m1 * dur], [0, 1], {...clamp, easing: Easing.inOut(Easing.cubic)})
            : 0;
          const x = u.to ? u.x + (u.to[0] - u.x) * p : u.x;
          const y = u.to ? u.y + (u.to[1] - u.y) * p : u.y;
          const pop = ramp(frame, 10 + i * 3, 8, Easing.out(Easing.back(1.6)));
          const col = sideColor(u.side);
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: X(x) - w / 2,
                top: Y(y) - h / 2,
                width: w,
                height: h,
                background: col,
                border: '1.5px solid rgba(255,255,255,0.55)',
                boxShadow: `0 0 18px ${col}aa, 0 3px 8px rgba(0,0,0,0.5)`,
                opacity: pop,
                transform: `scale(${0.6 + 0.4 * pop})`,
              }}
            >
              <svg width={w} height={h} style={{position: 'absolute', inset: 0}}>
                <Symbol kind={u.kind} w={w} h={h} />
              </svg>
            </div>
          );
        })}
        {units
          .filter((u) => u.label)
          .map((u, i) => {
            const [m0, m1] = u.move ?? [0.25, 0.75];
            const p = u.to ? interpolate(frame, [m0 * dur, m1 * dur], [0, 1], {...clamp, easing: Easing.inOut(Easing.cubic)}) : 0;
            const x = u.to ? u.x + (u.to[0] - u.x) * p : u.x;
            const y = u.to ? u.y + (u.to[1] - u.y) * p : u.y;
            return (
              <div
                key={`l${i}`}
                style={{
                  position: 'absolute',
                  left: X(x),
                  top: Y(y) + (u.h ?? 30) / 2 + 8,
                  transform: 'translateX(-50%)',
                  opacity: ramp(frame, 22 + i * 3, 10),
                  ...labelStyle(u.side),
                }}
              >
                {u.label}
              </div>
            );
          })}
        {(labels ?? []).map((l, i) => (
          <div
            key={`z${i}`}
            style={{
              position: 'absolute',
              left: X(l.x),
              top: Y(l.y),
              transform: 'translate(-50%, -50%)',
              opacity: ramp(frame, 26 + i * 4, 10),
              ...labelStyle(l.side),
            }}
          >
            {l.text}
          </div>
        ))}
      </AbsoluteFill>
      {/* titre en bas à gauche */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          bottom: 60,
          padding: '26px 60px 22px 58px',
          background: 'linear-gradient(90deg, rgba(10,9,7,0.82) 0%, rgba(10,9,7,0.7) 70%, rgba(10,9,7,0) 100%)',
          opacity: ramp(frame, 4, 12),
          transform: `translateX(${interpolate(ramp(frame, 4, 14), [0, 1], [-30, 0])}px)`,
        }}
      >
        <div
          style={{
            fontFamily: F.title,
            fontWeight: 700,
            fontSize: 58,
            letterSpacing: '0.04em',
            color: C.cream,
            textTransform: 'uppercase',
            textShadow: '0 2px 10px rgba(0,0,0,0.7)',
          }}
        >
          {title}
        </div>
        {subtitle ? (
          <div
            style={{
              fontFamily: F.serif,
              fontWeight: 600,
              fontSize: 27,
              letterSpacing: '0.32em',
              color: C.gold,
              textTransform: 'uppercase',
              marginTop: 6,
            }}
          >
            {subtitle}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

const labelStyle = (side?: 'a' | 'b' | 'neutral'): React.CSSProperties => ({
  fontFamily: F.label,
  fontWeight: 600,
  fontSize: 19,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  color: side ? sideText(side) : C.creamDim,
  background: side ? 'rgba(14,16,22,0.72)' : 'rgba(0,0,0,0)',
  padding: side ? '3px 9px' : 0,
  whiteSpace: 'nowrap',
  border: side ? `1px solid ${sideColor(side)}55` : 'none',
});
