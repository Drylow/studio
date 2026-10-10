/**
 * Original, texture-free marine models. Coordinates use Y-up; fish face +X.
 * Every animation is a deterministic function of seconds, independent of FPS.
 */
export function createCreatures(THREE) {
  const TAU = Math.PI * 2;
  const material = () => new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: true });
  const skinMaterial = material();
  const glowMaterial = new THREE.MeshBasicMaterial({ color: '#c4e9be', toneMapped: false });
  const fragments = [];

  // Merge colored primitives so a detailed silhouette does not cost a draw per part.
  function coloredFragment(geometry, color, position = [0,0,0], scale = [1,1,1], rotation = [0,0,0]) {
    const g = geometry.index ? geometry.toNonIndexed() : geometry.clone();
    const matrix = new THREE.Matrix4().compose(
      new THREE.Vector3(...position),
      new THREE.Quaternion().setFromEuler(new THREE.Euler(...rotation)),
      new THREE.Vector3(...scale),
    );
    g.applyMatrix4(matrix);
    // Explicit independent face normals preserve the low-poly surface after merging.
    g.computeVertexNormals();
    const base = new THREE.Color(color);
    const colors = new Float32Array(g.attributes.position.count * 3);
    for (let i = 0; i < g.attributes.position.count; i++) {
      // Coherent per-face pigment variation creates original hand-painted facets.
      const value = 0.87 + 0.20 * (0.5 + 0.5 * Math.sin(Math.floor(i / 3) * 3.97));
      colors[i*3] = base.r * value; colors[i*3+1] = base.g * value; colors[i*3+2] = base.b * value;
    }
    g.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    fragments.push(g);
    geometry.dispose();
  }
  function flushMesh(parent) {
    const positions = [], normals = [], colors = [];
    for (const g of fragments) {
      if (!g.attributes.normal) g.computeVertexNormals();
      positions.push(...g.attributes.position.array);
      normals.push(...g.attributes.normal.array);
      colors.push(...g.attributes.color.array);
      g.dispose();
    }
    fragments.length = 0;
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    g.computeBoundingSphere();
    const mesh = new THREE.Mesh(g, skinMaterial);
    parent.add(mesh);
    return mesh;
  }
  function triangleGeometry(points, triangles) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(points.flat(), 3));
    g.setIndex(triangles.flat());
    g.computeVertexNormals();
    return g;
  }
  function finGeometry(length, height, thickness = 0.06) {
    // A narrow closed triangular volume, rather than a camera-facing billboard.
    return triangleGeometry([
      [0,0,-thickness],[-length,height,0],[-length*0.8,-height*0.18,0],
      [0,0,thickness],
    ], [[0,2,1],[3,1,2],[0,1,3],[0,3,2]]);
  }
  function loftGeometry(rings, segments = 10, closeBack = true, closeFront = false) {
    const points = [], faces = [];
    for (const [x,y,ry,rz] of rings) {
      for (let j = 0; j < segments; j++) {
        const a = j / segments * TAU;
        points.push([x, y + Math.cos(a)*ry, Math.sin(a)*rz]);
      }
    }
    for (let i = 0; i < rings.length - 1; i++) for (let j = 0; j < segments; j++) {
      const a = i*segments+j, b=i*segments+(j+1)%segments;
      const c=a+segments, d=b+segments;
      faces.push([a,b,c],[b,d,c]);
    }
    if (closeBack) {
      const id=points.length;points.push([rings[0][0],rings[0][1],0]);
      for(let j=0;j<segments;j++)faces.push([id,(j+1)%segments,j]);
    }
    if (closeFront) {
      const id=points.length,r=(rings.length-1)*segments;
      points.push([rings.at(-1)[0],rings.at(-1)[1],0]);
      for(let j=0;j<segments;j++)faces.push([id,r+j,r+(j+1)%segments]);
    }
    return triangleGeometry(points,faces);
  }

  const angler = new THREE.Group();
  angler.name = 'Original faceted deep-sea anglerfish (+X forward)';
  // Front ring remains open: the wide black cavity is inside a genuine 3D head.
  coloredFragment(loftGeometry([
    [-2.50,-.04,.21,.19],[-1.90,.01,.52,.42],[-1.05,.10,1.05,.78],
    [-.12,.14,1.42,1.06],[.82,.08,1.43,1.05],[1.68,-.02,1.12,.88],
  ],12), '#594355');
  coloredFragment(loftGeometry([[1.68,-.02,1.115,.875],[1.01,-.02,.53,.48],[.75,-.02,.01,.01]],12,false,true), '#122930');
  // Angular brow and lips give the broad mouth a readable profile.
  coloredFragment(new THREE.IcosahedronGeometry(1,0),'#76516a',[1.05,.94,0],[1.02,.34,.95]);
  coloredFragment(new THREE.IcosahedronGeometry(1,0),'#553c54',[.22,1.22,0],[.90,.26,.78]);
  for (const z of [-.88,.88]) {
    coloredFragment(new THREE.IcosahedronGeometry(1,0),'#b2b3a0',[.93,.70,z],[.34,.25,.12]);
    coloredFragment(new THREE.IcosahedronGeometry(1,0),'#0b1e24',[1.00,.72,z*1.09],[.15,.15,.10]);
  }
  // A continuous, bowed lure stalk made of a low-sided tube.
  const lureCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(.10,1.38,0),new THREE.Vector3(.38,2.18,0),
    new THREE.Vector3(1.25,2.72,0),new THREE.Vector3(2.25,2.59,0),
    new THREE.Vector3(2.58,2.07,0),
  ]);
  coloredFragment(new THREE.TubeGeometry(lureCurve,10,.041,5,false),'#655b70');
  // Dorsal fin and small gill plates stay fused into the single body draw.
  coloredFragment(finGeometry(1.8,.82,.055),'#48384f',[-.55,1.01,0],[1,1,1],[0,0,-.2]);
  for(const z of [-1,1]) {
    coloredFragment(new THREE.IcosahedronGeometry(1,0),'#513b50',[-.05,.05,z*.94],[.42,.52,.11]);
  }
  const anglerBody = flushMesh(angler);
  const lureTip = new THREE.Mesh(new THREE.IcosahedronGeometry(.13,1),glowMaterial);
  lureTip.position.copy(lureCurve.getPoint(1));angler.add(lureTip);

  const upperTeeth = new THREE.Group();
  for(let i=0;i<11;i++) {
    const a=(-1.11+i*.222), z=Math.sin(a)*.84, y=Math.cos(a)*1.00-.02;
    const length=.39+.19*(.5+.5*Math.cos(i*2.13));
    // Cone tip points down into the cavity; tails remain narrow and uneven.
    coloredFragment(new THREE.ConeGeometry(.053,length,4), '#d2ccb4', [1.70,y-length*.45,z],[1,1,1],[0,0,Math.PI]);
  }
  flushMesh(upperTeeth);angler.add(upperTeeth);

  const jaw = new THREE.Group();jaw.position.set(.91,-.93,0);angler.add(jaw);
  coloredFragment(new THREE.IcosahedronGeometry(1,0),'#674861',[.35,-.01,0],[.88,.20,.89]);
  for(let i=0;i<9;i++) {
    const z=(i-4)*.19,length=.29+.19*(.5+.5*Math.cos(i*1.83));
    coloredFragment(new THREE.ConeGeometry(.043,length,4),'#cbc6b0',[.81,.11+length*.5,z],[1,1,1]);
  }
  flushMesh(jaw);

  const tail = new THREE.Group();tail.position.set(-2.42,0,0);angler.add(tail);
  coloredFragment(loftGeometry([[0,0,.21,.18],[-.60,0,.13,.09]],6,true,true),'#513c51');
  coloredFragment(finGeometry(1.16,1.06,.045),'#665169',[-.51,0,0]);
  coloredFragment(finGeometry(1.16,-1.06,.045),'#514057',[-.51,0,0]);
  flushMesh(tail);
  const pectoralFins = [];
  for(const side of [-1,1]) {
    const fin=new THREE.Group();fin.position.set(-.47,-.25,side*.89);
    coloredFragment(finGeometry(1.25,.68,.04),'#715a6e',[0,0,0],[1,1,1],[side*Math.PI*.36,0,-.14]);
    flushMesh(fin);angler.add(fin);pectoralFins.push(fin);
  }

  const jelly = new THREE.Group();jelly.name = 'Original giant phantom jelly with four broad oral arms';
  const bell = new THREE.Group();jelly.add(bell);
  const bellPoints=[],bellFaces=[],bellSegments=16;
  const bellRings=[[1.36,.06],[1.23,.54],[.97,.95],[.60,1.22],[.13,1.31],[-.08,1.20],[-.13,.80]];
  for(let r=0;r<bellRings.length;r++)for(let i=0;i<bellSegments;i++) {
    const a=i/bellSegments*TAU,[y,radius]=bellRings[r];
    const edge=r===5||r===6?.04*Math.cos(i*Math.PI):0;
    bellPoints.push([Math.cos(a)*radius,y+edge,Math.sin(a)*radius]);
  }
  for(let r=0;r<bellRings.length-1;r++)for(let i=0;i<bellSegments;i++) {
    const a=r*bellSegments+i,b=r*bellSegments+(i+1)%bellSegments,c=a+bellSegments,d=b+bellSegments;
    bellFaces.push([a,b,c],[b,d,c]);
  }
  const topIndex=bellPoints.length;bellPoints.push([0,1.38,0]);
  for(let i=0;i<bellSegments;i++)bellFaces.push([topIndex,(i+1)%bellSegments,i]);
  coloredFragment(triangleGeometry(bellPoints,bellFaces),'#633748');
  coloredFragment(new THREE.IcosahedronGeometry(1,0),'#422738',[0,.15,0],[.65,.38,.65]);
  flushMesh(bell);

  const ribbonSections=21,ribbonPositions=[],ribbonColors=[],ribbonIndices=[];
  const ribbonColor=new THREE.Color('#673e53');
  for(let arm=0;arm<4;arm++) {
    const base=arm*(ribbonSections+1)*4;
    for(let row=0;row<=ribbonSections;row++)for(let corner=0;corner<4;corner++) {
      ribbonPositions.push(0,0,0);
      const shade=.91+.08*Math.sin(row*.43+arm)+((corner===0||corner===3)?.05:0);
      ribbonColors.push(ribbonColor.r*shade,ribbonColor.g*shade,ribbonColor.b*shade);
    }
    for(let row=0;row<ribbonSections;row++)for(let edge=0;edge<4;edge++) {
      const a=base+row*4+edge,b=base+row*4+(edge+1)%4,c=a+4,d=b+4;
      ribbonIndices.push(a,c,b,b,c,d);
    }
    ribbonIndices.push(base,base+1,base+2,base,base+2,base+3);
    const last=base+ribbonSections*4;
    ribbonIndices.push(last,last+2,last+1,last,last+3,last+2);
  }
  const ribbonGeometry=new THREE.BufferGeometry();
  ribbonGeometry.setAttribute('position',new THREE.Float32BufferAttribute(ribbonPositions,3));
  ribbonGeometry.setAttribute('color',new THREE.Float32BufferAttribute(ribbonColors,3));
  ribbonGeometry.setIndex(ribbonIndices);
  const ribbons=new THREE.Mesh(ribbonGeometry,skinMaterial);jelly.add(ribbons);
  function updateRibbons(time) {
    const arr=ribbonGeometry.attributes.position.array;
    for(let arm=0;arm<4;arm++) {
      const angle=arm*TAU/4+Math.PI*.25;
      const radialX=Math.cos(angle),radialZ=Math.sin(angle),tangentX=-radialZ,tangentZ=radialX;
      for(let row=0;row<=ribbonSections;row++) {
        const u=row/ribbonSections;
        const centerRadius=.40+u*.46+Math.sin(u*6.9-time*.65+arm*.64)*u*.23;
        const wander=Math.sin(u*5.9-time*.74+arm*1.17)*u*.31;
        const cx=radialX*centerRadius+tangentX*wander,cz=radialZ*centerRadius+tangentZ*wander;
        const cy=-.18-u*5.15+Math.sin(u*9-time*.65+arm)*u*.13;
        const width=(.31+.30*Math.sin(u*Math.PI*.85))*(1-Math.pow(u,6)*.87);
        const twist=Math.sin(u*5.1-time*.59+arm)*.53;
        const wx=tangentX*Math.cos(twist)+radialX*Math.sin(twist);
        const wz=tangentZ*Math.cos(twist)+radialZ*Math.sin(twist);
        const nx=-wz,nz=wx,thickness=.037*(1-u*.7);
        for(let corner=0;corner<4;corner++) {
          const left=corner<2?-1:1,depth=(corner===0||corner===3)?-1:1;
          const i=((arm*(ribbonSections+1)+row)*4+corner)*3;
          arr[i]=cx+wx*left*width+nx*depth*thickness;
          arr[i+1]=cy+Math.sin(u*11-time*.62+arm)*width*left*.19;
          arr[i+2]=cz+wz*left*width+nz*depth*thickness;
        }
      }
    }
    ribbonGeometry.attributes.position.needsUpdate=true;
    ribbonGeometry.computeVertexNormals();
    // Fixed conservative local bounds avoid per-frame bounds computation.
    if(!ribbonGeometry.boundingSphere)ribbonGeometry.boundingSphere=new THREE.Sphere(new THREE.Vector3(0,-2.7,0),3.7);
  }

  const fishSchool = new THREE.Group();fishSchool.name='Original geometric fish school (+X forward)';
  coloredFragment(loftGeometry([[-.66,0,.09,.055],[-.32,0,.19,.12],[.10,0,.26,.17],[.44,0,.18,.12],[.60,.01,.025,.025]],6,true,true),'#98b7ad');
  coloredFragment(finGeometry(.43,.31,.015),'#7caaa4',[-.61,0,0]);
  coloredFragment(finGeometry(.43,-.31,.015),'#7caaa4',[-.61,0,0]);
  coloredFragment(finGeometry(.30,.19,.012),'#abc1a9',[.10,.20,0]);
  for(const z of [-.125,.125])coloredFragment(new THREE.IcosahedronGeometry(.034,0),'#172e34',[.36,.074,z]);
  const fishTemplate = flushMesh(new THREE.Group());
  const fishCount=17;
  const schoolInstances=new THREE.InstancedMesh(fishTemplate.geometry,skinMaterial,fishCount);
  schoolInstances.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  fishSchool.add(schoolInstances);
  // Formation has actual depth and each fish has a unique trajectory.
  const fishDummy=new THREE.Object3D();
  function updateSchool(time) {
    for(let i=0;i<fishCount;i++) {
      const row=i%5,bank=Math.floor(i/5),phase=i*1.971;
      fishDummy.position.set((row-2)*1.35+Math.sin(time*.79+phase)*.30,
        (bank-1.5)*.65+Math.sin(time*.66+phase)*.15,
        (i%3-1)*1.20+Math.sin(time*.41+phase)*.22);
      const size=.65+.22*(.5+.5*Math.sin(phase));fishDummy.scale.set(size,size,size);
      fishDummy.rotation.set(.05*Math.sin(time+phase),.075*Math.cos(time*.64+phase),.06*Math.sin(time*.81+phase));
      fishDummy.updateMatrix();schoolInstances.setMatrixAt(i,fishDummy.matrix);
    }
    schoolInstances.instanceMatrix.needsUpdate=true;
    if(!schoolInstances.boundingSphere)schoolInstances.boundingSphere=new THREE.Sphere(new THREE.Vector3(),6.5);
  }

  function update(time) {
    if(!Number.isFinite(time))throw new Error('Creature animation time must be finite seconds.');
    jaw.rotation.z=-.055-.042*Math.sin(time*.73);
    tail.rotation.y=.19*Math.sin(time*1.71);
    tail.rotation.z=.035*Math.sin(time*.93);
    pectoralFins.forEach((fin,i)=>{fin.rotation.x=(i?1:-1)*.17*Math.sin(time*1.31+i);});
    bell.scale.set(1+.045*Math.sin(time*.91),1-.026*Math.sin(time*.91),1+.045*Math.sin(time*.91));
    updateRibbons(time);updateSchool(time);
  }
  update(0);
  // Hosts control all world transforms and visibility; update() never moves roots.
  return { angler, jelly, fishSchool, update };
}
