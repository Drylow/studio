import * as T from 'three';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
import {EffectComposer} from 'three/addons/postprocessing/EffectComposer.js';
import {RenderPass} from 'three/addons/postprocessing/RenderPass.js';
import {BokehPass} from 'three/addons/postprocessing/BokehPass.js';
import {OutputPass} from 'three/addons/postprocessing/OutputPass.js';
import {SAOPass} from 'three/addons/postprocessing/SAOPass.js';
import {gsap} from 'gsap';

const W=1920,H=1080,D=36;
const renderer=new T.WebGLRenderer({canvas:document.getElementById('scene'),antialias:true});
renderer.setSize(W,H,false);renderer.setPixelRatio(1);renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.02;renderer.localClippingEnabled=true;
const scene=new T.Scene();scene.background=new T.Color('#0b1014');scene.fog=new T.Fog('#0b1014',19,45);
const camera=new T.PerspectiveCamera(34,W/H,.025,70);
const studio=new T.Scene();studio.background=new T.Color('#252d33');
// Large luminous studio cards create shaped reflections on the machined surfaces.
function card(w,h,x,y,z,power){const p=new T.Mesh(new T.PlaneGeometry(w,h),new T.MeshBasicMaterial({color:new T.Color(power,power*.93,power*.82),side:T.DoubleSide}));p.position.set(x,y,z);p.lookAt(0,1.7,0);studio.add(p);}
card(3,8,-5,4,4,5);card(1.2,7,5,3,-2,7);card(7,1,0,6,2,4);card(4,5,0,3,-7,1.6);
const pmrem=new T.PMREMGenerator(renderer);scene.environment=pmrem.fromScene(studio,.025).texture;scene.environmentIntensity=.8;
scene.add(new T.HemisphereLight('#dbe4e5','#303641',.55));
const key=new T.DirectionalLight('#fff0d8',3.5);key.position.set(-3,7,6);key.castShadow=true;key.shadow.mapSize.set(2048,2048);Object.assign(key.shadow.camera,{left:-7,right:7,top:8,bottom:-5,near:.5,far:30});key.shadow.normalBias=.025;key.shadow.bias=-.0001;scene.add(key);
const rim=new T.DirectionalLight('#c2dcf2',3);rim.position.set(5,5,-4);scene.add(rim);const fill=new T.DirectionalLight('#ffcf99',.8);fill.position.set(0,3,8);scene.add(fill);
const targetBuffer=new T.WebGLRenderTarget(W,H,{type:T.HalfFloatType,samples:4});
const composer=new EffectComposer(renderer,targetBuffer);composer.addPass(new RenderPass(scene,camera));
const ao=new SAOPass(scene,camera,new T.Vector2(W,H));Object.assign(ao.params,{saoIntensity:.022,saoScale:10,saoKernelRadius:24,saoBlurRadius:5,saoBlurStdDev:3});composer.addPass(ao);
const dof=new BokehPass(scene,camera,{focus:8,aperture:.0011,maxblur:.0035});composer.addPass(dof);composer.addPass(new OutputPass());composer.setSize(W,H);
const clamp=T.MathUtils.clamp,lerp=T.MathUtils.lerp;
const ease=(a,b,t)=>{const q=clamp((t-a)/(b-a),0,1);return q*q*(3-2*q);};
const v=a=>new T.Vector3(...a);const byId=id=>document.getElementById(id);

