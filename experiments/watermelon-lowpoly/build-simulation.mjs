import * as THREE from 'three';
import * as CANNON from 'cannon-es';
import {ConvexHull} from 'three/addons/math/ConvexHull.js';
import {mkdirSync,writeFileSync} from 'node:fs';

// Convex clipping, followed by an offline, fixed-step rigid-body simulation.
// Rendering never integrates physics: every pose is baked and seekable.
const V=(x=0,y=0,z=0)=>new THREE.Vector3(x,y,z);
const EPS=1e-6, R=[1.55,1.65,1.55], HEIGHT=2.65;
const unique=pts=>[...new Map(pts.map(p=>[p.toArray().map(n=>n.toFixed(5)).join(','),p])).values()];
const mean=pts=>pts.reduce((s,p)=>s.add(p),V()).multiplyScalar(1/pts.length);
function original(){
  const g=new THREE.IcosahedronGeometry(1,3); const a=g.attributes.position;
  const faces=[];
  for(let i=0;i<a.count;i+=3) faces.push({kind:'skin',points:[0,1,2].map(j=>V(a.getX(i+j)*R[0],a.getY(i+j)*R[1],a.getZ(i+j)*R[2]))});
  return {faces,offset:V(),id:'fruit'};
}
function half(piece,n,d,sign,id){
  const faces=[],edge=[];
  for(const face of piece.faces){
    const pts=face.points,out=[];
    for(let i=0;i<pts.length;i++){
      const a=pts[i],b=pts[(i+1)%pts.length],da=(n.dot(a)-d)*sign,db=(n.dot(b)-d)*sign;
      if(Math.abs(da)<EPS)edge.push(a.clone());
      if(da>=-EPS) out.push(a.clone());
      if((da>EPS&&db<-EPS)||(da<-EPS&&db>EPS)){
        const p=a.clone().lerp(b,da/(da-db));out.push(p);edge.push(p);
      }
    }
    const clean=unique(out);
    if(clean.length>=3) faces.push({kind:face.kind,points:clean});
  }
  const cap=unique(edge);
  if(cap.length<3) return null;
  const c=mean(cap), outward=n.clone().multiplyScalar(-sign);
  const u=V(0,1,0);if(Math.abs(u.dot(outward))>.95)u.set(1,0,0);
  u.cross(outward).normalize(); const v=outward.clone().cross(u);
  cap.sort((a,b)=>Math.atan2(a.clone().sub(c).dot(v),a.clone().sub(c).dot(u))-Math.atan2(b.clone().sub(c).dot(v),b.clone().sub(c).dot(u)));
  faces.push({kind:'flesh',points:cap});
  return {id,faces,offset:piece.offset.clone().addScaledVector(n,sign*.035)};
}
const PLANES=[
 {n:V(1,0,0),d:0}, {n:V(0,0,1),d:0}, {n:V(0,1,0),d:.0},
 {n:V(1,0,0),d:.78}, {n:V(1,0,0),d:-.78},
 {n:V(0,0,1),d:.78}, {n:V(0,0,1),d:-.78},
];
function serialize(piece){
  const pts=unique(piece.faces.flatMap(f=>f.points)),center=mean(pts);
  return {id:piece.id,center:center.toArray(),offset:piece.offset.toArray(),faces:piece.faces.map(f=>({kind:f.kind,points:f.points.map(p=>p.toArray())}))};
}
function bake(count){
 let pieces=[original()];const stages=[pieces.map(serialize)],cutTimes=[];
 for(let i=0;i<count;i++){
  const {n,d}=PLANES[i];const next=[];
  for(const p of pieces){
   const values=p.faces.flatMap(f=>f.points.map(v=>n.dot(v)-d));
   if(Math.min(...values)<-EPS&&Math.max(...values)>EPS){
    next.push(half(p,n,d,1,p.id+'p'+i),half(p,n,d,-1,p.id+'m'+i));
   }else next.push(p);
  }
  pieces=next.filter(Boolean);stages.push(pieces.map(serialize));cutTimes.push(.82+i*.33);
 }
 const release=cutTimes.at(-1)+.34;
 const world=new CANNON.World({gravity:new CANNON.Vec3(0,-7.6,0)});
 world.solver.iterations=24;world.allowSleep=true;
 const material=new CANNON.Material('fruit');
 world.defaultContactMaterial.friction=.62;world.defaultContactMaterial.restitution=.09;
 const floor=new CANNON.Body({mass:0,shape:new CANNON.Plane()});floor.quaternion.setFromEuler(-Math.PI/2,0,0);world.addBody(floor);
 const board=new CANNON.Body({mass:0,shape:new CANNON.Box(new CANNON.Vec3(3.55,.17,2.65)),position:new CANNON.Vec3(0,.17,0)});world.addBody(board);
 const bodies=pieces.map((p,i)=>{
  const pts=unique(p.faces.flatMap(f=>f.points)),center=mean(pts);
  const lookup=new Map(pts.map((v,j)=>[v.toArray().map(n=>n.toFixed(5)).join(','),j]));
  const vertices=pts.map(v=>new CANNON.Vec3(...v.clone().sub(center).multiplyScalar(.995).toArray()));
  const hull=new ConvexHull().setFromPoints(pts);
  // Cannon expects planar polygon faces, not a triangulated coplanar cap.
  const planes=new Map();
  for(const f of hull.faces){
   const key=[...f.normal.toArray(),f.constant].map(n=>n.toFixed(4)).join(',');
   if(!planes.has(key))planes.set(key,{n:f.normal.clone(),pts:[]});
   let e=f.edge;do{planes.get(key).pts.push(e.head().point);e=e.next;}while(e!==f.edge);
  }
  const faces=[...planes.values()].map(({n,pts:raw})=>{
   const poly=unique(raw),c=mean(poly),u=V(0,1,0);
   if(Math.abs(n.dot(u))>.95)u.set(1,0,0);u.cross(n).normalize();const v=n.clone().cross(u);
   poly.sort((a,b)=>Math.atan2(a.clone().sub(c).dot(v),a.clone().sub(c).dot(u))-Math.atan2(b.clone().sub(c).dot(v),b.clone().sub(c).dot(u)));
   const corners=poly.filter((p,i)=>poly[(i+1)%poly.length].clone().sub(p).cross(p.clone().sub(poly[(i-1+poly.length)%poly.length])).length()>1e-7);
   return corners.map(v=>lookup.get(v.toArray().map(n=>n.toFixed(5)).join(',')));
  });
  const shape=new CANNON.ConvexPolyhedron({vertices,faces});
  let volume=0;for(const f of p.faces)for(let j=1;j<f.points.length-1;j++)volume+=f.points[0].dot(f.points[j].clone().cross(f.points[j+1]))/6;
  const mass=Math.max(.035,Math.abs(volume)*.2);
  const body=new CANNON.Body({mass,material,shape,linearDamping:.55,angularDamping:.72,sleepSpeedLimit:.10,sleepTimeLimit:.7});
  const loc=center.clone().add(p.offset).add(V(0,HEIGHT,0));body.position.set(...loc.toArray());
  body.velocity.set(center.x*.3, .12+((i*7)%5)*.025,center.z*.3);
  body.angularVelocity.set(.15*Math.sin(i*1.3),.12*Math.cos(i*2.1),-.15*Math.cos(i*.9));
  world.addBody(body);return body;
 });
 const frames=[],impacts=[];let elapsed=0;
 bodies.forEach((b,i)=>b.addEventListener('collide',e=>{
  const speed=Math.abs(e.contact.getImpactVelocityAlongNormal());
  if(speed>1.2)impacts.push({t:release+elapsed,speed,piece:i});
 }));
 for(let f=0;f<=Math.ceil((6-release)*120);f++){
  elapsed=f/120;
  frames.push(bodies.map(b=>[...b.position.toArray(),...b.quaternion.toArray()].map(n=>+n.toFixed(6))));
  world.step(1/120);
 }
 // Geometry-derived floor test (body centers alone do not detect penetration).
 let minBottom=Infinity,maxRadius=0;
 frames.forEach(frame=>frame.forEach((pose,i)=>{
  const q=new THREE.Quaternion(...pose.slice(3));const center=V(...stages.at(-1)[i].center);
  for(const f of pieces[i].faces)for(const v of f.points){
   const w=v.clone().sub(center).applyQuaternion(q).add(V(...pose.slice(0,3)));
   minBottom=Math.min(minBottom,w.y);maxRadius=Math.max(maxRadius,Math.hypot(w.x,w.z));
  }
 }));
 return {count,cutTimes,release,stages,frames,impacts,checks:{pieces:pieces.length,minBottom,maxRadius}};
}
mkdirSync('assets',{recursive:true});
const data={fps:120,height:HEIGHT,radii:R,shotLength:6,duration:18,planes:PLANES.map(p=>({n:p.n.toArray(),d:p.d})),shots:[1,3,7].map(bake)};
writeFileSync('assets/simulation.json',JSON.stringify(data));
writeFileSync('assets/events.json',JSON.stringify(data.shots.flatMap((s,i)=>[
 ...s.cutTimes.map(t=>({type:'cut',t:t+i*6})),...s.impacts.map(e=>({type:'impact',...e,t:e.t+i*6}))
]),null,2));
writeFileSync('simulation-report.json',JSON.stringify(data.shots.map(s=>s.checks),null,2));
console.log(JSON.stringify(data.shots.map(s=>({cuts:s.count,...s.checks})),null,2));
