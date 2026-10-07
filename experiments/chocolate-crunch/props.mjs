import * as THREE from 'three';
import {toolState,smooth} from './tools.mjs';
export function createCrazyTools(scene,box){
 const gloveRoot=new THREE.Group(),hammerRoot=new THREE.Group();scene.add(gloveRoot,hammerRoot);
 const frame=new THREE.Group();gloveRoot.add(frame);
 frame.add(box([1.6,.30,2.1],[-5.85,.16,0],'#244c37'));
 frame.add(box([.52,3.60,.80],[-6.12,2.02,0],'#47714a'));
 frame.add(box([.35,2.95,.91],[-6.12,2.01,0],'#b7c2ba'));
 frame.add(box([.70,.85,1.25],[-5.92,3.82,0],'#244c37'));
 const fist=new THREE.Group();gloveRoot.add(fist);
 const red=new THREE.MeshStandardMaterial({color:'#ef5867',roughness:.55,flatShading:true});
 const knuckles=new THREE.Mesh(new THREE.SphereGeometry(1,10,6),red);
 knuckles.scale.set(1.16,1.27,1.43);knuckles.castShadow=true;knuckles.receiveShadow=true;fist.add(knuckles);
 fist.add(box([1.15,1.70,2.0],[-.58,-.08,0],'#b93751'));
 const thumb=new THREE.Mesh(new THREE.SphereGeometry(.62,8,5),red);thumb.position.set(.02,-.83,1.03);thumb.scale.set(1,1,1.10);thumb.castShadow=true;fist.add(thumb);
 fist.add(box([.46,1.35,1.47],[-1.24,-.03,0],'#def2e1'));
 fist.add(box([.24,1.08,1.16],[-1.58,-.03,0],'#f2f0c4'));
 fist.add(box([.14,.14,.08],[-1.44,.28,.77],'#244c37'));
 const curve=new THREE.CatmullRomCurve3(Array.from({length:129},(_,i)=>new THREE.Vector3(i/128,Math.sin(i/128*Math.PI*16)*.31,Math.cos(i/128*Math.PI*16)*.31)));
 const coil=new THREE.Mesh(new THREE.TubeGeometry(curve,128,.08,5,false),new THREE.MeshStandardMaterial({color:'#b7c2ba',roughness:.4,metalness:.3}));coil.castShadow=true;gloveRoot.add(coil);
 const motor=new THREE.Group();hammerRoot.add(motor);
 motor.add(box([1.50,.14,1.35],[0,.42,0],'#244c37'));
 motor.add(box([.98,1.34,.88],[0,1.16,0],'#ffe59a'));
 motor.add(box([1.10,.28,.99],[0,.62,0],'#47714a'));
 motor.add(box([.85,.19,.81],[0,1.83,0],'#b7c2ba'));
 for(const x of [-.97,.97]){
  motor.add(box([.55,.22,.23],[x,.97,0],'#16201f'));
  motor.add(box([.15,.61,.23],[x*1.20,1.12,0],'#16201f'));
 }
 for(let i=0;i<4;i++)motor.add(box([.53,.065,.04],[0,.98+i*.15,.46],'#352922'));
 motor.add(box([.20,.16,.06],[.26,1.55,.48],'#ef5867'));
 motor.add(box([.23,.91,.23],[0,2.02,0],'#b7c2ba'));
 const chisel=new THREE.Mesh(new THREE.ConeGeometry(.255,.62,4),new THREE.MeshStandardMaterial({color:'#b7c2ba',roughness:.4,metalness:.25}));
 chisel.rotation.y=Math.PI/4;chisel.position.set(0,2.74,0);chisel.castShadow=true;motor.add(chisel);
 return (tool,t)=>{
  gloveRoot.visible=tool==='glove';hammerRoot.visible=tool==='jackhammer';
  const state=toolState(tool,t);
  fist.position.set(state.x,state.y,0);coil.position.set(-5.70,state.y,0);coil.scale.set(Math.max(.08,state.x-1.76+5.70),1,1);
  // Spring, cuff and glove form a single readable mechanism; absolute poses.
  gloveRoot.position.x=-8*(1-smooth(t/.30));
  motor.position.y=state.y;hammerRoot.position.y=-3.4*(1-smooth(t/.32));
 };
}
