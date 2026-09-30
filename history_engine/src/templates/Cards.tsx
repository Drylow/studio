import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {CardBg, Diamond, clamp, outFade, ramp} from '../components/common';
import type {ArchiveSeg, ArmySide, ChartSeg, CharacterSeg, CompareSeg, QuoteSeg} from '../schema';
import {C, F, sideColor} from '../theme';

const Framed: React.FC<{src: string; w: number; h: number; dur: number; border?: string}> = ({
  src,
  w,
  h,
  dur,
  border = C.goldDim,
}) => {
  const frame = useCurrentFrame();
  const z = interpolate(frame, [0, dur], [1.0, 1.07], clamp);
  return (
    <div
      style={{
        width: w,
        height: h,
        overflow: 'hidden',
        border: `1.5px solid ${border}`,
        boxShadow: '0 18px 50px rgba(0,0,0,0.65)',
        background: '#000',
      }}
    >
      <Img src={staticFile(src)} style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${z})`}} />
    </div>
  );
};

/* ───────────── Fiche personnage (« King Darius III ») ───────────── */
export const Character: React.FC<CharacterSeg & {dur: number}> = ({name, role, image, facts, dur}) => {
  const frame = useCurrentFrame();
  const pIn = ramp(frame, 2, 16);
  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur)}}>
      <CardBg />
      <div
        style={{
          position: 'absolute',
          right: 170,
          top: 150,
          opacity: pIn,
          transform: `translateX(${interpolate(pIn, [0, 1], [50, 0])}px)`,
        }}
      >
        <Framed src={image} w={620} h={780} dur={dur} />
      </div>
      <div style={{position: 'absolute', left: 190, top: 330, width: 820}}>
        <div
          style={{
            fontFamily: F.title,
            fontSize: 84,
            fontWeight: 400,
            color: C.cream,
            letterSpacing: '0.03em',
            lineHeight: 1.05,
            opacity: ramp(frame, 8, 14),
            transform: `translateY(${interpolate(ramp(frame, 8, 16), [0, 1], [18, 0])}px)`,
          }}
        >
          {name}
        </div>
        <div style={{height: 1.5, width: `${ramp(frame, 14, 20) * 300}px`, background: C.gold, margin: '26px 0 20px'}} />
        {role ? (
          <div
            style={{
              fontFamily: F.serif,
              fontWeight: 600,
              fontSize: 30,
              letterSpacing: '0.3em',
              textTransform: 'uppercase',
              color: C.gold,
              opacity: ramp(frame, 16, 12),
            }}
          >
            {role}
          </div>
        ) : null}
        <div style={{marginTop: 44}}>
          {(facts ?? []).slice(0, 4).map((f, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 18,
                marginBottom: 16,
                fontFamily: F.serif,
                fontSize: 34,
                fontWeight: 500,
                color: C.creamDim,
                opacity: ramp(frame, 26 + i * 12, 12),
              }}
            >
              <Diamond size={9} filled />
              {f}
            </div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ───────────── Carte d'armée + comparaison A vs B ───────────── */
const ArmyBlock: React.FC<{side: ArmySide; start: number; color: string}> = ({side, start, color}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', width: 640}}>
      <div
        style={{
          fontFamily: F.title,
          fontSize: 40,
          letterSpacing: '0.14em',
          color: C.cream,
          textTransform: 'uppercase',
          opacity: ramp(frame, start, 10),
        }}
      >
        {side.title}
      </div>
      <div style={{height: 1.5, width: 260 * ramp(frame, start + 4, 14), background: color, margin: '14px 0 26px'}} />
      {side.image ? (
        <div style={{opacity: ramp(frame, start + 6, 12)}}>
          <FramedStatic src={side.image} />
        </div>
      ) : null}
      <div style={{marginTop: 30, width: 560}}>
        {side.stats.slice(0, 4).map((s, i) => (
          <div
            key={i}
            style={{
              fontFamily: F.serif,
              fontSize: 30,
              fontWeight: 500,
              color: C.cream,
              background: 'rgba(255,255,255,0.045)',
              borderLeft: `2px solid ${color}`,
              padding: '9px 18px',
              marginBottom: 10,
              opacity: ramp(frame, start + 22 + i * 14, 10),
              transform: `translateX(${interpolate(ramp(frame, start + 22 + i * 14, 12), [0, 1], [-14, 0])}px)`,
            }}
          >
            {s}
          </div>
        ))}
      </div>
    </div>
  );
};

const FramedStatic: React.FC<{src: string}> = ({src}) => (
  <div style={{width: 280, height: 340, overflow: 'hidden', border: `1.5px solid ${C.goldDim}`, boxShadow: '0 14px 40px rgba(0,0,0,0.6)'}}>
    <Img src={staticFile(src)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
  </div>
);

export const Compare: React.FC<CompareSeg & {dur: number}> = ({left, right, splitAt = 0.45, dur}) => {
  const frame = useCurrentFrame();
  const split = right ? ramp(frame, splitAt * dur, 18, Easing.inOut(Easing.cubic)) : 0;
  const rightStart = Math.round(splitAt * dur) + 6;
  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur)}}>
      <CardBg />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'flex-start', paddingTop: 120}}>
        <div style={{transform: `translateX(${-460 * split}px)`}}>
          <ArmyBlock side={left} start={2} color={C.blue} />
        </div>
      </AbsoluteFill>
      {right ? (
        <>
          <AbsoluteFill style={{alignItems: 'center', justifyContent: 'flex-start', paddingTop: 120}}>
            <div style={{transform: `translateX(${interpolate(split, [0, 1], [1100, 460])}px)`}}>
              <ArmyBlock side={right} start={rightStart} color={C.red} />
            </div>
          </AbsoluteFill>
          <div
            style={{
              position: 'absolute',
              left: '50%',
              top: 150,
              bottom: 150,
              width: 1.5,
              background: `linear-gradient(180deg, rgba(201,164,90,0), ${C.gold}, rgba(201,164,90,0))`,
              opacity: split,
            }}
          />
          <div
            style={{
              position: 'absolute',
              left: '50%',
              top: '50%',
              transform: 'translate(-50%, -50%) rotate(45deg)',
              width: 46,
              height: 46,
              border: `1.5px solid ${C.gold}`,
              background: C.bg,
              opacity: split,
            }}
          />
          <div
            style={{
              position: 'absolute',
              left: '50%',
              top: '50%',
              transform: 'translate(-50%, -50%)',
              fontFamily: F.title,
              fontSize: 17,
              color: C.gold,
              opacity: split,
            }}
          >
            VS
          </div>
        </>
      ) : null}
    </AbsoluteFill>
  );
};

/* ───────────── Graphique en barres (effectifs, pertes, sources) ───────────── */
export const Chart: React.FC<ChartSeg & {dur: number}> = ({title, subtitle, bars, dur}) => {
  const frame = useCurrentFrame();
  const max = Math.max(...bars.map((b) => b.value), 1);
  const H = 470;
  const bw = Math.min(170, 900 / Math.max(1, bars.length));
  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur)}}>
      <CardBg tint="rgba(40,58,66,0.55)" />
      <div style={{position: 'absolute', top: 120, width: '100%', textAlign: 'center'}}>
        <div
          style={{
            fontFamily: F.title,
            fontSize: 54,
            letterSpacing: '0.08em',
            color: C.gold,
            textTransform: 'uppercase',
            opacity: ramp(frame, 2, 12),
          }}
        >
          {title}
        </div>
        {subtitle ? (
          <div
            style={{
              fontFamily: F.serif,
              fontSize: 28,
              letterSpacing: '0.28em',
              color: C.creamDim,
              textTransform: 'uppercase',
              marginTop: 8,
              opacity: ramp(frame, 8, 12),
            }}
          >
            {subtitle}
          </div>
        ) : null}
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 250,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-end',
          gap: 70,
        }}
      >
        {bars.map((b, i) => {
          const g = ramp(frame, 14 + i * 8, 34, Easing.out(Easing.cubic));
          const h = (b.value / max) * H * g;
          const shown = b.display && g >= 0.999 ? b.display : Math.round(b.value * g).toLocaleString('en-US');
          return (
            <div key={i} style={{display: 'flex', flexDirection: 'column', alignItems: 'center', width: bw}}>
              <div style={{fontFamily: F.label, fontSize: 36, color: C.cream, marginBottom: 12, opacity: g > 0.02 ? 1 : 0}}>
                {shown}
              </div>
              <div
                style={{
                  width: bw,
                  height: h,
                  background: `linear-gradient(180deg, ${sideColor(b.side)} 0%, ${sideColor(b.side)}cc 100%)`,
                  boxShadow: `0 0 24px ${sideColor(b.side)}66`,
                }}
              />
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', left: '18%', right: '18%', bottom: 248, height: 2, background: C.goldDim}} />
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 180, display: 'flex', justifyContent: 'center', gap: 70}}>
        {bars.map((b, i) => (
          <div
            key={i}
            style={{
              width: bw,
              textAlign: 'center',
              fontFamily: F.label,
              fontSize: 23,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: C.creamDim,
              opacity: ramp(frame, 18 + i * 8, 10),
            }}
          >
            {b.label}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/* ───────────── Document d'archive encadré ───────────── */
export const Archive: React.FC<ArchiveSeg & {dur: number}> = ({title, image, note, dur}) => {
  const frame = useCurrentFrame();
  const inP = ramp(frame, 0, 14);
  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur)}}>
      <CardBg brackets={false} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
        <div style={{opacity: inP, transform: `translateY(${interpolate(inP, [0, 1], [24, 0])}px) rotate(-0.6deg)`}}>
          <div
            style={{
              fontFamily: F.label,
              fontSize: 25,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: C.cream,
              marginBottom: 12,
            }}
          >
            {title}
          </div>
          <div style={{padding: 12, background: '#e7dfcc', boxShadow: '0 24px 60px rgba(0,0,0,0.7)'}}>
            <div style={{width: 1180, height: 664, overflow: 'hidden'}}>
              <Img
                src={staticFile(image)}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  filter: 'sepia(0.2) contrast(1.04)',
                  transform: `scale(${interpolate(frame, [0, dur], [1.0, 1.06], clamp)})`,
                }}
              />
            </div>
          </div>
          {note ? (
            <div
              style={{
                fontFamily: F.serif,
                fontStyle: 'italic',
                fontSize: 26,
                color: C.creamDim,
                marginTop: 14,
                opacity: ramp(frame, 18, 12),
              }}
            >
              {note}
            </div>
          ) : null}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* ───────────── Citation ───────────── */
export const Quote: React.FC<QuoteSeg & {dur: number}> = ({text, author, image, dur}) => {
  const frame = useCurrentFrame();
  const words = text.split(/\s+/);
  const per = Math.max(1, Math.min(4, (dur * 0.45) / words.length));
  return (
    <AbsoluteFill style={{opacity: outFade(frame, dur)}}>
      <CardBg brackets={false} />
      {image ? (
        <AbsoluteFill style={{width: '52%'}}>
          <Img
            src={staticFile(image)}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              filter: 'brightness(0.7) sepia(0.2)',
              transform: `scale(${interpolate(frame, [0, dur], [1.0, 1.06], clamp)})`,
            }}
          />
          <AbsoluteFill style={{background: `linear-gradient(90deg, rgba(21,19,15,0) 40%, ${C.bg} 100%)`}} />
        </AbsoluteFill>
      ) : null}
      <div style={{position: 'absolute', left: image ? '50%' : '18%', right: image ? 150 : '18%', top: 250}}>
        <div style={{fontFamily: F.title, fontSize: 150, color: C.gold, lineHeight: 0.6, opacity: ramp(frame, 0, 10)}}>“</div>
        <div style={{fontFamily: F.serif, fontStyle: 'italic', fontWeight: 500, fontSize: 60, lineHeight: 1.25, color: C.cream}}>
          {words.map((w, i) => (
            <span key={i} style={{opacity: ramp(frame, 8 + i * per, 8)}}>
              {w}{' '}
            </span>
          ))}
        </div>
        <div
          style={{
            marginTop: 36,
            fontFamily: F.serif,
            fontWeight: 600,
            fontSize: 30,
            letterSpacing: '0.3em',
            textTransform: 'uppercase',
            color: C.gold,
            opacity: ramp(frame, 8 + words.length * per, 12),
          }}
        >
          — {author}
        </div>
      </div>
    </AbsoluteFill>
  );
};
