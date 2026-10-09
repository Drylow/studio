import React from 'react';
import {AbsoluteFill, Audio, Freeze, Img, OffthreadVideo, Sequence, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {buildTimeline, PROFILES, RATINGS} from '../model.mjs';
import type {Segment, VideoProps} from './types';

export const RatingIcon: React.FC<{rating: string; set?: string; size?: number; editor?: boolean}> = ({rating,set='chesscom',size=60,editor=false}) => {
  const note=RATINGS[rating as keyof typeof RATINGS] || RATINGS.good;
  const iconStyle={width:size,height:size,objectFit:'contain' as const};
  return set==='chesscom' ? (editor ? <img src={`/chesscom/${rating}.svg`} style={iconStyle} alt={note.label}/> : <Img src={staticFile(`chesscom/${rating}.svg`)} style={iconStyle}/>) :
    <span style={{width:size,height:size,borderRadius:'50%',background:note.color,color:'#fff',fontSize:size*.48,fontWeight:800,display:'inline-flex',alignItems:'center',justifyContent:'center'}}>{note.symbol}</span>;
};
const Pawn: React.FC<{portrait?: string; dark?: boolean; size?: number}> = ({portrait,dark,size=140}) => <div style={{width:size,height:size*1.13,position:'relative'}}>
  <svg viewBox="0 0 120 136" style={{width:'100%',height:'100%',filter:'drop-shadow(0 4px 5px #0006)'}}>
    <path d="M37 63Q60 52 83 63L77 76Q71 88 91 103L95 111H25L29 103Q49 88 43 76Z" fill={dark?'#535355':'#f3f2e9'} stroke={dark?'#aaa8a1':'#908c80'} strokeWidth="2"/>
    <rect x="19" y="112" width="82" height="12" rx="5" fill={dark?'#414143':'#f3f2e9'} stroke={dark?'#aaa8a1':'#908c80'} strokeWidth="2"/>
    {!portrait && <circle cx="60" cy="38" r="27" fill={dark?'#414143':'#f3f2e9'} stroke={dark?'#aaa8a1':'#908c80'} strokeWidth="2"/>}
  </svg>
  {portrait && <Img src={staticFile(portrait)} style={{position:'absolute',top:size*.07,left:size*.23,width:size*.54,height:size*.54,borderRadius:'50%',objectFit:'cover',border:`2px solid ${dark?'#aaa8a1':'#f3f2e9'}`}}/>}
</div>;
const SegmentView: React.FC<{seg: Segment; props: VideoProps}> = ({seg,props}) => {
  const frame=useCurrentFrame(); const {fps}=useVideoConfig();
  const {project,media,stills={}}=props;const m=media[seg.mediaId];
  const accent=PROFILES[project.profile as keyof typeof PROFILES].accent;
  const move=seg.move;const held=seg.kind==='hold';
  const enter=interpolate(frame,[0,Math.round(fps*.25)],[0,1],{extrapolateRight:'clamp',easing:Easing.out(Easing.cubic)});
  const exit=interpolate(frame,[seg.duration-Math.round(fps*.16),seg.duration],[1,0],{extrapolateLeft:'clamp'});
  const zoom=held ? interpolate(frame,[0,seg.duration],[1,move?.zoom || 1],{easing:Easing.inOut(Easing.quad)}) : 1;
  const score=held ? interpolate(frame,[0,Math.round(fps*.5)],[seg.previousScore || 0,seg.score],{extrapolateRight:'clamp',easing:Easing.inOut(Easing.cubic)}) : seg.score;
  const ratio=100/(1+Math.exp(-score*.45));
  const note=move ? RATINGS[move.rating as keyof typeof RATINGS] : null;
  const player=move ? project.players[move.player] : project.players[0];
  const edgeFade=Math.min(1,frame/2,(seg.duration-1-frame)/2);
  return <AbsoluteFill style={{background:'#111214',fontFamily:'Arial, sans-serif',color:'#f4f3ee'}}>
    <div style={{position:'absolute',top:64,left:120,right:64,bottom:84,overflow:'hidden',borderRadius:6,background:'#090909'}}>
      <AbsoluteFill style={{transform:`scale(${zoom})`}}>
        {held ? (stills[move!.id] ? <Img src={staticFile(stills[move!.id])} style={{width:'100%',height:'100%',objectFit:'contain'}}/> :
          <Freeze frame={0}><OffthreadVideo src={staticFile(m.src)} trimBefore={seg.sourceFrame} muted style={{width:'100%',height:'100%',objectFit:'contain'}}/></Freeze>) :
          <OffthreadVideo src={staticFile(m.src)} trimBefore={seg.sourceFrame} volume={Math.max(0,edgeFade)*seg.volume} style={{width:'100%',height:'100%',objectFit:'contain'}}/>}
      </AbsoluteFill>
    </div>
    <div style={{position:'absolute',left:44,top:260,width:32,height:560,background:'#343537',border:'2px solid #6f6d66',borderRadius:4,overflow:'hidden'}}>
      <div style={{position:'absolute',bottom:0,width:'100%',height:`${ratio}%`,background:'#f3f2e9'}}/>
    </div>
    <div style={{position:'absolute',left:24,top:836,width:72,textAlign:'center',fontSize:23,fontWeight:700,fontVariantNumeric:'tabular-nums'}}>{score>0?'+':''}{score.toFixed(1)}</div>
    <div style={{position:'absolute',left:124,top:22,fontSize:18,letterSpacing:2,color:accent}}>{PROFILES[project.profile as keyof typeof PROFILES].label}</div>
    <div style={{position:'absolute',left:124,bottom:24,display:'flex',gap:22,alignItems:'center',fontSize:24}}>
      <span style={{color:'#f3f2e9'}}>● {project.players[0].name}</span><span style={{color:'#7c7d80'}}>vs</span><span style={{color:'#d0d0d3'}}>○ {project.players[1].name}</span>
    </div>
    {held && move && note && <>
      {project.sfx && <Sequence durationInFrames={Math.min(seg.duration,Math.round(fps*.2))} layout="none"><Audio src={staticFile(`sfx/${['blunder','mistake','miss'].includes(move.rating)?'low':'tick'}.wav`)} volume={.13}/></Sequence>}
      <div style={{position:'absolute',bottom:124,...(move.placement==='right'?{right:98}:{left:154}),width:580,opacity:enter*exit,
        transform:`translateY(${(1-enter)*16}px)`,background:'#202123f5',borderRadius:12,padding:'28px 32px 30px',boxShadow:'0 12px 42px #0007',borderTop:`4px solid ${note.color}`}}>
        <div style={{display:'flex',alignItems:'center',gap:18,marginBottom:16}}><RatingIcon rating={move.rating} set={project.iconSet} size={68}/><div>
          <div style={{color:note.color,fontSize:22,fontWeight:700}}>{note.label}</div><div style={{fontSize:34,fontWeight:700,lineHeight:1.15,marginTop:5}}>{move.title}</div>
        </div></div>
        <div style={{display:'flex',gap:14,alignItems:'flex-end'}}><Pawn portrait={player.portrait} dark={move.player===1} size={96}/>
          <div style={{flex:1,fontSize:28,lineHeight:1.35,paddingBottom:8}}>{move.comment}</div></div>
      </div>
      {move.quote && <div style={{position:'absolute',bottom:90,left:450,right:450,textAlign:'center',fontSize:25,textShadow:'0 2px 5px #000',background:'#111b',padding:'8px 16px',borderRadius:4,opacity:enter*exit}}>{move.quote}</div>}
    </>}
  </AbsoluteFill>;
};
export const ChessReview: React.FC<VideoProps> = (props) => {
  const timeline=buildTimeline(props.project);
  const {width}=useVideoConfig();
  return <AbsoluteFill style={{background:'#111214',overflow:'hidden'}}><div style={{position:'absolute',width:1920,height:1080,transform:`scale(${width/1920})`,transformOrigin:'top left'}}>{timeline.segments.map((seg: Segment,i: number)=><Sequence key={`${seg.shotId}-${i}`} from={seg.from} durationInFrames={seg.duration} premountFor={Math.min(30,props.project.fps)}><SegmentView seg={seg} props={props}/></Sequence>)}</div></AbsoluteFill>;
};
