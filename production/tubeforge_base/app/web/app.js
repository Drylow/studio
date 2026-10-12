/* TubeForge — interface (vanilla JS, aucune compilation) */
'use strict';

// ------------------------------------------------------------------ utilitaires
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const h = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const fmtTime = (s) => { s = Math.max(0, Math.round(s || 0)); const m = Math.floor(s / 60); return `${m}:${String(s % 60).padStart(2, '0')}`; };
const fmtDate = (ts) => new Date(ts * 1000).toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
const words = (t) => (t || '').trim().split(/\s+/).filter(Boolean).length;
const media = (pid, rel) => `/media/${pid}/${rel}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function api(path, opts = {}) {
  const o = { method: opts.method || (opts.body !== undefined ? 'POST' : 'GET'), headers: {} };
  if (opts.form) o.body = opts.form;
  else if (opts.body !== undefined) { o.body = JSON.stringify(opts.body); o.headers['Content-Type'] = 'application/json'; }
  const r = await fetch(path, o);
  let data = null;
  try { data = await r.json(); } catch { /* vide */ }
  if (!r.ok) throw new Error((data && data.detail) || `Erreur ${r.status}`);
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
      <div class="row end" style="margin-top:12px"><button data-close>Annuler</button><button class="primary" id="ok">Valider</button></div>`);
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

const LANGUAGES = [['English', 'Anglais'], ['French', 'Français'], ['Spanish', 'Espagnol'], ['German', 'Allemand'],
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
  return (lines || []).map((l) => `<div class="ll lv-${l.l}"><span class="lt">${new Date(l.t * 1000).toLocaleTimeString('fr-FR')}</span>${esc(l.m)}</div>`).join('');
}
const elapsed = (t) => fmtTime(Date.now() / 1000 - t);

const IMAGE_MODELS = []; // Configure through the workspace model catalog.
const ELEVEN_MODELS = []; // IDs are private runtime configuration.
const EDGE_VOICES = ['en-US-AndrewMultilingualNeural', 'en-US-BrianMultilingualNeural', 'en-US-ChristopherNeural', 'en-US-GuyNeural',
  'en-US-EricNeural', 'en-GB-RyanNeural', 'en-US-AvaMultilingualNeural', 'en-US-EmmaMultilingualNeural',
  'fr-FR-RemyMultilingualNeural', 'fr-FR-VivienneMultilingualNeural', 'fr-FR-HenriNeural', 'fr-FR-DeniseNeural'];
