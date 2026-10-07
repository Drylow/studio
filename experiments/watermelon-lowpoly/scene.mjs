import * as THREE from 'three';
import DATA from './assets/simulation.json';
import {PIXEL_WIDTH,PIXEL_HEIGHT,createPixelView} from './pixel.mjs';
const W=1080,H=1920;
const canvas=document.getElementById('fruit-canvas');
const renderer=new THREE.WebGLRenderer({antialias:false,alpha:false,preserveDrawingBuffer:true});
renderer.setSize(PIXEL_WIDTH,PIXEL_HEIGHT,false);renderer.setPixelRatio(1);
const drawPixelFrame=createPixelView(canvas);
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.25;
const scene=new THREE.Scene();scene.background=new THREE.Color('#f1e7d6');
const camera=new THREE.PerspectiveCamera(37,W/H,.1,100);
scene.add(new THREE.HemisphereLight('#fff4df','#99a98b',2.2));
const key=new THREE.DirectionalLight('#fff3de',3.4);key.position.set(-4,8,5);key.castShadow=true;
key.shadow.mapSize.set(1024,1024);key.shadow.camera.left=-7;key.shadow.camera.right=7;
key.shadow.camera.top=8;key.shadow.camera.bottom=-7;key.shadow.normalBias=.022;key.shadow.bias=-.0002;
key.shadow.radius=4;scene.add(key);
const rim=new THREE.DirectionalLight('#e6efce',1.3);rim.position.set(5,4,-4);scene.add(rim);
const ground=new THREE.Mesh(new THREE.PlaneGeometry(200,200),new THREE.MeshStandardMaterial({color:'#f1e7d6',roughness:.95}));
ground.rotation.x=-Math.PI/2;ground.receiveShadow=true;scene.add(ground);
function box(size,pos,color,roughness=.7){
 const m=new THREE.Mesh(new THREE.BoxGeometry(...size),new THREE.MeshStandardMaterial({color,roughness}));
 m.position.set(...pos);m.castShadow=true;m.receiveShadow=true;return m;
}
const board=new THREE.Group();board.add(box([7.1,.34,5.3],[0,.17,0],'#c99561'));
for(let i=0;i<14;i++){
 board.add(box([7.08,.003,.37],[0,.343,-2.46+i*.379],['#c99765','#ce9d6d','#c89460','#d1a072'][i%4]));
 for(let j=0;j<4;j++)board.add(box([.55+(i*3+j*7)%9*.14,.004,.006],[-2.65+j*1.75+(i%3)*.06,.347,-2.46+i*.379+(j%3-.8)*.08],'#b78355'));
}
scene.add(board);
const blade=new THREE.Group();
blade.add(box([.055,1.6,4.5],[0,0,0],'#b7c2ba',.25));
blade.add(box([.03,.06,4.52],[0,-.81,0],'#eef3e9',.2));
blade.add(box([.24,.38,1.6],[0,.52,2.93],'#203c2a',.5));
blade.add(box([.16,.42,.13],[0,.52,2.12],'#dfc79d',.3));
// A bounded pool supports overlapping throws in the teaser and 32-cut burst.
const knives=Array.from({length:12},()=>{
 const main=blade.clone(),echo=blade.clone();
 main.scale.setScalar(.78);echo.scale.setScalar(.78);
 echo.traverse(o=>{if(o.isMesh){o.material=o.material.clone();o.material.transparent=true;o.material.opacity=.12;o.material.depthWrite=false;o.castShadow=false;}});
 scene.add(main,echo);return {main,echo};
});
const seedsMat=new THREE.MeshStandardMaterial({color:'#352922',roughness:.7});
const seedGeometry=new THREE.IcosahedronGeometry(.045,1);
const skinMat=new THREE.MeshStandardMaterial({vertexColors:true,flatShading:true,roughness:.73});
const fleshMat=new THREE.MeshStandardMaterial({color:'#ed4b59',roughness:.82,flatShading:true});
fleshMat.onBeforeCompile=shader=>{
 shader.vertexShader='attribute vec3 fruitRest; varying vec3 vFruitPos;\n'+shader.vertexShader;
 shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvFruitPos=fruitRest;');
 shader.fragmentShader='varying vec3 vFruitPos;\n'+shader.fragmentShader;
 shader.fragmentShader=shader.fragmentShader.replace('#include <color_fragment>',`#include <color_fragment>
  float r=length(vFruitPos/vec3(1.55,1.65,1.55));
  if(r>.971)diffuseColor.rgb=vec3(.10,.24,.12);
  else if(r>.915)diffuseColor.rgb=vec3(.88,.90,.64);
  else diffuseColor.rgb*=.96+.04*sin(vFruitPos.x*11.+vFruitPos.z*9.);
 `);
};
const V=a=>new THREE.Vector3(...a);
const average=pts=>pts.reduce((s,p)=>s.add(p),new THREE.Vector3()).multiplyScalar(1/pts.length);
function normalized(p){return Math.sqrt((p.x/DATA.radii[0])**2+(p.y/DATA.radii[1])**2+(p.z/DATA.radii[2])**2)}
function createPiece(piece){
 const center=V(piece.center),group=new THREE.Group();const arrays={skin:[],flesh:[]},colors=[];
 for(const face of piece.faces){
  const pts=face.points.map(V),faceCenter=average(pts),tris=[];
  for(let j=1;j<pts.length-1;j++)tris.push([pts[0],pts[j],pts[j+1]]);
  const angle=Math.atan2(faceCenter.z,faceCenter.x),stripe=Math.sin(angle*10+Math.sin(faceCenter.y*4)*.28);
  const skinColor=new THREE.Color(stripe>-.2?'#6e9852':'#244c37');
  skinColor.multiplyScalar(.9+.12*(.5+.5*Math.sin(faceCenter.y*13+angle*17)));
  for(const tri of tris)for(const p of tri){
   arrays[face.kind==='skin'?'skin':'flesh'].push(...p.clone().sub(center).toArray());
   if(face.kind==='skin')colors.push(...skinColor.toArray());
  }
  if(face.kind==='flesh'){
   const normal=pts[1].clone().sub(pts[0]).cross(pts[2].clone().sub(pts[0])).normalize();
   const u=pts[1].clone().sub(pts[0]).normalize(),v=normal.clone().cross(u);
   for(let j=0;j<14;j++){
    const theta=j*2.3999632297,r=.24+Math.sqrt(j/14)*.85;
    const p=faceCenter.clone().addScaledVector(u,Math.cos(theta)*r).addScaledVector(v,Math.sin(theta)*r);
    const inside=pts.every((a,k)=>pts[(k+1)%pts.length].clone().sub(a).cross(p.clone().sub(a)).dot(normal)>=-1e-5);
    if(!inside||normalized(p)>.87)continue;
    const seed=new THREE.Mesh(seedGeometry,seedsMat);
    seed.scale.set(.7,1.4,.28);seed.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),normal);
    seed.position.copy(p.sub(center).addScaledVector(normal,.008));group.add(seed);
   }
  }
 }
 if(arrays.skin.length){
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(arrays.skin,3));g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));g.computeVertexNormals();
  const m=new THREE.Mesh(g,skinMat);m.castShadow=true;m.receiveShadow=true;group.add(m);
 }
 if(arrays.flesh.length){
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(arrays.flesh,3));g.computeVertexNormals();
  const m=new THREE.Mesh(g,fleshMat);m.castShadow=true;m.receiveShadow=true;group.add(m);
 }
 group.position.copy(center).add(V(piece.offset)).add(new THREE.Vector3(0,DATA.height,0));return group;
}
const fruit=new THREE.Group();scene.add(fruit);
const meshes=new Map(),batches=new Map();let activeStage='',activePose='';let parts=[],activeBatches=[];
function buildBatches(ids,prototypes){
 const bins=[skinMat,fleshMat,seedsMat].map(material=>({material,rest:[],normals:[],fruitRest:[],colors:[],owners:[]}));
 prototypes.forEach((group,owner)=>group.children.forEach(m=>{
  m.updateMatrix();const b=bins.find(b=>b.material===m.material),g=m.geometry.index?m.geometry.toNonIndexed():m.geometry;
  const a=g.attributes.position,n=g.attributes.normal,c=g.attributes.color;
  const normalMatrix=new THREE.Matrix3().getNormalMatrix(m.matrix),center=V(DATA.geometries[ids[owner]].center);
  for(let j=0;j<a.count;j++){
   const p=new THREE.Vector3().fromBufferAttribute(a,j).applyMatrix4(m.matrix);
   const normal=new THREE.Vector3().fromBufferAttribute(n,j).applyMatrix3(normalMatrix).normalize();
   b.rest.push(...p.toArray());b.normals.push(...normal.toArray());b.fruitRest.push(...p.clone().add(center).toArray());b.owners.push(owner);
   if(c)b.colors.push(c.getX(j),c.getY(j),c.getZ(j));
  }
 }));
 return bins.filter(b=>b.rest.length).map(b=>{
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(b.rest,3).setUsage(THREE.DynamicDrawUsage));
  g.setAttribute('normal',new THREE.Float32BufferAttribute(b.normals,3).setUsage(THREE.DynamicDrawUsage));
  g.setAttribute('fruitRest',new THREE.Float32BufferAttribute(b.fruitRest,3));
  if(b.colors.length)g.setAttribute('color',new THREE.Float32BufferAttribute(b.colors,3));
  const mesh=new THREE.Mesh(g,b.material);mesh.castShadow=true;mesh.receiveShadow=true;mesh.frustumCulled=false;
  return {...b,mesh};
 });
}
function mountStage(ids,key){
 if(activeStage===key)return;
 fruit.clear();parts=ids.map(id=>{
  if(!meshes.has(id))meshes.set(id,createPiece(DATA.geometries[id]));
  return meshes.get(id);
 });
 const geometryKey=ids.length;
 if(!batches.has(geometryKey))batches.set(geometryKey,buildBatches(ids,parts));
 activeBatches=batches.get(geometryKey);activeBatches.forEach(b=>fruit.add(b.mesh));activeStage=key;
}
const movingVertex=new THREE.Vector3(),movingNormal=new THREE.Vector3();
function updateBatches(){
 for(const b of activeBatches){
  const pos=b.mesh.geometry.attributes.position.array,norm=b.mesh.geometry.attributes.normal.array;
  for(let j=0;j<b.owners.length;j++){
   const p=j*3,g=parts[b.owners[j]];
   movingVertex.fromArray(b.rest,p).applyQuaternion(g.quaternion).add(g.position).toArray(pos,p);
   movingNormal.fromArray(b.normals,p).applyQuaternion(g.quaternion).toArray(norm,p);
  }
  b.mesh.geometry.attributes.position.needsUpdate=true;b.mesh.geometry.attributes.normal.needsUpdate=true;
 }
}
const poseA=new THREE.Quaternion(),poseB=new THREE.Quaternion(),yAxis=new THREE.Vector3(0,1,0);
function throwKnife(knife,i,age){
 const plane=DATA.planes[i],n=V(plane.n);
 if(Math.abs(n.y)>.9){
  knife.quaternion.setFromAxisAngle(new THREE.Vector3(0,0,1),Math.PI/2);
  knife.position.set(-age*80,DATA.height+plane.d,0);
 }else{
  knife.quaternion.setFromAxisAngle(yAxis,-Math.atan2(n.z,n.x));
  // Travel lies in the cut plane. No ease-in/out: a launched blade retains
  // its speed through the fruit and exits on the other side of the frame.
  const tangent=new THREE.Vector3(-n.z,0,n.x);
  knife.position.copy(n.multiplyScalar(plane.d)).addScaledVector(tangent,age*38);
  knife.position.y=DATA.height-age*60;
 }
}
function renderAt(input){
 const time=Math.max(0,Math.min(input,DATA.duration-1/60));
 const index=DATA.shots.findLastIndex(s=>time+1e-7>=s.start),shot=DATA.shots[index],t=Math.max(0,time-shot.start);
 const stage=shot.cutTimes.filter(c=>t>=c).length;
 const ids=shot.stages[stage];mountStage(ids,`${index}:${stage}`);
 if(t>=shot.release){
  const f=(t-shot.release)*DATA.fps,a=Math.min(Math.floor(f),shot.frames.length-1),b=Math.min(a+1,shot.frames.length-1),mix=f-a;
  parts.forEach((g,i)=>{const p=shot.frames[a][i],q=shot.frames[b][i];
   g.position.set(p[0]+(q[0]-p[0])*mix,p[1]+(q[1]-p[1])*mix,p[2]+(q[2]-p[2])*mix);
   poseA.set(...p.slice(3));poseB.set(...q.slice(3));g.quaternion.copy(poseA.slerp(poseB,mix));
  });
 }else parts.forEach((g,i)=>{
  const p=DATA.geometries[ids[i]],tease=index===0?4:1;
  g.position.copy(V(p.center)).addScaledVector(V(p.offset),tease).add(new THREE.Vector3(0,DATA.height,0));
  if(index===0)g.position.addScaledVector(V(p.center),.07*stage/shot.count);
  g.quaternion.identity();
 });
 // Held geometry stays identical between cuts. Only the camera and knives
 // move then, so do not transform every fruit vertex on every preview tick.
 const poseKey=t>=shot.release?`${index}:physics:${t}`:`${index}:held:${stage}`;
 if(poseKey!==activePose){updateBatches();activePose=poseKey;}
 knives.forEach(({main,echo})=>{main.visible=false;echo.visible=false;});
 let slot=0;
 shot.cutTimes.forEach((c,i)=>{
  const age=t-c;
  if(age<-.08||age>.07||slot>=knives.length)return;
  const {main,echo}=knives[slot++];main.visible=true;echo.visible=true;
  throwKnife(main,i,age);throwKnife(echo,i,age-.012);
 });
 const theta=.75+Math.sin(time*.18)*.045;
 const pullback=Math.max(0,Math.min(1,(t-shot.release)/.75));
 const radius=(index===0?16.9:18.5)+3.3*pullback;
 camera.position.set(Math.sin(theta)*radius,11.5+2*pullback,Math.cos(theta)*radius);camera.lookAt(0,1.9,0);renderer.render(scene,camera);
 drawPixelFrame(renderer.domElement,shot.count,index-1,index===0);
}
window.drawFruit=renderAt;
window.addEventListener('hf-seek',e=>renderAt(e.detail.time));renderAt(window.__hfThreeTime||0);
