import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame} from 'remotion';
import type {ImageSeg} from '../schema';
import {clamp} from './common';

/** Image fixe animée en « Ken Burns » : zoom / pan lent et linéaire, comme la référence. */
export const KenBurns: React.FC<{src: string; dur: number; motion?: ImageSeg['motion']; strength?: number}> = ({
  src,
  dur,
  motion = 'in',
  strength = 0.08,
}) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [0, Math.max(1, dur)], [0, 1], clamp);
  let scale = 1;
  let tx = 0;
  let ty = 0;
  const s = strength;
  switch (motion) {
    case 'out':
      scale = 1 + s * (1 - p);
      break;
    case 'left':
      scale = 1 + s;
      tx = interpolate(p, [0, 1], [s * 45, -s * 45]);
      break;
    case 'right':
      scale = 1 + s;
      tx = interpolate(p, [0, 1], [-s * 45, s * 45]);
      break;
    case 'up':
      scale = 1 + s;
      ty = interpolate(p, [0, 1], [s * 40, -s * 40]);
      break;
    case 'down':
      scale = 1 + s;
      ty = interpolate(p, [0, 1], [-s * 40, s * 40]);
      break;
    default:
      scale = 1 + s * p;
  }
  return (
    <AbsoluteFill style={{overflow: 'hidden', background: '#000'}}>
      <Img
        src={staticFile(src)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `translate(${tx}%, ${ty}%) scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};

export const VideoClip: React.FC<{src: string}> = ({src}) => (
  <AbsoluteFill style={{background: '#000'}}>
    <OffthreadVideo src={staticFile(src)} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
  </AbsoluteFill>
);
