import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, staticFile, useVideoConfig} from 'remotion';
import {Captions} from './components/Captions';
import {FilmOverlay} from './components/FilmOverlay';
import {ImageShot, VideoClip} from './components/Media';
import type {Segment, Timeline} from './schema';
import {Battle} from './templates/Battle';
import {Chart} from './templates/Cards';
import {Archive, BigNumber} from './templates/Extra';
import {Character, Compare} from './templates/People';
import {Quote} from './templates/Quote';
import {Route} from './templates/Route';
import {Statement} from './templates/Statement';
import {ensureFonts} from './theme';

const SegmentView: React.FC<{seg: Segment; dur: number}> = ({seg, dur}) => {
  switch (seg.type) {
    case 'image':
      return <ImageShot seg={seg} dur={dur} />;
    case 'video':
      return <VideoClip src={seg.src} />;
    case 'statement':
      return <Statement text={seg.text} dur={dur} reveal={seg.reveal} kicker={seg.kicker} />;
    case 'battle':
      return <Battle {...seg} dur={dur} />;
    case 'character':
      return <Character {...seg} dur={dur} />;
    case 'compare':
      return <Compare {...seg} dur={dur} />;
    case 'chart':
      return <Chart {...seg} dur={dur} />;
    case 'archive':
      return <Archive {...seg} dur={dur} />;
    case 'route':
      return <Route {...seg} dur={dur} />;
    case 'number':
      return <BigNumber {...seg} dur={dur} />;
    case 'quote':
      return <Quote {...seg} dur={dur} />;
    default:
      return null;
  }
};

export const HistoryVideo: React.FC<Timeline> = (t) => {
  ensureFonts();
  const {fps, durationInFrames} = useVideoConfig();
  const f = (s: number) => Math.round(s * fps);
  const mv = t.musicVolume ?? 0.1;
  // musique : montée douce au début, fondu sur les 2,5 dernières secondes
  const musicVolume = (fr: number) =>
    mv * interpolate(fr, [0, fps, durationInFrames - 2.5 * fps, durationInFrames], [0, 1, 1, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
  return (
    <AbsoluteFill style={{background: '#000'}}>
      {t.segments.map((seg, i) => {
        const from = f(seg.start);
        const dur = Math.max(1, f(seg.end) - from);
        return (
          <Sequence key={i} from={from} durationInFrames={dur} premountFor={fps}>
            <SegmentView seg={seg} dur={dur} />
          </Sequence>
        );
      })}
      <FilmOverlay intensity={t.film ?? 1} />
      <Captions items={t.captions ?? []} from={t.captionsFrom ?? 0} mute={t.captionsMute} />
      {t.voice ? <Audio src={staticFile(t.voice)} /> : null}
      {t.music ? <Audio src={staticFile(t.music)} volume={musicVolume} loop /> : null}
      {(t.sfx ?? []).map((s, i) => (
        <Sequence key={`sfx${i}`} from={f(s.at)} durationInFrames={f(4)}>
          <Audio src={staticFile(s.src)} volume={s.volume ?? 0.5} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