// Fine deterministic directional roughness, no external assets or random render state.
let seed=93751;function rand(){seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;}
const brushedCanvas=document.createElement('canvas');brushedCanvas.width=512;brushedCanvas.height=512;const bc=brushedCanvas.getContext('2d');bc.fillStyle='#999';bc.fillRect(0,0,512,512);for(let i=0;i<1400;i++){const n=100+Math.floor(rand()*70);bc.strokeStyle=`rgb(${n},${n},${n})`;bc.lineWidth=.25+rand()*.7;const y=rand()*512;bc.beginPath();bc.moveTo(0,y);bc.lineTo(512,y);bc.stroke();}const brushed=new T.CanvasTexture(brushedCanvas);brushed.wrapS=brushed.wrapT=T.RepeatWrapping;brushed.repeat.set(2,2);
const physical=(color,metalness=.7,roughness=.25,extra={})=>new T.MeshPhysicalMaterial({color,metalness,roughness,...extra});
const steel=physical('#aeb9b9',.98,.24,{roughnessMap:brushed}),chrome=physical('#e0e4df',1,.13),black=physical('#202b2d',.65,.3,{clearcoat:.5,clearcoatRoughness:.2}),rubber=physical('#111819',0,.7),copper=physical('#be7043',.9,.24,{roughnessMap:brushed}),brass=physical('#b79754',.85,.24),ceramic=physical('#ece7db',.02,.19,{clearcoat:.8}),wood=physical('#493329',.05,.35,{roughnessMap:brushed}),coffee=physical('#29120a',0,.34),blue=physical('#298caf',.05,.23,{transparent:true,opacity:.44,depthWrite:false}),glass=physical('#b4dadf',.0,.13,{transparent:true,opacity:.13,depthWrite:false,side:T.DoubleSide});
const grp=(p,x=0,y=0,z=0)=>{const g=new T.Group();g.position.set(x,y,z);p.add(g);return g;};
function mesh(p,geo,m,x=0,y=0,z=0){const o=new T.Mesh(geo,m);o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;p.add(o);return o;}
const box=(p,w,h,d,x,y,z,m,r=.04)=>mesh(p,new RoundedBoxGeometry(w,h,d,4,r),m,x,y,z);
const cyl=(p,r,h,x,y,z,m,rt=r,n=64)=>mesh(p,new T.CylinderGeometry(rt,r,h,n),m,x,y,z);
function ring(p,r,w,x,y,z,m,flat=true){const o=mesh(p,new T.TorusGeometry(r,w,14,96),m,x,y,z);if(flat)o.rotation.x=Math.PI/2;return o;}
function tube(p,points,r,m){const curve=new T.CatmullRomCurve3(points.map(v),false,'centripetal');return {curve,mesh:mesh(p,new T.TubeGeometry(curve,120,r,12,false),m)};}
function bolt(p,x,y,z,r=.042){const o=cyl(p,r,.045,x,y,z,steel,r,6);box(p,r*.8,.004,.009,x,y+.025,z,rubber,.001);return o;}
function screwFace(p,x,y,z){const s=grp(p,x,y,z);s.rotation.x=Math.PI/2;bolt(s,0,0,0,.028);}
function helix(p,r,h,turns,m,wire=.025){const pts=[];for(let i=0;i<=320;i++){const a=i/320*Math.PI*2*turns;pts.push([Math.cos(a)*r,-h/2+h*i/320,Math.sin(a)*r]);}return tube(p,pts,wire,m).mesh;}
function hollow(p,r,h,thickness,m){const pts=[[r-thickness,-h/2],[r,-h/2],[r,h/2],[r-thickness,h/2],[r-thickness,-h/2]].map(a=>new T.Vector2(...a));return mesh(p,new T.LatheGeometry(pts,96),m);}
function grains(p,r,y,count){const g=new T.IcosahedronGeometry(.018,0),m=physical('#472517',0,.93);const out=new T.InstancedMesh(g,m,count);const dummy=new T.Object3D();for(let i=0;i<count;i++){const a=rand()*Math.PI*2,rr=Math.sqrt(rand())*r;dummy.position.set(rr*Math.cos(a),y+rand()*.05,rr*Math.sin(a));dummy.rotation.set(rand()*4,rand()*4,rand()*4);dummy.scale.set(.55+rand()*.85,.5+rand()*.65,.6+rand()*.6);dummy.updateMatrix();out.setMatrixAt(i,dummy.matrix);out.setColorAt(i,new T.Color().setHSL(.06+rand()*.035,.42,.08+rand()*.085));}out.castShadow=true;out.receiveShadow=true;p.add(out);return out;}
const floor=mesh(scene,new T.PlaneGeometry(100,100),physical('#111b20',.46,.28));floor.rotation.x=-Math.PI/2;floor.position.y=-.07;

