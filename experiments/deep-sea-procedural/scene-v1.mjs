import * as THREE from 'three';

const WIDTH = 1920, HEIGHT = 1080, DURATION = 30;
const film = document.getElementById('film');
const ctx = film.getContext('2d', { alpha: false });
const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, preserveDrawingBuffer: true });
renderer.setSize(WIDTH, HEIGHT, false);
renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.18;

const scene = new THREE.Scene();
scene.background = new THREE.Color('#061d25');
scene.fog = new THREE.FogExp2('#082c33', 0.029);
const camera = new THREE.PerspectiveCamera(46, WIDTH / HEIGHT, 0.1, 170);
scene.add(new THREE.HemisphereLight('#759d9d', '#151d22', 1.8));
const moonlight = new THREE.DirectionalLight('#70b2bb', 2.0);
moonlight.position.set(-14, 28, 8); scene.add(moonlight);
const warm = new THREE.PointLight('#c1dacf', 80, 38, 2);
warm.position.set(-8, 1.5, 10); scene.add(warm);

function random(seed) {
  let state = seed >>> 0;
  return () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296; };
}
const rng = random(4271);
const clamp = (x, a=0, b=1) => Math.max(a, Math.min(b, x));
const smooth = (a, b, x) => { const t = clamp((x-a)/(b-a)); return t*t*(3-2*t); };

function material(color, options = {}) {
  const {metalness,roughness,...lambertOptions}=options;
  return new THREE.MeshLambertMaterial({ color, flatShading: true, ...lambertOptions });
}
const stoneMaterials = ['#344449', '#465355', '#29393c', '#52595a', '#424649'].map(c => material(c));
const floorMaterial = material('#34464a', { vertexColors: true });

// An original irregular grid: geometry, face colors, and lighting are calculated.
const vertices = [], colors = [];
const cols = 24, rows = 31;
const terrain = [];
for (let z = 0; z <= rows; z++) {
  terrain[z] = [];
  for (let x = 0; x <= cols; x++) {
    const wx = (x-cols/2)*4.4, wz = 24-z*4.2;
    const y = -9 + Math.sin(wx*.13 + wz*.046)*1.7 + Math.cos(wz*.14)*.7 + (rng()-.5)*1.1;
    terrain[z][x] = [wx + (rng()-.5)*1.4, y, wz + (rng()-.5)*1.2];
  }
}
function triangle(a,b,c) {
  vertices.push(...a,...b,...c);
  const color = new THREE.Color().setHSL(.50+rng()*.025,.09+rng()*.10,.17+rng()*.065);
  for(let i=0;i<3;i++) colors.push(color.r,color.g,color.b);
}
for(let z=0;z<rows;z++)for(let x=0;x<cols;x++){
  const a=terrain[z][x], b=terrain[z+1][x], c=terrain[z][x+1], d=terrain[z+1][x+1];
  triangle(a,c,b);triangle(b,c,d);
}
const terrainGeometry = new THREE.BufferGeometry();
terrainGeometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
terrainGeometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
terrainGeometry.computeVertexNormals();
scene.add(new THREE.Mesh(terrainGeometry,floorMaterial));

const rockGeometry = new THREE.IcosahedronGeometry(1, 0);
const rockTransforms=Array.from({length:5},()=>[]);
for(let i=0;i<56;i++) {
  const rock = new THREE.Object3D();
  const bank = i%2 ? 1 : -1;
  const z=15-rng()*103;
  const size=2.6+rng()*6;
  rock.position.set(bank*(13+rng()*12),-8+size*.28,z);
  rock.scale.set(size*(.8+rng()*.6),size*(.8+rng()*1.65),size*(.7+rng()*.6));
  rock.rotation.set(rng()*.8,rng()*6,rng()*.4);
  rock.updateMatrix();rockTransforms[i%5].push(rock.matrix.clone());
}
for(let i=0;i<28;i++) {
  const rock = new THREE.Object3D();
  rock.position.set((rng()-.5)*23,-8.5+rng()*.8,15-rng()*70);
  rock.scale.set(1+rng()*2,.5+rng()*1.2,.8+rng()*2);
  rock.rotation.y=rng()*6;rock.updateMatrix();rockTransforms[i%5].push(rock.matrix.clone());
}
for(let i=0;i<5;i++){
  const mesh=new THREE.InstancedMesh(rockGeometry,stoneMaterials[i],rockTransforms[i].length);
  rockTransforms[i].forEach((matrix,index)=>mesh.setMatrixAt(index,matrix));
  mesh.computeBoundingSphere();scene.add(mesh);
}

// Sparse, individually lit particles, never a simulated recording from a dive.
const particlePositions = new Float32Array(420*3);
const particleOrigins=[];
for(let i=0;i<420;i++) {
  const p=[(rng()-.5)*65,-7+rng()*24,22-rng()*95];
  particleOrigins.push(p);particlePositions.set(p,i*3);
}
const particleGeometry = new THREE.BufferGeometry();
particleGeometry.setAttribute('position',new THREE.BufferAttribute(particlePositions,3));
const particles = new THREE.Points(particleGeometry,new THREE.PointsMaterial({color:'#b5ccbc',size:.065,transparent:true,opacity:.44,depthWrite:false}));
scene.add(particles);

