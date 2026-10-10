/* Original, procedural Canvas2D scientific illustrations. No image assets.
 * Coordinates are in CSS pixels at scale 1; time is in seconds.
 * Angler points right by default. facing: -1 or "left" mirrors a drawing.
 * These are stylized anatomical interpretations, not 3D reconstructions.
 */
(function (global) {
  "use strict";

  const TAU = Math.PI * 2;
  const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
  const finite = (n, fallback) => Number.isFinite(n) ? n : fallback;

  function polygon(points) {
    const path = new Path2D();
    path.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length; i += 1) path.lineTo(points[i][0], points[i][1]);
    path.closePath();
    return path;
  }

  function facet(ctx, points, color) {
    ctx.fillStyle = color;
    ctx.fill(polygon(points));
  }

  function stroke(ctx, points, color, width) {
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length; i += 1) ctx.lineTo(points[i][0], points[i][1]);
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();
  }

  function begin(ctx, options) {
    const o = options || {};
    const s = Math.max(0, finite(o.scale, 1));
    const a = clamp(finite(o.alpha, 1), 0, 1);
    if (!s || !a) return null;
    ctx.save();
    ctx.translate(finite(o.x, 0), finite(o.y, 0));
    ctx.scale((o.facing === "left" || o.facing < 0 ? -1 : 1) * s, s);
    ctx.globalAlpha *= a;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    return finite(o.time, 0);
  }

  const anglerBody = polygon([
    [-77, 1], [-66, -19], [-43, -33], [-15, -39], [15, -38],
    [39, -29], [59, -13], [76, 4], [80, 15], [67, 32],
    [43, 43], [13, 47], [-17, 41], [-47, 27], [-65, 13]
  ]);
  const anglerMouth = polygon([
    [58, -9], [72, -1], [79, 12], [68, 28], [47, 36],
    [35, 25], [38, 8], [47, -4]
  ]);

  /** A compact female ceratioid anglerfish, ~200 px long at scale 1.
   * Body bounds: x -121..82, y -40..51; lure reaches approximately y -87.
   */
  function drawAngler(ctx, options) {
    const time = begin(ctx, options);
    if (time === null) return;
    ctx.rotate(Math.sin(time * 0.61) * 0.018);
    const beat = Math.sin(time * 2.35);

    // The caudal peduncle moves gently; the globular head remains stable.
    ctx.save();
    ctx.translate(-63, 6);
    ctx.rotate(beat * 0.075);
    facet(ctx, [[-8, -7], [-34, -21], [-57, -22], [-52, -3], [-58, 18], [-40, 28], [-8, 8]], "#122637");
    facet(ctx, [[-10, -3], [-35, -16], [-57, -22], [-43, 0]], "#283442");
    facet(ctx, [[-10, 4], [-43, 0], [-58, 18], [-40, 28]], "#241a2b");
    facet(ctx, [[-11, 0], [-42, 6], [-40, 28], [-19, 12]], "#182030");
    stroke(ctx, [[-12, 0], [-45, -9], [-53, -19]], "rgba(83,112,127,0.35)", 0.65);
    stroke(ctx, [[-12, 3], [-40, 12], [-49, 19]], "rgba(67,79,100,0.35)", 0.65);
    ctx.restore();

    // Short dorsal and anal fins sit toward the rear of a ceratioid body.
    facet(ctx, [[-60, -21], [-58, -43], [-43, -41], [-24, -31]], "#182631");
    facet(ctx, [[-57, -40], [-42, -33], [-28, -32]], "#2b3440");
    stroke(ctx, [[-57, -40], [-49, -26]], "rgba(103,116,122,0.22)", 0.7);
    stroke(ctx, [[-47, -39], [-38, -29]], "rgba(103,116,122,0.22)", 0.7);
    facet(ctx, [[-55, 20], [-48, 47], [-29, 43], [-15, 31]], "#231c2d");
    facet(ctx, [[-50, 29], [-47, 44], [-27, 40]], "#302332");

    const skin = ctx.createLinearGradient(-35, -44, 27, 48);
    skin.addColorStop(0, "#364051");
    skin.addColorStop(0.24, "#273344");
    skin.addColorStop(0.59, "#261c30");
    skin.addColorStop(1, "#101323");
    ctx.fillStyle = skin;
    ctx.fill(anglerBody);

    ctx.save();
    ctx.clip(anglerBody);
    facet(ctx, [[-77, 1], [-43, -33], [-31, -8], [-57, 15]], "#263848");
    facet(ctx, [[-43, -33], [-15, -39], [0, -13], [-31, -8]], "#3a4252");
    facet(ctx, [[-15, -39], [15, -38], [38, -28], [13, -10], [0, -13]], "#3c3549");
    facet(ctx, [[13, -10], [38, -28], [59, -13], [47, 5]], "#493044");
    facet(ctx, [[0, -13], [13, -10], [6, 18], [-25, 22], [-31, -8]], "#2f263e");
    facet(ctx, [[-31, -8], [-25, 22], [-47, 27], [-66, 14]], "#1a2a39");
    facet(ctx, [[-25, 22], [6, 18], [13, 47], [-17, 41]], "#201b2b");
    facet(ctx, [[6, 18], [35, 10], [47, 36], [43, 43], [13, 47]], "#291526");
    facet(ctx, [[35, 10], [47, 5], [67, 17], [47, 36]], "#3b2030");
    // Sparse skin folds, not a regular decorative wireframe.
    stroke(ctx, [[-52, -12], [-29, -23], [-8, -21]], "rgba(107,123,136,0.20)", 0.75);
    stroke(ctx, [[-28, 5], [-9, 10], [6, 7]], "rgba(77,58,80,0.46)", 0.75);
    stroke(ctx, [[-37, 23], [-16, 31], [4, 34]], "rgba(65,58,78,0.22)", 0.7);
    ctx.restore();

    // Large oblique gape, kept within the natural compact body silhouette.
    const mouth = ctx.createLinearGradient(39, 1, 73, 30);
    mouth.addColorStop(0, "#090e1a");
    mouth.addColorStop(0.55, "#080912");
    mouth.addColorStop(1, "#24101d");
    ctx.fillStyle = mouth;
    ctx.fill(anglerMouth);
    stroke(ctx, [[57, -10], [73, -1], [80, 11]], "#6a4856", 1.2);
    stroke(ctx, [[80, 15], [67, 32], [44, 42], [24, 44]], "#463343", 1.35);
    stroke(ctx, [[38, 25], [47, 36], [67, 28]], "#472436", 0.8);

    ctx.save();
    ctx.clip(anglerMouth);
    // Thin, inward pointing teeth; no oversized fantasy tusks.
    const upperTeeth = [
      [[47, -3], [49, 7], [50, -4]],
      [[55, -7], [54, 6], [58, -7]],
      [[63, -4], [60, 8], [66, -2]],
      [[70, 1], [64, 12], [72, 4]],
      [[75, 8], [69, 16], [77, 11]]
    ];
    const lowerTeeth = [
      [[43, 28], [44, 18], [46, 31]],
      [[51, 34], [50, 22], [54, 33]],
      [[60, 31], [56, 20], [63, 30]],
      [[68, 26], [61, 18], [71, 23]]
    ];
    upperTeeth.forEach(p => facet(ctx, p, "#9d9d9b"));
    lowerTeeth.forEach(p => facet(ctx, p, "#717782"));
    ctx.restore();

    // Small eye high on the cheek, with a muted reflection from the lure.
    ctx.fillStyle = "#161222";
    ctx.beginPath(); ctx.ellipse(35, -20, 5.1, 4.6, -0.22, 0, TAU); ctx.fill();
    ctx.strokeStyle = "#62505c"; ctx.lineWidth = 0.7; ctx.stroke();
    ctx.fillStyle = "#050a13";
    ctx.beginPath(); ctx.arc(35.4, -20.1, 2.65, 0, TAU); ctx.fill();
    ctx.fillStyle = "rgba(170,198,187,0.68)";
    ctx.beginPath(); ctx.arc(36.2, -21.5, 0.9, 0, TAU); ctx.fill();

    // Pectoral fin is a translucent fan, with restrained fin rays.
    ctx.save();
    ctx.translate(-6, 10);
    ctx.rotate(-0.10 + Math.sin(time * 1.63 + 0.9) * 0.075);
    facet(ctx, [[0, 0], [-18, 9], [-23, 25], [-10, 31], [9, 25], [17, 12]], "rgba(72,49,66,0.72)");
    facet(ctx, [[0, 0], [-10, 31], [9, 25], [17, 12]], "rgba(40,47,65,0.72)");
    for (const end of [[-18, 20], [-10, 28], [2, 26], [12, 18]]) {
      stroke(ctx, [[0, 1], end], "rgba(106,96,113,0.35)", 0.65);
    }
    ctx.restore();

    // Illicium: one dorsal lure, a flexible arc rather than a rigid antenna.
    const sway = Math.sin(time * 1.17) * 2.3;
    const lureX = 83 + sway;
    const lureY = -53 + Math.sin(time * 1.17 + 0.8) * 1.3;
    ctx.beginPath();
    ctx.moveTo(17, -37);
    ctx.bezierCurveTo(21, -72, 42 + sway, -88, 64 + sway, -80);
    ctx.bezierCurveTo(77 + sway, -76, 81 + sway, -65, lureX, lureY);
    ctx.strokeStyle = "#6a6972"; ctx.lineWidth = 1.55; ctx.stroke();
    ctx.strokeStyle = "rgba(139,162,163,0.32)"; ctx.lineWidth = 0.55; ctx.stroke();

    const pulse = 0.89 + Math.sin(time * 1.8) * 0.06;
    const halo = ctx.createRadialGradient(lureX, lureY, 0, lureX, lureY, 24);
    halo.addColorStop(0, "rgba(175,214,185,0.35)");
    halo.addColorStop(0.25, "rgba(117,181,158,0.13)");
    halo.addColorStop(1, "rgba(83,148,130,0)");
    ctx.save(); ctx.globalAlpha *= pulse;
    ctx.fillStyle = halo;
    ctx.beginPath(); ctx.arc(lureX, lureY, 24, 0, TAU); ctx.fill();
    ctx.fillStyle = "#a8c7a9";
    ctx.beginPath(); ctx.ellipse(lureX, lureY, 4, 5.1, -0.1, 0, TAU); ctx.fill();
    facet(ctx, [[lureX - 2, lureY - 3], [lureX + 1, lureY - 4], [lureX + 2, lureY], [lureX - 1, lureY + 1]], "#e0dfb9");
    ctx.restore();
    ctx.restore();
  }

  const jellyBell = polygon([
    [-67, 5], [-61, -23], [-45, -48], [-23, -62], [0, -68],
    [25, -61], [47, -46], [61, -23], [68, 5], [57, 19],
    [35, 25], [13, 21], [0, 26], [-15, 21], [-37, 24], [-56, 18]
  ]);

  function ribbon(ctx, time, index) {
    const lengths = [243, 286, 265, 232];
    const roots = [-34, -13, 14, 35];
    const widths = [26, 29, 27, 25];
    const drifts = [-24, -9, 10, 28];
    const centers = [];
    const left = [];
    const right = [];
    const count = 21;
    const phase = index * 1.86;
    for (let i = 0; i <= count; i += 1) {
      const u = i / count;
      const y = 15 + u * lengths[index];
      const wave = Math.sin(u * 7.7 - time * 0.73 + phase);
      const x = roots[index] + drifts[index] * u + wave * (3 + 24 * u)
        + Math.sin(u * 3.7 + time * 0.31 + phase) * 12 * u;
      centers.push([x, y]);
    }
    for (let i = 0; i <= count; i += 1) {
      const u = i / count;
      const previous = centers[Math.max(0, i - 1)];
      const next = centers[Math.min(count, i + 1)];
      const dx = next[0] - previous[0];
      const dy = next[1] - previous[1];
      const mag = Math.hypot(dx, dy) || 1;
      // Broad oral arms turn in the current, presenting narrower folds.
      const fold = 0.74 + 0.26 * Math.cos(u * 10.5 - time * 0.45 + phase);
      const width = widths[index] * (1 - u * 0.30) * fold * (1 - Math.pow(u, 16));
      const normal = [dy / mag, -dx / mag];
      left.push([centers[i][0] - normal[0] * width / 2, centers[i][1] - normal[1] * width / 2]);
      right.push([centers[i][0] + normal[0] * width / 2, centers[i][1] + normal[1] * width / 2]);
    }
    const outline = polygon(left.concat(right.slice().reverse()));
    const pigment = ctx.createLinearGradient(roots[index], 12, roots[index], lengths[index] + 15);
    pigment.addColorStop(0, "rgba(117,49,72,0.80)");
    pigment.addColorStop(0.45, "rgba(86,40,65,0.70)");
    pigment.addColorStop(1, "rgba(54,35,61,0.50)");
    ctx.fillStyle = pigment;
    ctx.fill(outline);
    for (let i = 0; i < count; i += 1) {
      const light = (i + index) % 3 === 0;
      facet(ctx, [left[i], right[i], centers[i + 1]], light ? "rgba(188,111,126,0.18)" : "rgba(31,31,51,0.20)");
      facet(ctx, [centers[i], right[i + 1], right[i]], "rgba(35,27,47,0.18)");
    }
    stroke(ctx, left, "rgba(182,105,120,0.30)", 0.6);
    stroke(ctx, right, "rgba(78,86,109,0.28)", 0.6);
    stroke(ctx, centers, "rgba(154,72,94,0.26)", 0.5);
  }

  /** Giant phantom jelly interpretation: dark bell and exactly four oral arms.
   * Bell width ~136 px; total height ~370 px. No invented light or tentacles.
   */
  function drawJelly(ctx, options) {
    const time = begin(ctx, options);
    if (time === null) return;
    ctx.rotate(Math.sin(time * 0.27) * 0.024);
    const contraction = Math.sin(time * 0.91);
    ctx.scale(1 - contraction * 0.016, 1 + contraction * 0.01);
    // Four broad arms, arranged in depth behind a translucent umbrella.
    ribbon(ctx, time, 0);
    ribbon(ctx, time, 3);
    ribbon(ctx, time, 1);
    ribbon(ctx, time, 2);

    const bell = ctx.createLinearGradient(-35, -65, 28, 26);
    bell.addColorStop(0, "rgba(105,68,90,0.88)");
    bell.addColorStop(0.42, "rgba(117,51,77,0.83)");
    bell.addColorStop(0.79, "rgba(78,35,59,0.80)");
    bell.addColorStop(1, "rgba(55,32,51,0.85)");
    ctx.fillStyle = bell;
    ctx.fill(jellyBell);
    ctx.save(); ctx.clip(jellyBell);
    facet(ctx, [[0, -68], [-23, -62], [-45, -48], [-30, -20], [-9, -34]], "rgba(170,134,150,0.25)");
    facet(ctx, [[0, -68], [25, -61], [47, -46], [32, -18], [9, -33]], "rgba(140,84,107,0.27)");
    facet(ctx, [[-45, -48], [-61, -23], [-67, 5], [-44, 2], [-30, -20]], "rgba(140,93,117,0.22)");
    facet(ctx, [[47, -46], [61, -23], [68, 5], [43, 3], [32, -18]], "rgba(24,35,55,0.27)");
    facet(ctx, [[-9, -34], [9, -33], [22, -7], [0, 14], [-24, -8]], "rgba(193,69,97,0.15)");
    facet(ctx, [[-30, -20], [-9, -34], [-24, -8], [-35, 25], [-44, 2]], "rgba(58,34,58,0.23)");
    facet(ctx, [[9, -33], [32, -18], [43, 3], [35, 25], [22, -7]], "rgba(39,30,51,0.27)");
    facet(ctx, [[-24, -8], [0, 14], [-15, 21], [-37, 24]], "rgba(147,66,88,0.18)");
    facet(ctx, [[22, -7], [35, 25], [13, 21], [0, 14]], "rgba(124,51,74,0.18)");

    // Shallow radial canals are pigment and reflected light, not emission.
    const ribs = [
      [[-1, -62], [-9, -34], [-24, -8], [-35, 21]],
      [[-3, -61], [-30, -20], [-44, 2], [-54, 17]],
      [[1, -62], [9, -33], [22, -7], [33, 21]],
      [[3, -61], [32, -18], [43, 3], [56, 16]],
      [[0, -60], [0, -28], [0, 12], [0, 22]]
    ];
    ribs.forEach((points, i) => stroke(ctx, points, i < 2 ? "rgba(208,132,150,0.24)" : "rgba(148,78,105,0.25)", 0.7));
    // A recessed lower cavity gives the umbrella a readable thickness.
    ctx.fillStyle = "rgba(23,24,43,0.42)";
    ctx.beginPath(); ctx.ellipse(0, 12, 58, 11, 0, 0, TAU); ctx.fill();
    ctx.restore();
    stroke(ctx, [[-61, -23], [-45, -48], [-23, -62], [0, -68], [25, -61]], "rgba(201,196,216,0.29)", 0.95);
    stroke(ctx, [[-67, 5], [-56, 18], [-37, 24], [-15, 21], [0, 26], [13, 21], [35, 25], [57, 19], [68, 5]], "rgba(173,86,113,0.45)", 1.1);
    ctx.restore();
  }

  function seedHash(value) {
    let n = (value | 0) + 0x6d2b79f5;
    n = Math.imul(n ^ (n >>> 15), n | 1);
    n ^= n + Math.imul(n ^ (n >>> 7), n | 61);
    return ((n ^ (n >>> 14)) >>> 0) / 4294967296;
  }

  function smallFish(ctx, time, phase) {
    const tail = Math.sin(time * 4.1 + phase) * 2.3;
    facet(ctx, [[-11, 0], [-20, -5 + tail], [-18, 1 + tail], [-20, 6 + tail]], "#142433");
    facet(ctx, [[-7, -2], [-2, -7], [3, -3]], "#1c3040");
    facet(ctx, [[-6, 2], [-1, 6], [4, 3]], "#172433");
    facet(ctx, [[-13, 0], [-4, -4], [5, -3], [13, 0], [6, 4], [-4, 4]], "#213746");
    facet(ctx, [[-13, 0], [-4, -4], [5, -3], [3, 0]], "#36525b");
    facet(ctx, [[3, 0], [5, -3], [13, 0], [6, 4]], "#283f4b");
    facet(ctx, [[-13, 0], [3, 0], [6, 4], [-4, 4]], "#142333");
    facet(ctx, [[0, 0], [-4, 6], [5, 2]], "#2c414b");
    ctx.fillStyle = "#0c1522";
    ctx.beginPath(); ctx.arc(8.5, -0.8, 0.9, 0, TAU); ctx.fill();
    // A few dim ventral points suggest photophores at this illustrative scale.
    ctx.fillStyle = "rgba(146,166,142,0.32)";
    for (const x of [-5, -1, 3]) {
      ctx.beginPath(); ctx.arc(x, 2.7, 0.48, 0, TAU); ctx.fill();
    }
  }

  /** Deterministic, loose group of dim mesopelagic fish.
   * Optional count (default 18), seed (default 23), spread (default 1).
   * At scale 1 the group spans about 380 × 110 px; individual fish ~12–27 px.
   */
  function drawSchool(ctx, options) {
    const o = options || {};
    const time = begin(ctx, o);
    if (time === null) return;
    const count = clamp(Math.floor(finite(o.count, 18)), 0, 80);
    const seed = finite(o.seed, 23) | 0;
    const spread = Math.max(0, finite(o.spread, 1));
    for (let i = 0; i < count; i += 1) {
      const r1 = seedHash(seed + i * 13);
      const r2 = seedHash(seed + i * 13 + 1);
      const r3 = seedHash(seed + i * 13 + 2);
      const phase = r3 * TAU;
      const x = (r1 - 0.5) * 355 * spread + Math.sin(time * 0.41 + phase) * 7;
      const y = ((r2 - 0.5) * 85 + Math.sin(r1 * Math.PI) * 10) * spread
        + Math.sin(time * 0.71 + phase) * 3;
      const s = 0.38 + r3 * 0.48;
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(Math.sin(time * 0.61 + phase) * 0.065);
      ctx.scale(s, s);
      ctx.globalAlpha *= 0.30 + r3 * 0.48;
      smallFish(ctx, time, phase);
      ctx.restore();
    }
    ctx.restore();
  }

  global.DeepSeaCreatures = Object.freeze({ drawAngler, drawJelly, drawSchool });
})(window);
