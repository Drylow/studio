import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

/** Original matte seafloor, basalt strata and cold-water benthic gardens. */
export function createSleepEnvironment(THREE,{ground,clearance,seed=451937,radius=26}={}){
  if(typeof ground!=='function')throw new Error('A finite seabed-height function is required.');
  if(!Number.isFinite(radius)||radius<15)throw new Error('The swimming-route radius must be at least 15.');
  const TAU=Math.PI*2,PERIOD=300;
  let state=seed>>>0;
  const random=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state/4294967296;};
  const sampleGround=(x,z)=>{const y=ground(x,z);if(!Number.isFinite(y))throw new Error('Non-finite seafloor height.');return y;};
  const group=new THREE.Group();group.name='Original basalt basin and cold-water benthic gardens';
  const matte=new THREE.MeshLambertMaterial({vertexColors:true,flatShading:true});
  const rockBoxes=[],buckets=new Map(),moving=[];
  const summary={seed,periodSeconds:PERIOD,radius,acceptedFeatures:0,rejectedByClearance:0,
    basaltColumns:0,mediumBoulders:0,rockShelves:0,pebbles:0,spongeTubes:0,seaFans:0,anemones:0,starfish:0,shells:0,
    sandRipplePatches:0,fineSeabedTriangles:0,sedimentFlecks:0,triangles:0,drawCalls:0,animatedVertices:0};
  const bandColors=['#454a4a','#4b5052','#535957','#484c58','#54534f'];

  function solidGeometry(points,faces,color,shadeFn=null){
    const positions=[],colors=[],base=new THREE.Color(color);
    for(let face=0;face<faces.length;face++){
      const ids=faces[face];const average=ids.reduce((sum,id)=>sum+points[id][1],0)/3;
      const shade=shadeFn?shadeFn(average,face):1;
      for(const id of ids){positions.push(...points[id]);colors.push(base.r*shade,base.g*shade,base.b*shade);}
    }
    const geometry=new THREE.BufferGeometry();
    geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
    geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
    geometry.computeVertexNormals();geometry.computeBoundingBox();return geometry;
  }
  function pigment(geometry,color,shade=1){
    const g=geometry.index?geometry.toNonIndexed():geometry.clone();geometry.dispose();
    g.deleteAttribute('uv');
    const values=new Float32Array(g.attributes.position.count*3),base=new THREE.Color(color);
    for(let i=0;i<values.length;i+=3){values[i]=base.r*shade;values[i+1]=base.g*shade;values[i+2]=base.b*shade;}
    g.setAttribute('color',new THREE.BufferAttribute(values,3));g.computeVertexNormals();g.computeBoundingBox();return g;
  }
  function geometryBounds(parts){const bounds=new THREE.Box3();for(const part of parts){part.computeBoundingBox();bounds.union(part.boundingBox);}return bounds;}
  function accept(parts,bucket,name,padding=0){
    const bounds=geometryBounds(parts).expandByScalar(padding);
    if(clearance?.intersects?.(bounds)){parts.forEach(g=>g.dispose());summary.rejectedByClearance++;return false;}
    rockBoxes.push(bounds.clone());summary.acceptedFeatures++;
    if(!buckets.has(bucket))buckets.set(bucket,[]);
    buckets.get(bucket).push(...parts);return true;
  }
  function segment(a,b,width,color,sides=5){
    const start=new THREE.Vector3(...a),end=new THREE.Vector3(...b),length=start.distanceTo(end);
    // Joined thin stems need their cylindrical walls; hidden joint caps add no detail.
    const g=pigment(new THREE.CylinderGeometry(width*.72,width,length,sides,1,true),color);
    const direction=end.clone().sub(start).normalize();
    g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),direction));
    g.translate((a[0]+b[0])*.5,(a[1]+b[1])*.5,(a[2]+b[2])*.5);g.computeBoundingBox();return g;
  }
  function column(x,z,width,height,length,color,phase,levels=8,sides=9){
    const y=sampleGround(x,z),points=[],faces=[];
    for(let level=0;level<=levels;level++){
      const u=Math.pow(level/levels,.94+.08*Math.sin(phase));
      const ledge=1+.12*Math.sin(level*2.1+phase)-.24*u;
      for(let side=0;side<sides;side++){
        const a=side/sides*TAU+phase;
        const fracture=Math.pow(Math.max(0,Math.cos(a*2+phase*.73)),14)*.19;
        const edge=1+.17*Math.sin(side*1.8+phase)+.065*Math.cos(level*.8+side)-fracture;
        const leanX=width*.24*Math.sin(phase+.7)*u*u,leanZ=length*.18*Math.cos(phase*.7)*u*u;
        const crest=(.14*Math.sin(side*2.1+phase)+.06*Math.cos(side*4.1-phase))*height*Math.pow(u,2.8);
        points.push([x+leanX+Math.cos(a)*width*ledge*edge,y+u*height+crest,
          z+leanZ+Math.sin(a)*length*ledge*edge]);
      }
    }
    for(let level=0;level<levels;level++)for(let side=0;side<sides;side++){
      const a=level*sides+side,b=level*sides+(side+1)%sides,c=a+sides,d=b+sides;
      faces.push([a,c,b],[b,c,d]);
    }
    const bottom=points.length;points.push([x,y,z]);
    const top=points.length;points.push([x+width*.24*Math.sin(phase+.7),y+height*(.95+.04*Math.sin(phase)),z+length*.18*Math.cos(phase*.7)]);
    for(let side=0;side<sides;side++){faces.push([bottom,side,(side+1)%sides]);const a=levels*sides+side,b=levels*sides+(side+1)%sides;faces.push([top,b,a]);}
    return solidGeometry(points,faces,color,(heightValue)=>.85+.105*Math.cos((heightValue-y)*1.6+phase)+.035*Math.sin((heightValue-y)*7));
  }
  function slab(x,z,width,height,length,color,angle){
    const g=pigment(new THREE.IcosahedronGeometry(1,1),color);
    const arr=g.attributes.position.array;
    for(let i=0;i<arr.length;i+=3){const sx=arr[i],sy=arr[i+1],sz=arr[i+2];const ridge=1+.11*Math.sin(sx*6+sz*4+sy*7)+.05*Math.cos(sz*9-sy*4);arr[i]=sx*ridge;arr[i+1]=sy*(1+.17*Math.cos(sx*5+sz*3));arr[i+2]=sz*ridge;}
    g.scale(width,height,length);g.rotateY(angle);g.translate(x,sampleGround(x,z)+height*.65,z);
    g.computeVertexNormals();g.computeBoundingBox();return g;
  }

  // Fine continuous relief under the swimming route; coarse rings only far away.
  // All vertices share the host's ground function, with no raised rectangular tiles.
  const radii=[0];
  for(let i=1;i<=8;i++)radii.push(i*2);
  for(let i=1;i<=32;i++)radii.push(16+i*.625);
  for(let i=1;i<=10;i++)radii.push(36+i*2.9);
  const sectorSteps=24;
  for(let sector=0;sector<8;sector++){
    const points=[],faces=[];
    for(let row=0;row<radii.length;row++)for(let col=0;col<=sectorSteps;col++){
      const a=(sector+col/sectorSteps)/8*TAU,x=Math.cos(a)*radii[row],z=Math.sin(a)*radii[row];
      points.push([x,sampleGround(x,z),z]);
    }
    for(let row=0;row<radii.length-1;row++)for(let col=0;col<sectorSteps;col++){
      const a=row*(sectorSteps+1)+col,b=a+1,c=a+sectorSteps+1,d=c+1;
      if(row>0)faces.push([a,b,c]);faces.push([b,d,c]);
    }
    const geometry=solidGeometry(points,faces,'#515952',(y)=>.91+.06*Math.sin(y*1.2));
    const floor=new THREE.Mesh(geometry,matte);floor.name='Quiet sediment relief';group.add(floor);
    summary.fineSeabedTriangles+=faces.length;
  }

  // A broken central ring, leaving a hollow basin instead of a solid mountain.
  for(let cluster=0;cluster<16;cluster++){
    const angle=cluster/16*TAU+.11*Math.sin(cluster*1.7),distance=10+random()*8;
    const x=Math.cos(angle)*distance,z=Math.sin(angle)*distance,parts=[];
    const height=3.5+random()*7.1,width=1.5+random()*1.8,length=1.7+random()*2.0;
    parts.push(column(x,z,width,height,length,bandColors[cluster%5],random()*TAU));
    parts.push(column(x+Math.cos(angle+.65)*2.2,z+Math.sin(angle+.65)*2.2,width*.56,height*.58,length*.58,bandColors[(cluster+2)%5],random()*TAU,6,8));
    const shelf=slab(x+Math.cos(angle)*width*.65,z+Math.sin(angle)*length*.65,width*1.13,.24+random()*.16,length*.84,'#424b4b',angle);
    shelf.translate(0,height*.38,0);parts.push(shelf);
    if(accept(parts,'central-basalt','Layered basalt cluster')){summary.basaltColumns+=2;summary.rockShelves++;}
  }
  // Distant enclosing cliffs are segmented to retain frustum culling.
  for(let cluster=0;cluster<28;cluster++){
    const angle=cluster/28*TAU,distance=Math.max(42,radius+18)+random()*11;
    const x=Math.cos(angle)*distance,z=Math.sin(angle)*distance,parts=[];
    parts.push(column(x,z,2.7+random()*2.1,9+random()*9,2.9+random()*2.4,bandColors[cluster%5],angle+random()*.9,6,9));
    parts.push(column(x+Math.cos(angle+1.4)*3.8,z+Math.sin(angle+1.4)*3.8,2.0+random(),4.5+random()*5,2.5,bandColors[(cluster+1)%5],angle,6,8));
    if(accept(parts,`outer-cliff-${Math.floor(cluster/7)}`,'Distant cliff cluster'))summary.basaltColumns+=2;
  }

  function tube(x,z,offsetX,offsetZ,height,width,color,lift=0){
    const y=sampleGround(x+offsetX,z+offsetZ)+.04+lift,points=[],faces=[],sides=8;
    const rings=[[0,width],[height*.50,width*.88],[height,width*.79],[height-.065,width*.45],[height-.20,width*.44]];
    for(const [h,r]of rings)for(let i=0;i<sides;i++){
      const a=i/sides*TAU;points.push([x+offsetX+Math.cos(a)*r+h*.13+.025*Math.sin(h*5+offsetX),y+h,z+offsetZ+Math.sin(a)*r+.035*Math.sin(h*4+offsetZ)]);
    }
    for(let row=0;row<rings.length-1;row++)for(let i=0;i<sides;i++){
      const a=row*sides+i,b=row*sides+(i+1)%sides,c=a+sides,d=b+sides;faces.push([a,c,b],[b,c,d]);
    }
    const center=points.length;points.push([x+offsetX+height*.08,y+height-.23,z+offsetZ]);
    for(let i=0;i<sides;i++)faces.push([center,4*sides+(i+1)%sides,4*sides+i]);
    return solidGeometry(points,faces,color,(heightValue)=>heightValue>y+height-.13?1.05:heightValue>y+height-.24?.44:.84+.08*Math.sin(heightValue*10));
  }
  function shell(x,z,size,angle){
    const points=[],faces=[],y=sampleGround(x,z)+.025,steps=7;
    points.push([x,y,z]);
    for(let i=0;i<=steps;i++){
      const a=angle+(-.70+i/steps*1.4);points.push([x+Math.cos(a)*size,y+.055+Math.sin(i/steps*Math.PI)*size*.19,z+Math.sin(a)*size]);
    }
    for(let i=0;i<steps;i++)faces.push([0,i+2,i+1]);
    const underside=points.length;points.push([x+Math.cos(angle)*size*.65,y-.025,z+Math.sin(angle)*size*.65]);
    for(let i=0;i<steps;i++)faces.push([underside,i+1,i+2]);
    return solidGeometry(points,faces,'#aaa493',(h,face)=>face%2?.78:.97);
  }
  function star(x,z,size,angle){
    const y=sampleGround(x,z)+.022,points=[[x,y+.085,z],[x,y-.012,z]],faces=[];
    for(let i=0;i<10;i++){
      const a=angle+i/10*TAU,r=i%2?size*.30:size;
      points.push([x+Math.cos(a)*r,y+.035,z+Math.sin(a)*r]);
    }
    for(let i=0;i<10;i++){const a=2+i,b=2+(i+1)%10;faces.push([0,b,a],[1,a,b]);}
    return solidGeometry(points,faces,'#9d8a6f',(h,face)=>face%2?.83:1);
  }
  function fan(x,z,height,angle,lift=0){
    const y=sampleGround(x,z)+.03+lift,parts=[],nodes=[];
    const toWorld=(u,v)=>[x+Math.cos(angle)*u+.035*Math.sin(v*5+angle),y+v,z+Math.sin(angle)*u+.065*Math.sin(v*3+angle)];
    const trunk=toWorld(.025,height*.23);
    parts.push(segment(toWorld(0,0),trunk,.033,'#989f8e'));
    for(let arm=0;arm<9;arm++){
      const a=-1.15+arm/8*2.30+.045*Math.sin(arm*2.1+angle);
      const asymmetry=1+.10*Math.sin(arm*1.6+angle),reach=Math.sin(a)*height*.71*asymmetry;
      const top=(.25+Math.cos(a)*.70)*height*asymmetry;
      const middle=toWorld(reach*.47,height*.23+(top-height*.23)*.48),end=toWorld(reach,top);
      parts.push(segment(trunk,middle,.016,'#a0a795'),segment(middle,end,.010,'#adb39f'));
      const branch=toWorld(reach+Math.cos(a)*height*.10,top+height*.12);
      const branch2=toWorld(reach-Math.cos(a)*height*.085,top+height*.10);
      parts.push(segment(end,branch,.007,'#babda9',4),segment(end,branch2,.006,'#aeb59e',4));
      nodes.push({middle,end});
    }
    for(let i=0;i<nodes.length-1;i++){
      if(i%3!==1)parts.push(segment(nodes[i].middle,nodes[i+1].middle,.006,'#969f8c',4));
      if(i%2===0)parts.push(segment(nodes[i].end,nodes[i+1].end,.005,'#afb69f',4));
    }
    const g=mergeGeometries(parts,false);parts.forEach(p=>p.dispose());return g;
  }
  function anemone(x,z,size,phase,lift=0){
    const y=sampleGround(x,z)+lift,parts=[];
    const foot=pigment(new THREE.CylinderGeometry(size*.20,size*.31,size*.37,7,1,false),'#736c62');foot.translate(x,y+size*.16,z);parts.push(foot);
    for(let arm=0;arm<9;arm++){
      const a=arm/9*TAU+phase,start=[x+Math.cos(a)*size*.13,y+size*.31,z+Math.sin(a)*size*.13];
      const middle=[x+Math.cos(a)*size*.26,y+size*.65,z+Math.sin(a)*size*.26];
      const end=[x+Math.cos(a)*size*.39,y+size*.69,z+Math.sin(a)*size*.39];
      parts.push(segment(start,middle,size*.018,'#c5c2af',4),segment(middle,end,size*.012,'#bdbfac',4));
    }
    return parts;
  }
  // Detail islands are deliberate compositions, never evenly scattered confetti.
  for(let patch=0;patch<28;patch++){
    const angle=patch/28*TAU+.08*Math.sin(patch*2.4)+(random()-.5)*.09;
    const distance=patch%3===0?radius+3.4+random()*3.1:radius-6+random()*3.0;
    const x=Math.cos(angle)*distance,z=Math.sin(angle)*distance,bucket=`garden-${Math.floor(patch/4)}`;
    const rockHeight=.45+random()*.58,width=1.25+random()*1.4,length=1.1+random()*1.4;
    const reef=[slab(x,z,width,rockHeight,length,patch%2?'#515951':'#555950',angle+random()*.8)];
    if(patch%3!==1)reef.push(slab(x+width*.9,z+length*.44,width*.54,rockHeight*.72,length*.63,'#444e4c',angle-.6));
    const tubeCount=3+patch%5;
    for(let tubeIndex=0;tubeIndex<tubeCount;tubeIndex++){
      const a=random()*TAU,d=.18+random()*.67;
      reef.push(tube(x,z,Math.cos(a)*d,Math.sin(a)*d,.39+random()*.95,.10+random()*.16,['#777961','#828568','#88877a'][tubeIndex%3],rockHeight*(1.3-.25*d)));
    }
    const reefAccepted=accept(reef,bucket,'Rock with clustered hollow sponges');
    if(reefAccepted){summary.spongeTubes+=tubeCount;summary.rockShelves++;}
    const fanX=x-Math.cos(angle)*(.5+random()*.9),fanZ=z-Math.sin(angle)*(.5+random()*.9);
    const fanHeight=.95+random()*1.35,fanLift=reefAccepted&&patch%2?rockHeight*.7:0;
    const fanGeometry=fan(fanX,fanZ,fanHeight,angle+.5+random(),fanLift);
    const fanBounds=geometryBounds([fanGeometry]).expandByScalar(.045);
    if(!clearance?.intersects?.(fanBounds)){
      const mesh=new THREE.Mesh(fanGeometry,matte);mesh.name='Delicate cold-water branching sea fan';group.add(mesh);
      rockBoxes.push(fanBounds);summary.acceptedFeatures++;summary.seaFans++;
      moving.push({mesh,base:Float32Array.from(fanGeometry.attributes.position.array),anchor:[fanX,sampleGround(fanX,fanZ)+fanLift,fanZ],phase:random()*TAU,cycle:3+patch%3,kind:'fan'});
    }else{fanGeometry.dispose();summary.rejectedByClearance++;}
    for(let polyp=0;polyp<1+patch%2;polyp++){
      const px=x+Math.cos(angle+.8+polyp)*1.9,pz=z+Math.sin(angle+.8+polyp)*1.9;
      const parts=anemone(px,pz,.54+random()*.53,random()*TAU);
      const bounds=geometryBounds(parts).expandByScalar(.025);
      if(!clearance?.intersects?.(bounds)){
        const geometry=mergeGeometries(parts,false);parts.forEach(g=>g.dispose());
        const mesh=new THREE.Mesh(geometry,matte);mesh.name='Small benthic anemone with articulated tentacles';group.add(mesh);
        rockBoxes.push(bounds);summary.acceptedFeatures++;summary.anemones++;
        moving.push({mesh,base:Float32Array.from(geometry.attributes.position.array),anchor:[px,sampleGround(px,pz),pz],phase:random()*TAU,cycle:5+polyp,kind:'polyp'});
      }else{parts.forEach(g=>g.dispose());summary.rejectedByClearance++;}
    }
    const shellX=x+Math.cos(angle+1.7)*2.3,shellZ=z+Math.sin(angle+1.7)*2.3;
    if(accept([shell(shellX,shellZ,.28+random()*.16,angle)],bucket,'Ridged bivalve shell'))summary.shells++;
    const starX=x+Math.cos(angle-.8)*2.5,starZ=z+Math.sin(angle-.8)*2.5;
    if(patch%2===0&&accept([star(starX,starZ,.35+random()*.18,angle)],bucket,'Five-armed benthic star'))summary.starfish++;
    const pebbles=[];
    for(let i=0;i<9;i++){
      const a=random()*TAU,d=1.4+random()*2.8,px=x+Math.cos(a)*d,pz=z+Math.sin(a)*d;
      const size=.07+random()*.21;
      const g=pigment(new THREE.IcosahedronGeometry(1,0),i%3?'#717468':'#8c8978');
      g.scale(size,.05+size*.35,size*.81);g.rotateY(a);g.translate(px,sampleGround(px,pz)+size*.13,pz);pebbles.push(g);
    }
    if(accept(pebbles,bucket,'Clustered near-bank rounded pebbles'))summary.pebbles+=pebbles.length;
    const sediment=[];
    for(let fleck=0;fleck<14;fleck++){
      const a=random()*TAU,d=.9+random()*2.7,px=x+Math.cos(a)*d,pz=z+Math.sin(a)*d,size=.025+random()*.025;
      const g=pigment(new THREE.TetrahedronGeometry(size,0),'#aaa794');g.scale(1,.20,1);g.rotateY(a);g.translate(px,sampleGround(px,pz)+.025,pz);sediment.push(g);
    }
    if(accept(sediment,bucket,'Small deposited pale sediment flecks'))summary.sedimentFlecks+=sediment.length;
  }
  // Lower inner shelves bring tangible foreground relief into the inward view.
  for(let i=0;i<16;i++){
    const a=i/16*TAU+.08+(random()-.5)*.16,d=radius-8.2+random()*2.8,x=Math.cos(a)*d,z=Math.sin(a)*d;
    const parts=[slab(x,z,1.5+random()*1.1,.40+random()*.45,1.6+random()*.9,'#4c5553',a+(random()-.5))];
    if(accept(parts,`inner-shelf-${Math.floor(i/4)}`,'Low inward basalt shelf'))summary.rockShelves++;
  }
  // Medium crags connect the low benthic banks with the large distant formations.
  // Shared input coordinates receive identical noise, keeping every face joined.
  for(let i=0;i<32;i++){
    const a=i/32*TAU+(random()-.5)*.13,d=20+random()*4,x=Math.cos(a)*d,z=Math.sin(a)*d;
    const width=1.0+random()*1.8,height=1.2+random(),length=.9+random()*1.45;
    const geometry=pigment(new THREE.IcosahedronGeometry(1,2),bandColors[(i+2)%5]);
    const positions=geometry.attributes.position.array;
    for(let p=0;p<positions.length;p+=3){
      const sx=positions[p],sy=positions[p+1],sz=positions[p+2];
      const ridge=1+.14*Math.sin(sx*5.1+sy*3.7+sz*4.8)+.075*Math.cos(sz*8.0-sy*3.1);
      positions[p]=sx*ridge+.065*sy*sy*Math.sin(i);
      positions[p+1]=sy*(1+.12*Math.sin(sx*4.0+sz*6.2));
      positions[p+2]=sz*ridge;
    }
    geometry.computeBoundingBox();
    const span=geometry.boundingBox.max.y-geometry.boundingBox.min.y;
    geometry.scale(width,height/span,length);geometry.rotateY(a+random()*TAU);geometry.computeBoundingBox();
    geometry.translate(x,sampleGround(x,z)-height*.08-geometry.boundingBox.min.y,z);
    const colors=geometry.attributes.color.array;
    for(let p=0;p<positions.length;p+=9){
      const shade=.94+.055*Math.sin(positions[p]*1.15+positions[p+1]*2.4+positions[p+2]*.57);
      for(let c=0;c<9;c++)colors[p+c]*=shade;
    }
    geometry.computeVertexNormals();geometry.computeBoundingBox();
    if(accept([geometry],`medium-crags-${Math.floor(i/4)}`,'Partly embedded intermediate-scale weathered boulder'))summary.mediumBoulders++;
  }
  for(const [name,parts]of buckets){
    const geometry=mergeGeometries(parts,false);parts.forEach(g=>g.dispose());geometry.computeBoundingSphere();
    const mesh=new THREE.Mesh(geometry,matte);mesh.name=name;group.add(mesh);
  }
  for(const item of moving){item.mesh.geometry.computeBoundingSphere();summary.animatedVertices+=item.base.length/3;}
  group.traverse(node=>{if(node.isMesh){summary.drawCalls++;summary.triangles+=(node.geometry.index?.count||node.geometry.attributes.position.count)/3;}});
  if(summary.triangles>80000)throw new Error(`Benthic environment exceeds the 80000-triangle budget: ${summary.triangles}.`);
  function update(t){
    if(!Number.isFinite(t))throw new Error('Environment animation needs finite seconds.');
    const wrapped=((t%PERIOD)+PERIOD)%PERIOD,phase=wrapped/PERIOD*TAU;
    for(const item of moving){
      const positions=item.mesh.geometry.attributes.position.array,base=item.base,[x,y,z]=item.anchor;
      for(let i=0;i<positions.length;i+=3){
        const height=Math.max(0,base[i+1]-y),influence=Math.min(1,height/(item.kind==='fan'?1.7:.75));
        const sway=(item.kind==='fan'?.027:.014)*influence*influence;
        positions[i]=base[i]+sway*Math.sin(phase*item.cycle+item.phase+height*.8);
        positions[i+1]=base[i+1];
        positions[i+2]=base[i+2]+sway*.63*Math.sin(phase*(item.cycle+1)+item.phase+height*1.1);
      }
      item.mesh.geometry.attributes.position.needsUpdate=true;item.mesh.geometry.computeVertexNormals();
    }
  }
  update(0);
  return {group,update,rockBoxes,summary};
}
