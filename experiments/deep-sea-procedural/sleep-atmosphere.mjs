// Original, gentle underwater depth. No textures, generation service or game assets.
// All motion is a bounded integer harmonic of the period, including a rewind.
export function createSleepAtmosphere(THREE, {
  duration = 300, ground = () => -7.5, radius = 26, seed = 942701,
  particleCount = 1250, waterColor = '#071a26', fogDensity = .024,
} = {}) {
  if (!Number.isFinite(duration) || duration <= 0) throw new Error('Atmosphere needs a positive duration.');
  const group = new THREE.Group(); group.name = 'Original cinematic water atmosphere';
  const tau = Math.PI * 2;
  let state = seed >>> 0;
  const random = () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296; };
  const uniforms = {
    uPhase: { value: 0 },
    uFogDensity: { value: fogDensity },
    uWaterColor: { value: new THREE.Color(waterColor) },
  };

  // The dome fills distant water, rather than leaving a uniform empty background.
  // It follows camera translation only; the vertical lighting stays world upright.
  const domeMaterial = new THREE.ShaderMaterial({
    uniforms,
    side: THREE.BackSide, depthWrite: false, depthTest: false,
    vertexShader: `
      varying vec3 vDirection;
      void main() {
        vDirection = position;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform float uPhase;
      uniform vec3 uWaterColor;
      varying vec3 vDirection;
      void main() {
        vec3 d = normalize(vDirection);
        float above = smoothstep(-0.50, 0.75, d.y);
        float zenith = smoothstep(0.05, 0.96, d.y);
        vec3 water = mix(uWaterColor, vec3(0.012, 0.041, 0.060), above);
        water = mix(water, vec3(0.020, 0.062, 0.082), zenith * 0.50);
        float softCloud = sin(d.x * 3.0 + sin(d.z * 2.3) + 0.025 * sin(uPhase));
        float upperHaze = pow(max(0.0, 0.5+0.5*sin(d.x*2.4-d.z*1.7)), 4.0);
        water *= 1.0 + 0.12 * softCloud * above;
        water += vec3(0.002,0.007,0.009)*upperHaze*above;
        gl_FragColor = vec4(water, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }
    `,
  });
  const dome = new THREE.Mesh(new THREE.SphereGeometry(118, 28, 14), domeMaterial);
  dome.name = 'Blue-black distant water gradient'; dome.frustumCulled = false;
  dome.renderOrder = -1000; group.add(dome);

  // Very broad, low-contrast scattering. These are intentionally not solid scenery.
  // Soft silhouette, open ends and subdued alpha prevent the opaque stripe effect.
  const beamMaterial = new THREE.ShaderMaterial({
    uniforms: { ...uniforms, uBeamColor: { value: new THREE.Color('#5e8490') } },
    transparent: true, depthWrite: false, depthTest: true,
    side: THREE.DoubleSide, blending: THREE.AdditiveBlending,
    vertexShader: `
      varying vec3 vWorld;
      varying vec3 vNormalWorld;
      varying vec2 vUv;
      void main() {
        vUv = uv;
        vec4 p = modelMatrix * vec4(position, 1.0);
        vWorld = p.xyz;
        vNormalWorld = normalize(mat3(modelMatrix) * normal);
        gl_Position = projectionMatrix * viewMatrix * p;
      }
    `,
    fragmentShader: `
      uniform float uFogDensity;
      uniform vec3 uBeamColor;
      varying vec3 vWorld;
      varying vec3 vNormalWorld;
      varying vec2 vUv;
      void main() {
        vec3 sight = normalize(cameraPosition - vWorld);
        float softEdge = pow(abs(dot(normalize(vNormalWorld), sight)), 2.7);
        float ends = smoothstep(0.0, 0.32, vUv.y) * (1.0 - smoothstep(0.78, 1.0, vUv.y));
        float distanceToEye = length(cameraPosition - vWorld);
        float attenuation = exp(-uFogDensity * distanceToEye * 0.72);
        float nearby = smoothstep(2.0, 10.0, distanceToEye);
        float alpha = 0.09 * softEdge * ends * attenuation * nearby;
        gl_FragColor = vec4(uBeamColor, alpha);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }
    `,
  });
  const beams = [];
  const beamGeometry = new THREE.CylinderGeometry(1.8, 5.8, 29, 18, 1, true);
  for (let i = 0; i < 8; i++) {
    const angle = i / 8 * tau + .17;
    const distance = radius * (.72 + .24 * Math.sin(i * 1.7));
    const x = distance * Math.sin(angle), z = distance * Math.cos(angle);
    const beam = new THREE.Mesh(beamGeometry, beamMaterial);
    beam.name = `Soft water scattering ${i + 1}`;
    beam.position.set(x, ground(x, z) + 14.2, z);
    beam.rotation.set(.09 * Math.sin(i * 1.71), i * .73, .065 * Math.cos(i * 2.07));
    beam.scale.set(1 + .2 * Math.sin(i * 1.9), 1, 1 + .16 * Math.cos(i * 1.4));
    beam.renderOrder = 3;
    beams.push({ mesh: beam, baseX: beam.rotation.x, baseZ: beam.rotation.z, offset: i * .81 });
    group.add(beam);
  }

  // Tiny slow suspended plankton is GPU animated: no geometry upload every frame.
  // No bubbles, coloured neon dots, bursts or visibility switches.
  const positions = new Float32Array(particleCount * 3);
  const sizes = new Float32Array(particleCount), offsets = new Float32Array(particleCount);
  const alphas = new Float32Array(particleCount);
  for (let i = 0; i < particleCount; i++) {
    const angle = random() * tau, distance = Math.sqrt(random()) * (radius + 37);
    const x = distance * Math.sin(angle), z = distance * Math.cos(angle);
    const y = ground(x, z) + 1.1 + Math.pow(random(), .8) * 21;
    positions.set([x, y, z], i * 3);
    sizes[i] = .022 + random() * .032;
    offsets[i] = random() * tau;
    alphas[i] = .13 + random() * .20;
  }
  const particlesGeometry = new THREE.BufferGeometry();
  particlesGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  particlesGeometry.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  particlesGeometry.setAttribute('aOffset', new THREE.BufferAttribute(offsets, 1));
  particlesGeometry.setAttribute('aAlpha', new THREE.BufferAttribute(alphas, 1));
  const particlesMaterial = new THREE.ShaderMaterial({
    uniforms: { ...uniforms, uParticleColor: { value: new THREE.Color('#9bb4b9') } },
    transparent: true, depthWrite: false, depthTest: true,
    vertexShader: `
      uniform float uPhase;
      attribute float aSize;
      attribute float aOffset;
      attribute float aAlpha;
      varying float vDepth;
      varying float vAlpha;
      void main() {
        vec3 p = position;
        p += vec3(0.42 * sin(2.0 * uPhase + aOffset),
                  0.24 * sin(3.0 * uPhase + 1.7 * aOffset),
                  0.37 * cos(2.0 * uPhase + 1.3 * aOffset));
        vec4 eye = modelViewMatrix * vec4(p, 1.0);
        vDepth = max(0.1, -eye.z); vAlpha = aAlpha;
        gl_PointSize = clamp(aSize * 800.0 / vDepth, 0.65, 3.4);
        gl_Position = projectionMatrix * eye;
      }
    `,
    fragmentShader: `
      uniform float uFogDensity;
      uniform vec3 uParticleColor;
      varying float vDepth;
      varying float vAlpha;
      void main() {
        float r = length(gl_PointCoord - vec2(0.5)) * 2.0;
        float dotShape = exp(-r * r * 5.6) * (1.0 - smoothstep(0.68, 1.0, r));
        float alpha = vAlpha * dotShape * exp(-uFogDensity * vDepth);
        gl_FragColor = vec4(uParticleColor, alpha);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }
    `,
  });
  const plankton = new THREE.Points(particlesGeometry, particlesMaterial);
  plankton.name = 'Fine suspended plankton'; plankton.renderOrder = 4; group.add(plankton);

  function update(t, camera) {
    if (!Number.isFinite(t)) throw new Error('A finite atmosphere time is required.');
    const phase = ((t % duration) + duration) % duration / duration * tau;
    uniforms.uPhase.value = phase;
    if (camera?.position) dome.position.copy(camera.position);
    for (const item of beams) {
      item.mesh.rotation.x = item.baseX + .008 * Math.sin(phase + item.offset);
      item.mesh.rotation.z = item.baseZ + .009 * Math.sin(2 * phase + item.offset);
    }
  }
  update(0);
  return {
    group, update,
    summary: {
      original_shader_gradient: true,
      soft_scattering_sheets: beams.length,
      suspended_plankton_particles: particleCount,
      additional_triangles: dome.geometry.index.count / 3 + beamGeometry.index.count / 3 * beams.length,
      period_seconds: duration, periodic_motion: true,
      external_textures: 0, solid_collision_obstacles: 0,
    },
  };
}
