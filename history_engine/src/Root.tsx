import React from 'react';
import {Composition} from 'remotion';
import {HistoryVideo} from './HistoryVideo';
import type {Timeline} from './schema';

const EMPTY: Timeline = {duration: 5, segments: [{type: 'statement', text: 'DRYLOW *HISTORY* ENGINE', start: 0, end: 5}]};

export const Root: React.FC = () => (
  <Composition
    id="History"
    component={HistoryVideo as unknown as React.FC<Record<string, unknown>>}
    defaultProps={EMPTY as unknown as Record<string, unknown>}
    fps={30}
    width={1920}
    height={1080}
    durationInFrames={150}
    calculateMetadata={({props}) => {
      const t = props as unknown as Timeline;
      const fps = t.fps ?? 30;
      return {
        fps,
        width: t.width ?? 1920,
        height: t.height ?? 1080,
        durationInFrames: Math.max(1, Math.ceil(t.duration * fps)),
      };
    }}
  />
);
