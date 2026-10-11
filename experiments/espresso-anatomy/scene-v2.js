import * as THREE from 'three';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {gsap} from 'gsap';
// Stable cutaway: motion explains changes in water and components.
const W=1920,H=1080,D=48;
const renderer=new THREE.WebGLRenderer({canvas:document.getElementById('scene'),antialias:true});
renderer.setSize(W,H,false);renderer.setPixelRatio(1);renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.94;
const scene=new THREE.Scene();scene.background=new THREE.Color('#eee9df');
const env=new THREE.PMREMGenerator(renderer);scene.environment=env.fromScene(new RoomEnvironment(),.035).texture;
const camera=new THREE.OrthographicCamera(-7.7,7.7,4.33125,-4.33125,.1,70);camera.position.set(0,6.26,22);camera.lookAt(0,2.21,0);camera.updateMatrixWorld();
scene.add(new THREE.HemisphereLight(0xfff9ef,0xb0b9b3,1.25));
const key=new THREE.DirectionalLight(0xfff4df,2.8);key.position.set(-5,10,9);key.castShadow=true;key.shadow.mapSize.set(2048,2048);Object.assign(key.shadow.camera,{left:-9,right:9,top:7,bottom:-6,near:1,far:35});key.shadow.normalBias=.025;scene.add(key);
const fill=new THREE.DirectionalLight(0xdcecff,2);fill.position.set(6,5,-4);scene.add(fill);
const mat=(c,m=0,r=.4)=>new THREE.MeshStandardMaterial({color:c,metalness:m,roughness:r});
const metal=mat('#a3b2ae',.82,.26),edge=mat('#d1d5ce',.65,.23),dark=mat('#343c38',.25,.36),copper=mat('#bd8155',.7,.28),white=mat('#eee8dc',.03,.28),blue=mat('#319fc7',.12,.3),brown=mat('#63361f',0,.6),crema=mat('#c4995c',0,.45);
const coilMat=mat('#a3673b',.63,.28);coilMat.emissive=new THREE.Color('#ff6512');
const coldColor=new THREE.Color('#319fc7'),hotColor=new THREE.Color('#ee913e');
const glass=new THREE.MeshPhysicalMaterial({color:'#badbdf',metalness:.03,roughness:.22,transparent:true,opacity:.13,depthWrite:false,side:THREE.DoubleSide});
function box(p,w,h,d,x,y,z,m,r=.06){const o=new THREE.Mesh(new RoundedBoxGeometry(w,h,d,3,r),m);o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;p.add(o);return o;}
function cyl(p,r,h,x,y,z,m,rt=r,open=false,start=0,length=Math.PI*2){const o=new THREE.Mesh(new THREE.CylinderGeometry(rt,r,h,64,1,open,start,length),m);o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;p.add(o);return o;}
function tube(p,pts,r,m){const curve=new THREE.CatmullRomCurve3(pts.map(a=>new THREE.Vector3(...a)),false,'centripetal');const mesh=new THREE.Mesh(new THREE.TubeGeometry(curve,100,r,12,false),m);p.add(mesh);mesh.castShadow=true;return {curve,mesh};}
function torus(p,r,w,x,y,z,m){const o=new THREE.Mesh(new THREE.TorusGeometry(r,w,12,64),m);o.position.set(x,y,z);o.rotation.x=Math.PI/2;p.add(o);return o;}
const ground=new THREE.Mesh(new THREE.PlaneGeometry(100,100),mat('#ddd9ce',0,.88));ground.rotation.x=-Math.PI/2;ground.position.y=-.18;ground.receiveShadow=true;scene.add(ground);

