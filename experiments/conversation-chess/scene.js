// Offline conversation-review graphics. Exact official SVGs; approved PNG stays unchanged.
window.ConversationChess = (() => {
  const W = 1920, H = 1080, canvas = document.querySelector('canvas');
  const ctx = canvas.getContext('2d', { alpha: true });
  const schema = window.ConversationRatingSchema;
  if (!schema?.categories?.length) throw new Error('Load ratings.json before scene.js.');
  const ratings = Object.fromEntries(schema.categories.map(v => [v.id, v]));
  const clamp = v => Math.max(0, Math.min(1, v));
  let tony = null, tonyOverlay = null, background = null;
  function text(s, x, y, size, color = '#ffffff', weight = 700, align = 'left', family = 'Arial') {
    ctx.font = `${weight} ${size}px ${family}`; ctx.textAlign = align;
    ctx.textBaseline = 'alphabetic'; ctx.fillStyle = color; ctx.fillText(s, x, y);
  }
  function lines(s, x, y, size, color, leading = size * 1.2, family = 'Arial', align = 'left') {
    String(s).split('\n').forEach((row, i) => text(row, x, y + i * leading, size, color, 700, align, family));
  }
  function imageContain(image, x, y, w, h) {
    const s = Math.min(w / image.width, h / image.height);
    const nw = image.width * s, nh = image.height * s;
    ctx.drawImage(image, x + (w - nw) / 2, y + (h - nh) / 2, nw, nh);
  }
  const officialIcons = {};
  function ratingIcon(v, x, y, size = 76) {
    const icon = officialIcons[v.id];
    if (!icon) throw new Error(`Official Chess.com icon unavailable: ${v.id}`);
    imageContain(icon, x, y, size, size);
  }
  // A single silhouette, recoloured for both sides; Unicode pawn glyphs differ.
  function pawn(x, y, height = 46, white = false) {
    ctx.save(); ctx.translate(x - height * .34, y); ctx.scale(height / 100, height / 100);
    ctx.beginPath(); ctx.arc(34, 17, 14, 0, Math.PI * 2);
    ctx.moveTo(19, 36); ctx.lineTo(49, 36); ctx.lineTo(51, 44); ctx.lineTo(17, 44); ctx.closePath();
    ctx.moveTo(22, 45); ctx.bezierCurveTo(24, 60, 19, 73, 12, 82);
    ctx.lineTo(56, 82); ctx.bezierCurveTo(49, 73, 44, 60, 46, 45); ctx.closePath();
    ctx.moveTo(10, 83); ctx.lineTo(58, 83); ctx.lineTo(62, 94); ctx.lineTo(6, 94); ctx.closePath();
    ctx.fillStyle = white ? '#ffffff' : '#403c38'; ctx.fill();
    ctx.strokeStyle = white ? '#aaa69e' : '#b8b2a8'; ctx.lineWidth = 2; ctx.stroke(); ctx.restore();
  }
  function guideBackground(transparentBackground = false) {
    ctx.clearRect(0, 0, W, H);
    if (background && !transparentBackground) imageContain(background, 0, 0, W, H);
    // Without a supplied frame this stays translucent for compositing over real footage.
    ctx.fillStyle = 'rgba(0,0,0,.79)'; ctx.fillRect(0, 0, W, H);
  }
  function symbols(transparentBackground = false) {
    guideBackground(transparentBackground);
    if (tonyOverlay || tony) imageContain(tonyOverlay || tony, 302, 12, 130, 130);
    text('Annotation Symbols Guide', 1120, 107, 65, '#f4f4f4', 700, 'center', 'monospace');
    for (const v of schema.categories) {
      const x = 36 + v.column * 960, y = 189 + v.row * 141;
      ratingIcon(v, x + 75, y, 76);
      text(v.label + (v.id === 'inaccuracy' ? '' : ' Move'), x + 114, y + 111,
        30, v.color, 700, 'center', 'monospace');
      lines(v.definition, x + 300, y + 36, 33, v.color, 40, 'monospace');
    }
  }
  function evaluation(t = 9, transparentBackground = false) {
    guideBackground(transparentBackground);
    text('What is the Conversation Score?', 1080, 120, 64, '#ffffff', 800, 'center');
    controlBar(t < 10 ? '0.0' : '-1.8', '0.0', t - 10, {x:110, y:40, width:50, height:1000});
    lines('The bar shows who controls the conversation: Black or White.\nThe score sits on the side with the advantage.\nEach conversation starts at 0.0. These are our judgments\nabout the dialogue, not chess engine calculations.', 1100, 254, 40, '#ffffff', 53, 'Arial', 'center');
    function note(ids, y, rest) {
      const size = 60;
      let x = 374;
      for (const [index, id] of ids.entries()) {
        if (index > 0) { text('and', x, y, 40, '#ffffff', 700); x += 104; }
        const v = ratings[id]; ratingIcon(v, x, y - 44, size);
        text(v.label + ' Moves', x + 75, y, 40, v.color, 700);
        ctx.font = '700 40px Arial'; x += 75 + ctx.measureText(v.label + ' Moves').width + 36;
      }
      text(rest, x, y, 40, '#ffffff', 700);
    }
    note(['best', 'great'], 559, 'leave the bar unchanged.');
    note(['book'], 675, 'may give the speaker a small edge.');
    note(['brilliant'], 791, 'shift control toward the speaker.');
    lines('The other labels show a loss of control for the speaker.\nA third party changes the bar only when their line\naffects one of the two main sides.', 1100, 923, 40, '#ffffff', 51, 'Arial', 'center');
  }
  function intro(t, transparentBackground = false) {
    if (t < schema.symbols_seconds) symbols(transparentBackground); else evaluation(t, transparentBackground);
    if (t > schema.intro_seconds - schema.fade_seconds) {
      ctx.fillStyle = `rgba(0,0,0,${clamp((t - schema.intro_seconds + schema.fade_seconds) / schema.fade_seconds)})`;
      ctx.fillRect(0, 0, W, H);
    }
  }
  function controlBar(scoreText = '0.0', previousScoreText = scoreText, seconds = .5, position = null) {
    const score = Number(scoreText), previous = Number(previousScoreText);
    const config = schema.bar, p = clamp(seconds / config.transition_seconds), eased = p * p * (3 - 2 * p);
    const shownScore = previous + (score - previous) * eased;
    // Same visual mapping as the existing chess review widget. This score is editorial.
    const whiteShare = 1 / (1 + Math.exp(-shownScore * .36));
    const bx = position?.x ?? config.x, by = position?.y ?? config.y;
    const bw = position?.width ?? config.width, bh = position?.height ?? config.height;
    ctx.fillStyle = config.black_color; ctx.fillRect(bx, by, bw, bh);
    ctx.fillStyle = config.white_color; ctx.fillRect(bx, by + bh * (1 - whiteShare), bw, bh * whiteShare);
    ctx.strokeStyle = '#11111188'; ctx.lineWidth = 3; ctx.strokeRect(bx, by, bw, bh);
    text(Math.abs(shownScore).toFixed(1), bx + bw / 2, shownScore < 0 ? by + 29 : by + bh - 14,
      config.score_font_size, shownScore < 0 ? '#ffffff' : config.score_text_color, 700, 'center');
    if (!position) {
      pawn(bx + bw / 2, by - 82, 46);
      pawn(bx + bw / 2, by + bh + 22, 46, true);
    }
  }
  function outro(options) {
    const elapsed = options.t || 0, duration = options.duration || 12;
    const counts = options.counts || {}, sides = options.sides || {black:'Janice', white:'Tony'};
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#262421'; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#302e2b'; ctx.beginPath(); ctx.roundRect(646, 210, 1122, 790, 24); ctx.fill();
    text('GAME REVIEW', 1208, 112, 72, '#f7f7f7', 800, 'center');
    text(`${sides.black} vs ${sides.white} · ${options.subtitle || 'Family dinner'}`, 1208, 166, 32, '#bcb7ae', 700, 'center');
    ctx.fillStyle = '#f7f7f7'; ctx.beginPath(); ctx.roundRect(78, 168, 472, 177, 38); ctx.fill();
    ctx.beginPath(); ctx.moveTo(242, 338); ctx.lineTo(279, 391); ctx.lineTo(324, 338); ctx.fill();
    lines('FAMILY DINNER.\nNO SURVIVORS.', 314, 239, 38, '#262421', 53, 'Arial', 'center');
    if (tonyOverlay || tony) {
      const bounce = 9 * Math.exp(-elapsed * 3) * Math.sin(elapsed * 15);
      imageContain(tonyOverlay || tony, 58, 357 + bounce, 524, 606);
    }
    pawn(1460, 222, 44); pawn(1655, 222, 44, true);
    text(sides.black, 1460, 302, 30, '#f7f7f7', 700, 'center');
    text(sides.white, 1655, 302, 30, '#f7f7f7', 700, 'center');
    const order = ['brilliant','great','best','excellent','good','book','inaccuracy','mistake','blunder'];
    for (const [i, id] of order.entries()) {
      const v = ratings[id], y = 329 + i * 53;
      if (!v) throw new Error(`Unknown official recap category: ${id}`);
      ratingIcon(v, 695, y, 41);
      text(v.label, 763, y + 32, 31, v.color, 700);
      for (const [side, x] of [['black',1460],['white',1655]]) {
        const n = counts[id]?.[side] || 0;
        text(String(n), x, y + 32, 32, n ? '#ffffff' : '#817c72', 700, 'center');
      }
    }
    ctx.fillStyle = '#555149'; ctx.fillRect(690, 879, 1034, 2);
    text('TOTAL MOVES', 763, 935, 30, '#c8c1b5', 700);
    for (const [side, x] of [['black',1460],['white',1655]]) {
      const n = order.reduce((sum, id) => sum + (counts[id]?.[side] || 0), 0);
      text(String(n), x, 935, 38, '#ffffff', 800, 'center');
    }
    text('Analysis complete. The family feud continues.', 320, 1018, 24, '#bcb7ae', 700, 'center');
    text('Music: Sneaky Snitch / Scheming Weasel (faster version) · Kevin MacLeod (incompetech.com) · Edited excerpts', W / 2, 1050, 19, '#bcb7ae', 400, 'center');
    text('Licensed under CC BY 4.0 · https://creativecommons.org/licenses/by/4.0/', W / 2, 1075, 17, '#bcb7ae', 400, 'center');
    const fade = clamp(elapsed / .35) * clamp((duration - elapsed) / .8);
    if (fade < 1) { ctx.fillStyle = `rgba(0,0,0,${1-fade})`; ctx.fillRect(0,0,W,H); }
  }
  function sourceFrame(options) {
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#171614'; ctx.fillRect(0, 0, schema.bar.gutter_width, H);
    controlBar(options.score_text ?? '0.0', options.previous_score_text ?? options.score_text ?? '0.0', options.reveal_seconds ?? .5);
    ctx.save(); ctx.translate(schema.bar.gutter_width, 0);
    if (options.evaluation) {
      const v = ratings[options.evaluation.rating];
      if (!v) throw new Error('Unknown conversation rating.');
      // The observed annotation layout: blurred/dim scene, rating top left,
      // approved pawn bottom left and a white speech bubble beside it.
      ctx.fillStyle = 'rgba(0,0,0,.52)'; ctx.fillRect(0, 0, W - schema.bar.gutter_width, H);
      const elapsed = options.reveal_seconds ?? 10, entering = clamp(elapsed / .2);
      const entryEase = 1 - Math.pow(1 - entering, 3), pop = .86 + .14 * entryEase;
      const jolt = v.id === 'blunder' && elapsed < .15 ? Math.sin(elapsed * 95) * 5 * (1 - elapsed / .15) : 0;
      ctx.save(); ctx.translate(376 + jolt, 196); ctx.scale(pop, pop); ctx.translate(-376, -196);
      ratingIcon(v, 278, 98, 196);
      ctx.restore();
      const title = v.label + (v.id === 'inaccuracy' ? '' : ' Move');
      text(title, 376, 397, 72, v.color, 700, 'center');
      if (tonyOverlay || tony) imageContain(tonyOverlay || tony, 110, 535 + 10 * (1 - entryEase), 470, 520);
      if (options.reveal_seconds == null || options.reveal_seconds >= schema.bubble_delay_seconds) {
      const bubbleEntry = 1 - Math.pow(1 - clamp((elapsed - schema.bubble_delay_seconds) / .16), 3);
      ctx.save(); ctx.translate(0, 12 * (1 - bubbleEntry)); ctx.globalAlpha = bubbleEntry;
      ctx.fillStyle = '#f7f7f7'; ctx.beginPath(); ctx.roundRect(690, 449, 895, 577, 105); ctx.fill();
      ctx.beginPath(); ctx.moveTo(704, 550); ctx.lineTo(574, 628);
      ctx.lineTo(704, 714); ctx.closePath(); ctx.fill();
      ctx.font = '700 50px Arial'; const rows = [''];
      for (const word of options.evaluation.comment.split(' ')) {
        const i = rows.length - 1;
        if (ctx.measureText((rows[i] + ' ' + word).trim()).width > 765 && rows[i]) rows.push(word);
        else rows[i] = (rows[i] + ' ' + word).trim();
      }
      if (rows.length > 8) throw new Error('Editorial comment is too long for the speech bubble.');
      const top = 738 - (rows.length - 1) * 29 + 16;
      let remaining = Math.floor(options.reveal_seconds == null ? options.evaluation.comment.length : Math.max(0, options.reveal_seconds - schema.bubble_delay_seconds) * schema.typewriter_cps);
      rows.forEach((s, i) => {
        const visible = s.slice(0, Math.max(0, remaining));
        remaining -= s.length + 1;
        ctx.font = '700 50px Arial';
        const start = 1138 - ctx.measureText(s).width / 2;
        text(visible, start, top + i * 58, 50, '#151515', 700);
      });
      ctx.restore();
      }
    }
    if (options.showSides) {
      ctx.fillStyle = 'rgba(0,0,0,.72)'; ctx.fillRect(48, 46, 1110, 70);
      const sides = options.sides || { black: 'Other speaker', white: 'Tony' };
      text(`${sides.white} is White · ${sides.black} is Black`, 72, 96, 40, '#ffffff', 700);
    }
    if (options.demo) text('Demo · synthetic source', 48, 1068, 28, '#ffffff', 700);
    if (options.low_res_preview) text(`SOURCE QUALITY PREVIEW · ${options.source_height}p source`, 1798, 44, 28, '#ffda7c', 700, 'right');
    ctx.restore();
  }
  async function load(src) {
    if (!src) return null;
    return new Promise((resolve, reject) => { const img = new Image(); img.onload = () => resolve(img); img.onerror = reject; img.src = src; });
  }
  async function init(src, backdropSrc = '', overlaySrc = '') {
    await document.fonts.ready; tony = await load(src); background = await load(backdropSrc); tonyOverlay = await load(overlaySrc);
    for (const v of schema.categories) {
      const data = window.ConversationRatingAssets?.[v.id];
      if (!data) throw new Error(`Load the official icon bytes before rendering: ${v.id}`);
      officialIcons[v.id] = await load(data);
    }
  }
  function introFrame(t) { intro(t); return canvas.toDataURL('image/png'); }
  function clipFrame(o) { if (o.phase === 'intro') intro(o.t || 0, o.intro_overlay === true); else if (o.phase === 'outro') outro(o); else sourceFrame(o); return canvas.toDataURL('image/png'); }
  function frame(t) { return introFrame(t); }
  return { init, frame, clipFrame, introFrame, width: W, height: H };
})();
