/**
 * Original living shoals. Ordinary indexed meshes expose the actual animated
 * vertices to Box3 and scene diagnostics; nothing is hidden in a GPU shader.
 * Y is up, +X is forward. The caller supplies each shoal's world trajectory.
 */
export function createSleepShoals(THREE, { duration = 300 } = {}) {
  if (!Number.isFinite(duration) || duration <= 0) throw new Error('A positive finite loop duration is required.');
  const TAU = Math.PI * 2;
  const wrap = t => ((t % duration) + duration) % duration;
  const clamp = (x, low = 0, high = 1) => Math.max(low, Math.min(high, x));
  const randomFor = initial => {
    let state = initial >>> 0;
    return () => {
      state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
      return state / 4294967296;
    };
  };
  // Fine original scale rows, deliberately low contrast. A generated texture
  // preserves smooth continuous bodies without adding thousands of plates.
  const textureWidth = 256, textureHeight = 128;
  const texturePixels = new Uint8Array(textureWidth * textureHeight * 4);
  for (let y = 0; y < textureHeight; y++) for (let x = 0; x < textureWidth; x++) {
    const rows = y / textureHeight * 12;
    const row = Math.floor(rows), v = rows - row;
    const columns = x / textureWidth * 42 + (row % 2) * .5;
    const u = columns - Math.floor(columns) - .5;
    const curve = .78 - .95 * u * u;
    const edge = Math.exp(-Math.pow((v - curve) / .06, 2));
    const value = Math.round(253 - 11 * edge - 2 * Math.sin(u * Math.PI) ** 2);
    const index = (y * textureWidth + x) * 4;
    texturePixels[index] = texturePixels[index + 1] = texturePixels[index + 2] = value;
    texturePixels[index + 3] = 255;
  }
  // Non-body vertices use this plain texel (eyes, mouth and fin membranes).
  texturePixels[0] = texturePixels[1] = texturePixels[2] = 255;
  const scaleTexture = new THREE.DataTexture(texturePixels, textureWidth, textureHeight, THREE.RGBAFormat);
  scaleTexture.colorSpace = THREE.SRGBColorSpace;
  scaleTexture.wrapS = scaleTexture.wrapT = THREE.RepeatWrapping;
  scaleTexture.magFilter = THREE.LinearFilter;
  scaleTexture.minFilter = THREE.LinearMipmapLinearFilter;
  scaleTexture.generateMipmaps = true; scaleTexture.needsUpdate = true;
  const material = new THREE.MeshLambertMaterial({ vertexColors: true, map: scaleTexture, flatShading: false });
  const species = [
    { name: 'silver fusiform fish', length: 1.30, depth: .208, width: .113, back: '#38545c', side: '#758e92', belly: '#93aaa6', fin: '#516e78' },
    { name: 'deep-bodied olive fish', length: 1.07, depth: .272, width: .120, back: '#3f5854', side: '#758d7f', belly: '#98aa96', fin: '#526d66' },
    { name: 'slender blue-silver fish', length: 1.49, depth: .147, width: .087, back: '#365462', side: '#7f9fa5', belly: '#a0b6b0', fin: '#567885' },
  ];

  function makeTemplate(spec) {
    const positions = [], indices = [], colors = [], flutter = [], uvs = [];
    const back = new THREE.Color(spec.back), side = new THREE.Color(spec.side);
    const belly = new THREE.Color(spec.belly), fin = new THREE.Color(spec.fin);
    const dark = new THREE.Color('#152b2d'), eyeRim = new THREE.Color('#6f8982');
    const gillPigment = new THREE.Color('#60776e');
    const L = spec.length, H = spec.depth, W = spec.width;
    function vertex(x, y, z, color, finFlex = 0, uv = [0, 0]) {
      const id = positions.length / 3;
      positions.push(x, y, z); colors.push(color.r, color.g, color.b); flutter.push(finFlex); uvs.push(...uv);
      return id;
    }
    function addPart(points, faces, color, flex = []) {
      const offset = positions.length / 3;
      for (let i = 0; i < points.length; i++) vertex(...points[i], color, flex[i] || 0);
      for (const face of faces) indices.push(...face.map(i => i + offset));
    }
    // A pointed nose and narrow tail peduncle, with uninterrupted silver flanks.
    const rings = [
      [-.54, .14, .19], [-.38, .43, .46], [-.18, .81, .82], [.02, 1, 1],
      [.21, .87, .92], [.36, .60, .75], [.475, .24, .30], [.535, .070, .085],
    ];
    const sides = 10, ringStride = sides + 1;
    for (let r = 0; r < rings.length; r++) {
      const [x, h, w] = rings[r];
      for (let j = 0; j <= sides; j++) {
        const a = j / sides * TAU, y = Math.cos(a) * H * h, z = Math.sin(a) * W * w;
        const dorsal = clamp((Math.cos(a) + .10) / .85);
        const ventral = clamp((-Math.cos(a) - .28) / .72);
        const color = side.clone().lerp(back, dorsal * .96).lerp(belly, ventral * .58);
        // Broad contiguous lateral sheen, not independently colored triangles.
        color.multiplyScalar(.96 + .04 * Math.cos(x * 3.2));
        vertex(x * L, y, z, color, 0, [(x + .54) / 1.075, j / sides]);
      }
    }
    for (let r = 0; r < rings.length - 1; r++) for (let j = 0; j < sides; j++) {
      const a = r * ringStride + j, next = a + 1, b = a + ringStride;
      indices.push(a, next, b, next, next + ringStride, b);
    }
    const tailCenter = vertex(rings[0][0] * L, 0, 0, fin);
    const noseCenter = vertex(rings.at(-1)[0] * L + .009 * L, 0, 0, side);
    for (let j = 0; j < sides; j++) {
      indices.push(tailCenter, j + 1, j);
      const a = (rings.length - 1) * ringStride + j;
      const b = a + 1;
      indices.push(noseCenter, a, b);
    }
    function membrane(outline, axis = 'z', thickness = .006, flex = 0) {
      const points = [];
      for (const sign of [-1, 1]) for (const p of outline) {
        const v = p.slice(); v[axis === 'z' ? 2 : 1] += sign * thickness; points.push(v);
      }
      const n = outline.length, faces = [], bends = [];
      for (let i = 1; i < n - 1; i++) faces.push([0, i + 1, i], [n, n + i, n + i + 1]);
      for (let i = 0; i < n; i++) {
        const j = (i + 1) % n;
        faces.push([i, j, i + n], [j, j + n, i + n]);
      }
      for (let side = 0; side < 2; side++) for (let i = 0; i < n; i++) bends.push(i === 0 ? 0 : flex);
      addPart(points, faces, fin, bends);
    }
    // Concave fork between two caudal lobes; each is a closed thin membrane.
    membrane([[-.53 * L, 0, 0], [-.74 * L, H * .98, 0], [-.77 * L, H * .77, 0], [-.70 * L, H * .19, 0]]);
    membrane([[-.53 * L, 0, 0], [-.70 * L, -H * .19, 0], [-.77 * L, -H * .73, 0], [-.74 * L, -H * .91, 0]]);
    membrane([[.13 * L, H * .95, 0], [-.10 * L, H * 1.39, 0], [-.19 * L, H * 1.37, 0], [-.28 * L, H * .92, 0], [-.36 * L, H * .48, 0]]);
    membrane([[-.09 * L, -H * .87, 0], [-.31 * L, -H * 1.10, 0], [-.38 * L, -H * 1.05, 0], [-.39 * L, -H * .42, 0]]);
    for (const sign of [-1, 1]) {
      membrane([
        [.10 * L, -H * .35, sign * W * .86],
        [-.13 * L, -H * .53, sign * W * 2.02],
        [-.19 * L, -H * .58, sign * W * 2.00],
        [-.23 * L, -H * .57, sign * W * .96],
      ], 'y', .004, sign * .022);
      // Fine dark eyes sit on the flank rather than large cartoon eyeballs.
      const eyeX = .38 * L, eyeY = H * .21, eyeZ = sign * W * .73;
      const eyeRadius = H * .12;
      const ring = [], eyeFaces = [], segments = 7;
      for (let j = 0; j < segments; j++) {
        const a = j / segments * TAU;
        ring.push([eyeX + Math.cos(a) * eyeRadius, eyeY + Math.sin(a) * eyeRadius, eyeZ + sign * .005]);
      }
      ring.push([eyeX, eyeY, eyeZ + sign * .012]);
      for (let j = 0; j < segments; j++) eyeFaces.push(sign === 1 ? [segments, j, (j + 1) % segments] : [segments, (j + 1) % segments, j]);
      addPart(ring, eyeFaces, eyeRim);
      const inner = ring.map(p => [eyeX + (p[0] - eyeX) * .76, eyeY + (p[1] - eyeY) * .76, p[2] + sign * .003]);
      addPart(inner, eyeFaces, dark);
      // A short dark gill crease and a restrained mouth slit, with no teeth.
      addPart([
        [.20 * L, H * .29, sign * W * .92], [.17 * L, -H * .27, sign * W * .96],
        [.174 * L, -H * .26, sign * W * .965], [.204 * L, H * .28, sign * W * .925],
      ], sign === 1 ? [[0, 1, 2], [0, 2, 3]] : [[0, 2, 1], [0, 3, 2]], gillPigment);
      addPart([
        [.476 * L, -.010, sign * W * .30], [.540 * L, -.007, sign * W * .06],
        [.476 * L, -.014, sign * W * .29],
      ], sign === 1 ? [[0, 1, 2]] : [[0, 2, 1]], dark);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setIndex(indices); geometry.computeVertexNormals();
    // Duplicated UV seam vertices share a smooth normal, avoiding a hard line.
    const templateNormals = geometry.attributes.normal.array;
    for (let r = 0; r < rings.length; r++) {
      const start = r * ringStride * 3, end = (r * ringStride + sides) * 3;
      const nx = templateNormals[start] + templateNormals[end];
      const ny = templateNormals[start + 1] + templateNormals[end + 1];
      const nz = templateNormals[start + 2] + templateNormals[end + 2];
      const length = Math.hypot(nx, ny, nz) || 1;
      for (const index of [start, end]) {
        templateNormals[index] = nx / length;
        templateNormals[index + 1] = ny / length;
        templateNormals[index + 2] = nz / length;
      }
    }
    const template = {
      positions: Float32Array.from(positions), normals: geometry.attributes.normal.array.slice(),
      colors: Float32Array.from(colors), indices, flutter: Float32Array.from(flutter),
      uvs: Float32Array.from(uvs),
      vertexCount: positions.length / 3, triangles: indices.length / 3, spec,
    };
    geometry.dispose(); return template;
  }
  const templates = species.map(makeTemplate);
  const roots = {}, schools = [], fishPerSchool = 26;
  const localBounds = {};
  for (let groupIndex = 0; groupIndex < 12; groupIndex++) {
    const template = templates[groupIndex % templates.length];
    const random = randomFor(703913 + groupIndex * 4909);
    const fish = [], centres = [];
    const totalVertices = template.vertexCount * fishPerSchool;
    const positions = new Float32Array(totalVertices * 3), normals = new Float32Array(totalVertices * 3);
    const colors = new Float32Array(totalVertices * 3), uvs = new Float32Array(totalVertices * 2), indices = [];
    // Rejection-spaced ellipsoidal clusters have a tapered nose and loose rear;
    // neither a rigid lattice nor an unbounded stochastic simulation.
    for (let i = 0; i < fishPerSchool; i++) {
      let centre, accepted = false;
      for (let attempt = 0; attempt < 2000; attempt++) {
        const x = -4.65 + random() * 8.5;
        const taper = .34 + .66 * Math.sqrt(Math.max(0, 1 - ((x + .40) / 4.65) ** 2));
        const y = (random() - .5) * 3.1 * taper;
        const z = (random() - .5) * 5.8 * taper;
        centre = [x, y + .12 * Math.sin(x * .65), z];
        if (centres.every(p => Math.hypot(p[0] - x, p[1] - centre[1], p[2] - z) > template.spec.length * .88)) {
          accepted = true; break;
        }
      }
      if (!accepted) throw new Error('Failed to construct a coherently spaced shoal.');
      centres.push(centre);
      const scale = .84 + random() * .29;
      const phase = random() * TAU;
      const cycles = 139 + Math.floor(random() * 26);
      const shade = .92 + random() * .13;
      const record = {
        centre, scale, phase, cycles, slow: 2 + Math.floor(random() * 3),
        vertexOffset: i * template.vertexCount,
        radius: template.spec.length * scale * .80,
        heading: (random() - .5) * .08, bank: (random() - .5) * .09,
        localCentre: [0, 0, 0],
      };
      fish.push(record);
      uvs.set(template.uvs, record.vertexOffset * 2);
      for (let vertex = 0; vertex < template.vertexCount; vertex++) {
        const source = vertex * 3, target = (record.vertexOffset + vertex) * 3;
        colors[target] = template.colors[source] * shade;
        colors[target + 1] = template.colors[source + 1] * shade;
        colors[target + 2] = template.colors[source + 2] * shade;
      }
      for (const index of template.indices) indices.push(record.vertexOffset + index);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3).setUsage(THREE.DynamicDrawUsage));
    geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3).setUsage(THREE.DynamicDrawUsage));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3)); geometry.setIndex(indices);
    geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = `Living ${template.spec.name} school (${fishPerSchool} fish)`;
    const root = new THREE.Group(), name = `shoal${String(groupIndex + 1).padStart(2, '0')}`;
    root.name = mesh.name; root.add(mesh); roots[name] = root;
    schools.push({ name, root, mesh, geometry, template, fish, groupIndex });
    // Includes all possible local shifts, flex, orientation and size changes.
    const bound = new THREE.Box3();
    for (const record of fish) {
      const centre = new THREE.Vector3(...record.centre);
      const radius = record.radius + .31;
      bound.expandByPoint(centre.clone().addScalar(radius));
      bound.expandByPoint(centre.clone().addScalar(-radius));
    }
    geometry.boundingBox = bound.clone();
    const sphere = new THREE.Sphere(); bound.getBoundingSphere(sphere); geometry.boundingSphere = sphere;
    localBounds[name] = { min: bound.min.toArray(), max: bound.max.toArray() };
  }

  function update(t) {
    if (!Number.isFinite(t)) throw new Error('A finite scene time in seconds is required.');
    const a = wrap(t) / duration * TAU;
    for (const school of schools) {
      const { geometry, template } = school;
      const p = geometry.attributes.position.array, n = geometry.attributes.normal.array;
      const rest = template.positions, restNormal = template.normals;
      const L = template.spec.length;
      for (const fish of school.fish) {
        const slow = a * fish.slow + fish.phase;
        const bodyPhase = a * fish.cycles + fish.phase;
        const cx = fish.centre[0] + .12 * Math.sin(slow);
        const cy = fish.centre[1] + .09 * Math.sin(slow + .7);
        const cz = fish.centre[2] + .13 * Math.cos(slow + .3);
        fish.localCentre[0] = cx; fish.localCentre[1] = cy; fish.localCentre[2] = cz;
        const yaw = fish.heading + .05 * Math.sin(slow + 1.3);
        const pitch = .035 * Math.cos(slow + .8);
        const roll = fish.bank + .085 * Math.sin(slow + .5);
        const sy = Math.sin(yaw), cyaw = Math.cos(yaw), sp = Math.sin(pitch), cp = Math.cos(pitch);
        const sr = Math.sin(roll), cr = Math.cos(roll);
        // R_yaw * R_pitch * R_roll, reused for every vertex of this fish.
        const r00 = cyaw * cp, r01 = -cyaw * sp * cr + sy * sr, r02 = cyaw * sp * sr + sy * cr;
        const r10 = sp, r11 = cp * cr, r12 = -cp * sr;
        const r20 = -sy * cp, r21 = sy * sp * cr + cyaw * sr, r22 = -sy * sp * sr + cyaw * cr;
        for (let vertex = 0; vertex < template.vertexCount; vertex++) {
          const source = vertex * 3, target = (fish.vertexOffset + vertex) * 3;
          const x = rest[source], y0 = rest[source + 1], z0 = rest[source + 2];
          const u = clamp((.30 * L - x) / (1.10 * L));
          const wave = bodyPhase - x / L * 3.8;
          const amplitude = .049 * L;
          const bend = amplitude * u * u * Math.sin(wave);
          const derivative = amplitude * (
            -2 * u / (1.10 * L) * Math.sin(wave) - u * u * 3.8 / L * Math.cos(wave)
          ) * (u > 0 && u < 1 ? 1 : u >= 1 ? 1 : 0);
          const x1 = x * fish.scale;
          const y1 = (y0 + template.flutter[vertex] * Math.sin(bodyPhase * 2 + .4)) * fish.scale;
          const z1 = (z0 + bend) * fish.scale;
          p[target] = cx + r00 * x1 + r01 * y1 + r02 * z1;
          p[target + 1] = cy + r10 * x1 + r11 * y1 + r12 * z1;
          p[target + 2] = cz + r20 * x1 + r21 * y1 + r22 * z1;
          // Inverse-transpose of the tail shear, followed by the rigid pose.
          let nx = restNormal[source] - derivative * restNormal[source + 2];
          let ny = restNormal[source + 1], nz = restNormal[source + 2];
          const inverseLength = 1 / (Math.hypot(nx, ny, nz) || 1);
          nx *= inverseLength; ny *= inverseLength; nz *= inverseLength;
          n[target] = r00 * nx + r01 * ny + r02 * nz;
          n[target + 1] = r10 * nx + r11 * ny + r12 * nz;
          n[target + 2] = r20 * nx + r21 * ny + r22 * nz;
        }
      }
      geometry.attributes.position.needsUpdate = true;
      geometry.attributes.normal.needsUpdate = true;
    }
  }
  function layout(t) {
    if (t !== undefined) update(t);
    return Object.fromEntries(schools.map(school => [school.name, school.fish.map((fish, index) => ({
      index, centre: fish.localCentre.slice(), radius: fish.radius,
    }))]));
  }
  const triangles = schools.reduce((sum, school) => sum + school.geometry.index.count / 3, 0);
  if (triangles > 95000) throw new Error('Shoal triangle budget exceeded.');
  update(0);
  const summary = {
    groups: schools.length, individuals: schools.length * fishPerSchool, fish_per_group: fishPerSchool,
    triangles, species: species.map(spec => spec.name), local_bounds: localBounds,
    original_geometry: true, ordinary_merged_meshes: true, loop_duration_seconds: duration,
    subtle_original_procedural_scale_texture: true,
    actual_vertices_are_animated: true, all_individuals_are_not_always_visible: true,
    animation: 'Independent body/tail waves, pectoral motion, slow bank and heading variation; deterministic periodic sampling.',
  };
  return { roots, update, layout, summary };
}
