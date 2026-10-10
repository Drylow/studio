import * as THREE from 'three';
import { createSleepShoals } from './sleep-shoals.mjs';
import { createSleepSharks } from './sleep-sharks.mjs';
import { createSleepJellies } from './sleep-jellies.mjs';
import { createCinematicEnvironment } from './sleep-cinematic-environment.mjs';
import { createSleepAtmosphere } from './sleep-atmosphere.mjs';
import { applyVertexLighting } from './vertex-lighting.mjs';
import { addSleepSurfaceDetail } from './sleep-surfaces.mjs';
import { addMarineSurfaceDetail } from './sleep-marine-surfaces.mjs';

// New cinematic art direction. The rejected faceted basin remains in sleep-scene.mjs.
const WIDTH=1920, HEIGHT=1080, DURATION=300, TAU=Math.PI*2, RADIUS=26;
const phase=t=>((t%DURATION)+DURATION)%DURATION/DURATION*TAU;
const canvas=document.getElementById('film');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true});
renderer.setPixelRatio(1);renderer.setSize(WIDTH,HEIGHT,false);
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;
const scene=new THREE.Scene();
scene.background=new THREE.Color('#051725');scene.fog=new THREE.FogExp2('#051725',.030);
const camera=new THREE.PerspectiveCamera(58,WIDTH/HEIGHT,.15,150);scene.add(camera);
scene.add(new THREE.HemisphereLight('#527494','#071421',1.25));
const key=new THREE.DirectionalLight('#6cacd2',2.40);key.position.set(-28,19,-15);scene.add(key);
const lamp=new THREE.SpotLight('#779faa',24,48,.76,.87,1.6);
lamp.position.set(.4,-.15,-.6);lamp.target.position.set(.1,-.05,-23);camera.add(lamp,lamp.target);
const fill=new THREE.PointLight('#527e9d',3.5,22,1.5);fill.position.set(-.6,.45,-1.5);camera.add(fill);
const ground=(x,z)=>-9+.25*Math.sin(x*.11+z*.07)+.32*Math.cos(z*.12-x*.035)+.055*Math.sin(x*.86+z*.63);
function cameraPosition(t){const a=phase(t);return new THREE.Vector3(1.35*Math.sin(a),-1.85+.20*Math.sin(2*a),27.5+1.20*Math.cos(a));}
const shoals=createSleepShoals(THREE,{duration:DURATION});
const sharks=createSleepSharks(THREE,{duration:DURATION});
const jellies=createSleepJellies(THREE,{duration:DURATION});
const roots={...shoals.roots,...sharks.roots,...jellies.roots};
for(const root of Object.values(roots))scene.add(root);
function faceTangent(root,dx,dy,dz,roll=0){root.rotation.set(0,Math.atan2(-dz,dx),Math.atan2(dy,Math.hypot(dx,dz))+roll);}
function orbit(root,q,r,y,dq=1,dr=0,dy=0,scale=1,roll=0){
  root.position.set(r*Math.sin(q),y,r*Math.cos(q));
  faceTangent(root,dr*Math.sin(q)+r*dq*Math.cos(q),dy,dr*Math.cos(q)-r*dq*Math.sin(q),roll);root.scale.setScalar(scale);
}
function placeAnimals(t){
  const a=phase(t), localTime=a/TAU*DURATION;
  shoals.update(localTime);sharks.update(localTime);jellies.update(localTime);
  // A new nocturnal panorama: lateral passing wildlife, a hovering lens and
  // luminous jellyfish suspended across depth. No annular animal/camera convoy.
  for(let i=0;i<12;i++){
    const root=roots[`shoal${String(i+1).padStart(2,'0')}`],offset=i*.77;
    const p=(i%2===0?1:-1)*a+offset;
    const rx=13.5+(i%3)*2.5,rz=1.15+(i%3)*.38,z=[16,2,-12,-27][i%4];
    const x=rx*Math.sin(p),y=-2.9+(Math.floor(i/4))*4.1+.30*Math.sin(2*a+offset);
    root.position.set(x,y,z+rz*Math.cos(p));
    const sign=i%2===0?1:-1;
    faceTangent(root,sign*rx*Math.cos(p),.60*Math.cos(2*a+offset),-sign*rz*Math.sin(p),.025*Math.sin(3*a+offset));
    root.scale.setScalar(.36+(i%3)*.065);
  }
  for(const [name,offset,y,z,speed,scale]of [
    ['shark1',.6,-5.4,7.0,1,.96],['shark2',3.0,5.4,-11,-1,1.03],['shark3',1.8,.2,-25,2,1.10]]){
    const root=roots[name],p=speed*a+offset,rx=21,rz=2.0;
    root.position.set(rx*Math.sin(p),y+.18*Math.sin(3*a+offset),z+rz*Math.cos(p));
    faceTangent(root,rx*speed*Math.cos(p),.54*Math.cos(3*a+offset),-rz*speed*Math.sin(p),.022*Math.sin(3*a+offset));root.scale.setScalar(scale);
  }
  for(const[name,x,y,z,scale,offset]of[
    ['jellyA',3.8,.2,8.0,1.72,.3],['jellyB',-6.4,1.8,-6.0,1.34,1.4],['jellyC',8.1,10.7,-16.0,1.40,2.2]]){
    const root=roots[name];
    root.position.set(x+.72*Math.sin(a+offset),y+.45*Math.sin(2*a+offset),z+.35*Math.cos(3*a+offset));
    root.rotation.set(.065*Math.sin(2*a+offset),.12*Math.sin(a+offset),.045*Math.cos(3*a+offset));root.scale.setScalar(scale);
  }
  for(const root of Object.values(roots))root.visible=true;
}
placeAnimals(0);
// Actual new animated meshes reserve their passages before any solid scenery is placed.
const reserved=[];
for(let frame=0;frame<=DURATION*2;frame++){
  const t=frame/2;placeAnimals(t);
  for(const root of Object.values(roots)){
    root.updateWorldMatrix(true,true);reserved.push(new THREE.Box3().setFromObject(root,true).expandByScalar(.70));
  }
  const p=cameraPosition(t);reserved.push(new THREE.Box3(p.clone(),p.clone()).expandByScalar(1));
}
const clearance={intersects:box=>reserved.some(zone=>zone.intersectsBox(box))};
const environment=createCinematicEnvironment(THREE,{ground,clearance,seed:853971,radius:RADIUS});scene.add(environment.group);
const atmosphere=createSleepAtmosphere(THREE,{duration:DURATION,ground,radius:RADIUS,waterColor:'#051725',fogDensity:.030});scene.add(atmosphere.group);
const lighting=applyVertexLighting(THREE,scene,camera);
const surfaces=addSleepSurfaceDetail(THREE,environment.group,{cinematic:true});
const marineSurfaces=addMarineSurfaceDetail(THREE,roots);
const layout={art_direction:'Original nocturnal luminous-jelly panorama; previous game-like travelling basin rejected',duration_seconds:DURATION,
  continuous_camera_circuit:false,slow_hovering_camera:true,clearance_sample_hz:2,clearance_margin:.7,reserved_volumes:reserved.length,
  environment:environment.summary,shoals:shoals.summary,sharks:sharks.summary,jellies:jellies.summary,atmosphere:atmosphere.summary,surfaces,marineSurfaces};
