import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { createCreatures } from './creatures-3d.mjs';
import { applyVertexLighting } from './vertex-lighting.mjs';

// An original first-person dive. Terrain and creatures are actual mesh volumes.
const WIDTH=1920, HEIGHT=1080, DURATION=24;
const film=document.getElementById('film');
const renderer=new THREE.WebGLRenderer({canvas:film,antialias:false,alpha:false,preserveDrawingBuffer:true});
renderer.setSize(WIDTH,HEIGHT,false); renderer.setPixelRatio(1);
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=1.35;
const scene=new THREE.Scene();
scene.background=new THREE.Color('#092b35'); scene.fog=new THREE.FogExp2('#092b35',.048);
const camera=new THREE.PerspectiveCamera(66,WIDTH/HEIGHT,.12,130); scene.add(camera);
scene.add(new THREE.HemisphereLight('#6ca7a0','#332532',2.45));
const overhead=new THREE.DirectionalLight('#8791b9',1.7); overhead.position.set(-9,17,5); scene.add(overhead);
const lamp=new THREE.SpotLight('#efdeb1',65,42,.70,.64,1.65);
lamp.position.set(.45,-.4,-.6); lamp.target.position.set(.4,-1.4,-20); camera.add(lamp,lamp.target);
const fill=new THREE.PointLight('#b7d9cf',3,14,1.6); fill.position.set(0,-.4,-1.0); camera.add(fill);

function random(seed){let s=seed>>>0;return()=>{s=(Math.imul(s,1664525)+1013904223)>>>0;return s/4294967296;};}
const rng=random(91347), clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const smooth=(a,b,x)=>{const q=clamp((x-a)/(b-a));return q*q*(3-2*q);};
const terrainMat=new THREE.MeshLambertMaterial({vertexColors:true,flatShading:true});
const ground=(x,z)=>-7.2+.015*z+.6*Math.sin(x*.22+z*.08)+.3*Math.cos(z*.3);

// Faceted ground and merged rock volumes: rich parallax with few draw calls.
const p=[],c=[];
function face(a,b,d,color){p.push(...a,...b,...d);for(let i=0;i<3;i++)c.push(color.r,color.g,color.b);}
const grid=[];
for(let iz=0;iz<=35;iz++){
  grid[iz]=[];for(let ix=0;ix<=20;ix++){
    const x=(ix-10)*3.5+(rng()-.5)*1.1,z=20-iz*3.2+(rng()-.5)*1.0;
    grid[iz][ix]=[x,ground(x,z)+(rng()-.5)*.36,z];
  }
}
for(let iz=0;iz<35;iz++)for(let ix=0;ix<20;ix++){
  const a=grid[iz][ix],b=grid[iz+1][ix],d=grid[iz][ix+1],e=grid[iz+1][ix+1];
  const tone=new THREE.Color().setHSL(.50+rng()*.05,.13+rng()*.08,.20+rng()*.08);
  face(a,d,b,tone);face(b,d,e,tone.clone().multiplyScalar(.86+rng()*.25));
}
const floor=new THREE.BufferGeometry(); floor.setAttribute('position',new THREE.Float32BufferAttribute(p,3));
floor.setAttribute('color',new THREE.Float32BufferAttribute(c,3));floor.computeVertexNormals();
scene.add(new THREE.Mesh(floor,terrainMat));
const rockParts=[];
function rock(x,z,width,height,length,shade){
  const g=new THREE.IcosahedronGeometry(1,0);
  g.scale(width,height,length);g.rotateY(rng()*Math.PI);g.rotateZ((rng()-.5)*.4);
  g.translate(x,ground(x,z)+height*.60,z); const count=g.attributes.position.count, colors=[];
  for(let i=0;i<count;i+=3){
    const col=new THREE.Color(shade).multiplyScalar(.78+rng()*.46);
    for(let k=0;k<3;k++)colors.push(col.r,col.g,col.b);
  }
  g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));g.computeVertexNormals();rockParts.push(g);
}
for(let i=0;i<76;i++){
  const side=i%2?1:-1,z=17-rng()*111;
  rock(side*(9+rng()*8),z,3+rng()*4.4,4+rng()*10,3+rng()*5,['#50566c','#4f625e','#57536a','#405555'][i%4]);
}
for(let i=0;i<38;i++)rock((rng()-.5)*16,12-rng()*100,.45+rng()*1.5,.35+rng()*1.1,.7+rng()*1.8,'#52626a');
// Uneven near banks create passage and occlusion, not a side-on display stage.
for(const [x,z,w,h,l]of[[-6,7,2.8,5.5,4.0],[6,-2,3.0,7,3.8],[-6.8,-14,3.2,8,4],[7.5,-25,3.5,10,4],[-7,-36,3.2,8,4]])rock(x,z,w,h,l,'#55516a');
for(const [x,z]of[[-11,-9],[11,-21],[-12,-35]])rock(x,z,7,2.8,6.5,'#49536b');
const rocks=mergeGeometries(rockParts,false);rockParts.forEach(g=>g.dispose());
scene.add(new THREE.Mesh(rocks,terrainMat));

