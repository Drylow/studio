import * as THREE from 'three';

// Original stylized props. All poses are absolute functions of composition time.
export function createChefTools(scene, box, height, fruitRadiusY){
 const Y=new THREE.Vector3(0,1,0);
 const smooth=v=>{v=Math.max(0,Math.min(1,v));return v*v*(3-2*v);};
 const saw=new THREE.Group(),wheel=new THREE.Group();saw.add(wheel);scene.add(saw);
 const shape=new THREE.Shape();
 for(let i=0;i<96;i++){
  const angle=i*Math.PI*2/96,r=[2.15,2.48,2.43][i%3];
  const x=Math.cos(angle)*r,y=Math.sin(angle)*r;
  if(i===0)shape.moveTo(x,y);else shape.lineTo(x,y);
 }
 shape.closePath();
 const gear=new THREE.ExtrudeGeometry(shape,{depth:.10,bevelEnabled:false});
 gear.translate(0,0,-.05);gear.rotateX(Math.PI/2);
 const metal=new THREE.MeshStandardMaterial({color:'#b7c2ba',roughness:.45,metalness:.3});
 const disk=new THREE.Mesh(gear,metal);disk.castShadow=true;wheel.add(disk);
 const hub=new THREE.Mesh(new THREE.CylinderGeometry(.43,.43,.18,12),new THREE.MeshStandardMaterial({color:'#352922',roughness:.6}));wheel.add(hub);
 for(let i=0;i<3;i++){
  const a=i*Math.PI*2/3,spoke=box([1.50,.015,.13],[Math.cos(a)*1.15,.065,Math.sin(a)*1.15],'#6b6c51');
  spoke.rotation.y=-a;wheel.add(spoke);
 }
 const motor=box([1.15,.75,.95],[0,-.55,0],'#244c37');saw.add(motor);
 saw.add(box([.25,.46,1.0],[.58,-.55,0],'#6e9852'));

 const rig=new THREE.Group();scene.add(rig);
 const sleeve=box([1.55,.69,.67],[-1.48,-.48,0],'#def2e1');sleeve.rotation.z=-.10;rig.add(sleeve);
 rig.add(box([.24,.77,.74],[-.77,-.40,0],'#f2f0c4'));
 rig.add(box([1.25,.035,.035],[-1.48,-.30,.35],'#b7c2ba'));
 rig.add(box([.09,.09,.04],[-.87,-.36,.40],'#244c37'));
 const palm=box([.61,.65,.47],[-.40,-.30,0],'#efb07a');rig.add(palm);
 // Rounded mitten silhouette with three short fingers wrapping the grip.
 for(let i=0;i<3;i++)rig.add(box([.38,.13,.20],[-.22,-.11-i*.16,.27],'#ffd09b'));
 const thumb=box([.34,.19,.22],[-.29,.12,.15],'#ffd09b');thumb.rotation.z=-.28;rig.add(thumb);
 // A separate palm-up pose supports the underside rather than borrowing
 // the upright pistol grip. Its top meets the fruit's lowest vertex.
 const carryHand=new THREE.Group();scene.add(carryHand);
 carryHand.add(box([1.55,.48,.62],[-1.64,-.05,.12],'#def2e1'));
 carryHand.add(box([.24,.54,.68],[-.82,-.05,.12],'#f2f0c4'));
 carryHand.add(box([1.25,.035,.035],[-1.64,.10,.45],'#b7c2ba'));
 carryHand.add(box([.09,.09,.04],[-.87,.11,.48],'#244c37'));
 carryHand.add(box([1.04,.24,.80],[-.18,0,.10],'#efb07a'));
 for(let i=0;i<3;i++)carryHand.add(box([.34,.22,.20],[.45,0,-.13+i*.24],'#ffd09b'));
 const carryThumb=box([.43,.22,.23],[-.35,.015,.58],'#ffd09b');
 carryThumb.rotation.y=-.25;carryHand.add(carryThumb);
 const gun=new THREE.Group();rig.add(gun);
 gun.add(box([1.50,.36,.38],[.37,.37,0],'#16201f',.8));
 gun.add(box([1.43,.14,.40],[.34,.12,0],'#20312d',.8));
 const grip=box([.36,.73,.34],[-.35,-.29,0],'#16201f',.9);grip.rotation.z=-.19;gun.add(grip);
 gun.add(box([.40,.055,.065],[-.14,-.03,.23],'#352922'));
 gun.add(box([.06,.17,.065],[.08,.025,.23],'#352922'));
 gun.add(box([.08,.08,.25],[1.01,.59,0],'#16201f'));
 for(let i=0;i<5;i++)gun.add(box([.025,.24,.014],[-.18+i*.085,.36,.20],'#47714a'));
 gun.add(box([.025,.15,.19],[1.14,.36,0],'#352922'));
 const flash=new THREE.Mesh(new THREE.IcosahedronGeometry(.24,0),new THREE.MeshBasicMaterial({color:'#ffd09b'}));
 flash.position.set(1.36,.37,0);gun.add(flash);
 const flashCore=box([.13,.09,.10],[1.21,.37,0],'#ffe59a');gun.add(flashCore);
 const bullet=box([.72,.045,.045],[0,0,0],'#ffe59a');scene.add(bullet);
 const impactRing=new THREE.Mesh(new THREE.RingGeometry(.17,.29,8),new THREE.MeshBasicMaterial({color:'#ffd09b',side:THREE.DoubleSide}));
 impactRing.rotation.y=-Math.PI/2;scene.add(impactRing);
 const wounds=Array.from({length:8},(_,i)=>{
  const wound=new THREE.Group();
  const angle=.52+i*.10,y=height+.24+Math.sin(i*2.4)*.22;
  const normal=new THREE.Vector3(Math.cos(angle),.10,Math.sin(angle)).normalize();
  wound.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),normal);
  wound.position.set(Math.cos(angle)*1.54,y,Math.sin(angle)*1.54);
  wound.add(new THREE.Mesh(new THREE.CircleGeometry(.14,8),new THREE.MeshBasicMaterial({color:'#ef5867',side:THREE.DoubleSide})));
  const hole=new THREE.Mesh(new THREE.CircleGeometry(.07,6),new THREE.MeshBasicMaterial({color:'#352922',side:THREE.DoubleSide}));
  hole.position.z=.008;wound.add(hole);scene.add(wound);return wound;
 });

 const crumbs=Array.from({length:64},(_,i)=>{
  const geometry=new THREE.TetrahedronGeometry(.09+(i%5)*.012,0);
  geometry.scale(.65+(i%3)*.35,.6+(i%4)*.19,.8+(i%2)*.35);
  const m=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:i%4===0?'#244c37':'#ef5867',roughness:.82,flatShading:true}));
  m.castShadow=false;scene.add(m);return m;
 });
 const spatula=new THREE.Group();rig.add(spatula);
 spatula.add(box([.14,1.0,.14],[-.34,.42,0],'#352922'));
 spatula.add(box([.57,.65,.10],[-.34,1.18,0],'#b7c2ba'));
 for(let i=0;i<3;i++)spatula.add(box([.065,.35,.012],[-.52+i*.18,1.19,.06],'#244c37'));

 return function pose({tool,t,cutTimes,count,planes,outro=false,intro=false}){
  saw.visible=false;rig.visible=false;carryHand.visible=false;bullet.visible=false;flash.visible=false;flashCore.visible=false;impactRing.visible=false;spatula.visible=false;gun.visible=false;
  crumbs.forEach(m=>m.visible=false);
  wounds.forEach(m=>m.visible=false);
  const elapsed=cutTimes.map(c=>t-c),latest=elapsed.filter(a=>a>=0).at(-1)??99;
  if(tool==='saw'){
   saw.visible=true;
   const path=(i,age)=>{
    const n=new THREE.Vector3(...planes[i].n);
    const tangent=Math.abs(n.y)>.9?new THREE.Vector3(-1,0,0):new THREE.Vector3(-n.z,0,n.x);
    return n.multiplyScalar(planes[i].d).addScaledVector(tangent,age*16.8).add(new THREE.Vector3(0,height,0));
   };
   let pass=0;while(pass<cutTimes.length-1&&t>cutTimes[pass]+.25)pass++;
   const age=t-cutTimes[pass],n=new THREE.Vector3(...planes[pass].n);
   const target=new THREE.Quaternion().setFromUnitVectors(Y,n);
   if(t<cutTimes[0]-.25){
    const u=smooth(t/(cutTimes[0]-.25));
    saw.position.lerpVectors(new THREE.Vector3(6,height+7,-3),path(0,-.25),u);
    // Show the broad face while entering, then align with the real cut plane.
    saw.quaternion.setFromUnitVectors(Y,new THREE.Vector3(.65,.12,.75).normalize()).slerp(target,smooth((u-.5)*2));
   }else if(age<-.25){
    const previousEnd=cutTimes[pass-1]+.25,nextStart=cutTimes[pass]-.25;
    const u=smooth((t-previousEnd)/(nextStart-previousEnd));
    saw.position.lerpVectors(path(pass-1,.25),path(pass,-.25),u);saw.position.y+=Math.sin(u*Math.PI)*1.2;
    saw.quaternion.setFromUnitVectors(Y,new THREE.Vector3(...planes[pass-1].n)).slerp(target,u);
   }else if(age<=.25){saw.position.copy(path(pass,age));saw.quaternion.copy(target);}
   else{
    const u=smooth((age-.25)/.45);saw.position.lerpVectors(path(pass,.25),new THREE.Vector3(7,height+7,-4),u);saw.quaternion.copy(target);
    if(u===1)saw.visible=false;
   }
   saw.scale.setScalar(1);wheel.rotation.y=t*54;
  }
  if(tool==='pistol'||outro){
   rig.visible=true;gun.visible=!outro;spatula.visible=outro;
   const entrance=Math.max(0,Math.min(1,t/.35));
   const fireAge=elapsed.filter(a=>a>=-1/60).at(-1)??99;
   const recoil=fireAge<.075?Math.sin(Math.PI*Math.max(0,fireAge+1/60)/(.075+1/60))*.20:0;
   const hop=outro?Math.max(0,Math.sin(t*Math.PI*3))*.22:0;
   rig.position.set(-2.9-(1-entrance)*3-recoil,height+.05+hop,1.0);
   rig.rotation.set(0,.22,outro?.12+Math.sin(t*Math.PI*3)*.035:recoil*.35);
   if(!outro){
    const hits=elapsed.filter(a=>a>=0).length;
    wounds.forEach((m,i)=>m.visible=i<hits&&t<cutTimes.at(-1)+.045);
    flash.visible=fireAge>=-1/60&&fireAge<.035;flashCore.visible=flash.visible;
    const brightness=Math.max(0,1-(fireAge+1/60)/.052);
    flash.scale.set(1.1*brightness,.55*brightness,.55*brightness);
    // A one-frame tracer and an immediate hit replace the slow projectile.
    if(fireAge>=-1/60&&fireAge<0){
     bullet.visible=true;bullet.position.set(-1.38,height+.42,.57);bullet.rotation.y=.22;
    }
    if(latest>=0&&latest<.055){
     impactRing.visible=true;impactRing.position.set(-1.48,height+.32,.30);
     impactRing.scale.setScalar(.5+latest*14);
    }
    let slot=0;
    elapsed.forEach((age,event)=>{
     if(age<0||age>1.0)return;
     const number=8+Math.min(count,8)*2;
     for(let j=0;j<number&&slot<crumbs.length;j++){
      const m=crumbs[slot++],a=j*2.399963+event*.83,speed=1.3+(j%7)*.22;
      // Eject chips from the entry wound and far side along the firing axis.
      const side=j%3===0?-1:1;
      m.visible=true;m.position.set(side*(1.25+age*speed*2.1),height+.32+Math.sin(a)*.16+age*(.9+(j%3)*.4)-3.8*age*age,.30+Math.cos(a)*(.16+age*speed*.65));
      m.position.y=Math.max(.43,m.position.y);m.rotation.set(age*(j%4+1),a+age*2,age*3);
      m.scale.setScalar(Math.min(1,(1.0-age)*5));
     }
    });
   }
  }
  // A sleeve and empty hand briefly follow the first knife launch.
  if(intro&&t<1.05){
   const arrival=smooth(t/.72),withdraw=smooth((t-.76)/.29);
   carryHand.visible=true;
   carryHand.position.set(-5*(1-arrival)-withdraw*6,height-fruitRadiusY-.12-withdraw*.22,0);
   carryHand.rotation.set(0,0,withdraw*.10);
  }else if(tool==='machete'&&count===1&&t<.60){
   rig.visible=true;rig.position.set(-4.3-Math.max(0,t-.17)*8,height-.25,1.0);rig.rotation.set(0,.22,-.12);
  }
 };
}