function makeBoiler(parent){
 const root=grp(parent),shell=grp(root);
 const shellMat=copper.clone();shellMat.side=T.DoubleSide;
 const rear=mesh(shell,new T.CylinderGeometry(.62,.62,1.66,80,1,true,Math.PI/2,Math.PI),shellMat);
 const front=mesh(shell,new T.CylinderGeometry(.62,.62,1.66,80,1,true,-Math.PI/2,Math.PI),shellMat);
 const top=grp(root,0,.86,0);cyl(top,.67,.12,0,0,0,brass);ring(top,.57,.016,0,.064,0,chrome);for(let i=0;i<8;i++){const a=i*Math.PI/4;bolt(top,Math.sin(a)*.54,.086,Math.cos(a)*.54);}
 cyl(root,.67,.11,0,-.88,0,brass);for(const y of [-.63,.63])ring(root,.635,.034,0,y,0,steel);
 const coilMat=physical('#a95428',.83,.25,{emissive:'#ff6a0a',emissiveIntensity:0});const coil=helix(root,.39,1.18,5.4,coilMat,.044);
 tube(root,[[.39,-.59,0],[.39,-.88,0],[.22,-1.01,.03]],.043,coilMat);tube(root,[[-.32,.59,.23],[-.43,.68,.18],[-.43,-.97,-.18]],.038,coilMat);
 const waterMat=blue.clone();const water=cyl(root,.54,1.49,0,-.04,0,waterMat);water.castShadow=false;water.receiveShadow=false;
 const capA=cyl(top,.095,.23,.23,.16,0,brass,.095,6),capB=cyl(top,.09,.18,-.24,.15,0,steel,.09,6);
 const bubbles=[];const bubbleMat=new T.MeshBasicMaterial({color:'#ffc878',transparent:true,opacity:.35});for(let i=0;i<24;i++){const b=mesh(root,new T.SphereGeometry(.017+(i%4)*.005,10,8),bubbleMat);b.castShadow=false;bubbles.push(b);}
 return {root,front,top,coil,coilMat,water,waterMat,bubbles,animate(t,open,heat){front.position.set(open*1.6,-open*.07,-open*.3);front.rotation.y=-open*.7;top.position.y=.86+open*.24;waterMat.color.set('#399fb5').lerp(new T.Color('#efa147'),heat);waterMat.opacity=.2;coilMat.emissiveIntensity=heat*.95;for(let i=0;i<bubbles.length;i++){const q=(t*.24+i/24)%1,a=i*2.4;const b=bubbles[i];b.visible=heat>.15;b.position.set(Math.cos(a)*.43,-.65+q*1.3,Math.sin(a)*.43);b.scale.setScalar(Math.sin(q*Math.PI)*heat);}}};
}
function makePump(parent){
 const root=grp(parent),body=grp(root);body.rotation.z=-Math.PI/2;
 const outer=physical('#a26743',.88,.3,{side:T.DoubleSide,roughnessMap:brushed});
 const back=mesh(body,new T.CylinderGeometry(.33,.33,1.36,64,1,true,Math.PI/2,Math.PI),outer);
 const front=mesh(body,new T.CylinderGeometry(.33,.33,1.36,64,1,true,-Math.PI/2,Math.PI),outer);
 for(const y of [-.68,.68]){cyl(body,.37,.12,0,y,0,steel);ring(body,.295,.022,0,y+(y<0?-.066:.066),0,rubber);for(let j=0;j<4;j++){const a=j*Math.PI/2;bolt(body,Math.cos(a)*.28,y+.075,Math.sin(a)*.28,.025);}}
 const spring=helix(body,.21,.63,8,steel,.027);spring.position.y=-.2;
 const piston=grp(body);cyl(piston,.255,.095,0,.22,0,chrome);cyl(piston,.083,.65,0,-.09,0,steel);ring(piston,.258,.022,0,.225,0,rubber);
 const fluid=cyl(body,.25,.3,0,.44,0,blue.clone());fluid.castShadow=false;
 const inlet=grp(root,-.84,0,0),outlet=grp(root,.84,0,0);for(const p of [inlet,outlet]){const a=cyl(p,.13,.24,0,0,0,brass,.13,6);a.rotation.z=Math.PI/2;const b=cyl(p,.085,.13,p===inlet?-.16:.16,0,0,chrome);b.rotation.z=Math.PI/2;}
 box(root,1.5,.08,.73,0,-.45,0,black);for(const x of [-.5,.5]){box(root,.12,.25,.67,x,-.33,0,rubber);bolt(root,x,-.395,.23,.03);}
 const motor=cyl(root,.36,.35,-.51,0,0,black);motor.rotation.z=Math.PI/2;
 const flow=grp(root);const particles=[];for(let i=0;i<18;i++){const a=mesh(flow,new T.SphereGeometry(.035,10,8),new T.MeshBasicMaterial({color:'#6bddf4'}));particles.push(a);}
 return {root,front,piston,spring,fluid,animate(t,open,run){front.position.x=open*.86;front.position.z=open*.13;front.rotation.y=open*.18;motor.position.z=-open*.27;const stroke=.21*(.5+.5*Math.sin(t*7))*run;piston.position.y=stroke;spring.scale.y=1+stroke/.63;spring.position.y=-.2+stroke/2;fluid.scale.y=(.3-stroke)/.3;fluid.position.y=.44+stroke/2;flow.visible=run>.1;for(let i=0;i<particles.length;i++){const q=(t*.35+i/18)%1;particles[i].position.set(-1.4+q*2.8,.08*Math.sin(i*2.3),.04+.06*Math.cos(i));}}};
}
function makeBrew(parent){
 const root=grp(parent),upper=grp(root,0,.56,0);cyl(upper,.54,.36,0,.1,0,brass);cyl(upper,.57,.09,0,-.125,0,steel);for(let j=0;j<6;j++){const a=j*Math.PI/3;bolt(upper,.43*Math.cos(a),.295,.43*Math.sin(a),.032);}
 const seal=grp(root,0,.27,0);ring(seal,.455,.036,0,0,0,rubber);
 const shower=grp(root,0,.16,0);cyl(shower,.448,.037,0,0,0,steel);for(let i=0;i<125;i++){const a=i*2.39996,r=.405*Math.sqrt(i/125);cyl(shower,.007,.003,r*Math.cos(a),.021,r*Math.sin(a),rubber,.007,6);}bolt(shower,0,.04,0,.033);
 const puck=grp(root,0,-.035,0);cyl(puck,.407,.15,0,0,0,coffee);grains(puck,.399,.079,1000);
 const basket=grp(root,0,-.23,0);const bs=hollow(basket,.455,.28,.025,steel);ring(basket,.46,.035,0,.16,0,chrome);cyl(basket,.425,.033,0,-.14,0,steel);for(let i=0;i<65;i++){const a=i*2.39996,r=.38*Math.sqrt(i/65);cyl(basket,.008,.003,r*Math.cos(a),-.158,r*Math.sin(a),rubber,.008,6);}
 const holder=grp(root,0,-.45,0);const h=hollow(holder,.5,.18,.05,chrome);cyl(holder,.45,.06,0,-.11,0,steel);tube(holder,[[0,-.13,0],[0,-.29,.08],[.17,-.32,.13]],.065,chrome);
 const handle=grp(holder);const neck=cyl(handle,.09,.45,.5,0,.07,chrome);neck.rotation.z=Math.PI/2;const grip=cyl(handle,.125,.84,1.12,0,.07,wood,.095);grip.rotation.z=Math.PI/2;for(let i=0;i<5;i++){const a=ring(handle,.12,.004,.88+i*.09,0,.07,rubber,false);a.rotation.y=Math.PI/2;}
 const drops=[];for(let i=0;i<65;i++){const d=mesh(root,new T.SphereGeometry(.012,8,6),new T.MeshBasicMaterial({color:'#ecc88b',transparent:true,opacity:.8}));drops.push(d);}
 return {root,upper,seal,shower,puck,basket,holder,drops,animate(t,spread,wet){upper.position.y=.38+spread*.82;seal.position.y=.265+spread*.42;shower.position.y=.215+spread*.19;puck.position.y=.105-spread*.18;basket.position.y=.025-spread*.5;holder.position.y=-.18-spread*.9;holder.rotation.y=spread*.42;for(let i=0;i<drops.length;i++){const q=(t*.65+i/65)%1,a=i*2.39996,rr=.37*Math.sqrt((i+.5)/65);drops[i].visible=wet>.01;drops[i].position.set(rr*Math.cos(a),lerp(.24+spread*.19,.02-spread*.5,q),rr*Math.sin(a));drops[i].scale.set(.7,2.1,.7);}}};
}

