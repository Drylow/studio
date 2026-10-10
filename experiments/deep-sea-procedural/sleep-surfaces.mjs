/** Original tiled pigment/grain textures, generated in code, anchored in 3D. */
export function addSleepSurfaceDetail(THREE, group, { cinematic = false } = {}) {
  const size=512,TAU=Math.PI*2;let state=80914;
  const random=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state/4294967296;};
  function lattice(n){return Float32Array.from({length:n*n},()=>random());}
  const grids=[4,8,16,32,64].map(n=>({n,data:lattice(n)}));
  function noise(grid,u,v){
    const x=u*grid.n,z=v*grid.n,ix=Math.floor(x),iz=Math.floor(z),fx=x-ix,fz=z-iz;
    const sx=fx*fx*(3-2*fx),sz=fz*fz*(3-2*fz),at=(a,b)=>grid.data[((b%grid.n)+grid.n)%grid.n*grid.n+((a%grid.n)+grid.n)%grid.n];
    return (at(ix,iz)*(1-sx)+at(ix+1,iz)*sx)*(1-sz)+(at(ix,iz+1)*(1-sx)+at(ix+1,iz+1)*sx)*sz;
  }
  const pixels=new Uint8Array(size*size*4);
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    const u=x/size,v=y/size,values=grids.map(grid=>noise(grid,u,v));
    const grain=.5+.17*(random()-.5),coarse=.46*values[0]+.27*values[1]+.17*values[2]+.1*values[3];
    const fissure=Math.min(1,Math.abs(values[1]-.49)*38);
    const ripple=.5+.5*Math.sin(TAU*(u*15+.18*Math.sin(TAU*v*3)+.09*Math.sin(TAU*v*7)));
    const i=(y*size+x)*4;
    // r: broad pigment, g: narrow weathered seams, b: resolved silt ripples.
    pixels[i]=Math.round(255*Math.max(0,Math.min(1,coarse*.82+grain*.18)));
    pixels[i+1]=Math.round(255*(.64+.36*fissure));
    pixels[i+2]=Math.round(255*(ripple*.84+grain*.16));pixels[i+3]=255;
  }
  const texture=new THREE.DataTexture(pixels,size,size,THREE.RGBAFormat);
  texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.magFilter=THREE.LinearFilter;
  texture.minFilter=THREE.LinearMipmapLinearFilter;texture.generateMipmaps=true;texture.needsUpdate=true;
  group.traverse(mesh=>{
    if(!mesh.isMesh)return;
    const sand=mesh.name.includes('sediment')||mesh.name.includes('seabed');
    const original=mesh.material,callback=original.onBeforeCompile;
    const material=original.clone();material.name=original.name+' — original surface grain';
    material.onBeforeCompile=shader=>{
      callback(shader);shader.uniforms.uSleepGrain={value:texture};
      shader.vertexShader=shader.vertexShader.replace('#include <common>','#include <common>\nvarying vec3 vSleepWorld,vSleepNormal;');
      shader.vertexShader=shader.vertexShader.replace('#include <fog_vertex>','#include <fog_vertex>\nvSleepWorld=(modelMatrix*vec4(transformed,1.0)).xyz;vSleepNormal=normalize(mat3(modelMatrix)*normal);');
      shader.fragmentShader=shader.fragmentShader.replace('#include <common>','#include <common>\nvarying vec3 vSleepWorld,vSleepNormal;uniform sampler2D uSleepGrain;');
      const detail=sand?(cinematic?`
        vec3 sleepSilt=texture2D(uSleepGrain,vSleepWorld.xz/7.9).rgb;
        outgoingLight*=.88+.16*sleepSilt.r+.035*sleepSilt.b;
      `:`
        vec3 sleepSilt=texture2D(uSleepGrain,vSleepWorld.xz/3.7).rgb;
        outgoingLight*=.76+.26*sleepSilt.r+.19*sleepSilt.b;
      `):`
        vec3 sleepWeights=pow(abs(vSleepNormal),vec3(3.0));sleepWeights/=max(dot(sleepWeights,vec3(1.0)),.0001);
        vec3 sleepStone=texture2D(uSleepGrain,vSleepWorld.zy/3.4).rgb*sleepWeights.x
          +texture2D(uSleepGrain,vSleepWorld.xz/3.4).rgb*sleepWeights.y
          +texture2D(uSleepGrain,vSleepWorld.xy/3.4).rgb*sleepWeights.z;
        outgoingLight*=(.70+.57*sleepStone.r)*(.72+.28*sleepStone.g);
      `;
      shader.fragmentShader=shader.fragmentShader.replace('#include <opaque_fragment>',detail+'\n#include <opaque_fragment>');
    };
    material.customProgramCacheKey=()=>`deep-sea-surface-v1-${cinematic?'cinematic':'study'}-${sand?'silt':'stone'}`;
    mesh.material=material;
  });
  return {texture_resolution:size,original_texture_count:1,world_anchored:true};
}