function update(t){
  if(!Number.isFinite(t))throw new Error('A finite time in seconds is required.');
  const a=phase(t);placeAnimals(t);environment.update?.(a/TAU*DURATION);
  camera.position.copy(cameraPosition(t));camera.up.set(0,1,0);
  const look=new THREE.Vector3(.6*Math.sin(a+.5),.25+.16*Math.sin(2*a),-7);
  camera.lookAt(look);camera.rotateZ(.003*Math.sin(3*a));
  lamp.target.position.set(.1+.19*Math.sin(2*a),-.05+.09*Math.sin(3*a),-23);
  atmosphere.update(a/TAU*DURATION,camera);lighting.update();
}
function render(t){update(t);renderer.render(scene,camera);return {time:t,drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,camera:camera.position.toArray()};}
window.DeepSeaFilm={render,duration:DURATION,width:WIDTH,height:HEIGHT,antialias:renderer.getContext().getContextAttributes().antialias,
  renderer:'Original nocturnal jellyfish panorama, lateral marine passages and softly drifting lens',layout};
if(window.__DEEPSEA_DIAGNOSTICS__){
  function bounds(){const result={};for(const [name,root]of Object.entries(roots)){root.updateWorldMatrix(true,true);const box=new THREE.Box3().setFromObject(root,true);result[name]={min:box.min.toArray(),max:box.max.toArray(),visible:root.visible};}return result;}
  const projectionMatrix=new THREE.Matrix4(),frustum=new THREE.Frustum(),point=new THREE.Vector3();
  window.DeepSeaFilm.diagnostics={
    ground,groundMaximum:-8.375,
    rockBoxes:environment.rockBoxes.map(box=>({min:box.min.toArray(),max:box.max.toArray()})),
    sample(t){placeAnimals(t);environment.update?.(phase(t)/TAU*DURATION);return {time:t,bounds:bounds(),camera:cameraPosition(t).toArray()};},
    vertices(t){placeAnimals(t);const result={};for(const [name,root]of Object.entries(roots)){const values=[];root.updateWorldMatrix(true,true);root.traverse(mesh=>{if(!mesh.isMesh)return;const attr=mesh.geometry.attributes.position;for(let i=0;i<attr.count;i++){point.fromBufferAttribute(attr,i).applyMatrix4(mesh.matrixWorld);values.push(point.x,point.y,point.z);}});result[name]=values;}return result;},
    screenCoverage(t){
      update(t);camera.updateMatrixWorld(true);scene.updateMatrixWorld(true);
      projectionMatrix.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse);frustum.setFromProjectionMatrix(projectionMatrix);
      const fishLayout=shoals.layout(),groups=[];
      for(const [name,root]of Object.entries(roots)){
        const box=new THREE.Box3().setFromObject(root,true),center=box.getCenter(new THREE.Vector3()),distance=center.distanceTo(camera.position),projection=center.clone().project(camera);
        const kind=name.startsWith('shoal')?'fish-school':name.startsWith('shark')?'shark':'jellyfish';
        let left=1,right=-1,top=-1,bottom=1;
        for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){
          const p=new THREE.Vector3(x,y,z);if(p.clone().applyMatrix4(camera.matrixWorldInverse).z>=-.15)continue;p.project(camera);
          left=Math.min(left,p.x);right=Math.max(right,p.x);bottom=Math.min(bottom,p.y);top=Math.max(top,p.y);
        }
        const visible=frustum.intersectsBox(box)&&distance<48;
        const visibleAreaFraction=visible?Math.max(0,Math.min(1,right)-Math.max(-1,left))*Math.max(0,Math.min(1,top)-Math.max(-1,bottom))/4:0;
        const centerVisible=distance<48&&projection.z>=-1&&projection.z<=1&&Math.abs(projection.x)<=1&&Math.abs(projection.y)<=1;
        const individuals=fishLayout[name]?.length||1;
        const visibleIndividuals=fishLayout[name]?fishLayout[name].filter(fish=>{point.set(...fish.centre).applyMatrix4(root.matrixWorld);const d=point.distanceTo(camera.position);point.project(camera);return d<48&&point.z>=-1&&point.z<=1&&Math.abs(point.x)<=1&&Math.abs(point.y)<=1;}).length:Number(centerVisible);
        groups.push({name,kind,visible,visibleAreaFraction,distance,centerVisible,projection:projection.toArray(),individuals,visibleIndividuals,countMethod:'Projected individual centres within48m; no occlusion or pixel-visibility test'});
      }
      return {time:t,groups,camera:camera.position.toArray()};
    },
  };
}
let playing=true,playbackTime=0,last=performance.now();
const seek=document.getElementById('seek'),play=document.getElementById('play'),clock=document.getElementById('time');
play?.addEventListener('click',()=>{playing=!playing;play.textContent=playing?'Pause':'Lire';last=performance.now();});
seek?.addEventListener('input',()=>{playbackTime=Number(seek.value);render(playbackTime);});
function tick(now){const delta=Math.min(.1,(now-last)/1000);last=now;if(playing){playbackTime=(playbackTime+delta)%DURATION;render(playbackTime);if(seek)seek.value=playbackTime;if(clock)clock.textContent=`${Math.floor(playbackTime/60)}:${String(Math.floor(playbackTime%60)).padStart(2,'0')}`;}if(!window.__CAPTURE_MODE__)requestAnimationFrame(tick);}
if(!window.__CAPTURE_MODE__)requestAnimationFrame(tick);else render(0);
