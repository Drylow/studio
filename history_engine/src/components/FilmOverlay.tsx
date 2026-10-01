import React from 'react';
import {AbsoluteFill, Img, random, useCurrentFrame, useVideoConfig} from 'remotion';
import g0 from '../assets/grain_0.png';
import g1 from '../assets/grain_1.png';
import g2 from '../assets/grain_2.png';
import g3 from '../assets/grain_3.png';

const GRAINS = [g0, g1, g2, g3];

/**
 * Look « pellicule d'archive » posé sur toute la vidéo : grain animé, rayures verticales qui
 * vivent quelques frames, poussières / cheveux d'une frame, vignettage et léger scintillement.
 * Tout est déterministe (random(seed)) → un rendu identique d'une passe à l'autre.
 */
export const FilmOverlay: React.FC<{intensity?: number}> = ({intensity = 1}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  if (intensity <= 0) return null;

  // Grain : 4 textures qui tournent, décalées au hasard à chaque frame.
  const gx = Math.round(random(`gx${frame}`) * 40 - 20);
  const gy = Math.round(random(`gy${frame}`) * 40 - 20);

  // Rayures : 3 « pistes », chacune tire une rayure qui vit 6 à 22 frames.
  const scratches: React.ReactNode[] = [];
  for (let k = 0; k < 3; k++) {
    const life = 6 + k * 8;
    const slot = Math.floor((frame + k * 5) / life);
    const r = random(`sc${k}-${slot}`);
    if (r < 0.42) {
      const x = random(`sx${k}-${slot}`) * width;
      const jitter = (random(`sj${k}-${frame}`) - 0.5) * 3;
      const op = (0.12 + random(`so${k}-${slot}`) * 0.35) * intensity;
      const top = random(`st${k}-${slot}`) < 0.5 ? 0 : random(`su${k}-${slot}`) * height * 0.4;
      scratches.push(
        <div
          key={`s${k}`}
          style={{
            position: 'absolute',
            left: x + jitter,
            top,
            width: random(`sw${k}-${slot}`) < 0.7 ? 1.2 : 2,
            height: height - top,
            background: random(`sd${k}-${slot}`) < 0.75 ? 'rgba(235,230,220,1)' : 'rgba(10,8,6,1)',
            opacity: op,
          }}
        />,
      );
    }
  }

  // Poussières et cheveux : 0-3 par paire de frames.
  const dust: React.ReactNode[] = [];
  const dslot = Math.floor(frame / 2);
  const count = Math.floor(random(`dc${dslot}`) * 4);
  for (let i = 0; i < count; i++) {
    const x = random(`dx${dslot}-${i}`) * width;
    const y = random(`dy${dslot}-${i}`) * height;
    const hair = random(`dh${dslot}-${i}`) < 0.3;
    const light = random(`dl${dslot}-${i}`) < 0.7;
    const col = light ? 'rgba(240,236,228,0.75)' : 'rgba(0,0,0,0.7)';
    if (hair) {
      const a = random(`da${dslot}-${i}`) * 60 + 20;
      const b = random(`db${dslot}-${i}`) * 50 - 25;
      dust.push(
        <svg key={`d${i}`} style={{position: 'absolute', left: x, top: y, overflow: 'visible'}} width={1} height={1}>
          <path
            d={`M0 0 q ${b} ${a / 2} ${b / 3} ${a} t ${-b / 2} ${a / 2}`}
            stroke={col}
            strokeWidth={1.3}
            fill="none"
            opacity={0.8 * intensity}
          />
        </svg>,
      );
    } else {
      const s = 2 + random(`ds${dslot}-${i}`) * 5;
      dust.push(
        <div
          key={`d${i}`}
          style={{
            position: 'absolute',
            left: x,
            top: y,
            width: s,
            height: s * (0.6 + random(`dr${dslot}-${i}`)),
            borderRadius: '50%',
            background: col,
            opacity: intensity,
          }}
        />,
      );
    }
  }

  // scintillement très léger, dans les deux sens (jamais d'assombrissement global)
  const flicker = (random(`fl${frame}`) - 0.5) * 0.03 * intensity;

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <AbsoluteFill style={{overflow: 'hidden'}}>
        <Img
          src={GRAINS[frame % GRAINS.length]}
          style={{
            position: 'absolute',
            left: -30 + gx,
            top: -30 + gy,
            width: width + 60,
            height: height + 60,
            mixBlendMode: 'overlay',
            opacity: 0.16 * intensity,
          }}
        />
      </AbsoluteFill>
      {scratches}
      {dust}
      <AbsoluteFill
        style={{
          background: 'radial-gradient(ellipse 85% 80% at 50% 50%, rgba(0,0,0,0) 62%, rgba(0,0,0,0.26) 100%)',
          opacity: intensity,
        }}
      />
      <AbsoluteFill style={{background: flicker > 0 ? '#fff' : '#000', opacity: Math.abs(flicker)}} />
    </AbsoluteFill>
  );
};
