import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const data=JSON.parse(readFileSync('assets/simulation.json','utf8'));
const dot=(a,b)=>a.reduce((s,n,i)=>s+n*b[i],0);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
function volume(piece){
 let v=0;
 for(const face of piece.faces)for(let i=1;i<face.points.length-1;i++)v+=dot(face.points[0],cross(face.points[i],face.points[i+1]))/6;
 return Math.abs(v);
}
for(const shot of data.shots){
 const expected=volume(shot.stages[0][0]);
 for(const stage of shot.stages){
  const actual=stage.reduce((s,p)=>s+volume(p),0);
  assert.ok(Math.abs(actual-expected)<1e-4,`Volume changed under ${shot.count} cuts: ${actual} / ${expected}`);
  stage.forEach(p=>assert.ok(volume(p)>.001,'Degenerate fragment'));
 }
 assert.equal(shot.cutTimes.length,shot.count);
 const pieces=shot.stages.at(-1).length;
 for(const frame of shot.frames){
  assert.equal(frame.length,pieces);
  frame.forEach(p=>{
   assert.equal(p.length,7);assert.ok(p.every(Number.isFinite));
   assert.ok(Math.abs(Math.hypot(...p.slice(3))-1)<2e-5,'Invalid orientation');
  });
 }
 assert.ok(shot.checks.minBottom>-.03,'Excessive visual floor penetration');
 console.log(`${shot.count} cuts: ${pieces} closed fragments; volume conserved; ${shot.frames.length} finite physics samples; floor tolerance passed.`);
}
