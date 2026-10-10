import * as THREE from 'three';
import { createSleepCreatures } from './sleep-creatures.mjs';
import { createSleepEnvironment } from './sleep-environment.mjs';
import { applyVertexLighting } from './vertex-lighting.mjs';
import { addSleepSurfaceDetail } from './sleep-surfaces.mjs';

// One uncut, periodic expedition. No stock image, game mesh, or generation API.
const WIDTH=1920, HEIGHT=1080, DURATION=300, TAU=Math.PI*2, RADIUS=26;
const phase=t=>((t%DURATION)+DURATION)%DURATION/DURATION*TAU;
const canvas=document.getElementById('film');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true});
renderer.setPixelRatio(1);renderer.setSize(WIDTH,HEIGHT,false);
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.36;
const scene=new THREE.Scene();
scene.background=new THREE.Color('#0a2630');scene.fog=new THREE.FogExp2('#0a2630',.031);
const camera=new THREE.PerspectiveCamera(64,WIDTH/HEIGHT,.12,150);scene.add(camera);
scene.add(new THREE.HemisphereLight('#8ca7af','#464448',3.4));
const sun=new THREE.DirectionalLight('#92a6ad',2.25);sun.position.set(-18,28,12);scene.add(sun);
const lamp=new THREE.SpotLight('#e4dec5',135,48,.79,.75,1.6);
lamp.position.set(.45,-.35,-.65);lamp.target.position.set(.4,-2.8,-23);camera.add(lamp,lamp.target);
const fill=new THREE.PointLight('#8eb9c2',7,18,1.5);fill.position.set(0,-.35,-1);camera.add(fill);

// Ripple height is also the collision surface: mesh and checker share one ground.
const ground=(x,z)=>-7.5+.28*Math.sin(x*.13+z*.09)+.16*Math.cos(z*.17)+.045*Math.sin(x*1.6+.25*Math.cos(z*.6));
function cameraPosition(t){const a=phase(t);return new THREE.Vector3(RADIUS*Math.sin(a),-2.8+.22*Math.sin(a*2),RADIUS*Math.cos(a));}
const animals=createSleepCreatures(THREE,{duration:DURATION});
for(const root of Object.values(animals.roots))scene.add(root);
const up=new THREE.Vector3(0,1,0);
function faceTangent(root,dx,dy,dz,roll=0){
  root.rotation.set(0,Math.atan2(-dz,dx),Math.atan2(dy,Math.hypot(dx,dz))+roll);
}
function placeAnimals(t){
  const a=phase(t), localTime=a/TAU*DURATION;animals.update(localTime);
  const r=animals.roots;
  if(r.angler){
    const q=2*a+.40;
    r.angler.position.set(22*Math.sin(q),-2.15+.35*Math.sin(3*a),22*Math.cos(q));
    faceTangent(r.angler,Math.cos(q),.023*Math.cos(3*a),-Math.sin(q),.025*Math.sin(8*a));
    r.angler.scale.setScalar(.82);
  }
  if(r.jelly){
    r.jelly.position.set(27*Math.sin(1.60)+.7*Math.sin(2*a),-.9+.28*Math.sin(4*a),27*Math.cos(1.60)+.55*Math.cos(2*a));
    r.jelly.rotation.set(.045*Math.sin(3*a),.5+.1*Math.sin(a),.045*Math.sin(2*a));
    r.jelly.scale.setScalar(.94);
  }
  if(r.jelly2){
    r.jelly2.position.set(28*Math.sin(4.20)+.45*Math.sin(3*a),-.75+.2*Math.sin(5*a+.8),28*Math.cos(4.20)+.45*Math.cos(3*a));
    r.jelly2.rotation.set(.035*Math.sin(2*a),-.4+.1*Math.cos(a),.05*Math.sin(3*a));r.jelly2.scale.setScalar(.67);
  }
  for(const [name,radius,cycles,offset,y,scale]of[['school1',30,2,2.8,.20,.60],['school2',18.5,1,3.7,-1.15,.49]]){
    if(!r[name])continue;const q=cycles*a+offset;
    r[name].position.set(radius*Math.sin(q),y+.35*Math.sin(3*a+offset),radius*Math.cos(q));
    faceTangent(r[name],Math.cos(q),0,-Math.sin(q),.03*Math.sin(6*a));r[name].scale.setScalar(scale);
  }
  for(const [name,offset,y,scale]of[['ray1',1.2,.35,.90],['ray2',3.6,-.6,.73]]){
    if(!r[name])continue;const q=a+offset;
    r[name].position.set(28*Math.sin(q),y+.6*Math.sin(2*a+offset),19*Math.cos(q));
    faceTangent(r[name],28*Math.cos(q),1.2*Math.cos(2*a+offset),-19*Math.sin(q),.065*Math.sin(3*a+offset));r[name].scale.setScalar(scale);
  }
  for(const root of Object.values(r))root.visible=true;
}

// Prepare solid decoration around the actual moving meshes, not model centres.
// At 2Hz the 0.7m padding exceeds the maximum displacement between samples.
const reserved=[];
for(let frame=0;frame<=DURATION*2;frame++){
  const t=frame/2;placeAnimals(t);
  for(const root of Object.values(animals.roots)){
    root.updateWorldMatrix(true,true);reserved.push(new THREE.Box3().setFromObject(root,true).expandByScalar(.70));
  }
  const p=cameraPosition(t);reserved.push(new THREE.Box3(p.clone(),p.clone()).expandByScalar(1));
}
const clearance={intersects:box=>reserved.some(zone=>zone.intersectsBox(box))};
const environment=createSleepEnvironment(THREE,{ground,clearance,seed:725903,radius:RADIUS});scene.add(environment.group);
placeAnimals(0);

