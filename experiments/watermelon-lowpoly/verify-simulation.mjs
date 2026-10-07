import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const data=JSON.parse(readFileSync('assets/simulation.json','utf8'));
assert.deepEqual(data.shots.filter(s=>s.tool==='machete').slice(1).map(s=>s.count),[1,4,8,16,32]);
for(const tool of ['saw','pistol'])assert.deepEqual(data.shots.filter(s=>s.tool===tool).map(s=>s.count),[1,4,8]);
assert.equal(data.duration,41.8);
assert.equal(data.outroStart,40.3);
assert.equal(data.shots[0].count,0,'No cutting teaser is allowed');
assert.deepEqual(data.shots[0].cutTimes,[],'Intro must have no blade launches');
assert.equal(data.shots[1].count,1,'First cutting chapter must be 1 CUT');
for(const s of data.shots.filter(s=>s.tool==='pistol'&&s.count>1)){
 const spacing=s.count===4?.12:.08;
 assert.ok(s.cutTimes.every((c,i)=>i===0||Math.abs(c-s.cutTimes[i-1]-spacing)<1e-7),'Pistol burst is too slow');
}
data.shots.forEach((s,i)=>{
 if(i)assert.ok(Math.abs(s.start-(data.shots[i-1].start+data.shots[i-1].length))<1e-7,'Gap between chapters');
 assert.ok(s.cutTimes.every((t,j)=>t>=0&&t<s.length&&(j===0||t>s.cutTimes[j-1])),'Invalid cut cadence');
});
const events=JSON.parse(readFileSync('assets/events.json','utf8')).filter(e=>e.type==='cut');
assert.equal(events.length,74,'Missing cutting sound event');
assert.equal(JSON.parse(readFileSync('assets/events.json','utf8')).filter(e=>e.type==='shot').length,13,'Missing projectile sound event');
const dot=(a,b)=>a.reduce((s,n,i)=>s+n*b[i],0);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
function volume(piece){
 let v=0;
 for(const face of piece.faces)for(let i=1;i<face.points.length-1;i++)v+=dot(face.points[0],cross(face.points[i],face.points[i+1]))/6;
 return Math.abs(v);
}
for(const [i,count] of [18,40,100].entries()){
 const shot=data.shots.filter(s=>s.tool==='pistol')[i],pieces=shot.stages.at(-1).map(id=>data.geometries[id]);
 assert.equal(pieces.length,count,'Projectile rubble count changed');
 const volumes=pieces.map(volume);
 assert.ok(Math.max(...volumes)/Math.min(...volumes)>3,'Projectile pieces must have unequal volumes');
 const oblique=pieces.flatMap(p=>p.faces.filter(f=>f.kind==='flesh')).filter(f=>{
  const a=f.points[1].map((n,i)=>n-f.points[0][i]),b=f.points[2].map((n,i)=>n-f.points[0][i]);
  const normal=cross(a,b),length=Math.hypot(...normal);
  return length>1e-6&&Math.max(...normal.map(Math.abs))/length<.98;
 });
 assert.ok(oblique.length>pieces.length,'Projectile fractures must be oblique, not an axis-aligned grid');
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
 if(shot.start===0){assert.equal(shot.stages.length,1,'Intro must keep the fruit intact');continue;}
 const pieces=shot.stages.at(-1).length;
 for(const frame of shot.frames){
  assert.equal(frame.length,pieces);
  frame.forEach(p=>{
   assert.equal(p.length,7);assert.ok(p.every(Number.isFinite));
   assert.ok(Math.abs(Math.hypot(...p.slice(3))-1)<2e-5,'Invalid orientation');
  });
 }
 assert.ok(shot.checks.minBottom>-.03,'Excessive visual floor penetration');
 console.log(`${shot.tool} ${shot.count}: ${pieces} closed fragments; volume conserved; ${shot.frames.length} finite physics samples; floor tolerance passed.`);
}
