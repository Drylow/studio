import React from 'react';
import {AbsoluteFill, Audio, Freeze, Img, OffthreadVideo, Sequence, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {buildTimeline, RATINGS} from '../model.mjs';
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
  const move=seg.move;const held=seg.kind==='hold';
  const enter=interpolate(frame,[0,Math.round(fps*.16)],[0,1],{extrapolateRight:'clamp',easing:Easing.out(Easing.cubic)});
  const exit=interpolate(frame,[seg.duration-Math.round(fps*.1),seg.duration],[1,0],{extrapolateLeft:'clamp'});
  const zoom=held ? interpolate(frame,[0,seg.duration],[1,move?.zoom || 1],{easing:Easing.inOut(Easing.quad)}) : 1;
  const score=held ? interpolate(frame,[0,Math.round(fps*.5)],[seg.previousScore || 0,seg.score],{extrapolateRight:'clamp',easing:Easing.inOut(Easing.cubic)}) : seg.score;
  const ratio=100/(1+Math.exp(-score*.36));
  const note=move ? RATINGS[move.rating as keyof typeof RATINGS] : null;
  const player=move ? project.players[move.player] : project.players[0];
  const ply=move ? project.shots.flatMap(s=>s.moves).findIndex(m=>m.id===move.id) : 0;
  const ratingSentence=note ? ({book:'a book move',great:'a great move',brilliant:'brilliant',best:'best',excellent:'excellent',good:'good',inaccuracy:'an inaccuracy',mistake:'a mistake',miss:'a miss',blunder:'a blunder'} as Record<string,string>)[move!.rating] : '';
  const right=move?.placement!=='left';
  const cardX=(move?.cardX ?? (right?68.2:12))*19.2;
  const cardY=(move?.cardY ?? (right?33.3:22.2))*10.8;
  const cardWidth=(move?.cardWidth ?? (right?29.2:26))*19.2;
  const iconX=(move?.iconX ?? (right?60.2:79.3))*19.2;
  const iconY=(move?.iconY ?? (right?12.8:31))*10.8;
  const reveal=held && move ? Math.min(move.comment.length,Math.max(0,Math.floor((frame/fps-.25)*Math.max(28,move.comment.length/Math.max(1,move.hold-1.1))))) : 0;
  const edgeFade=Math.min(1,frame/2,(seg.duration-1-frame)/2);
  return <AbsoluteFill style={{background:'#000',fontFamily:'Arial, sans-serif',color:'#fff'}}>
    <AbsoluteFill style={{overflow:'hidden'}}>
      <AbsoluteFill style={{transform:`scale(${zoom})`}}>
        {held ? (stills[move!.id] ? <Img src={staticFile(stills[move!.id])} style={{width:'100%',height:'100%',objectFit:'contain'}}/> :
          <Freeze frame={0}><OffthreadVideo src={staticFile(m.src)} trimBefore={seg.sourceFrame} muted style={{width:'100%',height:'100%',objectFit:'contain'}}/></Freeze>) :
          <OffthreadVideo src={staticFile(m.src)} trimBefore={seg.sourceFrame} volume={Math.max(0,edgeFade)*seg.volume} style={{width:'100%',height:'100%',objectFit:'contain'}}/>}
      </AbsoluteFill>
    </AbsoluteFill>
    {held && <AbsoluteFill style={{background:'#000',opacity:.2}}/>}
    <div style={{position:'absolute',left:26,top:112,width:41,height:857,background:'#403c38',overflow:'hidden',boxShadow:'0 0 0 3px #1118'}}>
      <div style={{position:'absolute',bottom:0,width:'100%',height:`${ratio}%`,background:'#fff'}}/>
      <div style={{position:'absolute',...(score<0?{top:7}:{bottom:7}),width:'100%',textAlign:'center',color:score<0?'#fff':'#262421',fontSize:14,fontWeight:700}}>{Math.abs(score).toFixed(1)}</div>
    </div>
    {[1,0].map((index)=><div key={index} style={{position:'absolute',left:26,top:index===1?30:982,display:'flex',gap:12,alignItems:'center',textShadow:'0 2px 3px #000'}}>
      {project.players[index].portrait?<Img src={staticFile(project.players[index].portrait)} style={{width:76,height:76,objectFit:'cover',borderRadius:7,boxShadow:'0 0 0 4px #111b'}}/>:<div style={{width:76,height:76,borderRadius:7,background:'#292722',display:'flex',justifyContent:'center',alignItems:'center',fontSize:58,color:index===1?'#b1aca3':'#fff'}}>♟</div>}
      <div><div style={{fontSize:28,fontWeight:700,lineHeight:1.2}}>{project.players[index].name}</div><div style={{fontSize:18,marginTop:3}}>{index===1?'Black':'White'}</div></div>
    </div>)}
    {held && move && note && <>
      {project.sfx && <Sequence durationInFrames={Math.min(seg.duration,Math.round(fps*.2))} layout="none"><Audio src={staticFile(`sfx/${['blunder','mistake','miss'].includes(move.rating)?'low':'tick'}.wav`)} volume={.13}/></Sequence>}
      <div style={{position:'absolute',left:iconX,top:iconY,opacity:enter*exit,transform:`scale(${.85+.15*enter})`,transformOrigin:'center'}}><RatingIcon rating={move.rating} set={project.iconSet} size={184}/></div>
      <div style={{position:'absolute',left:cardX,top:cardY,width:cardWidth,opacity:enter*exit,
        boxSizing:'border-box',background:'#262421f5',borderRadius:16,padding:'26px 28px 28px',borderLeft:`8px solid ${note.color}`}}>
        <div style={{color:note.color,fontSize:34,fontWeight:700,lineHeight:1.28}}>{move.title} is {ratingSentence}</div>
        <div style={{fontSize:22,fontWeight:600,color:'#b7b4ae',marginTop:8,marginBottom:18}}>{Math.floor(ply/2)+1}{move.player===1?'...':''} {player.name} · {move.title}{['mistake','blunder','inaccuracy','brilliant','great'].includes(move.rating)?note.symbol:''}</div>
        <div style={{fontSize:30,lineHeight:1.34,whiteSpace:'pre-wrap',textShadow:'0 1px 1px #000',overflowWrap:'anywhere'}}><span>{move.comment.slice(0,reveal)}</span><span style={{color:'#b7b4ae',opacity:.4}}>{move.comment.slice(reveal,reveal+6)}</span></div>
        {move.betterMove && <div style={{display:'flex',gap:8,alignItems:'center',marginTop:16,color:'#b2c76d',fontSize:20,fontWeight:600}}><RatingIcon rating="best" size={26}/>Better was: {move.betterMove}</div>}
        {move.tags && <div style={{marginTop:14,display:'flex',gap:7,flexWrap:'wrap'}}>{move.tags.split(',').map(tag=><span key={tag} style={{fontSize:15,color:'#b7b4ae',padding:'4px 7px',background:'#39352f',borderRadius:4}}>{tag.trim()}</span>)}</div>}
        {project.showPawn && <div style={{position:'absolute',left:-116,bottom:0}}><Pawn portrait={player.portrait} dark={move.player===1} size={96}/></div>}
      </div>
      {move.quote && <div style={{position:'absolute',bottom:50,left:280,right:280,textAlign:'center',fontSize:50,lineHeight:1.22,fontWeight:700,WebkitTextStroke:'2px #000',paintOrder:'stroke fill',textShadow:'0 2px 3px #000'}}>{move.quote}</div>}
    </>}
  </AbsoluteFill>;
};
export const ChessReview: React.FC<VideoProps> = (props) => {
  const timeline=buildTimeline(props.project);
  const {width}=useVideoConfig();
  return <AbsoluteFill style={{background:'#111214',overflow:'hidden'}}><div style={{position:'absolute',width:1920,height:1080,transform:`scale(${width/1920})`,transformOrigin:'top left'}}>{timeline.segments.map((seg: Segment,i: number)=><Sequence key={`${seg.shotId}-${i}`} from={seg.from} durationInFrames={seg.duration} premountFor={Math.min(30,props.project.fps)}><SegmentView seg={seg} props={props}/></Sequence>)}</div></AbsoluteFill>;
};
