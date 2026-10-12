/* TubeForge — interface (vanilla JS, aucune compilation) */
'use strict';

// ------------------------------------------------------------------ utilitaires
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const h = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const fmtTime = (s) => { s = Math.max(0, Math.round(s || 0)); const m = Math.floor(s / 60); return `${m}:${String(s % 60).padStart(2, '0')}`; };
const fmtDate = (ts) => new Date(ts * 1000).toLocaleString('en-US', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
const words = (t) => (t || '').trim().split(/\s+/).filter(Boolean).length;
const backendBase = window.TUBEFORGE_BASE || '';
const backendPath = path => backendBase && !path.startsWith(backendBase + '/') ? backendBase + path : path;
const media = (pid, rel) => backendPath(`/media/${pid}/${rel}`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function api(path, opts = {}) {
  const o = { method: opts.method || (opts.body !== undefined ? 'POST' : 'GET'), headers: {} };
  if (opts.form) o.body = opts.form;
  else if (opts.body !== undefined) { o.body = JSON.stringify(opts.body); o.headers['Content-Type'] = 'application/json'; }
  const r = await fetch(backendPath(path), o);
  let data = null;
  try { data = await r.json(); } catch { /* vide */ }
  if (!r.ok) throw new Error((data && data.detail) || `Error ${r.status}`);
  return data;
}

function toast(msg, err = false) {
  const t = h(`<div class="toast ${err ? 'err' : ''}">${esc(msg)}</div>`);
  $('#toasts').append(t);
  setTimeout(() => t.remove(), err ? 7000 : 3500);
}
async function guard(fn, okMsg) {
  try { const r = await fn(); if (okMsg) toast(okMsg); return r; } catch (e) { toast(e.message, true); return null; }
}

function modal(html, { wide = false } = {}) {
  const bg = h(`<div class="modal-bg"><div class="modal ${wide ? 'wide' : ''}">${html}</div></div>`);
  const close = () => bg.remove();
  bg.addEventListener('mousedown', (e) => { if (e.target === bg) close(); });
  document.body.append(bg);
  $$('[data-close]', bg).forEach((b) => b.addEventListener('click', close));
  return { el: $('.modal', bg), close };
}
function lightbox(src) {
  const bg = h(`<div class="modal-bg lightbox"><img src="${src}"></div>`);
  bg.addEventListener('click', () => bg.remove());
  document.body.append(bg);
}
function askText(title, placeholder = '', value = '') {
  return new Promise((resolve) => {
    const m = modal(`<h2>${esc(title)}</h2><textarea id="ask" placeholder="${esc(placeholder)}">${esc(value)}</textarea>
      <div class="row end" style="margin-top:12px"><button data-close>Cancel</button><button class="primary" id="ok">Confirm</button></div>`);
    $('#ask', m.el).focus();
    $('#ok', m.el).onclick = () => { const v = $('#ask', m.el).value.trim(); m.close(); resolve(v || null); };
    $$('[data-close]', m.el).forEach((b) => b.addEventListener('click', () => resolve(null)));
  });
}

function setPath(obj, path, value) {
  const keys = path.split('.');
  let o = obj;
  keys.slice(0, -1).forEach((k) => { o[k] = o[k] || {}; o = o[k]; });
  o[keys.at(-1)] = value;
  return obj;
}
function getPath(obj, path) { return path.split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj); }
function fieldValue(inp) {
  if (inp.type === 'checkbox') return inp.checked;
  if (inp.type === 'number' || inp.type === 'range') return inp.value === '' ? null : parseFloat(inp.value);
  return inp.value;
}
/** Associe chaque [data-k] à onChange(objetPartiel). */
function bindFields(root, onChange) {
  $$('[data-k]', root).forEach((inp) => {
    inp.addEventListener('change', () => onChange(setPath({}, inp.dataset.k, fieldValue(inp)), inp));
    if (inp.dataset.live) {
      inp.addEventListener('input', () => { const o = $(`[data-out="${inp.dataset.live}"]`, root); if (o) o.textContent = (+inp.value).toFixed(1); });
    }
  });
}

const LANGUAGES = [['English', 'Anglais'], ['French', "French"], ['Spanish', 'Espagnol'], ['German', 'Allemand'],
  ['Italian', 'Italien'], ['Portuguese', 'Portugais'], ['Arabic', 'Arabe']];
/** Devine la langue d'un titre (français si mots/accents typiques). */
function guessLanguage(t) {
  if (!t || t.length < 6) return null;
  if (/[àâçéèêëîïôûùœ]/i.test(t) || /\b(le|la|les|un|une|des|du|ta|ton|tes|tu|dans|pour|qui|vie|chaque|comme|est|sont|avec)\b/i.test(t)) return 'French';
  if (/\b(the|you|your|you're|a|an|of|in|at|during|life|every)\b/i.test(t)) return 'English';
  return null;
}
const LOG_ICONS = { step: '▸', ok: '✓', warn: '⚠', error: '✗', api: '·', info: '•' };
function logLines(lines) {
  return (lines || []).map((l) => `<div class="ll lv-${l.l}"><span class="lt">${new Date(l.t * 1000).toLocaleTimeString('en-US')}</span>${esc(l.m)}</div>`).join('');
}
const elapsed = (t) => fmtTime(Date.now() / 1000 - t);

const IMAGE_MODELS = []; // Configure through the workspace model catalog.
const ELEVEN_MODELS = []; // IDs are private runtime configuration.
const EDGE_VOICES = ['en-US-AndrewMultilingualNeural', 'en-US-BrianMultilingualNeural', 'en-US-ChristopherNeural', 'en-US-GuyNeural',
  'en-US-EricNeural', 'en-GB-RyanNeural', 'en-US-AvaMultilingualNeural', 'en-US-EmmaMultilingualNeural',
  'fr-FR-RemyMultilingualNeural', 'fr-FR-VivienneMultilingualNeural', 'fr-FR-HenriNeural', 'fr-FR-DeniseNeural'];
const MOTIONS = [['zoom_in', 'Zoom avant'], ['zoom_out', "Zoom out"], ['pan_left', 'Pan gauche'], ['pan_right', 'Pan droite'],
  ['pan_up', 'Pan haut'], ['pan_down', 'Pan bas'], ['static', 'Fixe']];
const opts = (list, cur) => list.map((x) => {
  const [v, l] = Array.isArray(x) ? x : [x, x];
  return `<option value="${esc(v)}" ${String(v) === String(cur) ? 'selected' : ''}>${esc(l)}</option>`;
}).join('');

let STATE = { has_elevenlabs: false };
let elevenVoicesCache = null;
let localInfoCache = null;
async function localInfo(force = false) {
  if (!localInfoCache || force) localInfoCache = await api('/api/local-tts').catch(() => ({ installed: false, voices: [] }));
  return localInfoCache;
}
async function elevenVoices() {
  if (!STATE.has_elevenlabs) return [];
  if (!elevenVoicesCache) elevenVoicesCache = await api('/api/elevenlabs/voices').catch(() => []);
  return elevenVoicesCache;
}

// ------------------------------------------------------------------ statistiques globales
async function pollStats() {
  try {
    STATE = await api('/api/state');
    const s = STATE.stats;
    const slots = Math.max(s.limits.image, 1);
    const img = Math.min(s.image.active, slots);
    const txt = Math.min(s.llm.active, slots - img);
    const dots = Array.from({ length: slots }, (_, i) => `<i class="${i < img ? 'img' : i < img + txt ? 'txt' : ''}"></i>`).join('');
    $('#stats').innerHTML = `
      <div class="slots" title="In-flight requests to the proxy (1 per account)">${dots}</div>
      <div>Images : <b>${s.image.active}</b>/${s.limits.image} in progress</div>
      <div>Make: <b>${s.image.done}</b>${s.image.errors ? ` · <span style="color:var(--err)">${s.image.errors} err.</span>` : ''}
        ${s.image.avg_seconds ? ` · ~${Math.round(s.image.avg_seconds)}s/img` : ''}</div>
      <div>Text: <b>${s.llm.active}</b>/${s.limits.llm} in progress</div>
      <div>Active projects: <b>${STATE.running.length}</b></div>
      ${STATE.has_algrow ? "<div style=\"margin-top:6px\">Voice: Algrow configure</div>" : STATE.has_elevenlabs ? '' : "<div style=\"color:var(--warn);margin-top:6px\">Voice provider to configure</div>"}`;
  } catch { $('#stats').textContent = 'Serveur injoignable'; }
}
setInterval(pollStats, 3000);

// ------------------------------------------------------------------ routeur
let cleanup = null;
async function route() {
  if (cleanup) { try { cleanup(); } catch { /* */ } cleanup = null; }
  const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  const el = $('#view');
  const nav = parts[0] === 'p' ? 'projects' : (parts[0] || 'home');
  $$('.nav a').forEach((a) => a.classList.toggle("active", a.dataset.nav === nav));
  el.innerHTML = '<div class="empty"><span class="spin"></span></div>';
  try {
    if (!parts.length) cleanup = await viewHome(el);
    else if (parts[0] === 'projects') cleanup = await viewProjects(el);
    else if (parts[0] === 'p') cleanup = await viewProject(el, parts[1], parts[2]);
    else if (parts[0] === 'batch') cleanup = await viewBatch(el);
    else if (parts[0] === 'planning') cleanup = await viewPlanning(el, parts[1]);
    else if (parts[0] === 'voices') cleanup = await viewVoices(el);
    else if (parts[0] === 'thumbs') cleanup = await viewThumbStudio(el);
    else if (parts[0] === 'styles' && parts[1]) cleanup = await viewStyle(el, parts[1]);
    else if (parts[0] === 'styles') cleanup = await viewStyles(el);
    else if (parts[0] === 'settings') cleanup = await viewSettings(el);
    else el.innerHTML = '<div class="empty">Page introuvable</div>';
  } catch (e) {
    el.innerHTML = `<div class="banner err">${esc(e.message)}</div>`;
  }
}
window.addEventListener('hashchange', route);

// ------------------------------------------------------------------ accueil
async function viewHome(el) {
  const [styles, chans] = await Promise.all([api('/api/styles'), api('/api/channels').catch(() => [])]);
  el.innerHTML = `
  <div class="hero">
    <h1>What are we creating today?</h1>
    <div class="card">
      <div class="small muted" style="font-weight:600;margin-bottom:10px">✨ NEW VIDEO</div>
      <div class="field"><label>Video title</label>
        <input type="text" id="title" placeholder="Type your title, or leave blank to generate one"></div>
      <label class="check" style="margin-bottom:14px"><input type="checkbox" id="autotitle"> Generate a title for me</label>
      <div class="field"><label>Format</label>
        <div class="seg" id="fmt"><button data-v="long" class="on">🎬 Long video (YouTube)</button><button data-v="short">📱 TikTok Short (1 min 30 max)</button></div></div>
      <div class="grid2">
        <div class="field"><label>Style</label><select id="style">${opts(styles.map((s) => [s.id, s.name]))}</select></div>
        <div class="field"><label>Length (words)</label><input type="number" id="words" min="100" step="100" placeholder="based on style"></div>
        <div class="field"><label>Format</label><select id="aspect"><option value="">based on style</option><option>16:9</option><option>9:16</option></select></div>
        <div class="field"><label>Video language <span id="langhint" class="muted" style="text-transform:none"></span></label>
          <select id="lang"><option value="">based on style</option>${opts(LANGUAGES)}</select></div>
      </div>
      <div class="field" id="chanrow" hidden><label>📅 TikTok channel (language, voice, publishing schedule)</label>
        <select id="chan"><option value="">— none —</option>${opts(chans.map((c) => [c.id, `${c.emoji} ${c.name}`]))}</select></div>
      <div class="field" id="promorow"><label>📣 TikTok ad Shorts created automatically at the end (teaser → YouTube)</label>
        <select id="promo" style="width:auto"><option value="0">None</option><option value="1">1 ad short</option><option value="2">2 ad shorts</option><option value="3">3 ad shorts</option></select>
        <select id="promochan" style="width:auto"><option value="">no channel</option>${opts(chans.map((c) => [c.id, `→ ${c.emoji} ${c.name}`]), (chans.find((c) => c.kind === 'promo') || {}).id)}</select>
        <span class="small muted">&nbsp;cliffhanger + “full video on YouTube” + end screen with the thumbnail</span></div>
      <div class="field" id="charsel"></div>
      <div class="field"><label>Reference YouTube video (context, optional)</label>
        <input type="url" id="url" placeholder="https://www.youtube.com/watch?v=…"></div>
      <div class="field"><label>Context / instructions (optional)</label>
        <textarea id="topic" placeholder="Angle, audience, facts to include, things to avoid…" style="min-height:60px"></textarea></div>
      <div class="field"><label>Mode</label>
        <div class="seg" id="mode"><button data-v="auto" class="on">⚡ Auto — from A to Z</button><button data-v="review">👀 Review — I approve prompts & images</button></div>
      </div>
      <div class="row">
        <button id="upload">⬆ Import a script</button>
        <span id="scriptinfo" class="muted small"></span>
        <span class="spacer"></span>
        <button class="primary" id="create">Create video →</button>
      </div>
    </div>
    <div class="tools">
      <a class="card tool" href="#/planning"><div class="ico">📅</div><b>TikTok planning</b><div class="muted small">Your channels, 2-3 posts per day prepared in advance.</div></a>
      <a class="card tool" href="#/batch"><div class="ico">📄</div><b>CSV batch</b><div class="muted small">30 videos at once, spread across the 36 accounts.</div></a>
      <a class="card tool" href="#/thumbs"><div class="ico">🖼️</div><b>Thumbnail studio</b><div class="muted small">Eye-catching thumbnails, without creating a video.</div></a>
      <a class="card tool" href="#/projects"><div class="ico">🎞️</div><b>Projects</b><div class="muted small">All your videos, in progress and archived.</div></a>
      <a class="card tool" href="#/styles"><div class="ico">🎨</div><b>Styles</b><div class="muted small">Writing tone, voice, image style, characters.</div></a>
      <a class="card tool" href="#/settings"><div class="ico">⚙️</div><b>Settings</b><div class="muted small">API keys, models, parallelism.</div></a>
    </div>
    <div id="live" style="margin-top:26px"></div>
  </div>`;
  const live = async () => {
    const ps = await api('/api/projects?archived=0').catch(() => []);
    const running = ps.filter((p) => Object.values(p.steps).some((s) => s.state === 'running'));
    const recent = ps.filter((p) => !running.includes(p)).slice(0, 4);
    const box = $('#live', el);
    if (!box) return;
    box.innerHTML = (running.length ? `<h2>⚙️ En production (${running.length})</h2><div class="card" style="padding:6px 14px">${running.map((p) => {
      const [k, s] = Object.entries(p.steps).find(([, x]) => x.state === 'running');
      const pct = s.total ? Math.round(100 * s.done / s.total) : 0;
      return `<a class="liverow" href="#/p/${p.id}"><span class="lthumb" style="${p.thumb ? `background-image:url('${media(p.id, p.thumb)}')` : ''}"></span>
        <span style="flex:1;min-width:0"><b>${esc(p.title)}</b><span class="small muted" style="display:block">${esc(s.msg || k)}${s.started ? ` · ⏱ ${elapsed(s.started)}` : ''}</span>
        ${p.last_log ? `<span class="small mono" style="display:block;opacity:.75;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(p.last_log)}</span>` : ''}
        <span class="bar" style="display:block;margin-top:6px"><div style="width:${pct}%"></div></span></span><span class="muted small">${s.total ? `${pct}%` : ''}</span></a>`;
    }).join('')}</div>` : '')
      + (recent.length ? `<h2 style="margin-top:22px">Recent</h2><div class="grid3">${recent.map((p) => `
        <a class="card pcard" href="#/p/${p.id}"><span class="thumb" style="${p.thumb ? `background-image:url('${media(p.id, p.thumb)}')` : ''}"></span>
        <div class="body"><b class="title">${esc(p.title)}</b><div class="row small muted">${fmtDate(p.created)}<span class="spacer"></span>${featureBadge(p.features)}</div></div></a>`).join('')}</div>` : '');
  };
  live();
  const lt = setInterval(live, 3000);
  let mode = 'auto';
  let format = 'long';
  let customScript = '';
  $$('#fmt button', el).forEach((b) => b.onclick = () => {
    format = b.dataset.v; $$('#fmt button', el).forEach((x) => x.classList.toggle('on', x === b));
    $('#words', el).placeholder = format === 'short' ? '190 (≈ 1 min 15)' : "according to style";
    $('#aspect', el).disabled = format === 'short';
    $('#promorow', el).hidden = format === 'short';
    $('#chanrow', el).hidden = format !== 'short';
  });
  $('#chan', el).addEventListener('change', () => {
    const c = chans.find((x) => x.id === $('#chan', el).value);
    if (c) { $('#lang', el).value = c.language; $('#style', el).value = c.style_id; $('#langhint', el).textContent = "(channel)"; }
  });
  const syncPromo = () => {
    const st = styles.find((x) => x.id === $('#style', el).value) || styles[0];
    $('#promo', el).value = String((st && st.shorts && st.shorts.promo_count) || 0);
  };
  $('#style', el).addEventListener('change', syncPromo);
  syncPromo();
  const renderCharSel = () => {
    const st = styles.find((x) => x.id === $('#style', el).value) || styles[0];
    const cs = (st && st.characters) || [];
    $('#charsel', el).innerHTML = cs.length ? `<label>Permanent characters in this video</label><div class="row">${cs.map((c) => `
      <label class="charpick ${c.auto_include ? 'on' : ''}" title="${esc(c.description)}">
        <input type="checkbox" value="${esc(c.id)}" ${c.auto_include ? 'checked' : ''}>
        ${c.image ? `<img src="${backendBase}/style-media/${st.id}/${c.image}">` : ''}<b>${esc(c.name)}</b></label>`).join('')}</div>` : '';
    $$('#charsel input', el).forEach((i) => i.addEventListener('change', () => i.parentElement.classList.toggle('on', i.checked)));
  };
  $('#style', el).addEventListener('change', renderCharSel);
  renderCharSel();
  $$('#mode button', el).forEach((b) => b.onclick = () => {
    mode = b.dataset.v; $$('#mode button', el).forEach((x) => x.classList.toggle('on', x === b));
  });
  let langTouched = false;
  $('#lang', el).addEventListener('change', () => { langTouched = true; $('#langhint', el).textContent = ''; });
  $('#title', el).addEventListener('input', () => {
    $('#autotitle', el).checked = !$('#title', el).value.trim();
    const g = guessLanguage($('#title', el).value);
    if (g && !langTouched) { $('#lang', el).value = g; $('#langhint', el).textContent = "(detected)"; }
  });
  $('#autotitle', el).checked = true;
  $('#upload', el).onclick = () => {
    const m = modal(`<h2>Import a script</h2><p class="muted">Paste your text or upload a .txt file — the Script step will be skipped.</p>
      <textarea id="st" style="min-height:300px">${esc(customScript)}</textarea>
      <div class="row" style="margin-top:10px"><input type="file" id="sf" accept=".txt,text/plain"><span class="spacer"></span>
      <button data-close>Cancel</button><button class="primary" id="ok">Use this script</button></div>`, { wide: true });
    $('#sf', m.el).onchange = async (e) => { const f = e.target.files[0]; if (f) $('#st', m.el).value = await f.text(); };
    $('#ok', m.el).onclick = () => {
      customScript = $('#st', m.el).value.trim();
      $('#scriptinfo', el).textContent = customScript ? `Script imported: ${words(customScript)} words` : '';
      m.close();
    };
  };
  $('#create', el).onclick = async () => {
    const btn = $('#create', el); btn.disabled = true;
    const p = await guard(() => api('/api/projects', { body: {
      title: $('#autotitle', el).checked && !$('#title', el).value.trim() ? '' : $('#title', el).value.trim(),
      style_id: $('#style', el).value, word_count: $('#words', el).value || null, aspect: $('#aspect', el).value || null,
      language: $('#lang', el).value || null,
      characters: $$('#charsel input', el).filter((i) => i.checked).map((i) => i.value),
      format,
      promo_shorts: format === 'long' ? +$('#promo', el).value : 0,
      channel_id: format === 'short' ? ($('#chan', el).value || null) : ($('#promochan', el).value || null),
      video_url: $('#url', el).value.trim(), topic: $('#topic', el).value.trim(), mode, custom_script: customScript,
    } }));
    btn.disabled = false;
    if (p) location.hash = `#/p/${p.id}`;
  };
  return () => clearInterval(lt);
}

// ------------------------------------------------------------------ projets
const FEATURE_LABELS = { title: "Title", script: 'Script', voice: "Voice", visuals: "Visuals", render: "Video", thumbnail: "Thumbnail" };
function featureBadge(f) {
  const done = Object.values(f).filter(Boolean).length;
  const tip = Object.entries(FEATURE_LABELS).map(([k, l]) => `${f[k] ? '✅' : '⬜'} ${l}`).join('<br>');
  return `<span class="chip badge ${done === 6 ? 'ok' : ''}">${done}/6<span class="tip">${tip}</span></span>`;
}
function statusChip(p) {
  const run = Object.entries(p.steps).find(([, s]) => s.state === 'running');
  if (run) {
    const [k, s] = run;
    const pct = s.total ? ` ${Math.round(100 * s.done / s.total)}%` : '';
    return `<span class="chip run"><span class="spin"></span>${esc(s.msg || k)}${pct}</span>`;
  }
  if (p.error) return `<span class="chip err" title="${esc(p.error)}">⚠ ${esc(p.error.length > 48 ? `${p.error.slice(0, 48)}…` : p.error)}</span>`;
  if (p.render) return '<span class="chip">Export available - needs review</span>';
  const waiting = Object.values(p.steps).find((s) => s.msg && s.state !== 'error');
  if (waiting) return `<span class="chip warn">${esc(waiting.msg.slice(0, 40))}</span>`;
  return "<span class=\"chip\">Draft</span>";
}

async function viewProjects(el) {
  let archived = 0;
  let layout = localStorage.getItem('layout') || 'grid';
  el.innerHTML = `
    <div class="row" style="margin-bottom:16px"><h1 style="margin:0">Projects</h1><span class="spacer"></span>
      <div class="seg" id="tabs"><button data-v="0" class="on">Active</button><button data-v="1">Archived</button></div>
      <div class="seg" id="layout"><button data-v="grid">▦</button><button data-v="list">☰</button></div>
      <a class="btn primary" href="#/">+ New video</a></div>
    <div id="list"></div>`;
  const list = $('#list', el);
  let openMenu = null;
  const render = (ps) => {
    if (!ps.length) { list.innerHTML = `<div class="empty">${archived ? "No archived projects." : "No projects yet. <a href=\"#/\">Create your first video</a>."}</div>`; return; }
    if (layout === 'grid') {
      list.innerHTML = `<div class="grid3">${ps.map((p) => `
        <div class="card pcard" data-id="${p.id}">
          <a class="thumb" href="#/p/${p.id}" style="${p.thumb ? `background-image:url('${media(p.id, p.thumb)}')` : ''}"></a>
          <button class="sm menu-btn" data-menu="${p.id}">⋯</button>
          <div class="body"><a class="title" href="#/p/${p.id}">${p.kind === 'promo' ? '<span class="chip warn">📣 Pub</span> ' : p.format === 'short' ? '<span class="chip run">📱 TikTok</span> ' : ''}${p.slot ? `<span class="chip" title="Publishing slot">${p.posted ? '📤' : '🗓'} ${esc(p.slot.slice(5, 10).split('-').reverse().join('/'))} ${esc(p.slot.slice(11))}</span> ` : ''}${esc(p.title)}</a>
            <div class="row small muted">${fmtDate(p.created)}${p.duration ? ` · ${fmtTime(p.duration)}` : ''}<span class="spacer"></span>${featureBadge(p.features)}</div>
            <div>${statusChip(p)}</div></div>
        </div>`).join('')}</div>`;
    } else {
      list.innerHTML = `<div class="card" style="padding:0"><table class="list"><tr><th></th><th>Title</th><th>Date</th><th>Duration</th><th>Progress</th><th>Status</th><th></th></tr>
        ${ps.map((p) => `<tr data-id="${p.id}"><td>${p.thumb ? `<img src="${media(p.id, p.thumb)}">` : ''}</td>
          <td><a href="#/p/${p.id}"><b>${esc(p.title)}</b></a></td><td class="small">${fmtDate(p.created)}</td>
          <td>${p.duration ? fmtTime(p.duration) : '–'}</td><td>${featureBadge(p.features)}</td><td>${statusChip(p)}</td>
          <td style="position:relative"><button class="sm" data-menu="${p.id}">⋯</button></td></tr>`).join('')}</table></div>`;
    }
  };
  let current = [];
  const load = async () => {
    if (openMenu) return;
    current = await api(`/api/projects?archived=${archived}`);
    render(current);
  };
  list.addEventListener('click', async (e) => {
    const mb = e.target.closest('[data-menu]');
    if (!mb) return;
    e.preventDefault();
    if (openMenu) { openMenu.remove(); openMenu = null; }
    const p = current.find((x) => x.id === mb.dataset.menu);
    const menu = h(`<div class="menu">
      <button data-a="edit">✏️ Open</button><button data-a="dup">📑 Duplicate</button>
      ${p.render ? "<button data-a=\"video\">⬇ Download video</button>" : ''}
      ${p.thumb ? "<button data-a=\"thumb\">🖼 Download thumbnail</button>" : ''}
      <button data-a="arch">${p.archived ? "📤 Unarchive" : '📦 Archiver'}</button>
      <button data-a="del" class="danger">🗑 Delete</button></div>`);
    mb.parentElement.append(menu);
    openMenu = menu;
    menu.addEventListener('click', async (ev) => {
      const a = ev.target.closest('[data-a]')?.dataset.a;
      if (!a) return;
      menu.remove(); openMenu = null;
      if (a === 'edit') location.hash = `#/p/${p.id}`;
      if (a === 'dup') await guard(() => api(`/api/projects/${p.id}/duplicate`, { body: {} }), "Project duplicated");
      if (a === 'video') location.href = `/download/${p.id}`;
      if (a === 'thumb') location.href = `/download/${p.id}?what=thumb`;
      if (a === 'arch') await guard(() => api(`/api/projects/${p.id}`, { method: 'PATCH', body: { archived: !p.archived } }));
      if (a === 'del' && confirm(`Permanently delete “ ${p.title} ” and all its files?`)) await guard(() => api(`/api/projects/${p.id}`, { method: 'DELETE' }), "Project deleted");
      load();
    });
  });
  const closeMenu = (e) => { if (openMenu && !e.target.closest('.menu') && !e.target.closest('[data-menu]')) { openMenu.remove(); openMenu = null; } };
  document.addEventListener('click', closeMenu);
  $$('#tabs button', el).forEach((b) => b.onclick = () => { archived = +b.dataset.v; $$('#tabs button', el).forEach((x) => x.classList.toggle('on', x === b)); load(); });
  const setLayout = () => $$('#layout button', el).forEach((x) => x.classList.toggle('on', x.dataset.v === layout));
  $$('#layout button', el).forEach((b) => b.onclick = () => { layout = b.dataset.v; localStorage.setItem('layout', layout); setLayout(); render(current); });
  setLayout();
  await load();
  const t = setInterval(load, 4000);
  return () => { clearInterval(t); document.removeEventListener('click', closeMenu); };
}

// ------------------------------------------------------------------ builder
const TABS = [['script', 'Script'], ['voice', "Voice-over"], ['visuals', "Visuals"], ['render', "Render"], ['thumbs', "Thumbnails"]];
const TAB_STEP = { script: 'script', voice: 'voiceover', visuals: 'visuals', render: 'render', thumbs: 'thumbnail' };

function stepProgress(st) {
  if (st.state !== 'running') return st.state === 'error' ? `<div class="banner err">${esc(st.msg)}</div>` : (st.msg ? `<div class="banner info">${esc(st.msg)}</div>` : '');
  const pct = st.total ? Math.round(100 * st.done / st.total) : 0;
  return `<div class="card inner" style="margin-bottom:14px"><div class="row"><span class="spin"></span><b>${esc(st.msg || "In progress…")}</b><span class="spacer"></span>
    ${st.started ? `<span class="muted small">⏱ ${elapsed(st.started)}</span>` : ''}<b>${st.total ? `${pct}%` : ''}</b></div>
    ${st.total ? `<div class="bar" style="margin-top:8px"><div style="width:${pct}%"></div></div>` : ''}</div>`;
}

async function viewProject(el, id, tab) {
  let p = await api(`/api/projects/${id}`);
  const defaultTab = () => (!p.script ? 'script' : !p.voiceover ? 'voice' : !p.render ? (p.scenes.every((s) => s.image) && p.scenes.length ? 'render' : 'visuals') : 'render');
  tab = tab || defaultTab();
  el.innerHTML = `
    <div class="bhead">
      <a href="#/projects" class="btn sm">←</a>
      <span class="chip">🎨 ${esc(p.style_name)}</span>
      <span class="ptitle" id="ptitle" contenteditable="true" spellcheck="false"></span>
      <span class="chip" id="modechip"></span>
      <span class="spacer"></span>
      <span id="runbtns"></span>
    </div>
    <div id="banner"></div>
    <div class="steps" id="steps"></div>
    <div class="logwrap" id="logwrap">
      <div class="row loghead"><b>📜 Journal en direct</b><span class="muted small" id="loglast"></span><span class="spacer"></span>
        <button class="sm ghost" id="logtoggle">Agrandir</button></div>
      <div class="logbox" id="logbox"></div>
    </div>
    <div id="tab"></div>`;
  const tabEl = $('#tab', el);
  let tabApi = null;

  const titleEl = $('#ptitle', el);
  titleEl.textContent = p.title || "(automatically generated title)";
  titleEl.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); titleEl.blur(); } });
  titleEl.addEventListener('blur', async () => {
    const t = titleEl.textContent.trim();
    if (t && t !== p.title) p = await guard(() => api(`/api/projects/${id}`, { method: 'PATCH', body: { title: t } })) || p;
  });

  let logCount = -1;
  const logbox = $('#logbox', el);
  let logBig = localStorage.getItem('logbig') === '1';
  const applyLogSize = () => { logbox.classList.toggle('big', logBig); $('#logtoggle', el).textContent = logBig ? "Collapse" : 'Agrandir'; };
  $('#logtoggle', el).onclick = () => { logBig = !logBig; localStorage.setItem('logbig', logBig ? '1' : '0'); applyLogSize(); logbox.scrollTop = logbox.scrollHeight; };
  applyLogSize();
  const renderLog = () => {
    const lines = p.log || [];
    const last = lines[lines.length - 1];
    $('#loglast', el).textContent = last ? `last activity ${elapsed(last.t)}` : "nothing yet";
    if (lines.length === logCount && lines.length < 500) return;
    const atBottom = logbox.scrollHeight - logbox.scrollTop - logbox.clientHeight < 40;
    logCount = lines.length;
    logbox.innerHTML = logLines(lines.slice(-300)) || "<div class=\"ll muted\">The log fills up as soon as a generation starts.</div>";
    if (atBottom || logCount <= 1) logbox.scrollTop = logbox.scrollHeight;
  };
  const renderHead = () => {
    renderLog();
    if (document.activeElement !== titleEl && p.title) titleEl.textContent = p.title;
    $('#modechip', el).innerHTML = p.mode === 'review' ? '👀 Review' : '⚡ Auto';
    $('#modechip', el).title = "Click to change mode";
    $('#runbtns', el).innerHTML = p.running
      ? "<button class=\"danger\" id=\"stopbtn\">■ Stop</button>"
      : `<button class="primary" id="runall">${p.render ? "↻ Retry missing items"
        : Object.values(p.steps).some((s) => s.state === 'error') || p.error ? "▶ Resume"
          : p.mode === 'review' ? '▶ Continuer' : "▶ Generate all"}</button>`;
    const rb = $('#runall', el);
    if (rb) rb.onclick = async () => { await guard(() => api(`/api/projects/${id}/run`, { body: { approve: true } }), "Generation started"); refresh(); };
    const sb = $('#stopbtn', el);
    if (sb) sb.onclick = async () => { await guard(() => api(`/api/projects/${id}/stop`, { body: {} }), "Stop requested"); refresh(); };
    $('#banner', el).innerHTML = (p.error ? `<div class="banner err">⚠ ${esc(p.error)}</div>` : '')
      + (p.voiceover_stale ? "<div class=\"banner warn\">The script has changed since the voice-over — regenerate the voice to update the scenes.</div>" : '');
    $('#steps', el).innerHTML = TABS.map(([k, label], i) => {
      const st = p.steps[TAB_STEP[k]];
      const done = k === 'visuals' ? p.features.visuals : k === 'thumbs' ? p.features.thumbnail : st.state === 'done' || (k === 'render' && p.render);
      const cls = st.state === 'running' ? 'running' : st.state === 'error' ? 'error' : done ? 'done' : '';
      const n = st.state === 'running' ? '<span class="spin" style="width:10px;height:10px"></span>' : done ? '✓' : st.state === 'error' ? '!' : i + 1;
      return `<div class="step ${cls} ${k === tab ? "active" : ''}" data-tab="${k}"><span class="n">${n}</span>${label}</div>`;
    }).join('');
  };
  $('#modechip', el).onclick = async () => {
    p = await guard(() => api(`/api/projects/${id}`, { method: 'PATCH', body: { mode: p.mode === 'review' ? 'auto' : 'review' } })) || p;
    renderHead();
  };
  $('#steps', el).addEventListener('click', (e) => {
    const s = e.target.closest('[data-tab]');
    if (s) { history.replaceState(null, '', `#/p/${id}/${s.dataset.tab}`); tab = s.dataset.tab; mountTab(); renderHead(); }
  });

  const ctx = {
    get p() { return p; },
    set p(v) { p = v; },
    id,
    async patch(body) { const np = await guard(() => api(`/api/projects/${id}`, { method: 'PATCH', body })); if (np) p = np; return np; },
    async action(path, body = {}, okMsg) { const r = await guard(() => api(`/api/projects/${id}/${path}`, { body }), okMsg); await refresh(); return r; },
    refresh: () => refresh(),
  };
  const mountTab = () => {
    tabApi = ({ script: tabScript, voice: tabVoice, visuals: tabVisuals, render: tabRender, thumbs: tabThumbs })[tab](tabEl, ctx);
  };

  let timer = null;
  let alive = true;
  const busy = () => p.running || Object.values(p.steps).some((s) => s.state === 'running')
    || p.scenes.some((s) => ['queued', 'running'].includes(s.status)) || (p.characters || []).some((c) => c.status === 'running');
  async function refresh() {
    try { p = await api(`/api/projects/${id}`); } catch { return; }
    renderHead();
    if (tabApi && tabApi.update) tabApi.update();
  }
  async function loop() {
    if (!alive) return;
    await refresh();
    timer = setTimeout(loop, busy() ? 1500 : 5000);
  }
  renderHead();
  mountTab();
  timer = setTimeout(loop, 1500);
  return () => { alive = false; clearTimeout(timer); };
}

