import test from 'node:test';
import assert from 'node:assert/strict';
import {newProject,buildTimeline,validateProject} from '../model.mjs';
import {youtubeUrl} from '../media.mjs';
const media={clip:{duration:20}};
const event=(id,at)=>({id,at,rating:'brilliant',player:0,title:'Trap',comment:'A precise explanation.',quote:'',hold:3.5,score:2,zoom:1.035,placement:'right'});
const fixture=()=>({...newProject(),shots:[{id:'s1',mediaId:'clip',in:2,out:10,volume:1,moves:[event('m1',4),event('m2',7)]}]});
test('pauses insert time without deleting or repeating any live source frames',()=>{
  const p=fixture();validateProject(p,media);const t=buildTimeline(p);
  assert.equal(t.durationInFrames,450);assert.deepEqual(t.segments.map(s=>s.duration),[60,105,90,105,90]);
  assert.deepEqual(t.segments.filter(s=>s.kind==='play').map(s=>[s.sourceFrame,s.sourceFrame+s.duration]),[[60,120],[120,210],[210,300]]);
  assert.deepEqual(t.segments.filter(s=>s.kind==='hold').map(s=>s.sourceFrame),[119,209]);
  for(let i=1;i<t.segments.length;i++)assert.equal(t.segments[i].from,t.segments[i-1].from+t.segments[i-1].duration);
});
test('nonzero trims, 24 fps and start-of-clip pauses remain frame accurate',()=>{
  const p=fixture();p.fps=24;p.shots[0].moves=[event('m1',2)];const t=buildTimeline(p);assert.equal(t.durationInFrames,276);
  assert.equal(t.segments[0].sourceFrame,48);assert.equal(t.segments[1].sourceFrame,48);
});
test('score carries into the next cut, never resets between source clips',()=>{
  const p=fixture();p.shots.push({id:'s2',mediaId:'clip',in:12,out:14,volume:.7,moves:[]});
  assert.equal(buildTimeline(p).segments.at(-1).score,2);
});
test('reject out of bounds cuts, missing media, simultaneous and out-of-order moves',()=>{
  for(const change of [p=>p.shots[0].out=21,p=>p.shots[0].mediaId='missing',p=>p.shots[0].moves[1].at=4,p=>p.shots[0].moves[1].at=3,p=>p.shots[0].moves[1].at=10]){
    const p=fixture();change(p);assert.throws(()=>validateProject(p,media));
  }
});
test('reject unsafe portrait paths, infinite times, invalid notes and empty commentary',()=>{
  for(const change of [p=>p.players[0].portrait='../secret.png',p=>p.shots[0].moves[0].at=NaN,p=>p.shots[0].moves[0].rating='fake',p=>p.shots[0].moves[0].comment='',p=>p.shots[0].moves[0].hold=0]){
    const p=fixture();change(p);assert.throws(()=>validateProject(p,media));
  }
});
test('YouTube URL handling rejects playlists, credentials, shell payloads and other origins',()=>{
  assert.equal(youtubeUrl('https://youtu.be/UsZNj9srzR8?list=no'),'https://www.youtube.com/watch?v=UsZNj9srzR8');
  for(const url of ['https://example.com/watch?v=UsZNj9srzR8','https://user@youtube.com/watch?v=UsZNj9srzR8','https://youtube.com/playlist?list=abc','https://youtube.com/watch?v=abc;calc','http://youtube.com/watch?v=UsZNj9srzR8'])assert.throws(()=>youtubeUrl(url));
});