const cremaCanvas=document.createElement('canvas');cremaCanvas.width=512;cremaCanvas.height=512;const cx=cremaCanvas.getContext('2d');cx.fillStyle='#a56b32';cx.fillRect(0,0,512,512);for(let i=0;i<1900;i++){const x=rand()*512,y=rand()*512,r=rand()*9+.8;cx.fillStyle=i%3?'#c99650':'#79451f';cx.globalAlpha=.12+rand()*.25;cx.beginPath();cx.ellipse(x,y,r,r*.5,rand()*3,0,Math.PI*2);cx.fill();}cx.globalAlpha=1;const cremaTex=new T.CanvasTexture(cremaCanvas);cremaTex.colorSpace=T.SRGBColorSpace;
function makeCup(parent){
 const root=grp(parent);const profile=[[0,0],[.24,0],[.29,.035],[.35,.12],[.405,.55],[.408,.59],[.386,.612],[.365,.585],[.318,.14],[.25,.07],[0,.07]].map(a=>new T.Vector2(...a));mesh(root,new T.LatheGeometry(profile,96),ceramic);
 const handle=ring(root,.192,.049,.465,.34,0,ceramic,false);handle.scale.y=1.12;cyl(root,.62,.042,0,-.025,0,ceramic,.64);ring(root,.53,.015,0,-.002,0,ceramic);
 const liquid=cyl(root,.337,.015,0,.21,0,physical('#b98a49',.0,.36,{map:cremaTex}));const ripple=[];for(let i=0;i<3;i++){const m=physical('#e5c078',0,.42,{transparent:true,opacity:.4,depthWrite:false});ripple.push(ring(root,.1,.003,0,.22,0,m));}
 const stream=mesh(root,new T.CylinderGeometry(.015,.022,1,20),physical('#723b17',.05,.22));
 const steam=[];for(let j=0;j<5;j++){const pts=[];for(let i=0;i<35;i++){const q=i/34;pts.push([Math.sin(q*6+j)*.028,q*.65,Math.cos(q*4+j)*.026]);}const m=new T.MeshBasicMaterial({color:'#cfd9d6',transparent:true,opacity:.045,depthWrite:false});const o=tube(root,pts,.012,m).mesh;steam.push(o);}
 return {root,liquid,stream,ripple,animate(t,pour,level){const h=.13+.36*level;liquid.position.y=h;liquid.rotation.y=t*.025;stream.visible=pour>.005;stream.position.set(.02,(1.18+h)/2,.015);stream.scale.set(pour*(1+.07*Math.sin(t*31)),1.18-h,pour);for(let i=0;i<ripple.length;i++){const q=(t*.7+i/3)%1;const r=ripple[i];r.position.y=h+.011;r.scale.set(q*3.15,q*3.15,q*3.15);r.material.opacity=(1-q)*.4*pour;}for(let i=0;i<steam.length;i++){steam[i].position.set(Math.sin(i*2.4)*.13,h+.02,Math.cos(i*2.4)*.1);steam[i].rotation.y=t*.2+i;steam[i].scale.y=.8+.15*Math.sin(t+i);}}};
}

