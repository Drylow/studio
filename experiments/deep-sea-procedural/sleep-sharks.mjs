/**
 * Original sleeper-shark silhouettes. Ordinary CPU-deformed meshes keep the
 * actual animated surface available to lighting, bounds and collision checks.
 * Y is up; the snout points along +X. No placement or external assets here.
 */
export function createSleepSharks(THREE, { duration = 300 } = {}) {
  if (!Number.isFinite(duration) || duration <= 0) throw new Error('Loop duration must be positive finite seconds.');
  const TAU = Math.PI * 2;
  const wrap = t => ((t % duration) + duration) % duration;
  const clamp = (x, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, x));
  const material = new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: false });
  material.name = 'Original smooth slate shark skin';
  const sharks = [];

  // A rounded, broad sleeper-like snout and long tapering tail peduncle. Rings
  // are interpolated before meshing, so the side profile stays gently curved.
  const sections = [
    [-3.28, .025, .105, .105], [-2.89, .045, .165, .150],
    [-2.34, .095, .255, .235], [-1.74, .125, .365, .335],
    [-1.05, .145, .475, .440], [-.25, .125, .550, .500],
    [.50, .075, .565, .535], [1.12, .020, .520, .495],
    [1.65, -.050, .405, .405], [2.06, -.115, .265, .300],
    [2.37, -.150, .140, .200], [2.53, -.158, .040, .070],
    [2.57, -.158, .006, .008],
  ];
  function profile(x) {
    let a = 0;
    while (a < sections.length - 2 && x > sections[a + 1][0]) a++;
    const first = sections[a], second = sections[a + 1];
    const u = clamp((x - first[0]) / (second[0] - first[0]));
    const before = sections[Math.max(0, a - 1)], after = sections[Math.min(sections.length - 1, a + 2)];
    const out = [x];
    for (let j = 1; j < 4; j++) {
      // Cubic Hermite tangents respect the nonuniform longitudinal spacing.
      const span = second[0] - first[0];
      const m0 = (second[j] - before[j]) / (second[0] - before[0]) * span;
      const m1 = (after[j] - first[j]) / (after[0] - first[0]) * span;
      out.push((2*u*u*u - 3*u*u + 1)*first[j] + (u*u*u - 2*u*u + u)*m0
        + (-2*u*u*u + 3*u*u)*second[j] + (u*u*u - u*u)*m1);
    }
    return out;
  }
  function geometry(points, faces) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(points.flat(), 3));
    g.setIndex(faces.flat()); g.computeVertexNormals(); return g;
  }
  function bodyGeometry() {
    const p = [], f = [], rows = 36, sides = 20;
    for (let r = 0; r <= rows; r++) {
      const x = sections[0][0] + (sections.at(-1)[0] - sections[0][0]) * r / rows;
      const [, center, ry, rz] = profile(x);
      for (let s = 0; s < sides; s++) {
        const a = s / sides * TAU;
        p.push([x, center + Math.cos(a) * ry, Math.sin(a) * rz]);
      }
    }
    for (let r = 0; r < rows; r++) for (let s = 0; s < sides; s++) {
      const a = r * sides + s, b = r * sides + (s + 1) % sides;
      f.push([a, b, a + sides], [b, b + sides, a + sides]);
    }
    const back = p.length; p.push([sections[0][0], sections[0][1], 0]);
    const front = p.length; p.push([sections.at(-1)[0], sections.at(-1)[1], 0]);
    for (let s = 0; s < sides; s++) {
      f.push([back, (s + 1) % sides, s]);
      const a = rows * sides + s, b = rows * sides + (s + 1) % sides;
      f.push([front, a, b]);
    }
    return geometry(p, f);
  }

  // A gently domed double-sided fin with a continuous curved perimeter. The
  // cross-section tapers at every edge; no broad flat triangular billboard.
  function finGeometry(outline, thickness = .042) {
    const curve = new THREE.CatmullRomCurve3(outline.map(p => new THREE.Vector3(...p)), true, 'centripetal');
    const edge = curve.getPoints(24).slice(0, -1), center = new THREE.Vector3();
    for (const p of edge) center.add(p); center.multiplyScalar(1 / edge.length);
    const normal = new THREE.Vector3();
    for (let i = 0; i < edge.length; i++) normal.add(new THREE.Vector3().subVectors(edge[i],center)
      .cross(new THREE.Vector3().subVectors(edge[(i+1)%edge.length],center)));
    normal.normalize();
    const points = [], faces = [], layers = 3, sides = edge.length;
    for (const sign of [-1, 1]) {
      points.push(center.clone().addScaledVector(normal, sign * thickness).toArray());
      const pole = points.length - 1, start = points.length;
      for (let layer = 1; layer <= layers; layer++) {
        const u = layer / layers;
        for (const e of edge) points.push(center.clone().lerp(e, u)
          .addScaledVector(normal, sign * thickness * Math.sin(Math.PI * u / 2 + Math.PI / 2)).toArray());
      }
      for (let s = 0; s < sides; s++) {
        const a = start + s, b = start + (s + 1) % sides;
        faces.push(sign === 1 ? [pole, a, b] : [pole, b, a]);
      }
      for (let layer = 0; layer < layers - 1; layer++) for (let s = 0; s < sides; s++) {
        const a = start + layer * sides + s, b = start + layer * sides + (s + 1) % sides;
        const tris = [[a, a + sides, b], [b, a + sides, b + sides]];
        for (const tri of tris) faces.push(sign === 1 ? tri : tri.toReversed());
      }
    }
    return geometry(points, faces);
  }
  function stroke(points, radius = .013, segments = 12) {
    const curve = new THREE.CatmullRomCurve3(points.map(p => new THREE.Vector3(...p)), false, 'centripetal');
    return new THREE.TubeGeometry(curve, segments, radius, 5, false);
  }
  function makeShark(name, { scale, mass, dorsal, belly, phase, cycles }) {
    const root = new THREE.Group(); root.name = name;
    const pieces = [];
    const top = new THREE.Color(dorsal), bottom = new THREE.Color(belly);
    function append(g, color = null, part = 'body') {
      const p = g.attributes.position.array, colors = new Float32Array(p.length);
      const fixed = color && new THREE.Color(color);
      for (let i = 0; i < p.length; i += 3) {
        const x = p[i], y = p[i + 1], z = p[i + 2];
        const [, cy, radius] = profile(clamp(x, sections[0][0], sections.at(-1)[0]));
        const ventral = clamp((cy - y) / Math.max(.12, radius) * .68 + .20);
        const c = fixed || top.clone().lerp(bottom, ventral * ventral * (3 - 2 * ventral));
        const pigment = .965 + .022 * Math.sin(x * 3.1 + z * 2.2) + .014 * Math.cos(x * 5.2 - z * 3.5);
        colors[i] = c.r * pigment; colors[i + 1] = c.g * pigment; colors[i + 2] = c.b * pigment;
        p[i] *= scale; p[i + 1] *= scale * mass; p[i + 2] *= scale * mass;
      }
      g.setAttribute('color', new THREE.BufferAttribute(colors, 3));
      g.computeVertexNormals(); pieces.push({ geometry: g, part });
    }
    append(bodyGeometry());
    append(finGeometry([
      [-1.08,.51,0], [-.62,.98,0], [-.37,1.37,0], [-.04,1.07,0],
      [.38,.64,0], [.29,.59,0], [-.14,.62,0], [-.69,.56,0],
    ], .055), dorsal, 'dorsal');
    append(finGeometry([
      [-2.58,.18,0], [-2.35,.54,0], [-2.19,.70,0], [-1.93,.38,0],
      [-1.77,.27,0], [-2.09,.30,0],
    ], .026), dorsal, 'second dorsal');
    for (const side of [-1, 1]) {
      append(finGeometry([
        [.45,-.12,side*.43], [.03,-.20,side*.80], [-.75,-.39,side*1.37],
        [-1.20,-.46,side*1.45], [-.92,-.42,side*1.07], [-.78,-.27,side*.50],
      ].map(p => p), .040), '#60747a', 'pectoral');
      append(finGeometry([
        [-1.75,-.12,side*.25], [-2.03,-.25,side*.54], [-2.45,-.28,side*.63],
        [-2.55,-.19,side*.48], [-2.10,-.08,side*.23],
      ], .024), '#738183', 'pelvic');
      const eye = new THREE.SphereGeometry(.080, 12, 8);
      eye.scale(1, .88, .42); eye.translate(1.85, .079, side*.366);
      append(eye, '#101f22', 'eye');
      // One tiny matte rim keeps the eye readable without a cartoon eyeball.
      const rim = new THREE.SphereGeometry(.021, 8, 5);
      rim.scale(1, .75, .36); rim.translate(1.867, .099, side*.396);
      append(rim, '#54696a', 'eye rim');
      const nostril = new THREE.SphereGeometry(.028, 8, 5);
      nostril.scale(.90, .42, .38); nostril.translate(2.255,-.13,side*.241);
      append(nostril, '#243438', 'nostril');
      for (let gill = 0; gill < 5; gill++) {
        const x = .20 + gill*.177, points = [];
        for (let row = 0; row <= 7; row++) {
          const a = .35*Math.PI + row/7*.44*Math.PI;
          const xx = x - Math.sin(row/7*Math.PI)*.041;
          const [, cy, ry, rz] = profile(xx);
          points.push([xx, cy + Math.cos(a)*ry*1.013, side*Math.sin(a)*rz*1.013]);
        }
        append(stroke(points,.012,9),'#2d4046','gill slit');
      }
    }
    const mouth = [];
    for (let i = 0; i <= 10; i++) {
      const z = (i/10-.5)*.44, x = 2.27 - .19*Math.pow(Math.abs(z)/.22,1.3);
      mouth.push([x,-.321 + .030*Math.pow(z/.22,2),z]);
    }
    append(stroke(mouth,.011,15),'#263b3d','closed ventral mouth');
    // Upper tail lobe is deliberately larger: the defining shark silhouette.
    append(finGeometry([
      [-3.13,.02,0], [-3.47,.47,0], [-4.11,1.19,0], [-4.50,1.36,0],
      [-4.39,.98,0], [-4.03,.40,0], [-3.72,.10,0], [-4.13,-.56,0],
      [-4.02,-.77,0], [-3.63,-.46,0], [-3.25,-.10,0],
    ], .033), dorsal, 'asymmetric caudal');

    let vertices = 0, indices = 0;
    for (const { geometry: g } of pieces) { vertices += g.attributes.position.count; indices += g.index.count; }
    const positions = new Float32Array(vertices*3), colors = new Float32Array(vertices*3), index = new Uint32Array(indices);
    let v = 0, f = 0;
    for (const { geometry: g } of pieces) {
      positions.set(g.attributes.position.array, v*3); colors.set(g.attributes.color.array,v*3);
      for (const n of g.index.array) index[f++] = n+v;
      v += g.attributes.position.count; g.dispose();
    }
    const merged = new THREE.BufferGeometry();
    merged.setAttribute('position',new THREE.BufferAttribute(positions,3).setUsage(THREE.DynamicDrawUsage));
    merged.setAttribute('color',new THREE.BufferAttribute(colors,3)); merged.setIndex(new THREE.BufferAttribute(index,1));
    merged.computeVertexNormals();
    const rest = positions.slice(); merged.userData.rest = rest;
    merged.computeBoundingSphere(); merged.boundingSphere.radius += .5;
    const mesh = new THREE.Mesh(merged,material);
    mesh.name = `${name}: rounded body, five gills per side and asymmetrical tail`; root.add(mesh);
    sharks.push({root,mesh,rest,scale,mass,phase,cycles}); return root;
  }
  const roots = {
    shark1: makeShark('shark1',{scale:1,mass:1,dorsal:'#526771',belly:'#9ba79e',phase:.35,cycles:55}),
    shark2: makeShark('shark2',{scale:.86,mass:1.10,dorsal:'#455962',belly:'#919e95',phase:2.39,cycles:62}),
    shark3: makeShark('shark3',{scale:.74,mass:.92,dorsal:'#5c7179',belly:'#a3aea1',phase:4.55,cycles:68}),
  };
  function update(time) {
    if (!Number.isFinite(time)) throw new Error('Shark seek time must be finite.');
    const t = wrap(time);
    for (const {mesh,rest,scale,mass,phase,cycles} of sharks) {
      const p = mesh.geometry.attributes.position.array;
      const cycle = t/duration*TAU*cycles + phase;
      const finCycle = t/duration*TAU*(cycles-7) + phase;
      for (let i = 0; i < p.length; i += 3) {
        const x = rest[i]/scale, y = rest[i+1]/(scale*mass), z = rest[i+2]/(scale*mass);
        const tailWeight = Math.pow(clamp((1.45-x)/5.95),2.05);
        const bend = (.010 + tailWeight*.34)*Math.sin(cycle+x*.79);
        const finWeight = clamp((Math.abs(z)-.51)/.95);
        const finLift = finWeight*.055*Math.sin(finCycle + x*.61 + Math.sign(z)*.30);
        p[i] = rest[i];
        p[i+1] = rest[i+1] + scale*(.014*Math.sin(t/duration*TAU*13+phase+x*.24) + finLift);
        p[i+2] = rest[i+2] + scale*bend;
      }
      mesh.geometry.attributes.position.needsUpdate = true;
      mesh.geometry.computeVertexNormals();
      mesh.geometry.computeBoundingBox();
    }
  }
  update(0);
  const localBounds = {};
  for (const {root,scale,mass} of sharks) localBounds[root.name] = {
    min:[-4.61*scale,-.85*scale*mass,-1.65*scale*mass],
    max:[2.59*scale,1.47*scale*mass,1.65*scale*mass],
  };
  const summary = {
    duration, sharkCount:sharks.length, meshCount:sharks.length,
    triangleCount:sharks.reduce((n,{mesh})=>n+mesh.geometry.index.count/3,0),
    coordinateSystem:'Y-up; snout points +X', localBounds,
    principalPeriodsSeconds:sharks.map(({root,cycles})=>({name:root.name,tail:duration/cycles,fin:duration/(cycles-7)})),
    claims:'Original illustrative sleeper/lantern shark-inspired geometry; no external models, textures or generation calls',
  };
  return {roots,update,summary};
}
