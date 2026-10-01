import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {CardBg, Diamond, clamp, outFade, ramp} from '../components/common';
import type {ArmySide, CharacterSeg, CompareSeg} from '../schema';
import {C, F} from '../theme';

const Portrait: React.FC<{src: string; w: number; h: number; dur: number; border?: string}> = ({src, w, h, dur, border = C.goldDim}) => {
  const frame = useCurrentFrame();
  const z = interpolate(frame, [0, dur], [1.0, 1.07], clamp);
  return (
    <div style={{width: w, height: h, overflow: 'hidden', border: `1.5px solid ${border}`, boxShadow: '0 18px 50px rgba(0,0,0,0.65)', background: '#000'}}>
      <Img
        src={staticFile(src)}
        style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: '50% 20%', transformOrigin: '50% 25%', transform: `scale(${z})`}}
      />
    </div>
  );
};

const NameBlock: React.FC<{name: string; role?: string; facts?: string[]; dur: number; align?: 'left' | 'right'}> = ({
  name,
  role,
  facts,
  dur,
  align = 'left',
}) => {
  const frame = useCurrentFrame();
  const step = Math.max(18, Math.round(dur * 0.1));
  return (
    <div style={{textAlign: align}}>
      <div
        style={{
          fontFamily: F.title,
          fontSize: 84,
          color: C.cream,
          letterSpacing: '0.03em',
          lineHeight: 1.05,
          opacity: ramp(frame, 8, 14),
          transform: `translateY(${interpolate(ramp(frame, 8, 16), [0, 1], [18, 0])}px)`,
          textShadow: '0 2px 14px rgba(0,0,0,0.6)',
        }}
      >
        {name}
      </div>
      <div
        style={{
          height: 1.5,
          width: ramp(frame, 14, 20) * 300,
          background: C.gold,
          margin: align === 'right' ? '26px 0 20px auto' : '26px 0 20px',
        }}
      />
      {role ? (
        <div style={{fontFamily: F.serif, fontWeight: 600, fontSize: 30, letterSpacing: '0.3em', textTransform: 'uppercase', color: C.gold, opacity: ramp(frame, 16, 12)}}>
          {role}
        </div>
      ) : null}
      <div style={{marginTop: 40}}>
        {(facts ?? []).slice(0, 4).map((f, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              flexDirection: align === 'right' ? 'row-reverse' : 'row',
              alignItems: 'center',
              gap: 18,
              marginBottom: 16,
              fontFamily: F.serif,
              fontSize: 36,
              fontWeight: 500,
              color: 'rgba(236,227,207,0.82)',
              opacity: ramp(frame, 30 + i * step, 14),
              transform: `translateX(${interpolate(ramp(frame, 30 + i * step, 14), [0, 1], [align === 'right' ? 14 : -14, 0])}px)`,
            }}
          >
            <Diamond size={9} filled />
            {f}
          </div>
        ))}
      </div>
    </div>
  );
};

/* ───────────── Fiche personnage : portrait à droite, à gauche, ou plein cadre ───────────── */
export const Character: React.FC<CharacterSeg & {dur: number}> = ({name, role, image, facts, dur, variant = 'right'}) => {
  const frame = useCurrentFrame();
  const pIn = ramp(frame, 2, 16);
  if (variant === 'full') {
    const z = interpolate(frame, [0, dur], [1.04, 1.12], clamp);
    return (
      <AbsoluteFill style={{opacity: outFade(frame, dur)}}>
        <AbsoluteFill style={{left: '30%', overflow: 'hidden', background: '#000'}}>
          <Img src={staticFile(image)} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: '50% 18%', transformOrigin: '50% 25%', transform: `scale(${z})`}} />
        </AbsoluteFill>
        <AbsoluteFill style={{background: `linear-gradient(90deg, ${C.bg} 30%, rgba(28,25,20,0.7) 48%, rgba(28,25,20,0) 72%)`}} />
        <div style={{position: 'absolute', left: 170, bottom: 220, width: 880}}>
          <NameBlock name={name} role={role} facts={facts} dur={dur} />
        </div>
      </AbsoluteFill>
    );
  }
  const left = variant === 'left';
  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur)}}>
      <CardBg />
      <div
        style={{
          position: 'absolute',
          [left ? 'left' : 'right']: 170,
          top: 150,
          opacity: pIn,
          transform: `translateX(${interpolate(pIn, [0, 1], [left ? -50 : 50, 0])}px)`,
        }}
      >
        <Portrait src={image} w={620} h={780} dur={dur} />
      </div>
      <div style={{position: 'absolute', [left ? 'right' : 'left']: 190, top: 330, width: 820}}>
        <NameBlock name={name} role={role} facts={facts} dur={dur} align={left ? 'right' : 'left'} />
      </div>
    </AbsoluteFill>
  );
};

