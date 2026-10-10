import reefUrl from './assets/nocturnal-reef.png';
import jellyUrl from './assets/jellyfish-cutout.png';

// New direction: an original painted night reef with original, coded marine life.
// No game scene, previous 3D meshes, online dependency or frame generation.
const WIDTH=1920,HEIGHT=1080,DURATION=300,TAU=Math.PI*2;
const canvas=document.getElementById('film'),ctx=canvas.getContext('2d',{alpha:false,willReadFrequently:true});
canvas.width=WIDTH;canvas.height=HEIGHT;ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
const phase=t=>((t%DURATION)+DURATION)%DURATION/DURATION*TAU;
let seed=371940;
const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
const clamp=x=>Math.max(0,Math.min(1,x));
const smooth=(lo,hi,x)=>{const s=clamp((x-lo)/(hi-lo));return s*s*(3-2*s);};
const reef=new Image();reef.src=reefUrl;
const jellyImage=new Image();jellyImage.src=jellyUrl;
const fish=Array.from({length:8},(_,school)=>Array.from({length:18},(_,i)=>({
  school,index:i,offset:school*.81,dx:(random()-.5)*.20,dy:(random()-.5)*.045,
  size:13+random()*16,depth:.44+random()*.30,fin:random()*TAU,
}))).flat();
const snow=Array.from({length:240},()=>({x:random(),y:random(),r:.55+random()*1.4,a:.035+random()*.07,p:random()*TAU}));
const jellySettings=[{x:.685,y:.215,r:85,length:220,p:.45,alpha:.88},
  {x:.43,y:.285,r:43,length:132,p:2.0,alpha:.52},{x:.29,y:.16,r:25,length:70,p:3.5,alpha:.28}];
const fronds=Array.from({length:12},(_,i)=>({x:i<6?.035+i*.032:.80+(i-6)*.036,
  y:.89+(i%3)*.035,h:72+(i%4)*17,angle:i<6?-.40:.40,p:random()*TAU}));