// --- onglet Script
function tabScript(el, ctx) {
  const p = ctx.p;
  const s = p.settings.script;
  el.innerHTML = `
  <div class="two">
    <div>
      <div class="card">
        <h3>Settings</h3>
        <div class="field"><label>Target length (words)</label><input type="number" data-k="settings.script.word_count" value="${s.word_count}" step="100">
          <div class="small muted">≈ ${Math.round(s.word_count / 160)} min of narration</div></div>
        <div class="field"><label>Language</label><select data-k="settings.language">${opts(LANGUAGES, p.settings.language || 'English')}</select></div>
        <div class="field"><label>Writing mode</label><select data-k="settings.script.mode">${opts([['pro', "Pro — outline + parts (best)"], ['fast', 'Rapide']], s.mode)}</select></div>
        <div class="field"><label>Context YouTube video</label>
          <div class="row"><input type="url" id="vurl" value="${esc(p.video_url)}" placeholder="https://youtube.com/…" style="flex:1"><button class="sm" id="fetch">Fetch</button></div>
          <div class="small muted" id="ctxinfo">${p.video_context_words ? `✓ Transcript loaded (${p.video_context_words} words)` : "Optional — used as source material."}</div></div>
        <div class="field"><label>Contexte / instructions</label><textarea data-k="topic" style="min-height:90px">${esc(p.topic)}</textarea></div>
        <button class="primary" id="gen" style="width:100%;justify-content:center">${p.script ? "↻ Rewrite all" : "✨ Generate script"}</button>
      </div>
    </div>
    <div>
      <div id="prog"></div>
      <div class="card">
        <div class="row" style="margin-bottom:10px"><b id="wc"></b><span class="muted small" id="dur"></span><span class="spacer"></span>
          <button class="sm" id="hist">🕘 History</button><button class="sm" id="copy">Copy</button><a class="btn sm" href="/download/${p.id}?what=script">.txt</a>
          <button class="sm primary" id="save" disabled>Save</button></div>
        <div class="row selbar card inner" id="selbar" style="margin-bottom:10px">
          <b class="small">Selection:</b>
          <button class="sm" data-sel="regenerate">↻ Regenerate</button><button class="sm" data-sel="adjust">✎ Adjust…</button>
          <button class="sm" data-sel="shorten">− Shorten</button><button class="sm" data-sel="lengthen">+ Lengthen</button></div>
        <textarea class="editor" id="ed" placeholder="The script will appear here. You can also paste your own.">${esc(p.script)}</textarea>
      </div>
    </div>
  </div>`;
  const ed = $('#ed', el);
  let dirty = false;
  const counts = () => { const n = words(ed.value); $('#wc', el).textContent = `${n} words`; $('#dur', el).textContent = `≈ ${fmtTime(n / 160 * 60)} of voice`; };
  counts();
  bindFields(el, async (obj) => { await ctx.patch(obj); });
  const save = async () => {
    if (!dirty) return;
    const np = await guard(() => api(`/api/projects/${ctx.id}/script`, { method: 'PUT', body: { text: ed.value } }));
    if (np) { ctx.p = np; dirty = false; $('#save', el).disabled = true; }
  };
  ed.addEventListener('input', () => { dirty = true; $('#save', el).disabled = false; counts(); });
  ed.addEventListener('blur', save);
  $('#save', el).onclick = save;
  const selCheck = () => $('#selbar', el).classList.toggle('show', ed.selectionEnd - ed.selectionStart > 3);
  ['select', 'mouseup', 'keyup'].forEach((ev) => ed.addEventListener(ev, selCheck));
  $$('[data-sel]', el).forEach((b) => b.addEventListener('mousedown', (e) => e.preventDefault()));
  $$('[data-sel]', el).forEach((b) => b.onclick = async () => {
    const start = ed.selectionStart; const end = ed.selectionEnd;
    if (end - start < 3) return;
    let instruction = '';
    if (b.dataset.sel === 'adjust') { instruction = await askText("How should this passage be edited?", "e.g. more punchy, add a detail about the food…"); if (!instruction) return; }
    await save();
    b.disabled = true; b.innerHTML = '<span class="spin"></span>';
    const np = await guard(() => api(`/api/projects/${ctx.id}/script/selection`, { body: { start, end, action: b.dataset.sel, instruction } }), "Passage replaced");
    b.disabled = false; b.textContent = { regenerate: "↻ Regenerate", adjust: '✎ Ajuster…', shorten: '− Raccourcir', lengthen: '+ Allonger' }[b.dataset.sel];
    if (np) { ctx.p = np; ed.value = np.script; counts(); }
  });
  $('#gen', el).onclick = async () => {
    if (ctx.p.script && !confirm("Rewrite the whole script? (the old version stays in history; the voice and scenes will need to be redone)")) return;
    await save();
    await ctx.action('script/generate', {}, "Writing started");
  };
  $('#fetch', el).onclick = async () => {
    $('#fetch', el).disabled = true;
    const np = await guard(() => api(`/api/projects/${ctx.id}/context/fetch`, { body: { url: $('#vurl', el).value.trim() } }), "Transcript retrieved");
    $('#fetch', el).disabled = false;
    if (np) { ctx.p = np; $('#ctxinfo', el).textContent = `✓ Transcript loaded (${np.video_context_words} words)`; }
  };
  $('#copy', el).onclick = () => { navigator.clipboard.writeText(ed.value); toast("Script copied"); };
  $('#hist', el).onclick = async () => {
    const hist = await api(`/api/projects/${ctx.id}/script/history`);
    const m = modal(`<h2>Historique du script</h2><div class="two" style="grid-template-columns:260px 1fr">
      <div id="hl">${hist.map((x, i) => `<div class="history-item" data-i="${i}"><b>${esc(x.kind)}</b><div class="small muted">${fmtDate(x.ts)} · ${x.words} words (${x.delta >= 0 ? '+' : ''}${x.delta})</div></div>`).reverse().join('') || '<div class="muted">Vide</div>'}</div>
      <div><pre id="hv" style="white-space:pre-wrap;max-height:60vh">Choose a version on the left.</pre><div class="row end"><button class="primary" id="restore" disabled>Restore this version</button></div></div></div>`, { wide: true });
    let sel = null;
    $('#hl', m.el).addEventListener('click', (e) => {
      const it = e.target.closest('[data-i]'); if (!it) return;
      sel = +it.dataset.i; $('#hv', m.el).textContent = hist[sel].text; $('#restore', m.el).disabled = false;
    });
    $('#restore', m.el).onclick = async () => {
      const np = await guard(() => api(`/api/projects/${ctx.id}/script/restore`, { body: { index: sel } }), "Version restored");
      if (np) { ctx.p = np; ed.value = np.script; counts(); m.close(); }
    };
  };
  const update = () => {
    const st = ctx.p.steps.script;
    $('#prog', el).innerHTML = stepProgress(st);
    $('#gen', el).disabled = ctx.p.running;
    const live = st.state === 'running' && ctx.p.script_draft;
    ed.readOnly = st.state === 'running';
    ed.classList.toggle('writing', !!live);
    if (live) {
      if (ed.value !== ctx.p.script_draft) { ed.value = ctx.p.script_draft; counts(); ed.scrollTop = ed.scrollHeight; }
    } else if (!dirty && document.activeElement !== ed && ed.value !== (ctx.p.script || '')) { ed.value = ctx.p.script || ''; counts(); }
    $('#gen', el).textContent = ctx.p.script ? "↻ Rewrite all" : "✨ Generate script";
  };
  update();
  return { update };
}

