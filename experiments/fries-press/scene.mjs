import * as T from 'three';
import data from './assets/piles.json';
import {createPixelView,PIXEL_WIDTH as W,PIXEL_HEIGHT as H} from './pixel.mjs';
import {createChef} from './chef.mjs';
import {stateAt,rand,smooth,clamp,FLOOR,HOME,OUTRO} from './model.mjs';
const canvas=document.getElementById('film'),publish=createPixelView(canvas);
const renderer=new T.WebGLRenderer({antialias:false,alpha:false,preserveDrawingBuffer:true});
renderer.setSize(W,H,false);renderer.setPixelRatio(1);renderer.outputColorSpace=T.SRGBColorSpace;
renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.25;
renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;renderer.localClippingEnabled=true;
const scene=new T.Scene();scene.background=new T.Color('#f1e7d6');
const camera=new T.PerspectiveCamera(37,1080/1920,.1,100);
scene.add(new T.HemisphereLight('#f2f0c4','#6e9852',2.2));
const key=new T.DirectionalLight('#f2f0c4',3.4);key.position.set(-4,10,5);key.castShadow=true;key.shadow.mapSize.set(1024,1024);
Object.assign(key.shadow.camera,{left:-8,right:8,top:12,bottom:-8});key.shadow.normalBias=.022;key.shadow.bias=-.0002;key.shadow.radius=4;scene.add(key);
const rim=new T.DirectionalLight('#def2e1',1.3);rim.position.set(5,4,-4);scene.add(rim);
const mats=new Map();
function mat(color,roughness=.7,metalness=0){const id=[color,roughness,metalness].join();if(!mats.has(id))mats.set(id,color==='#def2e1'?new T.MeshBasicMaterial({color,toneMapped:false}):new T.MeshStandardMaterial({color,roughness,metalness}));return mats.get(id);}
function mesh(g,pos,color,roughness=.7,metalness=0){const m=new T.Mesh(g,mat(color,roughness,metalness));m.position.set(...pos);m.castShadow=true;m.receiveShadow=true;return m;}
function box(size,pos,color,roughness=.7){return mesh(new T.BoxGeometry(...size),pos,color,roughness);}
function cyl(r,h,pos,color,n=16,roughness=.45,metalness=.15){return mesh(new T.CylinderGeometry(r,r,h,n),pos,color,roughness,metalness);}
function disc(pos,color){const m=cyl(1,.012,pos,color,16,.18,.15);m.castShadow=false;return m;}
const ground=mesh(new T.PlaneGeometry(200,200),[0,0,0],'#f1e7d6',.95);ground.rotation.x=-Math.PI/2;ground.castShadow=false;scene.add(ground);
const board=new T.Group();scene.add(board);board.add(box([7.3,.34,5.5],[0,.17,0],'#c79565'));
for(let i=0;i<14;i++){board.add(box([.49,.014,5.35],[-3.37+i*.52,.347,0],i%3===0?'#dfb27e':'#c79565'));for(let j=0;j<2;j++)board.add(box([.20,.005,.03],[-3.37+i*.52,.357,-1.8+j*2.6],i%2?'#eacd9b':'#a46b46'));}
// Fixed frame behind the food, with a single vertical ram.
const press=new T.Group();scene.add(press);
for(const x of [-3.13,3.13]){press.add(box([.48,7.05,.70],[x,3.88,-1.82],'#244c37'));press.add(box([.12,6.90,.04],[x-.16,3.85,-1.44],'#47714a'));press.add(box([.95,.22,1.14],[x,.48,-1.82],'#203c2a'));}
for(const [size,pos,color] of [[[7.08,.56,.83],[0,7.3,-1.82],'#244c37'],[[5.2,.31,2.05],[0,7.28,-.50],'#244c37'],[[1.8,.46,1.65],[0,6.91,0],'#47714a'],[[.48,1.2,.31],[-3.15,4.8,-1.34],'#ffe59a']])press.add(box(size,pos,color));
press.add(cyl(.78,1.18,[0,6.48,0],'#244c37'));press.add(cyl(.85,.16,[0,5.94,0],'#203c2a'));
for(let i=0;i<3;i++)press.add(box([.14,.14,.04],[-3.15,4.47+i*.24,-1.16],i===2?'#ef5867':'#203c2a'));
const gauge=cyl(.30,.09,[-2.82,6.48,-1.36],'#f2f0c4',12);gauge.rotation.x=Math.PI/2;press.add(gauge);
const needle=box([.03,.20,.03],[-2.82,6.49,-1.29],'#ef5867');press.add(needle);
const shaft=cyl(.35,1,[0,5,0],'#b7c2ba',12,.22,.42);scene.add(shaft);
const shine=box([.08,1,.018],[-.16,5,.32],'#def2e1');scene.add(shine);
const platen=new T.Group();scene.add(platen);platen.add(cyl(2.52,.36,[0,.18,0],'#b7c2ba',20,.24,.40));platen.add(cyl(2.56,.075,[0,.035,0],'#6b6c51',20));platen.add(cyl(.70,.12,[0,.40,0],'#b7c2ba',12));
const tray=new T.Group();scene.add(tray);
tray.add(cyl(2.56,.14,[0,FLOOR-.08,0],'#b7c2ba',20,.3,.35));tray.add(cyl(2.68,.09,[0,FLOOR-.16,0],'#6b6c51',20));press.add(cyl(.98,.40,[0,.72,0],'#203c2a'));press.add(cyl(2.48,.14,[0,.48,0],'#47714a'));
const lip=mesh(new T.TorusGeometry(2.49,.035,4,20),[0,FLOOR+.012,0],'#b7c2ba',.35,.25);lip.rotation.x=Math.PI/2;tray.add(lip);
const clip=new T.Plane(new T.Vector3(0,-1,0),HOME),fryMat=new T.MeshStandardMaterial({color:'#ffe59a',roughness:.64,clippingPlanes:[clip]});
const fryGeo=new T.BoxGeometry(1,1,1,2,1,1),verts=fryGeo.attributes.position;
for(let i=0;i<verts.count;i++){const x=verts.getX(i),y=verts.getY(i),z=verts.getZ(i);verts.setXYZ(i,x*(Math.abs(y)>.4?.97:1),y*(Math.abs(x)>.4?.88:1),z*(Math.abs(x)>.4?.91:1));}fryGeo.computeVertexNormals();
const fries=new T.InstancedMesh(fryGeo,fryMat,576);fries.castShadow=true;fries.receiveShadow=true;fries.frustumCulled=false;tray.add(fries);
const dummy=new T.Object3D(),q=new T.Quaternion(),euler=new T.Euler(0,0,0,'YXZ');
const colors=['#ffe59a','#ffd09b','#efb07a','#dfb27e'].map(x=>new T.Color(x));
const baked=data.piles.map(p=>p.fries.map(f=>{const quat=new T.Quaternion(...f.q),axis=new T.Vector3(1,0,0).applyQuaternion(quat);return {...f,quat,axis,yaw:Math.atan2(-axis.z,axis.x)};}));
const crumbs=new T.InstancedMesh(new T.TetrahedronGeometry(.07),mat('#dfb27e',.6),70);crumbs.castShadow=true;crumbs.frustumCulled=false;tray.add(crumbs);
const oil=new T.Group();tray.add(oil);const floorOil=new T.Group();scene.add(floorOil);
const oilPool=disc([0,FLOOR+.018,0],'#d88f28');oil.add(oilPool);
const puddles=[];for(let i=0;i<18;i++){const a=i/18*Math.PI*2,r=1.75+rand(i+500)*.54,m=disc([Math.cos(a)*r,.370,Math.sin(a)*r],'#d88f28');floorOil.add(m);puddles.push(m);}
const N=22,STEPS=28,RING=6,streams=[];
for(let i=0;i<N;i++){
 const a=(i+.18)/N*Math.PI*2,dx=Math.cos(a),dz=Math.sin(a),edge=Math.min(3.56/Math.abs(dx||.0001),2.67/Math.abs(dz||.0001)),positions=new Float32Array((STEPS+1)*RING*3),indices=[];
 for(let j=0;j<STEPS;j++)for(let k=0;k<RING;k++){const b=j*RING+k,n=j*RING+(k+1)%RING;indices.push(b,n,b+RING,n,n+RING,b+RING);}
 const geo=new T.BufferGeometry();geo.setAttribute('position',new T.BufferAttribute(positions,3));geo.setIndex(indices);
 const m=new T.Mesh(geo,mat(i%3?'#d88f28':'#f4ba45',.14,.12));m.frustumCulled=false;m.castShadow=true;oil.add(m);
 const glint=box([.025,.2,.025],[0,0,0],'#ffe59a');glint.castShadow=false;oil.add(glint);
 const pool=disc([dx*(edge+.15),.011,dz*(edge+.15)],'#d88f28'),highlight=disc([dx*(edge+.15)+.06,.023,dz*(edge+.15)],'#f4ba45');floorOil.add(pool,highlight);streams.push({m,geo,positions,dx,dz,edge,glint,pool,highlight});
}
const drops=new T.InstancedMesh(new T.OctahedronGeometry(1,0),mat('#d88f28',.12,.2),N*5);drops.castShadow=true;drops.frustumCulled=false;oil.add(drops);
function point(s,u){let r,y;if(u<.32){const f=u/.32;r=2.32+.43*f;y=FLOOR+.027-(FLOOR-.39)*smooth(f);}else if(u<.60){const f=(u-.32)/.28;r=2.75+(s.edge-2.75)*f;y=.388-.015*f;}else{const f=(u-.60)/.4;r=s.edge+.19*f;y=.374*(1-f*f);}return [s.dx*r,y,s.dz*r];}
function updateOil(s){
 oil.visible=s.oil>0;floorOil.visible=s.oil>0;const radius=1.3+s.oil*1.36;oilPool.scale.set(radius,1,radius);
 for(const m of puddles){const z=s.oil*(.55+s.index*.18);m.scale.set(.49*z,1,.28*z);}
 streams.forEach((st,i)=>{
  const enabled=i<(s.index===0?7:s.index===1?14:22),born=s.load.oilAt+1.15+rand(i+800)*1.5,growing=clamp((s.local-born)/1.2),width=(.035+s.index*.05+s.oil*.08)*(1+rand(i+860)*.65)*s.flow*(1-s.leave);
  st.m.visible=enabled&&growing>0;
  for(let j=0;j<=STEPS;j++){const u=j/STEPS*growing,[x,y,z]=point(st,u),w=width*(.88+.12*Math.sin(s.local*6-u*14+i));for(let k=0;k<RING;k++){const a=k/RING*Math.PI*2,p=(j*RING+k)*3;st.positions[p]=x+Math.cos(a)*w*st.dz;st.positions[p+1]=y+Math.sin(a)*w*.55;st.positions[p+2]=z-Math.cos(a)*w*st.dx;}}
  st.geo.attributes.position.needsUpdate=true;st.geo.computeVertexNormals();
  const grow=smooth((s.local-born-1.15)/3.5)*(enabled?1:0),size=grow*(.25+s.index*.23);st.pool.scale.set(size*1.5,1,size);st.highlight.scale.set(size*.6,1,size*.17);
  const [gx,gy,gz]=point(st,.30);st.glint.visible=st.m.visible;st.glint.position.set(gx,gy+.05,gz);st.glint.scale.set(1,growing,1);
  for(let k=0;k<5;k++){const cycle=.75+rand(i*19+k+970)*.7,phase=rand(i*19+k+999)*cycle,age=((s.local-born-phase)%cycle+cycle)%cycle,alive=enabled&&s.local>born+phase&&age<.42;dummy.position.set(st.dx*(st.edge+.09+.20*age),.35+age*.3-4.9*age*age,st.dz*(st.edge+.09+.20*age));const r=alive&&dummy.position.y>.025?(.034+.028*rand(i*19+k+1030))*s.flow:0;dummy.scale.set(r,r*1.4,r);dummy.rotation.set(0,0,age*3);dummy.updateMatrix();drops.setMatrixAt(i*5+k,dummy.matrix);}
 });drops.instanceMatrix.needsUpdate=true;
}
const chef=createChef(scene,box);
function updateFries(s){
 const list=baked[s.index],c=s.compression,vertical=1-.87*c;clip.constant=s.plate+.028;
 for(let i=0;i<192;i++)for(let part=0;part<3;part++){
  const index=i*3+part;if(i>=list.length){dummy.scale.set(0,0,0);dummy.updateMatrix();fries.setMatrixAt(index,dummy.matrix);continue;}
  const f=list[i],ratios=[.24+rand(f.seed+10)*.09,.31+rand(f.seed+11)*.06];ratios.push(1-ratios[0]-ratios[1]);
  const offset=f.length*(ratios.slice(0,part).reduce((a,b)=>a+b,0)+ratios[part]/2-.5),breakage=smooth((c-(.08+rand(f.seed+13)*.45))/.3),outward=1+.12*c+.025*s.index*c,drift=(part-1)*breakage*(.06+.10*rand(f.seed+part+21));
  dummy.position.set(f.p[0]*outward+f.axis.x*offset+Math.cos(f.yaw)*drift,Math.max(FLOOR+.035,FLOOR+(f.p[1]+f.axis.y*offset-FLOOR)*vertical),f.p[2]*outward+f.axis.z*offset-Math.sin(f.yaw)*drift);
  q.setFromEuler(euler.set(0,f.yaw+(rand(f.seed+part+30)-.5)*breakage*.34,0,'YXZ'));dummy.quaternion.copy(f.quat).slerp(q,c);dummy.scale.set(f.length*ratios[part]*(1+.025*c),f.height*(1-.53*c),f.width*(1+.12*c));dummy.updateMatrix();fries.setMatrixAt(index,dummy.matrix);fries.setColorAt(index,colors[(i+part+(i%7===0?2:0))%colors.length]);
 }fries.instanceMatrix.needsUpdate=true;fries.instanceColor.needsUpdate=true;
 for(let i=0;i<70;i++){const born=s.load.contact+.7+rand(i+1200)*(s.load.crushEnd-s.load.contact-1),age=s.local-born,a=rand(i+1230)*Math.PI*2,fly=age>0&&age<1.2&&i<20+s.index*24,y=FLOOR+.18+age*(.7+rand(i+1300))-4.9*age*age;dummy.position.set(Math.cos(a)*(1.4+(1.6+rand(i+1250))*age),Math.max(.40,y),Math.sin(a)*(1.4+(1.6+rand(i+1250))*age));const z=fly&&y>.40?1:0;dummy.scale.set(z*(.6+rand(i+1330)),z*.65,z);dummy.rotation.set(age*4,i+age*2,age*5);dummy.updateMatrix();crumbs.setMatrixAt(i,dummy.matrix);}crumbs.instanceMatrix.needsUpdate=true;
}
export function draw(time){
 const s=stateAt(time,data.piles.map(p=>p.height));tray.position.x=s.trayX;platen.position.y=s.plate;
 const length=Math.max(.18,6.04-(s.plate+.38));shaft.scale.y=length;shaft.position.y=s.plate+.38+length/2;shine.scale.y=length;shine.position.y=shaft.position.y;needle.rotation.z=.7-s.compression*1.4;
 updateFries(s);updateOil(s);
 const angle=.30+.13*s.cameraClose-.17*s.runoff,distance=21.7-3.2*s.cameraClose,shake=Math.sin(s.local*49)*.012*s.compression*(1-s.lift);
 camera.position.set(Math.sin(angle)*distance+shake,10.4-2.5*s.runoff,Math.cos(angle)*distance);camera.lookAt(shake,3.62-1.15*s.runoff,0);
 const anchor=chef({time:s.outro?s.t-OUTRO:s.local,first:!s.outro,outro:s.outro,base:FLOOR,trayX:s.trayX}),p=anchor?.clone().project(camera);
 renderer.render(scene,camera);publish(renderer.domElement,s.load.count,s.index,s.outro,p?{time:s.t-OUTRO,x:(p.x+1)*W/2,y:(1-p.y)*H/2}:null,'press',s);
 window.__friesState={time:s.t,count:s.load.count,compression:s.compression,oil:s.oil,plate:s.plate,index:s.index};
}
window.drawFries=draw;window.addEventListener('hf-seek',event=>draw(event.detail.time));draw(0);
