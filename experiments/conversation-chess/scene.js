// Offline conversation-review graphics. Original vector icons; approved PNG stays unchanged.
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
  function ratingIcon(v, x, y, size = 76) {
    ctx.beginPath(); ctx.arc(x + size / 2, y + size / 2, size / 2, 0, Math.PI * 2);
    ctx.fillStyle = v.color; ctx.fill();
    if (!['book', 'thumb'].includes(v.mark)) {
      text(v.mark, x + size / 2, y + size * .715, size * .65, '#ffffff', 800, 'center'); return;
    }
    ctx.save(); ctx.translate(x, y); ctx.scale(size / 72, size / 72);
    ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 3.6; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    if (v.mark === 'book') {
      ctx.beginPath(); ctx.moveTo(36, 26); ctx.quadraticCurveTo(25, 20, 16, 23);
      ctx.lineTo(16, 49); ctx.quadraticCurveTo(27, 47, 36, 53);
      ctx.quadraticCurveTo(46, 47, 56, 49); ctx.lineTo(56, 23);
      ctx.quadraticCurveTo(46, 20, 36, 26); ctx.lineTo(36, 53); ctx.stroke();
    } else {
      // Original geometric thumbs-up, distinct from a platform's artwork.
      ctx.beginPath(); ctx.moveTo(28, 49); ctx.lineTo(28, 30); ctx.lineTo(37, 20);
      ctx.quadraticCurveTo(45, 17, 43, 28); ctx.lineTo(51, 28);
      ctx.quadraticCurveTo(57, 28, 54, 35); ctx.lineTo(50, 49);
      ctx.closePath(); ctx.stroke(); ctx.strokeRect(17, 31, 8, 19);
    }
    ctx.restore();
  }
  function guideBackground() {
    ctx.clearRect(0, 0, W, H);
    if (background) imageContain(background, 0, 0, W, H);
    // Without a supplied frame this stays translucent for compositing over real footage.
    ctx.fillStyle = 'rgba(0,0,0,.79)'; ctx.fillRect(0, 0, W, H);
  }
  function symbols() {
    guideBackground();
    if (tonyOverlay || tony) imageContain(tonyOverlay || tony, 302, 12, 130, 130);
    text('Annotation Symbols Guide', 1120, 107, 65, '#f4f4f4', 700, 'center', 'monospace');
    for (const v of schema.categories) {
      const x = 36 + v.column * 960, y = 189 + v.row * 141;
      ratingIcon(v, x + 75, y, 76);
      text(v.label + (['miss','inaccuracy','interesting'].includes(v.id) ? '' : ' Move'), x + 114, y + 111,
        30, v.color, 700, 'center', 'monospace');
      lines(v.definition, x + 300, y + 36, 33, v.color, 40, 'monospace');
    }
  }
  function evaluation(t = 9) {
    guideBackground();
    text('What is the Evaluation Bar?', 1080, 120, 64, '#ffffff', 800, 'center');
    const bx = 110, by = 0, bw = 94, bh = H;
    const black = t < 10 ? .5 : .5 + .14 * clamp((t - 10) / 2);
    ctx.fillStyle = '#181818'; ctx.fillRect(bx, by, bw, bh);
    ctx.fillStyle = '#f3f3f3'; ctx.fillRect(bx, bh * black, bw, bh * (1 - black));
    ctx.strokeStyle = '#888888'; ctx.lineWidth = 2; ctx.strokeRect(bx, 1, bw, bh - 2);
    lines('The bar shows who controls the conversation: Black or White.\nThe colors identify the two sides, not who speaks first.\nEvery exchange starts equal. These are editorial judgments,\nnot calculations from a chess engine.', 1100, 254, 40, '#ffffff', 53, 'Arial', 'center');
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
  function intro(t) {
    if (t < schema.symbols_seconds) symbols(); else evaluation(t);
    if (t > schema.intro_seconds - schema.fade_seconds) {
      ctx.fillStyle = `rgba(0,0,0,${clamp((t - schema.intro_seconds + schema.fade_seconds) / schema.fade_seconds)})`;
      ctx.fillRect(0, 0, W, H);
    }
  }
  function controlBar(control, previous = control, seconds = .5) {
    const fraction = c => typeof c === 'number' ? c : ({ balanced: .5, black: .72, white: .28, tony: .72, ralph: .28 })[c] ?? .5;
    const p = clamp(seconds / .5), eased = p * p * (3 - 2 * p);
    const blackShare = fraction(previous) + (fraction(control) - fraction(previous)) * eased;
    ctx.fillStyle = '#111111'; ctx.fillRect(1800, 0, 120, H);
    ctx.fillStyle = '#eeeeee'; ctx.fillRect(1800, H * blackShare, 120, H * (1 - blackShare));
    ctx.strokeStyle = '#808080'; ctx.lineWidth = 2; ctx.strokeRect(1800, 0, 120, H);
  }
  function sourceFrame(options) {
    ctx.clearRect(0, 0, W, H); controlBar(options.control ?? .5, options.previous_control ?? options.control ?? .5, options.reveal_seconds ?? .5);
    if (options.evaluation) {
      const v = ratings[options.evaluation.rating];
      if (!v) throw new Error('Unknown conversation rating.');
      // The observed annotation layout: blurred/dim scene, rating top left,
      // approved pawn bottom left and a white speech bubble beside it.
      ctx.fillStyle = 'rgba(0,0,0,.52)'; ctx.fillRect(0, 0, 1800, H);
      ratingIcon(v, 278, 98, 196);
      const title = v.label + (['miss','inaccuracy','interesting'].includes(v.id) ? '' : ' Move');
      text(title, 376, 397, 72, v.color, 700, 'center');
      if (tonyOverlay || tony) imageContain(tonyOverlay || tony, 110, 535, 470, 520);
      if (options.reveal_seconds == null || options.reveal_seconds >= schema.bubble_delay_seconds) {
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
      }
    }
    if (options.showSides) {
      ctx.fillStyle = 'rgba(0,0,0,.72)'; ctx.fillRect(48, 46, 1110, 70);
      const sides = options.sides || { black: 'Tony', white: 'Other speaker' };
      text(`${sides.black} is Black · ${sides.white} is White`, 72, 96, 40, '#ffffff', 700);
    }
    if (options.demo) text('Demo · synthetic source', 48, 1068, 28, '#ffffff', 700);
  }
  async function load(src) {
    if (!src) return null;
    return new Promise((resolve, reject) => { const img = new Image(); img.onload = () => resolve(img); img.onerror = reject; img.src = src; });
  }
  async function init(src, backdropSrc = '', overlaySrc = '') { await document.fonts.ready; tony = await load(src); background = await load(backdropSrc); tonyOverlay = await load(overlaySrc); }
  function introFrame(t) { intro(t); return canvas.toDataURL('image/png'); }
  function clipFrame(o) { if (o.phase === 'intro') intro(o.t || 0); else sourceFrame(o); return canvas.toDataURL('image/png'); }
  function frame(t) { return introFrame(t); }
  return { init, frame, clipFrame, introFrame, width: W, height: H };
})();