// --- onglet Voix
function voiceFieldsHtml(v, prefix, voices, local = { installed: false, voices: [] }) {
  const list = voices.map((x) => [x.voice_id, `${x.name}${x.labels ? ` — ${x.labels}` : ''}`]);
  if (v.voice_id && !voices.some((x) => x.voice_id === v.voice_id)) list.unshift([v.voice_id, `${v.voice_name || "Custom voice"} (${v.voice_id})`]);
  const elevenSel = (list.length ? `<select data-k="${prefix}.voice_id" id="vsel">${opts(list, v.voice_id)}</select>` : '')
    + `<div class="row" style="margin-top:6px"><input type="text" id="vcustom" placeholder="…or paste the ID of one of your ElevenLabs voices" style="flex:1"><button class="sm" id="vcustomok">Use</button></div>
       <div class="small muted">${STATE.has_elevenlabs ? (voices.some((x) => x.category !== 'premade') ? '' : "Your key can’t list your voices: standard voices are offered, or paste your voice ID (Voice Library → ⋯ → Copy voice ID).") : "Add your ElevenLabs key in Settings."}</div>`;
  return `
    <div class="field"><label>Provider</label><select data-k="${prefix}.provider">${opts([['algrow', "Algrow (studio voice)"], ['local', "Local voice"], ['elevenlabs', 'ElevenLabs'], ['edge', 'Edge']], v.provider)}</select></div>
    <div data-show="algrow" ${v.provider === 'algrow' ? '' : 'hidden'}>
      <div class="field"><label>Algrow voice ID</label><input type="text" data-k="${prefix}.voice_id" value="${esc(v.voice_id || '')}"></div>
    </div>
    <div data-show="local" ${v.provider === 'local' ? '' : 'hidden'}>
      ${local.installed ? '' : "<div class=\"banner warn\">Local voice not installed.</div>"}
      <div class="field"><label>Voice (imitated reference) <span class="muted" style="text-transform:none" id="lstatus">${local.health ? `· engine ready: ${local.health.workers} process on ${esc(local.health.gpu || local.health.device)}, ${local.health.vram_gb} Go` : "· engine stopped (starts by itself)"}</span></label>
        <select data-k="${prefix}.local_voice">${opts([['', "Automatic (based on language)"], ...local.voices.map((x) => [x.id, `${ACCENT_FLAGS[x.accent] || '🎙️'} ${x.label || x.name}${x.desc ? ` — ${x.desc}` : ''}`])], v.local_voice || '')}</select>
        <a class="small" href="#/voices" style="display:inline-block;margin-top:4px">🎧 Listen to all voices</a>
        <div class="row" style="margin-top:6px"><label class="btn sm">⬆ Import my voice (10-20 s)<input type="file" accept="audio/*" hidden id="lupload"></label>
          <span class="small muted">A clean clip, with no music, in the video’s language.</span></div></div>
      <div class="field"><label>Engine</label><select data-k="${prefix}.local_engine">${opts([['auto', "Automatic — Turbo for English (×2 faster), Multilingual otherwise"], ['multilingual', 'Multilingue partout (plus expressif, plus lent)']], v.local_engine || 'auto')}</select></div>
      <div class="field"><label>Expressiveness: <span data-out="lex">${(+(v.local_exaggeration ?? 0.5)).toFixed(2)}</span></label>
        <input type="range" min="0.25" max="1.5" step="0.05" value="${v.local_exaggeration ?? 0.5}" data-k="${prefix}.local_exaggeration" data-live="lex" style="width:100%">
        <div class="row small muted" style="justify-content:space-between"><span>calm</span><span>dramatic</span></div>
        <div class="small muted">Expressiveness and fidelity: Multilingual engine only (Turbo ignores them).</div></div>
      <div class="field"><label>Reference fidelity / pacing: <span data-out="lcf">${(+(v.local_cfg ?? 0.5)).toFixed(2)}</span></label>
        <input type="range" min="0" max="1" step="0.05" value="${v.local_cfg ?? 0.5}" data-k="${prefix}.local_cfg" data-live="lcf" style="width:100%">
        <div class="small muted">Lower = slower delivery and less reference accent (useful if the reference voice is not in the video's language).</div></div>
      <div class="field"><label>Creativity: <span data-out="ltp">${(+(v.local_temperature ?? 0.8)).toFixed(2)}</span></label>
        <input type="range" min="0.4" max="1.2" step="0.05" value="${v.local_temperature ?? 0.8}" data-k="${prefix}.local_temperature" data-live="ltp" style="width:100%"></div>
    </div>
    <div data-show="elevenlabs" ${v.provider === 'elevenlabs' ? '' : 'hidden'}>
      <div class="field"><label>Voice</label>${elevenSel}</div>
      <div class="field"><label>Model</label><select data-k="${prefix}.model_id">${opts(ELEVEN_MODELS, v.model_id)}</select></div>
      <div class="field"><label>Performance</label><select data-k="${prefix}.delivery">${opts([['stable', 'Stable'], ['balanced', "Balanced"], ['creative', "Creative"]], v.delivery)}</select></div>
    </div>
    <div data-show="edge" ${v.provider === 'edge' ? '' : 'hidden'}>
      <div class="field"><label>Edge voice</label><select data-k="${prefix}.edge_voice">${opts(EDGE_VOICES, v.edge_voice)}</select></div>
    </div>
    <div class="field"><label>Speed: <span id="spd">${(+v.speed).toFixed(2)}×</span></label>
      <input type="range" min="0.8" max="1.2" step="0.05" value="${v.speed}" data-k="${prefix}.speed" style="width:100%"></div>
    <div class="row" style="margin-bottom:14px"><button class="sm" id="vpreview">🔊 Test voice</button><audio id="vaudio" style="flex:1;height:32px" controls hidden></audio></div>
    <div class="field"><label>Trim silences</label><select data-k="${prefix}.cut_silences">${opts([['none', 'Non'], ['smooth', 'Doux (0,75 s)'], ['natural', 'Naturel (0,5 s)'], ['jumpy', 'Nerveux (0,25 s)']], v.cut_silences)}</select></div>`;
}
function wireVoiceFields(el, getVoice, getLang) {
  const up = $('#lupload', el);
  if (up) {
    up.onchange = async (e) => {
      const f = e.target.files[0]; if (!f) return;
      const name = await askText("Name of this voice", 'ex. Mon narrateur FR', f.name.replace(/\.[^.]+$/, ''));
      if (!name) return;
      const fd = new FormData(); fd.append('name', name); fd.append('file', f);
      const vs = await guard(() => api('/api/local-tts/voices', { form: fd, method: 'POST' }), "Voice added");
      if (vs) {
        localInfoCache = null;
        const sel = $('[data-k$="local_voice"]', el);
        sel.innerHTML = opts([['', "Automatic (based on language)"], ...vs.map((x) => [x.id, x.name])], `${name}.wav`);
        sel.dispatchEvent(new Event('change'));
      }
    };
  }
  const pv = $('#vpreview', el);
  if (pv && getVoice) {
    pv.onclick = async () => {
      pv.disabled = true; pv.innerHTML = "<span class=\"spin\"></span> Generating…";
      const r = await guard(() => api('/api/voice/preview', { body: { voice: getVoice(), language: getLang ? getLang() : null } }));
      pv.disabled = false; pv.textContent = "🔊 Test voice";
      if (r) { const a = $('#vaudio', el); a.hidden = false; a.src = r.url; a.play().catch(() => {}); }
    };
  }
  const prov = $('[data-k$="provider"]', el);
  if (prov) prov.addEventListener('change', () => $$('[data-show]', el).forEach((d) => { d.hidden = d.dataset.show !== prov.value; }));
  const r = $('input[type=range]', el);
  if (r) r.addEventListener('input', () => { $('#spd', el).textContent = `${(+r.value).toFixed(2)}×`; });
  const ok = $('#vcustomok', el);
  if (ok) {
    ok.onclick = () => {
      const id = $('#vcustom', el).value.trim();
      if (!/^[A-Za-z0-9]{16,40}$/.test(id)) return toast("Invalid voice ID", true);
      let sel = $('#vsel', el);
      if (!sel) return;
      if (![...sel.options].some((o) => o.value === id)) sel.prepend(new Option(`Custom voice (${id})`, id));
      sel.value = id;
      sel.dispatchEvent(new Event('change'));
      $('#vcustom', el).value = '';
    };
  }
}

function tabVoice(el, ctx) {
  const p = ctx.p;
  el.innerHTML = `<div class="two"><div class="card" id="vf"><h3>Voice settings</h3><div class="muted">Loading voices…</div></div>
    <div><div id="prog"></div><div class="card" id="player"></div></div></div>`;
  (async () => {
    const [voices, local] = await Promise.all([elevenVoices(), localInfo(true)]);
    const chars = (ctx.p.script || '').length;
    $('#vf', el).innerHTML = `<h3>Voice settings</h3>${voiceFieldsHtml(p.settings.voice, 'settings.voice', voices, local)}
      <div class="card inner small" style="margin-bottom:12px">📏 Script : <b>${chars.toLocaleString('en-US')}</b> characters
        ≈ <b>${chars.toLocaleString('en-US')}</b> ElevenLabs credits (1 credit / character in Multilingual v2, ½ in Flash/Turbo).
        Already generated chunks are cached: rerunning won't charge for them again.</div>
      <button class="primary" id="gen" style="width:100%;justify-content:center">🎙 Generate voice-over</button>
      <div class="small muted" style="margin-top:8px">Same script + different voice = scenes and images preserved (only timings change).</div>`;
    wireVoiceFields($('#vf', el), () => ctx.p.settings.voice, () => ctx.p.settings.language);
    bindFields($('#vf', el), async (obj, inp) => {
      if (inp.id === 'vsel') setPath(obj, 'settings.voice.voice_name', inp.options[inp.selectedIndex].text.split(' — ')[0]);
      await ctx.patch(obj);
    });
    $('#gen', el).onclick = async () => {
      if (ctx.p.voiceover_stale && ctx.p.scenes.some((s) => s.image)
        && !confirm("The script has changed: scenes will be split again and the current images will be lost. Continue?")) return;
      await ctx.action('voiceover/generate', {}, "Synthesis started");
    };
    update();
  })();
  let lastTs;
  const update = () => {
    const pp = ctx.p;
    $('#prog', el).innerHTML = stepProgress(pp.steps.voiceover);
    const g = $('#gen', el); if (g) g.disabled = pp.running;
    const vo = pp.voiceover;
    const key = `${vo ? vo.ts : 'none'}|${!!pp.script}`;
    if (key !== lastTs) {
      lastTs = key;
      $('#player', el).innerHTML = vo
        ? `<h3>Voice-over</h3><audio controls src="${media(pp.id, vo.file)}?t=${vo.ts}"></audio>
           <div class="row small muted" style="margin-top:8px">Duration ${fmtTime(vo.duration)} · ${pp.scenes.length} scenes · ${esc(vo.provider)} ${esc(vo.voice || '')}
           <span class="spacer"></span><a class="btn sm" href="/download/${pp.id}?what=voice">⬇ MP3</a></div>`
        : `<div class="empty">${pp.script ? "No voice-over yet." : "Write or import a script first."}</div>`;
    }
  };
  update();
  return { update };
}

// --- onglet Visuels
function sceneSig(s) { return [s.image, s.status, s.error, s.prompt, s.motion, s.critique, s.continues].join('|'); }

