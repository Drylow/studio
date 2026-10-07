import * as THREE from 'three';
import DATA from './assets/simulation.json';
import {PIXEL_WIDTH,PIXEL_HEIGHT,createPixelView} from './pixel.mjs';
import {createChef} from './chef.mjs';
import {createCrazyTools} from './props.mjs';
const canvas=document.getElementById('chocolate-canvas');
const renderer=new THREE.WebGLRenderer({antialias:false,alpha:false,preserveDrawingBuffer:true});
renderer.setSize(PIXEL_WIDTH,PIXEL_HEIGHT,false);renderer.setPixelRatio(1);
renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.shadowMap.enabled=true;
renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.25;
const pixel=createPixelView(canvas),scene=new THREE.Scene();scene.background=new THREE.Color('#f1e7d6');
const camera=new THREE.PerspectiveCamera(37,1080/1920,.1,100);
scene.add(new THREE.HemisphereLight('#fff4df','#99a98b',2.2));
const key=new THREE.DirectionalLight('#fff3de',3.4);key.position.set(-4,10,5);key.castShadow=true;
key.shadow.mapSize.set(1024,1024);Object.assign(key.shadow.camera,{left:-7,right:7,top:11,bottom:-7});
key.shadow.normalBias=.022;key.shadow.bias=-.0002;key.shadow.radius=4;scene.add(key);
const rim=new THREE.DirectionalLight('#e6efce',1.3);rim.position.set(5,4,-4);scene.add(rim);
const ground=new THREE.Mesh(new THREE.PlaneGeometry(200,200),new THREE.MeshStandardMaterial({color:'#f1e7d6',roughness:.95}));ground.rotation.x=-Math.PI/2;ground.receiveShadow=true;scene.add(ground);
function box(size,pos,color,roughness=.7){
 const material=color==='#def2e1'?new THREE.MeshBasicMaterial({color,toneMapped:false}):new THREE.MeshStandardMaterial({color,roughness});
 const m=new THREE.Mesh(new THREE.BoxGeometry(...size),material);m.position.set(...pos);m.castShadow=true;m.receiveShadow=true;return m;
}
const board=new THREE.Group();board.add(box([7.1,.34,5.3],[0,.17,0],'#c99561'));
for(let i=0;i<14;i++){
 board.add(box([7.08,.003,.37],[0,.343,-2.46+i*.379],['#c99765','#ce9d6d','#c89460','#d1a072'][i%4]));
 for(let j=0;j<4;j++)board.add(box([.55+(i*3+j*7)%9*.14,.004,.006],[-2.65+j*1.75+(i%3)*.06,.347,-2.46+i*.379+(j%3-.8)*.08],'#b78355'));
}scene.add(board);
const fork=new THREE.Group();scene.add(fork);
fork.add(box([1.35,.12,.82],[0,.41,0],'#244c37'));
fork.add(box([.36,1.1,.30],[0,.95,0],'#b7c2ba'));
fork.add(box([.075,1.05,.025],[.13,.95,.16],'#def2e1'));
fork.add(box([1.90,.48,.32],[0,1.59,0],'#b7c2ba'));
for(const x of [-.75,-.25,.25,.75]){
 const tooth=new THREE.Mesh(new THREE.ConeGeometry(.198,1.2,4),new THREE.MeshStandardMaterial({color:'#b7c2ba',roughness:.45,metalness:.3}));
 tooth.rotation.y=Math.PI/4;tooth.position.set(x,2.35,0);tooth.castShadow=true;tooth.receiveShadow=true;fork.add(tooth);
}
const poseChef=createChef(scene,box);
const poseTools=createCrazyTools(scene,box);
const material=new THREE.MeshStandardMaterial({color:'#704530',roughness:.73,flatShading:true});
material.onBeforeCompile=s=>{
 s.vertexShader='attribute vec3 chocolateRest; attribute float fractureFace; varying vec3 vRest; varying float vFracture;\n'+s.vertexShader;
 s.vertexShader=s.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvRest=chocolateRest;vFracture=fractureFace;');
 s.fragmentShader='varying vec3 vRest; varying float vFracture;\n'+s.fragmentShader;
 s.fragmentShader=s.fragmentShader.replace('#include <color_fragment>',`#include <color_fragment>
 if(vFracture>.5){diffuseColor.rgb*=1.20+.08*sin(vRest.x*31.+vRest.z*39.);}
 else if(vRest.y>.087){
  vec2 tile=fract((vRest.xz+vec2(1.9,1.35))/vec2(.95,.90));
  float seam=min(min(tile.x,1.-tile.x),min(tile.y,1.-tile.y));
  diffuseColor.rgb*=seam<.05?.48:1.0+.30*(1.-tile.y);
 }
 `);
};
const V=a=>new THREE.Vector3(...a),groups=[],intacts=[],pieces=[];
function meshFor(p){
 const center=V(p.center),positions=[],rest=[],fracture=[];
 for(const face of p.faces)for(let j=1;j<face.points.length-1;j++)for(const a of [face.points[0],face.points[j],face.points[j+1]]){
  positions.push(...V(a).sub(center).toArray());rest.push(...a);fracture.push(face.kind==='fracture'?1:0);
 }
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
 g.setAttribute('chocolateRest',new THREE.Float32BufferAttribute(rest,3));g.setAttribute('fractureFace',new THREE.Float32BufferAttribute(fracture,1));g.computeVertexNormals();
 const m=new THREE.Mesh(g,material);m.castShadow=true;m.receiveShadow=true;return m;
}
// One persistent world. Trial data selects the food; all transforms are absolute.
for(const trial of DATA.trials){
 const group=new THREE.Group();scene.add(group);groups.push(group);
 const whole=[],broken=[];
 for(const bar of trial.bars){
  const g=new THREE.BoxGeometry(...DATA.size).toNonIndexed(),rest=g.attributes.position.array;
  g.setAttribute('chocolateRest',new THREE.Float32BufferAttribute(rest.slice(),3));g.setAttribute('fractureFace',new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count),1));
  const m=new THREE.Mesh(g,material);m.castShadow=true;m.receiveShadow=true;group.add(m);whole.push(m);
  const parts=bar.ids.map(id=>{const m=meshFor(DATA.geometries[id]);group.add(m);return m;});broken.push(parts);
 }intacts.push(whole);pieces.push(broken);
}
const smooth=v=>{v=Math.max(0,Math.min(1,v));return v*v*(3-2*v);};
const qa=new THREE.Quaternion(),qb=new THREE.Quaternion();
function setPose(mesh,p,q,mix){mesh.position.set(p[0]+(q[0]-p[0])*mix,p[1]+(q[1]-p[1])*mix,p[2]+(q[2]-p[2])*mix);qa.set(...p.slice(3));qb.set(...q.slice(3));mesh.quaternion.copy(qa.slerp(qb,mix));}
function renderAt(input){
 const time=Math.max(0,Math.min(input,DATA.duration-1/60)),index=DATA.trials.findLastIndex(s=>time>=s.start),trial=DATA.trials[index];
 const outro=time>=DATA.outroStart,t=Math.min(time-trial.start,trial.length-1/120),f=t*DATA.fps,a=Math.floor(f),b=a+1,mix=f-a;
 fork.visible=trial.tool==='fork';poseTools(trial.tool,t);
 groups.forEach((g,i)=>g.visible=i===index);
 const carry=index===0&&t<.72?-5*(1-smooth(t/.72)):0;
 groups[index].position.set(carry,0,0);
 trial.bars.forEach((bar,i)=>{
  const broken=t>=bar.hit,frames=bar.frames,pa=frames[Math.min(a,frames.length-1)],pb=frames[Math.min(b,frames.length-1)];
  intacts[index][i].visible=!broken;pieces[index][i].forEach(m=>m.visible=broken);
  if(!broken)setPose(intacts[index][i],pa[0],pb.length===1?pb[0]:pa[0],pb.length===1?mix:0);
  else pieces[index][i].forEach((m,j)=>{
   const first=Math.ceil(bar.hit*DATA.fps-1e-7),ia=Math.max(first,a),ib=Math.max(first,b);
   setPose(m,frames[Math.min(ia,frames.length-1)][j],frames[Math.min(ib,frames.length-1)][j],ia===a?mix:0);
  });
 });
 const clear=smooth((t-(trial.length-.38))/.26);
 if(index<DATA.trials.length-1)groups[index].position.x+=clear*10;
 const lastHit=trial.bars.filter(b=>t>=b.hit).at(-1)?.hit??-99,age=t-lastHit;
 const stack=Math.max(0,trial.count-4)*.32,anticipation=1-smooth((t-1.4)/1.2);
 const radius=(trial.tool==='glove'?25:20.5)+stack*anticipation+1.3*smooth((t-2.3)/.8),theta=.75+Math.sin(time*.18)*.025;
 const shake=age>=0&&age<.12?Math.sin(age*185)*(trial.tool==='fork'?.025:.10)*(1-age/.12):trial.tool==='jackhammer'&&t>=.98&&t<2.3?Math.sin(t*138)*.018:0;
 camera.position.set(Math.sin(theta)*radius+shake,11.5+stack*.25*anticipation,Math.cos(theta)*radius);
 camera.lookAt(0,3.25+stack*.20*anticipation,0);
 const anchor=poseChef({time:outro?time-DATA.outroStart:t,first:index===0,outro,base:trial.base}).project(camera);
 renderer.render(scene,camera);
 pixel(renderer.domElement,trial.count,index,outro,outro?{time:time-DATA.outroStart,x:(anchor.x+1)*PIXEL_WIDTH/2,y:(1-anchor.y)*PIXEL_HEIGHT/2}:null,trial.tool);
 canvas.dataset.trial=String(trial.count);canvas.dataset.broken=String(trial.bars.filter(b=>t>=b.hit).length);
 canvas.dataset.tool=trial.tool;
}
window.drawChocolate=renderAt;window.addEventListener('hf-seek',e=>renderAt(e.detail.time));renderAt(window.__hfThreeTime||0);
