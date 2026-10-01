import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, interpolateColors, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {CardBg, clamp, outFade, ramp} from '../components/common';
import type {QuoteSeg} from '../schema';
import {C, F} from '../theme';

/**
 * Citation plein écran : l'image (portrait ou scène) occupe tout le cadre avec un lent travelling,
 * un voile sombre à gauche porte la citation en italique. Chaque mot s'allume au moment exact où le
 * narrateur le prononce (words = secondes depuis le début du segment), passe par l'or puis se pose
 * en crème. Ensuite : filet doré, auteur en petites capitales, source en italique.
 */
export const Quote: React.FC<QuoteSeg & {dur: number}> = ({text, author, source, image, words: times, dur}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const words = text.replace(/^["“”«»\s]+|["“”«»\s]+$/g, '').split(/\s+/).filter(Boolean);
  // instants d'apparition (frames) : timings de la voix, sinon cadence régulière sur 60 % du plan
  const step = Math.max(3, Math.min(14, Math.floor((dur * 0.6) / Math.max(1, words.length))));
  const at = words.map((_, i) =>
    times && times.length === words.length && times[i] != null ? Math.round(times[i] * fps) : 12 + i * step,
  );
  const last = at.length ? at[at.length - 1] : 12;
  const size = words.length > 26 ? 54 : words.length > 16 ? 64 : 80;
  const push = interpolate(frame, [0, dur], [1.02, 1.1], clamp);
  const sweep = interpolate(frame, [0, dur], [-40, 130], clamp);

  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur, 8)}}>
      <CardBg brackets={false} />
      {image ? (
        // portrait à droite (visage bien visible), fondu vers la gauche où se pose la citation
        <AbsoluteFill style={{left: '42%', overflow: 'hidden'}}>
          <Img
            src={staticFile(image)}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              objectPosition: '50% 22%',
              transform: `scale(${push}) translateX(${interpolate(frame, [0, dur], [1, -1], clamp)}%)`,
              filter: 'brightness(0.86) saturate(0.92)',
            }}
          />
          <AbsoluteFill
            style={{
              background: `linear-gradient(90deg, ${C.bg} 0%, rgba(${C.bgRgb},0.55) 28%, rgba(${C.bgRgb},0) 58%, rgba(${C.bgRgb},0.2) 100%)`,
            }}
          />
        </AbsoluteFill>
      ) : null}
      {/* reflet doré qui traverse lentement le plan */}
      <AbsoluteFill
        style={{
          background: `linear-gradient(105deg, rgba(0,0,0,0) ${sweep - 18}%, rgba(214,170,90,0.07) ${sweep}%, rgba(0,0,0,0) ${sweep + 18}%)`,
          mixBlendMode: 'screen',
        }}
      />
      <div style={{position: 'absolute', left: 170, top: 0, bottom: 0, width: 1050, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
        <div
          style={{
            position: 'absolute',
            left: -70,
            top: '50%',
            transform: 'translateY(-78%)',
            fontFamily: F.title,
            fontSize: 380,
            lineHeight: 1,
            color: C.gold,
            opacity: 0.14 * ramp(frame, 0, 14),
          }}
        >
          “
        </div>
        <div style={{fontFamily: F.serif, fontStyle: 'italic', fontWeight: 500, fontSize: size, lineHeight: 1.22, color: C.cream}}>
          {words.map((w, i) => {
            const t = frame - at[i];
            const o = interpolate(t, [0, 7], [0.14, 1], clamp);
            const col = interpolateColors(Math.max(0, t), [0, 5, 22], [C.paper ? C.red : '#e6c47a', C.paper ? C.red : '#e6c47a', C.cream]);
            const blur = interpolate(t, [0, 7], [3, 0], clamp);
            const y = interpolate(t, [0, 8], [6, 0], {...clamp, easing: Easing.out(Easing.cubic)});
            return (
              <span
                key={i}
                style={{
                  display: 'inline-block',
                  marginRight: '0.26em',
                  opacity: o,
                  color: t < 0 ? C.cream : col,
                  filter: `blur(${blur}px)`,
                  transform: `translateY(${y}px)`,
                  textShadow: C.shadow,
                }}
              >
                {w}
              </span>
            );
          })}
        </div>
        <div style={{height: 1.5, width: 140 * ramp(frame, last + 10, 16), background: C.gold, margin: '38px 0 22px'}} />
        <div
          style={{
            fontFamily: F.title,
            fontSize: 30,
            letterSpacing: '0.24em',
            textTransform: 'uppercase',
            color: C.gold,
            opacity: ramp(frame, last + 16, 14),
          }}
        >
          {author}
        </div>
        {source ? (
          <div
            style={{
              fontFamily: F.serif,
              fontStyle: 'italic',
              fontSize: 27,
              color: C.creamDim,
              marginTop: 8,
              opacity: ramp(frame, last + 24, 14),
            }}
          >
            {source}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
