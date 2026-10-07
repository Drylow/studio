import * as THREE from 'three';
import * as CANNON from 'cannon-es';
import {mkdirSync,writeFileSync} from 'node:fs';

// Closed prisms are clipped by seeded oblique planes. None is a pre-cut cube.
const V=(x=0,y=0,z=0)=>new THREE.Vector3(x,y,z), EPS=1e-7;
const unique=pts=>[...new Map(pts.map(p=>[p.toArray().map(n=>n.toFixed(6)).join(','),p])).values()];
const mean=pts=>pts.reduce((s,p)=>s.add(p),V()).multiplyScalar(1/pts.length);
const SIZE=[3.8,.18,2.7], BASE=5.3, GAP=.22, FPS=120, STEP=1/240;
const forkTop=2.95,release=.90;
let seed=7319107;
const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
function slab(){
 const [x,y,z]=SIZE.map(n=>n/2);
 const pts=[V(-x,-y,-z),V(x,-y,-z),V(x,-y,z),V(-x,-y,z),V(-x,y,-z),V(x,y,-z),V(x,y,z),V(-x,y,z)];
 const faces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[3,7,6,2],[0,4,7,3],[1,2,6,5]].map(ids=>({kind:'outer',points:ids.reverse().map(i=>pts[i])}));
 return {faces};
}
function volume(p){let v=0;for(const f of p.faces)for(let j=1;j<f.points.length-1;j++)v+=f.points[0].dot(f.points[j].clone().cross(f.points[j+1]))/6;return Math.abs(v);}
function half(piece,n,d,sign){
 const faces=[],edge=[];
 for(const face of piece.faces){const out=[],pts=face.points;
  for(let i=0;i<pts.length;i++){
   const a=pts[i],b=pts[(i+1)%pts.length],da=(n.dot(a)-d)*sign,db=(n.dot(b)-d)*sign;
   if(Math.abs(da)<EPS)edge.push(a.clone());
   if(da>=-EPS)out.push(a.clone());
   if((da>EPS&&db<-EPS)||(da<-EPS&&db>EPS)){const p=a.clone().lerp(b,da/(da-db));out.push(p);edge.push(p);}
  }
  const clean=unique(out);if(clean.length>=3)faces.push({kind:face.kind,points:clean});
 }
 const cap=unique(edge);if(cap.length<3)return null;
 const c=mean(cap),outward=n.clone().multiplyScalar(-sign),u=V(0,1,0);
 if(Math.abs(u.dot(outward))>.95)u.set(1,0,0);u.cross(outward).normalize();const v=outward.clone().cross(u);
 cap.sort((a,b)=>Math.atan2(a.clone().sub(c).dot(v),a.clone().sub(c).dot(u))-Math.atan2(b.clone().sub(c).dot(v),b.clone().sub(c).dot(u)));
 faces.push({kind:'fracture',points:cap});return {faces};
}
function fracture(target){
 const pieces=[slab()];let attempts=0;
 while(pieces.length<target&&attempts++<500){
  const ranked=pieces.map((p,i)=>({p,i,v:volume(p)})).sort((a,b)=>b.v-a.v);
  const {p,i}=ranked[Math.floor(random()*Math.min(3,ranked.length))];
  const angle=random()*Math.PI*2,n=V(Math.cos(angle),(random()-.5)*.75,Math.sin(angle)).normalize();
  const projections=unique(p.faces.flatMap(f=>f.points)).map(v=>n.dot(v));
  const lo=Math.min(...projections),hi=Math.max(...projections),d=lo+(hi-lo)*(.32+random()*.36);
  const a=half(p,n,d,1),b=half(p,n,d,-1);
  if(!a||!b||Math.min(volume(a),volume(b))<.004)continue;
  pieces.splice(i,1,a,b);
 }
 return pieces;
}
function serialize(p){const center=mean(unique(p.faces.flatMap(f=>f.points)));return {center:center.toArray(),volume:volume(p),faces:p.faces.map(f=>({kind:f.kind,points:f.points.map(v=>v.toArray())}))};}
function convex(p){
 const pts=unique(p.faces.flatMap(f=>f.points)),center=mean(pts);
 const lookup=new Map(pts.map((v,j)=>[v.toArray().map(n=>n.toFixed(6)).join(','),j]));
 const vertices=pts.map(v=>new CANNON.Vec3(...v.clone().sub(center).multiplyScalar(.999).toArray()));
 const faces=p.faces.map(f=>f.points.map(v=>lookup.get(v.toArray().map(n=>n.toFixed(6)).join(','))));
 return new CANNON.ConvexPolyhedron({vertices,faces});
}
const geometries={},trials=[],events=[];
const counts=[1,2,4,8,16],lengths=[4.4,4.6,5,5.8,6.4];let cursor=0;
for(const [chapter,count] of counts.entries()){
 const length=lengths[chapter],world=new CANNON.World({gravity:new CANNON.Vec3(0,-10.8,0)});
 world.solver.iterations=18;world.allowSleep=true;world.broadphase=new CANNON.SAPBroadphase(world);
 world.defaultContactMaterial.friction=.50;world.defaultContactMaterial.restitution=.08;
 const floor=new CANNON.Body({mass:0,shape:new CANNON.Plane()});floor.quaternion.setFromEuler(-Math.PI/2,0,0);world.addBody(floor);
 const board=new CANNON.Body({mass:0,shape:new CANNON.Box(new CANNON.Vec3(3.55,.17,2.65)),position:new CANNON.Vec3(0,.17,0)});world.addBody(board);
 const fork=new CANNON.Body({mass:0});
 fork.addShape(new CANNON.Box(new CANNON.Vec3(.18,.55,.15)),new CANNON.Vec3(0,.95,0));
 fork.addShape(new CANNON.Box(new CANNON.Vec3(.95,.24,.16)),new CANNON.Vec3(0,1.59,0));
 const tooth=new CANNON.ConvexPolyhedron({vertices:[new CANNON.Vec3(-.14,0,-.14),new CANNON.Vec3(.14,0,-.14),new CANNON.Vec3(.14,0,.14),new CANNON.Vec3(-.14,0,.14),new CANNON.Vec3(0,1.2,0)],faces:[[0,3,2,1],[0,1,4],[1,2,4],[2,3,4],[3,0,4]].map(f=>f.reverse())});
 for(const x of [-.75,-.25,.25,.75])fork.addShape(tooth,new CANNON.Vec3(x,1.75,0));world.addBody(fork);
 const bars=[],fragments=[],pending=new Set();let now=0;
 for(let i=0;i<count;i++){
  const id=`${chapter}-bar${i}`,pieces=fracture(12+(i+chapter)%5);
  const ids=pieces.map((p,j)=>{const key=`${id}-${j}`;geometries[key]=serialize(p);return key;});
  const intact=new CANNON.Body({mass:0,shape:new CANNON.Box(new CANNON.Vec3(...SIZE.map(n=>n/2))),position:new CANNON.Vec3(0,BASE+i*GAP,0),linearDamping:.01});
  intact.collisionFilterGroup=4;intact.collisionFilterMask=1;
  intact.addEventListener('collide',e=>{if(e.body===fork)pending.add(i);});world.addBody(intact);
  bars.push({id,ids,pieces,intact,hit:null,frames:[]});
 }
 let active=false;
 for(let step=0;step<=Math.ceil(length/STEP);step++){
  now=step*STEP;
  if(!active&&now>=release){active=true;for(const b of bars){b.intact.type=CANNON.Body.DYNAMIC;b.intact.mass=1;b.intact.updateMassProperties();b.intact.wakeUp();}}
  if(active)world.step(STEP);
  for(const index of pending){
   const bar=bars[index];if(bar.hit!==null)continue;
   bar.hit=now;events.push({type:'crunch',t:+(cursor+now).toFixed(6),chapter,bar:index,count});
   const position=bar.intact.position.clone(),velocity=bar.intact.velocity.clone(),q=bar.intact.quaternion.clone();world.removeBody(bar.intact);
   bar.bodies=bar.pieces.map((p,j)=>{
    const geometry=geometries[bar.ids[j]],center=new CANNON.Vec3(...geometry.center),local=q.vmult(center);
    const body=new CANNON.Body({mass:Math.max(.004,geometry.volume*.65),shape:convex(p),linearDamping:.52,angularDamping:.60,sleepSpeedLimit:.1,sleepTimeLimit:.55});
    body.position.copy(position.vadd(local));body.quaternion.copy(q);
    body.collisionFilterGroup=2;body.collisionFilterMask=1;
    // Contact produces modest outward separation; retain the falling momentum.
    const a=Math.atan2(center.z,center.x),spread=.55+.30*random();
    body.velocity.set(Math.cos(a)*spread,Math.min(-.5,velocity.y*.3)+.25*random(),Math.sin(a)*spread);
    body.angularVelocity.set((random()-.5)*6,(random()-.5)*2,(random()-.5)*6);
    body.addEventListener('collide',e=>{
     const speed=Math.abs(e.contact.getImpactVelocityAlongNormal());
     if(speed>.9&&(e.body===board||e.body===floor||e.body===fork))events.push({type:'landing',t:+(cursor+now).toFixed(6),chapter,bar:index,piece:j,speed,mass:body.mass});
    });world.addBody(body);fragments.push(body);return body;
   });
  }
  pending.clear();
  // Continuous contact guard protects very thin chips at the real support plane.
  const p=new CANNON.Vec3();
  for(const body of fragments){
   // Thin wedges against a sharp static tine can create solver energy spikes.
   // Bound that numerical energy; this is an edible crunch, not an explosion.
   const horizontal=Math.hypot(body.velocity.x,body.velocity.z);
   if(horizontal>2.4){body.velocity.x*=2.4/horizontal;body.velocity.z*=2.4/horizontal;}
   body.velocity.y=Math.max(-8,Math.min(2.0,body.velocity.y));
   const spin=body.angularVelocity.length();if(spin>7)body.angularVelocity.scale(7/spin,body.angularVelocity);
   let bottom=Infinity;
   for(const v of body.shapes[0].vertices){body.quaternion.vmult(v,p);bottom=Math.min(bottom,p.y+body.position.y);}
   const support=Math.abs(body.position.x)<3.5&&Math.abs(body.position.z)<2.60?.345:.005;
   if(bottom<support){body.position.y+=support-bottom;if(body.velocity.y<0)body.velocity.y=0;body.aabbNeedsUpdate=true;}
  }
  if(step%2===0)for(const bar of bars){
   const body=bar.intact;
   bar.frames.push(bar.hit===null?[[...body.position.toArray(),...body.quaternion.toArray()].map(n=>+n.toFixed(5))]:bar.bodies.map(b=>[...b.position.toArray(),...b.quaternion.toArray()].map(n=>+n.toFixed(5))));
  }
 }
 const data=bars.map(({id,ids,hit,frames})=>({id,ids,hit,frames}));
 if(data.some(b=>b.hit===null))throw Error('A bar did not reach the fork');
 trials.push({start:cursor,length,count,bars:data});cursor=+(cursor+length).toFixed(3);
 console.log(`${count} bars: ${data.reduce((s,b)=>s+b.ids.length,0)} irregular pieces; contacts ${data.map(b=>b.hit.toFixed(3)).join(', ')}`);
}
const outroStart=cursor,duration=+(cursor+1.6).toFixed(3);
mkdirSync('assets',{recursive:true});
writeFileSync('assets/simulation.json',JSON.stringify({fps:FPS,size:SIZE,base:BASE,gap:GAP,forkTop,release,duration,outroStart,geometries,trials}));
writeFileSync('assets/events.json',JSON.stringify(events,null,2));
console.log(`Duration ${duration}s; ${events.filter(e=>e.type==='crunch').length} actual fork contacts.`);
