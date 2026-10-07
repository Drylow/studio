// Moteur des vidéos TikTok « pixel » : dessine l'image du temps t (en secondes) d'après une
// timeline JSON déjà calée sur la voix. Tout est déterministe (pas de hasard non semé) pour que
// plusieurs navigateurs puissent rendre des morceaux différents de la même vidéo.
(function () {
  "use strict";
  const W = 540, H = 960, S = 2;            // espace de dessin 540x960, sortie 1080x1920
  const BASE_PAL = {
    bg: "#030407", K: "#05060c", B: "#2347ff", H: "#8197ff", D: "#14259a", N: "#0b1452",
    W: "#eceaf2", G: "#8d91a5", g: "#2b2e3b", S: "#dcc6bc", F: "#ff7a1a", Y: "#ffd04a", R: "#c2410c",
  };
  const DITHER = { b: ["B", "D"], h: ["H", "B"], d: ["D", "N"], n: ["N", "K"], w: ["W", "G"] };
  const PRESETS = {
    title: { type: "text", font: "sans", size: 27, color: "W", y: 160, in: "fade" },
    sub: { type: "text", font: "sans", size: 20, color: "W", in: "fade" },
    big: { type: "text", font: "pixelb", size: 76, color: "B", ls: 5, stripes: true, in: "slam", y: 245 },
    num: { type: "text", font: "pixelb", size: 50, color: "B", ls: 4, stripes: true, in: "pop" },
    label: { type: "text", font: "pixel", size: 14, color: "G", ls: 2, in: "type" },
    tag: { type: "text", font: "pixel", size: 19, color: "B", ls: 2, in: "type" },
  };
  const FONTS = { sans: '"Archivo Black"', pixel: "Silkscreen", pixelb: "Tiny5" };

  const cv = document.getElementById("c");
  cv.width = W * S; cv.height = H * S;
  const ctx = cv.getContext("2d");
  const off = document.createElement("canvas");       // calque pour les effets (rayures, pixelisation)
  const octx = off.getContext("2d");
  let spec = null, PAL = BASE_PAL, scenes = [], hits = [];

  // ---------- outils ----------
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, p) => a + (b - a) * p;
  const easeOut = p => 1 - Math.pow(1 - p, 3);
  const easeInOut = p => (p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
  const easeBack = p => { const c = 1.9; return 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2); };
  function hash(a, b = 0, c = 0) {
    let h = (a * 374761393 + b * 668265263 + c * 2147483647) | 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  }
  const col = k => (k && k[0] === "#" ? k : PAL[k] || k || PAL.W);
  function alpha(hex, a) {
    const c = col(hex), n = parseInt(c.slice(1), 16);
    return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`;
  }

  // ---------- chargement ----------
  async function load(s) {
    spec = s;
    PAL = Object.assign({}, BASE_PAL, s.palette || {});
    scenes = (s.scenes || []).slice().sort((a, b) => a.start - b.start);
    scenes.forEach((sc, i) => {
      sc.end = sc.end ?? (scenes[i + 1] ? scenes[i + 1].start : s.duration);
      sc.els = (sc.els || []).map(e => Object.assign({}, PRESETS[e.preset] || {}, e));
    });
    hits = [];
    for (const sc of scenes) for (const e of sc.els)
      if (e.in === "slam" || e.flash) hits.push({ t: e.at, c: e.flashColor || e.color || "B", k: e.flash === "big" ? 1.6 : 1 });
    TT.duration = s.duration;
    await Promise.all(['40px "Archivo Black"', "40px Silkscreen", "40px Tiny5"].map(f => document.fonts.load(f)));
  }

  // ---------- apparition / disparition ----------
  function life(e, t, sc) {
    const lt = t - e.at;
    let a = 1, s = 1, dx = 0, dy = 0, rev = 1;
    switch (e.in || "pop") {
      case "none": break;
      case "fade": a = clamp(lt / 0.14); break;
      case "pop": { const p = clamp(lt / 0.24); s = 0.35 + 0.65 * easeBack(p); a = clamp(lt / 0.06); break; }
      case "slam": { const p = clamp(lt / 0.14); s = 1 + 1.1 * (1 - easeOut(p)); a = clamp(lt / 0.04); break; }
      case "rise": { const p = clamp(lt / 0.3); dy = 22 * (1 - easeOut(p)); a = p; break; }
      case "drop": { const p = clamp(lt / 0.35); dy = -80 * (1 - easeOut(p)); a = clamp(lt / 0.08); break; }
      case "type": rev = clamp(lt / (e.typeDur ?? Math.max(0.25, (e.text || "").length / 34))); break;
      case "build": rev = clamp(lt / (e.buildDur ?? 0.5)); break;
    }
    const outT = e.out ?? null;
    if (outT !== null && t > outT) a *= 1 - clamp((t - outT) / (e.outDur ?? 0.12));
    if (e.blink && lt > 0) a *= Math.floor(lt * (e.blink || 2) * 2) % 2 ? 0.25 : 1;
    let x = e.x ?? W / 2, y = e.y ?? H / 2;
    for (const m of e.moves || (e.move ? [e.move] : [])) {
      const p = easeInOut(clamp((t - m.at) / (m.dur || 0.5)));
      if (m.to) { x = lerp(x, m.to[0], p); y = lerp(y, m.to[1], p); }
      if (m.scale) s *= lerp(1, m.scale, p);
    }
    return { a, s, x: x + dx, y: y + dy, rev, lt };
  }

  // ---------- fond ----------
  function background(t, sc) {
    ctx.fillStyle = PAL.bg; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = alpha("B", 0.028);                 // grille très légère
    for (let x = 0; x < W; x += 12) ctx.fillRect(x, 0, 0.5, H);
    for (let y = 0; y < H; y += 12) ctx.fillRect(0, y, W, 0.5);
    const g = sc && sc.glow !== false ? Object.assign({ x: W / 2, y: 400, r: 260, a: 0.17 }, sc.glow || {}) : null;
    if (g) {
      const fl = g.flicker ? 1 + 0.12 * Math.sin(t * 23) * Math.sin(t * 7.3) : 1;
      const rg = ctx.createRadialGradient(g.x, g.y, 0, g.x, g.y, g.r * fl);
      rg.addColorStop(0, alpha(g.c || "B", g.a * fl)); rg.addColorStop(1, alpha(g.c || "B", 0));
      ctx.fillStyle = rg; ctx.fillRect(0, 0, W, H);
    }
    particles(t, sc);
  }
  function particles(t, sc) {
    const kind = (sc && sc.particles) || "dust";
    if (kind === "none") return;
    const n = kind === "snow" ? (sc.density || 140) : 22;
    for (let i = 0; i < n; i++) {
      const r1 = hash(i, 11), r2 = hash(i, 23), r3 = hash(i, 37);
      if (kind === "snow") {
        const sp = 18 + 40 * r3, y = ((r2 * (H + 40)) + t * sp) % (H + 40) - 20;
        const x = (r1 * W + Math.sin(t * (0.6 + r3) + i) * 14 + t * (sc.wind || 10)) % W;
        ctx.fillStyle = alpha("W", 0.35 + 0.5 * r3); const z = r3 > 0.7 ? 3 : 2;
        ctx.fillRect(Math.round(x), Math.round(y), z, z);
      } else {
        const sp = 4 + 10 * r3, y = (H - ((r2 * H + t * sp) % H));
        const x = r1 * W + Math.sin(t * 0.3 + i) * 6;
        ctx.fillStyle = alpha("B", 0.12 + 0.35 * r3 * (0.6 + 0.4 * Math.sin(t * 2 + i)));
        ctx.fillRect(Math.round(x), Math.round(y), 2, 2);
      }
    }
  }
  function overlay(t) {
    for (const h of hits) {                              // flash plein écran sur les gros chiffres
      const d = t - h.t;
      if (d >= 0 && d < 0.16) { ctx.fillStyle = alpha(h.c, 0.3 * h.k * (1 - d / 0.16)); ctx.fillRect(0, 0, W, H); }
    }
    const v = ctx.createRadialGradient(W / 2, H * 0.42, H * 0.22, W / 2, H * 0.45, H * 0.78);
    v.addColorStop(0, "rgba(0,0,0,0)"); v.addColorStop(1, "rgba(0,0,0,0.72)");
    ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
  }
  function shake(t) {
    let x = 0, y = 0;
    for (const h of hits) {
      const d = t - h.t;
      if (d >= 0 && d < 0.2) { const k = 4 * h.k * (1 - d / 0.2); x += (hash(Math.floor(t * 60), 1) - .5) * 2 * k; y += (hash(Math.floor(t * 60), 2) - .5) * 2 * k; }
    }
    return [x, y];
  }

  // ---------- texte ----------
  function tokens(text) {      // *mot* = couleur d'accent, ~mot~ = gris
    const out = [];
    let mode = null;
    for (const part of String(text).split(/(\*|~|\n)/)) {
      if (part === "*" || part === "~") { mode = mode === part ? null : part; continue; }
      if (part === "\n") { out.push({ br: true }); continue; }
      for (const w of part.split(/(\s+)/)) if (w) out.push({ w, m: mode });
    }
    return out;
  }
  function fontOf(e) { return `${e.size}px ${FONTS[e.font] || FONTS.sans}`; }
  function layoutText(e) {
    ctx.font = fontOf(e); ctx.letterSpacing = (e.ls || 0) + "px";
    const maxW = e.maxW || 480, lines = [[]], widths = [0];
    for (const tk of tokens(e.upper ? String(e.text).toUpperCase() : e.text)) {
      if (tk.br) { lines.push([]); widths.push(0); continue; }
      const w = ctx.measureText(tk.w).width, L = lines.length - 1, sp = /^\s+$/.test(tk.w);
      if (!sp && widths[L] + w > maxW && lines[L].length) { lines.push([]); widths.push(0); }
      const L2 = lines.length - 1;
      if (sp && !lines[L2].length) continue;
      lines[L2].push({ ...tk, width: w }); widths[L2] += w;
    }
    lines.forEach((ln, i) => { while (ln.length && /^\s+$/.test(ln[ln.length - 1].w)) widths[i] -= ln.pop().width; });
    return { lines, widths };
  }
  function drawText(e, t) {
    const L = life(e, t), lay = layoutText(e), lh = e.size * (e.lh || 1.15);
    const total = lay.lines.length * lh;
    let chars = Infinity;
    if (e.in === "type") chars = Math.floor(L.rev * String(e.text).replace(/[*~]/g, "").length);
    const tw = Math.max(...lay.widths);
    const draw = c => {
      c.font = fontOf(e); c.letterSpacing = (e.ls || 0) + "px"; c.textBaseline = "middle";
      let y = -total / 2 + lh / 2, n = 0;
      lay.lines.forEach((ln, i) => {
        let x = e.align === "left" ? -tw / 2 : e.align === "right" ? tw / 2 - lay.widths[i] : -lay.widths[i] / 2;
        for (const tk of ln) {
          let s = tk.w;
          if (n + s.length > chars) s = s.slice(0, Math.max(0, chars - n));
          n += tk.w.length;
          c.fillStyle = col(tk.m === "*" ? (e.accent || "B") : tk.m === "~" ? "G" : e.color);
          if (s) c.fillText(s, x, y);
          x += tk.width;
        }
        y += lh;
      });
    };
    ctx.save();
    ctx.globalAlpha *= L.a; ctx.translate(L.x, L.y); ctx.scale(L.s, L.s);
    if (e.rot) ctx.rotate(e.rot * Math.PI / 180);
    if (e.stripes) {                                   // chiffres façon écran LED (lignes sombres)
      const pw = Math.ceil(tw + 40), ph = Math.ceil(total + 30);
      off.width = pw * S; off.height = ph * S;
      octx.setTransform(S, 0, 0, S, pw * S / 2, ph * S / 2); octx.clearRect(-pw, -ph, pw * 2, ph * 2);
      draw(octx);
      octx.globalCompositeOperation = "source-atop"; octx.fillStyle = "rgba(0,0,0,0.38)";
      for (let y = -ph / 2; y < ph / 2; y += 2.5) octx.fillRect(-pw / 2, y, pw, 0.8);
      octx.globalCompositeOperation = "source-over";
      ctx.shadowColor = alpha(e.color, 0.55); ctx.shadowBlur = 14;
      ctx.drawImage(off, -pw / 2, -ph / 2, pw, ph);
      ctx.shadowBlur = 0;
    } else draw(ctx);
    if (e.strike) {                                    // trait qui barre le texte
      const p = clamp((t - e.strike.at) / (e.strike.dur || 0.3));
      if (p > 0) { ctx.fillStyle = col(e.strike.color || "B"); ctx.fillRect(-tw / 2 - 6, -2, (tw + 12) * p, 4); }
    }
    ctx.restore();
  }

  // ---------- dessins en pixels ----------
  function spriteGrid(e, t) {
    let g = window.SPRITES[e.sprite] || e.grid;
    if (!g) return null;
    if (Array.isArray(g[0])) g = g[Math.floor(t * (e.fps || 6)) % g.length];
    return g;
  }
  function drawSpriteAt(g, x0, y0, px, opts = {}) {
    const w = Math.max(...g.map(r => r.length)), h = g.length;
    for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
      let ch = g[j][opts.flip ? w - 1 - i : i];
      if (!ch || ch === "." || ch === " ") continue;
      if (opts.rev !== undefined && opts.rev < 1 && hash(i, j, 7) > opts.rev) continue;
      if (DITHER[ch]) ch = DITHER[ch][(i + j) & 1];
      ctx.fillStyle = opts.mono ? col(opts.mono) : col(ch);
      ctx.fillRect(x0 + i * px, y0 + j * px, px + 0.02, px + 0.02);
    }
    return [w * px, h * px];
  }
  function drawSprite(e, t) {
    const L = life(e, t), g = spriteGrid(e, t);
    if (!g) return;
    const px = e.px || 6, w = Math.max(...g.map(r => r.length)) * px, h = g.length * px;
    let bob = 0;
    if (e.fx === "bob") bob = Math.round(Math.sin(t * 5) * 1.5) * (px / 2);
    if (e.fx === "shiver") bob = (hash(Math.floor(t * 20), 5) - .5) * px * 0.6;
    ctx.save();
    ctx.globalAlpha *= L.a; ctx.translate(L.x, L.y + bob); ctx.scale(L.s, L.s);
    if (e.glow) { ctx.shadowColor = alpha(e.glow, 0.7); ctx.shadowBlur = 18; }
    drawSpriteAt(g, -w / 2, -h / 2, px, { flip: e.flip, rev: L.rev, mono: e.mono });
    ctx.restore();
  }

  // ---------- grille d'icônes (une icône = N personnes) ----------
  function iconsLit(e, t) {
    let n = e.count;
    const ks = e.keys || [];
    if (e.fill) n = Math.floor(e.count * clamp((t - e.at) / e.fill));
    for (let k = 0; k < ks.length; k++) {
      const a = ks[k];
      if (t < a.at) break;
      const prev = k ? ks[k - 1].n : (e.fill ? e.count : e.count);
      n = Math.round(lerp(prev, a.n, easeOut(clamp((t - a.at) / (a.dur || 1.2)))));
    }
    return n;
  }
  function drawIcons(e, t) {
    const L = life(e, t), g = window.SPRITES[e.sprite] || window.SPRITES.soldier;
    const px = e.px || 2, cols = e.cols || 10, gw = Math.max(...g.map(r => r.length)) * px, gh = g.length * px;
    const gx = e.gapX ?? 4, gy = e.gapY ?? 6, rows = Math.ceil(e.count / cols);
    const tw = cols * gw + (cols - 1) * gx, th = rows * gh + (rows - 1) * gy;
    const lit = iconsLit(e, t);
    // ordre d'extinction semé : les icônes s'éteignent un peu partout, pas ligne par ligne
    const order = [...Array(e.count).keys()].sort((a, b) => hash(a, 99) - hash(b, 99));
    const rank = new Array(e.count); order.forEach((v, i) => (rank[v] = i));
    const filling = e.fill && t - e.at < e.fill;
    ctx.save(); ctx.globalAlpha *= L.a; ctx.translate(L.x - tw / 2, L.y - th / 2);
    for (let i = 0; i < e.count; i++) {
      const cx = (i % cols) * (gw + gx), cy = Math.floor(i / cols) * (gh + gy);
      const on = filling ? i < lit : rank[i] < lit;
      if (filling && !on) continue;
      drawSpriteAt(g, cx, cy, px, on ? {} : { mono: e.offColor || "g" });
    }
    ctx.restore();
  }

  // ---------- grille de carrés ----------
  function drawGrid(e, t) {
    const L = life(e, t), cols = e.cols || 10, rows = e.rows || 10, c = e.cell || 12, gp = e.gap ?? 3;
    const tw = cols * c + (cols - 1) * gp, th = rows * c + (rows - 1) * gp;
    let lit = e.lit || 0;
    if (e.litAt !== undefined) lit = t >= e.litAt ? lit : 0;
    if (e.fillDur) lit = Math.floor(lit * clamp((t - (e.litAt ?? e.at)) / e.fillDur));
    ctx.save(); ctx.globalAlpha *= L.a; ctx.translate(L.x - tw / 2, L.y - th / 2);
    for (let i = 0; i < cols * rows; i++) {
      const x = (i % cols) * (c + gp), y = Math.floor(i / cols) * (c + gp);
      const on = e.from === "end" ? i >= cols * rows - lit : i < lit;
      if (L.rev < 1 && hash(i, 3) > L.rev) continue;
      ctx.fillStyle = col(on ? (e.color || "B") : (e.offColor || "g"));
      ctx.fillRect(x, y, c, c);
      if (on) { ctx.fillStyle = "rgba(255,255,255,0.25)"; ctx.fillRect(x, y, c, Math.max(1, c / 6)); }
    }
    ctx.restore();
  }

  // ---------- barres en segments ----------
  function drawBars(e, t) {
    const L = life(e, t), bw = e.w || 260, bh = e.barH || 14, gp = e.gap || 14;
    const max = e.max || Math.max(...e.items.map(i => i.value));
    ctx.save(); ctx.globalAlpha *= L.a; ctx.translate(L.x - bw / 2, L.y - (e.items.length * (bh + gp)) / 2);
    e.items.forEach((it, k) => {
      const p = easeOut(clamp((t - e.at - k * (e.stagger ?? 0.15)) / (e.grow || 0.6)));
      const y = k * (bh + gp);
      ctx.font = `${e.fontSize || 15}px Silkscreen`; ctx.letterSpacing = "1px"; ctx.textBaseline = "middle"; ctx.textAlign = "right";
      ctx.fillStyle = col(it.hl ? "B" : "G"); ctx.fillText(it.label, -10, y + bh / 2);
      const n = Math.round((bw * it.value / max) * p / 4);
      ctx.fillStyle = col(it.hl ? "B" : (it.color || "G"));
      for (let s = 0; s < n; s++) ctx.fillRect(s * 4, y, 2.6, bh);
      ctx.textAlign = "left"; ctx.fillStyle = col(it.hl ? "B" : "G");
      if (p > 0.95 && it.text) ctx.fillText(it.text, n * 4 + 8, y + bh / 2);
    });
    ctx.restore();
  }

  // ---------- tampon ----------
  function drawStamp(e, t) {
    const L = life(e, t);
    ctx.save(); ctx.globalAlpha *= L.a; ctx.translate(L.x, L.y); ctx.scale(L.s, L.s); ctx.rotate((e.rot ?? -4) * Math.PI / 180);
    ctx.font = `${e.size || 15}px Silkscreen`; ctx.letterSpacing = "2px"; ctx.textBaseline = "middle"; ctx.textAlign = "center";
    const w = ctx.measureText(e.text).width + 22, h = (e.size || 15) + 14;
    if (e.fill) { ctx.fillStyle = col(e.color || "B"); ctx.fillRect(-w / 2, -h / 2, w, h); ctx.fillStyle = col(e.textColor || "W"); }
    else { ctx.strokeStyle = col(e.color || "B"); ctx.lineWidth = 3; ctx.strokeRect(-w / 2, -h / 2, w, h); ctx.fillStyle = col(e.color || "B"); }
    ctx.fillText(e.text, 1, 1);
    ctx.restore();
  }

  // ---------- compteur ----------
  function fmt(v, e) {
    const n = e.decimals ? v.toFixed(e.decimals).replace(".", ",") : String(Math.round(v));
    const [a, b] = n.split(",");
    return (e.prefix || "") + a.replace(/\B(?=(\d{3})+(?!\d))/g, " ") + (b ? "," + b : "") + (e.suffix || "");
  }
  function drawCounter(e, t) {
    const p = easeOut(clamp((t - e.at) / (e.dur || 1.2)));
    let v = lerp(e.from ?? 0, e.to, p);
    for (const k of e.keys || []) if (t >= k.at) v = lerp(v, k.to, easeOut(clamp((t - k.at) / (k.dur || 1.2))));
    const settled = p >= 1;
    drawText(Object.assign({}, PRESETS.big, { in: "fade" }, e, {
      type: "text", text: fmt(v, e), color: settled || !e.dimWhileCounting ? (e.color || "B") : "D",
    }), t);
  }

  // ---------- flux de Minard (bande dont l'épaisseur = effectif) ----------
  function drawFlow(e, t) {
    const L = life(e, t), pts = e.points, k = e.scale || 0.0004;
    const p = clamp((t - (e.drawAt ?? e.at)) / (e.dur || 2));
    const seg = []; let total = 0;
    for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y); seg.push(d); total += d; }
    let rem = total * easeInOut(p);
    const pk = e.pixel || 3;                         // on dessine en basse définition puis on agrandit : rendu pixel
    off.width = Math.ceil(W * S / pk); off.height = Math.ceil(H * S / pk);
    octx.setTransform(S / pk, 0, 0, S / pk, 0, 0); octx.clearRect(0, 0, W, H);
    octx.fillStyle = col(e.color || "B");
    for (let i = 1; i < pts.length && rem > 0; i++) {
      const a = pts[i - 1], b = pts[i], f = Math.min(1, rem / seg[i - 1]); rem -= seg[i - 1];
      const bx = lerp(a.x, b.x, f), by = lerp(a.y, b.y, f), bn = lerp(a.n, b.n, f);
      const wa = Math.max(1.5, a.n * k), wb = Math.max(1.5, bn * k), side = e.side || 1;
      octx.beginPath();
      octx.moveTo(a.x, a.y); octx.lineTo(bx, by);
      octx.lineTo(bx, by + side * wb); octx.lineTo(a.x, a.y + side * wa); octx.closePath(); octx.fill();
    }
    ctx.save(); ctx.globalAlpha *= L.a; ctx.imageSmoothingEnabled = false;
    if (e.glowFx !== false) { ctx.shadowColor = alpha(e.color || "B", 0.6); ctx.shadowBlur = 12; }
    ctx.drawImage(off, 0, 0, W, H);
    ctx.restore();
  }

  // ---------- courbe ----------
  function drawLine(e, t) {
    const L = life(e, t), b = e.box, p = easeInOut(clamp((t - e.at) / (e.dur || 1.5)));
    const [x0, x1] = e.xr, [y0, y1] = e.yr;
    const X = v => b.x + (v - x0) / (x1 - x0) * b.w, Y = v => b.y + b.h - (v - y0) / (y1 - y0) * b.h;
    ctx.save(); ctx.globalAlpha *= L.a;
    ctx.fillStyle = col("g"); ctx.fillRect(b.x, b.y + b.h, b.w, 1.5); ctx.fillRect(b.x, b.y, 1.5, b.h);
    ctx.font = "10px Silkscreen"; ctx.letterSpacing = "1px"; ctx.fillStyle = col("G"); ctx.textBaseline = "middle";
    for (const tk of e.yTicks || []) { ctx.textAlign = "right"; ctx.fillText(tk.label, b.x - 6, Y(tk.v)); ctx.fillStyle = alpha("G", .15); ctx.fillRect(b.x, Y(tk.v), b.w, 1); ctx.fillStyle = col("G"); }
    for (const tk of e.xTicks || []) { ctx.textAlign = "center"; ctx.fillText(tk.label, X(tk.v), b.y + b.h + 12); }
    const pts = e.points, n = (pts.length - 1) * p;
    ctx.fillStyle = col(e.color || "B");
    const step = 2.5;
    for (let i = 0; i < Math.ceil(n); i++) {
      const a = pts[i], c = pts[i + 1], f = Math.min(1, n - i);
      const ax = X(a[0]), ay = Y(a[1]), cx = lerp(ax, X(c[0]), f), cy = lerp(ay, Y(c[1]), f);
      const d = Math.max(1, Math.hypot(cx - ax, cy - ay) / step);
      for (let s = 0; s <= d; s++) ctx.fillRect(Math.round(lerp(ax, cx, s / d) / step) * step, Math.round(lerp(ay, cy, s / d) / step) * step, 3, 3);
    }
    for (const m of e.marks || []) if (n >= m.i) {
      const [mx, my] = [X(pts[m.i][0]), Y(pts[m.i][1])];
      ctx.fillStyle = col(m.color || "W"); ctx.textAlign = "center"; ctx.font = `${m.size || 12}px Silkscreen`;
      ctx.fillText(m.label, mx, my + (m.dy ?? -16));
    }
    ctx.restore();
  }

  // ---------- forêt en cercle autour d'un feu ----------
  function drawForest(e, t) {
    const L = life(e, t), n = e.count || 16, r = e.r || 150, px = e.px || 4;
    ctx.save(); ctx.globalAlpha *= L.a;
    for (let i = 0; i < n; i++) {
      const ang = (i / n) * Math.PI * 2 + hash(i, 4) * 0.3, rr = r * (0.9 + 0.35 * hash(i, 8));
      const x = L.x + Math.cos(ang) * rr, y = L.y + Math.sin(ang) * rr * 0.75;
      const g = window.SPRITES.pine, sz = px * (0.8 + 0.6 * hash(i, 9));
      ctx.globalAlpha = L.a * (0.45 + 0.4 * hash(i, 12));
      drawSpriteAt(g, x - 4.5 * sz, y - 10 * sz, sz);
    }
    ctx.restore();
  }

  // ---------- carte de fin ----------
  function drawEndcard(e, t) {
    const L = life(e, t);
    ctx.save(); ctx.globalAlpha *= L.a;
    ctx.fillStyle = col(e.bg || "B"); ctx.fillRect(0, 0, W, H);
    ctx.restore();
    drawText({ type: "text", font: "sans", size: 25, color: "W", accent: "N", text: e.text, y: e.y || 170, at: e.at, in: "fade", maxW: 460 }, t);
    if (e.button) {
      const p = clamp((t - e.at - 0.3) / 0.3);
      ctx.save(); ctx.globalAlpha *= p; ctx.translate(W / 2, e.by || 560); ctx.rotate(-3 * Math.PI / 180);
      ctx.font = "15px Silkscreen"; ctx.letterSpacing = "2px"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      const w = ctx.measureText(e.button + "  ▶").width + 26;
      ctx.fillStyle = alpha("N", 0.85); ctx.fillRect(-w / 2, -16, w, 32);
      ctx.fillStyle = col("W"); ctx.fillText(e.button + "  ▶", 0, 1);
      ctx.restore();
    }
  }

  // ---------- rectangle / trait ----------
  function drawRect(e, t) {
    const L = life(e, t);
    ctx.save(); ctx.globalAlpha *= L.a; ctx.translate(L.x, L.y);
    const p = e.grow ? easeOut(clamp((t - e.at) / e.grow)) : 1;
    ctx.fillStyle = col(e.color || "B");
    if (e.stroke) { ctx.strokeStyle = col(e.color || "B"); ctx.lineWidth = e.stroke; ctx.strokeRect(-e.w / 2, -e.h / 2, e.w * p, e.h); }
    else ctx.fillRect(-e.w / 2, -e.h / 2, e.w * p, e.h);
    ctx.restore();
  }

  // ---------- double hélice d'ADN qui tourne ----------
  function drawDna(e, t) {
    const L = life(e, t), h = e.h || 260, amp = e.amp || 34, px = e.px || 5, n = Math.floor(h / (px * 1.6));
    ctx.save(); ctx.globalAlpha *= L.a; ctx.translate(L.x, L.y - h / 2);
    for (let i = 0; i < n; i++) {
      if (L.rev < 1 && i / n > L.rev) break;
      const y = i * px * 1.6, ph = i * 0.42 + t * (e.speed || 2.2);
      const x1 = Math.sin(ph) * amp, x2 = -x1, front = Math.cos(ph) > 0;
      if (i % 3 === 0) {                               // barreaux entre les deux brins
        ctx.fillStyle = alpha("H", 0.35);
        const a = Math.min(x1, x2), b = Math.max(x1, x2);
        for (let x = a; x < b; x += px) ctx.fillRect(Math.round(x / px) * px, y, px - 1, px - 1);
      }
      ctx.fillStyle = col(front ? "B" : "D"); ctx.fillRect(Math.round(x1 / px) * px, y, px, px);
      ctx.fillStyle = col(front ? "D" : "B"); ctx.fillRect(Math.round(x2 / px) * px, y, px, px);
    }
    ctx.restore();
  }

  const DRAW = { dna: drawDna, text: drawText, sprite: drawSprite, icons: drawIcons, grid: drawGrid, bars: drawBars, stamp: drawStamp,
    counter: drawCounter, flow: drawFlow, line: drawLine, forest: drawForest, endcard: drawEndcard, rect: drawRect };

  function sceneAt(t) { let s = null; for (const sc of scenes) if (sc.start <= t) s = sc; return s; }
  function frame(t) {
    ctx.setTransform(S, 0, 0, S, 0, 0);
    ctx.imageSmoothingEnabled = false; ctx.globalAlpha = 1; ctx.letterSpacing = "0px";
    const sc = sceneAt(t);
    background(t, sc);
    if (sc) {
      const [sx, sy] = shake(t);
      ctx.save(); ctx.translate(sx, sy);
      for (const e of sc.els) {
        if (t < e.at) continue;
        if (e.out != null && t > e.out + (e.outDur ?? 0.12)) continue;
        ctx.save(); (DRAW[e.type] || drawText)(e, t, sc); ctx.restore();
      }
      ctx.restore();
    }
    overlay(t);
  }

  window.TT = { load, frame, duration: 0, W, H, S };
})();
