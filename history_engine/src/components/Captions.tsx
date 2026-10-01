import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import type {Caption} from '../schema';
import {F} from '../theme';

// Contour noir épais façon référence (texte blanc, majuscules, en bas au centre).
const OUTLINE = (() => {
  const out: string[] = [];
  for (let a = 0; a < 16; a++) {
    const t = (a / 16) * Math.PI * 2;
    out.push(`${(Math.cos(t) * 3.2).toFixed(2)}px ${(Math.sin(t) * 3.2).toFixed(2)}px 0 #000`);
  }
  out.push('0 3px 6px rgba(0,0,0,0.6)');
  return out.join(',');
})();

export const Captions: React.FC<{items: Caption[]; from?: number; mute?: [number, number][]}> = ({
  items,
  from = 0,
  mute = [],
}) => {
  const frame = useCurrentFrame();
  const {fps, height} = useVideoConfig();
  const t = frame / fps;
  if (t < from || mute.some(([a, b]) => t >= a && t < b)) return null;
  const cur = items.find((c) => t >= c.start && t < c.end);
  if (!cur) return null;
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: Math.round(height * 0.035),
        textAlign: 'center',
        fontFamily: F.caption,
        fontWeight: 800,
        fontSize: Math.round(height * 0.037),
        letterSpacing: 0.5,
        color: '#fff',
        textTransform: 'uppercase',
        textShadow: OUTLINE,
        padding: '0 12%',
      }}
    >
      {cur.text}
    </div>
  );
};
