import reefUrl from './assets/nocturnal-reef.png';
import jellyUrl from './assets/jellyfish-cutout.png';
import {makeReef, drawReef, reefDiagnostics} from './sleep-forward-reef.mjs';

// A moving camera in a repeating world, projected onto Canvas2D. This is
// layered 2.5D illustration, not a navigable 3D mesh or a global image zoom.
const WIDTH=1920, HEIGHT=1080, DURATION=300, LENGTH=600, TAU=Math.PI*2;
const canvas=document.getElementById('film');
const ctx=canvas.getContext('2d',{alpha:false,willReadFrequently:true});
canvas.width=WIDTH;canvas.height=HEIGHT;ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
const reef=new Image();reef.src=reefUrl;
const jellyImage=new Image();jellyImage.src=jellyUrl;
const wrap=(v,n)=>((v%n)+n)%n;
const phase=t=>wrap(t,DURATION)/DURATION*TAU;
const clamp=v=>Math.max(0,Math.min(1,v));
const smooth=(lo,hi,v)=>{const u=clamp((v-lo)/(hi-lo));return u*u*(3-2*u);};
let seed=148039;
const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
const cameraAt=t=>({x:.35*Math.sin(phase(t)),y:.8+.13*Math.sin(phase(t)*2),z:wrap(t*2,LENGTH),width:WIDTH,height:HEIGHT,focal:1000,far:160,near:2,trackLength:LENGTH});
const project=(point,camera)=>{
  const depth=wrap(point.z-camera.z,LENGTH);
  // Animals leave the viewport on planned paths before this clip plane.
  // Only distant haze changes opacity; approaching wildlife never dissolves.
  const alpha=depth>2?1-smooth(85,160,depth):0;
  const scale=camera.focal/Math.max(depth,1);
  return {x:WIDTH/2+(point.x-camera.x)*scale,y:HEIGHT*.45-(point.y-camera.y)*scale,depth,scale,alpha};
};
const fish=Array.from({length:30},(_,school)=>Array.from({length:16},(_,i)=>({
  school,index:i,z:school*20+random()*3,p:random()*TAU,
  dx:(random()-.5)*2.8,dy:(random()-.5)*1.5,
  baseX:(school%3-1)*1.5,baseY:.1+(school%4)*.62,
  length:.32+random()*.36,blue:random(),fin:random()*TAU,
}))).flat();
const sharks=Array.from({length:8},(_,i)=>({z:22+i*75,x:i%2?-.6:.6,y:1.25+(i%3)*.7,p:i*.72,length:4.1+(i%3)*.45}));
const jellies=Array.from({length:12},(_,i)=>({z:19+i*50,x:(i%2?-1:1)*(1.5+(i%3)*.65),y:1.8+(i%4)*.42,p:i*.61,size:.72+(i%3)*.26}));
const particles=Array.from({length:900},()=>({x:(random()-.5)*35,y:(random()-.5)*17,z:random()*LENGTH,p:random()*TAU,r:.008+random()*.022,alpha:.08+random()*.17}));

