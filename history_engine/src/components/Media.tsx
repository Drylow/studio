import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame} from 'remotion';
import type {ImageSeg} from '../schema';
import {C, F} from '../theme';
import {clamp, ramp} from './common';

/**
 * Image fixe animée en « Ken Burns » : zoom / pan lent et linéaire, comme la référence.
 * Jamais de mouvement vertical (il finissait sur un buste sans tête) : les zooms sont ancrés sur le
 * haut du cadre (là où sont les visages), les pans sont horizontaux.
 */
export const KenBurns: React.FC<{src: string; dur: number; motion?: ImageSeg['motion']; strength?: number}> = ({
  src,
  dur,
  motion = 'in',
  strength = 0.08,
}) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [0, Math.max(1, dur)], [0, 1], clamp);
  const s = strength;
  let scale = 1 + s * p;
  let tx = 0;
  const m = motion === 'up' || motion === 'down' ? 'in' : motion;
  if (m === 'out') {
    scale = 1 + s * (1 - p);
  } else if (m === 'left' || m === 'right') {
    scale = 1 + s;
    const a = (s / (1 + s)) * 46; // reste dans l'image agrandie
    tx = m === 'left' ? interpolate(p, [0, 1], [a, -a]) : interpolate(p, [0, 1], [-a, a]);
  }
  return (
    <AbsoluteFill style={{overflow: 'hidden', background: '#000'}}>
      <Img
        src={staticFile(src)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          objectPosition: '50% 22%',
          transformOrigin: '50% 28%',
          transform: `translateX(${tx}%) scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};

/** Plan image + habillages éventuels : cartouche nom/rôle (bas gauche), tampon lieu · date (haut gauche). */
export const ImageShot: React.FC<{seg: ImageSeg; dur: number}> = ({seg, dur}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <KenBurns src={seg.src} dur={dur} motion={seg.motion} strength={seg.strength} />
      {seg.stamp ? <Stamp text={seg.stamp} frame={frame} dur={dur} /> : null}
      {seg.label ? <LowerThird name={seg.label.name} role={seg.label.role} frame={frame} dur={dur} /> : null}
    </AbsoluteFill>
  );
};

/** Tampon « HASTINGS, ENGLAND · 14 OCTOBER 1066 » tapé lettre à lettre, en haut à gauche. */
const Stamp: React.FC<{text: string; frame: number; dur: number}> = ({text, frame, dur}) => {
  const start = 10;
  const shown = Math.max(0, Math.min(text.length, Math.floor((frame - start) / 1.6)));
  const out = interpolate(frame, [Math.min(dur - 10, 5.5 * 30), Math.min(dur, 6 * 30)], [1, 0], clamp);
  if (frame < start) return null;
  return (
    <div style={{position: 'absolute', left: 60, top: 56, opacity: out, padding: '14px 26px 16px', background: 'linear-gradient(90deg, rgba(10,8,6,0.62), rgba(10,8,6,0.35) 75%, rgba(10,8,6,0))'}}>
      <div
        style={{
          fontFamily: F.serif,
          fontWeight: 600,
          fontSize: 30,
          letterSpacing: '0.28em',
          textTransform: 'uppercase',
          color: '#f1e8d4',
          textShadow: '0 2px 12px rgba(0,0,0,0.85)',
        }}
      >
        {text.slice(0, shown)}
        <span style={{opacity: frame % 20 < 10 && shown < text.length ? 1 : 0}}>▍</span>
      </div>
      <div style={{height: 1.5, width: `${ramp(frame, start + 4, 30) * 100}%`, background: '#d4ad62', marginTop: 10, opacity: 0.9}} />
    </div>
  );
};

/** Cartouche nom + rôle, glissé depuis la gauche, tient 5 s puis s'efface. */
const LowerThird: React.FC<{name: string; role?: string; frame: number; dur: number}> = ({name, role, frame, dur}) => {
  const start = 18;
  const inP = ramp(frame, start, 16);
  const outP = interpolate(frame, [Math.min(dur - 12, start + 6 * 30), Math.min(dur, start + 6.5 * 30)], [1, 0], clamp);
  return (
    <div
      style={{
        position: 'absolute',
        left: 84,
        bottom: 150,
        opacity: inP * outP,
        transform: `translateX(${interpolate(inP, [0, 1], [-24, 0])}px)`,
        display: 'flex',
        alignItems: 'stretch',
        gap: 18,
      }}
    >
      <div style={{width: 3, background: '#d4ad62', transform: `scaleY(${inP})`, transformOrigin: 'top'}} />
      <div style={{padding: '10px 60px 12px 18px', margin: '0 0 0 -18px', background: 'linear-gradient(90deg, rgba(10,8,6,0.72), rgba(10,8,6,0.5) 70%, rgba(10,8,6,0))'}}>
        <div style={{fontFamily: F.title, fontSize: 46, color: '#f1e8d4', letterSpacing: '0.04em', textShadow: '0 2px 12px rgba(0,0,0,0.8)'}}>
          {name}
        </div>
        {role ? (
          <div
            style={{
              fontFamily: F.serif,
              fontWeight: 600,
              fontSize: 24,
              letterSpacing: '0.26em',
              textTransform: 'uppercase',
              color: '#d4ad62',
              marginTop: 2,
              textShadow: '0 2px 10px rgba(0,0,0,0.8)',
            }}
          >
            {role}
          </div>
        ) : null}
      </div>
    </div>
  );
};

export const VideoClip: React.FC<{src: string}> = ({src}) => (
  <AbsoluteFill style={{background: '#000'}}>
    <OffthreadVideo src={staticFile(src)} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
  </AbsoluteFill>
);