const tank=new THREE.Group();tank.position.set(-5.2,0,0);scene.add(tank);
box(tank,1.75,.12,1.25,0,.42,0,edge);box(tank,1.75,.1,1.25,0,3.25,0,edge);
box(tank,1.65,2.65,.08,0,1.85,-.58,white);for(const x of [-.8,.8])box(tank,.075,2.67,1.15,x,1.85,0,edge,.025);
const tankWater=box(tank,1.52,2.14,1.02,0,1.55,0,blue,.025);box(tank,1.52,2.57,.018,0,1.83,.54,glass,.006);
for(let i=0;i<6;i++)box(tank,.17,.018,.018,.6,.78+i*.37,.563,white,.003);
box(tank,.78,.13,.18,0,3.38,0,dark,.04);

// Exposed pump, with a deliberately slowed piston and two one-way valves.
const pump=new THREE.Group();pump.position.set(-2.15,0,0);scene.add(pump);
box(pump,2.02,.16,1.05,0,.65,0,metal);box(pump,1.9,1.12,.14,0,1.43,-.46,copper);
box(pump,1.95,.14,.9,0,1.98,0,copper);box(pump,1.95,.14,.9,0,.93,0,copper);
box(pump,.15,1.05,.9,.88,1.45,0,metal);box(pump,.13,1.05,.9,-.9,1.45,0,metal);
const chamber=box(pump,1.56,.88,.55,0,1.45,-.08,blue,.025);
const piston=new THREE.Group();pump.add(piston);box(piston,.15,.88,.7,-.55,1.45,.04,edge,.024);box(piston,.74,.14,.18,-.99,1.45,.12,dark,.025);
const springPts=[];for(let i=0;i<=160;i++){const q=i/160;springPts.push([.195*q,.16*Math.sin(q*Math.PI*10),.16*Math.cos(q*Math.PI*10)]);}const spring=tube(pump,springPts,.025,metal);spring.mesh.position.set(-.82,1.45,.3);
const inletValve=box(pump,.12,.29,.64,-.69,1.01,.11,white,.02),outletValve=box(pump,.12,.29,.64,.65,1.85,.11,white,.02);
box(pump,1.55,.88,.016,0,1.45,.46,glass,.002);

// Rear boiler shell and water cross section; front removed to expose the heater.
const boiler=new THREE.Group();boiler.position.set(1.16,0,0);scene.add(boiler);
cyl(boiler,.94,2.4,0,1.98,0,copper,.94,true,Math.PI/2,Math.PI);
cyl(boiler,.94,.14,0,.77,0,metal);cyl(boiler,.94,.14,0,3.2,0,copper);
const boilerWater=box(boiler,1.73,2.23,.72,0,1.98,-.1,blue.clone(),.04);
for(const x of [-.9,.9])box(boiler,.065,2.38,.055,x,1.98,.04,edge,.012);
torus(boiler,.94,.055,0,3.25,0,edge);torus(boiler,.94,.055,0,.69,0,edge);
box(boiler,.7,.16,.55,0,.55,0,dark);
const coilPts=[[-.59,.73,.43],[-.59,1.03,.43]];
for(let j=0;j<4;j++){const yy=1.05+j*.43;const direction=j%2===0?1:-1;for(let i=0;i<=12;i++){const q=i/12;coilPts.push([direction*(-.59+1.18*q),yy+.14*Math.sin(Math.PI*q),.43]);}if(j<3)coilPts.push([direction*.59,yy+.4,.43]);}
tube(boiler,coilPts,.059,coilMat);box(boiler,.25,.14,.26,-.59,.6,.43,dark,.03);
const heatArrows=[];for(let i=0;i<5;i++){const m=new THREE.MeshBasicMaterial({color:'#ffe1a2',transparent:true,opacity:0});const a=new THREE.Mesh(new THREE.ConeGeometry(.06,.18,3),m);boiler.add(a);heatArrows.push(a);}

