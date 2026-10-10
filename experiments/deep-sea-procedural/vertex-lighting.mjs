/** Optional texture-free vertex lighting for a software-rendered faceted scene. */
export function applyVertexLighting(THREE, scene, camera) {
  const lights = { hemi: null, directional: null, spot: null, point: null };
  scene.traverse(object => {
    if (object.isHemisphereLight && !lights.hemi) lights.hemi = object;
    if (object.isDirectionalLight && !lights.directional) lights.directional = object;
    if (object.isSpotLight && !lights.spot) lights.spot = object;
    if (object.isPointLight && !lights.point) lights.point = object;
  });
  const vector = () => new THREE.Vector3();
  const color = () => new THREE.Color(0, 0, 0);
  const uniforms = {
    uDeepHemiSky: { value: color() }, uDeepHemiGround: { value: color() },
    uDeepHemiDirection: { value: vector() },
    uDeepDirectionalColor: { value: color() }, uDeepDirectionalDirection: { value: vector() },
    uDeepSpotColor: { value: color() }, uDeepSpotPosition: { value: vector() }, uDeepSpotDirection: { value: vector() },
    uDeepSpotDistance: { value: 0 }, uDeepSpotDecay: { value: 2 }, uDeepSpotCone: { value: 0 }, uDeepSpotPenumbra: { value: 1 },
    uDeepPointColor: { value: color() }, uDeepPointPosition: { value: vector() },
    uDeepPointDistance: { value: 0 }, uDeepPointDecay: { value: 2 },
  };
  const declarations = `
    varying vec3 vDeepLight;
    uniform vec3 uDeepHemiSky, uDeepHemiGround, uDeepHemiDirection;
    uniform vec3 uDeepDirectionalColor, uDeepDirectionalDirection;
    uniform vec3 uDeepSpotColor, uDeepSpotPosition, uDeepSpotDirection;
    uniform float uDeepSpotDistance, uDeepSpotDecay, uDeepSpotCone, uDeepSpotPenumbra;
    uniform vec3 uDeepPointColor, uDeepPointPosition;
    uniform float uDeepPointDistance, uDeepPointDecay;
    float deepDistanceFalloff(float distanceValue, float cutoff, float decay) {
      float falloff = 1.0 / max(pow(max(distanceValue, 0.01), decay), 0.01);
      if (cutoff > 0.0) {
        float ratio = distanceValue / cutoff;
        float windowValue = clamp(1.0 - ratio*ratio*ratio*ratio, 0.0, 1.0);
        falloff *= windowValue * windowValue;
      }
      return falloff;
    }
  `;
  const lighting = `
    vec3 deepN = normalize(transformedNormal);
    vDeepLight = mix(uDeepHemiGround, uDeepHemiSky, dot(deepN,uDeepHemiDirection)*0.5+0.5);
    vDeepLight += uDeepDirectionalColor * max(dot(deepN,uDeepDirectionalDirection),0.0);
    vec3 deepToSpot = uDeepSpotPosition - mvPosition.xyz;
    float deepSpotLength = max(length(deepToSpot),0.001);
    vec3 deepSpotL = deepToSpot / deepSpotLength;
    float deepCone = smoothstep(uDeepSpotCone,uDeepSpotPenumbra,dot(deepSpotL,uDeepSpotDirection));
    vDeepLight += uDeepSpotColor * max(dot(deepN,deepSpotL),0.0) * deepCone * deepDistanceFalloff(deepSpotLength,uDeepSpotDistance,uDeepSpotDecay);
    vec3 deepToPoint = uDeepPointPosition - mvPosition.xyz;
    float deepPointLength = max(length(deepToPoint),0.001);
    vDeepLight += uDeepPointColor * max(dot(deepN,deepToPoint/deepPointLength),0.0) * deepDistanceFalloff(deepPointLength,uDeepPointDistance,uDeepPointDecay);
    vDeepLight *= 0.3183098861837907;
  `;
  const cache = new Map();
  function replace(original) {
    if (!original?.isMeshLambertMaterial) return original;
    if (cache.has(original)) return cache.get(original).replacement;
    if (original.map || original.normalMap || original.lightMap || original.alphaMap) return original;
    const replacement = new THREE.MeshBasicMaterial({
      color: original.color.clone(), vertexColors: original.vertexColors,
      side: original.side, transparent: original.transparent, opacity: original.opacity,
      depthTest: original.depthTest, depthWrite: original.depthWrite, fog: original.fog,
      toneMapped: original.toneMapped, wireframe: original.wireframe,
      blending: original.blending, alphaTest: original.alphaTest,
    });
    replacement.name = `${original.name || 'Faceted mesh'} — vertex lit`;
    const emissive = { value: original.emissive.clone().multiplyScalar(original.emissiveIntensity) };
    replacement.onBeforeCompile = shader => {
      Object.assign(shader.uniforms, uniforms, { uDeepEmissive: emissive });
      shader.vertexShader = shader.vertexShader.replace('#include <common>', '#include <common>\n'+declarations);
      // Basic does not ordinarily need normals; Three's chunks handle scaled instances.
      shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>', `
        #include <beginnormal_vertex>
        #include <defaultnormal_vertex>
        #include <begin_vertex>
      `);
      shader.vertexShader = shader.vertexShader.replace('#include <fog_vertex>', '#include <fog_vertex>\n'+lighting);
      shader.fragmentShader = shader.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vDeepLight; uniform vec3 uDeepEmissive;');
      shader.fragmentShader = shader.fragmentShader.replace('vec3 outgoingLight = reflectedLight.indirectDiffuse;', 'vec3 outgoingLight = reflectedLight.indirectDiffuse * vDeepLight + uDeepEmissive;');
    };
    replacement.customProgramCacheKey = () => 'deep-sea-vertex-lighting-v1';
    cache.set(original, { replacement, emissive });
    return replacement;
  }
  scene.traverse(object => {
    if (!object.isMesh || !object.material) return;
    object.material = Array.isArray(object.material) ? object.material.map(replace) : replace(object.material);
  });
  const a=vector(), b=vector();
  function update() {
    scene.updateMatrixWorld(true); camera.updateMatrixWorld(true);
    const view = camera.matrixWorldInverse;
    if (lights.hemi) {
      uniforms.uDeepHemiSky.value.copy(lights.hemi.color).multiplyScalar(lights.hemi.intensity);
      uniforms.uDeepHemiGround.value.copy(lights.hemi.groundColor).multiplyScalar(lights.hemi.intensity);
      lights.hemi.getWorldPosition(a); uniforms.uDeepHemiDirection.value.copy(a.normalize()).transformDirection(view);
    }
    if (lights.directional) {
      lights.directional.getWorldPosition(a); lights.directional.target.getWorldPosition(b);
      uniforms.uDeepDirectionalDirection.value.copy(a.sub(b).normalize()).transformDirection(view);
      uniforms.uDeepDirectionalColor.value.copy(lights.directional.color).multiplyScalar(lights.directional.intensity);
    }
    if (lights.spot) {
      lights.spot.getWorldPosition(a); lights.spot.target.getWorldPosition(b);
      uniforms.uDeepSpotPosition.value.copy(a).applyMatrix4(view);
      uniforms.uDeepSpotDirection.value.copy(a.sub(b).normalize()).transformDirection(view);
      uniforms.uDeepSpotColor.value.copy(lights.spot.color).multiplyScalar(lights.spot.intensity);
      uniforms.uDeepSpotDistance.value=lights.spot.distance; uniforms.uDeepSpotDecay.value=lights.spot.decay;
      uniforms.uDeepSpotCone.value=Math.cos(lights.spot.angle);
      uniforms.uDeepSpotPenumbra.value=Math.cos(lights.spot.angle*(1-lights.spot.penumbra));
    }
    if (lights.point) {
      lights.point.getWorldPosition(a); uniforms.uDeepPointPosition.value.copy(a).applyMatrix4(view);
      uniforms.uDeepPointColor.value.copy(lights.point.color).multiplyScalar(lights.point.intensity);
      uniforms.uDeepPointDistance.value=lights.point.distance; uniforms.uDeepPointDecay.value=lights.point.decay;
    }
    for (const [original, { replacement, emissive }] of cache) {
      replacement.color.copy(original.color); replacement.opacity=original.opacity;
      emissive.value.copy(original.emissive).multiplyScalar(original.emissiveIntensity);
    }
  }
  update();
  return { update, materials: cache.size };
}