// The complete machine and its detachable housing.
const product=grp(scene),parts=grp(product);const casing=grp(product);
box(product,3.12,.2,2.65,0,.22,0,black,.12);box(product,2.87,.08,2.45,0,.105,0,steel,.03);
for(const x of [-1.18,1.18])for(const z of [-.97,.97])cyl(product,.14,.16,x,.04,z,rubber);
box(product,2.63,.12,1.07,0,.37,.64,steel);box(product,2.42,.04,.94,0,.45,.65,black,.02);for(let i=0;i<24;i++)box(product,.042,.032,.86,-1.12+i*.098,.484,.65,chrome,.008);
const shellLeft=box(casing,.095,2.95,2.34,-1.47,1.85,-.18,black),shellRight=box(casing,.095,2.95,2.34,1.47,1.85,-.18,black),shellBack=box(casing,2.86,2.95,.09,0,1.85,-1.32,black),shellTop=box(casing,3.04,.12,2.57,0,3.37,-.1,steel,.08),shellFront=box(casing,2.86,2.03,.07,0,1.61,.7,black,.03);
for(let i=0;i<12;i++)box(shellTop,.04,.008,.98,-.77+i*.14,.065,0,rubber,.003);
for(const x of [-1.29,1.29])for(const y of [-.83,.83])screwFace(shellFront,x,y,.05);
const fascia=box(product,2.95,.61,.19,0,2.99,1.0,steel,.055);
const gauge=grp(product,0,3.01,1.13);const gf=cyl(gauge,.21,.035,0,0,0,physical('#ece5d7',.05,.6));gf.rotation.x=Math.PI/2;ring(gauge,.222,.022,0,0,.015,chrome,false);
for(let i=0;i<15;i++){const a=-2.55+i*.365;const b=box(gauge,.008,.034,.006,Math.sin(a)*.167,Math.cos(a)*.167,.027,rubber,.001);b.rotation.z=-a;}
const needle=grp(gauge);box(needle,.011,.159,.006,0,.059,.041,copper,.001);const pin=cyl(gauge,.022,.01,0,0,.048,black);pin.rotation.x=Math.PI/2;
for(const x of [-1.12,1.12]){const dial=grp(product,x,3.01,1.13);const d=cyl(dial,.167,.15,0,0,0,black);d.rotation.x=Math.PI/2;ring(dial,.161,.009,0,0,.083,chrome,false);for(let j=0;j<36;j++){const a=j*Math.PI/18;box(dial,.013,.022,.05,Math.cos(a)*.165,Math.sin(a)*.165,.04,steel,.002);}}
const on=cyl(product,.035,.035,.49,3.01,1.12,new T.MeshBasicMaterial({color:'#b8e0bc'}));on.rotation.x=Math.PI/2;
for(const x of [-1.31,1.31])box(parts,.055,2.72,.1,x,1.9,-.8,steel,.01);
const tank=grp(parts,-.86,.68,-.5);box(tank,.63,2.04,.72,0,1.02,0,glass,.045);const tankFill=box(tank,.58,1.66,.66,0,.87,0,blue,.03);tankFill.castShadow=false;box(tank,.7,.1,.79,0,2.05,0,black);for(let i=0;i<6;i++)box(tank,.13,.01,.01,.18,.34+i*.25,.37,steel,.002);
const pb=makeBoiler(parts);pb.root.position.set(.44,1.81,-.2);pb.root.scale.setScalar(.83);
const pp=makePump(parts);pp.root.position.set(-.69,.86,.39);pp.root.scale.setScalar(.55);
const pg=makeBrew(parts);pg.root.position.set(.02,1.92,1.0);pg.root.scale.setScalar(.84);
box(parts,2.59,.1,.13,0,2.42,.48,steel,.02);box(parts,.18,.13,.53,.02,2.42,.7,steel,.02);
const pc=makeCup(product);pc.root.position.set(.15,.525,1.10);pc.root.scale.setScalar(.85);
tube(product,[[1.1,2.73,1.03],[1.28,2.54,1.19],[1.29,1.55,1.28],[1.12,1.07,1.46]],.039,chrome);cyl(product,.065,.17,1.12,1.02,1.46,black);
const pathCold=tube(parts,[[-.85,.75,-.2],[-1.13,.69,.04],[-1.16,.86,.37]],.032,steel);
const pathPump=tube(parts,[[-.16,.86,.39],[.06,.86,.39],[.17,1.22,.2]],.037,copper);
const pathHot=tube(parts,[[.64,2.62,-.2],[.64,2.85,.15],[.24,2.86,.63],[.02,2.55,1.0]],.043,copper);
for(const path of [pathCold,pathPump,pathHot])for(const q of [0,1]){const p=path.curve.getPoint(q);const n=mesh(parts,new T.IcosahedronGeometry(.07,0),brass);n.position.copy(p);}
const flowDots=[];for(const [k,path]of [pathCold,pathPump,pathHot].entries())for(let i=0;i<12;i++){const m=new T.MeshBasicMaterial({color:k===2?'#ffbd65':'#6bdaed'});const o=mesh(parts,new T.SphereGeometry(.028,10,8),m);o.castShadow=false;flowDots.push({o,curve:path.curve,i,k});}

