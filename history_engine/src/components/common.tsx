import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, useCurrentFrame} from 'remotion';
import parchment from '../assets/parchment.jpg';
import {C} from '../theme';

export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

/** 0 → 1 entre deux frames, avec easing doux. */
export const ramp = (frame: number, start: number, len: number, ease = Easing.out(Easing.cubic)) =>
  interpolate(frame, [start, start + Math.max(1, len)], [0, 1], {...clamp, easing: ease});

/** Opacité de sortie des cartes (fondu court sur les dernières frames). */
export const outFade = (frame: number, dur: number, len = 6) =>
  interpolate(frame, [dur - len, dur], [1, 0], clamp);

/** Fond des cartes animées : charbon chaud, halo central, coins en équerre. */
export const CardBg: React.FC<{children?: React.ReactNode; brackets?: boolean; tint?: string}> = ({
  children,
  brackets = true,
  tint,
}) => (
  <AbsoluteFill style={{background: C.bg}}>
    {C.paper ? (
      <Img src={parchment} style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover'}} />
    ) : (
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse 70% 60% at 50% 45%, ${tint ?? 'rgba(60,52,40,0.55)'} 0%, rgba(0,0,0,0) 70%)`,
        }}
      />
    )}
    {brackets ? <Brackets /> : null}
    {children}
  </AbsoluteFill>
);

export const Brackets: React.FC<{inset?: number; size?: number; color?: string}> = ({
  inset = 58,
  size = 26,
  color,
}) => {
  const s = {position: 'absolute' as const, width: size, height: size, borderColor: color ?? C.bracket, borderStyle: 'solid'};
  return (
    <AbsoluteFill>
      <div style={{...s, left: inset, top: inset, borderWidth: '1.5px 0 0 1.5px'}} />
      <div style={{...s, right: inset, top: inset, borderWidth: '1.5px 1.5px 0 0'}} />
      <div style={{...s, left: inset, bottom: inset, borderWidth: '0 0 1.5px 1.5px'}} />
      <div style={{...s, right: inset, bottom: inset, borderWidth: '0 1.5px 1.5px 0'}} />
    </AbsoluteFill>
  );
};

/** Flash gris d'entrée (2-3 frames) utilisé par les phrases chocs. */
export const Flash: React.FC<{frames?: number}> = ({frames = 3}) => {
  const frame = useCurrentFrame();
  if (frame > frames + 2) return null;
  const o = interpolate(frame, [0, frames, frames + 2], [1, 1, 0], clamp);
  return <AbsoluteFill style={{background: '#7c7a74', opacity: o, mixBlendMode: 'screen'}} />;
};

/** Petit losange doré (marqueurs, puces). */
export const Diamond: React.FC<{size?: number; color?: string; filled?: boolean; style?: React.CSSProperties}> = ({
  size = 10,
  color = C.gold,
  filled = false,
  style,
}) => (
  <div
    style={{
      width: size,
      height: size,
      transform: 'rotate(45deg)',
      border: `1.5px solid ${color}`,
      background: filled ? color : 'transparent',
      flexShrink: 0,
      ...style,
    }}
  />
);
