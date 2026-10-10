import {mergeGeometries,mergeVertices} from 'three/addons/utils/BufferGeometryUtils.js';

/** Original smooth, weathered underwater formations and small cold-water colonies. */
export function createCinematicEnvironment(THREE,{ground,clearance,seed=938517,radius=26}={}){
  const PERIOD=300,TAU=Math.PI*2;
  if(!Number.isFinite(radius)||radius<12)throw new Error('The expedition radius must be finite and at least 12.');
  let state=seed>>>0;
  const random=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state/4294967296;};
  const floorHeight=typeof ground==='function'?ground:()=>-7.5;
  const heightAt=(x,z)=>{const y=floorHeight(x,z);if(!Number.isFinite(y))throw new Error('Non-finite seafloor height.');return y;};
  const group=new THREE.Group();group.name='Smooth weathered cinematic underwater canyon';
  const material=new THREE.MeshLambertMaterial({vertexColors:true,flatShading:false});
  const buckets=new Map(),motionBuckets=new Map(),animations=[],rockBoxes=[];
  const summary={seed,radius,periodSeconds:PERIOD,smoothIndexedNormals:true,externalAssets:0,
    acceptedFeatures:0,rejectedByClearance:0,farFormations:0,mediumOutcrops:0,roundedPebbles:0,
    lobedSponges:0,anemones:0,branchingCorals:0,seaFans:0,featherStars:0,coralGardens:0,triangles:0,drawCalls:0,animatedVertices:0};
  const stoneColors=['#263e44','#30474b','#354a4b','#283b43','#3b4949'];

  function colored(geometry,color,shadeAt=null){
    geometry.deleteAttribute('uv');geometry.deleteAttribute('normal');
    // Weld primitive seams before computing normals, including sphere poles and tubes.
    const welded=mergeVertices(geometry,1e-5);geometry.dispose();geometry=welded;
    const positions=geometry.attributes.position,values=new Float32Array(positions.count*3),base=new THREE.Color(color);
    for(let i=0;i<positions.count;i++){
      const shade=shadeAt?shadeAt(positions.getX(i),positions.getY(i),positions.getZ(i)):1;
      values[i*3]=base.r*shade;values[i*3+1]=base.g*shade;values[i*3+2]=base.b*shade;
    }
    geometry.setAttribute('color',new THREE.BufferAttribute(values,3));
    geometry.computeVertexNormals();geometry.computeBoundingBox();return geometry;
  }
  function boundsOf(parts,padding=0){
    const box=new THREE.Box3();for(const geometry of parts){geometry.computeBoundingBox();box.union(geometry.boundingBox);}
    return box.expandByScalar(padding);
  }
  function reserve(parts,bucket,padding=0){
    const box=boundsOf(parts,padding);
    if(clearance?.intersects?.(box)){parts.forEach(g=>g.dispose());summary.rejectedByClearance++;return false;}
    rockBoxes.push(box.clone());summary.acceptedFeatures++;
    if(!buckets.has(bucket))buckets.set(bucket,[]);buckets.get(bucket).push(...parts);return true;
  }
  function moving(parts,sector,anchor,amplitude,cycle){
    const box=boundsOf(parts,amplitude*1.6);
    if(clearance?.intersects?.(box)){parts.forEach(g=>g.dispose());summary.rejectedByClearance++;return false;}
    const geometry=mergeGeometries(parts,false);parts.forEach(g=>g.dispose());
    const record={geometry,base:Float32Array.from(geometry.attributes.position.array),anchor,amplitude,cycle,phase:random()*TAU};
    if(!motionBuckets.has(sector))motionBuckets.set(sector,[]);motionBuckets.get(sector).push(record);
    rockBoxes.push(box.clone());summary.acceptedFeatures++;return true;
  }
  function roundedRock(x,z,width,height,length,phase,color,burial=.28,segments=24){
    let geometry=new THREE.SphereGeometry(1,segments,segments<16?8:segments<24?12:16);
    geometry.deleteAttribute('uv');geometry.deleteAttribute('normal');
    const positions=geometry.attributes.position.array;
    for(let i=0;i<positions.length;i+=3){
      const sx=positions[i],sy=positions[i+1],sz=positions[i+2];
      // Coherent displacement preserves neighbouring vertices and rounded volumes.
      const broad=.18*Math.sin(sx*3.4+sy*2.1+phase)*Math.cos(sz*2.8-phase*.5);
      const weather=.047*Math.sin(sx*8.2+sy*5.6+sz*7.3+phase)+.023*Math.cos(sz*13.0-sy*9.1+sx*4.2);
      const bedding=.05*Math.sin(sy*19+sx*2.7+phase)*(.35+.65*Math.sin(sy*4+phase)**2);
      const fracture=.095*Math.pow(Math.max(0,Math.sin(sx*6.2+sz*4.0+phase)),8);
      const swell=1+broad+weather+bedding-fracture;
      positions[i]=sx*swell+.14*sy*sy*Math.cos(phase);
      positions[i+1]=sy*(1+broad*.64+weather*.48)+.07*sx*Math.sin(sz*3+phase);
      positions[i+2]=sz*swell+.09*sy*Math.sin(phase);
    }
    const welded=mergeVertices(geometry,1e-5);geometry.dispose();geometry=welded;
    geometry.computeBoundingBox();
    const span=geometry.boundingBox.max.y-geometry.boundingBox.min.y;
    geometry.scale(width,height/span,length);geometry.rotateY(phase);geometry.computeBoundingBox();
    geometry.translate(x,heightAt(x,z)-height*burial-geometry.boundingBox.min.y,z);
    return colored(geometry,color,(wx,wy,wz)=>.86+.065*Math.sin(wx*.45+wy*.68+wz*.31)+.025*Math.sin(wy*3.2+wz*.87));
  }

  // Quiet continuous ground, with smoothly shared normals instead of painted facets.
  const extent=72,steps=26;
  for(const sx of [-1,1])for(const sz of [-1,1]){
    const points=[],indices=[];
    for(let row=0;row<=steps;row++)for(let col=0;col<=steps;col++){
      const x=sx*col/steps*extent,z=sz*row/steps*extent;points.push(x,heightAt(x,z),z);
    }
    for(let row=0;row<steps;row++)for(let col=0;col<steps;col++){
      const a=row*(steps+1)+col,b=a+1,c=a+steps+1,d=c+1;
      if(sx*sz>0)indices.push(a,c,b,b,c,d);else indices.push(a,b,c,b,d,c);
    }
    let geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(points,3));geometry.setIndex(indices);
    geometry=colored(geometry,'#263c3f',(x,y,z)=>.88+.023*Math.sin(x*.13+z*.09));
    const mesh=new THREE.Mesh(geometry,material);mesh.name='Subtle continuous abyssal ground';group.add(mesh);
  }

  // Broad, connected distant masses leave uneven windows onto darker open water.
  const formations=14;
  for(let i=0;i<formations;i++){
    const a=i/formations*TAU+(random()-.5)*.22,d=Math.max(45,radius+20)+random()*8;
    const x=Math.sin(a)*d,z=Math.cos(a)*d,width=4.5+random()*4,height=8+random()*10,length=4+random()*4;
    const parts=[roundedRock(x,z,width,height,length,random()*TAU,stoneColors[i%5],.34,20)];
    parts.push(roundedRock(x+Math.cos(a)*width*.8,z-Math.sin(a)*width*.8,width*.72,height*(.50+random()*.30),length*.84,random()*TAU,stoneColors[(i+2)%5],.28,20));
    if(reserve(parts,`far-canyon-${Math.floor(i/3)}`))summary.farFormations++;
  }

  // Mid-distance shapes are low banks, overhang-like shoulders and joined boulders.
  // They replace both geometric towers and the former repeated slab props.
  const acceptedOutcrops=[];
  for(let i=0;i<22;i++){
    const a=i/22*TAU+(random()-.5)*.20,d=i%3===0?33+random()*7:17+random()*4;
    const x=Math.sin(a)*d,z=Math.cos(a)*d,width=1.5+random()*2.3,height=1.8+random()*3.1,length=1.8+random()*2.8;
    const phase=random()*TAU,rock=roundedRock(x,z,width,height,length,phase,stoneColors[(i+1)%5],.26);
    const parts=[rock];
    if(i%2===0)parts.push(roundedRock(x+Math.cos(a)*width*.75,z-Math.sin(a)*width*.75,width*.67,height*.61,length*.7,phase+.74,stoneColors[(i+3)%5],.31,20));
    if(reserve(parts,`mid-bank-${Math.floor(i/4)}`)){
      summary.mediumOutcrops++;acceptedOutcrops.push({x,z,width,length,rock,a,sector:Math.floor(i/4)});
    }
  }

  // Probe the actual displaced rock surface before anchoring a colony into it.
  const ray=new THREE.Ray(),va=new THREE.Vector3(),vb=new THREE.Vector3(),vc=new THREE.Vector3(),hit=new THREE.Vector3();
  function rockSurface(geometry,x,z){
    ray.origin.set(x,35,z);ray.direction.set(0,-1,0);
    const positions=geometry.attributes.position,index=geometry.index;let highest=-Infinity;
    for(let i=0;i<index.count;i+=3){
      va.fromBufferAttribute(positions,index.getX(i));vb.fromBufferAttribute(positions,index.getX(i+1));vc.fromBufferAttribute(positions,index.getX(i+2));
      if(ray.intersectTriangle(va,vb,vc,false,hit))highest=Math.max(highest,hit.y);
    }
    return Number.isFinite(highest)?highest:heightAt(x,z);
  }
  function sponge(x,y,z,width,height,phase){
    const points=[],indices=[],segments=14;
    const rings=[[0,.18],[.18,.73],[.45,1],[.70,.79],[.85,.49],[.82,.32],[.57,.18],[.42,.03]];
    for(let ring=0;ring<rings.length;ring++)for(let i=0;i<segments;i++){
      const a=i/segments*TAU,[u,r]=rings[ring];
      const lobe=1+.13*Math.sin(a*3+phase)+.055*Math.cos(a*5-phase);
      points.push(x+Math.cos(a)*r*width*lobe+height*u*.10*Math.cos(phase),
        y+u*height+.04*height*Math.sin(a*2+phase)*Math.sin(u*Math.PI),
        z+Math.sin(a)*r*width*lobe+height*u*.08*Math.sin(phase));
    }
    for(let ring=0;ring<rings.length-1;ring++)for(let i=0;i<segments;i++){
      const a=ring*segments+i,b=ring*segments+(i+1)%segments,c=a+segments,d=b+segments;indices.push(a,c,b,b,c,d);
    }
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(points,3));geometry.setIndex(indices);
    return colored(geometry,phase>Math.PI?'#506c76':'#6d7375',(px,py,pz)=>py<y+height*.60?.75:.94);
  }
  function curvedStem(points,width,color,segments=6,sides=4){
    const curve=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)));
    return colored(new THREE.TubeGeometry(curve,segments,width,sides,false),color);
  }
  function anemone(x,y,z,size,phase){
    const parts=[],body=colored(new THREE.SphereGeometry(1,12,8),'#596979');
    body.scale(size*.24,size*.16,size*.23);body.translate(x,y+size*.10,z);parts.push(body);
    for(let arm=0;arm<8;arm++){
      const a=arm/8*TAU+phase,reach=size*(.34+.075*Math.sin(arm*1.7+phase)),h=size*(.48+.10*Math.cos(arm*2.1+phase));
      parts.push(curvedStem([[x,y+size*.12,z],[x+Math.cos(a)*reach*.44,y+h*.63,z+Math.sin(a)*reach*.44],
        [x+Math.cos(a)*reach,y+h,z+Math.sin(a)*reach],[x+Math.cos(a)*reach*1.12,y+h*.86,z+Math.sin(a)*reach*1.12]],size*.023,arm%3?'#919fae':'#968b9e',4));
    }
    return parts;
  }
  // An anastomosing gorgonian fan: an irregular curved web of living branches
  // encloses many open cells, with fleshy polyps on its uneven upper contour.
  function seaFan(x,y,z,size,angle,variation){
    const parts=[],stemColor='#55738d',branchColor=variation>.5?'#839db7':'#969faf';
    const transform=(u,v,w)=>[x+u*Math.cos(angle)-w*Math.sin(angle),y+v,z+u*Math.sin(angle)+w*Math.cos(angle)];
    const root=transform(0,0,0),neck=transform(.035*size,.24*size,.03*size);
    parts.push(curvedStem([root,transform(-.025*size,.10*size,0),neck],size*.022,stemColor,4,3));
    const rows=7,columns=8,nodes=[];
    for(let row=0;row<rows;row++){
      const q=row/(rows-1),spread=size*(.17+.43*Math.sin(q*Math.PI*.68));
      for(let col=0;col<columns;col++){
        const lateral=(col/(columns-1)*2-1),jitter=.030*size*Math.sin(row*2.13+col*1.77+variation*TAU);
        const u=lateral*spread+jitter,v=size*(.24+q*.70-.085*lateral*lateral*q)+.023*size*Math.sin(col*2.1+row*1.13+variation*5);
        const w=size*(.10*Math.sin(lateral*2.7+q*1.4+variation*TAU)*q+.042*lateral*lateral);
        nodes.push(new THREE.Vector3(...transform(u,v,w)));
      }
    }
    for(const col of [1,3,6]){
      const end=nodes[columns+col],middle=new THREE.Vector3(...neck).lerp(end,.48).add(new THREE.Vector3(0,.025*size,0));
      parts.push(curvedStem([neck,middle.toArray(),end.toArray()],size*.013,stemColor,4,3));
    }
    function connect(a,b,row,col,vertical){
      const start=nodes[a],end=nodes[b],middle=start.clone().lerp(end,.5);
      middle.y+=size*.010*Math.sin(row*1.9+col*2.3+variation*5);
      middle.x+=Math.sin(angle)*size*.014*Math.cos(row+col*1.7);
      middle.z-=Math.cos(angle)*size*.014*Math.cos(row+col*1.7);
      const width=size*(vertical?.0077:.0058)*(1-.32*row/(rows-1));
      parts.push(curvedStem([start.toArray(),middle.toArray(),end.toArray()],width,branchColor,2,3));
    }
    for(let row=0;row<rows;row++)for(let col=0;col<columns;col++){
      const index=row*columns+col;
      if(row<rows-1)connect(index,index+columns,row,col,true);
      // Uneven openings avoid a uniform wire grid and leave a delicate lace edge.
      if(col<columns-1&&(row*11+col*5+Math.floor(variation*7))%8!==0)connect(index,index+1,row,col,false);
      if(row===rows-1){
        const polyp=colored(new THREE.IcosahedronGeometry(1,0),col%3?'#8aabc3':'#a1a6bf');
        polyp.scale(size*.031,size*.061,size*.027);polyp.rotateZ(.15*Math.sin(col*1.3+variation*4));
        const tip=nodes[index];polyp.translate(tip.x,tip.y+size*.029,tip.z);parts.push(polyp);
      }
    }
    return parts;
  }
  // Seven recurved feather-star arms carry short paired pinnules. The pale
  // edge catches the light but the central body remains a subdued blue violet.
  function featherStar(x,y,z,size,phase){
    const parts=[],body=colored(new THREE.SphereGeometry(1,10,6),'#69778f');
    body.scale(size*.10,size*.065,size*.10);body.translate(x,y+size*.045,z);parts.push(body);
    for(let arm=0;arm<7;arm++){
      const a=phase+arm/7*TAU,reach=size*(.65+.08*Math.sin(arm*1.9+phase)),height=size*(.38+.06*Math.cos(arm*1.3));
      const path=new THREE.CatmullRomCurve3([new THREE.Vector3(x,y+.04*size,z),
        new THREE.Vector3(x+Math.cos(a)*reach*.42,y+height,z+Math.sin(a)*reach*.42),
        new THREE.Vector3(x+Math.cos(a)*reach*.87,y+height*.90,z+Math.sin(a)*reach*.87),
        new THREE.Vector3(x+Math.cos(a)*reach,y+height*.52,z+Math.sin(a)*reach)]);
      parts.push(curvedStem([0,.33,.66,1].map(q=>path.getPoint(q).toArray()),size*.012,'#92a5b7',5,3));
      for(let leaf=0;leaf<4;leaf++)for(const side of [-1,1]){
        const q=.23+leaf*.175,base=path.getPoint(q),length=size*(.12-.016*leaf),b=a+side*Math.PI*.40;
        const end=base.clone().add(new THREE.Vector3(Math.cos(b)*length,.055*size,Math.sin(b)*length));
        parts.push(curvedStem([base.toArray(),base.clone().lerp(end,.55).toArray(),end.toArray()],size*.0056,'#b2bbc4',1,3));
      }
    }
    return parts;
  }

  // Small asymmetric colonies grow out of actual rock shoulders, at varied scales.
  for(let i=0;i<acceptedOutcrops.length;i++){
    const feature=acceptedOutcrops[i],{x,z,width,length,rock,sector}=feature;
    const phase=random()*TAU,angle=phase+random()*.6;
    const sx=x+Math.cos(angle)*width*.36,sz=z+Math.sin(angle)*length*.32;
    const sponges=[],count=1+i%2;
    for(let k=0;k<count;k++){
      const px=sx+Math.cos(k*2.4+phase)*.32,pz=sz+Math.sin(k*2.4+phase)*.30;
      sponges.push(sponge(px,rockSurface(rock,px,pz)-.03,pz,.15+random()*.18,.35+random()*.44,phase+k));
    }
    if(reserve(sponges,`colonies-${sector}`))summary.lobedSponges+=count;
    if(i%2===0){
      const px=x-Math.cos(angle)*width*.38,pz=z-Math.sin(angle)*length*.34,y=rockSurface(rock,px,pz)-.015;
      if(moving(anemone(px,y,pz,.9+random()*.65,phase),sector,[px,y,pz],.024,3+i%4))summary.anemones++;
    }
  }

  // Tall, uneven gardens occupy the inward foreground bank rather than only
  // boulder tops. Exact world boxes let the host reserve every animal passage.
  for(let garden=0;garden<9;garden++){
    const angle=garden/9*TAU+.35+(random()-.5)*.12,radial=18.2+random()*2.8;
    const x=Math.sin(angle)*radial,z=Math.cos(angle)*radial,y=heightAt(x,z)-.035,sector=garden%6;
    let accepted=0;
    for(let fan=0;fan<2;fan++){
      const side=fan===0?-.58:.72,px=x+Math.cos(angle)*side,pz=z-Math.sin(angle)*side,base=heightAt(px,pz)-.035;
      const size=(fan===0?2.8:1.65)+random()*.48,rotation=angle+Math.PI*.17+random()*.34;
      if(moving(seaFan(px,base,pz,size,rotation,random()),sector,[px,base,pz],.052,2+garden%3)){
        summary.seaFans++;summary.branchingCorals++;accepted++;
      }
    }
    if(garden!==4){
      const px=x+Math.cos(angle)*1.35,pz=z-Math.sin(angle)*1.35,base=heightAt(px,pz)-.02;
      if(moving(featherStar(px,base,pz,1.35+random()*.50,angle),sector,[px,base,pz],.032,3+garden%3)){summary.featherStars++;accepted++;}
    }
    const px=x-Math.cos(angle)*1.10,pz=z+Math.sin(angle)*1.10,base=heightAt(px,pz)-.018;
    if(moving(anemone(px,base,pz,1.25+random()*.42,angle),sector,[px,base,pz],.029,3+garden%4)){summary.anemones++;accepted++;}
    if(accepted)summary.coralGardens++;
  }

  // Scattered rounded rubble belongs to a few banks, rather than a regular ring.
  for(let cluster=0;cluster<12;cluster++){
    const a=random()*TAU,d=19+random()*15,cx=Math.sin(a)*d,cz=Math.cos(a)*d,parts=[];
    for(let i=0;i<4;i++){
      const q=random()*TAU,r=random()*2.1,x=cx+Math.cos(q)*r,z=cz+Math.sin(q)*r,size=.13+random()*.32;
      parts.push(roundedRock(x,z,size,.20+random()*.29,size*(.7+random()*.5),q,stoneColors[(i+cluster)%5],.25,10));
    }
    if(reserve(parts,`rubble-${Math.floor(cluster/3)}`))summary.roundedPebbles+=parts.length;
  }
  for(const [name,parts]of buckets){
    const geometry=mergeGeometries(parts,false);parts.forEach(g=>g.dispose());geometry.computeBoundingSphere();
    const mesh=new THREE.Mesh(geometry,material);mesh.name=name;group.add(mesh);
  }
  for(const [sector,records]of motionBuckets){
    const geometry=mergeGeometries(records.map(r=>r.geometry),false),mesh=new THREE.Mesh(geometry,material);
    mesh.name=`Quiet organic colony motion ${sector}`;group.add(mesh);let offset=0;
    for(const record of records){record.offset=offset;offset+=record.base.length;record.geometry.dispose();summary.animatedVertices+=record.base.length/3;}
    geometry.computeBoundingSphere();geometry.boundingSphere.radius+=.09;
    animations.push({mesh,records});
  }
  group.traverse(mesh=>{if(mesh.isMesh){summary.drawCalls++;summary.triangles+=(mesh.geometry.index?.count||mesh.geometry.attributes.position.count)/3;}});
  if(summary.triangles>90000||summary.drawCalls>60)throw new Error(`Cinematic environment exceeds its budget: ${summary.triangles} triangles, ${summary.drawCalls} meshes.`);
  function update(t){
    if(!Number.isFinite(t))throw new Error('Environment animation needs finite seconds.');
    const phase=(((t%PERIOD)+PERIOD)%PERIOD)/PERIOD*TAU;
    for(const {mesh,records}of animations){
      const positions=mesh.geometry.attributes.position.array;
      for(const item of records){
        const [x,y,z]=item.anchor;
        for(let i=0;i<item.base.length;i+=3){
          const h=Math.max(0,item.base[i+1]-y),weight=Math.min(1,h/1.3),sway=item.amplitude*weight*weight,j=item.offset+i;
          positions[j]=item.base[i]+sway*Math.sin(phase*item.cycle+item.phase+h*.7);
          positions[j+1]=item.base[i+1];positions[j+2]=item.base[i+2]+sway*.63*Math.cos(phase*(item.cycle+1)+item.phase+h*.9);
        }
      }
      mesh.geometry.attributes.position.needsUpdate=true;mesh.geometry.computeVertexNormals();
    }
  }
  update(0);return {group,update,summary,rockBoxes};
}
