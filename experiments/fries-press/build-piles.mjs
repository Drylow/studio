import * as C from 'cannon-es';
import {writeFileSync,mkdirSync} from 'node:fs';
import {loads,rand,FLOOR,eventsFor,DURATION,OUTRO} from './model.mjs';
mkdirSync('assets',{recursive:true});
const piles=[];
for(let trial=0;trial<loads.length;trial++){
 const world=new C.World({gravity:new C.Vec3(0,-9.82,0)});
 world.broadphase=new C.SAPBroadphase(world);world.solver.iterations=15;
 world.defaultContactMaterial.friction=.53;world.defaultContactMaterial.restitution=.035;
 const ground=new C.Body({mass:0,shape:new C.Box(new C.Vec3(2.4,.12,2.4)),position:new C.Vec3(0,FLOOR-.12,0)});world.addBody(ground);
 for(const [x,z,sx,sz] of [[-2.24,0,.08,2.4],[2.24,0,.08,2.4],[0,-2.24,2.4,.08],[0,2.24,2.4,.08]])world.addBody(new C.Body({mass:0,shape:new C.Box(new C.Vec3(sx,1.8,sz)),position:new C.Vec3(x,FLOOR+1.8,z)}));
 const items=[];
 for(let i=0;i<loads[trial].count;i++){
  const n=trial*2000+i*17,length=.98+rand(n+1)*.75,width=.16+rand(n+2)*.045,height=.145+rand(n+3)*.025;
  const body=new C.Body({mass:.035,shape:new C.Box(new C.Vec3(length/2,height/2,width/2)),linearDamping:.40,angularDamping:.50});
  body.position.set((rand(n+4)-.5)*3.1,FLOOR+.9+(i/16)*.32,(rand(n+5)-.5)*3.1);
  body.quaternion.setFromEuler((rand(n+6)-.5)*.30,rand(n+7)*Math.PI*2,(rand(n+8)-.5)*.35);
  world.addBody(body);items.push({body,length,width,height,seed:n});
 }
 for(let step=0;step<1440;step++)world.step(1/120);
 let top=0;
 const fries=items.map(({body:b,length,width,height,seed})=>{
  const xaxis=b.quaternion.vmult(new C.Vec3(1,0,0)),yaxis=b.quaternion.vmult(new C.Vec3(0,1,0)),zaxis=b.quaternion.vmult(new C.Vec3(0,0,1));
  top=Math.max(top,b.position.y-FLOOR+Math.abs(xaxis.y)*length/2+Math.abs(yaxis.y)*height/2+Math.abs(zaxis.y)*width/2);
  return {p:b.position.toArray(),q:b.quaternion.toArray(),length,width,height,seed};
 });
 piles.push({count:fries.length,height:top,fries});
 console.log('Settled load',trial+1,fries.length,'fries, height',top.toFixed(3));
}
writeFileSync('assets/piles.json',JSON.stringify({duration:DURATION,outro:OUTRO,piles}));
writeFileSync('assets/events.json',JSON.stringify(eventsFor(piles)));
