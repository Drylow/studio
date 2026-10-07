import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import * as THREE from 'three';
const d=JSON.parse(readFileSync('assets/simulation.json')),events=JSON.parse(readFileSync('assets/events.json'));
const assert=(condition,message)=>{if(!condition)throw Error(message);},V=a=>new THREE.Vector3(...a);
const key=v=>v.map(n=>n.toFixed(5)).join(',');
let poseCount=0,minimum=Infinity,maximum=0,volumeError=0,unitError=0;
const localVertices={};
for(const [id,g] of Object.entries(d.geometries)){
 const edges=new Map();let volume=0;
 for(const face of g.faces){
  assert(face.points.length>=3,'Incomplete face '+id);
  for(let i=0;i<face.points.length;i++){
   const a=key(face.points[i]),b=key(face.points[(i+1)%face.points.length]),k=[a,b].sort().join('|');edges.set(k,(edges.get(k)||0)+1);
  }
  for(let i=1;i<face.points.length-1;i++)volume+=V(face.points[0]).dot(V(face.points[i]).cross(V(face.points[i+1])))/6;
 }
 assert([...edges.values()].every(n=>n===2),'Open fragment '+id);
 assert(volume>0,'Wrong face winding '+id);
 localVertices[id]=[...new Map(g.faces.flatMap(f=>f.points).map(v=>[key(v),V(v).sub(V(g.center))])).values()];
}
let cursor=0,barCount=0;
for(const s of d.trials){
 assert(s.start===cursor,'Incorrect trial boundary');cursor=+(cursor+s.length).toFixed(3);
 assert(s.bars.length===s.count,'Counter mismatch');
 barCount+=s.count;
 for(const bar of s.bars){
  const initial=d.size.reduce((a,n)=>a*n,1),sum=bar.ids.reduce((a,id)=>a+d.geometries[id].volume,0);
  volumeError=Math.max(volumeError,Math.abs(sum-initial));assert(Math.abs(sum-initial)<1e-6,'Lost chocolate volume');
  const first=Math.ceil(bar.hit*d.fps-1e-7);
  assert(bar.hit>d.release&&bar.hit<3,'Invalid contact time');
  assert(bar.frames.slice(0,first).every(f=>f.length===1),'Fracture before contact');
  assert(bar.frames.slice(first).every(f=>f.length===bar.ids.length),'Missing fragments');
  const pre=bar.frames[first-1][0];
  if(s.tool==='fork')assert(Math.abs(pre[1]-d.size[1]/2-d.forkTop)<.15,'Break did not happen at the fork');
  if(s.tool==='jackhammer')assert(Math.abs(pre[1]-d.size[1]/2-3.05)<.23,'Break missed the upward chisel');
  if(s.tool==='glove')assert(Math.abs(pre[1]-(s.base+s.bars.indexOf(bar)*d.gap))<.06,'Chocolate fell before the glove hit');
  assert(events.some(e=>e.type==='crunch'&&e.chapter===d.trials.indexOf(s)&&e.bar===s.bars.indexOf(bar)&&Math.abs(e.t-s.start-bar.hit)<1e-6),'SFX contact mismatch');
  bar.frames.forEach((frame,i)=>frame.forEach((p,j)=>{
   poseCount++;assert(p.every(Number.isFinite),'Non-finite pose');
   const q=new THREE.Quaternion(...p.slice(3));unitError=Math.max(unitError,Math.abs(q.length()-1));
   const vertices=i<first?[new THREE.Vector3(0,-d.size[1]/2,0)]:localVertices[bar.ids[j]];
   for(const v of vertices){const point=v.clone().applyQuaternion(q).add(V(p.slice(0,3)));minimum=Math.min(minimum,point.y);maximum=Math.max(maximum,Math.hypot(point.x,point.z));}
  }));
 }
}
assert(minimum>-.015,'Fragment crossed the ground');assert(maximum<8,'Debris escaped the tabletop view');assert(unitError<2e-5,'Invalid rotation');
assert(d.duration===23.3&&d.outroStart===cursor,'Wrong duration');
assert(d.trials.map(t=>t.tool).join(',')==='fork,fork,glove,glove,jackhammer,jackhammer','Wrong tool progression');
const report={ok:true,bars:barCount,geometries:Object.keys(d.geometries).length,poseCount,minimumBottom:minimum,maximumRadius:maximum,volumeError,unitError};
mkdirSync('qa',{recursive:true});writeFileSync('qa/simulation-report.json',JSON.stringify(report,null,2));console.log(report);