/* ───────────── Duo : portrait à gauche, portrait à droite (deux personnages ou deux camps) ───────────── */
const DuoSide: React.FC<{side: ArmySide; start: number; color: string; dur: number}> = ({side, start, color, dur}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', width: 700}}>
      {side.image ? (
        <div style={{opacity: ramp(frame, start, 14), transform: `translateY(${interpolate(ramp(frame, start, 16), [0, 1], [20, 0])}px)`}}>
          <Portrait src={side.image} w={400} h={480} dur={dur} border={color} />
        </div>
      ) : null}
      <div
        style={{
          marginTop: 30,
          fontFamily: F.title,
          fontSize: 46,
          letterSpacing: '0.08em',
          color: C.cream,
          textTransform: 'uppercase',
          textAlign: 'center',
          opacity: ramp(frame, start + 8, 12),
        }}
      >
        {side.title}
      </div>
      {side.subtitle ? (
        <div style={{fontFamily: F.serif, fontWeight: 600, fontSize: 24, letterSpacing: '0.28em', textTransform: 'uppercase', color: C.gold, marginTop: 6, opacity: ramp(frame, start + 12, 12)}}>
          {side.subtitle}
        </div>
      ) : null}
      <div style={{height: 2, width: 220 * ramp(frame, start + 12, 14), background: color, margin: '16px 0 18px'}} />
      <div style={{width: 560}}>
        {side.stats.slice(0, 3).map((s, i) => (
          <div
            key={i}
            style={{
              fontFamily: F.serif,
              fontSize: 31,
              fontWeight: 500,
              color: C.cream,
              textAlign: 'center',
              padding: '5px 0',
              opacity: ramp(frame, start + 26 + i * 16, 12),
            }}
          >
            {s}
          </div>
        ))}
      </div>
    </div>
  );
};

export const Compare: React.FC<CompareSeg & {dur: number}> = ({left, right, splitAt = 0.3, dur}) => {
  const frame = useCurrentFrame();
  const split = right ? ramp(frame, splitAt * dur, 20, Easing.inOut(Easing.cubic)) : 0;
  const rightStart = Math.round(splitAt * dur) + 8;
  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur)}}>
      <CardBg />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
        <div style={{transform: `translateX(${-470 * split}px)`}}>
          <DuoSide side={left} start={2} color={C.blue} dur={dur} />
        </div>
      </AbsoluteFill>
      {right ? (
        <>
          <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
            <div style={{transform: `translateX(${interpolate(split, [0, 1], [1150, 470])}px)`}}>
              <DuoSide side={right} start={rightStart} color={C.red} dur={dur} />
            </div>
          </AbsoluteFill>
          <div
            style={{
              position: 'absolute',
              left: '50%',
              top: 140,
              bottom: 140,
              width: 1.5,
              background: `linear-gradient(180deg, rgba(201,164,90,0), ${C.gold}, rgba(201,164,90,0))`,
              opacity: split,
            }}
          />
          <div
            style={{
              position: 'absolute',
              left: '50%',
              top: '42%',
              transform: 'translate(-50%, -50%) rotate(45deg)',
              width: 54,
              height: 54,
              border: `1.5px solid ${C.gold}`,
              background: C.bg,
              opacity: split,
            }}
          />
          <div
            style={{position: 'absolute', left: '50%', top: '42%', transform: 'translate(-50%, -50%)', fontFamily: F.title, fontSize: 20, color: C.gold, opacity: split}}
          >
            VS
          </div>
        </>
      ) : null}
    </AbsoluteFill>
  );
};