// Keep each passage continuous even behind the camera: the recovery happens
// outside the visible distance, rather than teleporting at wrapped depth zero.
function passageWeight(z,t){
  const wrapped=wrap(z-wrap(t*2,LENGTH),LENGTH),depth=wrapped>LENGTH/2?wrapped-LENGTH:wrapped;
  return (1-smooth(6,28,depth))*smooth(-30,-6,depth);
}
function fishPose(f,t){
  const a=phase(t),q=a*5+f.school*.57;
  const z=f.z+2*Math.sin(a*2+f.school),near=passageWeight(z,t);
  const nominal=f.baseX+2.3*Math.sin(TAU*(f.school*20/LENGTH)*5+f.school*.57);
  const exitSide=nominal<0?-1:1,normalX=f.baseX+2.3*Math.sin(q)+f.dx;
  return {...f,x:normalX*(1-near)+exitSide*5.1*near,y:f.baseY+f.dy+.18*Math.sin(a*8+f.p),z,
    facing:Math.cos(q)*(1-near)+exitSide*near,halfWidth:f.length*.68,halfHeight:f.length*.40,passageWeight:near};
}
function sharkPose(s,t){
  const a=phase(t),q=a*4+s.p,z=s.z+4*Math.sin(a*2+s.p),near=passageWeight(z,t),facing=Math.cos(q);
  return {...s,x:s.x+2.0*Math.sin(q),y:(s.y+.16*Math.sin(a*6+s.p))*(1-near)+5.8*near,z,facing,
    halfWidth:s.length*Math.max(.63*Math.abs(facing)+.008,.085),halfHeight:s.length*.34,passageWeight:near};
}
function jellyPose(j,t){
  const a=phase(t),z=j.z+Math.sin(a*3+j.p),near=passageWeight(z,t),width=j.size*2.6;
  const aspect=jellyImage.naturalHeight/jellyImage.naturalWidth;
  // Pulse, ribbon shear and rotation are included in the whole-sprite envelope.
  const halfWidth=width*(.535+Math.sin(.026)*(aspect+.18));
  const exitSide=Math.sin(TAU*j.z/LENGTH)>=0?-1:1,exitX=exitSide*(6-halfWidth-.28);
  return {...j,x:(j.x+.4*Math.sin(a*3+j.p))*(1-near)+exitX*near,y:j.y+.38*Math.sin(a*5+j.p),z,
    halfWidth,halfHeight:width*(aspect+.20),passageWeight:near};
}
function drawFish(f,screen,a){
  const length=f.length*screen.scale;if(length<1.4||screen.alpha<.01)return;
  const bend=.09*length*Math.sin(a*285+f.fin);
  ctx.save();ctx.translate(screen.x,screen.y);ctx.rotate(.025*Math.sin(a*180+f.fin));ctx.save();ctx.scale(f.facing,1);
  ctx.globalAlpha=screen.alpha*(.72+f.blue*.22);
  const color=ctx.createLinearGradient(0,-length*.2,0,length*.2);
  color.addColorStop(0,f.blue>.5?'#7caaa9':'#618b9b');color.addColorStop(.5,'#365d70');color.addColorStop(1,'#162f42');
  ctx.fillStyle=color;ctx.beginPath();ctx.moveTo(length*.49,0);
  ctx.bezierCurveTo(length*.27,-length*.17,-length*.13,-length*.18,-length*.37,bend*.35);
  ctx.lineTo(-length*.63,-length*.20+bend);ctx.quadraticCurveTo(-length*.57,bend,-length*.65,length*.20+bend);
  ctx.lineTo(-length*.37,bend*.35);ctx.bezierCurveTo(-length*.16,length*.17,length*.28,length*.13,length*.49,0);ctx.fill();
  ctx.fillStyle='rgba(129,173,178,.38)';ctx.beginPath();ctx.moveTo(-length*.17,-length*.11);ctx.quadraticCurveTo(-length*.02,-length*.35,length*.12,-length*.11);ctx.fill();
  ctx.fillStyle='rgba(124,162,170,.4)';ctx.beginPath();ctx.moveTo(length*.05,0);ctx.quadraticCurveTo(-length*.02,length*.25+Math.sin(a*285+f.fin)*length*.04,length*.21,length*.10);ctx.fill();
  if(length>12){ctx.strokeStyle='rgba(166,200,201,.24)';ctx.lineWidth=Math.max(.5,length*.014);ctx.beginPath();ctx.moveTo(length*.25,-length*.04);ctx.quadraticCurveTo(0,-length*.04,-length*.27,0);ctx.stroke();
    ctx.fillStyle='#0a1720';ctx.beginPath();ctx.arc(length*.34,-length*.028,Math.max(.7,length*.028),0,TAU);ctx.fill();}
  ctx.restore();
  // A continuous yaw has an end-on cross-section instead of an instant mirror.
  const endOn=Math.sqrt(Math.max(0,1-f.facing*f.facing));
  ctx.globalAlpha=screen.alpha*(.72+f.blue*.22);
  if(endOn>0){ctx.fillStyle=color;ctx.beginPath();ctx.ellipse(length*.12*f.facing,0,length*.10*endOn,length*.155,0,0,TAU);ctx.fill();}
  ctx.restore();
}
function drawShark(s,p,a){
  if(p.alpha<.015)return;const size=s.length*p.scale,tail=size*.045*Math.sin(a*125+s.p);
  ctx.save();ctx.translate(p.x,p.y);ctx.rotate(.015*Math.sin(a*50+s.p));ctx.globalAlpha=p.alpha*.63;ctx.save();ctx.scale(s.facing,1);
  const color=ctx.createLinearGradient(0,-size*.12,0,size*.12);color.addColorStop(0,'#193a50');color.addColorStop(.5,'#254b61');color.addColorStop(1,'#456778');ctx.fillStyle=color;
  ctx.beginPath();ctx.moveTo(size*.53,0);ctx.bezierCurveTo(size*.42,-size*.07,size*.24,-size*.095,size*.04,-size*.083);
  ctx.quadraticCurveTo(-size*.02,-size*.24,-size*.105,-size*.084);ctx.bezierCurveTo(-size*.22,-size*.075,-size*.37,-size*.04,-size*.44,tail);
  ctx.bezierCurveTo(-size*.47,-size*.08+tail,-size*.5,-size*.23+tail,-size*.59,-size*.24+tail);ctx.lineTo(-size*.56,tail);ctx.lineTo(-size*.62,size*.09+tail);ctx.quadraticCurveTo(-size*.49,size*.1+tail,-size*.44,tail);
  ctx.bezierCurveTo(-size*.23,size*.045,-size*.10,size*.045,size*.035,size*.06);ctx.quadraticCurveTo(size*.09,size*.17,size*.19,size*.11);ctx.lineTo(size*.16,size*.037);ctx.bezierCurveTo(size*.30,size*.04,size*.47,size*.02,size*.53,0);ctx.fill();
  if(size>120){ctx.strokeStyle='rgba(9,26,39,.5)';ctx.lineWidth=Math.max(1,size*.004);for(let k=0;k<3;k++){ctx.beginPath();ctx.moveTo(size*(.24-k*.025),-size*.03);ctx.lineTo(size*(.22-k*.025),size*.025);ctx.stroke();}ctx.fillStyle='#091721';ctx.beginPath();ctx.arc(size*.40,-size*.015,Math.max(.8,size*.007),0,TAU);ctx.fill();}
  ctx.restore();
  const endOn=Math.sqrt(Math.max(0,1-s.facing*s.facing));
  if(endOn>0){ctx.fillStyle=color;ctx.beginPath();ctx.ellipse(0,0,size*.075*endOn,size*.105,0,0,TAU);ctx.fill();}
  ctx.restore();
}
function drawJelly(j,p,a){
  if(p.alpha<.01)return;const width=j.size*p.scale*2.6;if(width<8)return;
  const height=width*jellyImage.naturalHeight/jellyImage.naturalWidth,strips=40,sourceHeight=jellyImage.naturalHeight/strips;
  ctx.save();ctx.translate(p.x,p.y-width*.17);ctx.rotate(.026*Math.sin(a*8+j.p));ctx.globalAlpha=p.alpha*.59;
  for(let i=0;i<strips;i++){const u=(i+.5)/strips,flex=smooth(.25,.85,u),pulse=1+.026*Math.sin(a*55+j.p)*(1-smooth(.24,.53,u));
    const dx=width*(.01*Math.sin(a*65+u*5.5+j.p)+.005*Math.sin(a*50-u*9+j.p))*flex;
    const w=width*pulse;ctx.drawImage(jellyImage,0,i*sourceHeight,jellyImage.naturalWidth,Math.min(sourceHeight+.6,jellyImage.naturalHeight-i*sourceHeight),-w/2+dx,i/strips*height,w,height/strips+.2);}
  ctx.restore();
}
function render(t){
  if(!Number.isFinite(t))throw new Error('Time must be finite.');
  const a=phase(t),camera=cameraAt(t);
  ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';
  ctx.fillStyle='#051b2b';ctx.fillRect(0,0,WIDTH,HEIGHT);
  // Only the distant painting is stationary. All close layers and wildlife
  // use projected world depth as the camera advances at two units/second.
  const base=Math.max(WIDTH/reef.naturalWidth,HEIGHT/reef.naturalHeight),w=reef.naturalWidth*base,h=reef.naturalHeight*base;
  ctx.drawImage(reef,(WIDTH-w)/2,(HEIGHT-h)/2,w,h);
  ctx.fillStyle='rgba(4,28,44,.20)';ctx.fillRect(0,0,WIDTH,HEIGHT);
  const reefStats=drawReef(ctx,camera,t);
  const creatures=[...fish.map(f=>({type:'fish',pose:fishPose(f,t)})),...sharks.map(s=>({type:'shark',pose:sharkPose(s,t)})),...jellies.map(j=>({type:'jelly',pose:jellyPose(j,t)}))]
    .map(item=>({...item,screen:project(item.pose,camera)})).filter(item=>item.screen.alpha>.01).sort((a,b)=>b.screen.depth-a.screen.depth);
  let visibleFish=0,visibleSharks=0,visibleJellies=0;
  for(const {type,pose,screen} of creatures){if(screen.x<-900||screen.x>WIDTH+900||screen.y<-900||screen.y>HEIGHT+900)continue;
    if(type==='fish'){drawFish(pose,screen,a);if(screen.x>0&&screen.x<WIDTH&&screen.y>0&&screen.y<HEIGHT)visibleFish++;}
    else if(type==='shark'){drawShark(pose,screen,a);if(screen.x>0&&screen.x<WIDTH&&screen.y>0&&screen.y<HEIGHT)visibleSharks++;}
    else {drawJelly(pose,screen,a);if(screen.x>0&&screen.x<WIDTH&&screen.y>0&&screen.y<HEIGHT)visibleJellies++;}}
  for(const particle of particles){const p=project({...particle,x:particle.x+.24*Math.sin(a*3+particle.p),y:particle.y+.20*Math.sin(a*4+particle.p)},camera);
    if(p.alpha<.01||p.x<0||p.x>WIDTH||p.y<0||p.y>HEIGHT)continue;
    ctx.globalAlpha=p.alpha*particle.alpha;ctx.fillStyle='#aac6cf';ctx.beginPath();ctx.arc(p.x,p.y,Math.min(3.1,Math.max(.45,particle.r*p.scale)),0,TAU);ctx.fill();}
  ctx.globalAlpha=1;
  const vignette=ctx.createRadialGradient(WIDTH*.5,HEIGHT*.45,HEIGHT*.3,WIDTH*.5,HEIGHT*.45,WIDTH*.66);vignette.addColorStop(0,'rgba(0,6,15,0)');vignette.addColorStop(1,'rgba(0,5,13,.17)');ctx.fillStyle=vignette;ctx.fillRect(0,0,WIDTH,HEIGHT);
  return {time:t,renderer:'Canvas2D perspective-projected marine corridor',camera_z:camera.z,visible_fish:visibleFish,visible_sharks:visibleSharks,visible_jellies:visibleJellies,reef:reefStats};
}
function sample(t){const camera=cameraAt(t),a=phase(t),reefState=reefDiagnostics(camera,t);
  const creatures=[...fish.map(f=>({id:`fish-${f.school}-${f.index}`,kind:'fish',pose:fishPose(f,t)})),
    ...sharks.map((s,i)=>({id:`shark-${i}`,kind:'shark',pose:sharkPose(s,t)})),
    ...jellies.map((j,i)=>({id:`jelly-${i}`,kind:'jelly',pose:jellyPose(j,t)}))]
    .map(({id,kind,pose})=>{const p=project(pose,camera);return {id,kind,world:[pose.x,pose.y,wrap(pose.z,LENGTH)],depth:p.depth,screen:[p.x,p.y],scale:p.scale,
      halfWidth:pose.halfWidth,halfHeight:pose.halfHeight,facing:pose.facing??null,passageWeight:pose.passageWeight,
      visible:p.alpha>.01&&p.x>=0&&p.x<=WIDTH&&p.y>=0&&p.y<=HEIGHT,waterClearance:6-Math.abs(pose.x)-pose.halfWidth};});
  return {time:t,phase:a,camera,cameraProgress:t*2,trackLength:LENGTH,worldCounts:{fish:fish.length,sharks:sharks.length,jellies:jellies.length,reef:reefState.total_objects},landmarks:reefState.landmarks??[],creatures,
  fish:fish.map(f=>{const pose=fishPose(f,t),p=project(pose,camera);return {world:{x:pose.x,y:pose.y,z:wrap(pose.z,LENGTH)},halfWidth:pose.halfWidth,halfHeight:pose.halfHeight,x:p.x/WIDTH,y:p.y/HEIGHT,depth:p.depth,visible:p.alpha,scale:p.scale};}),
  sharks:sharks.map(s=>{const pose=sharkPose(s,t),p=project(pose,camera);return {world:{x:pose.x,y:pose.y,z:wrap(pose.z,LENGTH)},x:p.x/WIDTH,y:p.y/HEIGHT,depth:p.depth,visible:p.alpha};}),
  jellies:jellies.map(j=>{const pose=jellyPose(j,t),p=project(pose,camera);return {world:{x:pose.x,y:pose.y,z:wrap(pose.z,LENGTH)},x:p.x/WIDTH,y:p.y/HEIGHT,depth:p.depth,visible:p.alpha};}),
  reef:reefState,forward:{speed_world_units_per_second:2,track_length:LENGTH,global_zoom:false,near_clip_depth:2,near_opacity_fade:false,
    wildlife_passages:'Small fish and jellies swim out sideways; sharks pass overhead before the camera clip plane',world_geometry:'Perspective projected illustrated layers, not solid 3D meshes'}};}
