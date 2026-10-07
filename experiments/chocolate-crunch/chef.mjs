import * as THREE from 'three';
// Geometry and colours of the approved Watermelon sleeve, palm and spatula.
export function createChef(scene,box){
 const smooth=v=>{v=Math.max(0,Math.min(1,v));return v*v*(3-2*v);};
 const carry=new THREE.Group();scene.add(carry);
 carry.add(box([3.10,.48,.62],[-2.42,-.05,.12],'#def2e1'));
 carry.add(box([.24,.54,.68],[-.82,-.05,.12],'#f2f0c4'));
 carry.add(box([2.75,.035,.035],[-2.42,.10,.45],'#b7c2ba'));
 carry.add(box([.09,.09,.04],[-.87,.11,.48],'#244c37'));
 carry.add(box([1.04,.24,.80],[-.18,0,.10],'#efb07a'));
 for(let i=0;i<3;i++)carry.add(box([.34,.22,.20],[.45,0,-.13+i*.24],'#ffd09b'));
 const thumb=box([.43,.22,.23],[-.35,.015,.58],'#ffd09b');thumb.rotation.y=-.25;carry.add(thumb);
 const happy=new THREE.Group();scene.add(happy);
 const sleeve=box([1.55,.69,.67],[-1.48,-.48,0],'#def2e1');sleeve.rotation.z=-.10;happy.add(sleeve);
 happy.add(box([.24,.77,.74],[-.77,-.40,0],'#f2f0c4'));
 happy.add(box([1.25,.035,.035],[-1.48,-.30,.35],'#b7c2ba'));
 happy.add(box([.09,.09,.04],[-.87,-.36,.40],'#244c37'));
 happy.add(box([.61,.65,.47],[-.40,-.30,0],'#efb07a'));
 for(let i=0;i<3;i++)happy.add(box([.38,.13,.20],[-.22,-.11-i*.16,.27],'#ffd09b'));
 happy.add(box([.34,.19,.22],[-.29,.12,.15],'#ffd09b'));
 happy.add(box([.14,1,.14],[-.34,.42,0],'#352922'));
 happy.add(box([.57,.65,.10],[-.34,1.18,0],'#b7c2ba'));
 for(let i=0;i<3;i++)happy.add(box([.065,.35,.012],[-.52+i*.18,1.19,.06],'#244c37'));
 return ({time,first,outro,base})=>{
  carry.visible=first&&!outro&&time<1.05;happy.visible=outro;
  const arrival=smooth(time/.72),withdraw=smooth((time-.76)/.29);
  carry.position.set(-5*(1-arrival)-withdraw*6,base-.09-.12-withdraw*.22,1.0);
  carry.rotation.set(0,0,withdraw*.10);
  const hop=Math.max(0,Math.sin(time*Math.PI*3))*.22;
  happy.position.set(-2.4-(1-Math.min(1,time/.35))*3,2.8+hop,1);
  happy.rotation.set(0,.22,.12+Math.sin(time*Math.PI*3)*.035);
  return new THREE.Vector3(happy.position.x-.35,happy.position.y+.65,1);
 };
}