// Brew group + basket in section, with a visible shower, grounds and outlet.
const brew=new THREE.Group();brew.position.set(4.72,0,0);scene.add(brew);
cyl(brew,.84,.38,0,2.94,0,metal);cyl(brew,.88,.1,0,2.7,0,edge);
box(brew,1.47,.14,.8,0,2.61,.06,edge,.025);
for(let i=0;i<9;i++)box(brew,.035,.035,.027,-.61+i*.152,2.55,.49,dark,.002);
cyl(brew,.65,.67,0,2.19,0,metal,.79,true,Math.PI/2,Math.PI);
box(brew,1.29,.1,.82,0,1.85,0,edge,.025);for(const x of [-.72,.72])box(brew,.085,.7,.08,x,2.19,.09,edge,.02);
const grounds=box(brew,1.32,.46,.82,0,2.13,.09,brown,.035);
for(let i=0;i<78;i++){const g=new THREE.Mesh(new THREE.IcosahedronGeometry(.03+(i%4)*.007,0),mat(i%2?'#71472f':'#94603e',0,.9));g.position.set(-.6+((i*31)%79)/79*1.2,1.94+((i*19)%73)/73*.38,.518);g.rotation.set(i*.7,i*.3,i*.1);brew.add(g);}
const wetMat=mat('#322219',0,.5);wetMat.transparent=true;wetMat.opacity=.56;wetMat.depthWrite=false;
const wetLayer=box(brew,1.32,.46,.025,0,2.13,.56,wetMat,.008);wetLayer.visible=false;
box(brew,.3,.18,.4,0,1.69,0,metal,.04);tube(brew,[[0,1.7,0],[0,1.54,.17],[.15,1.5,.3]],.11,metal);
const handle=cyl(brew,.13,1.1,1.23,2.31,-.02,dark,.17);handle.rotation.z=Math.PI/2;box(brew,.48,.16,.19,.69,2.31,-.02,metal);

const cup=new THREE.Group();cup.position.set(4.87,0,.3);scene.add(cup);
const cupGlaze=mat('#8fa29a',.12,.25);cupGlaze.side=THREE.DoubleSide;
cyl(cup,.95,.1,0,.015,0,cupGlaze);cyl(cup,.57,.12,0,.13,0,cupGlaze);
cyl(cup,.56,.77,0,.56,0,cupGlaze,.73,true,Math.PI/2,Math.PI);
for(const x of [-.65,.65])box(cup,.08,.73,.11,x,.56,.035,cupGlaze,.025);
const cupHandle=new THREE.Mesh(new THREE.TorusGeometry(.27,.085,16,48),cupGlaze);cupHandle.position.set(.82,.56,-.03);cup.add(cupHandle);
const coffeeBody=box(cup,1.11,.04,.62,0,.24,.06,brown,.02),coffeeTop=box(cup,1.12,.018,.64,0,.26,.06,crema,.015);coffeeBody.visible=false;coffeeTop.visible=false;
const stream=cyl(scene,.042,1,4.87,1.1,.3,mat('#794c24',.08,.25));stream.visible=false;

// Wide pipes remain visible; moving arrows encode the direction of water flow.
const pipeBase=new THREE.MeshStandardMaterial({color:'#7ba8b0',transparent:true,opacity:.22,roughness:.38,metalness:.1,depthWrite:false});
const hotBase=pipeBase.clone();hotBase.color.set('#d5a16b');
const cold1=tube(scene,[[-4.37,.88,.05],[-3.89,.88,.08],[-3.45,1.08,.08],[-3.12,1.08,.08]],.1,pipeBase);
const cold2=tube(scene,[[-1.21,1.8,.04],[-.85,1.8,.04],[-.38,1.13,.06],[.26,1.13,.06]],.1,pipeBase);
const hot=tube(scene,[[2.05,2.96,.03],[2.5,2.96,.03],[2.87,3.42,.03],[3.8,3.42,.03],[4.72,3.42,.03],[4.72,3.14,.03]],.11,hotBase);
const flows=[];function addFlow(path,color,n,start){const group=new THREE.Group();scene.add(group);const arrows=[];const material=new THREE.MeshBasicMaterial({color});for(let i=0;i<n;i++){const a=new THREE.Mesh(new THREE.ConeGeometry(.083,.22,4),material);group.add(a);arrows.push(a);}flows.push({curve:path.curve,group,arrows,start});}
addFlow(cold1,'#268bb5',5,17);addFlow(cold2,'#268bb5',6,18);addFlow(hot,'#e8832e',11,28);
const shower=[];for(let i=0;i<7;i++){const p=new THREE.Mesh(new THREE.SphereGeometry(.043,12,8),new THREE.MeshBasicMaterial({color:'#ef9d4c'}));brew.add(p);shower.push(p);}
const extractDots=[];for(let i=0;i<11;i++){const p=new THREE.Mesh(new THREE.SphereGeometry(.031,10,8),new THREE.MeshBasicMaterial({color:'#d4a165'}));brew.add(p);extractDots.push(p);}

