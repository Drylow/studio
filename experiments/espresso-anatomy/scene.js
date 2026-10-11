import * as THREE from 'three';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {gsap} from 'gsap';
const W=1920,H=1080,D=36;
const renderer=new THREE.WebGLRenderer({canvas:document.getElementById('scene'),antialias:true});
renderer.setSize(W,H,false);renderer.setPixelRatio(1);renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.98;
const scene=new THREE.Scene();scene.background=new THREE.Color('#eee9df');scene.fog=new THREE.Fog('#eee9df',22,48);
const pmrem=new THREE.PMREMGenerator(renderer);scene.environment=pmrem.fromScene(new RoomEnvironment(),.04).texture;
const camera=new THREE.PerspectiveCamera(34,W/H,.1,80);
scene.add(new THREE.HemisphereLight(0xfff8ed,0xa3aaa4,1.55));
const key=new THREE.DirectionalLight(0xfff3dc,4.2);key.position.set(-3,9,5);key.castShadow=true;key.shadow.mapSize.set(2048,2048);Object.assign(key.shadow.camera,{left:-8,right:8,top:8,bottom:-8,near:.5,far:30});key.shadow.normalBias=.035;key.shadow.bias=-.0002;scene.add(key);
const rim=new THREE.DirectionalLight(0xe4f0ff,2.3);rim.position.set(6,5,-5);scene.add(rim);
const mat=(c,m=0,r=.4)=>new THREE.MeshStandardMaterial({color:c,metalness:m,roughness:r});
const ivory=mat('#d5d7d0',.58,.24),chrome=mat('#c3cdc9',.9,.2),dark=mat('#262c2a',.35,.28),rubber=mat('#181e1c',.05,.62),copper=mat('#b46b3e',.78,.26),brass=mat('#b39350',.8,.28),ceramic=mat('#f8eee0',.06,.23),cold=mat('#4baca8',.2,.24),coffeeMat=mat('#512712',.06,.3),crema=mat('#c89049',.05,.46);
const glass=new THREE.MeshPhysicalMaterial({color:'#d5eeeb',roughness:.12,transparent:true,opacity:.23,depthWrite:false,side:THREE.DoubleSide});
const machine=new THREE.Group();scene.add(machine);machine.position.x=.65;
const cube=(p,w,h,d,x,y,z,m,b=.06)=>{const o=new THREE.Mesh(new RoundedBoxGeometry(w,h,d,3,b),m);o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;p.add(o);return o;};
const cyl=(p,r,h,x,y,z,m,rt=r)=>{const o=new THREE.Mesh(new THREE.CylinderGeometry(rt,r,h,64,1),m);o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;p.add(o);return o;};
const ring=(p,r,t,x,y,z,m,rot=true)=>{const o=new THREE.Mesh(new THREE.TorusGeometry(r,t,12,64),m);o.position.set(x,y,z);if(rot)o.rotation.x=Math.PI/2;p.add(o);o.castShadow=true;return o;};
function pipe(p,pts,r,m){const c=new THREE.CatmullRomCurve3(pts.map(a=>new THREE.Vector3(...a)),false,'centripetal');const o=new THREE.Mesh(new THREE.TubeGeometry(c,100,r,12,false),m);p.add(o);o.castShadow=true;return {curve:c,mesh:o};}
function bolt(p,x,y,z){cyl(p,.044,.036,x,y,z,chrome);cube(p,.043,.008,.008,x,y+.02,z,dark,.001);}
const ground=new THREE.Mesh(new THREE.PlaneGeometry(180,180),mat('#d2cabc',0,.78));ground.rotation.x=-Math.PI/2;ground.position.y=-.04;ground.receiveShadow=true;scene.add(ground);
// Base, feet, tray, frame.
cube(machine,3.7,.22,3.1,0,.24,0,ivory,.13);cube(machine,3.25,.16,2.8,0,.12,0,dark,.08);
for(const x of [-1.4,1.4])for(const z of [-1.12,1.12])cyl(machine,.16,.16,x,.03,z,rubber);
cube(machine,3.15,.13,1.1,0,.4,.85,chrome,.04);cube(machine,2.93,.033,.92,0,.48,.87,dark,.02);
for(let i=0;i<23;i++)cube(machine,.065,.025,.79,-1.36+i*.123,.505,.87,chrome,.01);
for(const x of [-1.57,1.57]){cube(machine,.09,3.25,.12,x,2.02,-1,chrome,.02);cube(machine,.09,3,.1,x,2.14,.2,chrome,.02);}
cube(machine,3.12,.1,1.58,0,3.65,-.48,chrome,.02);
const shell=new THREE.Group();machine.add(shell);
const left=cube(shell,.13,3.36,2.5,-1.72,2,-.25,ivory.clone(),.07),right=cube(shell,.13,3.36,2.5,1.72,2,-.25,ivory.clone(),.07),back=cube(shell,3.4,3.34,.12,0,2,-1.48,ivory.clone(),.06),lid=cube(shell,3.62,.14,2.8,0,3.77,-.2,ivory.clone(),.1);
const front=cube(shell,3.32,2.47,.09,0,1.91,.79,ivory.clone(),.03);
// Machined service-panel fasteners: face the viewer, stay attached during separation.
for(const x of [-1.5,1.5])for(const y of [-1.05,1.05]){const b=cyl(front,.035,.025,x,y,.065,chrome);b.rotation.x=Math.PI/2;}
for(let i=0;i<9;i++)cube(lid,.085,.012,1.04,-.7+i*.18,.075,0,dark,.015);
const fascia=cube(machine,3.36,.7,.19,0,3.22,1.05,ivory,.06);
for(const x of [-1.4,1.4]){const dial=cyl(machine,.21,.16,x,3.24,1.2,dark);dial.rotation.x=Math.PI/2;for(let i=0;i<24;i++){const a=i*Math.PI/12,o=new THREE.Mesh(new THREE.SphereGeometry(.017,8,6),chrome);o.position.set(x+.19*Math.cos(a),3.24+.19*Math.sin(a),1.29);machine.add(o);}}
const gauge=new THREE.Group();gauge.position.set(0,3.26,1.17);machine.add(gauge);
const face=cyl(gauge,.225,.05,0,0,0,ceramic);face.rotation.x=Math.PI/2;ring(gauge,.234,.024,0,0,.02,chrome,false);
for(let i=0;i<13;i++){const a=-2.5+i*.416,o=cube(gauge,.012,.04,.007,Math.sin(a)*.175,Math.cos(a)*.175,.04,dark,.001);o.rotation.z=-a;}
const needle=new THREE.Group();gauge.add(needle);cube(needle,.013,.15,.014,0,.065,.051,copper,.001);const np=cyl(gauge,.025,.02,0,0,.06,dark);np.rotation.x=Math.PI/2;
for(let i=0;i<2;i++){const btn=cyl(machine,.065,.04,.52+i*.19,3.25,1.18,i?cold:dark);btn.rotation.x=Math.PI/2;}
// Reservoir.
const tank=new THREE.Group();machine.add(tank);tank.position.set(-1.03,.62,-.63);
cube(tank,.79,2.15,.86,0,1.075,0,glass,.07);cube(tank,.7,1.62,.76,0,.86,0,new THREE.MeshPhysicalMaterial({color:'#4c9996',transparent:true,opacity:.48,roughness:.23,metalness:.05,depthWrite:false}),.04);cube(tank,.85,.1,.92,0,2.18,0,dark,.03);
for(let i=0;i<5;i++)cube(tank,.15,.015,.015,.235,.45+i*.32,.45,chrome,.003);
cyl(tank,.19,.065,0,2.265,0,chrome);ring(tank,.12,.02,0,2.306,0,dark);
// Vibration pump, brackets and connectors.
const pump=new THREE.Group();machine.add(pump);pump.position.set(-.98,.91,.48);
cube(pump,.73,.1,.7,0,-.32,0,dark,.03);const body=cyl(pump,.24,.63,0,0,0,copper);body.rotation.z=Math.PI/2;
cube(pump,.35,.48,.5,0,0,0,dark,.04);const valve=cyl(pump,.12,.24,.43,0,0,brass);valve.rotation.z=Math.PI/2;
for(const x of [-.24,.24]){const b=cyl(pump,.25,.065,x,0,0,chrome);b.rotation.z=Math.PI/2;bolt(pump,x,-.245,.25);}
// Open boiler shell: front segment intentionally removed for the explanatory view.
const boiler=new THREE.Group();machine.add(boiler);boiler.position.set(.47,1.95,-.25);
const boilerShell=new THREE.Mesh(new THREE.CylinderGeometry(.61,.61,1.72,80,1,true,Math.PI*.12,Math.PI*1.5),copper);boilerShell.rotation.y=Math.PI*.3;boiler.add(boilerShell);boilerShell.castShadow=true;
cyl(boiler,.64,.1,0,-.86,0,brass);cyl(boiler,.64,.11,0,.86,0,brass);
for(const y of [-.67,.67])ring(boiler,.623,.043,0,y,0,chrome);
for(let i=0;i<8;i++){const a=i*Math.PI/4;bolt(boiler,.51*Math.sin(a),.935,.51*Math.cos(a));}
const waterCore=cyl(boiler,.535,1.51,0,-.045,0,new THREE.MeshPhysicalMaterial({color:'#72bbb1',roughness:.18,transparent:true,opacity:.32,depthWrite:false}));
const coilPoints=[];for(let i=0;i<=240;i++){const a=i/240*Math.PI*12;coilPoints.push([Math.cos(a)*.37,-.58+i/240*1.15,Math.sin(a)*.37]);}
const coilMat=mat('#944324',.58,.35);pipe(boiler,coilPoints,.035,coilMat);
cyl(boiler,.08,.2,.24,1.02,0,brass);cyl(boiler,.08,.2,-.21,1.02,0,chrome);cube(machine,.95,.08,.86,.47,1.02,-.25,dark,.04);
// Brewing group and portafilter.
const group=new THREE.Group();machine.add(group);group.position.set(.08,2.36,1.03);
cube(machine,3.12,.1,.12,0,2.42,.6,chrome,.02);cube(machine,.22,.14,.5,.08,2.42,.82,chrome,.03);
cyl(group,.46,.24,0,.04,0,brass);cyl(group,.5,.12,0,-.14,0,chrome);cyl(group,.44,.2,0,-.28,0,chrome,.5);ring(group,.45,.032,0,-.37,0,dark);
cyl(group,.35,.17,0,-.43,0,chrome,.43);cyl(group,.32,.02,0,-.335,0,coffeeMat);
const handle=new THREE.Group();group.add(handle);const neck=cyl(handle,.09,.38,.38,-.38,.14,chrome);neck.rotation.z=Math.PI/2;
const grip=cyl(handle,.14,.78,.91,-.38,.14,mat('#3d2b22',.05,.4),.105);grip.rotation.z=Math.PI/2;
for(let i=0;i<4;i++){const rr=ring(handle,.14,.004,.75+i*.08,-.38,.14,dark);rr.rotation.set(0,Math.PI/2,0);}
pipe(group,[[0,-.5,0],[0,-.63,.03],[.16,-.7,.07]],.07,chrome);cyl(group,.07,.1,.16,-.73,.07,chrome);
pipe(machine,[[1.28,2.88,1],[1.48,2.5,1.15],[1.42,1.6,1.42],[1.22,1.24,1.48]],.045,chrome);cyl(machine,.074,.18,1.22,1.17,1.48,dark);
// Plumbing with identifiable terminal fittings. Flow markers are explanatory overlays.
const routeCold=pipe(machine,[[-1.03,.67,-.2],[-1.3,.64,.08],[-1.36,.89,.48],[-1.25,.91,.48]],.04,chrome);
const routePump=pipe(machine,[[-.42,.91,.48],[-.2,.91,.5],[-.13,1.15,.43],[.01,1.29,.23]],.042,copper);
const routeHot=pipe(machine,[[.23,2.96,-.25],[.23,3.06,.18],[.1,2.95,.6],[.08,2.52,1.03]],.047,copper);
for(const [x,y,z]of [[-1.03,.67,-.2],[-1.25,.91,.48],[-.42,.91,.48],[.01,1.29,.23],[.23,2.96,-.25],[.08,2.52,1.03]]){const m=new THREE.Mesh(new THREE.IcosahedronGeometry(.088,0),brass);m.position.set(x,y,z);machine.add(m);}
const flow=new THREE.Group();machine.add(flow);const markers=[];
for(const [idx,r]of [routeCold,routePump,routeHot].entries())for(let i=0;i<13;i++){const o=new THREE.Mesh(new THREE.SphereGeometry(.052,12,8),mat(idx===2?'#f4a54d':'#65d5cc',.15,.22));flow.add(o);markers.push({o,c:r.curve,i,idx});}
// Ceramic demitasse and crema.
const cup=new THREE.Group();machine.add(cup);cup.position.set(.24,.52,1.1);
const profile=[[0,0],[.23,0],[.29,.05],[.35,.12],[.4,.47],[.405,.57],[.385,.59],[.365,.565],[.35,.16],[.27,.08],[0,.08]].map(([x,y])=>new THREE.Vector2(x,y));
const cupBody=new THREE.Mesh(new THREE.LatheGeometry(profile,80),ceramic);cup.add(cupBody);cupBody.castShadow=true;cupBody.receiveShadow=true;
const cupHandle=ring(cup,.19,.05,.47,.34,0,ceramic,false);cupHandle.scale.set(1,1.15,1);
cyl(cup,.59,.045,0,-.018,0,ceramic,.61);ring(cup,.51,.012,0,.01,0,ceramic);
const liquid=cyl(cup,.341,.014,0,.1,0,crema),ripple=ring(cup,.13,.008,0,.11,0,mat('#e3b66c',.1,.4));ripple.material.transparent=true;
const stream=cyl(machine,.022,1,.24,1.4,1.1,coffeeMat);stream.visible=false;
const floorRing=ring(scene,3,.007,.65,.007,0,mat('#d6cbbc',0,.9));floorRing.scale.z=.85;
shell.traverse(o=>{if(o.isMesh){o.material=o.material.clone();o.material.transparent=true;}});
const smooth=(a,b,t)=>{const u=THREE.MathUtils.clamp((t-a)/(b-a),0,1);return u*u*(3-2*u);};const lerp=(a,b,u)=>a+(b-a)*u;
const camKeys=[{t:0,p:[8,5.6,11.8],target:[.55,1.95,0]},{t:4,p:[7.2,5.2,11.5],target:[.6,1.96,0]},{t:9,p:[8.4,6.6,13.4],target:[.6,2.06,0]},{t:13,p:[6.8,5.3,10.6],target:[.15,1.86,.05]},{t:18,p:[5.3,4.6,8],target:[.65,2.08,.04]},{t:22,p:[4.9,4.25,7.8],target:[.76,2.15,.15]},{t:26,p:[4,2.9,6.1],target:[.85,1.43,1.05]},{t:30,p:[3.6,2.65,5.8],target:[.86,1.3,1.07]},{t:34,p:[7.7,5.4,12.2],target:[.58,1.9,0]},{t:36,p:[7.5,5.3,12.1],target:[.58,1.9,0]}];
const step=document.getElementById('step'),caption=document.getElementById('caption'),title=document.querySelector('.title'),progress=document.getElementById('progress');
function renderAt(t){
 t=THREE.MathUtils.clamp(t,0,D);let j=0;while(j<camKeys.length-2&&t>camKeys[j+1].t)j++;const a=camKeys[j],b=camKeys[j+1],u=smooth(a.t,b.t,t);
 camera.position.set(...a.p.map((v,i)=>lerp(v,b.p[i],u)));camera.lookAt(new THREE.Vector3(...a.target.map((v,i)=>lerp(v,b.target[i],u))));camera.setViewOffset(W,H,-150,0,W,H);
 const explode=smooth(4.6,9,t),fade=smooth(11,14,t);left.position.set(-1.72-explode,2+explode*.18,-.25);right.position.set(1.72+explode,2+explode*.18,-.25);back.position.z=-1.48-explode*.6;lid.position.y=3.77+explode*1.05;
 front.position.x=-explode*3.8;front.position.z=.79+explode*.12;
 shell.visible=t<14;shell.traverse(o=>{if(o.isMesh){o.material.opacity=1-fade;o.material.depthWrite=fade<.2;}});
 const active=smooth(10,12,t)*(1-smooth(30,31.5,t));flow.visible=active>.01;for(const v of markers){const f=((t*.32+v.i/13)%1+1)%1;v.o.position.copy(v.c.getPointAt(f));v.o.scale.setScalar(active*.94);}
 coilMat.emissive.set('#d05210');coilMat.emissiveIntensity=.65*smooth(15,18,t);waterCore.material.color.set(cold.color).lerp(new THREE.Color('#d9ac62'),smooth(16,20,t));needle.rotation.z=lerp(1.9,-1.4,smooth(11,23,t));
 const pour=smooth(23.4,24.4,t)*(1-smooth(30,31,t)),level=lerp(.1,.45,smooth(24,31,t));liquid.position.y=level;ripple.position.y=level+.014;ripple.scale.setScalar(.45+((t*1.3)%1)*1.6);ripple.material.opacity=pour*(1-((t*1.3)%1))*.6;
 const top=2.36-.78,bottom=.52+level;stream.position.set(.24,(top+bottom)/2,1.1);stream.scale.set(pour,top-bottom,pour);stream.visible=pour>.005;
 const stages=t<5?['01 / L’OBJET','Tout commence à l’intérieur.']:t<11?['02 / SOUS LA CARROSSERIE','Chaque pièce a son rôle.']:t<17?['03 / LE CIRCUIT','L’eau entre. La pompe agit.']:t<23?['04 / LA CHALEUR','L’eau traverse la chaudière.']:t<32?['05 / L’EXTRACTION','Le mécanisme devient espresso.']:['ESPRESSO / VUE INTÉRIEURE','Un quotidien extraordinaire.'];
 step.textContent=stages[0];caption.textContent=stages[1];title.style.opacity=String(1-smooth(9.8,11.2,t)*.82);progress.style.transform=`scaleX(${t/D})`;renderer.render(scene,camera);
}
window.gsap=gsap;const clock={t:0},tl=gsap.timeline({paused:true});tl.to(clock,{t:D,duration:D,ease:'none',onUpdate:()=>renderAt(clock.t)},0);window.__timelines=window.__timelines||{};window.__timelines.espresso=tl;window.espressoTimeline=tl;window.addEventListener('hf-seek',e=>renderAt(e.detail.time));window.renderEspressoAt=renderAt;renderAt(0);