function tabVisuals(el, ctx) {
  const p = ctx.p;
  const v = p.settings.visuals;
  el.innerHTML = `
    <div id="prog"></div>
    <div class="card">
      <div class="row" style="align-items:flex-end">
        <div style="width:120px"><label>Format</label><select data-k="settings.visuals.aspect">${opts(['16:9', '9:16'], v.aspect)}</select></div>
        <div style="width:200px"><label>Image model</label><select data-k="settings.visuals.image_model">${opts(IMAGE_MODELS, v.image_model)}</select></div>
        <div style="width:150px"><label>Mouvement : <span data-out="ms">${(+v.motion_strength).toFixed(1)}</span></label><input type="range" min="0" max="2" step="0.1" data-k="settings.visuals.motion_strength" value="${v.motion_strength}" data-live="ms" style="width:100%"></div>
        <label class="check"><input type="checkbox" data-k="settings.visuals.use_style_refs" ${v.use_style_refs ? 'checked' : ''}> Style reference images</label>
        <label class="check"><input type="checkbox" data-k="settings.visuals.use_character_refs" ${v.use_character_refs ? 'checked' : ''}> Consistent characters</label>
        <label class="check"><input type="checkbox" data-k="settings.visuals.captions" ${v.captions ? 'checked' : ''}> Burned-in subtitles</label>
        <div style="width:300px"><label>Continuity between images</label><select data-k="settings.visuals.continuity">${opts([['smart', "⛓ Smart — linked scenes drawn from the previous one"], ['always', "Full — each image starts from the previous one (slow)"], ['off', "None — all in parallel (fast)"]], v.continuity || 'smart')}</select></div>
      </div>
      <div class="card inner" style="margin-top:14px">
        <div class="row" style="align-items:flex-end">
          <div style="flex:1;min-width:260px">
            <label>Average image duration: <b style="color:var(--accent);font-size:15px" data-out="avg">${(+v.avg_scene_seconds).toFixed(1)} s</b></label>
            <input type="range" min="1" max="10" step="0.1" value="${v.avg_scene_seconds}" id="avg" class="big" style="width:100%">
            <div class="row small muted" style="justify-content:space-between"><span>1 s · rythme nerveux</span><span id="estim"></span><span>10 s · contemplatif</span></div>
          </div>
          <div style="width:90px"><label>Min (s)</label><input type="number" step="0.1" min="0.5" max="10" id="minsc" value="${v.min_scene_seconds}"></div>
          <div style="width:90px"><label>Max (s)</label><input type="number" step="0.1" min="1" max="30" id="maxsc" value="${v.max_scene_seconds}"></div>
          <button id="resplit">✂ Re-split scenes</button>
        </div>
        <div class="small muted" style="margin-top:6px">Cuts always fall on natural voice pauses (sentence endings first). Re-splitting deletes the current prompts and images.</div>
      </div>
    </div>
    <div class="card"><div class="row"><h3 style="margin:0">Recurring characters</h3>
        <span class="muted small">Check “Keep” for those that must stay identical from one image to the next.</span><span class="spacer"></span>
        <button class="sm primary" id="detect">✨ Generate characters</button><button class="sm" id="library">📚 Library</button><button class="sm" id="addchar">+ Add manually</button></div>
      <div class="chars" id="chars" style="margin-top:12px"></div></div>
    <div class="card">
      <div class="row" id="actions"></div>
      <div class="row" style="margin-top:12px">
        <div class="seg" id="sview"><button data-v="list">☰ List</button><button data-v="grid">▦ Grid</button></div>
        <select id="sfilter" style="width:auto"><option value="all">All scenes</option><option value="noimg">No image</option><option value="err">Failed</option></select>
        <span class="spacer"></span>
        <button id="preview">▶ Animated preview</button>
      </div>
    </div>
    <div class="scenes" id="scenes" style="margin-top:14px"></div>`;
  bindFields(el, async (obj) => { await ctx.patch(obj); });

  const avg = $('#avg', el);
  const estim = () => {
    const d = ctx.p.voiceover ? ctx.p.voiceover.duration : words(ctx.p.script) / 160 * 60;
    $('[data-out="avg"]', el).textContent = `${(+avg.value).toFixed(1)} s`;
    $('#estim', el).textContent = d ? `≈ ${Math.max(1, Math.round(d / avg.value))} images for ${fmtTime(d)}` : '';
  };
  avg.addEventListener('input', estim);
  estim();
  const saveDurations = async () => ctx.patch({ settings: { visuals: {
    avg_scene_seconds: +avg.value, min_scene_seconds: +$('#minsc', el).value, max_scene_seconds: +$('#maxsc', el).value } } });
  [avg, $('#minsc', el), $('#maxsc', el)].forEach((i) => i.addEventListener('change', saveDurations));
  $('#resplit', el).onclick = async () => {
    if (!ctx.p.voiceover) return toast("Generate the voice-over first", true);
    const n = ctx.p.scenes.filter((s) => s.image || s.prompt).length;
    if (n && !confirm(`Re-splitting deletes the prompts and images for ${n} scene(s). Continue?`)) return;
    await saveDurations();
    const np = await guard(() => api(`/api/projects/${ctx.id}/visuals/resplit`, { body: {
      avg_scene_seconds: +avg.value, min_scene_seconds: +$('#minsc', el).value, max_scene_seconds: +$('#maxsc', el).value } }));
    if (np) { ctx.p = np; mountScenes(); renderActions(); toast(`${np.scenes.length} scenes`); }
  };

  const scenesEl = $('#scenes', el);
  const sigs = {};
  let charSig = '';
  const vertical = () => ctx.p.settings.visuals.aspect === '9:16';
  const imgInner = (s) => {
    const st = s.status === 'running' ? "<div class=\"st\"><span class=\"spin\"></span>&nbsp;Generating…</div>"
      : s.status === 'queued' ? '<div class="st">En file d\'attente…</div>' : '';
    return (s.image ? `<img loading="lazy" src="${media(ctx.p.id, s.image)}">` : '<span>No image</span>') + st;
  };
  const sceneHtml = (s) => `
    <div class="card scene ${s.status === 'error' ? 'err' : ''}" data-sid="${s.id}">
      <div><div class="img ${vertical() ? 'vertical' : ''}" data-act="zoom">${imgInner(s)}</div>
        <div class="row" style="margin-top:8px;gap:6px">
          <button class="sm" data-act="regen" title="Redo with the same prompt">↻</button>
          <button class="sm" data-act="mine" title="Redo with YOUR prompt">✍ My prompt</button>
          <button class="sm" data-act="fix" title="The AI looks at the image and its neighbors, understands what's wrong, and remakes it">🧠 Fix</button>
          <button class="sm" data-act="full" title="New prompt written by the AI (before/after scenes)">✎ New</button>
          <button class="sm" data-act="adjust" title="Retouch the current image (e.g.: at night)">🪄</button>
          <label class="btn sm" title="Import your own image">⬆<input type="file" accept="image/*" hidden data-act="upload"></label>
          <button class="sm danger" data-act="del" title="Delete (merge with previous)">✕</button>
        </div></div>
      <div>
        <div class="meta"><b>#${s.id}</b><span>${fmtTime(s.start)} → ${fmtTime(s.end)}</span><span>${(s.end - s.start).toFixed(1)} s</span>
          <select class="sm" data-f="motion" style="width:auto;padding:3px 6px">${opts(MOTIONS, s.motion || 'zoom_in')}</select>
          ${(s.characters || []).map((c) => `<span class="chip">${esc(c)}</span>`).join('')}
          ${s.continues ? `<span class="chip" title="${esc(s.link || "continuation of the previous scene")}">⛓ suite de #${s.id - 1}</span>` : ''}</div>
        <div class="text">${esc(s.text)}</div>
        <textarea data-f="prompt" placeholder="Image prompt (written automatically)">${esc(s.prompt)}</textarea>
        <div class="small critique" data-f="critique">${s.critique ? `🧠 ${esc(s.critique)}` : ''}</div>
        <div class="small" style="color:var(--err)" data-f="error">${esc(s.error || '')}</div>
      </div>
    </div>`;
  const mountScenes = () => {
    const sc = ctx.p.scenes;
    scenesEl.innerHTML = sc.length ? sc.map(sceneHtml).join('') : "<div class=\"card empty\">Scenes appear after the voice-over is generated.</div>";
    sc.forEach((s) => { sigs[s.id] = sceneSig(s); });
    const f = $('#sfilter', el);
    if (f && f.value !== 'all') f.onchange();
  };
  const patchScenes = () => {
    const sc = ctx.p.scenes;
    if (sc.length !== $$('[data-sid]', scenesEl).length) { mountScenes(); return; }
    sc.forEach((s) => {
      const sig = sceneSig(s);
      if (sigs[s.id] === sig) return;
      sigs[s.id] = sig;
      const card = $(`[data-sid="${s.id}"]`, scenesEl);
      if (!card) return;
      card.classList.toggle('err', s.status === 'error');
      $('.img', card).innerHTML = imgInner(s);
      const ta = $('[data-f=prompt]', card);
      if (document.activeElement !== ta) ta.value = s.prompt || '';
      $('[data-f=error]', card).textContent = s.error || '';
      $('[data-f=critique]', card).textContent = s.critique ? `🧠 ${s.critique}` : '';
      const ms = $('[data-f=motion]', card); if (document.activeElement !== ms) ms.value = s.motion || 'zoom_in';
    });
    if ($('#sfilter', el).value !== 'all') applyFilter();
  };
  scenesEl.addEventListener('change', async (e) => {
    const card = e.target.closest('[data-sid]'); if (!card) return;
    const sid = card.dataset.sid;
    if (e.target.dataset.f === 'prompt' || e.target.dataset.f === 'motion') {
      await guard(() => api(`/api/projects/${ctx.id}/scenes/${sid}`, { method: 'PUT', body: { [e.target.dataset.f]: e.target.value } }));
    }
    if (e.target.dataset.act === 'upload' && e.target.files[0]) {
      const fd = new FormData(); fd.append('file', e.target.files[0]);
      await guard(() => api(`/api/projects/${ctx.id}/scenes/${sid}/upload`, { form: fd, method: 'POST' }), "Imported image");
      ctx.refresh();
    }
  });
  scenesEl.addEventListener('click', async (e) => {
    const card = e.target.closest('[data-sid]'); if (!card) return;
    const act = e.target.closest('[data-act]')?.dataset.act;
    const sid = card.dataset.sid;
    const s = ctx.p.scenes.find((x) => String(x.id) === sid);
    if (act === 'zoom' && s && s.image) lightbox(media(ctx.p.id, s.image));
    if (act === 'regen' || act === 'full') {
      const ta = $('[data-f=prompt]', card);
      if (act === 'regen' && ta.value !== (s.prompt || '')) await api(`/api/projects/${ctx.id}/scenes/${sid}`, { method: 'PUT', body: { prompt: ta.value } });
      await guard(() => api(`/api/projects/${ctx.id}/scenes/${sid}/regenerate`, { body: { mode: act === 'full' ? 'full' : 'same' } }));
      ctx.refresh();
    }
    if (act === 'mine') {
      const prompt = await askText(`Your prompt for scene #${sid}`, "Describe the image you want (the style is added automatically)", s.prompt || '');
      if (prompt) { await guard(() => api(`/api/projects/${ctx.id}/scenes/${sid}/regenerate`, { body: { mode: 'custom', prompt } }), "Image in progress with your prompt"); ctx.refresh(); }
    }
    if (act === 'fix') {
      const reason = await askText('Qu\'est-ce qui ne va pas ? (optionnel)', "e.g. there is a real human, it doesn't look like the previous scene, wrong place… Leave empty: the AI finds it by itself.");
      if (reason === null && !confirm('Laisser l\'IA trouver toute seule ce qui cloche ?')) return;
      await guard(() => api(`/api/projects/${ctx.id}/scenes/${sid}/regenerate`, { body: { mode: 'fix', instruction: reason || '' } }), 'L\'IA analyse l\'image et ses voisines…');
      ctx.refresh();
    }
    if (act === 'adjust') {
      if (!s.image) return toast("No image to adjust yet", true);
      const instruction = await askText('Retoucher l\'image', "e.g. make it at night, add snow, closer shot…");
      if (instruction) { await guard(() => api(`/api/projects/${ctx.id}/scenes/${sid}/regenerate`, { body: { mode: 'adjust', instruction } })); ctx.refresh(); }
    }
    if (act === 'del' && confirm(`Delete scene #${sid} ? Its text and duration will be merged with the previous scene.`)) {
      const np = await guard(() => api(`/api/projects/${ctx.id}/scenes/${sid}`, { method: 'DELETE' }));
      if (np) { ctx.p = np; mountScenes(); }
    }
  });

  const renderChars = () => {
    const cs = ctx.p.characters || [];
    const sig = JSON.stringify(cs);
    if (sig === charSig || $('#chars', el).contains(document.activeElement)) return;
    charSig = sig;
    const used = {};
    ctx.p.scenes.forEach((s) => (s.characters || []).forEach((c) => { used[c] = (used[c] || 0) + 1; }));
    $('#chars', el).innerHTML = cs.length ? cs.map((c) => {
      const on = c.enabled !== false;
      const busyImg = c.status === 'running';
      return `
      <div class="card inner char ${on ? '' : 'off'}" data-cid="${esc(c.id)}">
        <div class="cimg" data-ca="zoom" style="${c.image ? `background-image:url('${media(ctx.p.id, c.image)}')` : ''}">
          ${busyImg ? "<span class=\"chip run\"><span class=\"spin\"></span>Sheet in progress…</span>" : c.image ? '' : (c.error ? `<span class="small" style="color:var(--err)" title="${esc(c.error)}">⚠ failed</span>` : 'No reference')}</div>
        <label class="check keep"><input type="checkbox" data-cf="enabled" ${on ? 'checked' : ''}> Keep</label>
        <input type="text" data-cf="name" value="${esc(c.name)}" style="margin:6px 0">
        <textarea data-cf="description" style="min-height:80px;font-size:12px">${esc(c.description)}</textarea>
        <div class="row small muted" style="margin:6px 0">${c.role === 'protagonist' ? '<span class="chip ok">Protagoniste</span>' : ''}
          ${used[c.id] ? `<span>${used[c.id]} scene(s)</span>` : c.scenes_estimate ? `<span>~${c.scenes_estimate} scenes</span>` : ''}
          <span class="spacer"></span><label class="check small"><input type="checkbox" data-cf="every_image" ${c.every_image ? 'checked' : ''}> Partout</label></div>
        <div class="row"><button class="sm" data-ca="img" ${busyImg ? 'disabled' : ''}>${c.image ? '↻ Nouvelle fiche' : "✨ Create sheet"}</button><span class="spacer"></span><button class="sm danger" data-ca="del">✕</button></div>
      </div>`;
    }).join('') : "<div class=\"muted small\">Click “Generate characters”: the AI reads the script, suggests recurring characters, and draws their sheet. You keep the ones you want.</div>";
  };
  $('#chars', el).addEventListener('change', async (e) => {
    const card = e.target.closest('[data-cid]'); const f = e.target.dataset.cf; if (!card || !f) return;
    const np = await guard(() => api(`/api/projects/${ctx.id}/characters/${card.dataset.cid}`, { method: 'PUT', body: { [f]: fieldValue(e.target) } }));
    if (np) ctx.p = np;
  });
  $('#chars', el).addEventListener('click', async (e) => {
    const card = e.target.closest('[data-cid]'); const a = e.target.closest('[data-ca]')?.dataset.ca; if (!card || !a) return;
    const ch = ctx.p.characters.find((c) => c.id === card.dataset.cid);
    if (a === 'zoom' && ch && ch.image) lightbox(media(ctx.p.id, ch.image));
    if (a === 'img') {
      const np = await guard(() => api(`/api/projects/${ctx.id}/characters/${card.dataset.cid}/image`, { body: {} }), "Current card (~40 s)");
      if (np) { ctx.p = np; charSig = ''; renderChars(); }
    }
    if (a === 'del' && confirm("Delete this character?")) {
      const np = await guard(() => api(`/api/projects/${ctx.id}/characters/${card.dataset.cid}`, { method: 'DELETE' }));
      if (np) { ctx.p = np; charSig = ''; renderChars(); }
    }
  });
  $('#library', el).onclick = async () => {
    const st = await api(`/api/styles/${ctx.p.style_id}`);
    const have = new Set((ctx.p.characters || []).map((c) => c.id));
    const cs = st.characters || [];
    const m = modal(`<h2>Character library</h2><p class="muted">Permanent characters for style “ ${esc(st.name)} ” — click to add it to this video (its card stays the same from one video to the next).</p>
      <div class="chars">${cs.map((c) => `<div class="card inner char ${have.has(c.id) ? 'off' : ''}" data-lib="${esc(c.id)}" style="cursor:${have.has(c.id) ? 'default' : 'pointer'}">
        <div class="cimg" style="${c.image ? `background-image:url('${backendBase}/style-media/${st.id}/${c.image}')` : ''}">${c.image ? '' : 'No reference'}</div>
        <b>${esc(c.name)}</b><div class="small muted">${have.has(c.id) ? "✓ already in the video" : "Click to add"}</div></div>`).join('') || "<div class=\"muted\">No permanent characters: create them in Styles.</div>"}</div>
      <div class="row end" style="margin-top:12px"><a class="btn" href="#/styles/${ctx.p.style_id}">Manage in Styles</a><button data-close>Close</button></div>`, { wide: true });
    m.el.addEventListener('click', async (e) => {
      const card = e.target.closest('[data-lib]'); if (!card || have.has(card.dataset.lib)) return;
      const np = await guard(() => api(`/api/projects/${ctx.id}/characters/from-style`, { body: { id: card.dataset.lib } }), "Character added");
      if (np) { ctx.p = np; charSig = ''; renderChars(); m.close(); }
    });
  };
  $('#detect', el).onclick = async () => {
    if (!ctx.p.script) return toast('Il faut un script d\'abord', true);
    await ctx.action('characters/detect', {}, "Reading the script… characters are coming");
  };
  $('#addchar', el).onclick = async () => {
    const m = modal(`<h2>New character</h2><div class="field"><label>Name</label><input type="text" id="cn"></div>
      <div class="field"><label>Visual description</label><textarea id="cd" placeholder="age, outfit, colors, accessories…"></textarea></div>
      <label class="check"><input type="checkbox" id="ce"> In every image</label>
      <div class="small muted" style="margin-top:6px">The reference card is drawn automatically.</div>
      <div class="row end"><button data-close>Cancel</button><button class="primary" id="ok">Add</button></div>`);
    $('#ok', m.el).onclick = async () => {
      const np = await guard(() => api(`/api/projects/${ctx.id}/characters`, { body: { name: $('#cn', m.el).value, description: $('#cd', m.el).value, every_image: $('#ce', m.el).checked } }));
      if (np) { ctx.p = np; charSig = ''; renderChars(); m.close(); }
    };
  };

  const renderActions = () => {
    const pp = ctx.p; const sc = pp.scenes;
    const nPrompt = sc.filter((s) => s.prompt).length; const nImg = sc.filter((s) => s.image).length;
    const nErr = sc.filter((s) => s.status === 'error').length; const missing = sc.length - nImg;
    const dis = pp.running ? 'disabled' : '';
    $('#actions', el).innerHTML = !sc.length ? "<span class=\"muted\">Generate the voiceover first: scenes are timed to it.</span>" : `
      <b>${sc.length} scenes</b><span class="muted">· ${nPrompt} prompts · ${nImg} images${nErr ? ` · <span style="color:var(--err)">${nErr} failed</span>` : ''}</span>
      <span class="spacer"></span>
      <button ${dis} id="prompts">${nPrompt ? "↻ Rewrite all prompts" : "✍️ Write prompts"}</button>
      ${nErr ? `<button ${dis} id="failed">↻ Retry failed</button>` : ''}
      ${missing >= 10 ? `<button ${dis} id="next10">Generate next 10</button>` : ''}
      <button class="primary" ${dis} id="all">${missing ? `🖼 Generate ${missing === sc.length ? "all" : "the"} ${missing} images` : "↻ Regenerate all"}</button>`;
    const on = (sel, fn) => { const b = $(sel, el); if (b) b.onclick = fn; };
    on('#prompts', async () => { if (nPrompt && !confirm("Rewrite all prompts (your changes will be lost)?")) return; await ctx.action('visuals/prompts', { all: nPrompt > 0 }, "Prompt writing started"); });
    on('#failed', () => ctx.action('visuals/images', { scope: 'failed' }, "Retrying failed"));
    on('#next10', () => ctx.action('visuals/images', { scope: 'next10' }, "10 images started"));
    on('#all', async () => {
      if (!missing && !confirm("Regenerate ALL images?")) return;
      await ctx.action('visuals/images', missing ? { scope: 'all' } : { scope: 'ids', ids: sc.map((s) => s.id) }, "Image generation started");
    });
  };

  // vue liste / grille + filtre
  let sview = localStorage.getItem('sview') || 'list';
  const applyView = () => {
    scenesEl.classList.toggle('grid', sview === 'grid');
    $$('#sview button', el).forEach((b) => b.classList.toggle('on', b.dataset.v === sview));
  };
  $$('#sview button', el).forEach((b) => b.onclick = () => { sview = b.dataset.v; localStorage.setItem('sview', sview); applyView(); });
  const applyFilter = () => {
    const f = $('#sfilter', el).value;
    ctx.p.scenes.forEach((s) => {
      const card = $(`[data-sid="${s.id}"]`, scenesEl);
      if (card) card.hidden = (f === 'noimg' && s.image) || (f === 'err' && s.status !== 'error');
    });
  };
  $('#sfilter', el).onchange = applyFilter;
  applyView();

  // aperçu animé : la voix off défile avec l'image de chaque scène
  $('#preview', el).onclick = () => {
    const pp = ctx.p;
    if (!pp.voiceover) return toast("No voiceover yet", true);
    const m = modal(`<div class="pv"><div class="pvframe ${vertical() ? 'vertical' : ''}"><img id="pvi"><div class="pvcap" id="pvc"></div>
      <div class="pvnum" id="pvn"></div></div>
      <audio controls id="pva" src="${media(pp.id, pp.voiceover.file)}?t=${pp.voiceover.ts}"></audio>
      <div class="pvstrip" id="pvs">${pp.scenes.map((s) => `<div data-t="${s.start}" title="#${s.id}" style="flex:${(s.end - s.start).toFixed(2)};${s.image ? `background-image:url('${media(pp.id, s.image)}')` : ''}"></div>`).join('')}</div>
      <div class="row end" style="margin-top:10px"><span class="small muted">Approximate preview — the final render has smoother movements.</span><span class="spacer"></span><button data-close>Close</button></div></div>`, { wide: true });
    const audio = $('#pva', m.el); const img = $('#pvi', m.el);
    let cur = -1;
    const show = () => {
      const t = audio.currentTime;
      const i = pp.scenes.findIndex((s) => t >= s.start && t < s.end);
      if (i === cur || i < 0) return;
      cur = i;
      const s = pp.scenes[i];
      img.src = s.image ? media(pp.id, s.image) : '';
      img.style.animation = 'none'; void img.offsetWidth;
      img.style.animation = `kb-${s.motion || 'zoom_in'} ${(s.end - s.start).toFixed(2)}s linear forwards`;
      $('#pvc', m.el).textContent = s.text;
      $('#pvn', m.el).textContent = `#${s.id} · ${fmtTime(s.start)}`;
      $$('#pvs div', m.el).forEach((d, k) => d.classList.toggle('on', k === i));
    };
    audio.addEventListener('timeupdate', show);
    audio.addEventListener('seeked', () => { cur = -1; show(); });
    $('#pvs', m.el).addEventListener('click', (e) => { const d = e.target.closest('[data-t]'); if (d) { audio.currentTime = +d.dataset.t + 0.01; audio.play(); } });
    show();
    audio.play().catch(() => {});
    const obs = new MutationObserver(() => { if (!document.body.contains(m.el)) { audio.pause(); obs.disconnect(); } });
    obs.observe(document.body, { childList: true });
  };

  mountScenes();
  renderChars();
  renderActions();
  const update = () => {
    $('#prog', el).innerHTML = stepProgress(ctx.p.steps.visuals);
    renderActions();
    renderChars();
    patchScenes();
  };
  update();
  return { update };
}