const el=id=>document.getElementById(id),labels=['tankLabel','pumpLabel','boilerLabel','filterLabel'];
for(let i=0;i<4;i++){const pos=new THREE.Vector3([-5.2,-2.15,1.16,4.72][i],0,0).project(camera);el(labels[i]).style.left=`${(pos.x*.5+.5)*W}px`;}
function locate(id,x,y,z,dx=0,dy=0){const p=new THREE.Vector3(x,y,z).project(camera);el(id).style.left=`${(p.x*.5+.5)*W+dx}px`;el(id).style.top=`${(-p.y*.5+.5)*H+dy}px`;}
locate('coilTag',1.16,.57,.6,0,30);locate('pistonTag',-2.55,.6,.6,0,32);locate('groundsTag',4.72,2.15,.65,0,-72);
const smooth=(a,b,t)=>{const v=THREE.MathUtils.clamp((t-a)/(b-a),0,1);return v*v*(3-2*v);};const yAxis=new THREE.Vector3(0,1,0);
const stages=[
 {at:0,no:'→',title:'Comment l’eau devient un espresso.',verb:'Un seul trajet : du réservoir jusqu’à la tasse.',detail:'Quatre éléments, chacun avec un rôle précis.',active:[0,1,2,3]},
 {at:6,no:'01',title:'D’abord, chauffer l’eau.',verb:'La résistance chauffe l’eau contenue dans la chaudière.',detail:'L’orange indique l’eau chaude. La chauffe est accélérée ici.',active:[2]},
 {at:16,no:'02',title:'Puis, la mettre en mouvement.',verb:'La pompe aspire l’eau du réservoir, puis la pousse.',detail:'Le piston avance et recule : il met le circuit sous pression.',active:[0,1]},
 {at:27,no:'03',title:'L’eau chaude rencontre le café.',verb:'Sous pression, l’eau traverse le lit de café moulu.',detail:'Elle en extrait des substances qui donnent goût et couleur.',active:[2,3]},
 {at:38,no:'04',title:'L’extraction arrive dans la tasse.',verb:'Le liquide devenu café s’écoule sous le porte-filtre.',detail:'Le café moulu reste dans le panier : seule la boisson sort.',active:[3]},
 {at:44,no:'↳',title:'Chauffer. Pousser. Extraire.',verb:'La chaleur et la pression permettent l’extraction.',detail:'Réservoir → pompe → chaudière → café moulu → tasse.',active:[0,1,2,3]}
];
function renderAt(t){
 t=THREE.MathUtils.clamp(t,0,D);const heat=smooth(7,14,t),running=smooth(16.5,17.2,t)*(1-smooth(43,44,t));
 boilerWater.material.color.copy(coldColor).lerp(hotColor,heat);coilMat.emissiveIntensity=.7*heat;
 for(let i=0;i<heatArrows.length;i++){const q=((t*.32+i/5)%1);heatArrows[i].position.set(-.58+i*.29,1.15+q*1.55,.58);heatArrows[i].material.opacity=(t>=7&&t<16)?.58*Math.sin(q*Math.PI):0;}
 const motion=Math.sin((t-16.5)*Math.PI*1.2),velocity=Math.cos((t-16.5)*Math.PI*1.2);const stroke=.43*(motion+1)/2*running;piston.position.x=stroke;chamber.scale.x=(1.255-stroke)/1.56;chamber.position.x=(.305+stroke)/2;spring.mesh.scale.x=1+stroke/.195;
 inletValve.rotation.z=running*(velocity<0?-.5:0);outletValve.rotation.z=running*(velocity>=0?.5:0);el('pistonTag').textContent=velocity>=0?'Piston → pousse':'Piston ← aspire';
 const empty=smooth(17,43,t);tankWater.scale.y=1-.19*empty;tankWater.position.y=.48+2.14*tankWater.scale.y/2;
 for(const flow of flows){flow.group.visible=t>=flow.start&&t<44;for(let i=0;i<flow.arrows.length;i++){const q=(((t-flow.start)*.37+i/flow.arrows.length)%1+1)%1;const a=flow.arrows[i];a.position.copy(flow.curve.getPointAt(q));a.quaternion.setFromUnitVectors(yAxis,flow.curve.getTangentAt(q).normalize());}}
 const wet=smooth(30,33,t);wetLayer.visible=wet>.001;wetLayer.scale.y=wet;wetLayer.position.y=2.36-.46*wet/2;
 for(let i=0;i<shower.length;i++){const q=((t*1.2+i/7)%1);shower[i].visible=t>=29&&t<44;shower[i].position.set(-.54+i*.18,2.55-q*.23,.59);}
 for(let i=0;i<extractDots.length;i++){const q=((t*.45+i/11)%1);extractDots[i].visible=t>=31&&t<44;extractDots[i].position.set(-.56+i*.11,2.34-q*.45,.6);}
 const level=.04+.46*smooth(33,44,t);coffeeBody.visible=t>=33;coffeeTop.visible=t>=33;coffeeBody.scale.y=level/.04;coffeeBody.position.y=.21+level/2;coffeeTop.position.y=.21+level+.012;
 const pouring=smooth(32.7,33.1,t)*(1-smooth(43.7,44,t));stream.visible=pouring>.001;stream.scale.set(pouring,1.5-(.21+level),pouring*(1+.08*Math.sin(t*30)));stream.position.y=(1.5+.21+level)/2;
 let stage=stages[0];for(const s of stages)if(t>=s.at)stage=s;
 el('headline').textContent=stage.title;el('number').textContent=stage.no;el('verb').textContent=stage.verb;el('detail').textContent=stage.detail;
 for(let i=0;i<labels.length;i++)el(labels[i]).classList.toggle('active',stage.active.includes(i));
 el('coilTag').style.opacity=t>=6&&t<16?'1':'0';el('pistonTag').style.opacity=t>=16&&t<27?'1':'0';el('groundsTag').style.opacity=t>=27&&t<32?'1':'0';
 const entrance=smooth(stage.at,stage.at+.5,t);el('headline').style.opacity=String(.25+.75*entrance);el('headline').style.transform=`translateY(${(1-entrance)*9}px)`;
 el('clock').textContent=`${String(Math.floor(t)).padStart(2,'0')} / 48 s`;el('progress').style.transform=`scaleX(${t/D})`;renderer.render(scene,camera);
}
window.gsap=gsap;const time={t:0},tl=gsap.timeline({paused:true});tl.to(time,{t:D,duration:D,ease:'none',onUpdate:()=>renderAt(time.t)},0);window.__timelines=window.__timelines||{};window.__timelines.espresso=tl;window.espressoTimeline=tl;window.addEventListener('hf-seek',e=>renderAt(e.detail.time));window.renderEspressoAt=renderAt;renderAt(0);
