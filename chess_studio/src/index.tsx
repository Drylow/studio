import React from 'react';
import {Composition,registerRoot} from 'remotion';
import {ChessReview} from './ChessReview';
import {buildTimeline,newProject} from '../model.mjs';
import type {VideoProps} from './types';
const Root: React.FC=()=> <Composition id="ChessReview" component={ChessReview} durationInFrames={1} fps={30} width={1920} height={1080}
  defaultProps={{project:newProject(),media:{}} as VideoProps}
  calculateMetadata={({props})=>({durationInFrames:buildTimeline(props.project).durationInFrames,fps:props.project.fps,width:props.project.resolution===2160?3840:1920,height:props.project.resolution})}/>;
registerRoot(Root);