// Bespoke unmanned observation vehicle: no game model, logo, or external texture.
const rov = new THREE.Group();
function box(size,pos,color) {
  const mesh=new THREE.Mesh(new THREE.BoxGeometry(...size),material(color));
  mesh.position.set(...pos);rov.add(mesh);return mesh;
}
box([2.8,.85,1.8],[0,.85,0],'#b1a171');
box([2.35,1.20,2.3],[0,-.05,0],'#3e5656');
box([1.75,.90,1.2],[0,-.13,.78],'#52676a');
for(const x of [-1.65,1.65]){
  box([.13,1.75,.13],[x,-.35,.90],'#253438');
  box([.13,1.75,.13],[x,-.35,-.95],'#253438');
  box([.14,.14,2.20],[x,-1.15,0],'#253438');
  box([.75,.75,.7],[x,.1,-.25],'#273e40');
  const propeller=new THREE.Mesh(new THREE.CylinderGeometry(.32,.32,.10,10),material('#18292d'));
  propeller.rotation.x=Math.PI/2;propeller.position.set(x,.1,.13);rov.add(propeller);
}
const port = new THREE.Mesh(new THREE.CylinderGeometry(.28,.28,.18,12),material('#0d2029',{metalness:.35}));
port.rotation.x=Math.PI/2;port.position.set(0,-.12,1.47);rov.add(port);
for(const x of [-.78,.78]){
  const lamp = new THREE.Mesh(new THREE.CylinderGeometry(.19,.19,.15,8),material('#f0e3bc',{emissive:'#dddbbb',emissiveIntensity:2}));
  lamp.rotation.x=Math.PI/2;lamp.position.set(x,.13,1.37);rov.add(lamp);
}
const statusLamp = new THREE.Mesh(new THREE.SphereGeometry(.055,6,4),material('#ba744e',{emissive:'#ba744e',emissiveIntensity:1}));
statusLamp.position.set(1.18,.65,1.01);rov.add(statusLamp);
rov.position.set(-7,-1.6,8);rov.rotation.y=.84;scene.add(rov);

// Two transparent light cones are atmospheric illustrations, not ray tracing.
for(const x of [-.78,.78]) {
  const cone = new THREE.Mesh(new THREE.ConeGeometry(4.1,20,24,1,true),new THREE.MeshBasicMaterial({color:'#a9c9b6',transparent:true,opacity:.055,depthWrite:false,side:THREE.DoubleSide,blending:THREE.AdditiveBlending}));
  cone.rotation.x=-Math.PI/2;cone.position.set(x,.13,11.45);rov.add(cone);
}
const spot = new THREE.SpotLight('#c4e6d3',280,65,.29,.65,1.8);
spot.position.set(0,.15,1.35);spot.target.position.set(0,-4,28);rov.add(spot,spot.target);

function textureNoise() {
  const c=document.createElement('canvas');c.width=256;c.height=256;
  const g=c.getContext('2d'), data=g.createImageData(256,256), r=random(1082);
  for(let i=0;i<data.data.length;i+=4){const v=r()*255;data.data[i]=v;data.data[i+1]=v;data.data[i+2]=v;data.data[i+3]=16;}
  g.putImageData(data,0,0);return c;
}
const grain=textureNoise();
const motes = Array.from({length:75},()=>({x:rng()*WIDTH,y:rng()*HEIGHT,r:.5+rng()*1.8,s:.6+rng()*1.2}));

function vignette() {
  const glow=ctx.createRadialGradient(1040,490,150,960,540,1140);
  glow.addColorStop(0,'rgba(0,0,0,0)');glow.addColorStop(.57,'rgba(0,8,15,.03)');glow.addColorStop(1,'rgba(0,4,11,.86)');
  ctx.fillStyle=glow;ctx.fillRect(0,0,WIDTH,HEIGHT);
}
function typeLabel(x,y,headline,detail,alpha=1){
  ctx.save();ctx.globalAlpha=alpha;ctx.textAlign='left';
  ctx.fillStyle='#b7c4b6';ctx.font='18px Arial';ctx.letterSpacing='4px';ctx.fillText(headline,x,y);
  ctx.letterSpacing='0px';ctx.font='28px Arial';ctx.fillStyle='#e7e9d8';ctx.fillText(detail,x,y+39);
  ctx.fillStyle='#92a79d';ctx.fillRect(x,y+62,58,2);ctx.restore();
}

