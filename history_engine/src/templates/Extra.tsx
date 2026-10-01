import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {CardBg, Flash, clamp, outFade, ramp} from '../components/common';
import type {ArchiveSeg, NumberSeg} from '../schema';
import {C, F} from '../theme';

/* ───────────── Document / objet d'archive (vraie image de musée si trouvée) ───────────── */
export const Archive: React.FC<ArchiveSeg & {dur: number}> = ({title, image, note, credit, tilt = -0.6, dur}) => {
  const frame = useCurrentFrame();
  const inP = ramp(frame, 0, 16);
  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur)}}>
      <CardBg brackets={false} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
        <div style={{opacity: inP, transform: `translateY(${interpolate(inP, [0, 1], [24, 0])}px) rotate(${tilt}deg)`}}>
          <div style={{fontFamily: F.label, fontSize: 26, letterSpacing: '0.12em', textTransform: 'uppercase', color: C.cream, marginBottom: 12}}>
            {title}
          </div>
          <div style={{padding: 12, background: '#e7dfcc', boxShadow: '0 24px 60px rgba(0,0,0,0.7)'}}>
            <div style={{width: 1180, height: 664, overflow: 'hidden', background: '#111'}}>
              <Img
                src={staticFile(image)}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain',
                  background: 'radial-gradient(ellipse at center, #3a352d 0%, #16130f 100%)',
                  transform: `scale(${interpolate(frame, [0, dur], [1.0, 1.06], clamp)})`,
                }}
              />
            </div>
          </div>
          <div style={{display: 'flex', justifyContent: 'space-between', marginTop: 12, gap: 30}}>
            <div style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 26, color: C.creamDim, opacity: ramp(frame, 18, 12)}}>{note}</div>
            {credit ? (
              <div style={{fontFamily: F.label, fontSize: 17, letterSpacing: '0.06em', color: 'rgba(236,227,207,0.45)', opacity: ramp(frame, 22, 12)}}>
                {credit}
              </div>
            ) : null}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* ───────────── Grand chiffre qui défile (47 000 hommes, 3 heures…) ───────────── */
export const BigNumber: React.FC<NumberSeg & {dur: number}> = ({value, prefix = '', suffix = '', label, sub, reveal = 0, dur}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const r = Math.max(0, Math.min(dur - 60, Math.round(reveal * fps)));
  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur)}}>
      <CardBg />
      <Sequence from={r}>
        <NumberInner value={value} prefix={prefix} suffix={suffix} label={label} sub={sub} />
      </Sequence>
    </AbsoluteFill>
  );
};

const NumberInner: React.FC<{value: number; prefix: string; suffix: string; label: string; sub?: string}> = ({value, prefix, suffix, label, sub}) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [2, 46], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  const shown = Math.round(value * p).toLocaleString('en-US');
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
      <div style={{textAlign: 'center'}}>
        <div
          style={{
            fontFamily: F.title,
            fontWeight: 700,
            fontSize: 190,
            lineHeight: 1,
            color: C.cream,
            letterSpacing: '0.02em',
            textShadow: '0 4px 30px rgba(0,0,0,0.6)',
            transform: `scale(${interpolate(frame, [0, 60, 400], [0.96, 1, 1.04], clamp)})`,
          }}
        >
          <span style={{color: C.gold}}>{prefix}</span>
          {shown}
          <span style={{color: C.gold}}>{suffix}</span>
        </div>
        <div style={{height: 2, width: ramp(frame, 20, 24) * 420, background: C.gold, margin: '26px auto 22px'}} />
        <div style={{fontFamily: F.serif, fontWeight: 600, fontSize: 40, letterSpacing: '0.3em', textTransform: 'uppercase', color: C.cream, opacity: ramp(frame, 26, 14)}}>
          {label}
        </div>
        {sub ? (
          <div style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: 28, color: C.creamDim, marginTop: 12, opacity: ramp(frame, 40, 14)}}>{sub}</div>
        ) : null}
      </div>
      <Flash frames={2} />
    </AbsoluteFill>
  );
};
