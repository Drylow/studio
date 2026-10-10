/** Original translucent jellyfish, with inspectable CPU-deformed geometry. */
export function createSleepJellies(THREE, { duration = 300 } = {}) {
  if (!Number.isFinite(duration) || duration <= 0) throw new Error('A positive finite duration is required.');
  const TAU = Math.PI * 2;
  const clamp = (x, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, x));
  const phase = t => (((t % duration) + duration) % duration) / duration * TAU;
  const variants = [
    { name: 'jellyA', radius: .91, height: .66, armLength: 1.84, offset: .32, cycles: 33, color: '#91d2ec' },
    { name: 'jellyB', radius: .75, height: .56, armLength: 1.66, offset: 2.01, cycles: 37, color: '#b4dfe9' },
    { name: 'jellyC', radius: 1.00, height: .70, armLength: 2.04, offset: 4.20, cycles: 31, color: '#77c9e9' },
  ];
  const roots = {}, models = [];
  let triangles = 0, meshCount = 0;

  function mesh(parent, geometry, material, name, moving = false) {
    const object = new THREE.Mesh(geometry, material);
    object.name = name;
    if (moving) geometry.attributes.position.setUsage(THREE.DynamicDrawUsage);
    geometry.computeVertexNormals(); geometry.computeBoundingBox(); geometry.computeBoundingSphere();
    triangles += (geometry.index?.count || geometry.attributes.position.count) / 3;
    meshCount++; parent.add(object); return object;
  }
  function dynamicGeometry(vertexCount, indices) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(vertexCount * 3), 3));
    geometry.setIndex(indices); return geometry;
  }
  function refresh(geometry) {
    geometry.attributes.position.needsUpdate = true;
    geometry.computeVertexNormals(); geometry.computeBoundingBox(); geometry.computeBoundingSphere();
  }

  for (const v of variants) {
    const root = new THREE.Group(); root.name = `${v.name}: luminous layered original jellyfish`;
    roots[v.name] = root;
    const shellMaterial = new THREE.MeshPhongMaterial({
      color: v.color, vertexColors: true, transparent: true, opacity: .49, depthWrite: false,
      side: THREE.FrontSide, flatShading: false, specular: '#bce8f4', shininess: 52,
      emissive: '#286f9d', emissiveIntensity: 1.15,
    });
    // Fresnel changes with the view, never with time; all deformation remains on the CPU.
    shellMaterial.onBeforeCompile = shader => {
      shader.fragmentShader = shader.fragmentShader.replace('#include <opaque_fragment>', `
        float jellyEdge = pow(1.0 - abs(dot(normal, normalize(vViewPosition))), 2.7);
        outgoingLight += vec3(0.22, 0.52, 0.78) * jellyEdge;
        diffuseColor.a *= 0.70 + 0.30 * jellyEdge;
        #include <opaque_fragment>
      `);
    };
    shellMaterial.customProgramCacheKey = () => 'original-jelly-soft-fresnel-v1';
    const filamentMaterial = new THREE.MeshBasicMaterial({
      color: '#79c8eb', transparent: true, opacity: .43, depthWrite: false, toneMapped: true,
    });
    const oralMaterial = new THREE.MeshPhongMaterial({
      color: '#d0ecf5', transparent: true, opacity: .56, depthWrite: false, flatShading: false,
      emissive: '#426e80', emissiveIntensity: .45, specular: '#ccecf5', shininess: 36,
    });
    const internalMaterial = new THREE.MeshPhongMaterial({
      color: '#a4d9ee', transparent: true, opacity: .20, depthWrite: false, flatShading: false,
      emissive: '#5d8b9a', emissiveIntensity: .30,
    });
    const frillMaterial = new THREE.MeshPhongMaterial({
      color: '#b6deed', transparent: true, opacity: .29, depthWrite: false,
      side: THREE.DoubleSide, forceSinglePass: true, flatShading: false,
      emissive: '#335f75', emissiveIntensity: .45, specular: '#d1edf6', shininess: 46,
    });

    // One smooth indexed dome; the last two rings form a soft inward lip.
    const sectors = 48, rings = 12, bellIndices = [], bellRest = [];
    for (let row = 0; row < rings; row++) {
      const theta = row < 10 ? .065 + row / 9 * (Math.PI / 2 - .065) : Math.PI / 2;
      const radius = v.radius * (row < 10 ? Math.sin(theta) : row === 10 ? .97 : .89);
      const y = row < 10 ? v.height * Math.cos(theta) - .035 : row === 10 ? -.095 : -.155;
      for (let side = 0; side < sectors; side++) {
        const a = side / sectors * TAU;
        const edge = row >= 8 ? .017 * Math.cos(a * 6) : .003 * Math.sin(a * 6) * Math.sin(theta);
        const scallop = row >= 8 ? .022 * Math.cos(a * 6) * (row - 7) / 4 : 0;
        bellRest.push(Math.cos(a) * (radius + edge), y + scallop, Math.sin(a) * (radius + edge));
      }
    }
    const top = bellRest.length / 3; bellRest.push(0, v.height - .033, 0);
    for (let row = 0; row < rings - 1; row++) for (let side = 0; side < sectors; side++) {
      const a = row * sectors + side, b = row * sectors + (side + 1) % sectors, c = a + sectors, d = b + sectors;
      bellIndices.push(a, b, c, b, d, c);
    }
    for (let side = 0; side < sectors; side++) bellIndices.push(top, (side + 1) % sectors, side);
    const bellGeometry = dynamicGeometry(top + 1, bellIndices);
    bellGeometry.attributes.position.array.set(bellRest);
    const bellColor = new Float32Array((top + 1) * 4);
    for (let i = 0; i <= top; i++) {
      // Clear crown and a slightly denser margin avoid an opaque hemispherical cutout.
      const depth = clamp(1 - bellRest[i * 3 + 1] / v.height);
      bellColor.set([1, 1, 1, .75 + .25 * Math.pow(depth, .7)], i * 4);
    }
    bellGeometry.setAttribute('color', new THREE.BufferAttribute(bellColor, 4));
    mesh(root, bellGeometry, shellMaterial, 'Smooth clear dome and rolled bell lip', true);

    const tissueGeometry = new THREE.SphereGeometry(v.radius * .82, 24, 6, 0, TAU, 0, Math.PI / 2);
    tissueGeometry.scale(1, v.height * .70 / (v.radius * .82), 1); tissueGeometry.translate(0, -.105, 0);
    const tissueRest = tissueGeometry.attributes.position.array.slice();
    mesh(root, tissueGeometry, new THREE.MeshPhongMaterial({
      color: '#7cbdde', transparent: true, opacity: .075, depthWrite: false,
      side: THREE.FrontSide, emissive: '#335d74', emissiveIntensity: .38, shininess: 38,
    }), 'Second fine translucent tissue layer inside the bell', true);

    const veinCount = 12, veinSections = 7, veinSides = 3, veinIndices = [];
    for (let cord = 0; cord < veinCount; cord++) for (let row = 0; row < veinSections; row++) for (let side = 0; side < veinSides; side++) {
      const a = (cord * (veinSections + 1) + row) * veinSides + side;
      const b = (cord * (veinSections + 1) + row) * veinSides + (side + 1) % veinSides;
      veinIndices.push(a, b, a + veinSides, b, b + veinSides, a + veinSides);
    }
    const veinGeometry = dynamicGeometry(veinCount * (veinSections + 1) * veinSides, veinIndices);
    mesh(root, veinGeometry, new THREE.MeshBasicMaterial({
      color: '#82cfe9', transparent: true, opacity: .19, depthWrite: false, toneMapped: true,
    }), 'Twelve fine luminous meridian contours', true);

    // The fine marginal cord makes the otherwise transparent bell legible.
    const rimSectors = 48, rimSides = 3, rimIndices = [];
    for (let layer = 0; layer < 2; layer++) for (let row = 0; row < rimSectors; row++) for (let side = 0; side < rimSides; side++) {
      const offset = layer * rimSectors * rimSides;
      const a = offset + row * rimSides + side, b = offset + row * rimSides + (side + 1) % rimSides;
      const c = offset + ((row + 1) % rimSectors) * rimSides + side, d = offset + ((row + 1) % rimSectors) * rimSides + (side + 1) % rimSides;
      rimIndices.push(a, b, c, b, d, c);
    }
    const rimGeometry = dynamicGeometry(2 * rimSectors * rimSides, rimIndices);
    mesh(root, rimGeometry, filamentMaterial, 'Two scalloped luminous bell margins', true);

    // Four small internal lobes remain quiet: contraction changes shape, never brightness.
    const lobes = [];
    for (let i = 0; i < 4; i++) {
      const lobe = mesh(root, new THREE.SphereGeometry(1, 8, 4), internalMaterial, 'Smooth inner blue-white oral lobe');
      lobe.scale.set(.125, .085, .205); lobes.push(lobe);
    }
    const core = mesh(root, new THREE.IcosahedronGeometry(.037, 1),
      new THREE.MeshBasicMaterial({ color: '#d9eff5', transparent: true, opacity: .13, depthWrite: false, toneMapped: true }),
      'Tiny steady pale core, no point light or flashing');
    core.position.y = .11;

    // Thin three-dimensional cords, not broad opaque ribbons.
    const filaments = [];
    for (const [kind, count, sections, sides] of [['tentacle', 16, 20, 3], ['oral', 4, 26, 4]]) {
      const indices = [];
      for (let i = 0; i < count; i++) for (let row = 0; row < sections; row++) for (let side = 0; side < sides; side++) {
        const a = (i * (sections + 1) + row) * sides + side;
        const b = (i * (sections + 1) + row) * sides + (side + 1) % sides;
        indices.push(a, b, a + sides, b, b + sides, a + sides);
      }
      const geometry = dynamicGeometry(count * (sections + 1) * sides, indices);
      mesh(root, geometry, kind === 'oral' ? oralMaterial : filamentMaterial,
        kind === 'oral' ? 'Four slender gently twisting oral filaments' : 'Sixteen fine flowing marginal tentacles', true);
      filaments.push({ kind, count, sections, sides, geometry, centers: new Float64Array((sections + 1) * 3) });
    }
    const frillSections = 26, frillIndices = [];
    for (let arm = 0; arm < 4; arm++) for (let row = 0; row < frillSections; row++) for (let col = 0; col < 2; col++) {
      const a = (arm * (frillSections + 1) + row) * 3 + col;
      frillIndices.push(a, a + 1, a + 3, a + 1, a + 4, a + 3);
    }
    const frillGeometry = dynamicGeometry(4 * (frillSections + 1) * 3, frillIndices);
    mesh(root, frillGeometry, frillMaterial, 'Four delicate folded translucent oral tissues', true);
    models.push({ v, bellGeometry, bellRest: new Float32Array(bellRest), tissueGeometry, tissueRest,
      veinGeometry, rimGeometry, filaments, frillGeometry, lobes });
  }

  function update(t) {
    if (!Number.isFinite(t)) throw new Error('A finite time in seconds is required.');
    const a = phase(t);
    for (const model of models) {
      const { v, bellGeometry, bellRest, tissueGeometry, tissueRest, veinGeometry,
        rimGeometry, filaments, frillGeometry, lobes } = model;
      const beat = .5 + .5 * Math.sin(a * v.cycles + v.offset);
      const contraction = beat * beat;
      const radial = 1 - .075 * contraction;
      const p = bellGeometry.attributes.position.array;
      for (let i = 0; i < p.length; i += 3) {
        const rim = clamp(1 - bellRest[i + 1] / v.height);
        const r = radial - .016 * contraction * rim;
        p[i] = bellRest[i] * r;
        p[i + 1] = bellRest[i + 1] * (1 + .065 * contraction) + .020 * contraction * rim;
        p[i + 2] = bellRest[i + 2] * r;
      }
      refresh(bellGeometry);
      const tp = tissueGeometry.attributes.position.array;
      for (let i = 0; i < tp.length; i += 3) {
        tp[i] = tissueRest[i] * (radial - .010 * contraction);
        tp[i + 1] = tissueRest[i + 1] * (1 + .045 * contraction) + .015 * contraction;
        tp[i + 2] = tissueRest[i + 2] * (radial - .010 * contraction);
      }
      refresh(tissueGeometry);
      const vp = veinGeometry.attributes.position.array;
      for (let cord = 0; cord < 12; cord++) for (let row = 0; row <= 7; row++) {
        const angle = cord / 12 * TAU, u = row / 7, theta = .065 + u * (Math.PI / 2 - .065);
        const rim = 1 - Math.cos(theta), bend = radial - .016 * contraction * rim;
        const r = (v.radius * Math.sin(theta) + .004) * bend;
        const y = (v.height * Math.cos(theta) - .035) * (1 + .065 * contraction) + .020 * contraction * rim;
        const dx = v.radius * Math.cos(theta), dy = -v.height * Math.sin(theta), norm = Math.hypot(dx, dy);
        for (let side = 0; side < 3; side++) {
          const edge = side / 3 * TAU, c = Math.cos(edge) * .0024, s = Math.sin(edge) * .0024;
          const i = ((cord * 8 + row) * 3 + side) * 3;
          vp[i] = Math.cos(angle) * r - Math.sin(angle) * c + dy / norm * Math.cos(angle) * s;
          vp[i + 1] = y - dx / norm * s;
          vp[i + 2] = Math.sin(angle) * r + Math.cos(angle) * c + dy / norm * Math.sin(angle) * s;
        }
      }
      refresh(veinGeometry);
      const rp = rimGeometry.attributes.position.array;
      for (let layer = 0; layer < 2; layer++) for (let row = 0; row < 48; row++) {
        const angle = row / 48 * TAU;
        const r = (v.radius * (layer ? .89 : 1) + (layer ? .012 : .017) * Math.cos(angle * 6)) * (radial - .016 * contraction);
        const y = (layer ? -.155 : -.035) + (layer ? .022 : .012) * Math.cos(angle * 6) + .020 * contraction;
        for (let side = 0; side < 3; side++) {
          const edge = side / 3 * TAU, thickness = layer ? .0035 : .0055;
          const i = ((layer * 48 + row) * 3 + side) * 3;
          rp[i] = Math.cos(angle) * (r + Math.cos(edge) * thickness);
          rp[i + 1] = y + Math.sin(edge) * thickness;
          rp[i + 2] = Math.sin(angle) * (r + Math.cos(edge) * thickness);
        }
      }
      refresh(rimGeometry);
      for (let i = 0; i < lobes.length; i++) {
        const angle = i / 4 * TAU + .45;
        lobes[i].position.set(Math.cos(angle) * .23 * radial, -.010, Math.sin(angle) * .23 * radial);
        lobes[i].rotation.y = -angle;
      }

      for (const f of filaments) {
        const positions = f.geometry.attributes.position.array;
        for (let cord = 0; cord < f.count; cord++) {
          const oral = f.kind === 'oral';
          const angle = cord / f.count * TAU + (oral ? .45 : .12), rx = Math.cos(angle), rz = Math.sin(angle);
          const length = v.armLength * (oral ? .96 + .04 * Math.sin(cord * 1.6 + v.offset) : .75 + .20 * (.5 + .5 * Math.sin(cord * 2.3)));
          for (let row = 0; row <= f.sections; row++) {
            const u = row / f.sections, lag = u * 1.6;
            const delayedBeat = .5 + .5 * Math.sin(a * v.cycles + v.offset - lag);
            const wave = Math.sin(a * 6 + cord * 1.73 + v.offset - u * 6.8);
            const drift = Math.sin(a * 8 + cord * 1.11 - u * 4.1);
            const attachment = (oral ? .19 : v.radius * .94) * radial;
            const spread = (oral ? .055 : .025) * u;
            const lateral = (oral ? .17 : .29) * u * wave + (oral ? .045 : .09) * u * u * drift;
            const outward = attachment + spread + (oral ? .055 : .12) * u * Math.sin(a * 5 + cord - u * 5);
            const i = row * 3;
            f.centers[i] = rx * outward - rz * lateral;
            f.centers[i + 1] = -.110 - u * length + .018 * contraction + .035 * u * (delayedBeat - .5)
              + .045 * u * Math.sin(a * 7 + cord * 1.2 - u * 5);
            f.centers[i + 2] = rz * outward + rx * lateral;
          }
          for (let row = 0; row <= f.sections; row++) {
            const u = row / f.sections, previous = Math.max(0, row - 1) * 3, next = Math.min(f.sections, row + 1) * 3;
            let dx = f.centers[next] - f.centers[previous], dy = f.centers[next + 1] - f.centers[previous + 1], dz = f.centers[next + 2] - f.centers[previous + 2];
            const length = Math.hypot(dx, dy, dz); dx /= length; dy /= length; dz /= length;
            // The tangent never becomes horizontal: this frame remains continuous and finite.
            const norm = Math.hypot(dy, dx), sx = dy / norm, sy = -dx / norm;
            const bx = -dz * sy, by = dz * sx, bz = dx * sy - dy * sx;
            const width = oral ? .025 * (1 - u * .82) * (1 + .12 * Math.sin(u * 8)) : .0085 * (1 - u * .72);
            for (let side = 0; side < f.sides; side++) {
              const angle = side / f.sides * TAU + (oral ? .18 * Math.sin(a * 7 + cord + u * 4) : 0);
              const c = Math.cos(angle) * width, s = Math.sin(angle) * width;
              const i = ((cord * (f.sections + 1) + row) * f.sides + side) * 3, center = row * 3;
              positions[i] = f.centers[center] + sx * c + bx * s;
              positions[i + 1] = f.centers[center + 1] + sy * c + by * s;
              positions[i + 2] = f.centers[center + 2] + bz * s;
            }
            if (oral) {
              const twist = angle + u * 4.3 + .75 * Math.sin(u * 10 - a * 4 + cord);
              const scallop = .023 * Math.sin(u * 33 - a * 5 + cord * 2) * Math.sin(u * Math.PI);
              const wing = (.068 + .083 * Math.sin(u * Math.PI)) * (1 - u * .55);
              const fp = frillGeometry.attributes.position.array;
              for (let col = 0; col < 3; col++) {
                const side = col - 1, i = ((cord * (f.sections + 1) + row) * 3 + col) * 3;
                const width = side * (wing + (col === 1 ? 0 : scallop));
                fp[i] = f.centers[row * 3] + Math.cos(twist) * width;
                fp[i + 1] = f.centers[row * 3 + 1] + side * .034 * Math.sin(u * 28 - a * 6 + cord) * Math.sin(u * Math.PI);
                fp[i + 2] = f.centers[row * 3 + 2] + Math.sin(twist) * width;
              }
            }
          }
        }
        refresh(f.geometry);
        if (f.kind === 'oral') refresh(frillGeometry);
      }
    }
  }
  update(0);
  if (triangles > 18000) throw new Error(`Jellyfish exceed their 18000-triangle budget: ${triangles}.`);
  const summary = {
    duration, count: 3, rootNames: Object.keys(roots), triangles, meshes: meshCount,
    coordinateSystem: 'Y-up; luminous layered bell near origin, delicate folded oral tissues and fine curved tentacles below',
    animation: 'CPU position deformation, indexed smooth normals, integer periodic frequencies and stateless seek',
    transparentBellOpacity: .49, brightnessAnimation: false, pointLights: 0,
    tissueLayers: 2, meridianContoursPerBell: 12, tentaclesPerBell: 16, foldedOralTissuesPerBell: 4,
    maximumOralArmLength: 2.06, originalAssets: true,
    localBounds: Object.fromEntries(Object.entries(roots).map(([name, root]) => {
      const box = new THREE.Box3().setFromObject(root, true);
      return [name, { atTime: 0, min: box.min.toArray(), max: box.max.toArray() }];
    })),
  };
  return { roots, update, summary };
}