function ready(){
  makeReef(58247,reef);
  window.DeepSeaFilm={render,duration:DURATION,width:WIDTH,height:HEIGHT,antialias:'Canvas2D smooth paths and high-quality image interpolation',renderer:'Layered 2.5D marine corridor with forward camera',
    layout:{art_direction:'Nocturnal illustrated reef with projected forward-motion foreground and original coded wildlife',duration_seconds:DURATION,background_source_dimensions:[reef.naturalWidth,reef.naturalHeight],original_generated_backgrounds:1,original_generated_sprites:1,source_images:2,asset_generation_calls:2,video_generation_calls:0,algrow_calls:0,runtime_network_calls:0,
      fish_total:fish.length,fish_schools:30,shark_silhouettes:8,jellyfish:jellies.length,marine_snow:particles.length,motion:'Constant forward camera z, perspective depth parallax, stateless 300-second periodic world and independent swimming',camera_speed:2,global_zoom:false,asset_reused_for_all_frames:true},diagnostics:{sample}};
  let playing=true,playbackTime=0,last=performance.now();
  const seek=document.getElementById('seek'),play=document.getElementById('play'),clock=document.getElementById('time');
  play?.addEventListener('click',()=>{playing=!playing;play.textContent=playing?'Pause':'Lire';last=performance.now();});
  seek?.addEventListener('input',()=>{playbackTime=Number(seek.value);render(playbackTime);});
  function tick(now){const delta=Math.min(.1,(now-last)/1000);last=now;if(playing){playbackTime=(playbackTime+delta)%DURATION;render(playbackTime);if(seek)seek.value=playbackTime;if(clock)clock.textContent=`${Math.floor(playbackTime/60)}:${String(Math.floor(playbackTime%60)).padStart(2,'0')}`;}if(!window.__CAPTURE_MODE__)requestAnimationFrame(tick);}
  render(0);if(!window.__CAPTURE_MODE__)requestAnimationFrame(tick);
}
Promise.all([reef.decode(),jellyImage.decode()]).then(ready).catch(error=>{setTimeout(()=>{throw new Error('Original offline images failed to load: '+error.message);});});
