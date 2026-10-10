/** Original restrained skin sheen; the actual marine geometry still deforms on CPU. */
export function addMarineSurfaceDetail(THREE, roots) {
  const cache=new Map();let meshes=0;
  for(const [name,root]of Object.entries(roots)){
    if(name.startsWith('jelly'))continue;
    root.traverse(mesh=>{
      if(!mesh.isMesh||Array.isArray(mesh.material))return;
      const original=mesh.material;
      if(!cache.has(original)){
        const callback=original.onBeforeCompile,material=original.clone();
        material.name='Smooth original marine pigment and grazing sheen';
        material.onBeforeCompile=shader=>{
          callback(shader);
          shader.vertexShader=shader.vertexShader.replace('#include <common>','#include <common>\nvarying vec3 vMarineN,vMarineEye,vMarineLocal;');
          shader.vertexShader=shader.vertexShader.replace('#include <fog_vertex>','#include <fog_vertex>\nvMarineN=normalize(transformedNormal);vMarineEye=-mvPosition.xyz;vMarineLocal=position;');
          shader.fragmentShader=shader.fragmentShader.replace('#include <common>','#include <common>\nvarying vec3 vMarineN,vMarineEye,vMarineLocal;');
          shader.fragmentShader=shader.fragmentShader.replace('#include <opaque_fragment>',`
            vec3 marineN=normalize(vMarineN),marineV=normalize(vMarineEye);
            float marineRim=pow(1.0-abs(dot(marineN,marineV)),3.4);
            float marineShine=pow(max(dot(reflect(-normalize(vec3(-.38,.73,.55)),marineN),marineV),0.0),30.0);
            float marinePigment=.97+.025*sin(vMarineLocal.x*2.7+sin(vMarineLocal.z*4.1));
            outgoingLight*=marinePigment;
            outgoingLight+=vec3(.009,.019,.030)*marineRim+vec3(.024,.036,.045)*marineShine;
            #include <opaque_fragment>
          `);
        };
        material.customProgramCacheKey=()=> 'deep-sea-smooth-skin-v1';cache.set(original,material);
      }
      mesh.material=cache.get(original);meshes++;
    });
  }
  return {original_shader:true,meshes,materials:cache.size,external_textures:0};
}
