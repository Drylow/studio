import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const data=JSON.parse(readFileSync('assets/simulation.json','utf8'));
assert.deepEqual(data.shots.slice(1).map(s=>s.count),[1,4,8,16,32]);
assert.equal(data.duration,14.65);
data.shots.forEach((s,i)=>{
 if(i)assert.ok(Math.abs(s.start-(data.shots[i-1].start+data.shots[i-1].length))<1e-7,'Gap between chapters');
 assert.ok(s.cutTimes.every((t,j)=>t>=0&&t<s.length&&(j===0||t>s.cutTimes[j-1])),'Invalid cut cadence');
});
const events=JSON.parse(readFileSync('assets/events.json','utf8')).filter(e=>e.type==='cut');
assert.equal(events.length,93,'Missing slash sound event');
const dot=(a,b)=>a.reduce((s,n,i)=>s+n*b[i],0);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
function volume(piece){
 let v=0;
 for(const face of piece.faces)for(let i=1;i<face.points.length-1;i++)v+=dot(face.points[0],cross(face.points[i],face.points[i+1]))/6;
 return Math.abs(v);
}
for(const shot of data.shots){
 const expected=volume(data.geometries[shot.stages[0][0]]);
 for(const stage of shot.stages){
  const actual=stage.reduce((s,id)=>s+volume(data.geometries[id]),0);
  assert.ok(Math.abs(actual-expected)<1e-4,`Volume changed under ${shot.count} cuts: ${actual} / ${expected}`);
  stage.forEach(id=>assert.ok(volume(data.geometries[id])>1e-5,'Degenerate fragment'));
 }
 assert.equal(shot.cutTimes.length,shot.count);
 for(let i=1;i<shot.stages.length;i++)assert.ok(shot.stages[i].length>shot.stages[i-1].length,'A pass failed to cut the fruit');
 if(shot.start===0){assert.ok(shot.length<shot.release,'Teaser reveals the release');continue;}
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
