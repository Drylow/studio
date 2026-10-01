import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig} from 'remotion';
import {Captions} from './components/Captions';
import {FilmOverlay} from './components/FilmOverlay';
import {KenBurns, VideoClip} from './components/Media';
import type {Segment, Timeline} from './schema';
import {Battle} from './templates/Battle';
import {Archive, Character, Chart, Compare} from './templates/Cards';
import {Quote} from './templates/Quote';
import {Route} from './templates/Route';
import {Statement} from './templates/Statement';
import {ensureFonts} from './theme';

const SegmentView: React.FC<{seg: Segment; dur: number}> = ({seg, dur}) => {
  switch (seg.type) {
    case 'image':
      return <KenBurns src={seg.src} dur={dur} motion={seg.motion} strength={seg.strength} />;
    case 'video':
      return <VideoClip src={seg.src} />;
    case 'statement':
      return <Statement text={seg.text} dur={dur} reveal={seg.reveal} />;
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
    case 'quote':
      return <Quote {...seg} dur={dur} />;
    default:
      return null;
  }
};

export const HistoryVideo: React.FC<Timeline> = (t) => {
  ensureFonts();
  const {fps} = useVideoConfig();
  const f = (s: number) => Math.round(s * fps);
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
      {t.music ? <Audio src={staticFile(t.music)} volume={t.musicVolume ?? 0.1} loop /> : null}
      {(t.sfx ?? []).map((s, i) => (
        <Sequence key={`sfx${i}`} from={f(s.at)} durationInFrames={f(4)}>
          <Audio src={staticFile(s.src)} volume={s.volume ?? 0.5} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
