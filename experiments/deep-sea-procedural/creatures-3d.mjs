/**
 * Original matte marine meshes, Y-up and +X forward. No borrowed game assets.
 * Mesh deformation and appendages are deterministic functions of seconds.
 */
export function createCreatures(THREE) {
  const TAU = Math.PI * 2;
  const matte = new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: true });
  const parts = [];
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const fragment = (geometry, color, position = [0, 0, 0], scale = [1, 1, 1], rotation = [0, 0, 0]) => {
    const g = geometry.index ? geometry.toNonIndexed() : geometry.clone();
    g.applyMatrix4(new THREE.Matrix4().compose(new THREE.Vector3(...position),
      new THREE.Quaternion().setFromEuler(new THREE.Euler(...rotation)), new THREE.Vector3(...scale)));
    g.computeVertexNormals();
    const base = new THREE.Color(color), rgb = new Float32Array(g.attributes.position.count * 3);
    const p = g.attributes.position.array;
    for (let i = 0; i < g.attributes.position.count; i++) {
      // Quiet contiguous pigment bands rather than random triangle colors.
      const shade = .91 + .055 * Math.sin(p[i * 3] * .88 + p[i * 3 + 2] * .43)
        - .055 * clamp(p[i * 3 + 1], -1, 1);
      rgb[i * 3] = base.r * shade; rgb[i * 3 + 1] = base.g * shade; rgb[i * 3 + 2] = base.b * shade;
    }
    g.setAttribute('color', new THREE.BufferAttribute(rgb, 3)); parts.push(g); geometry.dispose();
  };
  function mesh(parent, name = 'Original marine mesh') {
    let size = 0; for (const g of parts) size += g.attributes.position.array.length;
    const p = new Float32Array(size), n = new Float32Array(size), c = new Float32Array(size);
    let offset = 0;
    for (const g of parts) {
      p.set(g.attributes.position.array, offset); n.set(g.attributes.normal.array, offset);
      c.set(g.attributes.color.array, offset); offset += g.attributes.position.array.length; g.dispose();
    }
    parts.length = 0;
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(p, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('normal', new THREE.BufferAttribute(n, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('color', new THREE.BufferAttribute(c, 3));
    g.userData.rest = p.slice(); g.computeBoundingSphere(); g.boundingSphere.radius += .8;
    const m = new THREE.Mesh(g, matte); m.name = name; parent.add(m); return m;
  }
  function geometry(points, faces) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(points.flat(), 3));
    g.setIndex(faces.flat()); g.computeVertexNormals(); return g;
  }
  function loft(rings, segments = 12, frontCap = false) {
    const points = [], faces = [];
    for (let r = 0; r < rings.length; r++) {
      const [x, y, ry, rz] = rings[r];
      for (let j = 0; j < segments; j++) {
        const a = j / segments * TAU;
        const uneven = 1 + .025 * Math.sin(j * 2.1 + r * .87);
        points.push([x, y + Math.cos(a) * ry * uneven, Math.sin(a) * rz * uneven]);
      }
    }
    for (let r = 0; r < rings.length - 1; r++) for (let j = 0; j < segments; j++) {
      const a = r * segments + j, b = r * segments + (j + 1) % segments;
      faces.push([a, b, a + segments], [b, b + segments, a + segments]);
    }
    const cap = (ring, reverse) => {
      const id = points.length; points.push([rings[ring][0], rings[ring][1], 0]);
      for (let j = 0; j < segments; j++) {
        const a = ring * segments + j, b = ring * segments + (j + 1) % segments;
        faces.push(reverse ? [id, a, b] : [id, b, a]);
      }
    };
    cap(0, false); if (frontCap) cap(rings.length - 1, true);
    return geometry(points, faces);
  }
  function fan(points, thickness = .012) {
    const vertices = [], faces = [];
    for (const z of [-thickness, thickness]) for (const [x, y] of points) vertices.push([x, y, z]);
    const count = points.length;
    for (let i = 1; i < count - 1; i++) faces.push([0, i + 1, i], [count, count + i, count + i + 1]);
    for (let i = 0; i < count; i++) {
      const next = (i + 1) % count; faces.push([i, next, i + count], [next, next + count, i + count]);
    }
    return geometry(vertices, faces);
  }
  function deform(m, fn) {
    const g = m.geometry, p = g.attributes.position.array, base = g.userData.rest;
    for (let i = 0; i < p.length; i += 3) fn(p, i, base[i], base[i + 1], base[i + 2]);
    g.attributes.position.needsUpdate = true; g.computeVertexNormals();
  }

  const angler = new THREE.Group();
  angler.name = 'Original angular anglerfish, recessed eyes and living body wave';
  // Compressed upper skull, tapered abdomen, a sloping rather than circular gape.
  fragment(loft([
    [-2.68, -.04, .12, .11], [-2.10, .01, .29, .26], [-1.43, .13, .51, .46],
    [-.62, .14, .80, .66], [.19, .16, .91, .75], [.86, .08, .77, .73],
    [1.47, -.09, .59, .63], [1.87, -.15, .43, .52],
  ], 14), '#4f5b4e');
  fragment(loft([[1.87, -.15, .425, .515], [1.36, -.18, .34, .42], [1.08, -.16, .01, .01]], 14, true), '#172621');
  fragment(new THREE.IcosahedronGeometry(1, 1), '#485247', [.89, .46, 0], [.63, .20, .59], [0, 0, -.13]);
  for (const side of [-1, 1]) {
    const z = side * .63;
    fragment(new THREE.IcosahedronGeometry(1, 1), '#354238', [.74, .32, z], [.21, .15, .09]);
    fragment(new THREE.IcosahedronGeometry(1, 1), '#101c19', [.80, .33, z + side * .055], [.089, .092, .063]);
    fragment(new THREE.IcosahedronGeometry(1, 0), '#647366', [.823, .36, z + side * .113], [.018, .016, .009]);
    fragment(new THREE.IcosahedronGeometry(1, 0), '#263b31', [-.49, -.07, side * .649], [.065, .32, .013], [0, 0, .13]);
  }
  for (let i = 0; i < 11; i++) {
    const a = -1.16 + i * .232, z = Math.sin(a) * .46, top = -.15 + Math.cos(a) * .38;
    const length = .135 + .115 * (.5 + .5 * Math.sin(i * 2.61));
    fragment(new THREE.ConeGeometry(.018 + .004 * (i % 3), length, 4), '#9eaa88',
      [1.79 - .08 * Math.abs(Math.sin(a)), top - length * .47, z], [1, 1, 1], [.08 * Math.sin(i), 0, Math.PI + .13 * Math.sin(i * 1.7)]);
  }
  const body = mesh(angler, 'Asymmetrical charcoal olive body with restrained teeth');

  const jaw = new THREE.Group(); jaw.position.set(.84, -.48, 0); angler.add(jaw);
  fragment(loft([[-.03, -.01, .10, .46], [.47, -.07, .135, .59], [.98, -.04, .07, .50], [1.18, .015, .035, .33]], 10, true), '#4f5b48');
  for (let i = 0; i < 9; i++) {
    const z = (i - 4) * .105, length = .11 + .085 * (.5 + .5 * Math.cos(i * 2.03));
    fragment(new THREE.ConeGeometry(.017, length, 4), '#929d7b', [.91 - .11 * Math.abs(z), .015 + length * .45, z], [1, 1, 1], [0, 0, -.1 * Math.cos(i)]);
  }
  mesh(jaw, 'Living narrow lower jaw');

  const tail = new THREE.Group(); tail.position.set(-2.55, -.035, 0); angler.add(tail);
  fragment(loft([[.1, 0, .15, .12], [-.51, 0, .085, .046]], 8, true), '#405047');
  fragment(fan([[0, 0], [-.27, .15], [-.82, .55], [-1.11, .49], [-.97, .14], [-1.04, -.21], [-1.03, -.50], [-.71, -.51], [-.27, -.13]]), '#45564a', [-.39, 0, 0]);
  const tailMesh = mesh(tail, 'Flexible tapered caudal fan');

  const dorsal = new THREE.Group(); dorsal.position.set(-.1, .86, 0); angler.add(dorsal);
  fragment(fan([[0, 0], [-.23, .25], [-.57, .31], [-.92, .30], [-1.24, .23], [-1.53, .09], [-1.69, -.11]]), '#38483f');
  const dorsalMesh = mesh(dorsal, 'Soft dorsal membrane');
  const pectorals = [], gills = [];
  for (const side of [-1, 1]) {
    const fin = new THREE.Group(); fin.position.set(-.61, -.20, side * .57); angler.add(fin);
    fragment(fan([[0, 0], [-.22, .22], [-.66, .30], [-1.13, .20], [-1.25, -.02], [-.98, -.18], [-.37, -.10]], .011), '#576653',
      [0, 0, 0], [1, 1, 1], [side * 1.04, 0, -.08]);
    pectorals.push({ group: fin, mesh: mesh(fin, 'Fluttering ray-shaped pectoral membrane'), side });
    const gill = new THREE.Group(); gill.position.set(-.34, -.01, side * .62); angler.add(gill);
    fragment(new THREE.IcosahedronGeometry(1, 1), '#4a594a', [0, 0, 0], [.15, .33, .045], [0, 0, -.12]);
    mesh(gill, 'Breathing opercular flap'); gills.push({ group: gill, side });
  }

  const lureBase = [.30, .99, 0], lureSegments = 17, lureSides = 5;
  const lurePoints = [], lureFaces = [];
  for (let row = 0; row <= lureSegments; row++) for (let side = 0; side < lureSides; side++) lurePoints.push([0, 0, 0]);
  for (let row = 0; row < lureSegments; row++) for (let side = 0; side < lureSides; side++) {
    const a = row * lureSides + side, b = row * lureSides + (side + 1) % lureSides;
    lureFaces.push([a, b, a + lureSides], [b, b + lureSides, a + lureSides]);
  }
  fragment(geometry(lurePoints, lureFaces), '#50644e');
  const lure = mesh(angler, 'Flexible continuous lure stalk');
  const lightMaterial = new THREE.MeshBasicMaterial({ color: '#c9dbc4', toneMapped: false });
  const lureTip = new THREE.Mesh(new THREE.IcosahedronGeometry(.078, 2), lightMaterial); angler.add(lureTip);
  function lureCenter(u, t) {
    const a = u * Math.PI * .94;
    return [lureBase[0] + Math.sin(a * .59) * 1.55 + u * u * .065 * Math.sin(t * 1.09),
      lureBase[1] + Math.sin(a) * 1.00 + u * u * .035 * Math.cos(t * 1.27),
      .025 * Math.sin(t * 1.53) + Math.sin(u * 3.1 - t * 1.33) * u * .095];
  }
  function updateLure(t) {
    const g = lure.geometry, p = g.attributes.position.array;
    let index = 0;
    for (const face of lureFaces) for (const vertex of face) {
      const row = Math.floor(vertex / lureSides), side = vertex % lureSides, u = row / lureSegments;
      const center = lureCenter(u, t), next = lureCenter(Math.min(1, u + .015), t), previous = lureCenter(Math.max(0, u - .015), t);
      const dx = next[0] - previous[0], dy = next[1] - previous[1], length = Math.hypot(dx, dy) || 1;
      const a = side / lureSides * TAU, radius = .024 * (1 - u * .45);
      p[index++] = center[0] - dy / length * Math.cos(a) * radius;
      p[index++] = center[1] + dx / length * Math.cos(a) * radius;
      p[index++] = center[2] + Math.sin(a) * radius;
    }
    g.attributes.position.needsUpdate = true; g.computeVertexNormals();
    g.boundingSphere = new THREE.Sphere(new THREE.Vector3(1.1, 1.5, 0), 1.7);
    lureTip.position.set(...lureCenter(1, t));
  }

  const jelly = new THREE.Group(); jelly.name = 'Original phantom jelly, contracting bell and four delayed oral arms';
  const bell = new THREE.Group(); jelly.add(bell);
  const bellRings = [[1.19, .07], [1.15, .38], [.98, .78], [.67, 1.08], [.30, 1.21], [.01, 1.16], [-.07, .94]], bellSegments = 18;
  const bp = [], bf = [];
  for (let row = 0; row < bellRings.length; row++) for (let i = 0; i < bellSegments; i++) {
    const a = i / bellSegments * TAU, [y, r] = bellRings[row];
    bp.push([Math.cos(a) * r, y + (row > 4 ? .032 * Math.cos(a * 6) : 0), Math.sin(a) * r]);
  }
  for (let row = 0; row < bellRings.length - 1; row++) for (let i = 0; i < bellSegments; i++) {
    const a = row * bellSegments + i, b = row * bellSegments + (i + 1) % bellSegments;
    bf.push([a, b, a + bellSegments], [b, b + bellSegments, a + bellSegments]);
  }
  bp.push([0, 1.20, 0]); const top = bp.length - 1;
  for (let i = 0; i < bellSegments; i++) bf.push([top, (i + 1) % bellSegments, i]);
  fragment(geometry(bp, bf), '#645053');
  fragment(new THREE.IcosahedronGeometry(1, 1), '#382f32', [0, .18, 0], [.64, .30, .64]);
  const bellMesh = mesh(bell, 'Rhythmic flattened jelly bell');
  const sections = 26, rp = [], rc = [], ri = [], ribbonColor = new THREE.Color('#715953');
  for (let arm = 0; arm < 4; arm++) {
    const base = arm * (sections + 1) * 4;
    for (let row = 0; row <= sections; row++) for (let corner = 0; corner < 4; corner++) {
      rp.push(0, 0, 0); const shade = .85 + .10 * Math.sin(row * .39 + arm) + (corner % 3 === 0 ? .04 : 0);
      rc.push(ribbonColor.r * shade, ribbonColor.g * shade, ribbonColor.b * shade);
    }
    for (let row = 0; row < sections; row++) for (let edge = 0; edge < 4; edge++) {
      const a = base + row * 4 + edge, b = base + row * 4 + (edge + 1) % 4;
      ri.push(a, a + 4, b, b, a + 4, b + 4);
    }
    ri.push(base, base + 1, base + 2, base, base + 2, base + 3);
    const end = base + sections * 4; ri.push(end, end + 2, end + 1, end, end + 3, end + 2);
  }
  const ribbonGeometry = new THREE.BufferGeometry();
  ribbonGeometry.setAttribute('position', new THREE.Float32BufferAttribute(rp, 3).setUsage(THREE.DynamicDrawUsage));
  ribbonGeometry.setAttribute('color', new THREE.Float32BufferAttribute(rc, 3)); ribbonGeometry.setIndex(ri);
  const ribbons = new THREE.Mesh(ribbonGeometry, matte); jelly.add(ribbons);
  function pulse(t) { return Math.pow(.5 + .5 * Math.sin(t * 2.05), 2); }
  function updateJelly(t) {
    const contraction = pulse(t);
    deform(bellMesh, (p, i, x, y, z) => {
      const rim = clamp(1 - y / 1.2);
      const radial = 1.045 - contraction * (.115 + rim * .04);
      p[i] = x * radial; p[i + 1] = y * (1 + contraction * .09) - rim * contraction * .045; p[i + 2] = z * radial;
    });
    const p = ribbonGeometry.attributes.position.array;
    for (let arm = 0; arm < 4; arm++) {
      const angle = arm * TAU / 4 + Math.PI * .25, ax = Math.cos(angle), az = Math.sin(angle), tx = -az, tz = ax;
      for (let row = 0; row <= sections; row++) {
        const u = row / sections, lag = t - u * 1.32, flex = pulse(lag);
        const radius = .41 * (1.045 - contraction * .13) + .28 * u
          + Math.sin(u * 5.8 - t * 1.12 + arm * .43) * u * .24 + (flex - .5) * u * .17;
        const lateral = Math.sin(u * 7.1 - t * 1.09 + arm * 1.42) * u * .38;
        const cx = ax * radius + tx * lateral, cz = az * radius + tz * lateral;
        const cy = -.13 - u * 5.1 + Math.sin(u * 8.2 - t * 1.17 + arm) * u * .11 + (flex - .5) * u * .16;
        const width = (.26 + .22 * Math.sin(u * Math.PI * .91)) * (1 - Math.pow(u, 5) * .90);
        const twist = Math.sin(u * 6 - t * .97 + arm) * .61;
        const wx = tx * Math.cos(twist) + ax * Math.sin(twist), wz = tz * Math.cos(twist) + az * Math.sin(twist);
        for (let corner = 0; corner < 4; corner++) {
          const side = corner < 2 ? -1 : 1, depth = corner === 0 || corner === 3 ? -1 : 1;
          const i = ((arm * (sections + 1) + row) * 4 + corner) * 3, thickness = .028 * (1 - u * .8);
          p[i] = cx + wx * side * width - wz * depth * thickness;
          p[i + 1] = cy + Math.sin(u * 12 - lag * .7 + arm) * width * side * .15;
          p[i + 2] = cz + wz * side * width + wx * depth * thickness;
        }
      }
    }
    ribbonGeometry.attributes.position.needsUpdate = true; ribbonGeometry.computeVertexNormals();
    if (!ribbonGeometry.boundingSphere) ribbonGeometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, -2.5, 0), 3.8);
  }

  const fishSchool = new THREE.Group(); fishSchool.name = 'Seventeen independently flexing original shoal fish';
  const templateParent = new THREE.Group();
  fragment(loft([[-.68, 0, .033, .024], [-.44, .005, .105, .067], [-.12, .016, .19, .115], [.19, .018, .19, .12], [.43, .003, .12, .09], [.61, -.006, .025, .024]], 8, true), '#7d8f7d');
  fragment(fan([[0, 0], [-.38, .31], [-.25, .04], [-.29, -.05], [-.36, -.30]], .008), '#647b70', [-.65, 0, 0]);
  fragment(fan([[0, 0], [-.21, .19], [-.50, .08], [-.60, -.01]], .007), '#657c6a', [.08, .17, 0]);
  for (const z of [-.098, .098]) fragment(new THREE.IcosahedronGeometry(.024, 0), '#152b24', [.39, .045, z]);
  const template = mesh(templateParent), fishCount = 17, vertexCount = template.geometry.attributes.position.count;
  const schoolGeometry = new THREE.BufferGeometry(), sp = new Float32Array(vertexCount * fishCount * 3);
  const colors = new Float32Array(sp.length), templateColors = template.geometry.attributes.color.array;
  for (let i = 0; i < fishCount; i++) colors.set(templateColors, i * vertexCount * 3);
  schoolGeometry.setAttribute('position', new THREE.BufferAttribute(sp, 3).setUsage(THREE.DynamicDrawUsage));
  schoolGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  const school = new THREE.Mesh(schoolGeometry, matte); fishSchool.add(school);
  const fishRest = template.geometry.userData.rest;
  function updateSchool(t) {
    const p = schoolGeometry.attributes.position.array;
    for (let fish = 0; fish < fishCount; fish++) {
      const phase = fish * 1.971, size = .64 + .22 * (.5 + .5 * Math.sin(phase));
      const cx = (fish % 5 - 2) * 1.34 + Math.sin(t * .74 + phase) * .23;
      const cy = (Math.floor(fish / 5) - 1.5) * .64 + Math.sin(t * .59 + phase) * .12;
      const cz = (fish % 3 - 1) * 1.19 + Math.sin(t * .43 + phase) * .19;
      const heading = .04 * Math.sin(t * .71 + phase), cos = Math.cos(heading), sin = Math.sin(heading);
      for (let v = 0; v < fishRest.length; v += 3) {
        const x = fishRest[v], y = fishRest[v + 1], z = fishRest[v + 2];
        const amplitude = .11 * Math.pow(clamp((.5 - x) / 1.5), 1.45);
        const bend = amplitude * Math.sin(t * (4.3 + (fish % 3) * .33) + x * 5.2 + phase);
        const nx = x * size, nz = (z + bend) * size, i = fish * vertexCount * 3 + v;
        p[i] = cx + nx * cos - nz * sin; p[i + 1] = cy + y * size; p[i + 2] = cz + nx * sin + nz * cos;
      }
    }
    schoolGeometry.attributes.position.needsUpdate = true; schoolGeometry.computeVertexNormals();
    if (!schoolGeometry.boundingSphere) schoolGeometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 6.5);
  }
  function update(t) {
    if (!Number.isFinite(t)) throw new Error('Creature animation time must be finite seconds.');
    deform(body, (p, i, x, y, z) => {
      const rear = clamp((1.75 - x) / 4.5);
      p[i] = x; p[i + 1] = y + rear * rear * .035 * Math.sin(t * 2.1 - x * 1.8);
      p[i + 2] = z + (.019 + .205 * rear * rear) * Math.sin(t * 2.65 - x * 1.45);
    });
    const tailBend = .019 + .205 * Math.pow(clamp((1.75 + 2.55) / 4.5), 2);
    tail.position.z = tailBend * Math.sin(t * 2.65 + 2.55 * 1.45);
    tail.rotation.y = .18 * Math.cos(t * 2.65 + 2.55 * 1.45);
    deform(tailMesh, (p, i, x, y, z) => { p[i] = x; p[i + 1] = y;
      p[i + 2] = z + clamp(-x / 1.5) * .13 * Math.sin(t * 2.65 - x * 2.8 + 3.4); });
    jaw.rotation.z = -.055 - .028 * Math.sin(t * 1.44); jaw.position.z = .014 * Math.sin(t * 2.65 - .84 * 1.45);
    dorsal.position.z = .045 * Math.sin(t * 2.65 + .1 * 1.45);
    deform(dorsalMesh, (p, i, x, y, z) => { p[i] = x; p[i + 1] = y;
      p[i + 2] = z + clamp(y / .32) * .046 * Math.sin(t * 3.3 - x * 3.2); });
    for (const { group, mesh: m, side } of pectorals) {
      group.rotation.x = side * (.15 + .16 * Math.sin(t * 2.18 + side * .4));
      group.rotation.y = side * .055 * Math.sin(t * 2.18 + .7);
      deform(m, (p, i, x, y, z) => { p[i] = x; p[i + 1] = y;
        p[i + 2] = z + side * clamp(-x / 1.2) * .047 * Math.sin(t * 3.6 - x * 3.1); });
    }
    for (const { group, side } of gills) { group.rotation.y = side * (.035 + .045 * Math.sin(t * 2.42));
      group.position.z = side * (.62 + .009 * Math.sin(t * 2.42)); }
    updateLure(t); updateJelly(t); updateSchool(t);
  }
  update(0);
  return { angler, jelly, fishSchool, update };
}