function wildlife(t){
  const a=phase(t);
  return fish.map(f=>{const q=a+f.offset,sign=Math.cos(q)>=0?1:-1;
    return {...f,x:.5+1.05*Math.sin(q)+f.dx,y:.195+(f.school%3)*.085+f.dy+.013*Math.sin(2*a+f.offset),sign};});
}
// This envelope was fitted to the open-water valley in the original painting.
// Marine silhouettes fade behind its sides instead of swimming over the reef.
function waterVisibility(x,y){
  const limit=.535-.47*Math.pow(Math.abs(x-.51)/.51,1.75);
  return smooth(.035,.105,x)*smooth(.035,.105,1-x)*(1-smooth(limit-.055,limit+.01,y));
}
function drawFish(f,a){
  const visible=waterVisibility(f.x,f.y);if(visible<.01)return;
  const length=f.size,tail=.16*Math.sin(a*90+f.fin),bend=length*tail;
  ctx.save();ctx.translate(f.x*WIDTH,f.y*HEIGHT);ctx.scale(f.sign,1);
  ctx.rotate(.02*Math.sin(a*60+f.fin));ctx.globalAlpha=visible*f.depth;
  const gradient=ctx.createLinearGradient(0,-length*.16,0,length*.18);
  gradient.addColorStop(0,'#4c7183');gradient.addColorStop(.42,'#244c63');gradient.addColorStop(1,'#102a3d');
  ctx.fillStyle=gradient;ctx.beginPath();ctx.moveTo(length*.48,0);
  ctx.bezierCurveTo(length*.18,-length*.19,-length*.15,-length*.16,-length*.38,bend*.25);
  ctx.bezierCurveTo(-length*.52,-length*.24+bend,-length*.65,-length*.14+bend,-length*.58,bend*.6);
  ctx.bezierCurveTo(-length*.65,length*.17+bend,-length*.49,length*.23+bend,-length*.38,bend*.25);
  ctx.bezierCurveTo(-length*.11,length*.17,length*.18,length*.13,length*.48,0);ctx.fill();
  ctx.fillStyle='rgba(94,131,149,.24)';ctx.beginPath();ctx.moveTo(-length*.08,-length*.105);
  ctx.quadraticCurveTo(length*.04,-length*.29,length*.16,-length*.10);ctx.fill();
  ctx.fillStyle='rgba(4,16,26,.65)';ctx.beginPath();ctx.arc(length*.32,-length*.018,Math.max(.6,length*.026),0,TAU);ctx.fill();ctx.restore();
}
function drawShark(index,a){
  const p=a+(index?.55:3.1),x=.5+1.22*Math.sin(p),y=index?.29:.40;
  const alpha=waterVisibility(x,y)*(index?.18:.30);if(alpha<.01)return;
  const sign=Math.cos(p)>=0?1:-1,size=index?143:210,tail=Math.sin(a*60+index)*size*.025;
  ctx.save();ctx.translate(x*WIDTH,y*HEIGHT);ctx.scale(sign,1);ctx.globalAlpha=alpha;ctx.fillStyle='#061a2b';
  ctx.beginPath();ctx.moveTo(size*.53,0);ctx.bezierCurveTo(size*.42,-size*.07,size*.24,-size*.095,size*.04,-size*.083);
  ctx.bezierCurveTo(-size*.012,-size*.19,-size*.08,-size*.215,-size*.105,-size*.084);
  ctx.bezierCurveTo(-size*.22,-size*.075,-size*.37,-size*.04,-size*.44,tail);
  ctx.bezierCurveTo(-size*.47,-size*.08+tail,-size*.50,-size*.23+tail,-size*.59,-size*.24+tail);
  ctx.lineTo(-size*.56,tail);ctx.lineTo(-size*.62,size*.09+tail);ctx.quadraticCurveTo(-size*.49,size*.10+tail,-size*.44,tail);
  ctx.bezierCurveTo(-size*.23,size*.045,-size*.10,size*.045,size*.035,size*.06);
  ctx.quadraticCurveTo(size*.09,size*.17,size*.19,size*.11);ctx.lineTo(size*.16,size*.037);
  ctx.bezierCurveTo(size*.30,size*.040,size*.47,size*.02,size*.53,0);ctx.fill();ctx.restore();
}
function drawJelly(j,a){
  const x=(j.x+.010*Math.sin(a+j.p))*WIDTH,y=(j.y+.009*Math.sin(2*a+j.p))*HEIGHT;
  const width=j.r*3.30,height=width*jellyImage.naturalHeight/jellyImage.naturalWidth;
  const strips=64,sourceHeight=jellyImage.naturalHeight/strips;
  ctx.save();ctx.translate(x,y-j.r*.65);ctx.rotate(.017*Math.sin(a*2+j.p));ctx.globalAlpha=j.alpha*.78;
  // Fine vertical tissue sway and bell expansion deform the original cutout.
  // Small overlapping bands prevent cracks; no square plate or painted ocean follows it.
  for(let i=0;i<strips;i++){
    const u=(i+.5)/strips,flex=smooth(.25,.85,u);
    const bellPulse=1+.032*Math.sin(a*50+j.p)*(1-smooth(.24,.53,u));
    const horizontal=width*(.011*Math.sin(a*50+u*5.5+j.p)+.005*Math.sin(a*40-u*9.0+j.p))*flex;
    const w=width*bellPulse,yy=i/strips*height;
    ctx.drawImage(jellyImage,0,i*sourceHeight,jellyImage.naturalWidth,Math.min(sourceHeight+.6,jellyImage.naturalHeight-i*sourceHeight),
      -w/2+horizontal,yy,w,height/strips+.20);
  }
  ctx.restore();
}
function drawFronds(a){
  for(const f of fronds){ctx.save();ctx.translate(f.x*WIDTH,f.y*HEIGHT);ctx.rotate(f.angle+.018*Math.sin(a*30+f.p));
    ctx.strokeStyle='rgba(104,160,164,.12)';ctx.lineWidth=1.0;ctx.beginPath();ctx.moveTo(0,0);ctx.quadraticCurveTo(8,-f.h*.5,0,-f.h);ctx.stroke();
    for(let k=2;k<16;k++){const u=k/16,yy=-u*f.h,w=Math.sin(u*Math.PI)*f.h*.22;
      for(const sign of [-1,1]){ctx.beginPath();ctx.moveTo(4*Math.sin(u*Math.PI),yy+4);ctx.quadraticCurveTo(sign*w*.6,yy-5,sign*w,yy-11);ctx.stroke();}}
    ctx.restore();}
}
function render(t){
  if(!Number.isFinite(t))throw new Error('Time must be finite.');const a=phase(t);
  ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';
  ctx.fillStyle='#051321';ctx.fillRect(0,0,WIDTH,HEIGHT);
  const zoom=1.10+.055*Math.sin(a);
  ctx.save();ctx.translate(WIDTH/2+26*Math.sin(a),HEIGHT/2+8*Math.sin(2*a));ctx.scale(zoom,zoom);ctx.translate(-WIDTH/2,-HEIGHT/2);
  const base=Math.max(WIDTH/reef.naturalWidth,HEIGHT/reef.naturalHeight);
  const w=reef.naturalWidth*base,h=reef.naturalHeight*base;
  ctx.drawImage(reef,(WIDTH-w)/2,(HEIGHT-h)/2,w,h);
  const wash=ctx.createLinearGradient(0,0,0,HEIGHT);wash.addColorStop(0,'rgba(2,13,24,.08)');wash.addColorStop(1,'rgba(2,10,21,.14)');ctx.fillStyle=wash;ctx.fillRect(0,0,WIDTH,HEIGHT);
  // Large weak luminance variation: no flickering, bright flashes or rainbow dots.
  ctx.globalCompositeOperation='screen';ctx.globalAlpha=.021+.003*Math.sin(2*a);
  const light=ctx.createRadialGradient(WIDTH*.21,0,0,WIDTH*.21,0,WIDTH*.62);
  light.addColorStop(0,'#a9dbe4');light.addColorStop(1,'rgba(20,75,111,0)');ctx.fillStyle=light;ctx.fillRect(0,0,WIDTH,HEIGHT);
  ctx.globalCompositeOperation='source-over';ctx.globalAlpha=1;
  drawShark(1,a);for(const f of wildlife(t))drawFish(f,a);drawShark(0,a);
  for(const j of [...jellySettings].reverse())drawJelly(j,a);
  for(const p of snow){const x=(p.x+.018*Math.sin(2*a+p.p))*WIDTH,y=(p.y+.022*Math.cos(3*a+p.p))*HEIGHT;
    ctx.fillStyle=`rgba(165,194,209,${p.a})`;ctx.beginPath();ctx.arc(x,y,p.r,0,TAU);ctx.fill();}
  drawFronds(a);ctx.restore();
  const vignette=ctx.createRadialGradient(WIDTH*.50,HEIGHT*.44,HEIGHT*.28,WIDTH*.50,HEIGHT*.44,WIDTH*.68);
  vignette.addColorStop(0,'rgba(0,4,12,0)');vignette.addColorStop(1,'rgba(0,5,14,.21)');ctx.fillStyle=vignette;ctx.fillRect(0,0,WIDTH,HEIGHT);
  ctx.globalAlpha=1;return {time:t,drawCalls:0,triangles:0,renderer:'Canvas2D original nocturnal marine illustration'};
}
function ready(){
  window.DeepSeaFilm={render,duration:DURATION,width:WIDTH,height:HEIGHT,antialias:'Canvas2D smooth paths and high-quality image interpolation',
    renderer:'New painted nocturnal ocean with original procedural marine animation',
    layout:{art_direction:'Original painted nocturnal marine valley; the 3D aquarium directions are abandoned',
      duration_seconds:DURATION,background_source_dimensions:[reef.naturalWidth,reef.naturalHeight],original_generated_backgrounds:1,original_generated_sprites:1,source_images:2,
      asset_generation_calls:2,video_generation_calls:0,algrow_calls:0,runtime_network_calls:0,
      fish_total:fish.length,fish_schools:8,shark_silhouettes:2,jellyfish:3,marine_snow:240,
      motion:'Stateless integer-periodic harmonics; slow framing drift, independent pulsing and tentacles',
      asset_reused_for_all_frames:true},
    diagnostics:{sample(t){const a=phase(t);return {time:t,phase:a,
      fish: wildlife(t).map(f=>({x:f.x,y:f.y,sign:f.sign,visible:waterVisibility(f.x,f.y)})),
      jellies:jellySettings.map(j=>({x:j.x+.010*Math.sin(a+j.p),y:j.y+.009*Math.sin(2*a+j.p),pulse:1+.035*Math.sin(a*50+j.p)}))};}},
  };
  let playing=true,playbackTime=0,last=performance.now();
  const seek=document.getElementById('seek'),play=document.getElementById('play'),clock=document.getElementById('time');
  play?.addEventListener('click',()=>{playing=!playing;play.textContent=playing?'Pause':'Lire';last=performance.now();});
  seek?.addEventListener('input',()=>{playbackTime=Number(seek.value);render(playbackTime);});
  function tick(now){const delta=Math.min(.1,(now-last)/1000);last=now;if(playing){playbackTime=(playbackTime+delta)%DURATION;render(playbackTime);if(seek)seek.value=playbackTime;if(clock)clock.textContent=`${Math.floor(playbackTime/60)}:${String(Math.floor(playbackTime%60)).padStart(2,'0')}`;}if(!window.__CAPTURE_MODE__)requestAnimationFrame(tick);}
  render(0);if(!window.__CAPTURE_MODE__)requestAnimationFrame(tick);
}
Promise.all([reef.decode(),jellyImage.decode()]).then(ready).catch(error=>{setTimeout(()=>{throw new Error('An original offline image failed to load: '+error.message);});});
