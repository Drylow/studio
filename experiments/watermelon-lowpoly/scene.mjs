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
blade.add(box([.16,.42,.13],[0,.52,2.12],'#dfc79d',.3));scene.add(blade);
const seedsMat=new THREE.MeshStandardMaterial({color:'#352922',roughness:.7});
const skinMat=new THREE.MeshStandardMaterial({vertexColors:true,flatShading:true,roughness:.73});
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
    const seed=new THREE.Mesh(new THREE.IcosahedronGeometry(.045,1),seedsMat);
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
  const mat=new THREE.MeshStandardMaterial({color:'#ed4b59',roughness:.82,flatShading:true});
  mat.onBeforeCompile=shader=>{
   shader.uniforms.fruitCenter={value:center};
   shader.vertexShader='varying vec3 vFruitPos; uniform vec3 fruitCenter;\n'+shader.vertexShader;
   shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvFruitPos=position+fruitCenter;');
   shader.fragmentShader='varying vec3 vFruitPos;\n'+shader.fragmentShader;
   shader.fragmentShader=shader.fragmentShader.replace('#include <color_fragment>',`#include <color_fragment>
    float r=length(vFruitPos/vec3(1.55,1.65,1.55));
    if(r>.971)diffuseColor.rgb=vec3(.10,.24,.12);
    else if(r>.915)diffuseColor.rgb=vec3(.88,.90,.64);
    else diffuseColor.rgb*=.96+.04*sin(vFruitPos.x*11.+vFruitPos.z*9.);
   `);
  };
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(arrays.flesh,3));g.computeVertexNormals();
  const m=new THREE.Mesh(g,mat);m.castShadow=true;m.receiveShadow=true;group.add(m);
 }
 group.position.copy(center).add(V(piece.offset)).add(new THREE.Vector3(0,DATA.height,0));return group;
}
const shots=DATA.shots.map(shot=>{
 const root=new THREE.Group();scene.add(root);
 const stages=shot.stages.map(stage=>{const holder=new THREE.Group();root.add(holder);return {holder,parts:stage.map(p=>{const g=createPiece(p);holder.add(g);return g;})};});
 return {root,stages};
});
const poseA=new THREE.Quaternion(),poseB=new THREE.Quaternion(),yAxis=new THREE.Vector3(0,1,0);
function renderAt(input){
 const time=Math.max(0,Math.min(input,DATA.duration-1/60)),index=Math.min(2,Math.floor(time/DATA.shotLength)),t=time-index*DATA.shotLength,shot=DATA.shots[index],view=shots[index];
 shots.forEach((s,i)=>s.root.visible=i===index);
 const stage=shot.cutTimes.filter(c=>t>=c).length;
 view.stages.forEach((s,i)=>s.holder.visible=i===stage);const parts=view.stages[stage].parts;
 if(t>=shot.release){
  const f=(t-shot.release)*DATA.fps,a=Math.min(Math.floor(f),shot.frames.length-1),b=Math.min(a+1,shot.frames.length-1),mix=f-a;
  parts.forEach((g,i)=>{const p=shot.frames[a][i],q=shot.frames[b][i];
   g.position.set(p[0]+(q[0]-p[0])*mix,p[1]+(q[1]-p[1])*mix,p[2]+(q[2]-p[2])*mix);
   poseA.set(...p.slice(3));poseB.set(...q.slice(3));g.quaternion.copy(poseA.slerp(poseB,mix));
  });
 }else parts.forEach((g,i)=>{const p=shot.stages[stage][i];g.position.copy(V(p.center)).add(V(p.offset)).add(new THREE.Vector3(0,DATA.height,0));g.quaternion.identity();});
 let cutting=-1;shot.cutTimes.forEach((c,i)=>{if(t>=c-.07&&t<=c+.075)cutting=i;});blade.visible=cutting>=0;
 if(cutting>=0){
  const c=shot.cutTimes[cutting],n=V(DATA.planes[cutting].n);
  const p=Math.max(0,Math.min(1,(t-c+.07)/.145));
  const sweep=p*p*(3-2*p);
  if(Math.abs(n.y)>.9){blade.quaternion.setFromAxisAngle(new THREE.Vector3(0,0,1),Math.PI/2);blade.position.set(5.2-10.4*sweep,DATA.height,0);}
  else{blade.quaternion.setFromAxisAngle(yAxis,-Math.atan2(n.z,n.x));blade.position.copy(n.multiplyScalar(DATA.planes[cutting].d)).add(new THREE.Vector3(0,5.55-4.4*sweep,0));}
 }
 const theta=.75+Math.sin(time*.18)*.045;
 const pullback=Math.max(0,Math.min(1,(t-shot.release)/1.0));
 const radius=18.5+5.5*pullback;
 camera.position.set(Math.sin(theta)*radius,11.5+3.5*pullback,Math.cos(theta)*radius);camera.lookAt(0,1.9,0);renderer.render(scene,camera);
 drawPixelFrame(renderer.domElement,shot.count,index);
}
window.drawFruit=renderAt;
window.addEventListener('hf-seek',e=>renderAt(e.detail.time));renderAt(window.__hfThreeTime||0);