const animals=createCreatures(THREE);scene.add(animals.angler,animals.jelly,animals.fishSchool);
const dustArray=new Float32Array(360*3),dustOrigins=[];
for(let i=0;i<360;i++){const a=[(rng()-.5)*26,-6+rng()*11,16-rng()*78];dustOrigins.push(a);dustArray.set(a,i*3);}
const dustGeo=new THREE.BufferGeometry();dustGeo.setAttribute('position',new THREE.BufferAttribute(dustArray,3));
const speck=document.createElement('canvas');speck.width=speck.height=32;
const speckCtx=speck.getContext('2d'),speckGlow=speckCtx.createRadialGradient(16,16,1,16,16,15);
speckGlow.addColorStop(0,'rgba(255,255,255,.9)');speckGlow.addColorStop(.35,'rgba(255,255,255,.6)');speckGlow.addColorStop(1,'rgba(255,255,255,0)');
speckCtx.fillStyle=speckGlow;speckCtx.fillRect(0,0,32,32);
scene.add(new THREE.Points(dustGeo,new THREE.PointsMaterial({color:'#adc7ae',map:new THREE.CanvasTexture(speck),size:.048,transparent:true,opacity:.49,depthWrite:false,sizeAttenuation:true})));
const vertexLighting=applyVertexLighting(THREE,scene,camera);

function render(t){
  if(!Number.isFinite(t))throw new Error('A finite time in seconds is required.');t=clamp(t,0,DURATION);
  const x=.65*Math.sin(t*.14),y=-2.8-.035*t+.055*Math.sin(t*.62),z=12-1.8*t;
  camera.position.set(x,y,z);
  camera.lookAt(x+.36*Math.sin(t*.24),y-.35-.18*Math.sin(t*.16),z-13);
  camera.rotateZ(.012*Math.sin(t*.42));
  lamp.target.position.set(.5+1.7*Math.sin(t*.18),-1.6,-21);
  animals.update(t);
  animals.angler.position.set(-16+(t-6)*2.3,-3.15+.18*Math.sin(t*.8),-16.2+.17*(t-9));
  animals.angler.rotation.set(0,-.36+.10*Math.sin(t*.3),.035*Math.sin(t*.65));animals.angler.scale.setScalar(.78);
  animals.angler.visible=t>=6&&t<=17;
  animals.jelly.position.set(-2.4,-1.4,-32);animals.jelly.rotation.y=.25+t*.09;
  animals.jelly.visible=t>=14;
  animals.fishSchool.position.set(-3.6+.65*t,-2.5,0);animals.fishSchool.rotation.y=.35;animals.fishSchool.scale.setScalar(.70);
  animals.fishSchool.visible=t<=10;
  const arr=dustGeo.attributes.position.array;
  for(let i=0;i<dustOrigins.length;i++){
    const a=dustOrigins[i];arr[i*3]=a[0]+.12*Math.sin(t*.35+i);arr[i*3+1]=a[1]+.14*Math.sin(t*.4+i*.3);arr[i*3+2]=a[2]+.03*t;
  }
  dustGeo.attributes.position.needsUpdate=true;
  // Small exposure fade preserves original colours without another full-screen pass.
  renderer.toneMappingExposure=1.35*(.04+.96*smooth(0,.65,t)*(1-.95*smooth(23.2,24,t)));
  vertexLighting.update();renderer.render(scene,camera);
  return{time:t,drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,camera:[x,y,z]};
}
window.DeepSeaFilm={render,duration:DURATION,width:WIDTH,height:HEIGHT,renderer:'Original 3D faceted meshes, first-person camera, native WebGL output'};
let playing=true,playbackTime=0,last=performance.now();
const seek=document.getElementById('seek'),play=document.getElementById('play'),clock=document.getElementById('time');
if(seek)seek.max=DURATION;
play?.addEventListener('click',()=>{playing=!playing;play.textContent=playing?'Pause':'Lire';last=performance.now();});
seek?.addEventListener('input',()=>{playbackTime=Number(seek.value);render(playbackTime);});
function tick(now){const delta=Math.min(1,(now-last)/1000);last=now;if(playing){playbackTime+=delta;if(playbackTime>DURATION)playbackTime=0;render(playbackTime);if(seek)seek.value=playbackTime;if(clock)clock.textContent=`0:${String(Math.floor(playbackTime)).padStart(2,'0')}`;}if(!window.__CAPTURE_MODE__)requestAnimationFrame(tick);}
if(!window.__CAPTURE_MODE__)requestAnimationFrame(tick);else render(0);