let seed=181934;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
const count=2200, origins=[], dust=new Float32Array(count*3);
for(let i=0;i<count;i++){
  const a=random()*TAU,r=Math.sqrt(random())*56;
  const p=[r*Math.sin(a),-6+random()*16,r*Math.cos(a)];origins.push(p);dust.set(p,i*3);
}
const dustGeo=new THREE.BufferGeometry();dustGeo.setAttribute('position',new THREE.BufferAttribute(dust,3));
const speck=document.createElement('canvas');speck.width=speck.height=32;
const ctx=speck.getContext('2d'),gradient=ctx.createRadialGradient(16,16,0,16,16,15);
gradient.addColorStop(0,'rgba(220,236,231,.7)');gradient.addColorStop(.35,'rgba(220,236,231,.3)');gradient.addColorStop(1,'rgba(220,236,231,0)');
ctx.fillStyle=gradient;ctx.fillRect(0,0,32,32);
scene.add(new THREE.Points(dustGeo,new THREE.PointsMaterial({map:new THREE.CanvasTexture(speck),color:'#9fb5b8',size:.045,opacity:.42,transparent:true,depthWrite:false})));
const lighting=applyVertexLighting(THREE,scene,camera);
const surfaces=addSleepSurfaceDetail(THREE,environment.group);
const layout={duration_seconds:DURATION,continuous_camera_circuit:true,clearance_sample_hz:2,clearance_margin:.7,reserved_volumes:reserved.length,environment:environment.summary,creatures:animals.summary,surfaces};

function update(t){
  if(!Number.isFinite(t))throw new Error('A finite time in seconds is required.');
  const a=phase(t);placeAnimals(t);environment.update?.(a/TAU*DURATION);
  camera.position.copy(cameraPosition(t));camera.up.copy(up);
  const look=camera.position.clone().add(new THREE.Vector3(12*Math.cos(a)-2.5*Math.sin(a),-1.6+.12*Math.sin(2*a),-12*Math.sin(a)-2.5*Math.cos(a)));
  camera.lookAt(look);camera.rotateZ(.004*Math.sin(3*a));
  lamp.target.position.set(.4+.32*Math.sin(2*a),-2.8+.15*Math.sin(3*a),-23);
  for(let i=0;i<count;i++){
    const p=origins[i];dust[i*3]=p[0]+.35*Math.sin(a*3+i*1.1);dust[i*3+1]=p[1]+.26*Math.sin(a*5+i*.3);dust[i*3+2]=p[2]+.3*Math.cos(a*3+i*.9);
  }
  dustGeo.attributes.position.needsUpdate=true;
  lighting.update();
}
function render(t){
  update(t);renderer.render(scene,camera);
  return {time:t,drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,camera:camera.position.toArray()};
}
window.DeepSeaFilm={render,duration:DURATION,width:WIDTH,height:HEIGHT,antialias:renderer.getContext().getContextAttributes().antialias,renderer:'Original periodic 3D abyssal basin, benthic detail, locally deforming creatures, native antialiased WebGL',layout};
if(window.__DEEPSEA_DIAGNOSTICS__){
  window.DeepSeaFilm.diagnostics={
    ground,
    groundMaximum:-7.015,
    rockBoxes:environment.rockBoxes.map(box=>({min:box.min.toArray(),max:box.max.toArray()})),
    sample(t){
      placeAnimals(t);environment.update?.(phase(t)/TAU*DURATION);
      const bounds={};
      for(const [name,root]of Object.entries(animals.roots)){
        root.updateWorldMatrix(true,true);const box=new THREE.Box3().setFromObject(root,true);
        bounds[name]={min:box.min.toArray(),max:box.max.toArray(),visible:root.visible};
      }
      return {time:t,bounds,camera:cameraPosition(t).toArray()};
    },
    vertices(t){
      placeAnimals(t);const result={},p=new THREE.Vector3();
      for(const [name,root]of Object.entries(animals.roots)){
        const values=[];root.updateWorldMatrix(true,true);
        root.traverse(mesh=>{if(!mesh.isMesh)return;const attr=mesh.geometry.attributes.position;
          for(let i=0;i<attr.count;i++){p.fromBufferAttribute(attr,i).applyMatrix4(mesh.matrixWorld);values.push(p.x,p.y,p.z);}
        });result[name]=values;
      }
      return result;
    },
  };
}
let playing=true,playbackTime=0,last=performance.now();
const seek=document.getElementById('seek'),play=document.getElementById('play'),clock=document.getElementById('time');
play?.addEventListener('click',()=>{playing=!playing;play.textContent=playing?'Pause':'Lire';last=performance.now();});
seek?.addEventListener('input',()=>{playbackTime=Number(seek.value);render(playbackTime);});
function tick(now){
  const delta=Math.min(.1,(now-last)/1000);last=now;
  if(playing){playbackTime=(playbackTime+delta)%DURATION;render(playbackTime);if(seek)seek.value=playbackTime;if(clock)clock.textContent=`${Math.floor(playbackTime/60)}:${String(Math.floor(playbackTime%60)).padStart(2,'0')}`;}
  if(!window.__CAPTURE_MODE__)requestAnimationFrame(tick);
}
if(!window.__CAPTURE_MODE__)requestAnimationFrame(tick);else render(0);