const MOTIONS = [['zoom_in', 'Zoom avant'], ['zoom_out', 'Zoom arrière'], ['pan_left', 'Pan gauche'], ['pan_right', 'Pan droite'],
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
      <div class="slots" title="Requêtes en vol vers le proxy (1 par compte)">${dots}</div>
      <div>Images : <b>${s.image.active}</b>/${s.limits.image} en cours</div>
      <div>Faites : <b>${s.image.done}</b>${s.image.errors ? ` · <span style="color:var(--err)">${s.image.errors} err.</span>` : ''}
        ${s.image.avg_seconds ? ` · ~${Math.round(s.image.avg_seconds)}s/img` : ''}</div>
      <div>Texte : <b>${s.llm.active}</b>/${s.limits.llm} en cours</div>
      <div>Projets actifs : <b>${STATE.running.length}</b></div>
      ${STATE.has_algrow ? '<div style="margin-top:6px">Voix : Algrow configure</div>' : STATE.has_elevenlabs ? '' : '<div style="color:var(--warn);margin-top:6px">Fournisseur vocal a configurer</div>'}`;
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
  $$('.nav a').forEach((a) => a.classList.toggle('active', a.dataset.nav === nav));
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
    <h1>Qu'est-ce qu'on crée aujourd'hui ?</h1>
    <div class="card">
      <div class="small muted" style="font-weight:600;margin-bottom:10px">✨ NOUVELLE VIDÉO</div>
      <div class="field"><label>Titre de la vidéo</label>
        <input type="text" id="title" placeholder="Tape ton titre, ou laisse vide pour en générer un"></div>
      <label class="check" style="margin-bottom:14px"><input type="checkbox" id="autotitle"> Générer un titre pour moi</label>
      <div class="field"><label>Format</label>
        <div class="seg" id="fmt"><button data-v="long" class="on">🎬 Vidéo longue (YouTube)</button><button data-v="short">📱 Short TikTok (1 min 30 max)</button></div></div>
      <div class="grid2">
        <div class="field"><label>Style</label><select id="style">${opts(styles.map((s) => [s.id, s.name]))}</select></div>
        <div class="field"><label>Longueur (mots)</label><input type="number" id="words" min="100" step="100" placeholder="selon le style"></div>
        <div class="field"><label>Format</label><select id="aspect"><option value="">selon le style</option><option>16:9</option><option>9:16</option></select></div>
        <div class="field"><label>Langue de la vidéo <span id="langhint" class="muted" style="text-transform:none"></span></label>
          <select id="lang"><option value="">selon le style</option>${opts(LANGUAGES)}</select></div>
      </div>
      <div class="field" id="chanrow" hidden><label>📅 Chaîne TikTok (langue, voix, planning de publication)</label>
        <select id="chan"><option value="">— aucune —</option>${opts(chans.map((c) => [c.id, `${c.emoji} ${c.name}`]))}</select></div>
      <div class="field" id="promorow"><label>📣 Shorts pub TikTok créés automatiquement à la fin (teaser → YouTube)</label>
        <select id="promo" style="width:auto"><option value="0">Aucun</option><option value="1">1 short pub</option><option value="2">2 shorts pub</option><option value="3">3 shorts pub</option></select>
        <select id="promochan" style="width:auto"><option value="">sans chaîne</option>${opts(chans.map((c) => [c.id, `→ ${c.emoji} ${c.name}`]), (chans.find((c) => c.kind === 'promo') || {}).id)}</select>
        <span class="small muted">&nbsp;cliffhanger + « vidéo complète sur YouTube » + écran de fin avec la miniature</span></div>
      <div class="field" id="charsel"></div>
      <div class="field"><label>Vidéo YouTube de référence (contexte, optionnel)</label>
        <input type="url" id="url" placeholder="https://www.youtube.com/watch?v=…"></div>
      <div class="field"><label>Contexte / instructions (optionnel)</label>
        <textarea id="topic" placeholder="Angle, public, faits à inclure, choses à éviter…" style="min-height:60px"></textarea></div>
      <div class="field"><label>Mode</label>
        <div class="seg" id="mode"><button data-v="auto" class="on">⚡ Auto — de A à Z</button><button data-v="review">👀 Relecture — je valide prompts & images</button></div>
      </div>
      <div class="row">
        <button id="upload">⬆ Importer un script</button>
        <span id="scriptinfo" class="muted small"></span>
        <span class="spacer"></span>
        <button class="primary" id="create">Créer la vidéo →</button>
      </div>
    </div>
    <div class="tools">
      <a class="card tool" href="#/planning"><div class="ico">📅</div><b>Planning TikTok</b><div class="muted small">Tes chaînes, 2-3 posts par jour préparés à l'avance.</div></a>
      <a class="card tool" href="#/batch"><div class="ico">📄</div><b>Batch CSV</b><div class="muted small">30 vidéos d'un coup, réparties sur les 36 comptes.</div></a>
      <a class="card tool" href="#/thumbs"><div class="ico">🖼️</div><b>Studio miniatures</b><div class="muted small">Des miniatures qui claquent, sans créer de vidéo.</div></a>
      <a class="card tool" href="#/projects"><div class="ico">🎞️</div><b>Projets</b><div class="muted small">Toutes tes vidéos, en cours et archivées.</div></a>
      <a class="card tool" href="#/styles"><div class="ico">🎨</div><b>Styles</b><div class="muted small">Ton d'écriture, voix, style d'image, personnages.</div></a>
      <a class="card tool" href="#/settings"><div class="ico">⚙️</div><b>Réglages</b><div class="muted small">Clés API, modèles, parallélisme.</div></a>
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
      + (recent.length ? `<h2 style="margin-top:22px">Récents</h2><div class="grid3">${recent.map((p) => `
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
    $('#words', el).placeholder = format === 'short' ? '190 (≈ 1 min 15)' : 'selon le style';
    $('#aspect', el).disabled = format === 'short';
    $('#promorow', el).hidden = format === 'short';
    $('#chanrow', el).hidden = format !== 'short';
  });
  $('#chan', el).addEventListener('change', () => {
    const c = chans.find((x) => x.id === $('#chan', el).value);
    if (c) { $('#lang', el).value = c.language; $('#style', el).value = c.style_id; $('#langhint', el).textContent = '(chaîne)'; }
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
    $('#charsel', el).innerHTML = cs.length ? `<label>Personnages permanents dans cette vidéo</label><div class="row">${cs.map((c) => `
      <label class="charpick ${c.auto_include ? 'on' : ''}" title="${esc(c.description)}">
        <input type="checkbox" value="${esc(c.id)}" ${c.auto_include ? 'checked' : ''}>
        ${c.image ? `<img src="/style-media/${st.id}/${c.image}">` : ''}<b>${esc(c.name)}</b></label>`).join('')}</div>` : '';
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
    if (g && !langTouched) { $('#lang', el).value = g; $('#langhint', el).textContent = '(détectée)'; }
  });
  $('#autotitle', el).checked = true;
  $('#upload', el).onclick = () => {
    const m = modal(`<h2>Importer un script</h2><p class="muted">Colle ton texte ou charge un fichier .txt — l'étape Script sera sautée.</p>
      <textarea id="st" style="min-height:300px">${esc(customScript)}</textarea>
      <div class="row" style="margin-top:10px"><input type="file" id="sf" accept=".txt,text/plain"><span class="spacer"></span>
      <button data-close>Annuler</button><button class="primary" id="ok">Utiliser ce script</button></div>`, { wide: true });
    $('#sf', m.el).onchange = async (e) => { const f = e.target.files[0]; if (f) $('#st', m.el).value = await f.text(); };
    $('#ok', m.el).onclick = () => {
      customScript = $('#st', m.el).value.trim();
      $('#scriptinfo', el).textContent = customScript ? `Script importé : ${words(customScript)} mots` : '';
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
const FEATURE_LABELS = { title: 'Titre', script: 'Script', voice: 'Voix', visuals: 'Visuels', render: 'Vidéo', thumbnail: 'Miniature' };
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
  if (p.render) return '<span class="chip">Export disponible - a verifier</span>';
  const waiting = Object.values(p.steps).find((s) => s.msg && s.state !== 'error');
  if (waiting) return `<span class="chip warn">${esc(waiting.msg.slice(0, 40))}</span>`;
  return '<span class="chip">Brouillon</span>';
}

async function viewProjects(el) {
  let archived = 0;
  let layout = localStorage.getItem('layout') || 'grid';
  el.innerHTML = `
    <div class="row" style="margin-bottom:16px"><h1 style="margin:0">Projets</h1><span class="spacer"></span>
      <div class="seg" id="tabs"><button data-v="0" class="on">Actifs</button><button data-v="1">Archivés</button></div>
      <div class="seg" id="layout"><button data-v="grid">▦</button><button data-v="list">☰</button></div>
      <a class="btn primary" href="#/">+ Nouvelle vidéo</a></div>
    <div id="list"></div>`;
  const list = $('#list', el);
  let openMenu = null;
  const render = (ps) => {
    if (!ps.length) { list.innerHTML = `<div class="empty">${archived ? 'Aucun projet archivé.' : 'Aucun projet pour l\'instant. <a href="#/">Crée ta première vidéo</a>.'}</div>`; return; }
    if (layout === 'grid') {
      list.innerHTML = `<div class="grid3">${ps.map((p) => `
        <div class="card pcard" data-id="${p.id}">
          <a class="thumb" href="#/p/${p.id}" style="${p.thumb ? `background-image:url('${media(p.id, p.thumb)}')` : ''}"></a>
          <button class="sm menu-btn" data-menu="${p.id}">⋯</button>
          <div class="body"><a class="title" href="#/p/${p.id}">${p.kind === 'promo' ? '<span class="chip warn">📣 Pub</span> ' : p.format === 'short' ? '<span class="chip run">📱 TikTok</span> ' : ''}${p.slot ? `<span class="chip" title="Créneau de publication">${p.posted ? '📤' : '🗓'} ${esc(p.slot.slice(5, 10).split('-').reverse().join('/'))} ${esc(p.slot.slice(11))}</span> ` : ''}${esc(p.title)}</a>
            <div class="row small muted">${fmtDate(p.created)}${p.duration ? ` · ${fmtTime(p.duration)}` : ''}<span class="spacer"></span>${featureBadge(p.features)}</div>
            <div>${statusChip(p)}</div></div>
        </div>`).join('')}</div>`;
    } else {
      list.innerHTML = `<div class="card" style="padding:0"><table class="list"><tr><th></th><th>Titre</th><th>Date</th><th>Durée</th><th>Avancement</th><th>Statut</th><th></th></tr>
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
      <button data-a="edit">✏️ Ouvrir</button><button data-a="dup">📑 Dupliquer</button>
      ${p.render ? '<button data-a="video">⬇ Télécharger la vidéo</button>' : ''}
      ${p.thumb ? '<button data-a="thumb">🖼 Télécharger la miniature</button>' : ''}
      <button data-a="arch">${p.archived ? '📤 Désarchiver' : '📦 Archiver'}</button>
      <button data-a="del" class="danger">🗑 Supprimer</button></div>`);
    mb.parentElement.append(menu);
    openMenu = menu;
    menu.addEventListener('click', async (ev) => {
      const a = ev.target.closest('[data-a]')?.dataset.a;
      if (!a) return;
      menu.remove(); openMenu = null;
      if (a === 'edit') location.hash = `#/p/${p.id}`;
      if (a === 'dup') await guard(() => api(`/api/projects/${p.id}/duplicate`, { body: {} }), 'Projet dupliqué');
      if (a === 'video') location.href = `/download/${p.id}`;
      if (a === 'thumb') location.href = `/download/${p.id}?what=thumb`;
      if (a === 'arch') await guard(() => api(`/api/projects/${p.id}`, { method: 'PATCH', body: { archived: !p.archived } }));
      if (a === 'del' && confirm(`Supprimer définitivement « ${p.title} » et tous ses fichiers ?`)) await guard(() => api(`/api/projects/${p.id}`, { method: 'DELETE' }), 'Projet supprimé');
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
const TABS = [['script', 'Script'], ['voice', 'Voix off'], ['visuals', 'Visuels'], ['render', 'Rendu'], ['thumbs', 'Miniatures']];
const TAB_STEP = { script: 'script', voice: 'voiceover', visuals: 'visuals', render: 'render', thumbs: 'thumbnail' };

function stepProgress(st) {
  if (st.state !== 'running') return st.state === 'error' ? `<div class="banner err">${esc(st.msg)}</div>` : (st.msg ? `<div class="banner info">${esc(st.msg)}</div>` : '');
  const pct = st.total ? Math.round(100 * st.done / st.total) : 0;
  return `<div class="card inner" style="margin-bottom:14px"><div class="row"><span class="spin"></span><b>${esc(st.msg || 'En cours…')}</b><span class="spacer"></span>
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
  titleEl.textContent = p.title || '(titre généré automatiquement)';
  titleEl.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); titleEl.blur(); } });
  titleEl.addEventListener('blur', async () => {
    const t = titleEl.textContent.trim();
    if (t && t !== p.title) p = await guard(() => api(`/api/projects/${id}`, { method: 'PATCH', body: { title: t } })) || p;
  });

  let logCount = -1;
  const logbox = $('#logbox', el);
  let logBig = localStorage.getItem('logbig') === '1';
  const applyLogSize = () => { logbox.classList.toggle('big', logBig); $('#logtoggle', el).textContent = logBig ? 'Réduire' : 'Agrandir'; };
  $('#logtoggle', el).onclick = () => { logBig = !logBig; localStorage.setItem('logbig', logBig ? '1' : '0'); applyLogSize(); logbox.scrollTop = logbox.scrollHeight; };
  applyLogSize();
  const renderLog = () => {
    const lines = p.log || [];
    const last = lines[lines.length - 1];
    $('#loglast', el).textContent = last ? `dernière activité il y a ${elapsed(last.t)}` : 'rien pour l\'instant';
    if (lines.length === logCount && lines.length < 500) return;
    const atBottom = logbox.scrollHeight - logbox.scrollTop - logbox.clientHeight < 40;
    logCount = lines.length;
    logbox.innerHTML = logLines(lines.slice(-300)) || '<div class="ll muted">Le journal se remplit dès qu\'une génération démarre.</div>';
    if (atBottom || logCount <= 1) logbox.scrollTop = logbox.scrollHeight;
  };
  const renderHead = () => {
    renderLog();
    if (document.activeElement !== titleEl && p.title) titleEl.textContent = p.title;
    $('#modechip', el).innerHTML = p.mode === 'review' ? '👀 Relecture' : '⚡ Auto';
    $('#modechip', el).title = 'Cliquer pour changer de mode';
    $('#runbtns', el).innerHTML = p.running
      ? '<button class="danger" id="stopbtn">■ Arrêter</button>'
      : `<button class="primary" id="runall">${p.render ? '↻ Relancer ce qui manque'
        : Object.values(p.steps).some((s) => s.state === 'error') || p.error ? '▶ Reprendre'
          : p.mode === 'review' ? '▶ Continuer' : '▶ Tout générer'}</button>`;
    const rb = $('#runall', el);
    if (rb) rb.onclick = async () => { await guard(() => api(`/api/projects/${id}/run`, { body: { approve: true } }), 'Génération lancée'); refresh(); };
    const sb = $('#stopbtn', el);
    if (sb) sb.onclick = async () => { await guard(() => api(`/api/projects/${id}/stop`, { body: {} }), 'Arrêt demandé'); refresh(); };
    $('#banner', el).innerHTML = (p.error ? `<div class="banner err">⚠ ${esc(p.error)}</div>` : '')
      + (p.voiceover_stale ? '<div class="banner warn">Le script a changé depuis la voix off — régénère la voix pour mettre à jour les scènes.</div>' : '');
    $('#steps', el).innerHTML = TABS.map(([k, label], i) => {
      const st = p.steps[TAB_STEP[k]];
      const done = k === 'visuals' ? p.features.visuals : k === 'thumbs' ? p.features.thumbnail : st.state === 'done' || (k === 'render' && p.render);
      const cls = st.state === 'running' ? 'running' : st.state === 'error' ? 'error' : done ? 'done' : '';
      const n = st.state === 'running' ? '<span class="spin" style="width:10px;height:10px"></span>' : done ? '✓' : st.state === 'error' ? '!' : i + 1;
      return `<div class="step ${cls} ${k === tab ? 'active' : ''}" data-tab="${k}"><span class="n">${n}</span>${label}</div>`;
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
        <h3>Réglages</h3>
        <div class="field"><label>Longueur cible (mots)</label><input type="number" data-k="settings.script.word_count" value="${s.word_count}" step="100">
          <div class="small muted">≈ ${Math.round(s.word_count / 160)} min de narration</div></div>
        <div class="field"><label>Langue</label><select data-k="settings.language">${opts(LANGUAGES, p.settings.language || 'English')}</select></div>
        <div class="field"><label>Mode d'écriture</label><select data-k="settings.script.mode">${opts([['pro', 'Pro — plan + parties (meilleur)'], ['fast', 'Rapide']], s.mode)}</select></div>
        <div class="field"><label>Vidéo YouTube de contexte</label>
          <div class="row"><input type="url" id="vurl" value="${esc(p.video_url)}" placeholder="https://youtube.com/…" style="flex:1"><button class="sm" id="fetch">Récupérer</button></div>
          <div class="small muted" id="ctxinfo">${p.video_context_words ? `✓ Transcription chargée (${p.video_context_words} mots)` : 'Optionnel — sert de matière première.'}</div></div>
        <div class="field"><label>Contexte / instructions</label><textarea data-k="topic" style="min-height:90px">${esc(p.topic)}</textarea></div>
        <button class="primary" id="gen" style="width:100%;justify-content:center">${p.script ? '↻ Tout réécrire' : '✨ Générer le script'}</button>
      </div>
    </div>
    <div>
      <div id="prog"></div>
      <div class="card">
        <div class="row" style="margin-bottom:10px"><b id="wc"></b><span class="muted small" id="dur"></span><span class="spacer"></span>
          <button class="sm" id="hist">🕘 Historique</button><button class="sm" id="copy">Copier</button><a class="btn sm" href="/download/${p.id}?what=script">.txt</a>
          <button class="sm primary" id="save" disabled>Enregistrer</button></div>
        <div class="row selbar card inner" id="selbar" style="margin-bottom:10px">
          <b class="small">Sélection :</b>
          <button class="sm" data-sel="regenerate">↻ Régénérer</button><button class="sm" data-sel="adjust">✎ Ajuster…</button>
          <button class="sm" data-sel="shorten">− Raccourcir</button><button class="sm" data-sel="lengthen">+ Allonger</button></div>
        <textarea class="editor" id="ed" placeholder="Le script apparaîtra ici. Tu peux aussi coller le tien.">${esc(p.script)}</textarea>
      </div>
    </div>
  </div>`;
  const ed = $('#ed', el);
  let dirty = false;
  const counts = () => { const n = words(ed.value); $('#wc', el).textContent = `${n} mots`; $('#dur', el).textContent = `≈ ${fmtTime(n / 160 * 60)} de voix`; };
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
    if (b.dataset.sel === 'adjust') { instruction = await askText('Comment modifier ce passage ?', 'ex. plus percutant, ajoute un détail sur la nourriture…'); if (!instruction) return; }
    await save();
    b.disabled = true; b.innerHTML = '<span class="spin"></span>';
    const np = await guard(() => api(`/api/projects/${ctx.id}/script/selection`, { body: { start, end, action: b.dataset.sel, instruction } }), 'Passage remplacé');
    b.disabled = false; b.textContent = { regenerate: '↻ Régénérer', adjust: '✎ Ajuster…', shorten: '− Raccourcir', lengthen: '+ Allonger' }[b.dataset.sel];
    if (np) { ctx.p = np; ed.value = np.script; counts(); }
  });
  $('#gen', el).onclick = async () => {
    if (ctx.p.script && !confirm('Réécrire tout le script ? (l\'ancienne version reste dans l\'historique ; la voix et les scènes seront à refaire)')) return;
    await save();
    await ctx.action('script/generate', {}, 'Rédaction lancée');
  };
  $('#fetch', el).onclick = async () => {
    $('#fetch', el).disabled = true;
    const np = await guard(() => api(`/api/projects/${ctx.id}/context/fetch`, { body: { url: $('#vurl', el).value.trim() } }), 'Transcription récupérée');
    $('#fetch', el).disabled = false;
    if (np) { ctx.p = np; $('#ctxinfo', el).textContent = `✓ Transcription chargée (${np.video_context_words} mots)`; }
  };
  $('#copy', el).onclick = () => { navigator.clipboard.writeText(ed.value); toast('Script copié'); };
  $('#hist', el).onclick = async () => {
    const hist = await api(`/api/projects/${ctx.id}/script/history`);
    const m = modal(`<h2>Historique du script</h2><div class="two" style="grid-template-columns:260px 1fr">
      <div id="hl">${hist.map((x, i) => `<div class="history-item" data-i="${i}"><b>${esc(x.kind)}</b><div class="small muted">${fmtDate(x.ts)} · ${x.words} mots (${x.delta >= 0 ? '+' : ''}${x.delta})</div></div>`).reverse().join('') || '<div class="muted">Vide</div>'}</div>
      <div><pre id="hv" style="white-space:pre-wrap;max-height:60vh">Choisis une version à gauche.</pre><div class="row end"><button class="primary" id="restore" disabled>Restaurer cette version</button></div></div></div>`, { wide: true });
    let sel = null;
    $('#hl', m.el).addEventListener('click', (e) => {
      const it = e.target.closest('[data-i]'); if (!it) return;
      sel = +it.dataset.i; $('#hv', m.el).textContent = hist[sel].text; $('#restore', m.el).disabled = false;
    });
    $('#restore', m.el).onclick = async () => {
      const np = await guard(() => api(`/api/projects/${ctx.id}/script/restore`, { body: { index: sel } }), 'Version restaurée');
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
    $('#gen', el).textContent = ctx.p.script ? '↻ Tout réécrire' : '✨ Générer le script';
  };
  update();
  return { update };
}

// --- onglet Voix
function voiceFieldsHtml(v, prefix, voices, local = { installed: false, voices: [] }) {
  const list = voices.map((x) => [x.voice_id, `${x.name}${x.labels ? ` — ${x.labels}` : ''}`]);
  if (v.voice_id && !voices.some((x) => x.voice_id === v.voice_id)) list.unshift([v.voice_id, `${v.voice_name || 'Voix perso'} (${v.voice_id})`]);
  const elevenSel = (list.length ? `<select data-k="${prefix}.voice_id" id="vsel">${opts(list, v.voice_id)}</select>` : '')
    + `<div class="row" style="margin-top:6px"><input type="text" id="vcustom" placeholder="…ou colle l'ID d'une de tes voix ElevenLabs" style="flex:1"><button class="sm" id="vcustomok">Utiliser</button></div>
       <div class="small muted">${STATE.has_elevenlabs ? (voices.some((x) => x.category !== 'premade') ? '' : 'Ta clé ne peut pas lister tes voix : voix standard proposées, ou colle l\'ID de ta voix (Voice Library → ⋯ → Copy voice ID).') : 'Ajoute ta clé ElevenLabs dans Réglages.'}</div>`;
  return `
    <div class="field"><label>Fournisseur</label><select data-k="${prefix}.provider">${opts([['algrow', 'Algrow (voix du studio)'], ['local', 'Voix locale'], ['elevenlabs', 'ElevenLabs'], ['edge', 'Edge']], v.provider)}</select></div>
    <div data-show="algrow" ${v.provider === 'algrow' ? '' : 'hidden'}>
      <div class="field"><label>ID de voix Algrow</label><input type="text" data-k="${prefix}.voice_id" value="${esc(v.voice_id || '')}"></div>
    </div>
    <div data-show="local" ${v.provider === 'local' ? '' : 'hidden'}>
      ${local.installed ? '' : '<div class="banner warn">Voix locale non installée.</div>'}
      <div class="field"><label>Voix (référence imitée) <span class="muted" style="text-transform:none" id="lstatus">${local.health ? `· moteur prêt : ${local.health.workers} processus sur ${esc(local.health.gpu || local.health.device)}, ${local.health.vram_gb} Go` : '· moteur arrêté (démarre tout seul)'}</span></label>
        <select data-k="${prefix}.local_voice">${opts([['', 'Automatique (selon la langue)'], ...local.voices.map((x) => [x.id, `${ACCENT_FLAGS[x.accent] || '🎙️'} ${x.label || x.name}${x.desc ? ` — ${x.desc}` : ''}`])], v.local_voice || '')}</select>
        <a class="small" href="#/voices" style="display:inline-block;margin-top:4px">🎧 Écouter toutes les voix</a>
        <div class="row" style="margin-top:6px"><label class="btn sm">⬆ Importer ma voix (10-20 s)<input type="file" accept="audio/*" hidden id="lupload"></label>
          <span class="small muted">Un extrait propre, sans musique, dans la langue de la vidéo.</span></div></div>
      <div class="field"><label>Moteur</label><select data-k="${prefix}.local_engine">${opts([['auto', 'Automatique — Turbo pour l’anglais (×2 plus rapide), Multilingue sinon'], ['multilingual', 'Multilingue partout (plus expressif, plus lent)']], v.local_engine || 'auto')}</select></div>
      <div class="field"><label>Expressivité : <span data-out="lex">${(+(v.local_exaggeration ?? 0.5)).toFixed(2)}</span></label>
        <input type="range" min="0.25" max="1.5" step="0.05" value="${v.local_exaggeration ?? 0.5}" data-k="${prefix}.local_exaggeration" data-live="lex" style="width:100%">
        <div class="row small muted" style="justify-content:space-between"><span>posée</span><span>dramatique</span></div>
        <div class="small muted">Expressivité et fidélité : moteur Multilingue seulement (le Turbo les ignore).</div></div>
      <div class="field"><label>Fidélité à la référence / rythme : <span data-out="lcf">${(+(v.local_cfg ?? 0.5)).toFixed(2)}</span></label>
        <input type="range" min="0" max="1" step="0.05" value="${v.local_cfg ?? 0.5}" data-k="${prefix}.local_cfg" data-live="lcf" style="width:100%">
        <div class="small muted">Plus bas = débit plus lent et moins d'accent de la référence (utile si la voix de référence n'est pas dans la langue de la vidéo).</div></div>
      <div class="field"><label>Créativité : <span data-out="ltp">${(+(v.local_temperature ?? 0.8)).toFixed(2)}</span></label>
        <input type="range" min="0.4" max="1.2" step="0.05" value="${v.local_temperature ?? 0.8}" data-k="${prefix}.local_temperature" data-live="ltp" style="width:100%"></div>
    </div>
    <div data-show="elevenlabs" ${v.provider === 'elevenlabs' ? '' : 'hidden'}>
      <div class="field"><label>Voix</label>${elevenSel}</div>
      <div class="field"><label>Modèle</label><select data-k="${prefix}.model_id">${opts(ELEVEN_MODELS, v.model_id)}</select></div>
      <div class="field"><label>Interprétation</label><select data-k="${prefix}.delivery">${opts([['stable', 'Stable'], ['balanced', 'Équilibrée'], ['creative', 'Créative']], v.delivery)}</select></div>
    </div>
    <div data-show="edge" ${v.provider === 'edge' ? '' : 'hidden'}>
      <div class="field"><label>Voix Edge</label><select data-k="${prefix}.edge_voice">${opts(EDGE_VOICES, v.edge_voice)}</select></div>
    </div>
    <div class="field"><label>Vitesse : <span id="spd">${(+v.speed).toFixed(2)}×</span></label>
      <input type="range" min="0.8" max="1.2" step="0.05" value="${v.speed}" data-k="${prefix}.speed" style="width:100%"></div>
    <div class="row" style="margin-bottom:14px"><button class="sm" id="vpreview">🔊 Tester la voix</button><audio id="vaudio" style="flex:1;height:32px" controls hidden></audio></div>
    <div class="field"><label>Couper les silences</label><select data-k="${prefix}.cut_silences">${opts([['none', 'Non'], ['smooth', 'Doux (0,75 s)'], ['natural', 'Naturel (0,5 s)'], ['jumpy', 'Nerveux (0,25 s)']], v.cut_silences)}</select></div>`;
}
function wireVoiceFields(el, getVoice, getLang) {
  const up = $('#lupload', el);
  if (up) {
    up.onchange = async (e) => {
      const f = e.target.files[0]; if (!f) return;
      const name = await askText('Nom de cette voix', 'ex. Mon narrateur FR', f.name.replace(/\.[^.]+$/, ''));
      if (!name) return;
      const fd = new FormData(); fd.append('name', name); fd.append('file', f);
      const vs = await guard(() => api('/api/local-tts/voices', { form: fd, method: 'POST' }), 'Voix ajoutée');
      if (vs) {
        localInfoCache = null;
        const sel = $('[data-k$="local_voice"]', el);
        sel.innerHTML = opts([['', 'Automatique (selon la langue)'], ...vs.map((x) => [x.id, x.name])], `${name}.wav`);
        sel.dispatchEvent(new Event('change'));
      }
    };
  }
  const pv = $('#vpreview', el);
  if (pv && getVoice) {
    pv.onclick = async () => {
      pv.disabled = true; pv.innerHTML = '<span class="spin"></span> Génération…';
      const r = await guard(() => api('/api/voice/preview', { body: { voice: getVoice(), language: getLang ? getLang() : null } }));
      pv.disabled = false; pv.textContent = '🔊 Tester la voix';
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
      if (!/^[A-Za-z0-9]{16,40}$/.test(id)) return toast('ID de voix invalide', true);
      let sel = $('#vsel', el);
      if (!sel) return;
      if (![...sel.options].some((o) => o.value === id)) sel.prepend(new Option(`Voix perso (${id})`, id));
      sel.value = id;
      sel.dispatchEvent(new Event('change'));
      $('#vcustom', el).value = '';
    };
  }
}

function tabVoice(el, ctx) {
  const p = ctx.p;
  el.innerHTML = `<div class="two"><div class="card" id="vf"><h3>Réglages voix</h3><div class="muted">Chargement des voix…</div></div>
    <div><div id="prog"></div><div class="card" id="player"></div></div></div>`;
  (async () => {
    const [voices, local] = await Promise.all([elevenVoices(), localInfo(true)]);
    const chars = (ctx.p.script || '').length;
    $('#vf', el).innerHTML = `<h3>Réglages voix</h3>${voiceFieldsHtml(p.settings.voice, 'settings.voice', voices, local)}
      <div class="card inner small" style="margin-bottom:12px">📏 Script : <b>${chars.toLocaleString('fr-FR')}</b> caractères
        ≈ <b>${chars.toLocaleString('fr-FR')}</b> crédits ElevenLabs (1 crédit / caractère en Multilingual v2, ½ en Flash/Turbo).
        Les morceaux déjà générés sont en cache : une relance ne les refacture pas.</div>
      <button class="primary" id="gen" style="width:100%;justify-content:center">🎙 Générer la voix off</button>
      <div class="small muted" style="margin-top:8px">Même script + autre voix = scènes et images conservées (seuls les timings changent).</div>`;
    wireVoiceFields($('#vf', el), () => ctx.p.settings.voice, () => ctx.p.settings.language);
    bindFields($('#vf', el), async (obj, inp) => {
      if (inp.id === 'vsel') setPath(obj, 'settings.voice.voice_name', inp.options[inp.selectedIndex].text.split(' — ')[0]);
      await ctx.patch(obj);
    });
    $('#gen', el).onclick = async () => {
      if (ctx.p.voiceover_stale && ctx.p.scenes.some((s) => s.image)
        && !confirm('Le script a changé : les scènes vont être redécoupées et les images actuelles perdues. Continuer ?')) return;
      await ctx.action('voiceover/generate', {}, 'Synthèse lancée');
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
        ? `<h3>Voix off</h3><audio controls src="${media(pp.id, vo.file)}?t=${vo.ts}"></audio>
           <div class="row small muted" style="margin-top:8px">Durée ${fmtTime(vo.duration)} · ${pp.scenes.length} scènes · ${esc(vo.provider)} ${esc(vo.voice || '')}
           <span class="spacer"></span><a class="btn sm" href="/download/${pp.id}?what=voice">⬇ MP3</a></div>`
        : `<div class="empty">${pp.script ? 'Pas encore de voix off.' : 'Écris ou importe un script d\'abord.'}</div>`;
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
        <div style="width:200px"><label>Modèle d'image</label><select data-k="settings.visuals.image_model">${opts(IMAGE_MODELS, v.image_model)}</select></div>
        <div style="width:150px"><label>Mouvement : <span data-out="ms">${(+v.motion_strength).toFixed(1)}</span></label><input type="range" min="0" max="2" step="0.1" data-k="settings.visuals.motion_strength" value="${v.motion_strength}" data-live="ms" style="width:100%"></div>
        <label class="check"><input type="checkbox" data-k="settings.visuals.use_style_refs" ${v.use_style_refs ? 'checked' : ''}> Images de réf. du style</label>
        <label class="check"><input type="checkbox" data-k="settings.visuals.use_character_refs" ${v.use_character_refs ? 'checked' : ''}> Persos cohérents</label>
        <label class="check"><input type="checkbox" data-k="settings.visuals.captions" ${v.captions ? 'checked' : ''}> Sous-titres incrustés</label>
        <div style="width:300px"><label>Continuité entre images</label><select data-k="settings.visuals.continuity">${opts([['smart', '⛓ Intelligente — scènes liées dessinées à partir de la précédente'], ['always', 'Totale — chaque image part de la précédente (lent)'], ['off', 'Aucune — toutes en parallèle (rapide)']], v.continuity || 'smart')}</select></div>
      </div>
      <div class="card inner" style="margin-top:14px">
        <div class="row" style="align-items:flex-end">
          <div style="flex:1;min-width:260px">
            <label>Durée moyenne d'une image : <b style="color:var(--accent);font-size:15px" data-out="avg">${(+v.avg_scene_seconds).toFixed(1)} s</b></label>
            <input type="range" min="1" max="10" step="0.1" value="${v.avg_scene_seconds}" id="avg" class="big" style="width:100%">
            <div class="row small muted" style="justify-content:space-between"><span>1 s · rythme nerveux</span><span id="estim"></span><span>10 s · contemplatif</span></div>
          </div>
          <div style="width:90px"><label>Min (s)</label><input type="number" step="0.1" min="0.5" max="10" id="minsc" value="${v.min_scene_seconds}"></div>
          <div style="width:90px"><label>Max (s)</label><input type="number" step="0.1" min="1" max="30" id="maxsc" value="${v.max_scene_seconds}"></div>
          <button id="resplit">✂ Redécouper les scènes</button>
        </div>
        <div class="small muted" style="margin-top:6px">Les coupes tombent toujours sur les pauses naturelles de la voix (fins de phrases en priorité). Redécouper efface les prompts et images actuels.</div>
      </div>
    </div>
    <div class="card"><div class="row"><h3 style="margin:0">Personnages récurrents</h3>
        <span class="muted small">Coche « Garder » pour ceux qui doivent rester identiques d'une image à l'autre.</span><span class="spacer"></span>
        <button class="sm primary" id="detect">✨ Générer les personnages</button><button class="sm" id="library">📚 Bibliothèque</button><button class="sm" id="addchar">+ Ajouter à la main</button></div>
      <div class="chars" id="chars" style="margin-top:12px"></div></div>
    <div class="card">
      <div class="row" id="actions"></div>
      <div class="row" style="margin-top:12px">
        <div class="seg" id="sview"><button data-v="list">☰ Liste</button><button data-v="grid">▦ Grille</button></div>
        <select id="sfilter" style="width:auto"><option value="all">Toutes les scènes</option><option value="noimg">Sans image</option><option value="err">En échec</option></select>
        <span class="spacer"></span>
        <button id="preview">▶ Aperçu animé</button>
      </div>
    </div>
    <div class="scenes" id="scenes" style="margin-top:14px"></div>`;
  bindFields(el, async (obj) => { await ctx.patch(obj); });

  const avg = $('#avg', el);
  const estim = () => {
    const d = ctx.p.voiceover ? ctx.p.voiceover.duration : words(ctx.p.script) / 160 * 60;
    $('[data-out="avg"]', el).textContent = `${(+avg.value).toFixed(1)} s`;
    $('#estim', el).textContent = d ? `≈ ${Math.max(1, Math.round(d / avg.value))} images pour ${fmtTime(d)}` : '';
  };
  avg.addEventListener('input', estim);
  estim();
  const saveDurations = async () => ctx.patch({ settings: { visuals: {
    avg_scene_seconds: +avg.value, min_scene_seconds: +$('#minsc', el).value, max_scene_seconds: +$('#maxsc', el).value } } });
  [avg, $('#minsc', el), $('#maxsc', el)].forEach((i) => i.addEventListener('change', saveDurations));
  $('#resplit', el).onclick = async () => {
    if (!ctx.p.voiceover) return toast('Génère la voix off d\'abord', true);
    const n = ctx.p.scenes.filter((s) => s.image || s.prompt).length;
    if (n && !confirm(`Redécouper efface les prompts et images de ${n} scène(s). Continuer ?`)) return;
    await saveDurations();
    const np = await guard(() => api(`/api/projects/${ctx.id}/visuals/resplit`, { body: {
      avg_scene_seconds: +avg.value, min_scene_seconds: +$('#minsc', el).value, max_scene_seconds: +$('#maxsc', el).value } }));
    if (np) { ctx.p = np; mountScenes(); renderActions(); toast(`${np.scenes.length} scènes`); }
  };

  const scenesEl = $('#scenes', el);
  const sigs = {};
  let charSig = '';
  const vertical = () => ctx.p.settings.visuals.aspect === '9:16';
  const imgInner = (s) => {
    const st = s.status === 'running' ? '<div class="st"><span class="spin"></span>&nbsp;Génération…</div>'
      : s.status === 'queued' ? '<div class="st">En file d\'attente…</div>' : '';
    return (s.image ? `<img loading="lazy" src="${media(ctx.p.id, s.image)}">` : '<span>Pas d\'image</span>') + st;
  };
  const sceneHtml = (s) => `
    <div class="card scene ${s.status === 'error' ? 'err' : ''}" data-sid="${s.id}">
      <div><div class="img ${vertical() ? 'vertical' : ''}" data-act="zoom">${imgInner(s)}</div>
        <div class="row" style="margin-top:8px;gap:6px">
          <button class="sm" data-act="regen" title="Refaire avec le même prompt">↻</button>
          <button class="sm" data-act="mine" title="Refaire avec TON prompt">✍ Mon prompt</button>
          <button class="sm" data-act="fix" title="L'IA regarde l'image et ses voisines, comprend ce qui cloche et la refait">🧠 Corriger</button>
          <button class="sm" data-act="full" title="Nouveau prompt écrit par l'IA (scènes d'avant/après)">✎ Nouveau</button>
          <button class="sm" data-act="adjust" title="Retoucher l'image actuelle (ex. : de nuit)">🪄</button>
          <label class="btn sm" title="Importer ta propre image">⬆<input type="file" accept="image/*" hidden data-act="upload"></label>
          <button class="sm danger" data-act="del" title="Supprimer (fusion avec la précédente)">✕</button>
        </div></div>
      <div>
        <div class="meta"><b>#${s.id}</b><span>${fmtTime(s.start)} → ${fmtTime(s.end)}</span><span>${(s.end - s.start).toFixed(1)} s</span>
          <select class="sm" data-f="motion" style="width:auto;padding:3px 6px">${opts(MOTIONS, s.motion || 'zoom_in')}</select>
          ${(s.characters || []).map((c) => `<span class="chip">${esc(c)}</span>`).join('')}
          ${s.continues ? `<span class="chip" title="${esc(s.link || 'suite de la scène précédente')}">⛓ suite de #${s.id - 1}</span>` : ''}</div>
        <div class="text">${esc(s.text)}</div>
        <textarea data-f="prompt" placeholder="Prompt de l'image (écrit automatiquement)">${esc(s.prompt)}</textarea>
        <div class="small critique" data-f="critique">${s.critique ? `🧠 ${esc(s.critique)}` : ''}</div>
        <div class="small" style="color:var(--err)" data-f="error">${esc(s.error || '')}</div>
      </div>
    </div>`;
  const mountScenes = () => {
    const sc = ctx.p.scenes;
    scenesEl.innerHTML = sc.length ? sc.map(sceneHtml).join('') : '<div class="card empty">Les scènes apparaissent après la génération de la voix off.</div>';
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
      await guard(() => api(`/api/projects/${ctx.id}/scenes/${sid}/upload`, { form: fd, method: 'POST' }), 'Image importée');
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
      const prompt = await askText(`Ton prompt pour la scène #${sid}`, 'Décris l\'image voulue (le style est ajouté automatiquement)', s.prompt || '');
      if (prompt) { await guard(() => api(`/api/projects/${ctx.id}/scenes/${sid}/regenerate`, { body: { mode: 'custom', prompt } }), 'Image en cours avec ton prompt'); ctx.refresh(); }
    }
    if (act === 'fix') {
      const reason = await askText('Qu\'est-ce qui ne va pas ? (optionnel)', 'ex. il y a un vrai humain, ça ne ressemble pas à la scène d\'avant, mauvais lieu… Laisse vide : l\'IA trouve toute seule.');
      if (reason === null && !confirm('Laisser l\'IA trouver toute seule ce qui cloche ?')) return;
      await guard(() => api(`/api/projects/${ctx.id}/scenes/${sid}/regenerate`, { body: { mode: 'fix', instruction: reason || '' } }), 'L\'IA analyse l\'image et ses voisines…');
      ctx.refresh();
    }
    if (act === 'adjust') {
      if (!s.image) return toast('Pas encore d\'image à ajuster', true);
      const instruction = await askText('Retoucher l\'image', 'ex. fais-le de nuit, ajoute de la neige, plan plus serré…');
      if (instruction) { await guard(() => api(`/api/projects/${ctx.id}/scenes/${sid}/regenerate`, { body: { mode: 'adjust', instruction } })); ctx.refresh(); }
    }
    if (act === 'del' && confirm(`Supprimer la scène #${sid} ? Son texte et sa durée sont fusionnés avec la scène précédente.`)) {
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
          ${busyImg ? '<span class="chip run"><span class="spin"></span>Fiche en cours…</span>' : c.image ? '' : (c.error ? `<span class="small" style="color:var(--err)" title="${esc(c.error)}">⚠ échec</span>` : 'Pas de fiche')}</div>
        <label class="check keep"><input type="checkbox" data-cf="enabled" ${on ? 'checked' : ''}> Garder</label>
        <input type="text" data-cf="name" value="${esc(c.name)}" style="margin:6px 0">
        <textarea data-cf="description" style="min-height:80px;font-size:12px">${esc(c.description)}</textarea>
        <div class="row small muted" style="margin:6px 0">${c.role === 'protagonist' ? '<span class="chip ok">Protagoniste</span>' : ''}
          ${used[c.id] ? `<span>${used[c.id]} scène(s)</span>` : c.scenes_estimate ? `<span>~${c.scenes_estimate} scènes</span>` : ''}
          <span class="spacer"></span><label class="check small"><input type="checkbox" data-cf="every_image" ${c.every_image ? 'checked' : ''}> Partout</label></div>
        <div class="row"><button class="sm" data-ca="img" ${busyImg ? 'disabled' : ''}>${c.image ? '↻ Nouvelle fiche' : '✨ Créer la fiche'}</button><span class="spacer"></span><button class="sm danger" data-ca="del">✕</button></div>
      </div>`;
    }).join('') : '<div class="muted small">Clique sur « Générer les personnages » : l\'IA lit le script, propose les personnages récurrents et dessine leur fiche. Tu gardes ceux que tu veux.</div>';
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
      const np = await guard(() => api(`/api/projects/${ctx.id}/characters/${card.dataset.cid}/image`, { body: {} }), 'Fiche en cours (~40 s)');
      if (np) { ctx.p = np; charSig = ''; renderChars(); }
    }
    if (a === 'del' && confirm('Supprimer ce personnage ?')) {
      const np = await guard(() => api(`/api/projects/${ctx.id}/characters/${card.dataset.cid}`, { method: 'DELETE' }));
      if (np) { ctx.p = np; charSig = ''; renderChars(); }
    }
  });
  $('#library', el).onclick = async () => {
    const st = await api(`/api/styles/${ctx.p.style_id}`);
    const have = new Set((ctx.p.characters || []).map((c) => c.id));
    const cs = st.characters || [];
    const m = modal(`<h2>Bibliothèque de personnages</h2><p class="muted">Personnages permanents du style « ${esc(st.name)} » — clique pour l'ajouter à cette vidéo (sa fiche reste identique d'une vidéo à l'autre).</p>
      <div class="chars">${cs.map((c) => `<div class="card inner char ${have.has(c.id) ? 'off' : ''}" data-lib="${esc(c.id)}" style="cursor:${have.has(c.id) ? 'default' : 'pointer'}">
        <div class="cimg" style="${c.image ? `background-image:url('/style-media/${st.id}/${c.image}')` : ''}">${c.image ? '' : 'Pas de fiche'}</div>
        <b>${esc(c.name)}</b><div class="small muted">${have.has(c.id) ? '✓ déjà dans la vidéo' : 'Cliquer pour ajouter'}</div></div>`).join('') || '<div class="muted">Aucun personnage permanent : crée-les dans Styles.</div>'}</div>
      <div class="row end" style="margin-top:12px"><a class="btn" href="#/styles/${ctx.p.style_id}">Gérer dans Styles</a><button data-close>Fermer</button></div>`, { wide: true });
    m.el.addEventListener('click', async (e) => {
      const card = e.target.closest('[data-lib]'); if (!card || have.has(card.dataset.lib)) return;
      const np = await guard(() => api(`/api/projects/${ctx.id}/characters/from-style`, { body: { id: card.dataset.lib } }), 'Personnage ajouté');
      if (np) { ctx.p = np; charSig = ''; renderChars(); m.close(); }
    });
  };
  $('#detect', el).onclick = async () => {
    if (!ctx.p.script) return toast('Il faut un script d\'abord', true);
    await ctx.action('characters/detect', {}, 'Lecture du script… les personnages arrivent');
  };
  $('#addchar', el).onclick = async () => {
    const m = modal(`<h2>Nouveau personnage</h2><div class="field"><label>Nom</label><input type="text" id="cn"></div>
      <div class="field"><label>Description visuelle</label><textarea id="cd" placeholder="âge, tenue, couleurs, accessoires…"></textarea></div>
      <label class="check"><input type="checkbox" id="ce"> Dans toutes les images</label>
      <div class="small muted" style="margin-top:6px">La fiche de référence est dessinée automatiquement.</div>
      <div class="row end"><button data-close>Annuler</button><button class="primary" id="ok">Ajouter</button></div>`);
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
    $('#actions', el).innerHTML = !sc.length ? '<span class="muted">Génère la voix off d\'abord : les scènes sont calées dessus.</span>' : `
      <b>${sc.length} scènes</b><span class="muted">· ${nPrompt} prompts · ${nImg} images${nErr ? ` · <span style="color:var(--err)">${nErr} en échec</span>` : ''}</span>
      <span class="spacer"></span>
      <button ${dis} id="prompts">${nPrompt ? '↻ Réécrire tous les prompts' : '✍️ Écrire les prompts'}</button>
      ${nErr ? `<button ${dis} id="failed">↻ Relancer les échecs</button>` : ''}
      ${missing >= 10 ? `<button ${dis} id="next10">Générer les 10 suivantes</button>` : ''}
      <button class="primary" ${dis} id="all">${missing ? `🖼 Générer ${missing === sc.length ? 'toutes les' : 'les'} ${missing} images` : '↻ Tout régénérer'}</button>`;
    const on = (sel, fn) => { const b = $(sel, el); if (b) b.onclick = fn; };
    on('#prompts', async () => { if (nPrompt && !confirm('Réécrire tous les prompts (tes modifications seront perdues) ?')) return; await ctx.action('visuals/prompts', { all: nPrompt > 0 }, 'Écriture des prompts lancée'); });
    on('#failed', () => ctx.action('visuals/images', { scope: 'failed' }, 'Relance des échecs'));
    on('#next10', () => ctx.action('visuals/images', { scope: 'next10' }, '10 images lancées'));
    on('#all', async () => {
      if (!missing && !confirm('Régénérer TOUTES les images ?')) return;
      await ctx.action('visuals/images', missing ? { scope: 'all' } : { scope: 'ids', ids: sc.map((s) => s.id) }, 'Génération des images lancée');
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
    if (!pp.voiceover) return toast('Pas encore de voix off', true);
    const m = modal(`<div class="pv"><div class="pvframe ${vertical() ? 'vertical' : ''}"><img id="pvi"><div class="pvcap" id="pvc"></div>
      <div class="pvnum" id="pvn"></div></div>
      <audio controls id="pva" src="${media(pp.id, pp.voiceover.file)}?t=${pp.voiceover.ts}"></audio>
      <div class="pvstrip" id="pvs">${pp.scenes.map((s) => `<div data-t="${s.start}" title="#${s.id}" style="flex:${(s.end - s.start).toFixed(2)};${s.image ? `background-image:url('${media(pp.id, s.image)}')` : ''}"></div>`).join('')}</div>
      <div class="row end" style="margin-top:10px"><span class="small muted">Aperçu approximatif — le rendu final a des mouvements plus fluides.</span><span class="spacer"></span><button data-close>Fermer</button></div></div>`, { wide: true });
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
      <div class="card"><h3>🎬 Montage dans DaVinci Resolve</h3>
        <div class="small muted" style="margin-bottom:10px">TubeForge ouvre Resolve et construit la timeline : V1 scènes, V2 sous-titres, V3 accroche, A1 voix, A2 bruitages. Tout reste modifiable, puis rendu par Resolve.</div>
        <div id="resinfo" class="small" style="margin-bottom:10px"></div>
        <div class="row"><button class="primary" id="toresolve">🎬 Monter dans Resolve + rendu</button><button id="toresolve2">Timeline seule</button></div></div>
      <div class="card"><h3>📄 Récap de montage</h3>
        <div class="small muted" style="margin-bottom:10px">Tout le texte (script, accroche, légende TikTok, hashtags), les scènes, les sous-titres minutés et les bruitages.</div>
        <a class="btn" href="/download/${ctx.id}?what=montage">⬇ MONTAGE.md</a></div>
      <div class="card" id="shortscard"><h3>📱 Shorts TikTok de cette vidéo</h3>
        <div class="small muted" style="margin-bottom:10px">Verticaux, accroche « grand jeu », sous-titres, bruitages, voix locale.</div>
        <div class="field"><select id="kshorts"><option value="promo">📣 Pub pour la vidéo YouTube — teaser, cliffhanger, « vidéo complète sur YouTube » + écran de fin</option>
          <option value="standalone">📱 TikTok autonome — histoire complète, se suffit à elle-même</option></select></div>
        <div class="row"><select id="nshorts" style="width:auto"><option>1</option><option selected>2</option><option>3</option></select>
          <select id="cshorts" style="width:auto"><option value="">sans chaîne</option></select>
          <button class="primary" id="mkshorts">✂ Créer les shorts</button><span class="small muted" id="childinfo"></span></div></div>
      <div class="card" id="chancard" hidden><h3>📅 Chaîne TikTok</h3>
        <div class="small muted" style="margin-bottom:10px">Le short est rangé dans le planning de la chaîne (créneau de publication, export, projet Resolve de la chaîne).</div>
        <div class="row"><select id="chsel" style="width:auto"><option value="">— aucune —</option></select><span class="small" id="slotinfo"></span></div></div>
    </div>`;
  api('/api/channels').then((chans) => {
    const o = opts(chans.map((c) => [c.id, `${c.emoji} ${c.name}`]));
    $('#cshorts', el).insertAdjacentHTML('beforeend', o);
    $('#chsel', el).insertAdjacentHTML('beforeend', o);
    $('#chsel', el).value = ctx.p.channel_id || '';
    $('#chsel', el).onchange = async () => {
      const r = await guard(() => api(`/api/projects/${ctx.id}/channel`, { body: { channel_id: $('#chsel', el).value || null } }), 'Chaîne mise à jour');
      if (r) Object.assign(ctx.p, { channel_id: r.channel_id, post: r.post });
    };
  }).catch(() => {});
  $('#toresolve', el).onclick = () => ctx.action('resolve', { render: true }, 'Resolve s\'ouvre — construction de la timeline…');
  $('#toresolve2', el).onclick = () => ctx.action('resolve', { render: false }, 'Construction de la timeline dans Resolve…');
  $('#mkshorts', el).onclick = async () => {
    await guard(() => api(`/api/projects/${ctx.id}/shorts`, { body: { count: +$('#nshorts', el).value, kind: $('#kshorts', el).value, channel_id: $('#cshorts', el).value || null } }), 'Création des shorts lancée — ils apparaîtront dans Projets');
  };
  let lastTs = undefined;
  const update = () => {
    const p = ctx.p;
    $('#prog', el).innerHTML = stepProgress(p.steps.render);
    $('#prog2', el).innerHTML = p.steps.resolve ? stepProgress(p.steps.resolve) : '';
    const rs = p.resolve;
    $('#resinfo', el).innerHTML = rs ? `✓ Projet <b>${esc(rs.project)}</b>, timeline <b>${esc(rs.timeline)}</b> (${rs.placed}/${rs.expected} éléments)
      ${rs.render_status ? ` — rendu : ${esc(rs.render_status)} <a href="/download/${p.id}?what=resolve">⬇ vidéo Resolve</a>` : ''}` : '';
    $('#shortscard', el).hidden = p.format === 'short';
    $('#chancard', el).hidden = p.format !== 'short';
    $('#slotinfo', el).innerHTML = p.post && p.post.slot ? `&nbsp;🗓 ${esc(dayLabel(p.post.slot.slice(0, 10)))} à ${esc(p.post.slot.slice(11))}${p.post.posted ? ' — 📤 publié' : ''} · <a href="#/planning/${p.channel_id}">voir le planning</a>` : '';
    ['#toresolve', '#toresolve2'].forEach((sel) => { $(sel, el).disabled = p.running || !p.voiceover || p.scenes.some((x) => !x.image); });
    const r = p.render;
    const missing = p.scenes.filter((s) => !s.image).length;
    const key = `${r && r.ts}|${missing}|${p.running}|${!!p.voiceover}`;
    if (key === lastTs) return;
    lastTs = key;
    $('#rc', el).innerHTML = `
      ${r ? `<video controls preload="metadata" src="${media(p.id, r.file)}?t=${r.ts}" style="max-height:70vh"></video>
        <div class="row" style="margin-top:12px"><b>${esc(p.title)}</b><span class="muted">· ${fmtTime(r.duration)} · ${r.width}×${r.height}</span><span class="spacer"></span>
          <a class="btn primary" href="/download/${p.id}">⬇ Télécharger la vidéo</a><a class="btn" href="/download/${p.id}?what=srt">Sous-titres .srt</a>
          <a class="btn" href="/download/${p.id}?what=voice">Voix .mp3</a><a class="btn" href="/download/${p.id}?what=script">Script .txt</a></div>`
        : `<div class="empty">${!p.voiceover ? 'Il faut d\'abord la voix off et les images.' : missing ? `${missing} scène(s) sans image — termine l'étape Visuels.` : 'Tout est prêt pour le rendu.'}</div>`}
      <div class="row end" style="margin-top:12px"><button class="primary" id="go" ${p.running || missing || !p.voiceover ? 'disabled' : ''}>🎬 ${r ? 'Refaire le rendu' : 'Lancer le rendu'}</button></div>`;
    $('#go', el).onclick = () => ctx.action('render', {}, 'Rendu lancé');
  };
  update();
  return { update };
}

// --- onglet Miniatures
function tabThumbs(el, ctx) {
  el.innerHTML = `<div id="prog"></div>
    <div class="card"><div class="row" style="align-items:flex-end">
      <div style="width:110px"><label>Nombre</label><input type="number" id="n" min="1" max="6" value="2"></div>
      <div style="flex:1;min-width:240px"><label>Instructions (optionnel)</label><input type="text" id="ins" placeholder="ex. mains qui tiennent une lettre, texte « 24 HOURS »"></div>
      <button class="primary" id="gen">✨ Générer des miniatures</button></div>
      <div class="small muted" style="margin-top:8px">Style défini dans le Style du projet (POV mains au premier plan, roman graphique…).</div></div>
    <div class="thumbs" id="grid" style="margin-top:14px"></div>`;
  let sig = '';
  $('#gen', el).onclick = () => ctx.action('thumbnails', { count: +$('#n', el).value || 2, instruction: $('#ins', el).value }, 'Miniatures en cours (~40 s)');
  $('#grid', el).addEventListener('click', async (e) => {
    const t = e.target.closest('[data-i]'); if (!t) return;
    if (e.target.closest('[data-zoom]')) return lightbox(media(ctx.p.id, ctx.p.thumbnails[+t.dataset.i].file));
    const np = await guard(() => api(`/api/projects/${ctx.id}/thumbnails/select`, { body: { index: +t.dataset.i } }), 'Miniature principale choisie');
    if (np) { ctx.p = np; sig = ''; update(); }
  });
  const update = () => {
    const p = ctx.p;
    $('#prog', el).innerHTML = stepProgress(p.steps.thumbnail);
    const s = JSON.stringify([p.thumbnails, p.thumbnail_selected]);
    if (s === sig) return;
    sig = s;
    $('#grid', el).innerHTML = (p.thumbnails || []).map((t, i) => `<div class="t ${i === p.thumbnail_selected ? 'sel' : ''}" data-i="${i}" title="Cliquer pour la choisir">
      <img src="${media(p.id, t.file)}"><button class="sm" data-zoom style="position:absolute;top:6px;right:6px">🔍</button>
      ${i === p.thumbnail_selected ? '<span class="chip ok" style="position:absolute;top:6px;left:6px">★ Principale</span>' : ''}</div>`).join('')
      || '<div class="muted">Aucune miniature pour l\'instant.</div>';
  };
  update();
  return { update };
}

// ------------------------------------------------------------------ studio miniatures
async function viewThumbStudio(el) {
  const styles = await api('/api/styles');
  const tsm = (rel) => `/thumbstudio-media/${rel}`;
  el.innerHTML = `
    <div class="row" style="margin-bottom:16px"><h1 style="margin:0">Studio miniatures</h1><span class="muted">— des miniatures qui donnent envie de cliquer, sans créer de vidéo.</span></div>
    <div class="two" style="grid-template-columns:380px 1fr">
      <div class="card" style="position:sticky;top:16px">
        <div class="field"><label>Titre de la vidéo</label><input type="text" id="t" placeholder="POV: You're a Spy in 1960s Berlin"></div>
        <div class="field"><label>Idée / ce qui doit se passer</label><textarea id="i" placeholder="ex. mes mains tiennent un dossier TOP SECRET, une silhouette derrière la vitre…" style="min-height:90px"></textarea></div>
        <div class="field"><label>Texte sur la miniature (optionnel)</label><input type="text" id="tx" placeholder="ex. 24 HOURS LEFT — vide = l'IA décide"></div>
        <div class="grid2">
          <div class="field"><label>Style</label><select id="st">${opts(styles.map((s) => [s.id, s.name]))}</select></div>
          <div class="field"><label>Format</label><select id="ar"><option>16:9</option><option>9:16</option><option>1:1</option></select></div>
        </div>
        <div class="field"><label>Nombre de variantes : <b data-out="n">4</b></label><input type="range" id="n" min="1" max="8" step="1" value="4" style="width:100%"></div>
        <div class="field"><label>Image d'inspiration (optionnel)</label><input type="file" id="ref" accept="image/*">
          <img id="refprev" style="display:none;width:100%;border-radius:8px;margin-top:8px">
          <div class="small muted">Une miniature qui marche chez un concurrent : elle sera redessinée dans ton style.</div></div>
        <details class="field"><summary class="small muted" style="cursor:pointer">Style personnalisé pour cette série</summary>
          <textarea id="sx" placeholder="Laisse vide pour utiliser le style de miniatures du Style choisi" style="margin-top:8px"></textarea></details>
        <button class="primary" id="go" style="width:100%;justify-content:center">✨ Générer les miniatures</button>
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
      : it.status === 'error' ? `<div class="small" style="color:var(--err);padding:10px">⚠ ${esc(it.error || 'échec')}</div>`
        : `<div class="chip run"><span class="spin"></span>${it.status === 'queued' ? 'Concept…' : 'Dessin…'}</div>`;
    return `<div class="tsi" data-set="${s.id}" data-it="${it.id}" style="aspect-ratio:${ratio}">${inner}
      ${it.file ? `<div class="tsa">
        <button class="sm" data-a="zoom" title="Agrandir">🔍</button><a class="btn sm" href="/thumbstudio-download/${it.file}" title="Télécharger">⬇</a>
        <button class="sm" data-a="edit" title="Retoucher">🪄</button><button class="sm" data-a="var" title="Variantes proches">♻</button>
        <button class="sm" data-a="proj" title="Envoyer vers un projet">➜🎞</button><button class="sm danger" data-a="del" title="Supprimer">✕</button></div>` : ''}
      ${it.instruction ? `<span class="chip" style="position:absolute;left:6px;bottom:6px">🪄 ${esc(it.instruction.slice(0, 30))}</span>` : ''}</div>`;
  };
  const render = () => {
    $('#sets', el).innerHTML = sets.length ? sets.map((s) => `
      <div class="card" style="margin-bottom:16px">
        <div class="row" style="margin-bottom:10px"><div><b>${esc(s.title || s.idea.slice(0, 60))}</b>
          <div class="small muted">${fmtDate(s.created)} · ${s.aspect}${s.text ? ` · texte « ${esc(s.text)} »` : ''}${s.ref ? ' · avec inspiration' : ''}</div></div>
          <span class="spacer"></span>${s.ref ? `<img src="${tsm(s.ref)}" style="height:40px;border-radius:6px">` : ''}
          <button class="sm" data-more="${s.id}">+2 variantes</button><button class="sm danger" data-delset="${s.id}">Supprimer la série</button></div>
        <div class="tsgrid">${s.items.map((it) => itemHtml(s, it)).join('')}</div>
      </div>`).join('') : '<div class="card empty">Tes miniatures apparaîtront ici. Exemple : « POV: You\'re a Corrupt Prohibition Agent » + « mes mains gantées posent une liasse de billets sur un dossier TOP SECRET ».</div>';
  };
  const load = async () => {
    sets = await api('/api/thumbstudio');
    const s2 = JSON.stringify(sets);
    if (s2 !== sig) { sig = s2; render(); }
  };
  $('#sets', el).addEventListener('click', async (e) => {
    const more = e.target.closest('[data-more]');
    if (more) { await guard(() => api(`/api/thumbstudio/${more.dataset.more}/more`, { body: { count: 2 } }), '2 variantes en cours'); return load(); }
    const ds = e.target.closest('[data-delset]');
    if (ds) { if (confirm('Supprimer toute la série ?')) { await guard(() => api(`/api/thumbstudio/${ds.dataset.delset}`, { method: 'DELETE' })); load(); } return; }
    const card = e.target.closest('[data-it]'); const a = e.target.closest('[data-a]')?.dataset.a;
    if (!card) return;
    const s = sets.find((x) => x.id === card.dataset.set); const it = s && s.items.find((x) => x.id === card.dataset.it);
    if (!it) return;
    if (!a && it.file) return lightbox(tsm(it.file));
    const base = `/api/thumbstudio/${s.id}/items/${it.id}`;
    if (a === 'zoom') lightbox(tsm(it.file));
    if (a === 'edit') {
      const instruction = await askText('Retoucher la miniature', 'ex. texte plus gros et rouge, ajoute de la fumée, visage plus effrayé…');
      if (instruction) { await guard(() => api(`${base}/edit`, { body: { instruction } }), 'Retouche en cours'); load(); }
    }
    if (a === 'var') { await guard(() => api(`${base}/variations`, { body: { count: 2 } }), 'Variantes en cours'); load(); }
    if (a === 'del' && confirm('Supprimer cette miniature ?')) { await guard(() => api(base, { method: 'DELETE' })); load(); }
    if (a === 'proj') {
      const ps = await api('/api/projects?archived=0');
      if (!ps.length) return toast('Aucun projet', true);
      const m = modal(`<h2>Envoyer vers un projet</h2><select id="pp">${opts(ps.map((p) => [p.id, p.title]))}</select>
        <div class="row end" style="margin-top:12px"><button data-close>Annuler</button><button class="primary" id="ok">Définir comme miniature</button></div>`);
      $('#ok', m.el).onclick = async () => {
        const r = await guard(() => api(`${base}/to-project`, { body: { project_id: $('#pp', m.el).value } }), 'Miniature ajoutée au projet');
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
          <div class="field"><label>Fichier CSV</label><input type="file" id="csv" accept=".csv,text/csv,.txt"></div>
          <div class="field"><label>Style par défaut</label><select id="style">${opts(styles.map((s) => [s.id, s.name]))}</select></div>
          <div class="field"><label>Chaîne TikTok par défaut (lignes sans colonne <code>chaine</code>)</label><select id="chan"><option value="">— aucune (vidéos YouTube) —</option>${opts(chans.map((c) => [c.id, `${c.emoji} ${c.name}`]))}</select></div>
          <div class="field"><label>Mode</label><div class="seg" id="mode"><button data-v="auto" class="on">⚡ Auto — vidéos finies</button><button data-v="review">👀 Relecture — s'arrête aux prompts</button></div></div>
          <div class="row"><button class="primary" id="go">🚀 Lancer le batch</button><a class="btn" href="/exemple.csv">⬇ Modèle CSV</a><a class="btn" href="/exemple_tiktok.csv">⬇ Modèle TikTok</a></div>
        </div>
        <div class="small">
          <b>Format :</b> une ligne par vidéo, séparateur <code>,</code> ou <code>;</code> (Excel OK). Seule la colonne <code>title</code> est obligatoire.
          <pre>title;words;context;video_url;style
POV: You're a Viking Raider;3000;;https://youtu.be/…;pov-history
POV: You're a Medieval Plague Doctor;2500;focus on 1348;;</pre>
          Colonnes reconnues : <code>title/titre</code>, <code>words/mots</code>, <code>context/contexte</code>, <code>video_url/youtube</code>,
          <code>style</code>, <code>format</code> (16:9, 9:16 ou <code>short</code>), <code>voice_id</code>, <code>provider</code> (local, elevenlabs ou edge), <code>script</code> (ton propre texte),
          <code>langue</code>, <code>personnages</code>, <code>shorts</code> (nombre de shorts pub).<br>
          <b>TikTok :</b> <code>chaine</code> (ex. <code>tiktok-fr</code>) → la ligne devient un TikTok de cette chaîne, rangé dans son planning.
          <b>Clipping :</b> <code>source</code> = un lien YouTube ou le titre d'une vidéo TubeForge, <code>shorts</code> = combien de clips.
          <pre>title;chaine;source;shorts
POV : Tu es un gladiateur;tiktok-fr;;
;tiktok-en-clips;https://youtu.be/…;3</pre>
          Sans en-tête : 1 titre par ligne.<br><br>
          Les vidéos tournent en parallèle (réglage <code>PROJECT_PARALLEL</code>) et les images sont réparties sur les 36 comptes.
        </div>
      </div>
    </div>
    <h2 style="margin-top:24px">Batchs récents</h2><div id="list"></div>`;
  let mode = 'auto';
  $$('#mode button', el).forEach((b) => b.onclick = () => { mode = b.dataset.v; $$('#mode button', el).forEach((x) => x.classList.toggle('on', x === b)); });
  $('#go', el).onclick = async () => {
    const f = $('#csv', el).files[0];
    if (!f) return toast('Choisis un fichier CSV', true);
    const fd = new FormData(); fd.append('file', f); fd.append('mode', mode); fd.append('style_id', $('#style', el).value); fd.append('channel_id', $('#chan', el).value);
    const r = await guard(() => api('/api/batch', { form: fd, method: 'POST' }));
    if (r) { toast(`${r.projects.length} vidéos lancées${r.clips ? ` + ${r.clips} vidéo(s) à clipper (en cours d'écriture)` : ''}`); load(); }
  };
  const load = async () => {
    const bs = await api('/api/batches');
    $('#list', el).innerHTML = bs.map((b) => {
      const done = b.projects.filter((p) => p.render).length;
      return `<div class="card"><div class="row"><b>${esc(b.name)}</b><span class="muted small">${fmtDate(b.created)} · ${b.mode === 'auto' ? 'Auto' : 'Relecture'}</span>
        <span class="spacer"></span><span class="chip ${done === b.projects.length ? 'ok' : ''}">${done}/${b.projects.length} exports disponibles</span></div>
        <table class="list" style="margin-top:8px">${b.projects.map((p) => `<tr><td style="width:40%"><a href="#/p/${p.id}">${esc(p.title)}</a></td>
          <td>${featureBadge(p.features)}</td><td>${statusChip(p)}</td>
          <td style="text-align:right">${p.render ? `<a class="btn sm" href="/download/${p.id}">⬇ MP4</a>` : ''}</td></tr>`).join('')}</table></div>`;
    }).join('') || '<div class="muted">Aucun batch pour l\'instant.</div>';
  };
  await load();
  const t = setInterval(load, 4000);
  return () => clearInterval(t);
}

// ------------------------------------------------------------------ planning TikTok (chaînes)
const DAY_FMT = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
const dayLabel = (d) => { const s = DAY_FMT.format(new Date(`${d}T12:00:00`)); return s.charAt(0).toUpperCase() + s.slice(1); };
const STEP_LABELS = { script: 'Script', voiceover: 'Voix', visuals: 'Images', render: 'Rendu', resolve: 'Resolve', thumbnail: 'Miniatures' };
const PLAN_STATUS = { ready: ['ok', '✓ Prêt'], production: ['run', '⚙ En production'], error: ['err', '✗ Erreur'], posted: ['', '📤 Publié'] };

function channelForm(ch, styles, voices) {
  const v = ch.voice || {};
  return `
    <div class="grid2">
      <div class="field"><label>Nom</label><input type="text" data-c="name" value="${esc(ch.name)}" placeholder="ex. TikTok FR"></div>
      <div class="field"><label>Emoji</label><input type="text" data-c="emoji" value="${esc(ch.emoji || '📱')}" style="width:90px"></div>
      <div class="field"><label>Langue</label><select data-c="language">${opts(LANGUAGES, ch.language)}</select></div>
      <div class="field"><label>Style</label><select data-c="style_id">${opts(styles.map((s) => [s.id, s.name]), ch.style_id)}</select></div>
    </div>
    <div class="field"><label>Type de vidéos par défaut</label>
      <select data-c="kind">${opts([['standalone', '📱 TikTok autonome — histoire complète'], ['promo', '📣 Clipping / pub — teaser qui renvoie vers la vidéo YouTube']], ch.kind)}</select></div>
    <div class="grid2">
      <div class="field"><label>Voix</label><select data-c="voice.provider">${opts([['algrow', 'Algrow'], ['local', 'Locale'], ['edge', 'Edge'], ['elevenlabs', 'ElevenLabs']], v.provider || 'algrow')}</select></div>
      <div class="field"><label>Voix locale</label><select data-c="voice.local_voice"><option value="">Auto (selon la langue)</option>${opts(voices, v.local_voice || '')}</select></div>
      <div class="field"><label>Publications par jour</label><input type="number" min="1" max="6" data-c="posts_per_day" value="${ch.posts_per_day || 2}"></div>
      <div class="field"><label>Heures (séparées par des virgules)</label><input type="text" data-c="post_times" value="${esc((ch.post_times || []).join(', '))}" placeholder="12:30, 19:00"></div>
      <div class="field"><label>Premier jour du planning</label><input type="date" data-c="start_date" value="${esc(ch.start_date || '')}"></div>
      <div class="field"><label>@ du compte (optionnel)</label><input type="text" data-c="handle" value="${esc(ch.handle || '')}" placeholder="@moncompte"></div>
    </div>
    <div class="field"><label>Hashtags ajoutés à chaque légende</label><input type="text" data-c="hashtags" value="${esc((ch.hashtags || []).map((x) => `#${x}`).join(' '))}" placeholder="#histoire #pov"></div>
    <details style="margin:6px 0 12px"><summary class="small muted" style="cursor:pointer">Appel à l'action des shorts pub (vide = texte par défaut dans la langue)</summary>
      <div class="field" style="margin-top:8px"><label>Phrase dite à la fin</label><input type="text" data-c="cta.spoken" value="${esc((ch.cta || {}).spoken || '')}"></div>
      <div class="grid2"><div class="field"><label>Écran de fin — ligne 1</label><input type="text" data-c="cta.line1" value="${esc((ch.cta || {}).line1 || '')}"></div>
        <div class="field"><label>Ligne 2 (bandeau rouge)</label><input type="text" data-c="cta.line2" value="${esc((ch.cta || {}).line2 || '')}"></div></div>
      <div class="field"><label>Ligne 3</label><input type="text" data-c="cta.line3" value="${esc((ch.cta || {}).line3 || '')}"></div></details>
    <label class="check"><input type="checkbox" data-c="auto_resolve" ${ch.auto_resolve !== false ? 'checked' : ''}> 🎬 Monter chaque short fini dans DaVinci Resolve (projet « TubeForge - ${esc(ch.name || 'chaîne')} »)</label>`;
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
  const m = modal(`<h2>${isNew ? '+ Nouvelle chaîne' : `⚙ ${esc(ch.emoji)} ${esc(ch.name)}`}</h2>${channelForm(ch, styles, voices)}
    <div class="row" style="margin-top:14px">${isNew ? '' : '<button class="danger" id="del">Supprimer</button>'}<span class="spacer"></span>
      <button data-close>Annuler</button><button class="primary" id="ok">Enregistrer</button></div>`, { wide: true });
  $('#ok', m.el).onclick = async () => {
    const body = readChannelForm(m.el);
    if (!body.name) return toast('Donne un nom à la chaîne', true);
    const r = await guard(() => api(isNew ? '/api/channels' : `/api/channels/${ch.id}`, { method: isNew ? 'POST' : 'PUT', body }), 'Chaîne enregistrée');
    if (r) { m.close(); onSaved(r); }
  };
  if (!isNew) $('#del', m.el).onclick = async () => {
    if (!confirm(`Supprimer la chaîne « ${ch.name} » ? (les vidéos restent dans Projets)`)) return;
    if (await guard(() => api(`/api/channels/${ch.id}`, { method: 'DELETE' }), 'Chaîne supprimée')) { m.close(); onSaved(null); }
  };
}

async function clipModal(ch) {
  const ps = (await api('/api/projects?archived=0')).filter((p) => p.format !== 'short' && p.features.script);
  const m = modal(`<h2>✂ Clipper une vidéo pour ${esc(ch.emoji)} ${esc(ch.name)}</h2>
    <p class="muted small">L'IA lit toute la vidéo et écrit des shorts${ch.language ? ` en ${esc(ch.language)}` : ''} (traduits si besoin), chacun sur un angle différent. Ils se génèrent et se rangent tout seuls dans le planning.</p>
    <div class="field"><label>Lien YouTube (une vidéo déjà en ligne)</label><input type="url" id="url" placeholder="https://www.youtube.com/watch?v=…"></div>
    <div class="field"><label>… ou une vidéo TubeForge</label><select id="pid"><option value="">—</option>${opts(ps.map((p) => [p.id, p.title]))}</select></div>
    <div class="grid2"><div class="field"><label>Nombre de shorts</label><select id="n">${opts(['1', '2', '3', '4', '5'], '3')}</select></div>
      <div class="field"><label>Type</label><select id="kind">${opts([['promo', '📣 Pub → vidéo YouTube (cliffhanger + écran de fin)'], ['standalone', '📱 Autonome (histoire complète)']], ch.kind)}</select></div></div>
    <div class="row end"><button data-close>Annuler</button><button class="primary" id="go">✂ Lancer le clipping</button></div>`);
  $('#go', m.el).onclick = async () => {
    const body = { url: $('#url', m.el).value.trim(), project_id: $('#pid', m.el).value || null, count: +$('#n', m.el).value, kind: $('#kind', m.el).value };
    if (!body.url && !body.project_id) return toast('Colle un lien YouTube ou choisis une vidéo', true);
    if (await guard(() => api(`/api/channels/${ch.id}/clip`, { body }), 'Clipping lancé — les shorts arrivent dans le planning d\'ici ~1 min')) m.close();
  };
}

async function ideasModal(ch) {
  const m = modal(`<h2>💡 Idées de TikToks pour ${esc(ch.emoji)} ${esc(ch.name)}</h2>
    <p class="muted small">L'IA propose des sujets nouveaux (jamais déjà faits sur la chaîne). Tu modifies la liste, puis tu lances tout d'un coup.</p>
    <div class="grid2"><div class="field"><label>Combien ?</label><input type="number" id="n" value="30" min="1" max="60"></div>
      <div class="field"><label>Thème (optionnel)</label><input type="text" id="theme" placeholder="ex. Moyen Âge, mafia, guerres modernes…"></div></div>
    <div class="row end"><button class="primary" id="gen">💡 Proposer des idées</button></div>
    <div id="out" style="margin-top:12px"></div>`, { wide: true });
  $('#gen', m.el).onclick = async () => {
    const b = $('#gen', m.el); b.disabled = true; b.innerHTML = '<span class="spin"></span> L\'IA réfléchit…';
    const r = await guard(() => api(`/api/channels/${ch.id}/ideas`, { body: { count: +$('#n', m.el).value, theme: $('#theme', m.el).value } }));
    b.disabled = false; b.textContent = '💡 Proposer d\'autres idées';
    if (!r) return;
    $('#out', m.el).innerHTML = `<div class="field"><label>${r.ideas.length} idées — une ligne = un TikTok (tu peux modifier, supprimer, ajouter)</label>
      <textarea id="csv" style="min-height:320px;font-family:var(--mono, monospace);font-size:12px">${esc(r.csv)}</textarea></div>
      <div class="row"><button id="dl">⬇ Télécharger le .csv</button><span class="spacer"></span>
        <div class="seg" id="mode"><button data-v="auto" class="on">⚡ Auto</button><button data-v="review">👀 Relecture</button></div>
        <button class="primary" id="go">🚀 Lancer ces TikToks</button></div>`;
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
      fd.append('style_id', ch.style_id); fd.append('name', `Idées ${ch.name} — ${new Date().toLocaleDateString('fr-FR')}`);
      const res = await guard(() => api('/api/batch', { form: fd, method: 'POST' }));
      if (res) { toast(`${res.projects.length} TikToks lancés`); m.close(); }
    };
  };
}

function previewVideo(it) {
  modal(`<h2 style="margin-bottom:8px">${esc(it.title)}</h2>
    <video controls autoplay src="${media(it.id, it.video)}?t=${it.video_ts}" style="max-height:72vh;display:block;margin:0 auto;border-radius:10px"></video>
    <pre class="small" style="white-space:pre-wrap;margin-top:10px">${esc(it.caption)}</pre>
    <div class="row end"><button id="cp">📋 Copier la légende</button><a class="btn" href="/download/${it.id}">⬇ MP4</a><a class="btn" href="#/p/${it.id}">Ouvrir le projet</a><button data-close>Fermer</button></div>`);
  $('#cp').onclick = () => navigator.clipboard.writeText(it.caption).then(() => toast('Légende copiée'));
}

async function viewPlanning(el, cid) {
  let chans = await api('/api/channels');
  if (!chans.length) {
    el.innerHTML = `<h1>📅 Planning TikTok</h1><div class="card empty">Aucune chaîne. <button class="primary" id="new">+ Créer une chaîne</button></div>`;
    $('#new', el).onclick = () => editChannel({}, () => route());
    return null;
  }
  let ch = chans.find((c) => c.id === cid) || chans[0];
  el.innerHTML = `
    <div class="row" style="margin-bottom:14px"><h1 style="margin:0">📅 Planning TikTok</h1><span class="spacer"></span>
      <button id="tpl" title="Projet modèle Resolve : réglages 1080x1920, preset de rendu, ton pack d'assets">🎬 Modèle Resolve</button>
      <button id="newch">+ Chaîne</button></div>
    <div class="row" id="tabs" style="margin-bottom:14px;flex-wrap:wrap"></div>
    <div class="card" id="head"></div>
    <div id="list"></div>`;
  const tabs = () => {
    $('#tabs', el).innerHTML = chans.map((c) => `<a class="chip ${c.id === ch.id ? 'run' : ''}" style="font-size:14px;padding:7px 14px" href="#/planning/${c.id}">${esc(c.emoji)} ${esc(c.name)}
      <span class="muted small">${c.plan.ready} prêt${c.plan.ready > 1 ? 's' : ''}${c.plan.production ? ` · ${c.plan.production} en cours` : ''}</span></a>`).join('');
  };
  tabs();
  $('#newch', el).onclick = () => editChannel({ language: ch.language, style_id: ch.style_id, posts_per_day: 2, post_times: ['12:30', '19:00'], kind: 'standalone', auto_resolve: true },
    (r) => { if (r) location.hash = `#/planning/${r.id}`; });
  $('#tpl', el).onclick = async () => {
    const b = $('#tpl', el); b.disabled = true; b.innerHTML = '<span class="spin"></span> Resolve…';
    const r = await guard(() => api('/api/resolve/template', { body: {} }));
    b.disabled = false; b.textContent = '🎬 Modèle Resolve';
    if (r) modal(`<h2>🎬 Modèle DaVinci Resolve prêt</h2>
      <p>Projet <b>${esc(r.project)}</b> ${r.created ? 'créé' : 'mis à jour'} — preset de rendu <b>${esc(r.preset)}</b>${r.pack_added ? `, ${r.pack_added} fichier(s) de ton pack importés dans le chutier « Pack »` : ''}.</p>
      <p class="small muted">Chaque chaîne a son propre projet Resolve créé à partir de ce modèle, avec une timeline par short (rangées par date de publication).
      Tu peux retoucher le projet modèle dans Resolve (réglages, LUT, chutiers…) puis recliquer ici : les prochains projets de chaîne reprendront tes changements.
      Dépose ton pack dans <code>assets/pack/</code> (images, logos) et <code>assets/sfx/pack/</code> (sons).</p>
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
        <span class="spacer"></span><button class="sm" id="edit">⚙ Réglages</button></div>
      <div class="row" style="margin:12px 0;gap:8px;flex-wrap:wrap">
        <span class="chip ok">✓ ${s.ready} prêt${s.ready > 1 ? 's' : ''}</span>
        ${s.production ? `<span class="chip run">⚙ ${s.production} en production</span>` : ''}
        ${s.errors ? `<span class="chip err">✗ ${s.errors} en erreur</span>` : ''}
        ${s.posted ? `<span class="chip">📤 ${s.posted} publié${s.posted > 1 ? 's' : ''}</span>` : ''}
        ${s.late ? `<span class="chip warn">⚠ ${s.late} créneau(x) dépassé(s)</span>` : ''}
        <span class="small muted">${s.covered_until ? `Vidéos prêtes jusqu'au <b>${dayLabel(s.covered_until.slice(0, 10))}</b> (${days} jour${days > 1 ? 's' : ''} d'avance)` : 'Aucune vidéo prête pour l\'instant'}</span></div>
      <div class="row" style="flex-wrap:wrap;gap:8px">
        <button class="primary" id="ideas">💡 Idées → batch</button>
        <button id="clip">✂ Clipper une vidéo</button>
        <button id="resolve">🎬 Monter les prêts dans Resolve</button>
        <button id="export">📦 Exporter les exports disponibles</button>
        <button id="open">📂 Ouvrir le dossier</button>
        <button id="reset" title="Recalcule tous les créneaux à partir du premier jour (sauf les vidéos déjà publiées)">↻ Replanifier</button></div>`;
    $('#edit', el).onclick = () => editChannel(ch, (r) => { if (!r) location.hash = '#/planning'; else { lastKey = ''; refreshAll(); } });
    $('#ideas', el).onclick = () => ideasModal(ch);
    $('#clip', el).onclick = () => clipModal(ch);
    $('#resolve', el).onclick = async () => { const r = await guard(() => api(`/api/channels/${ch.id}/resolve-all`, { body: {} })); if (r) toast(r.started ? `${r.started} short(s) envoyés à Resolve (un par un)` : 'Tout est déjà monté dans Resolve'); };
    $('#export', el).onclick = async () => {
      const b = $('#export', el); b.disabled = true; b.innerHTML = '<span class="spin"></span> Export…';
      const r = await guard(() => api(`/api/channels/${ch.id}/export`, { body: {} }));
      b.disabled = false; b.textContent = '📦 Exporter les exports disponibles';
      if (r) toast(`${r.count} publication(s) prêtes dans ${r.dir}`);
      lastKey = ''; load();
    };
    $('#open', el).onclick = () => guard(() => api(`/api/channels/${ch.id}/open`, { body: {} }));
    $('#reset', el).onclick = async () => {
      if (!confirm('Recalculer tous les créneaux (ordre de création) ? Les vidéos déjà publiées ne bougent pas.')) return;
      await guard(() => api(`/api/channels/${ch.id}/assign`, { body: { reset: true } }), 'Planning recalculé'); lastKey = ''; load();
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
            ${it.resolve ? '<span class="chip" title="Monté et rendu dans DaVinci Resolve">🎬 Resolve</span>' : ''}${it.exported ? '<span class="chip" title="Copié dans le dossier d\'export">📦</span>' : ''}
            ${it.error ? `<span class="small" style="color:var(--err)">${esc(it.error.slice(0, 120))}</span>` : ''}</span></span>
        <span class="row" style="gap:4px">
          ${it.status === 'ready' ? '<button class="sm" data-a="copy" title="Copier la légende + hashtags">📋</button>' : ''}
          ${it.status !== 'posted' ? '<button class="sm" data-a="up" title="Plus tôt">↑</button><button class="sm" data-a="down" title="Plus tard">↓</button>' : ''}
          ${it.status === 'ready' ? '<button class="sm" data-a="posted" title="Marquer comme publié">✓ Publié</button>' : ''}
          ${it.status === 'posted' ? '<button class="sm" data-a="unposted">↺</button>' : ''}</span></div>`;
    };
    $('#list', el).innerHTML = (Object.keys(groups).sort().map((k) => `<h3 style="margin:22px 0 8px">${k === 'zz' ? 'Sans créneau' : dayLabel(k)}</h3>
      <div class="card" style="padding:4px 14px">${groups[k].map(row).join('')}</div>`).join('')
      || `<div class="card empty" style="margin-top:16px">Rien de prévu. Clique sur <b>💡 Idées → batch</b> pour préparer 30 TikToks d'un coup, ou <b>✂ Clipper une vidéo</b>.</div>`)
      + (posted.length ? `<details style="margin-top:22px"><summary class="muted" style="cursor:pointer">📤 Déjà publiés (${posted.length})</summary>
        <div class="card" style="padding:4px 14px;margin-top:8px">${posted.slice().reverse().map(row).join('')}</div></details>` : '');
    const byId = Object.fromEntries(d.items.map((i) => [i.id, i]));
    $$('.planrow [data-a]', el).forEach((b) => b.onclick = async (e) => {
      e.preventDefault();
      const it = byId[b.closest('.planrow').dataset.id];
      const a = b.dataset.a;
      if (a === 'play') { if (it.video) previewVideo(it); return; }
      if (a === 'copy') { await navigator.clipboard.writeText(it.caption); toast('Légende copiée'); return; }
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
const ACCENT_FLAGS = { FR: '🇫🇷', 'Québec': '🇨🇦', CA: '🇨🇦', Belgique: '🇧🇪', BE: '🇧🇪', CH: '🇨🇭', US: '🇺🇸', UK: '🇬🇧', GB: '🇬🇧', Australie: '🇦🇺', AU: '🇦🇺', Irlande: '🇮🇪', IE: '🇮🇪', EN: '🇺🇸' };
const VOICE_GROUPS = [['all', 'Toutes'], ['fr', '🇫🇷 Français'], ['US', '🇺🇸 Anglais US'], ['UK', '🇬🇧 Anglais UK'], ['other', '🌍 Autres accents']];

async function viewVoices(el) {
  let filter = 'all';
  const player = new Audio();
  let playing = null;
  const [styles, chans] = await Promise.all([api('/api/styles'), api('/api/channels').catch(() => [])]);
  const targets = [...styles.map((s) => [`style:${s.id}`, `🎨 Style « ${s.name} »`]), ...chans.map((c) => [`chan:${c.id}`, `${c.emoji} Chaîne « ${c.name} »`])];
  el.innerHTML = `
    <div class="row" style="margin-bottom:6px"><h1 style="margin:0">🎙️ Voix</h1><span class="spacer"></span>
      <label class="btn">+ Ajouter ma voix<input type="file" id="up" accept="audio/*" hidden></label>
      <button id="gen">🎧 Générer les échantillons</button></div>
    <div class="small muted" style="margin-bottom:14px">Toutes ces voix tournent en local sur ta carte (Chatterbox), gratuites et illimitées. Chaque échantillon dit la même phrase, générée par le vrai moteur des vidéos :<br>
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
    $('#sampling', el).innerHTML = s.running ? `<div class="banner">⚙ Génération des échantillons : ${s.done}/${s.total}…<div class="bar" style="margin-top:6px"><div style="width:${s.total ? Math.round(100 * s.done / s.total) : 0}%"></div></div></div>`
      : missing ? `<div class="banner">${missing} voix sans échantillon — clique sur « 🎧 Générer les échantillons » (~10 s par voix).</div>` : '';
    $('#gen', el).disabled = s.running;
    const rank = (v) => (v.lang === 'fr' ? 0 : v.accent === 'US' ? 1 : v.accent === 'UK' ? 2 : 3) * 10 + (v.default ? 0 : 1);
    $('#grid', el).innerHTML = data.voices.filter(inGroup).sort((a, b) => rank(a) - rank(b)).map((v) => `
      <div class="card voicecard ${playing === v.id ? 'playing' : ''}" data-id="${esc(v.id)}">
        <div class="row" style="gap:10px">
          <button class="playbtn" data-a="play" ${v.sample ? '' : 'disabled'} title="${v.sample ? 'Écouter' : 'Pas encore d\'échantillon'}">${playing === v.id ? '❚❚' : '▶'}</button>
          <div style="flex:1;min-width:0"><b>${ACCENT_FLAGS[v.accent] || '🎙️'} ${esc(v.label)}</b> <span class="muted small">${v.gender === 'f' ? '♀' : v.gender === 'm' ? '♂' : ''}</span>
            <div class="small muted">${v.default ? '<b style="color:var(--ok)" title="Utilisée quand la voix est sur « Auto »">⭐ par défaut</b> · ' : ''}${esc(v.accent)}${v.desc ? ` · ${esc(v.desc)}` : ''}</div></div></div>
        <div class="row" style="margin-top:10px;gap:6px"><select data-a="use" style="flex:1"><option value="">Utiliser pour…</option>${opts(targets)}</select></div>
      </div>`).join('') || '<div class="muted">Aucune voix dans cette catégorie.</div>';
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
      if (ok) toast(`Voix « ${data.voices.find((x) => x.id === id).label} » choisie pour ${sel.options[sel.selectedIndex].text} (prochaines vidéos)`);
      sel.value = '';
    });
  };
  player.onended = () => { playing = null; draw(); };
  const load = async () => { data = await api('/api/voices/gallery'); draw(); };
  $('#gen', el).onclick = async () => { await guard(() => api('/api/voices/gallery/samples', { body: {} }), 'Génération des échantillons lancée'); load(); };
  $('#up', el).onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const name = await askText('Nom de cette voix', 'ex. Ma voix FR', f.name.replace(/\.[^.]+$/, ''));
    if (!name) return;
    const fd = new FormData(); fd.append('name', name); fd.append('file', f);
    if (await guard(() => api('/api/local-tts/voices', { form: fd, method: 'POST' }), 'Voix ajoutée — génère son échantillon pour l\'écouter')) load();
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
      <span class="thumb" style="${s.visuals.style_refs[0] ? `background-image:url('/style-media/${s.id}/${s.visuals.style_refs[0]}')` : ''}"></span>
      <div class="body"><b class="title">${esc(s.name)}</b><div class="small muted">${esc(s.language)} · ${s.script.word_count} mots · ${s.script.references.length} script(s) de réf. · ${s.characters.length} perso(s)</div></div></a>`).join('')}</div>`;
  $('#new', el).onclick = async () => {
    const name = await askText('Nom du nouveau style', 'ex. POV History FR');
    if (!name) return;
    const base = styles[0] && confirm(`Partir d'une copie de « ${styles[0].name} » ? (Annuler = style vierge)`) ? styles[0].id : null;
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
      <span class="muted small">Enregistrement automatique</span><button class="danger" id="del">Supprimer</button></div>
    <div class="grid2" style="grid-template-columns:repeat(auto-fit,minmax(420px,1fr));align-items:start">
      <div>
        <div class="card"><h2>Général</h2>
          <div class="field"><label>Nom</label><input type="text" data-k="name" value="${esc(s.name)}"></div>
          <div class="field"><label>Langue des vidéos</label><input type="text" data-k="language" value="${esc(s.language)}" placeholder="English, French…"></div></div>
        <div class="card"><h2>Écriture du script</h2>
          <div class="grid2"><div class="field"><label>Longueur (mots)</label><input type="number" step="100" data-k="script.word_count" value="${s.script.word_count}"></div>
            <div class="field"><label>Mode</label><select data-k="script.mode">${opts([['pro', 'Pro'], ['fast', 'Rapide']], s.script.mode)}</select></div></div>
          <div class="field"><label>Instructions de la chaîne</label><textarea data-k="script.instructions" style="min-height:180px">${esc(s.script.instructions)}</textarea></div>
          <label>Scripts de référence (le ton à imiter)</label>
          ${s.script.references.map((r, i) => `<div class="row card inner" style="padding:8px 12px;margin-bottom:6px"><span>${esc(r.title)}</span><span class="muted small">${words(r.text)} mots</span><span class="spacer"></span><button class="sm danger" data-delref="${i}">✕</button></div>`).join('') || '<div class="muted small">Aucun.</div>'}
          <div class="row" style="margin-top:8px"><input type="url" id="refurl" placeholder="URL YouTube d'une vidéo de la chaîne" style="flex:1"><button class="sm" id="addyt">+ Depuis YouTube</button><button class="sm" id="addtxt">+ Coller un texte</button></div>
        </div>
        <div class="card"><h2>Voix</h2><div id="voice">${voiceFieldsHtml(s.voice, 'voice', voices, local)}</div></div>
      </div>
      <div>
        <div class="card"><h2>Visuels</h2>
          <div class="field"><label>Art style (ajouté à chaque prompt d'image)</label><textarea data-k="visuals.art_style" style="min-height:150px">${esc(v.art_style)}</textarea></div>
          <label>Images de référence du style</label>
          <div class="refs">${v.style_refs.map((r) => `<div class="r"><img src="/style-media/${sid}/${r}"><button class="sm danger" data-delimg="${esc(r.split('/').pop())}">✕</button></div>`).join('')}</div>
          <div class="row" style="margin:8px 0 14px"><label class="btn sm">⬆ Ajouter une image<input type="file" accept="image/*" hidden id="addimg"></label>
            <label class="check"><input type="checkbox" data-k="visuals.use_style_refs" ${v.use_style_refs ? 'checked' : ''}> Utiliser la 1re image comme référence de style</label></div>
          <div class="grid2">
            <div class="field"><label>Modèle d'image</label><select data-k="visuals.image_model">${opts(IMAGE_MODELS, v.image_model)}</select></div>
            <div class="field"><label>Format</label><select data-k="visuals.aspect">${opts(['16:9', '9:16'], v.aspect)}</select></div>
            <div class="field" style="grid-column:1/-1"><label>Durée moyenne d'une image : <b style="color:var(--accent)"><span data-out="savg">${(+v.avg_scene_seconds).toFixed(1)}</span> s</b></label>
              <input type="range" min="1" max="10" step="0.1" data-k="visuals.avg_scene_seconds" data-live="savg" value="${v.avg_scene_seconds}" style="width:100%">
              <div class="row small muted" style="justify-content:space-between"><span>1 s</span><span>10 s</span></div></div>
            <div class="field"><label>Min / max (s)</label><div class="row"><input type="number" step="0.1" data-k="visuals.min_scene_seconds" value="${v.min_scene_seconds}" style="width:45%"><input type="number" step="0.1" data-k="visuals.max_scene_seconds" value="${v.max_scene_seconds}" style="width:45%"></div></div>
            <div class="field"><label>Intensité du mouvement : <span data-out="smot">${(+v.motion_strength).toFixed(1)}</span></label><input type="range" step="0.1" min="0" max="2" data-k="visuals.motion_strength" data-live="smot" value="${v.motion_strength}" style="width:100%"></div>
          </div>
          <label class="check"><input type="checkbox" data-k="visuals.auto_characters" ${v.auto_characters ? 'checked' : ''}> Détecter les personnages récurrents automatiquement</label>
          <label class="check"><input type="checkbox" data-k="visuals.use_character_refs" ${v.use_character_refs ? 'checked' : ''}> Garder les personnages cohérents (fiches de référence)</label>
          <label class="check"><input type="checkbox" data-k="visuals.captions" ${v.captions ? 'checked' : ''}> Sous-titres incrustés dans la vidéo</label>
          <div class="field" style="margin-top:10px"><label>Continuité entre images</label><select data-k="visuals.continuity">${opts([['smart', '⛓ Intelligente — scènes liées dessinées à partir de la précédente'], ['always', 'Totale — chaque image part de la précédente (lent)'], ['off', 'Aucune — toutes en parallèle (rapide)']], v.continuity || 'smart')}</select></div>
        </div>
        <div class="card"><h2>Personnages permanents</h2><div class="muted small" style="margin-bottom:8px">Copiés dans chaque nouveau projet de ce style.</div>
          <div class="chars">${s.characters.map((c, i) => `<div class="card inner char"><div class="cimg" style="${c.image ? `background-image:url('/style-media/${sid}/${c.image}')` : ''}">${c.image ? '' : 'Pas de référence'}</div>
            <b>${esc(c.name)}</b><div class="small muted">${esc(c.description)}</div>
            ${c.signature ? `<div class="small" style="margin-top:4px">🔖 ${esc(c.signature)}</div>` : ''}
            <label class="check small"><input type="checkbox" data-chopt="${i}" data-o="auto_include" ${c.auto_include ? 'checked' : ''}> Coché par défaut dans les nouvelles vidéos</label>
            <label class="check small"><input type="checkbox" data-chopt="${i}" data-o="in_script" ${c.in_script ? 'checked' : ''}> Joue un rôle dans le script</label>
            <label class="check small"><input type="checkbox" data-chopt="${i}" data-o="outfit_varies" ${c.outfit_varies ? 'checked' : ''}> Tenue selon l'époque de la vidéo</label>
            <label class="check small"><input type="checkbox" data-chev="${i}" ${c.every_image ? 'checked' : ''}> Dans toutes les images</label>
            <div class="row"><button class="sm" data-chimg="${esc(c.id)}">✨ Référence</button><span class="spacer"></span><button class="sm danger" data-chdel="${i}">✕</button></div></div>`).join('')}</div>
          <button class="sm" id="addchar" style="margin-top:8px">+ Ajouter un personnage</button></div>
        <div class="card"><h2>📣 Shorts pub TikTok</h2>
          <div class="field"><label>Shorts pub créés automatiquement après chaque vidéo longue</label><select data-k="shorts.promo_count">${opts([['0', 'Aucun'], ['1', '1'], ['2', '2'], ['3', '3']], String((s.shorts || {}).promo_count || 0))}</select></div>
          <div class="small muted" style="margin-bottom:8px">Textes de l'appel à l'action (laisse vide = texte par défaut dans la langue de la vidéo : « L'histoire complète est sur ma chaîne YouTube », « VIDÉO COMPLÈTE / SUR YOUTUBE / lien en bio »).</div>
          <div class="field"><label>Phrase dite à la fin</label><input type="text" data-k="shorts.cta_spoken" value="${esc((s.shorts || {}).cta_spoken || '')}"></div>
          <div class="grid2"><div class="field"><label>Écran de fin — ligne 1</label><input type="text" data-k="shorts.cta_line1" value="${esc((s.shorts || {}).cta_line1 || '')}"></div>
            <div class="field"><label>Ligne 2 (bandeau rouge)</label><input type="text" data-k="shorts.cta_line2" value="${esc((s.shorts || {}).cta_line2 || '')}"></div></div>
          <div class="field"><label>Ligne 3</label><input type="text" data-k="shorts.cta_line3" value="${esc((s.shorts || {}).cta_line3 || '')}"></div></div>
        <div class="card"><h2>Miniatures</h2>
          <div class="grid2"><div class="field"><label>Nombre par vidéo (auto)</label><input type="number" min="0" max="6" data-k="thumbnail.count" value="${s.thumbnail.count}"></div>
            <div class="field"><label>Modèle</label><select data-k="thumbnail.model">${opts(IMAGE_MODELS, s.thumbnail.model)}</select></div></div>
          <div class="field"><label>Style des miniatures</label><textarea data-k="thumbnail.style" style="min-height:120px">${esc(s.thumbnail.style)}</textarea></div></div>
      </div>
    </div>`;
    wireVoiceFields($('#voice', el), () => s.voice, () => s.language);
    bindFields(el, async (obj, inp) => {
      if (inp.id === 'vsel') setPath(obj, 'voice.voice_name', inp.options[inp.selectedIndex].text.split(' — ')[0]);
      await put(obj);
    });
    $('#del', el).onclick = async () => { if (confirm('Supprimer ce style ?') && await guard(() => api(`/api/styles/${sid}`, { method: 'DELETE' }))) location.hash = '#/styles'; };
    $$('[data-delref]', el).forEach((b) => b.onclick = async () => { const refs = s.script.references.filter((_, i) => i !== +b.dataset.delref); s.script.references = refs; await put({ script: { references: refs } }); render(); });
    $('#addyt', el).onclick = async () => {
      const url = $('#refurl', el).value.trim(); if (!url) return;
      $('#addyt', el).disabled = true;
      const ns = await guard(() => api(`/api/styles/${sid}/references/youtube`, { body: { url } }), 'Transcription ajoutée');
      if (ns) { s = ns; render(); } else $('#addyt', el).disabled = false;
    };
    $('#addtxt', el).onclick = async () => {
      const text = await askText('Colle un script de référence'); if (!text) return;
      const title = (await askText('Titre de ce script')) || 'Référence';
      s.script.references.push({ title, text }); await put({ script: { references: s.script.references } }); render();
    };
    $('#addimg', el).onchange = async (e) => {
      const fd = new FormData(); fd.append('file', e.target.files[0]);
      const ns = await guard(() => api(`/api/styles/${sid}/refs`, { form: fd, method: 'POST' }), 'Image ajoutée'); if (ns) { s = ns; render(); }
    };
    $$('[data-delimg]', el).forEach((b) => b.onclick = async () => { const ns = await guard(() => api(`/api/styles/${sid}/refs/${b.dataset.delimg}`, { method: 'DELETE' })); if (ns) { s = ns; render(); } });
    $$('[data-chdel]', el).forEach((b) => b.onclick = async () => { const cs = s.characters.filter((_, i) => i !== +b.dataset.chdel); await put({ characters: cs }); render(); });
    $$('[data-chev]', el).forEach((b) => b.onchange = async () => { s.characters[+b.dataset.chev].every_image = b.checked; await put({ characters: s.characters }); });
    $$('[data-chopt]', el).forEach((b) => b.onchange = async () => { s.characters[+b.dataset.chopt][b.dataset.o] = b.checked; await put({ characters: s.characters }); });
    $$('[data-chimg]', el).forEach((b) => b.onclick = async () => {
      b.disabled = true; b.innerHTML = '<span class="spin"></span>';
      const ns = await guard(() => api(`/api/styles/${sid}/characters/${b.dataset.chimg}/image`, { body: {} }), 'Référence créée'); if (ns) { s = ns; render(); }
    });
    $('#addchar', el).onclick = async () => {
      const name = await askText('Nom du personnage'); if (!name) return;
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
    ['ELEVENLABS_API_KEY', 'Clé API ElevenLabs', 'password', 'Voix off. Trouvable sur elevenlabs.io → Profile → API keys.'],
    ['LOCAL_TTS_VRAM_GB', 'Mémoire graphique max pour la voix locale (Go)', 'number', 'Chatterbox utilise ~3-5 Go ; plafond de sécurité.'],
    ['PROXY_BASE_URL', 'URL du proxy (36 comptes)', 'text', ''],
    ['PROXY_API_KEY', 'Clé du proxy', 'password', ''],
    ['SCRIPT_MODEL', 'Modèle pour les scripts', 'text', 'ID configuré dans le proxy'],
    ['FAST_MODEL', 'Modèle rapide (prompts, titres…)', 'text', 'ID configuré dans le proxy'],
    ['IMAGE_CONCURRENCY', 'Images en parallèle', 'number', '36 = une requête par compte'],
    ['LLM_CONCURRENCY', 'Requêtes texte en parallèle', 'number', ''],
    ['PROJECT_PARALLEL', 'Vidéos traitées en même temps (batch)', 'number', ''],
    ['TTS_CONCURRENCY', 'Requêtes voix en parallèle', 'number', 'selon ton forfait ElevenLabs (2 à 15)'],
    ['RENDER_WORKERS', 'Processus de rendu par vidéo', 'number', 'cœurs CPU utilisés pour le rendu'],
    ['RENDER_CONCURRENCY', 'Rendus simultanés', 'number', ''],
  ];
  el.innerHTML = `<h1>Réglages</h1><div class="card" style="max-width:760px">
    ${F.map(([k, l, t, help]) => `<div class="field"><label>${l}</label><input type="${t}" data-key="${k}" value="${t === 'password' ? '' : esc(cfg[k])}" placeholder="${t === 'password' ? esc(cfg[k] || 'non définie') : ''}">
      ${help ? `<div class="small muted">${esc(help)}</div>` : ''}</div>`).join('')}
    <div class="row"><button class="primary" id="save">Enregistrer</button><button id="test11">Tester ElevenLabs</button><span class="spacer"></span>
      <span class="small muted">Les clés sont stockées dans le fichier <code>.env</code> du dossier.</span></div></div>`;
  $('#save', el).onclick = async () => {
    const body = {};
    $$('[data-key]', el).forEach((i) => { if (i.type !== 'password' || i.value.trim()) if (i.type === 'password' || i.value !== String(cfg[i.dataset.key])) body[i.dataset.key] = i.value.trim(); });
    if (!Object.keys(body).length) return toast('Rien à enregistrer');
    if (await guard(() => api('/api/settings', { method: 'PUT', body }), 'Réglages enregistrés')) { elevenVoicesCache = null; await pollStats(); route(); }
  };
  $('#test11', el).onclick = async () => {
    const r = await guard(() => api('/api/elevenlabs/voices'));
    if (r) toast(r.length ? `ElevenLabs OK — ${r.length} voix disponibles` : 'Aucune clé ElevenLabs configurée', !r.length);
  };
}

// ------------------------------------------------------------------ démarrage
pollStats().then(route);