// Isolated inspection rigs preserve the same component geometry as the machine.
const boilerRig=grp(scene);const b=makeBoiler(boilerRig);b.root.position.y=1.75;
const pumpRig=grp(scene);const p=makePump(pumpRig);p.root.position.y=1.65;
const brewRig=grp(scene);const g=makeBrew(brewRig);g.root.position.y=2.15;
const cupRig=grp(scene);const c=makeCup(cupRig);c.root.position.y=.2;
const cupBrew=makeBrew(cupRig);cupBrew.root.position.set(-.15,1.88,-.115);cupBrew.root.scale.setScalar(1);const portSupport=box(cupRig,1.45,.22,.4,-.15,2.55,-.42,black);box(cupRig,.22,.92,.26,-.68,2.94,-.42,steel);
const waterRoute=grp(scene);const route=tube(waterRoute,[[-1.4,1.2,0],[-1.1,1.35,.1],[-.5,2.1,.4],[.7,2.1,.1],[1.2,1.65,0],[1.2,1.1,0]],.082,physical('#667d80',.75,.23));
const routeSleeve=mesh(waterRoute,new T.TubeGeometry(route.curve,120,.095,12,false),glass);routeSleeve.castShadow=false;
const tracer=[];for(let i=0;i<20;i++){const o=mesh(waterRoute,new T.SphereGeometry(.029,16,10),physical('#e9a547',.0,.25,{emissive:'#c98025',emissiveIntensity:.35}));o.castShadow=false;tracer.push(o);}
// Contextual fittings anchor the pipe close-up to the boiler outlet and brew inlet.
for(const q of [0,1]){const a=grp(waterRoute);a.position.copy(route.curve.getPointAt(q));const f=cyl(a,.19,.25,0,0,0,brass,.19,6);f.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),route.curve.getTangentAt(q));ring(a,.14,.022,0,.14,0,steel);}