// --- onglet Rendu
function tabRender(el, ctx) {
  el.innerHTML = `<div id="prog"></div><div id="prog2"></div><div class="card" id="rc"></div>
    <div class="grid2" style="margin-top:16px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))">
      <div class="card"><h3>🎬 Editing in DaVinci Resolve</h3>
        <div class="small muted" style="margin-bottom:10px">TubeForge opens Resolve and builds the timeline: V1 scenes, V2 subtitles, V3 hook, A1 voice, A2 sound effects. Everything stays editable, then rendered by Resolve.</div>
        <div id="resinfo" class="small" style="margin-bottom:10px"></div>
        <div class="row"><button class="primary" id="toresolve">🎬 Edit in Resolve + render</button><button id="toresolve2">Timeline only</button></div></div>
      <div class="card"><h3>📄 Editing recap</h3>
        <div class="small muted" style="margin-bottom:10px">All the text (script, hook, TikTok caption, hashtags), scenes, timed subtitles, and sound effects.</div>
        <a class="btn" href="/download/${ctx.id}?what=montage">⬇ MONTAGE.md</a></div>
      <div class="card" id="shortscard"><h3>📱 TikTok Shorts from this video</h3>
        <div class="small muted" style="margin-bottom:10px">Vertical, big-hook opening, subtitles, sound effects, local voice.</div>
        <div class="field"><select id="kshorts"><option value="promo">📣 Ad for the YouTube video — teaser, cliffhanger, “full video on YouTube” + end screen</option>
          <option value="standalone">📱 Standalone TikTok — complete story, works on its own</option></select></div>
        <div class="row"><select id="nshorts" style="width:auto"><option>1</option><option selected>2</option><option>3</option></select>
          <select id="cshorts" style="width:auto"><option value="">no channel</option></select>
          <button class="primary" id="mkshorts">✂ Create shorts</button><span class="small muted" id="childinfo"></span></div></div>
      <div class="card" id="chancard" hidden><h3>📅 TikTok Channel</h3>
        <div class="small muted" style="margin-bottom:10px">The short is placed in the channel schedule (publishing slot, export, channel Resolve project).</div>
        <div class="row"><select id="chsel" style="width:auto"><option value="">— none —</option></select><span class="small" id="slotinfo"></span></div></div>
    </div>`;
  api('/api/channels').then((chans) => {
    const o = opts(chans.map((c) => [c.id, `${c.emoji} ${c.name}`]));
    $('#cshorts', el).insertAdjacentHTML('beforeend', o);
    $('#chsel', el).insertAdjacentHTML('beforeend', o);
    $('#chsel', el).value = ctx.p.channel_id || '';
    $('#chsel', el).onchange = async () => {
      const r = await guard(() => api(`/api/projects/${ctx.id}/channel`, { body: { channel_id: $('#chsel', el).value || null } }), "Channel updated");
      if (r) Object.assign(ctx.p, { channel_id: r.channel_id, post: r.post });
    };
  }).catch(() => {});
  $('#toresolve', el).onclick = () => ctx.action('resolve', { render: true }, "Resolve opens — building the timeline…");
  $('#toresolve2', el).onclick = () => ctx.action('resolve', { render: false }, "Building the timeline in Resolve…");
  $('#mkshorts', el).onclick = async () => {
    await guard(() => api(`/api/projects/${ctx.id}/shorts`, { body: { count: +$('#nshorts', el).value, kind: $('#kshorts', el).value, channel_id: $('#cshorts', el).value || null } }), "Shorts creation started — they will appear in Projects");
  };
  let lastTs = undefined;
  const update = () => {
    const p = ctx.p;
    $('#prog', el).innerHTML = stepProgress(p.steps.render);
    $('#prog2', el).innerHTML = p.steps.resolve ? stepProgress(p.steps.resolve) : '';
    const rs = p.resolve;
    $('#resinfo', el).innerHTML = rs ? `✓ Projet <b>${esc(rs.project)}</b>, timeline <b>${esc(rs.timeline)}</b> (${rs.placed}/${rs.expected} items)
      ${rs.render_status ? ` — render: ${esc(rs.render_status)} <a href="/download/${p.id}?what=resolve">⬇ Resolve video</a>` : ''}` : '';
    $('#shortscard', el).hidden = p.format === 'short';
    $('#chancard', el).hidden = p.format !== 'short';
    $('#slotinfo', el).innerHTML = p.post && p.post.slot ? `&nbsp;🗓 ${esc(dayLabel(p.post.slot.slice(0, 10)))} at ${esc(p.post.slot.slice(11))}${p.post.posted ? " — 📤 published" : ''} · <a href="#/planning/${p.channel_id}">view schedule</a>` : '';
    ['#toresolve', '#toresolve2'].forEach((sel) => { $(sel, el).disabled = p.running || !p.voiceover || p.scenes.some((x) => !x.image); });
    const r = p.render;
    const missing = p.scenes.filter((s) => !s.image).length;
    const key = `${r && r.ts}|${missing}|${p.running}|${!!p.voiceover}`;
    if (key === lastTs) return;
    lastTs = key;
    $('#rc', el).innerHTML = `
      ${r ? `<video controls preload="metadata" src="${media(p.id, r.file)}?t=${r.ts}" style="max-height:70vh"></video>
        <div class="row" style="margin-top:12px"><b>${esc(p.title)}</b><span class="muted">· ${fmtTime(r.duration)} · ${r.width}×${r.height}</span><span class="spacer"></span>
          <a class="btn primary" href="/download/${p.id}">⬇ Download video</a><a class="btn" href="/download/${p.id}?what=srt">Sous-titres .srt</a>
          <a class="btn" href="/download/${p.id}?what=voice">Voice .mp3</a><a class="btn" href="/download/${p.id}?what=script">Script .txt</a></div>`
        : `<div class="empty">${!p.voiceover ? "Voice-over and images are required first." : missing ? `${missing} scene(s) without an image — finish the Visuals step.` : "Everything is ready to render."}</div>`}
      <div class="row end" style="margin-top:12px"><button class="primary" id="go" ${p.running || missing || !p.voiceover ? 'disabled' : ''}>🎬 ${r ? "Render again" : "Start rendering"}</button></div>`;
    $('#go', el).onclick = () => ctx.action('render', {}, "Rendering started");
  };
  update();
  return { update };
}

// --- onglet Miniatures
function tabThumbs(el, ctx) {
  el.innerHTML = `<div id="prog"></div>
    <div class="card"><div class="row" style="align-items:flex-end">
      <div style="width:110px"><label>Number</label><input type="number" id="n" min="1" max="6" value="2"></div>
      <div style="flex:1;min-width:240px"><label>Instructions (optional)</label><input type="text" id="ins" placeholder="e.g. hands holding a letter, text “24 HOURS”"></div>
      <button class="primary" id="gen">✨ Generate thumbnails</button></div>
      <div class="small muted" style="margin-top:8px">Style defined in the project Style (POV hands in the foreground, graphic novel…).</div></div>
    <div class="thumbs" id="grid" style="margin-top:14px"></div>`;
  let sig = '';
  $('#gen', el).onclick = () => ctx.action('thumbnails', { count: +$('#n', el).value || 2, instruction: $('#ins', el).value }, "Thumbnails in progress (~40 s)");
  $('#grid', el).addEventListener('click', async (e) => {
    const t = e.target.closest('[data-i]'); if (!t) return;
    if (e.target.closest('[data-zoom]')) return lightbox(media(ctx.p.id, ctx.p.thumbnails[+t.dataset.i].file));
    const np = await guard(() => api(`/api/projects/${ctx.id}/thumbnails/select`, { body: { index: +t.dataset.i } }), "Main thumbnail selected");
    if (np) { ctx.p = np; sig = ''; update(); }
  });
  const update = () => {
    const p = ctx.p;
    $('#prog', el).innerHTML = stepProgress(p.steps.thumbnail);
    const s = JSON.stringify([p.thumbnails, p.thumbnail_selected]);
    if (s === sig) return;
    sig = s;
    $('#grid', el).innerHTML = (p.thumbnails || []).map((t, i) => `<div class="t ${i === p.thumbnail_selected ? 'sel' : ''}" data-i="${i}" title="Click to choose it">
      <img src="${media(p.id, t.file)}"><button class="sm" data-zoom style="position:absolute;top:6px;right:6px">🔍</button>
      ${i === p.thumbnail_selected ? '<span class="chip ok" style="position:absolute;top:6px;left:6px">★ Principale</span>' : ''}</div>`).join('')
      || "<div class=\"muted\">No thumbnails yet.</div>";
  };
  update();
  return { update };
}

