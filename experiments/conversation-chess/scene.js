// Original, silent layout study. No scene footage, dialogue recreation or external assets.
window.ConversationChess = (() => {
  const W = 1920, H = 1080;
  const C = { bg: '#161a1e', panel: '#20262b', ivory: '#f3eddf', muted: '#9ca7ae',
    line: '#38434b', teal: '#73d1ba', amber: '#e4b661', red: '#e77870', light: '#badad5' };
  const canvas = document.querySelector('canvas');
  const ctx = canvas.getContext('2d', { alpha: true });
  const clamp = v => Math.max(0, Math.min(1, v));
  const smooth = v => { v = clamp(v); return v * v * (3 - 2 * v); };
  const mix = (a, b, v) => a + (b - a) * v;
  let tony = null;

  function round(x, y, w, h, r = 22, color = C.panel, stroke = null) {
    ctx.beginPath(); ctx.roundRect(x, y, w, h, r); ctx.fillStyle = color; ctx.fill();
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 2; ctx.stroke(); }
  }
  function text(s, x, y, size, color = C.ivory, weight = 400, align = 'left', family = 'Arial') {
    ctx.font = `${weight} ${size}px ${family}`; ctx.textAlign = align;
    ctx.textBaseline = 'alphabetic'; ctx.fillStyle = color; ctx.fillText(s, x, y);
  }
  function line(x1, y1, x2, y2, color = C.line, width = 2) {
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
  }
  function dot(x, y, r, color) {
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill();
  }
  function badge(mark, x, y, color, size = 88) {
    round(x, y, size, size, size * .28, color);
    // Each label has a distinct mark: the artwork does not reuse a platform icon.
    text(mark, x + size / 2, y + size * .70, size * .55, C.bg, 800, 'center');
  }
  function pawn(x, y, scale, color, outline = C.bg) {
    ctx.save(); ctx.translate(x, y); ctx.scale(scale, scale);
    ctx.fillStyle = color; ctx.strokeStyle = outline; ctx.lineWidth = 4;
    const paths = [
      () => { ctx.beginPath(); ctx.arc(70, 32, 27, 0, 2 * Math.PI); },
      () => { ctx.beginPath(); ctx.roundRect(39, 66, 62, 16, 7); },
      () => { ctx.beginPath(); ctx.moveTo(52, 82); ctx.lineTo(88, 82); ctx.bezierCurveTo(87, 120, 98, 152, 118, 178); ctx.lineTo(22, 178); ctx.bezierCurveTo(44, 144, 53, 122, 52, 82); ctx.closePath(); },
      () => { ctx.beginPath(); ctx.roundRect(15, 177, 110, 24, 10); },
      () => { ctx.beginPath(); ctx.roundRect(7, 200, 126, 21, 9); }
    ];
    for (const path of paths) { path(); ctx.fill(); ctx.stroke(); }
    ctx.restore();
  }
  function imageContain(image, x, y, w, h) {
    const s = Math.min(w / image.width, h / image.height);
    const nw = image.width * s, nh = image.height * s;
    ctx.drawImage(image, x + (w - nw) / 2, y + h - nh, nw, nh);
  }
  function backdrop() {
    ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H);
    const g = ctx.createRadialGradient(220, 20, 20, 500, 250, 1000);
    g.addColorStop(0, 'rgba(89,141,128,.11)'); g.addColorStop(1, 'rgba(89,141,128,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    line(90, 1014, 1830, 1014);
  }
  function legend(t) {
    backdrop();
    // The first frame already carries the headline; only the cards ease in.
    ctx.save();
    text('THE CONVERSATION, REVIEWED.', 112, 123, 27, C.teal, 700);
    text('Every line is a move.', 106, 231, 92, C.ivory, 800);
    text('A quick guide before the first exchange.', 112, 290, 32, C.muted);
    const items = [
      { name: 'Brilliant', mark: '!!', color: C.teal,
        a: 'Turns pressure into', b: 'an unexpected advantage.' },
      { name: 'Best', mark: '!', color: C.light,
        a: 'The strongest response', b: 'in the moment.' },
      { name: 'Mistake', mark: '?', color: C.amber,
        a: 'Gives up ground', b: 'without gaining much back.' },
      { name: 'Blunder', mark: '??', color: C.red,
        a: 'Hands the other side', b: 'control of the exchange.' }
    ];
    items.forEach((v, i) => {
      const x = 112 + (i % 2) * 874, y = 354 + Math.floor(i / 2) * 231;
      const pop = smooth((t - .2 - i * .1) / .4);
      ctx.save(); ctx.globalAlpha *= pop; ctx.translate(0, 16 * (1 - pop));
      round(x, y, 842, 200, 24, C.panel);
      badge(v.mark, x + 27, y + 30, v.color, 90);
      text(v.name, x + 145, y + 67, 45, v.color, 800);
      text(v.a, x + 145, y + 115, 32, C.ivory);
      text(v.b, x + 145, y + 158, 32, C.ivory);
      ctx.restore();
    });
    line(112, 857, 1800, 857);
    text('The bar tracks control of the conversation.', 112, 922, 43, C.ivory, 600);
    text('Editorial labels. Context matters.', 112, 973, 25, C.muted);
    ctx.restore();
  }
  function controlBar(t, control = null) {
    const x = 1559, y = 177, w = 251, h = 805;
    round(x, y, w, h, 26, C.panel);
    text('CONTROL', x + w / 2, y + 51, 22, C.muted, 700, 'center');
    text('TONY', x + w / 2, y + 107, 32, C.ivory, 800, 'center');
    const bx = x + 88, by = y + 147, bw = 75, bh = 522;
    // A subjective visual indicator, deliberately without scores or tick values.
    const share = control ? ({ balanced: .5, tony: .72, ralph: .28 }[control] ?? .5)
      : mix(.49, .72, smooth((t - 8.5) / 1.1));
    ctx.save(); ctx.beginPath(); ctx.roundRect(bx, by, bw, bh, 15); ctx.clip();
    ctx.fillStyle = '#11171b'; ctx.fillRect(bx, by, bw, bh);
    ctx.fillStyle = C.ivory; ctx.fillRect(bx, by, bw, bh * share);
    ctx.restore();
    ctx.beginPath(); ctx.roundRect(bx, by, bw, bh, 15); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.stroke();
    const indicator = by + bh * share;
    line(bx - 11, indicator, bx + bw + 11, indicator, C.teal, 6);
    dot(bx + bw + 11, indicator, 5, C.teal);
    text('RALPH', x + w / 2, y + 726, 32, C.muted, 800, 'center');
    text('Context, not a score.', x + w / 2, y + 771, 18, C.muted, 400, 'center');
  }
  function example(t, options = null) {
    const media = options?.media === true;
    const rating = options?.evaluation?.rating;
    const ratings = { brilliant: { name: 'BRILLIANT', mark: '!!', color: C.teal },
      best: { name: 'BEST', mark: '!', color: C.light },
      mistake: { name: 'MISTAKE', mark: '?', color: C.amber },
      blunder: { name: 'BLUNDER', mark: '??', color: C.red } };
    backdrop();
    text('CONVERSATION REVIEW', 112, 123, 27, C.teal, 700);
    if (!media || options?.demo) text('Demo', 1447, 123, 26, C.muted, 700, 'right');
    // Pure white deliberately matches the supplied avatar's white canvas.
    // Keep its pixels unchanged: no alpha extraction, tint, mask or shadow.
    round(112, 177, 1390, 580, 26, '#ffffff');
    ctx.save(); ctx.beginPath(); ctx.roundRect(112, 177, 1390, 580, 26); ctx.clip();
    if (media) {
      // The source video occupies its own area. A supplied avatar stays on white,
      // beside the footage, and cannot cover a character's face.
      ctx.clearRect(472, 177, 1030, 580);
    } else {
      // The frame intentionally says what it is; no fabricated television scene.
      text('SCENE FOOTAGE GOES HERE', 880, 371, 43, '#424b49', 700, 'center');
      text('The edit pauses on the line', 880, 432, 30, '#646c67', 400, 'center');
      text('that changes the exchange.', 880, 475, 30, '#646c67', 400, 'center');
    }
    ctx.restore();
    // Tony image is an optional supplied PNG. The fallback is an original neutral pawn.
    if (tony) imageContain(tony, 132, 228, media ? 310 : 388, 508);
    else {
      pawn(171, 361, 1.58, '#f4edde', '#35443e');
      text('TONY', 283, 742, 23, '#424b49', 800, 'center');
    }
    if (!media) {
      pawn(1244, 459, .9, '#374743', '#27352f');
      text('RALPH', 1307, 715, 23, '#424b49', 800, 'center');
    }
    controlBar(t, options?.control);
    const inComment = media ? (options.evaluation ? 1 : 0) : smooth((t - 8.1) / .45);
    ctx.save(); ctx.globalAlpha = inComment; ctx.translate(0, 16 * (1 - inComment));
    round(112, 799, 1390, 183, 25, C.panel);
    const selected = ratings[rating] || ratings.brilliant;
    badge(selected.mark, 139, 832, selected.color, 108);
    text(selected.name, 280, 849, 23, selected.color, 800);
    const comment = options?.evaluation?.comment || 'Returned to sender.';
    ctx.font = '700 58px Arial';
    const lines = [''];
    for (const word of comment.split(' ')) {
      const last = lines.length - 1;
      if (ctx.measureText((lines[last] + ' ' + word).trim()).width > 1140 && lines[last]) lines.push(word);
      else lines[last] = (lines[last] + ' ' + word).trim();
    }
    if (lines.length > 2) throw new Error('Editorial comment must fit in two lines. Shorten it.');
    lines.forEach((s, i) => text(s, 276, (lines.length === 1 ? 927 : 897) + i * 64, 58, C.ivory, 700));
    ctx.restore();
    if (!media && inComment < 1) {
      ctx.save(); ctx.globalAlpha = 1 - inComment;
      text('Pause. Read the move.', 112, 878, 53, C.ivory, 700);
      text('An example of the overlay, not a finished scene.', 112, 933, 27, C.muted);
      ctx.restore();
    }
    if (!media || options?.demo) text('Demo · layout preview', 112, 1055, 20, C.muted);
    if (!media) text('NO VOICEOVER', 1809, 1055, 20, C.muted, 600, 'right');
  }
  async function init(src) {
    await document.fonts.ready;
    if (src) {
      tony = await new Promise((resolve, reject) => {
        const image = new Image(); image.onload = () => resolve(image); image.onerror = reject; image.src = src;
      });
    }
  }
  function frame(t) {
    if (t < 6) legend(t);
    else if (t < 6.5) {
      // Side-by-side slide avoids unreadable text superimposed by a crossfade.
      const progress = smooth((t - 6) / .5);
      ctx.save(); ctx.translate(-progress * W, 0); legend(6); ctx.restore();
      ctx.save(); ctx.translate((1 - progress) * W, 0); example(t); ctx.restore();
    }
    else example(t);
    return canvas.toDataURL('image/png');
  }
  function clipFrame(options) {
    if (options.phase === 'intro') legend(2);
    else sourceFrame(options);
    return canvas.toDataURL('image/png');
  }
  function sourceFrame(options) {
    backdrop();
    const freeze = Boolean(options.evaluation);
    const source = freeze ? [72,72,1280,720] : [72,72,1600,900];
    ctx.clearRect(...source);
    const control = options.control || 'balanced';
    const share = { balanced: .5, tony: .72, ralph: .28 }[control] ?? .5;
    const bx = freeze ? 1851 : 1786, by = freeze ? 210 : 230;
    const bw = freeze ? 28 : 40, bh = freeze ? 450 : 600;
    round(bx, by, bw, bh, 10, '#0f1519', C.line);
    ctx.save(); ctx.beginPath(); ctx.roundRect(bx, by, bw, bh, 10); ctx.clip();
    ctx.fillStyle = C.ivory; ctx.fillRect(bx, by, bw, bh * share); ctx.restore();
    line(bx - 6, by + bh * share, bx + bw + 6, by + bh * share, C.teal, 4);
    text('TONY', bx + bw / 2, by - 25, freeze ? 19 : 27, C.ivory, 700, 'center');
    text('RALPH', bx + bw / 2, by + bh + 39, freeze ? 18 : 26, C.muted, 700, 'center');
    if (!freeze) {
      round(1736, 28, 140, 140, 16, '#ffffff');
      if (tony) imageContain(tony, 1740, 32, 132, 132);
    } else {
      round(1400, 72, 418, 720, 24, '#ffffff');
      if (tony) imageContain(tony, 1420, 244, 376, 430);
      const labels = { brilliant: ['BRILLIANT','!!',C.teal], best: ['BEST','!',C.light],
        mistake: ['MISTAKE','?',C.amber], blunder: ['BLUNDER','??',C.red] };
      const [label, mark, color] = labels[options.evaluation.rating];
      round(72, 832, 1280, 180, 24, C.panel);
      badge(mark, 96, 866, color, 100);
      text(label, 224, 881, 24, color, 800);
      ctx.font = '700 51px Arial'; const rows = [''];
      for (const word of options.evaluation.comment.split(' ')) {
        const i = rows.length - 1;
        if (ctx.measureText((rows[i] + ' ' + word).trim()).width > 1080 && rows[i]) rows.push(word);
        else rows[i] = (rows[i] + ' ' + word).trim();
      }
      if (rows.length > 2) throw new Error('Editorial comment is too long.');
      rows.forEach((s, i) => text(s, 222, (rows.length === 1 ? 954 : 930) + i * 58, 51, C.ivory, 700));
    }
    if (options.demo) text('Demo', 72, 1053, 23, C.muted, 700);
  }
  return { init, frame, clipFrame, width: W, height: H };
})();