const CUT={hero:3,open:6,heat:10,pump:15,route:20,brew:23,cup:29,close:33};
const shots=[
 {start:0,end:3,rig:'cup',a:[1.95,3.1,3.65],z:[1.1,2.65,3.25],target:[0,.78,0],text:['AVANT LA PREMIÈRE GOUTTE','Toute une','mécanique.','De l’eau, de la chaleur et de la pression.'],nav:2},
 {start:3,end:6,rig:'product',a:[6.3,4.6,8.7],z:[4.4,3.5,8.7],target:[0,1.8,0],text:['UN OBJET DU QUOTIDIEN','L’espresso.','Vu de l’intérieur.','Ouvrons la machine.'],nav:-1},
 {start:6,end:10,rig:'product',a:[4.8,3.65,10.4],z:[5.6,4.5,11.3],target:[0,1.85,0],text:['SOUS LA CARROSSERIE','Chaque pièce','a son rôle.','Le circuit se révèle.'],nav:-1},
 {start:10,end:15,rig:'boiler',a:[3.2,3.3,5.8],z:[-1.4,2.9,5.8],target:[0,1.83,0],text:['01 / LA CHALEUR','L’eau','se prépare.','La résistance chauffe l’eau dans la chaudière.'],nav:0},
 {start:15,end:20,rig:'pump',a:[2.2,2.75,4.5],z:[.65,2.0,3.75],target:[0,1.65,0],text:['02 / LA PRESSION','La pompe','pousse.','Le piston met l’eau en mouvement dans le circuit.'],nav:1},
 {start:20,end:23,rig:'route',a:[2.2,3.8,5.9],z:[-.3,2.5,5.5],target:[.1,1.65,0],text:['DU CHAUD AU CAFÉ','Suivre','le trajet.','L’eau chaude rejoint le groupe d’extraction.'],nav:1},
 {start:23,end:29,rig:'brew',a:[2.8,4.7,6.8],z:[1.8,3.9,5.6],target:[.08,2.26,0],text:['03 / L’EXTRACTION','Au cœur','du café.','Sous pression, l’eau traverse le café moulu.'],nav:2},
 {start:29,end:33,rig:'cup',a:[1.1,3.1,3.65],z:[-1.1,2.65,3.6],target:[0,.78,0],text:['DE LA MACHINE À LA TASSE','La dernière','étape.','Le café s’écoule. La tasse se remplit.'],nav:2},
 {start:33,end:36,rig:'product',a:[5.0,4.1,10.5],z:[3.4,3.55,8.7],target:[0,1.83,0],text:['LE QUOTIDIEN, DÉCOMPOSÉ','Un espresso.','Tout s’explique.','Chauffer. Pousser. Extraire.'],nav:-1}
];
const rigs={product,boiler:boilerRig,pump:pumpRig,brew:brewRig,cup:cupRig,route:waterRoute};
function pointLabel(i,text,world,dx,dy){const a=world.clone().project(camera),x=(a.x*.5+.5)*W,y=(-a.y*.5+.5)*H;const tag=byId('tag'+i),line=byId('line'+i);tag.textContent=text;tag.style.display='block';tag.style.left=`${x+dx}px`;tag.style.top=`${y+dy-18}px`;line.style.display='block';line.style.left=x+'px';line.style.top=y+'px';line.style.width=Math.hypot(dx,dy)+'px';line.style.transform=`rotate(${Math.atan2(dy,dx)}rad)`;}
function renderAt(t){
 t=clamp(t,0,D);const shot=shots.find(s=>t>=s.start&&t<s.end)||shots.at(-1);const q=clamp((t-shot.start)/(shot.end-shot.start),0,1),u=q*q*(3-2*q);
 for(const [name,rig] of Object.entries(rigs))rig.visible=name===shot.rig;
 floor.visible=['product','cup'].includes(shot.rig);camera.position.copy(v(shot.a).lerp(v(shot.z),u));const target=v(shot.target);camera.lookAt(target);camera.setViewOffset(W,H,-265,0,W,H);camera.updateMatrixWorld();dof.uniforms.focus.value=camera.position.distanceTo(target);dof.uniforms.aperture.value=shot.rig==='product'?.0007:.0017;
 let explosion=shot.start===CUT.open?ease(6.15,8.6,t):shot.start===CUT.close?1-ease(33,34.7,t):0;
 casing.visible=true;shellLeft.position.set(-1.47-explosion*1.75,1.85+explosion*.12,-.18);shellLeft.rotation.z=explosion*.08;shellRight.position.set(1.47+explosion*1.75,1.85+explosion*.12,-.18);shellRight.rotation.z=-explosion*.08;shellBack.position.z=-1.32-explosion*1.2;shellTop.position.y=3.37+explosion*1.2;shellFront.position.set(-explosion*.55,1.61, .7+explosion*2.6);shellFront.rotation.y=-explosion*.5;
 tank.position.x=-.86-explosion*.5;pb.root.position.x=.44+explosion*.42;pg.root.position.z=1+explosion*.3;parts.rotation.y=0;
 pb.animate(t,.85*explosion,1);pp.animate(t,explosion,.7);pg.animate(t,explosion*.2,0);pc.animate(t,t>=34?1:0,t>=33?.75:.2);needle.rotation.z=lerp(1.8,-1.0,ease(3,5,t));
 for(const a of flowDots){a.o.visible=explosion>.7;const phase=(t*.3+a.i/12)%1;a.o.position.copy(a.curve.getPointAt(phase));}
 b.animate(t,ease(10.1,11.4,t),ease(11.2,13.8,t));boilerRig.rotation.y=.02;
 p.animate(t,ease(15.05,16.1,t),1);pumpRig.rotation.y=-.09;
 for(let i=0;i<tracer.length;i++){const phase=(t*.4+i/tracer.length)%1;tracer[i].position.copy(route.curve.getPointAt(phase));}route.mesh.material.transparent=true;route.mesh.material.opacity=.23;
 const spread=ease(23,24.1,t)*(1-.52*ease(25.25,27,t));g.animate(t,spread,ease(26.6,27.1,t));brewRig.rotation.y=lerp(-.3,.22,u);
 c.animate(t,1,shot.start===0?lerp(.4,.75,q):lerp(.4,.97,q));cupRig.rotation.y=shot.start===0?-.22:0;cupBrew.animate(t,0,0);
 byId('eyebrow').textContent=shot.text[0];byId('title1').textContent=shot.text[1];byId('title2').textContent=shot.text[2];byId('sub').textContent=shot.text[3];
 const txt=ease(shot.start,shot.start+.38,t);byId('copy').style.opacity=String(.2+.8*txt);byId('copy').style.transform=`translateY(${(1-txt)*16}px)`;
 for(let i=0;i<3;i++){byId('nav'+i).classList.toggle('active',shot.nav===i);byId('tag'+i).style.display='none';byId('line'+i).style.display='none';}
 if(shot.start===CUT.open&&t>8.6){product.updateMatrixWorld(true);pointLabel(0,'RÉSERVOIR',tank.getWorldPosition(new T.Vector3()).add(new T.Vector3(0,1.3,0)),-95,-75);pointLabel(1,'CHAUDIÈRE',pb.root.getWorldPosition(new T.Vector3()).add(new T.Vector3(0,.5,0)),65,-45);}
 if(shot.rig==='brew'&&t>24&&t<26.4){brewRig.updateMatrixWorld(true);pointLabel(0,'CAFÉ MOULU',g.puck.getWorldPosition(new T.Vector3()),105,25);}
 byId('progress').style.transform=`scaleX(${t/D})`;composer.render(0);
}
window.gsap=gsap;const clock={t:0},tl=gsap.timeline({paused:true});tl.to(clock,{t:D,duration:D,ease:'none',onUpdate:()=>renderAt(clock.t)},0);window.__timelines=window.__timelines||{};window.__timelines.espresso=tl;window.espressoTimeline=tl;window.renderEspressoAt=renderAt;window.addEventListener('hf-seek',e=>renderAt(e.detail.time));renderAt(0);