// ------------------------------------------------------------------ studio miniatures
async function viewThumbStudio(el) {
  const styles = await api('/api/styles');
  const tsm = (rel) => `/thumbstudio-media/${rel}`;
  el.innerHTML = `
    <div class="row" style="margin-bottom:16px"><h1 style="margin:0">Thumbnail Studio</h1><span class="muted">— thumbnails that make people want to click, without creating a video.</span></div>
    <div class="two" style="grid-template-columns:380px 1fr">
      <div class="card" style="position:sticky;top:16px">
        <div class="field"><label>Video title</label><input type="text" id="t" placeholder="POV: You're a Spy in 1960s Berlin"></div>
        <div class="field"><label>Idea / what should happen</label><textarea id="i" placeholder="e.g. my hands hold a TOP SECRET file, a silhouette behind the glass…" style="min-height:90px"></textarea></div>
        <div class="field"><label>Text on thumbnail (optional)</label><input type="text" id="tx" placeholder="e.g. 24 HOURS LEFT — empty = AI decides"></div>
        <div class="grid2">
          <div class="field"><label>Style</label><select id="st">${opts(styles.map((s) => [s.id, s.name]))}</select></div>
          <div class="field"><label>Format</label><select id="ar"><option>16:9</option><option>9:16</option><option>1:1</option></select></div>
        </div>
        <div class="field"><label>Number of variants: <b data-out="n">4</b></label><input type="range" id="n" min="1" max="8" step="1" value="4" style="width:100%"></div>
        <div class="field"><label>Inspiration image (optional)</label><input type="file" id="ref" accept="image/*">
          <img id="refprev" style="display:none;width:100%;border-radius:8px;margin-top:8px">
          <div class="small muted">A thumbnail that works for a competitor: it will be redrawn in your style.</div></div>
        <details class="field"><summary class="small muted" style="cursor:pointer">Custom style for this set</summary>
          <textarea id="sx" placeholder="Leave blank to use the thumbnail style from the selected Style" style="margin-top:8px"></textarea></details>
        <button class="primary" id="go" style="width:100%;justify-content:center">✨ Generate thumbnails</button>
      </div>
      <div id="sets"></div>
    </div>`;
  $('#n', el).addEventListener('input', () => { $('[data-out="n"]', el).textContent = $('#n', el).value; });
  $('#ref', el).onchange = (e) => {
    const f = e.target.files[0]; const im = $('#refprev', el);
    if (f) { im.src = URL.createObjectURL(f); im.style.display = 'block'; } else im.style.display = 'none';
  };
  $('#go', el).onclick = async () => {
    const fd = new FormData();
    fd.append('title', $('#t', el).value); fd.append('idea', $('#i', el).value); fd.append('text', $('#tx', el).value);
    fd.append('count', $('#n', el).value); fd.append('style_id', $('#st', el).value); fd.append('aspect', $('#ar', el).value);
    fd.append('style_text', $('#sx', el).value);
    if ($('#ref', el).files[0]) fd.append('file', $('#ref', el).files[0]);
    const r = await guard(() => api('/api/thumbstudio', { form: fd, method: 'POST' }), 'C\'est parti — ~40 s');
    if (r) load();
  };
  let sets = [];
  let sig = '';
  const itemHtml = (s, it) => {
    const ratio = s.aspect === '9:16' ? '9/16' : s.aspect === '1:1' ? '1/1' : '16/9';
    const inner = it.file ? `<img src="${tsm(it.file)}" loading="lazy">`
      : it.status === 'error' ? `<div class="small" style="color:var(--err);padding:10px">⚠ ${esc(it.error || "failed")}</div>`
        : `<div class="chip run"><span class="spin"></span>${it.status === 'queued' ? 'Concept…' : 'Dessin…'}</div>`;
    return `<div class="tsi" data-set="${s.id}" data-it="${it.id}" style="aspect-ratio:${ratio}">${inner}
      ${it.file ? `<div class="tsa">
        <button class="sm" data-a="zoom" title="Agrandir">🔍</button><a class="btn sm" href="/thumbstudio-download/${it.file}" title="Download">⬇</a>
        <button class="sm" data-a="edit" title="Retouch">🪄</button><button class="sm" data-a="var" title="Similar variants">♻</button>
        <button class="sm" data-a="proj" title="Send to a project">➜🎞</button><button class="sm danger" data-a="del" title="Delete">✕</button></div>` : ''}
      ${it.instruction ? `<span class="chip" style="position:absolute;left:6px;bottom:6px">🪄 ${esc(it.instruction.slice(0, 30))}</span>` : ''}</div>`;
  };
  const render = () => {
    $('#sets', el).innerHTML = sets.length ? sets.map((s) => `
      <div class="card" style="margin-bottom:16px">
        <div class="row" style="margin-bottom:10px"><div><b>${esc(s.title || s.idea.slice(0, 60))}</b>
          <div class="small muted">${fmtDate(s.created)} · ${s.aspect}${s.text ? ` · text “ ${esc(s.text)} »` : ''}${s.ref ? " · with inspiration" : ''}</div></div>
          <span class="spacer"></span>${s.ref ? `<img src="${tsm(s.ref)}" style="height:40px;border-radius:6px">` : ''}
          <button class="sm" data-more="${s.id}">+2 variantes</button><button class="sm danger" data-delset="${s.id}">Delete set</button></div>
        <div class="tsgrid">${s.items.map((it) => itemHtml(s, it)).join('')}</div>
      </div>`).join('') : "<div class=\"card empty\">Your thumbnails will appear here. Example: “POV: You're a Corrupt Prohibition Agent” + “my gloved hands place a stack of bills on a TOP SECRET file”.</div>";
  };
  const load = async () => {
    sets = await api('/api/thumbstudio');
    const s2 = JSON.stringify(sets);
    if (s2 !== sig) { sig = s2; render(); }
  };
  $('#sets', el).addEventListener('click', async (e) => {
    const more = e.target.closest('[data-more]');
    if (more) { await guard(() => api(`/api/thumbstudio/${more.dataset.more}/more`, { body: { count: 2 } }), "2 variants in progress"); return load(); }
    const ds = e.target.closest('[data-delset]');
    if (ds) { if (confirm("Delete the whole series?")) { await guard(() => api(`/api/thumbstudio/${ds.dataset.delset}`, { method: 'DELETE' })); load(); } return; }
    const card = e.target.closest('[data-it]'); const a = e.target.closest('[data-a]')?.dataset.a;
    if (!card) return;
    const s = sets.find((x) => x.id === card.dataset.set); const it = s && s.items.find((x) => x.id === card.dataset.it);
    if (!it) return;
    if (!a && it.file) return lightbox(tsm(it.file));
    const base = `/api/thumbstudio/${s.id}/items/${it.id}`;
    if (a === 'zoom') lightbox(tsm(it.file));
    if (a === 'edit') {
      const instruction = await askText("Retouch thumbnail", "e.g. bigger red text, add smoke, more frightened face…");
      if (instruction) { await guard(() => api(`${base}/edit`, { body: { instruction } }), "Retouching in progress"); load(); }
    }
    if (a === 'var') { await guard(() => api(`${base}/variations`, { body: { count: 2 } }), "Variants in progress"); load(); }
    if (a === 'del' && confirm("Delete this thumbnail?")) { await guard(() => api(base, { method: 'DELETE' })); load(); }
    if (a === 'proj') {
      const ps = await api('/api/projects?archived=0');
      if (!ps.length) return toast("No project", true);
      const m = modal(`<h2>Envoyer vers un projet</h2><select id="pp">${opts(ps.map((p) => [p.id, p.title]))}</select>
        <div class="row end" style="margin-top:12px"><button data-close>Cancel</button><button class="primary" id="ok">Set as thumbnail</button></div>`);
      $('#ok', m.el).onclick = async () => {
        const r = await guard(() => api(`${base}/to-project`, { body: { project_id: $('#pp', m.el).value } }), "Thumbnail added to project");
        if (r) m.close();
      };
    }
  });
  await load();
  const t = setInterval(load, 2500);
  return () => clearInterval(t);
}

// ------------------------------------------------------------------ batch
async function viewBatch(el) {
  const [styles, chans] = await Promise.all([api('/api/styles'), api('/api/channels').catch(() => [])]);
  el.innerHTML = `
    <h1>Batch CSV</h1>
    <div class="card">
      <div class="two" style="grid-template-columns:1fr 1fr">
        <div>
          <div class="field"><label>CSV file</label><input type="file" id="csv" accept=".csv,text/csv,.txt"></div>
          <div class="field"><label>Default style</label><select id="style">${opts(styles.map((s) => [s.id, s.name]))}</select></div>
          <div class="field"><label>Default TikTok channel (rows without <code>chaine</code> column)</label><select id="chan"><option value="">— none (YouTube videos) —</option>${opts(chans.map((c) => [c.id, `${c.emoji} ${c.name}`]))}</select></div>
          <div class="field"><label>Mode</label><div class="seg" id="mode"><button data-v="auto" class="on">⚡ Auto — finished videos</button><button data-v="review">👀 Review — stops at prompts</button></div></div>
          <div class="row"><button class="primary" id="go">🚀 Start batch</button><a class="btn" href="${backendBase}/exemple.csv">⬇ CSV template</a><a class="btn" href="${backendBase}/exemple_tiktok.csv">⬇ TikTok template</a></div>
        </div>
        <div class="small">
          <b>Format:</b> one row per video, separator <code>,</code> or <code>;</code> (Excel OK). Only the <code>title</code> column is required.
          <pre>title;words;context;video_url;style
POV: You're a Viking Raider;3000;;https://youtu.be/…;pov-history
POV: You're a Medieval Plague Doctor;2500;focus on 1348;;</pre>
          Recognized columns: <code>title/titre</code>, <code>words/mots</code>, <code>context/contexte</code>, <code>video_url/youtube</code>,
          <code>style</code>, <code>format</code> (16:9, 9:16 or <code>short</code>), <code>voice_id</code>, <code>provider</code> (local, elevenlabs or edge), <code>script</code> (your own text),
          <code>langue</code>, <code>personnages</code>, <code>shorts</code> (number of ad shorts).<br>
          <b>TikTok:</b> <code>chaine</code> (e.g. <code>tiktok-fr</code>) → the row becomes a TikTok for that channel, placed in its schedule.
          <b>Clipping:</b> <code>source</code> = a YouTube link or the title of a TubeForge video, <code>shorts</code> = number of clips.
          <pre>title;chaine;source;shorts
POV : Tu es un gladiateur;tiktok-fr;;
;tiktok-en-clips;https://youtu.be/…;3</pre>
          No header: 1 title per row.<br><br>
          Videos run in parallel (<code>PROJECT_PARALLEL</code> setting) and images are distributed across the 36 accounts.
        </div>
      </div>
    </div>
    <h2 style="margin-top:24px">Recent batches</h2><div id="list"></div>`;
  let mode = 'auto';
  $$('#mode button', el).forEach((b) => b.onclick = () => { mode = b.dataset.v; $$('#mode button', el).forEach((x) => x.classList.toggle('on', x === b)); });
  $('#go', el).onclick = async () => {
    const f = $('#csv', el).files[0];
    if (!f) return toast("Choose a CSV file", true);
    const fd = new FormData(); fd.append('file', f); fd.append('mode', mode); fd.append('style_id', $('#style', el).value); fd.append('channel_id', $('#chan', el).value);
    const r = await guard(() => api('/api/batch', { form: fd, method: 'POST' }));
    if (r) { toast(`${r.projects.length} videos started${r.clips ? ` + ${r.clips} video(s) to clip (being written)` : ''}`); load(); }
  };
  const load = async () => {
    const bs = await api('/api/batches');
    $('#list', el).innerHTML = bs.map((b) => {
      const done = b.projects.filter((p) => p.render).length;
      return `<div class="card"><div class="row"><b>${esc(b.name)}</b><span class="muted small">${fmtDate(b.created)} · ${b.mode === 'auto' ? 'Auto' : 'Review'}</span>
        <span class="spacer"></span><span class="chip ${done === b.projects.length ? 'ok' : ''}">${done}/${b.projects.length} exports disponibles</span></div>
        <table class="list" style="margin-top:8px">${b.projects.map((p) => `<tr><td style="width:40%"><a href="#/p/${p.id}">${esc(p.title)}</a></td>
          <td>${featureBadge(p.features)}</td><td>${statusChip(p)}</td>
          <td style="text-align:right">${p.render ? `<a class="btn sm" href="/download/${p.id}">⬇ MP4</a>` : ''}</td></tr>`).join('')}</table></div>`;
    }).join('') || "<div class=\"muted\">No batches yet.</div>";
  };
  await load();
  const t = setInterval(load, 4000);
  return () => clearInterval(t);
}

// ------------------------------------------------------------------ planning TikTok (chaînes)
const DAY_FMT = new Intl.DateTimeFormat('en-US', { weekday: 'long', day: 'numeric', month: 'long' });
const dayLabel = (d) => { const s = DAY_FMT.format(new Date(`${d}T12:00:00`)); return s.charAt(0).toUpperCase() + s.slice(1); };
const STEP_LABELS = { script: 'Script', voiceover: "Voice", visuals: 'Images', render: "Render", resolve: 'Resolve', thumbnail: "Thumbnails" };
const PLAN_STATUS = { ready: ['ok', "✓ Ready"], production: ['run', '⚙ En production'], error: ['err', '✗ Erreur'], posted: ['', "📤 Published"] };