function render(t) {
  if(!Number.isFinite(t))throw new Error('A finite time in seconds is required.');
  t=clamp(t,0,DURATION);
  camera.position.set(.7*Math.sin(t*.095),4.7-.012*t,24.5-.027*t);
  camera.lookAt(.3*Math.sin(t*.055),-1.8,-16);
  rov.position.set(-7+.08*Math.sin(t*.33),-1.6+.21*Math.sin(t*.62),8+.22*Math.sin(t*.16));
  rov.rotation.y=.84+.055*Math.sin(t*.23);rov.rotation.z=.022*Math.sin(t*.51);
  const arr=particleGeometry.attributes.position.array;
  for(let i=0;i<particleOrigins.length;i++){
    const p=particleOrigins[i];arr[i*3]=p[0]+.28*Math.sin(t*.25+i);arr[i*3+1]=p[1]+.14*Math.sin(t*.4+i*.3);arr[i*3+2]=p[2]+((t*.15+i*.13)%1.5);
  }
  particleGeometry.attributes.position.needsUpdate=true;
  renderer.render(scene,camera);
  ctx.clearRect(0,0,WIDTH,HEIGHT);ctx.drawImage(renderer.domElement,0,0);
  const creatures=window.DeepSeaCreatures;
  if(!creatures)throw new Error('Procedural creature library has not loaded.');
  creatures.drawSchool(ctx,{x:1320-t*5,y:430,scale:.55,time:t,facing:-1,alpha:.13});
  const anglerAlpha=smooth(7,10,t)*(1-smooth(17,19,t));
  if(anglerAlpha>0)creatures.drawAngler(ctx,{x:1240-7*Math.max(0,t-7),y:585+9*Math.sin(t*.55),scale:1.75,time:t,facing:-1,alpha:anglerAlpha});
  const jellyAlpha=smooth(18,21,t)*(1-smooth(27.4,29.8,t));
  if(jellyAlpha>0){ctx.save();creatures.drawJelly(ctx,{x:1190+12*Math.sin(t*.12),y:390-2*(t-18),scale:1.10,time:t,alpha:jellyAlpha});ctx.restore();}
  ctx.save();ctx.globalCompositeOperation='screen';
  for(const p of motes){const x=(p.x+t*p.s*2)%WIDTH,y=p.y+9*Math.sin(t*.23+p.x);ctx.fillStyle='rgba(192,214,198,.15)';ctx.beginPath();ctx.arc(x,y,p.r,0,Math.PI*2);ctx.fill();}ctx.restore();
  vignette();
  ctx.save();ctx.globalAlpha=.13;ctx.drawImage(grain,0,0,WIDTH,HEIGHT);ctx.restore();
  const openingAlpha=smooth(.35,1.6,t)*(1-smooth(6,7.5,t));
  if(openingAlpha>0){
    ctx.save();ctx.globalAlpha=openingAlpha;
    ctx.fillStyle='#afbdb0';ctx.font='19px Arial';ctx.letterSpacing='6px';ctx.fillText('AU-DELÀ DE LA LUMIÈRE',92,160);
    ctx.letterSpacing='1px';ctx.font='64px Georgia';ctx.fillStyle='#e8e6d3';ctx.fillText('Le monde sous le monde.',92,243);
    ctx.fillStyle='#90a59d';ctx.fillRect(94,280,72,2);ctx.restore();
  }
  if(anglerAlpha>0)typeLabel(94,175,'UNE LUMIÈRE DANS LE NOIR','Le leurre d’une baudroie profonde.',anglerAlpha);
  if(jellyAlpha>0)typeLabel(94,175,'UNE SILHOUETTE DANS L’OBSCURITÉ','La méduse fantôme géante.',jellyAlpha);
  ctx.save();ctx.fillStyle='rgba(170,194,184,.55)';ctx.font='14px Arial';ctx.letterSpacing='2px';ctx.fillText('ÉTUDE VISUELLE • RECONSTITUTION ILLUSTRÉE',92,1005);ctx.restore();
  const fade=1-smooth(0,.45,t);const endFade=smooth(29.3,30,t);
  if(fade||endFade){ctx.fillStyle=`rgba(4,12,15,${Math.max(fade,endFade)})`;ctx.fillRect(0,0,WIDTH,HEIGHT);}
  return {time:t,drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles};
}
window.DeepSeaFilm={render,duration:DURATION,width:WIDTH,height:HEIGHT,renderer:'Three.js procedural geometry + original Canvas creature shapes'};

let playing=true,playbackTime=0,last=performance.now();
const seek=document.getElementById('seek'),play=document.getElementById('play'),clock=document.getElementById('time');
play?.addEventListener('click',()=>{playing=!playing;play.textContent=playing?'Pause':'Lire';last=performance.now();});
seek?.addEventListener('input',()=>{playbackTime=Number(seek.value);render(playbackTime);});
function tick(now){
  const delta=Math.min(.08,(now-last)/1000);last=now;
  if(playing){playbackTime+=delta;if(playbackTime>DURATION)playbackTime=0;render(playbackTime);if(seek)seek.value=playbackTime;if(clock)clock.textContent=`0:${String(Math.floor(playbackTime)).padStart(2,'0')}`;}
  if(!window.__CAPTURE_MODE__)requestAnimationFrame(tick);
}
if(!window.__CAPTURE_MODE__)requestAnimationFrame(tick);else render(0);
