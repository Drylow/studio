import React from 'react';
import {AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {CardBg, Flash, clamp, outFade, ramp} from '../components/common';
import {C, F} from '../theme';

/** Phrase choc : « THE STORY *HIDES* THE *TRUTH* » — serif en capitales, mots clés en rouge,
 * flash gris à l'entrée, trait doré qui se dessine sous la phrase, lent élargissement.
 * reveal (s) : la carte reste noire (poussière seule) jusqu'au mot prononcé, puis la phrase claque. */
export const Statement: React.FC<{text: string; dur: number; reveal?: number; kicker?: string}> = ({text, dur, reveal = 0, kicker}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const r = Math.max(0, Math.min(dur - 12, Math.round(reveal * fps)));
  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur, 5)}}>
      <CardBg />
      <Sequence from={r} durationInFrames={Math.max(1, dur - r)}>
        <StatementText text={text} dur={dur - r} kicker={kicker} />
      </Sequence>
    </AbsoluteFill>
  );
};

const StatementText: React.FC<{text: string; dur: number; kicker?: string}> = ({text, dur, kicker}) => {
  const frame = useCurrentFrame();
  const words = text.split(/\s+/).filter(Boolean);
  const inO = ramp(frame, 1, 9);
  const spacing = interpolate(frame, [0, dur], [0.03, 0.075], clamp);
  const scale = interpolate(frame, [0, dur], [1, 1.035], clamp);
  const line = ramp(frame, 8, 22);
  const size = words.join(' ').length > 26 ? 60 : 74;
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
        <div style={{transform: `scale(${scale})`, textAlign: 'center', maxWidth: 1400}}>
          {kicker ? (
            <div
              style={{
                fontFamily: F.serif,
                fontWeight: 600,
                fontSize: 28,
                letterSpacing: '0.34em',
                textTransform: 'uppercase',
                color: C.gold,
                marginBottom: 22,
                opacity: ramp(frame, 0, 10),
              }}
            >
              {kicker}
            </div>
          ) : null}
          <div
            style={{
              fontFamily: F.title,
              fontWeight: 400,
              fontSize: size,
              letterSpacing: `${spacing}em`,
              color: C.cream,
              opacity: inO,
              textTransform: 'uppercase',
              lineHeight: 1.15,
              textShadow: '0 2px 18px rgba(0,0,0,0.6)',
            }}
          >
            {words.map((w, i) => {
              const accent = /^\*.*\*[.,!?]?$/.test(w);
              const clean = w.replace(/\*/g, '');
              return (
                <span key={i} style={{color: accent ? C.red : C.cream}}>
                  {clean}
                  {i < words.length - 1 ? ' ' : ''}
                </span>
              );
            })}
          </div>
          <div
            style={{
              margin: '22px auto 0',
              height: 1.5,
              width: `${line * 62}%`,
              background: `linear-gradient(90deg, rgba(201,164,90,0), ${C.gold} 20%, ${C.gold} 80%, rgba(201,164,90,0))`,
            }}
          />
        </div>
      </AbsoluteFill>
      <Flash frames={2} />
    </AbsoluteFill>
  );
};
