import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {DURATION,OUTRO,loads,stateAt,FLOOR,HOME} from './model.mjs';
const data=JSON.parse(readFileSync('assets/piles.json')),heights=data.piles.map(p=>p.height),events=JSON.parse(readFileSync('assets/events.json'));
for(let i=0;i<3;i++){
 const pile=data.piles[i];assert.equal(pile.fries.length,loads[i].count);
 for(const f of pile.fries){assert(f.p.every(Number.isFinite)&&f.q.every(Number.isFinite));assert(f.p[1]>=FLOOR-.01);assert(f.length>.9&&f.length<1.8);}
 const l=loads[i];
 for(const dt of [0,1,2.15,l.contact-.01,l.contact,l.oilAt-.01,l.oilAt,l.crushEnd,l.liftAt,l.liftEnd]){
  const s=stateAt(l.start+dt,heights);assert.equal(s.index,i);assert(s.plate>=FLOOR&&s.plate<=HOME+.001);
  if(dt<l.contact)assert.equal(s.compression,0);
  if(dt<=l.oilAt)assert.equal(s.oil,0);
 }
 const crush=events.filter(e=>e.load===i&&e.kind==='crunch');assert(crush.every(e=>e.t>=l.start+l.contact&&e.t<=l.start+l.crushEnd));
 assert(events.filter(e=>e.load===i&&e.kind==='oil').every(e=>e.t>=l.start+l.oilAt));
}
for(let frame=0;frame<=Math.round(DURATION*60);frame++){
 const t=frame/60,s=stateAt(t,heights),again=stateAt(t,heights);assert.deepEqual(s,again);
 assert(s.compression>=0&&s.compression<=1&&s.oil>=0&&s.oil<=1);assert(s.oil===0||s.compression>0);assert.equal(s.outro,t>=OUTRO);
}
const result={ok:true,frames:Math.round(DURATION*60),fps:60,loads:data.piles.map(p=>p.count),oil_before_contact:false,food_below_floor:false,crunch_timing:true,absolute_time:true};
mkdirSync('qa',{recursive:true});writeFileSync('qa/simulation-report.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