function channelForm(ch, styles, voices) {
  const v = ch.voice || {};
  return `
    <div class="grid2">
      <div class="field"><label>Name</label><input type="text" data-c="name" value="${esc(ch.name)}" placeholder="ex. TikTok FR"></div>
      <div class="field"><label>Emoji</label><input type="text" data-c="emoji" value="${esc(ch.emoji || '📱')}" style="width:90px"></div>
      <div class="field"><label>Language</label><select data-c="language">${opts(LANGUAGES, ch.language)}</select></div>
      <div class="field"><label>Style</label><select data-c="style_id">${opts(styles.map((s) => [s.id, s.name]), ch.style_id)}</select></div>
    </div>
    <div class="field"><label>Default video type</label>
      <select data-c="kind">${opts([['standalone', "📱 Standalone TikTok — complete story"], ['promo', "📣 Clipping / ad — teaser that links to the YouTube video"]], ch.kind)}</select></div>
    <div class="grid2">
      <div class="field"><label>Voice</label><select data-c="voice.provider">${opts([['algrow', 'Algrow'], ['local', 'Locale'], ['edge', 'Edge'], ['elevenlabs', 'ElevenLabs']], v.provider || 'algrow')}</select></div>
      <div class="field"><label>Local voice</label><select data-c="voice.local_voice"><option value="">Auto (based on language)</option>${opts(voices, v.local_voice || '')}</select></div>
      <div class="field"><label>Posts per day</label><input type="number" min="1" max="6" data-c="posts_per_day" value="${ch.posts_per_day || 2}"></div>
      <div class="field"><label>Times (comma-separated)</label><input type="text" data-c="post_times" value="${esc((ch.post_times || []).join(', '))}" placeholder="12:30, 19:00"></div>
      <div class="field"><label>First schedule day</label><input type="date" data-c="start_date" value="${esc(ch.start_date || '')}"></div>
      <div class="field"><label>@ du compte (optionnel)</label><input type="text" data-c="handle" value="${esc(ch.handle || '')}" placeholder="@moncompte"></div>
    </div>
    <div class="field"><label>Hashtags added to each caption</label><input type="text" data-c="hashtags" value="${esc((ch.hashtags || []).map((x) => `#${x}`).join(' '))}" placeholder="#history #pov"></div>
    <details style="margin:6px 0 12px"><summary class="small muted" style="cursor:pointer">Call to action for ad shorts (empty = default text in the language)</summary>
      <div class="field" style="margin-top:8px"><label>Phrase spoken at the end</label><input type="text" data-c="cta.spoken" value="${esc((ch.cta || {}).spoken || '')}"></div>
      <div class="grid2"><div class="field"><label>End screen — line 1</label><input type="text" data-c="cta.line1" value="${esc((ch.cta || {}).line1 || '')}"></div>
        <div class="field"><label>Ligne 2 (bandeau rouge)</label><input type="text" data-c="cta.line2" value="${esc((ch.cta || {}).line2 || '')}"></div></div>
      <div class="field"><label>Ligne 3</label><input type="text" data-c="cta.line3" value="${esc((ch.cta || {}).line3 || '')}"></div></details>
    <label class="check"><input type="checkbox" data-c="auto_resolve" ${ch.auto_resolve !== false ? 'checked' : ''}> 🎬 Edit each finished short in DaVinci Resolve (project “TubeForge - ${esc(ch.name || "channel")} »)</label>`;
}

function readChannelForm(root) {
  const out = {};
  $$('[data-c]', root).forEach((inp) => {
    let val = inp.type === 'checkbox' ? inp.checked : inp.value;
    if (inp.dataset.c === 'post_times') val = val.split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean).map((x) => x.replace('h', ':'));
    if (inp.dataset.c === 'hashtags') val = val.split(/[\s,;]+/).map((x) => x.replace(/^#/, '')).filter(Boolean);
    if (inp.dataset.c === 'posts_per_day') val = +val || 1;
    setPath(out, inp.dataset.c, val);
  });
  return out;
}

async function editChannel(ch, onSaved) {
  const [styles, li] = await Promise.all([api('/api/styles'), localInfo()]);
  const voices = (li.voices || []).map((x) => (typeof x === 'string' ? x : x.name || x.file)).filter(Boolean);
  const isNew = !ch.id;
  const m = modal(`<h2>${isNew ? "+ New channel" : `⚙ ${esc(ch.emoji)} ${esc(ch.name)}`}</h2>${channelForm(ch, styles, voices)}
    <div class="row" style="margin-top:14px">${isNew ? '' : "<button class=\"danger\" id=\"del\">Delete</button>"}<span class="spacer"></span>
      <button data-close>Cancel</button><button class="primary" id="ok">Save</button></div>`, { wide: true });
  $('#ok', m.el).onclick = async () => {
    const body = readChannelForm(m.el);
    if (!body.name) return toast("Name the channel", true);
    const r = await guard(() => api(isNew ? '/api/channels' : `/api/channels/${ch.id}`, { method: isNew ? 'POST' : 'PUT', body }), "Channel saved");
    if (r) { m.close(); onSaved(r); }
  };
  if (!isNew) $('#del', m.el).onclick = async () => {
    if (!confirm(`Delete channel “ ${ch.name} ”? (videos stay in Projects)`)) return;
    if (await guard(() => api(`/api/channels/${ch.id}`, { method: 'DELETE' }), "Channel deleted")) { m.close(); onSaved(null); }
  };
}

async function clipModal(ch) {
  const ps = (await api('/api/projects?archived=0')).filter((p) => p.format !== 'short' && p.features.script);
  const m = modal(`<h2>✂ Clip a video for ${esc(ch.emoji)} ${esc(ch.name)}</h2>
    <p class="muted small">The AI reads the entire video and writes shorts${ch.language ? ` en ${esc(ch.language)}` : ''} (translated if needed), each from a different angle. They are generated and filed automatically in the schedule.</p>
    <div class="field"><label>YouTube link (a video already online)</label><input type="url" id="url" placeholder="https://www.youtube.com/watch?v=…"></div>
    <div class="field"><label>… or a TubeForge video</label><select id="pid"><option value="">—</option>${opts(ps.map((p) => [p.id, p.title]))}</select></div>
    <div class="grid2"><div class="field"><label>Nombre de shorts</label><select id="n">${opts(['1', '2', '3', '4', '5'], '3')}</select></div>
      <div class="field"><label>Type</label><select id="kind">${opts([['promo', "📣 Ad → YouTube video (cliffhanger + end screen)"], ['standalone', "📱 Standalone (complete story)"]], ch.kind)}</select></div></div>
    <div class="row end"><button data-close>Cancel</button><button class="primary" id="go">✂ Start clipping</button></div>`);
  $('#go', m.el).onclick = async () => {
    const body = { url: $('#url', m.el).value.trim(), project_id: $('#pid', m.el).value || null, count: +$('#n', m.el).value, kind: $('#kind', m.el).value };
    if (!body.url && !body.project_id) return toast("Paste a YouTube link or choose a video", true);
    if (await guard(() => api(`/api/channels/${ch.id}/clip`, { body }), "Clipping started — shorts will appear in the schedule in ~1 min")) m.close();
  };
}

async function ideasModal(ch) {
  const m = modal(`<h2>💡 TikTok ideas for ${esc(ch.emoji)} ${esc(ch.name)}</h2>
    <p class="muted small">The AI suggests new topics (never already done on the channel). You edit the list, then launch everything at once.</p>
    <div class="grid2"><div class="field"><label>How many?</label><input type="number" id="n" value="30" min="1" max="60"></div>
      <div class="field"><label>Theme (optional)</label><input type="text" id="theme" placeholder="e.g. Middle Ages, mafia, modern wars…"></div></div>
    <div class="row end"><button class="primary" id="gen">💡 Suggest ideas</button></div>
    <div id="out" style="margin-top:12px"></div>`, { wide: true });
  $('#gen', m.el).onclick = async () => {
    const b = $('#gen', m.el); b.disabled = true; b.innerHTML = "<span class=\"spin\"></span> AI is thinking…";
    const r = await guard(() => api(`/api/channels/${ch.id}/ideas`, { body: { count: +$('#n', m.el).value, theme: $('#theme', m.el).value } }));
    b.disabled = false; b.textContent = "💡 Suggest more ideas";
    if (!r) return;
    $('#out', m.el).innerHTML = `<div class="field"><label>${r.ideas.length} ideas — one line = one TikTok (you can edit, delete, add)</label>
      <textarea id="csv" style="min-height:320px;font-family:var(--mono, monospace);font-size:12px">${esc(r.csv)}</textarea></div>
      <div class="row"><button id="dl">⬇ Download the .csv</button><span class="spacer"></span>
        <div class="seg" id="mode"><button data-v="auto" class="on">⚡ Auto</button><button data-v="review">👀 Review</button></div>
        <button class="primary" id="go">🚀 Launch these TikToks</button></div>`;
    let mode = 'auto';
    $$('#mode button', m.el).forEach((x) => x.onclick = () => { mode = x.dataset.v; $$('#mode button', m.el).forEach((y) => y.classList.toggle('on', y === x)); });
    $('#dl', m.el).onclick = () => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob(['﻿' + $('#csv', m.el).value], { type: 'text/csv' }));
      a.download = `idees-${ch.id}.csv`; a.click();
    };
    $('#go', m.el).onclick = async () => {
      const fd = new FormData();
      fd.append('csv_text', $('#csv', m.el).value); fd.append('mode', mode); fd.append('channel_id', ch.id);
      fd.append('style_id', ch.style_id); fd.append('name', `Ideas ${ch.name} — ${new Date().toLocaleDateString('en-US')}`);
      const res = await guard(() => api('/api/batch', { form: fd, method: 'POST' }));
      if (res) { toast(`${res.projects.length} TikToks launched`); m.close(); }
    };
  };
}

function previewVideo(it) {
  modal(`<h2 style="margin-bottom:8px">${esc(it.title)}</h2>
    <video controls autoplay src="${media(it.id, it.video)}?t=${it.video_ts}" style="max-height:72vh;display:block;margin:0 auto;border-radius:10px"></video>
    <pre class="small" style="white-space:pre-wrap;margin-top:10px">${esc(it.caption)}</pre>
    <div class="row end"><button id="cp">📋 Copy caption</button><a class="btn" href="/download/${it.id}">⬇ MP4</a><a class="btn" href="#/p/${it.id}">Open project</a><button data-close>Close</button></div>`);
  $('#cp').onclick = () => navigator.clipboard.writeText(it.caption).then(() => toast("Caption copied"));
}

async function viewPlanning(el, cid) {
  let chans = await api('/api/channels');
  if (!chans.length) {
    el.innerHTML = `<h1>📅 TikTok Schedule</h1><div class="card empty">No channel. <button class="primary" id="new">+ Create a channel</button></div>`;
    $('#new', el).onclick = () => editChannel({}, () => route());
    return null;
  }
  let ch = chans.find((c) => c.id === cid) || chans[0];
  el.innerHTML = `
    <div class="row" style="margin-bottom:14px"><h1 style="margin:0">📅 TikTok Schedule</h1><span class="spacer"></span>
      <button id="tpl" title="Resolve template project: 1080x1920 settings, render preset, your asset pack">🎬 Resolve Template</button>
      <button id="newch">+ Channel</button></div>
    <div class="row" id="tabs" style="margin-bottom:14px;flex-wrap:wrap"></div>
    <div class="card" id="head"></div>
    <div id="list"></div>`;
  const tabs = () => {
    $('#tabs', el).innerHTML = chans.map((c) => `<a class="chip ${c.id === ch.id ? 'run' : ''}" style="font-size:14px;padding:7px 14px" href="#/planning/${c.id}">${esc(c.emoji)} ${esc(c.name)}
      <span class="muted small">${c.plan.ready} ready${c.plan.ready > 1 ? 's' : ''}${c.plan.production ? ` · ${c.plan.production} in progress` : ''}</span></a>`).join('');
  };
  tabs();
  $('#newch', el).onclick = () => editChannel({ language: ch.language, style_id: ch.style_id, posts_per_day: 2, post_times: ['12:30', '19:00'], kind: 'standalone', auto_resolve: true },
    (r) => { if (r) location.hash = `#/planning/${r.id}`; });
  $('#tpl', el).onclick = async () => {
    const b = $('#tpl', el); b.disabled = true; b.innerHTML = '<span class="spin"></span> Resolve…';
    const r = await guard(() => api('/api/resolve/template', { body: {} }));
    b.disabled = false; b.textContent = "🎬 Resolve Template";
    if (r) modal(`<h2>🎬 DaVinci Resolve template ready</h2>
      <p>Project <b>${esc(r.project)}</b> ${r.created ? "created" : "updated"} — render preset <b>${esc(r.preset)}</b>${r.pack_added ? `, ${r.pack_added} file(s) from your pack imported into the “Pack” bin` : ''}.</p>
      <p class="small muted">Each channel has its own Resolve project created from this template, with one timeline per short (sorted by publication date).
      You can tweak the template project in Resolve (settings, LUT, bins…) then click here again: future channel projects will use your changes.
      Drop your pack in <code>assets/pack/</code> (images, logos) and <code>assets/sfx/pack/</code> (sounds).</p>
      <div class="row end"><button data-close class="primary">OK</button></div>`);
  };
  let lastKey = '';
  const load = async () => {
    const d = await api(`/api/channels/${ch.id}/plan`).catch(() => null);
    if (!d || !$('#list', el)) return;
    ch = d.channel;
    const s = d.summary;
    const key = JSON.stringify(d);
    if (key === lastKey) return;
    lastKey = key;
    const days = s.covered_until ? Math.max(0, Math.round((new Date(s.covered_until.slice(0, 10)) - new Date(new Date().toISOString().slice(0, 10))) / 86400000)) : 0;
    $('#head', el).innerHTML = `
      <div class="row" style="flex-wrap:wrap;gap:8px">
        <b style="font-size:17px">${esc(ch.emoji)} ${esc(ch.name)}</b>
        <span class="chip">${ch.kind === 'promo' ? '📣 Clipping → YouTube' : '📱 TikTok autonome'}</span>
        <span class="chip">${esc(ch.language)}</span><span class="chip">🕒 ${ch.post_times.join(' · ')}</span>
        <span class="spacer"></span><button class="sm" id="edit">⚙ Settings</button></div>
      <div class="row" style="margin:12px 0;gap:8px;flex-wrap:wrap">
        <span class="chip ok">✓ ${s.ready} ready${s.ready > 1 ? 's' : ''}</span>
        ${s.production ? `<span class="chip run">⚙ ${s.production} en production</span>` : ''}
        ${s.errors ? `<span class="chip err">✗ ${s.errors} en erreur</span>` : ''}
        ${s.posted ? `<span class="chip">📤 ${s.posted} published${s.posted > 1 ? 's' : ''}</span>` : ''}
        ${s.late ? `<span class="chip warn">⚠ ${s.late} overdue slot(s)</span>` : ''}
        <span class="small muted">${s.covered_until ? `Videos ready until <b>${dayLabel(s.covered_until.slice(0, 10))}</b> (${days} day${days > 1 ? 's' : ''} d'avance)` : "No videos ready yet"}</span></div>
      <div class="row" style="flex-wrap:wrap;gap:8px">
        <button class="primary" id="ideas">💡 Ideas → batch</button>
        <button id="clip">✂ Clip a video</button>
        <button id="resolve">🎬 Edit ready videos in Resolve</button>
        <button id="export">📦 Export available exports</button>
        <button id="open">📂 Open folder</button>
        <button id="reset" title="Recalculate all slots from the first day (except videos already published)">↻ Reschedule</button></div>`;
    $('#edit', el).onclick = () => editChannel(ch, (r) => { if (!r) location.hash = '#/planning'; else { lastKey = ''; refreshAll(); } });
    $('#ideas', el).onclick = () => ideasModal(ch);
    $('#clip', el).onclick = () => clipModal(ch);
    $('#resolve', el).onclick = async () => { const r = await guard(() => api(`/api/channels/${ch.id}/resolve-all`, { body: {} })); if (r) toast(r.started ? `${r.started} short(s) sent to Resolve (one by one)` : "Everything is already edited in Resolve"); };
    $('#export', el).onclick = async () => {
      const b = $('#export', el); b.disabled = true; b.innerHTML = '<span class="spin"></span> Export…';
      const r = await guard(() => api(`/api/channels/${ch.id}/export`, { body: {} }));
      b.disabled = false; b.textContent = "📦 Export available exports";
      if (r) toast(`${r.count} publication(s) ready in ${r.dir}`);
      lastKey = ''; load();
    };
    $('#open', el).onclick = () => guard(() => api(`/api/channels/${ch.id}/open`, { body: {} }));
    $('#reset', el).onclick = async () => {
      if (!confirm("Recalculate all slots (creation order)? Videos already published will not move.")) return;
      await guard(() => api(`/api/channels/${ch.id}/assign`, { body: { reset: true } }), "Schedule recalculated"); lastKey = ''; load();
    };
    const todo = d.items.filter((i) => i.status !== 'posted');
    const posted = d.items.filter((i) => i.status === 'posted');
    const groups = {};
    todo.forEach((i) => { const k = i.slot ? i.slot.slice(0, 10) : 'zz'; (groups[k] = groups[k] || []).push(i); });
    const now = new Date().toISOString().slice(0, 16).replace('T', ' ');
    const row = (it) => {
      const [cls, lab] = PLAN_STATUS[it.status];
      return `<div class="planrow ${it.slot && it.slot < now && it.status !== 'posted' ? 'late' : ''}" data-id="${it.id}">
        <span class="ptime">${it.slot ? esc(it.slot.slice(11)) : '—'}</span>
        <span class="pthumb" data-a="play" style="${it.thumb ? `background-image:url('${media(it.id, it.thumb)}')` : ''}">${it.video ? '▶' : ''}</span>
        <span style="flex:1;min-width:0">
          <a href="#/p/${it.id}" class="ptitle">${esc(it.title)}</a>
          <span class="small muted" style="display:block">${it.kind === 'promo' ? `📣 Pub → « ${esc(it.parent_title || '')} »` : '📱 TikTok'}${it.hook ? ` · accroche « ${esc(it.hook)} »` : ''}${it.duration ? ` · ${fmtTime(it.duration)}` : ''}</span>
          <span class="row" style="gap:6px;margin-top:4px"><span class="chip ${cls}">${lab}${it.running && it.step ? ` — ${esc(STEP_LABELS[it.step] || it.step)}` : ''}</span>
            ${it.resolve ? "<span class=\"chip\" title=\"Edited and rendered in DaVinci Resolve\">🎬 Resolve</span>" : ''}${it.exported ? "<span class=\"chip\" title=\"Copied to the export folder\">📦</span>" : ''}
            ${it.error ? `<span class="small" style="color:var(--err)">${esc(it.error.slice(0, 120))}</span>` : ''}</span></span>
        <span class="row" style="gap:4px">
          ${it.status === 'ready' ? "<button class=\"sm\" data-a=\"copy\" title=\"Copy caption + hashtags\">📋</button>" : ''}
          ${it.status !== 'posted' ? "<button class=\"sm\" data-a=\"up\" title=\"Earlier\">↑</button><button class=\"sm\" data-a=\"down\" title=\"Later\">↓</button>" : ''}
          ${it.status === 'ready' ? "<button class=\"sm\" data-a=\"posted\" title=\"Mark as published\">✓ Published</button>" : ''}
          ${it.status === 'posted' ? '<button class="sm" data-a="unposted">↺</button>' : ''}</span></div>`;
    };
    $('#list', el).innerHTML = (Object.keys(groups).sort().map((k) => `<h3 style="margin:22px 0 8px">${k === 'zz' ? "No slot" : dayLabel(k)}</h3>
      <div class="card" style="padding:4px 14px">${groups[k].map(row).join('')}</div>`).join('')
      || `<div class="card empty" style="margin-top:16px">Nothing planned. Click <b>💡 Ideas → batch</b> to prepare 30 TikToks at once, or <b>✂ Clip a video</b>.</div>`)
      + (posted.length ? `<details style="margin-top:22px"><summary class="muted" style="cursor:pointer">📤 Already published (${posted.length})</summary>
        <div class="card" style="padding:4px 14px;margin-top:8px">${posted.slice().reverse().map(row).join('')}</div></details>` : '');
    const byId = Object.fromEntries(d.items.map((i) => [i.id, i]));
    $$('.planrow [data-a]', el).forEach((b) => b.onclick = async (e) => {
      e.preventDefault();
      const it = byId[b.closest('.planrow').dataset.id];
      const a = b.dataset.a;
      if (a === 'play') { if (it.video) previewVideo(it); return; }
      if (a === 'copy') { await navigator.clipboard.writeText(it.caption); toast("Caption copied"); return; }
      if (a === 'up' || a === 'down') await guard(() => api(`/api/projects/${it.id}/move`, { body: { dir: a === 'up' ? -1 : 1 } }));
      if (a === 'posted' || a === 'unposted') await guard(() => api(`/api/projects/${it.id}/post`, { body: { posted: a === 'posted' } }));
      lastKey = ''; refreshAll();
    });
  };
  const refreshAll = async () => { chans = await api('/api/channels').catch(() => chans); tabs(); await load(); };
  await load();
  const t = setInterval(refreshAll, 5000);
  return () => clearInterval(t);
}

// ------------------------------------------------------------------ galerie des voix
const ACCENT_FLAGS = { FR: '🇫🇷', "Quebec": '🇨🇦', CA: '🇨🇦', Belgique: '🇧🇪', BE: '🇧🇪', CH: '🇨🇭', US: '🇺🇸', UK: '🇬🇧', GB: '🇬🇧', Australie: '🇦🇺', AU: '🇦🇺', Irlande: '🇮🇪', IE: '🇮🇪', EN: '🇺🇸' };
const VOICE_GROUPS = [['all', "All"], ['fr', "🇫🇷 French"], ['US', '🇺🇸 Anglais US'], ['UK', '🇬🇧 Anglais UK'], ['other', '🌍 Autres accents']];

async function viewVoices(el) {
  let filter = 'all';
  const player = new Audio();
  let playing = null;
  const [styles, chans] = await Promise.all([api('/api/styles'), api('/api/channels').catch(() => [])]);
  const targets = [...styles.map((s) => [`style:${s.id}`, `🎨 Style « ${s.name} »`]), ...chans.map((c) => [`chan:${c.id}`, `${c.emoji} Channel “ ${c.name} »`])];
  el.innerHTML = `
    <div class="row" style="margin-bottom:6px"><h1 style="margin:0">🎙️ Voices</h1><span class="spacer"></span>
      <label class="btn">+ Add my voice<input type="file" id="up" accept="audio/*" hidden></label>
      <button id="gen">🎧 Generate samples</button></div>
    <div class="small muted" style="margin-bottom:14px">All these voices run locally on your card (Chatterbox), free and unlimited. Each sample says the same sentence, generated by the real video engine:<br>
      <span id="texts"></span></div>
    <div class="seg" id="flt" style="margin-bottom:14px">${VOICE_GROUPS.map(([v, l]) => `<button data-v="${v}" class="${v === 'all' ? 'on' : ''}">${l}</button>`).join('')}</div>
    <div id="sampling"></div>
    <div class="grid3" id="grid"></div>`;
  $$('#flt button', el).forEach((b) => b.onclick = () => { filter = b.dataset.v; $$('#flt button', el).forEach((x) => x.classList.toggle('on', x === b)); draw(); });
  let data = null;
  const inGroup = (v) => filter === 'all' || (filter === 'fr' ? v.lang === 'fr' : filter === 'other' ? v.lang === 'en' && !['US', 'UK'].includes(v.accent) : v.accent === filter);
  const draw = () => {
    $('#texts', el).innerHTML = `🇫🇷 « ${esc(data.texts.fr)} »<br>🇬🇧 « ${esc(data.texts.en)} »`;
    const s = data.sampling;
    const missing = data.voices.filter((v) => !v.sample).length;
    $('#sampling', el).innerHTML = s.running ? `<div class="banner">⚙ Sample generation: ${s.done}/${s.total}…<div class="bar" style="margin-top:6px"><div style="width:${s.total ? Math.round(100 * s.done / s.total) : 0}%"></div></div></div>`
      : missing ? `<div class="banner">${missing} voices without samples — click “🎧 Generate samples” (~10 s per voice).</div>` : '';
    $('#gen', el).disabled = s.running;
    const rank = (v) => (v.lang === 'fr' ? 0 : v.accent === 'US' ? 1 : v.accent === 'UK' ? 2 : 3) * 10 + (v.default ? 0 : 1);
    $('#grid', el).innerHTML = data.voices.filter(inGroup).sort((a, b) => rank(a) - rank(b)).map((v) => `
      <div class="card voicecard ${playing === v.id ? 'playing' : ''}" data-id="${esc(v.id)}">
        <div class="row" style="gap:10px">
          <button class="playbtn" data-a="play" ${v.sample ? '' : 'disabled'} title="${v.sample ? "Listen" : "No sample yet"}">${playing === v.id ? '❚❚' : '▶'}</button>
          <div style="flex:1;min-width:0"><b>${ACCENT_FLAGS[v.accent] || '🎙️'} ${esc(v.label)}</b> <span class="muted small">${v.gender === 'f' ? '♀' : v.gender === 'm' ? '♂' : ''}</span>
            <div class="small muted">${v.default ? "<b style=\"color:var(--ok)\" title=\"Used when the voice is set to “Auto”\">⭐ default</b> · " : ''}${esc(v.accent)}${v.desc ? ` · ${esc(v.desc)}` : ''}</div></div></div>
        <div class="row" style="margin-top:10px;gap:6px"><select data-a="use" style="flex:1"><option value="">Use for…</option>${opts(targets)}</select></div>
      </div>`).join('') || "<div class=\"muted\">No voices in this category.</div>";
    $$('.voicecard [data-a="play"]', el).forEach((b) => b.onclick = () => {
      const id = b.closest('.voicecard').dataset.id;
      const v = data.voices.find((x) => x.id === id);
      if (playing === id) { player.pause(); playing = null; draw(); return; }
      player.src = `/voice-sample/${encodeURIComponent(v.name)}.mp3?t=${Date.now()}`;
      player.play(); playing = id; draw();
    });
    $$('.voicecard [data-a="use"]', el).forEach((sel) => sel.onchange = async () => {
      if (!sel.value) return;
      const id = sel.closest('.voicecard').dataset.id;
      const [kind, key] = sel.value.split(':');
      const voice = { provider: 'local', local_voice: id };
      const ok = kind === 'style'
        ? await guard(() => api(`/api/styles/${key}`, { method: 'PUT', body: { voice } }))
        : await guard(() => api(`/api/channels/${key}`, { method: 'PUT', body: { voice } }));
      if (ok) toast(`Voice “ ${data.voices.find((x) => x.id === id).label} ” chosen for ${sel.options[sel.selectedIndex].text} (upcoming videos)`);
      sel.value = '';
    });
  };
  player.onended = () => { playing = null; draw(); };
  const load = async () => { data = await api('/api/voices/gallery'); draw(); };
  $('#gen', el).onclick = async () => { await guard(() => api('/api/voices/gallery/samples', { body: {} }), "Sample generation started"); load(); };
  $('#up', el).onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const name = await askText("Name of this voice", "e.g. My FR voice", f.name.replace(/\.[^.]+$/, ''));
    if (!name) return;
    const fd = new FormData(); fd.append('name', name); fd.append('file', f);
    if (await guard(() => api('/api/local-tts/voices', { form: fd, method: 'POST' }), "Voice added — generate its sample to listen to it")) load();
  };
  await load();
  const t = setInterval(() => { if (data && data.sampling.running) load(); }, 3000);
  return () => { clearInterval(t); player.pause(); };
}

// ------------------------------------------------------------------ styles
async function viewStyles(el) {
  const styles = await api('/api/styles');
  el.innerHTML = `<div class="row" style="margin-bottom:16px"><h1 style="margin:0">Styles</h1><span class="spacer"></span><button class="primary" id="new">+ Nouveau style</button></div>
    <div class="grid3">${styles.map((s) => `<a class="card pcard" href="#/styles/${s.id}">
      <span class="thumb" style="${s.visuals.style_refs[0] ? `background-image:url('${backendBase}/style-media/${s.id}/${s.visuals.style_refs[0]}')` : ''}"></span>
      <div class="body"><b class="title">${esc(s.name)}</b><div class="small muted">${esc(s.language)} · ${s.script.word_count} words · ${s.script.references.length} ref. script(s) · ${s.characters.length} perso(s)</div></div></a>`).join('')}</div>`;
  $('#new', el).onclick = async () => {
    const name = await askText("New style name", 'ex. POV History FR');
    if (!name) return;
    const base = styles[0] && confirm(`Start from a copy of “ ${styles[0].name} ”? (Cancel = blank style)`) ? styles[0].id : null;
    const s = await guard(() => api('/api/styles', { body: { name, base_id: base } }));
    if (s) location.hash = `#/styles/${s.id}`;
  };
}

async function viewStyle(el, sid) {
  let s = await api(`/api/styles/${sid}`);
  const [voices, local] = await Promise.all([elevenVoices(), localInfo(true)]);
  const put = async (obj) => { const ns = await guard(() => api(`/api/styles/${sid}`, { method: 'PUT', body: obj })); if (ns) s = ns; return ns; };
  const render = () => {
    const v = s.visuals;
    el.innerHTML = `
    <div class="row" style="margin-bottom:16px"><a class="btn sm" href="#/styles">←</a><h1 style="margin:0">${esc(s.name)}</h1><span class="spacer"></span>
      <span class="muted small">Autosave</span><button class="danger" id="del">Delete</button></div>
    <div class="grid2" style="grid-template-columns:repeat(auto-fit,minmax(420px,1fr));align-items:start">
      <div>
        <div class="card"><h2>General</h2>
          <div class="field"><label>Name</label><input type="text" data-k="name" value="${esc(s.name)}"></div>
          <div class="field"><label>Video language</label><input type="text" data-k="language" value="${esc(s.language)}" placeholder="English, French…"></div></div>
        <div class="card"><h2>Script writing</h2>
          <div class="grid2"><div class="field"><label>Length (words)</label><input type="number" step="100" data-k="script.word_count" value="${s.script.word_count}"></div>
            <div class="field"><label>Mode</label><select data-k="script.mode">${opts([['pro', 'Pro'], ['fast', 'Rapide']], s.script.mode)}</select></div></div>
          <div class="field"><label>Channel instructions</label><textarea data-k="script.instructions" style="min-height:180px">${esc(s.script.instructions)}</textarea></div>
          <label>Reference scripts (tone to imitate)</label>
          ${s.script.references.map((r, i) => `<div class="row card inner" style="padding:8px 12px;margin-bottom:6px"><span>${esc(r.title)}</span><span class="muted small">${words(r.text)} words</span><span class="spacer"></span><button class="sm danger" data-delref="${i}">✕</button></div>`).join('') || "<div class=\"muted small\">None.</div>"}
          <div class="row" style="margin-top:8px"><input type="url" id="refurl" placeholder="YouTube URL of a channel video" style="flex:1"><button class="sm" id="addyt">+ From YouTube</button><button class="sm" id="addtxt">+ Paste text</button></div>
        </div>
        <div class="card"><h2>Voice</h2><div id="voice">${voiceFieldsHtml(s.voice, 'voice', voices, local)}</div></div>
      </div>
      <div>
        <div class="card"><h2>Visuals</h2>
          <div class="field"><label>Art style (added to every image prompt)</label><textarea data-k="visuals.art_style" style="min-height:150px">${esc(v.art_style)}</textarea></div>
          <label>Style reference images</label>
          <div class="refs">${v.style_refs.map((r) => `<div class="r"><img src="${backendBase}/style-media/${sid}/${r}"><button class="sm danger" data-delimg="${esc(r.split('/').pop())}">✕</button></div>`).join('')}</div>
          <div class="row" style="margin:8px 0 14px"><label class="btn sm">⬆ Add an image<input type="file" accept="image/*" hidden id="addimg"></label>
            <label class="check"><input type="checkbox" data-k="visuals.use_style_refs" ${v.use_style_refs ? 'checked' : ''}> Use the 1st image as style reference</label></div>
          <div class="grid2">
            <div class="field"><label>Image model</label><select data-k="visuals.image_model">${opts(IMAGE_MODELS, v.image_model)}</select></div>
            <div class="field"><label>Format</label><select data-k="visuals.aspect">${opts(['16:9', '9:16'], v.aspect)}</select></div>
            <div class="field" style="grid-column:1/-1"><label>Average image duration: <b style="color:var(--accent)"><span data-out="savg">${(+v.avg_scene_seconds).toFixed(1)}</span> s</b></label>
              <input type="range" min="1" max="10" step="0.1" data-k="visuals.avg_scene_seconds" data-live="savg" value="${v.avg_scene_seconds}" style="width:100%">
              <div class="row small muted" style="justify-content:space-between"><span>1 s</span><span>10 s</span></div></div>
            <div class="field"><label>Min / max (s)</label><div class="row"><input type="number" step="0.1" data-k="visuals.min_scene_seconds" value="${v.min_scene_seconds}" style="width:45%"><input type="number" step="0.1" data-k="visuals.max_scene_seconds" value="${v.max_scene_seconds}" style="width:45%"></div></div>
            <div class="field"><label>Motion intensity: <span data-out="smot">${(+v.motion_strength).toFixed(1)}</span></label><input type="range" step="0.1" min="0" max="2" data-k="visuals.motion_strength" data-live="smot" value="${v.motion_strength}" style="width:100%"></div>
          </div>
          <label class="check"><input type="checkbox" data-k="visuals.auto_characters" ${v.auto_characters ? 'checked' : ''}> Automatically detect recurring characters</label>
          <label class="check"><input type="checkbox" data-k="visuals.use_character_refs" ${v.use_character_refs ? 'checked' : ''}> Keep characters consistent (reference sheets)</label>
          <label class="check"><input type="checkbox" data-k="visuals.captions" ${v.captions ? 'checked' : ''}> Subtitles burned into the video</label>
          <div class="field" style="margin-top:10px"><label>Continuity between images</label><select data-k="visuals.continuity">${opts([['smart', "⛓ Smart — linked scenes drawn from the previous one"], ['always', "Full — each image starts from the previous one (slow)"], ['off', "None — all in parallel (fast)"]], v.continuity || 'smart')}</select></div>
        </div>
        <div class="card"><h2>Permanent characters</h2><div class="muted small" style="margin-bottom:8px">Copied into every new project with this style.</div>
          <div class="chars">${s.characters.map((c, i) => `<div class="card inner char"><div class="cimg" style="${c.image ? `background-image:url('${backendBase}/style-media/${sid}/${c.image}')` : ''}">${c.image ? '' : "No reference"}</div>
            <b>${esc(c.name)}</b><div class="small muted">${esc(c.description)}</div>
            ${c.signature ? `<div class="small" style="margin-top:4px">🔖 ${esc(c.signature)}</div>` : ''}
            <label class="check small"><input type="checkbox" data-chopt="${i}" data-o="auto_include" ${c.auto_include ? 'checked' : ''}> Checked by default in new videos</label>
            <label class="check small"><input type="checkbox" data-chopt="${i}" data-o="in_script" ${c.in_script ? 'checked' : ''}> Plays a role in the script</label>
            <label class="check small"><input type="checkbox" data-chopt="${i}" data-o="outfit_varies" ${c.outfit_varies ? 'checked' : ''}> Outfit based on the video's period</label>
            <label class="check small"><input type="checkbox" data-chev="${i}" ${c.every_image ? 'checked' : ''}> In all images</label>
            <div class="row"><button class="sm" data-chimg="${esc(c.id)}">✨ Reference</button><span class="spacer"></span><button class="sm danger" data-chdel="${i}">✕</button></div></div>`).join('')}</div>
          <button class="sm" id="addchar" style="margin-top:8px">+ Add a character</button></div>
        <div class="card"><h2>📣 TikTok ad Shorts</h2>
          <div class="field"><label>Ad Shorts automatically created after each long video</label><select data-k="shorts.promo_count">${opts([['0', "None"], ['1', '1'], ['2', '2'], ['3', '3']], String((s.shorts || {}).promo_count || 0))}</select></div>
          <div class="small muted" style="margin-bottom:8px">Call-to-action texts (leave blank = default text in the video language: “The full story is on my YouTube channel”, “FULL VIDEO / ON YOUTUBE / link in bio”).</div>
          <div class="field"><label>Phrase said at the end</label><input type="text" data-k="shorts.cta_spoken" value="${esc((s.shorts || {}).cta_spoken || '')}"></div>
          <div class="grid2"><div class="field"><label>End screen — line 1</label><input type="text" data-k="shorts.cta_line1" value="${esc((s.shorts || {}).cta_line1 || '')}"></div>
            <div class="field"><label>Ligne 2 (bandeau rouge)</label><input type="text" data-k="shorts.cta_line2" value="${esc((s.shorts || {}).cta_line2 || '')}"></div></div>
          <div class="field"><label>Ligne 3</label><input type="text" data-k="shorts.cta_line3" value="${esc((s.shorts || {}).cta_line3 || '')}"></div></div>
        <div class="card"><h2>Thumbnails</h2>
          <div class="grid2"><div class="field"><label>Number per video (auto)</label><input type="number" min="0" max="6" data-k="thumbnail.count" value="${s.thumbnail.count}"></div>
            <div class="field"><label>Model</label><select data-k="thumbnail.model">${opts(IMAGE_MODELS, s.thumbnail.model)}</select></div></div>
          <div class="field"><label>Thumbnail style</label><textarea data-k="thumbnail.style" style="min-height:120px">${esc(s.thumbnail.style)}</textarea></div></div>
      </div>
    </div>`;
    wireVoiceFields($('#voice', el), () => s.voice, () => s.language);
    bindFields(el, async (obj, inp) => {
      if (inp.id === 'vsel') setPath(obj, 'voice.voice_name', inp.options[inp.selectedIndex].text.split(' — ')[0]);
      await put(obj);
    });
    $('#del', el).onclick = async () => { if (confirm("Delete this style?") && await guard(() => api(`/api/styles/${sid}`, { method: 'DELETE' }))) location.hash = '#/styles'; };
    $$('[data-delref]', el).forEach((b) => b.onclick = async () => { const refs = s.script.references.filter((_, i) => i !== +b.dataset.delref); s.script.references = refs; await put({ script: { references: refs } }); render(); });
    $('#addyt', el).onclick = async () => {
      const url = $('#refurl', el).value.trim(); if (!url) return;
      $('#addyt', el).disabled = true;
      const ns = await guard(() => api(`/api/styles/${sid}/references/youtube`, { body: { url } }), "Transcript added");
      if (ns) { s = ns; render(); } else $('#addyt', el).disabled = false;
    };
    $('#addtxt', el).onclick = async () => {
      const text = await askText("Paste a reference script"); if (!text) return;
      const title = (await askText("Title of this script")) || "Reference";
      s.script.references.push({ title, text }); await put({ script: { references: s.script.references } }); render();
    };
    $('#addimg', el).onchange = async (e) => {
      const fd = new FormData(); fd.append('file', e.target.files[0]);
      const ns = await guard(() => api(`/api/styles/${sid}/refs`, { form: fd, method: 'POST' }), "Image added"); if (ns) { s = ns; render(); }
    };
    $$('[data-delimg]', el).forEach((b) => b.onclick = async () => { const ns = await guard(() => api(`/api/styles/${sid}/refs/${b.dataset.delimg}`, { method: 'DELETE' })); if (ns) { s = ns; render(); } });
    $$('[data-chdel]', el).forEach((b) => b.onclick = async () => { const cs = s.characters.filter((_, i) => i !== +b.dataset.chdel); await put({ characters: cs }); render(); });
    $$('[data-chev]', el).forEach((b) => b.onchange = async () => { s.characters[+b.dataset.chev].every_image = b.checked; await put({ characters: s.characters }); });
    $$('[data-chopt]', el).forEach((b) => b.onchange = async () => { s.characters[+b.dataset.chopt][b.dataset.o] = b.checked; await put({ characters: s.characters }); });
    $$('[data-chimg]', el).forEach((b) => b.onclick = async () => {
      b.disabled = true; b.innerHTML = '<span class="spin"></span>';
      const ns = await guard(() => api(`/api/styles/${sid}/characters/${b.dataset.chimg}/image`, { body: {} }), "Reference created"); if (ns) { s = ns; render(); }
    });
    $('#addchar', el).onclick = async () => {
      const name = await askText("Character name"); if (!name) return;
      const description = await askText('Description visuelle', 'âge, tenue, couleurs, accessoires…'); if (!description) return;
      let cid = name.toLowerCase().replace(/[^a-z0-9]+/g, '_').slice(0, 30) || 'perso';
      while (s.characters.some((c) => c.id === cid)) cid += '_2';
      s.characters.push({ id: cid, name, description, image: null, every_image: false });
      await put({ characters: s.characters }); render();
    };
  };
  render();
}

// ------------------------------------------------------------------ réglages
async function viewSettings(el) {
  const cfg = await api('/api/settings');
  const F = [
    ['ELEVENLABS_API_KEY', "ElevenLabs API key", 'password', "Voice-over. Found on elevenlabs.io → Profile → API keys."],
    ['LOCAL_TTS_VRAM_GB', "Max graphics memory for local voice (GB)", 'number', "Chatterbox uses ~3-5 GB; safety cap."],
    ['PROXY_BASE_URL', 'URL du proxy (36 comptes)', 'text', ''],
    ['PROXY_API_KEY', "Proxy key", 'password', ''],
    ['SCRIPT_MODEL', "Model for scripts", 'text', "ID configured in the proxy"],
    ['FAST_MODEL', "Fast model (prompts, titles…)", 'text', "ID configured in the proxy"],
    ['IMAGE_CONCURRENCY', "Parallel images", 'number', "36 = one request per account"],
    ['LLM_CONCURRENCY', "Parallel text requests", 'number', ''],
    ['PROJECT_PARALLEL', "Videos processed at the same time (batch)", 'number', ''],
    ['TTS_CONCURRENCY', "Parallel voice requests", 'number', "depending on your ElevenLabs plan (2 to 15)"],
    ['RENDER_WORKERS', "Render processes per video", 'number', "CPU cores used for rendering"],
    ['RENDER_CONCURRENCY', "Simultaneous renders", 'number', ''],
  ];
  el.innerHTML = `<h1>Settings</h1><div class="card" style="max-width:760px">
    ${F.map(([k, l, t, help]) => `<div class="field"><label>${l}</label><input type="${t}" data-key="${k}" value="${t === 'password' ? '' : esc(cfg[k])}" placeholder="${t === 'password' ? esc(cfg[k] || "not defined") : ''}">
      ${help ? `<div class="small muted">${esc(help)}</div>` : ''}</div>`).join('')}
    <div class="row"><button class="primary" id="save">Save</button><button id="test11">Test ElevenLabs</button><span class="spacer"></span>
      <span class="small muted">Keys are stored in the folder's <code>.env</code> file.</span></div></div>`;
  $('#save', el).onclick = async () => {
    const body = {};
    $$('[data-key]', el).forEach((i) => { if (i.type !== 'password' || i.value.trim()) if (i.type === 'password' || i.value !== String(cfg[i.dataset.key])) body[i.dataset.key] = i.value.trim(); });
    if (!Object.keys(body).length) return toast("Nothing to save");
    if (await guard(() => api('/api/settings', { method: 'PUT', body }), "Settings saved")) { elevenVoicesCache = null; await pollStats(); route(); }
  };
  $('#test11', el).onclick = async () => {
    const r = await guard(() => api('/api/elevenlabs/voices'));
    if (r) toast(r.length ? `ElevenLabs OK — ${r.length} voices available` : "No ElevenLabs key configured", !r.length);
  };
}

// ------------------------------------------------------------------ démarrage
pollStats().then(route);
