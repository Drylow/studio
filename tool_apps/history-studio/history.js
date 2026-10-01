// ============================================================================
// History Docs — titre + durée → documentaire d'histoire monté (format à part des POV).
// Tout tourne côté serveur (/api/history/*) : on peut fermer l'onglet pendant une vidéo.
// ============================================================================
'use strict';

const $ = (sel, root = document) => root.querySelector(sel);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const fmtDur = sec => { if (sec == null || isNaN(sec)) return '–'; sec = Math.round(sec); return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`; };
const nf = n => Math.round(n).toLocaleString('fr-FR');
const ago = iso => {
  if (!iso) return ''; const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 60) return 'à l\'instant'; if (d < 3600) return `il y a ${Math.floor(d / 60)} min`;
  if (d < 86400) return `il y a ${Math.floor(d / 3600)} h`; return new Date(iso).toLocaleDateString('fr-FR');
};

async function api(method, path, body) {
  const opt = {method, headers: {Accept: 'application/json'}};
  if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers['Content-Type'] = 'application/json'; }
  let r;
  try { r = await fetch('/api/history' + path, opt); } catch (e) { throw new Error('Serveur injoignable — le studio tourne-t-il ?'); }
  if (r.status === 401) throw new Error('Session verrouillée — recharge la page et reconnecte-toi.');
  const data = (r.headers.get('Content-Type') || '').includes('json') ? await r.json() : null;
  if (!r.ok) throw new Error((data && data.error) || `Erreur ${r.status}`);
  return data;
}
const fileUrl = (pid, rel, dl) => `/api/history/projects/${pid}/files/${rel}${dl ? '?dl=1' : ''}`;
function toast(msg, kind = '') {
  const el = document.createElement('div'); el.className = 'toast ' + kind; el.textContent = msg;
  $('#toasts').appendChild(el); setTimeout(() => el.remove(), kind === 'err' ? 7000 : 3500);
}
async function guard(fn, okMsg) {
  try { const r = await fn(); if (okMsg) toast(okMsg, 'ok'); return r; } catch (e) { toast(e.message || String(e), 'err'); return null; }
}
function busy(btn, on, label) {
  if (!btn) return;
  if (on) { btn.dataset.label = btn.innerHTML; btn.disabled = true; btn.innerHTML = `<span class="spin"></span>${label || ''}`; }
  else { btn.disabled = false; if (btn.dataset.label) btn.innerHTML = btn.dataset.label; }
}
function lightbox(src) { $('#lightboxImg').src = src; $('#lightbox').classList.add('on'); }
$('#lightbox').onclick = () => $('#lightbox').classList.remove('on');
document.addEventListener('keydown', e => { if (e.key === 'Escape') { $('#lightbox').classList.remove('on'); closeModal(); } });

const S = {cfg: null, projects: [], pollT: null, playing: new Set(), open: null};
const STEP = {script: 'Script', voice: 'Voix off', plan: 'Plan visuel', images: 'Images', render: 'Montage', done: 'Terminée'};
const TYPE = {image: ['🖼', 'Image'], statement: ['❝', 'Phrase choc'], number: ['🔢', 'Grand chiffre'], battle: ['⚔', 'Bataille'],
  character: ['👤', 'Fiche perso'], compare: ['⚖', 'Duo (2 portraits)'], map: ['🗺', 'Carte (mouvements A → B)'], chart: ['📊', 'Graphique'], archive: ['🏺', 'Archive'], route: ['🧭', 'Itinéraire'], quote: ['✒', 'Citation']};

// ── Formulaire ─────────────────────────────────────────────────────────────
const CHIPS = [3, 5, 10, 15, 25, 35];
function renderChips() {
  const v = Number($('#minutes').value);
  $('#chips').innerHTML = CHIPS.map(m => `<span class="chip ${m === v ? 'on' : ''}" data-m="${m}">${m} min</span>`).join('');
}
$('#chips').onclick = e => { const c = e.target.closest('.chip'); if (!c) return; $('#minutes').value = c.dataset.m; onMinutes(); };
function onMinutes() {
  const m = Number($('#minutes').value), wpm = (S.cfg && S.cfg.wpm) || 153;
  $('#minOut').textContent = `${m} min`;
  renderChips();
  const words = m * wpm, secs = m * 60;
  const cards = Math.max(2, Math.round(m * 1.5)), imgs = Math.ceil(5 + (secs - cards * 9) / 16);
  const algrow = String($('#voice').value || '').startsWith('algrow');
  $('#est').innerHTML = `<span>≈ <b>${nf(words)}</b> mots</span><span>≈ <b>${nf(imgs)}</b> images IA</span><span>≈ <b>${nf(cards)}</b> animations</span>`
    + (algrow ? `<span>≈ <b>${nf(words * 5.9)}</b> caractères Algrow</span>` : '')
    + `<span>≈ <b>${nf(4 + m * 2.2)} min</b> de fabrication</span>`;
}
$('#minutes').oninput = onMinutes;
$('#voice').onchange = onMinutes;

$('#create').onclick = async e => {
  const title = $('#title').value.trim();
  if (title.length < 4) { toast('Écris le titre de la vidéo.', 'err'); $('#title').focus(); return; }
  const [provider, voice] = ($('#voice').value || 'algrow|').split('|');
  busy(e.currentTarget, true, 'Lancement…');
  const r = await guard(() => api('POST', '/projects', {
    title, minutes: Number($('#minutes').value), notes: $('#notes').value.trim(), voice: {provider, voice},
    options: {captions: $('#captions').checked, captions_after_hook: $('#afterHook').checked,
      film: Number($('#film').value), image_style: $('#style').value, templates: [...document.querySelectorAll('#tpls input:checked')].map(i => i.value)},
  }));
  busy($('#create'), false);
  if (r) { $('#title').value = ''; $('#notes').value = ''; toast('C\'est parti : la vidéo se fabrique.', 'ok'); await load(); }
};
$('#title').addEventListener('keydown', e => { if (e.key === 'Enter') $('#create').click(); });

// ── Liste ──────────────────────────────────────────────────────────────────
function statusOf(p) {
  const j = p.job;
  if (j && j.status === 'running') return {k: 'run', label: 'En fabrication', cls: 'acc'};
  if (p.render) return {k: 'done', label: 'Vidéo prête', cls: 'ok'};
  if (j && j.status === 'error') return {k: 'err', label: 'Erreur', cls: 'err'};
  if (j && j.status === 'cancelled') return {k: 'stop', label: 'Arrêtée', cls: 'warn'};
  return {k: 'idle', label: `Étape : ${STEP[p.stage] || p.stage}`, cls: ''};
}

function card(p) {
  const st = statusOf(p), j = p.job || {}, pct = Math.round((j.progress || 0) * 100);
  const media = S.playing.has(p.id) && p.render
    ? `<video src="${fileUrl(p.id, p.render.file)}" controls autoplay preload="metadata"></video>`
    : `🏛${p.render ? '<button class="play" data-act="play" title="Regarder">▶</button>' : ''}`;
  const meta = [
    `<span class="pill ${st.cls}">${st.k === 'run' ? '<span class="spin" style="width:10px;height:10px"></span>' : ''}${esc(st.label)}</span>`,
    `<span>${esc(p.minutes)} min visées</span>`,
    p.render ? `<span>durée ${fmtDur(p.render.duration)}</span>` : (p.duration ? `<span>voix ${fmtDur(p.duration)}</span>` : ''),
    p.segments ? `<span>${p.segments} plans · ${p.cards} animations</span>` : '',
    `<span class="faint">${esc(ago(p.created))}</span>`,
  ].filter(Boolean).join('');
  const prog = st.k === 'run' ? `<div class="prog"><i style="width:${pct}%"></i></div><div class="pmsg">${pct}% · ${esc(j.message || '')}</div>` : '';
  const err = st.k === 'err' ? `<div class="perr">${esc(j.error || j.message || 'Erreur')}</div>` : '';
  const acts = [];
  if (p.render) acts.push(`<a class="btn sm primary" href="${fileUrl(p.id, p.render.file, true)}">⬇ Télécharger</a>`);
  if (st.k === 'run') acts.push(`<button class="btn sm ghost" data-act="cancel">■ Arrêter</button>`);
  else if (!p.render) acts.push(`<button class="btn sm ok" data-act="resume">↻ Reprendre</button>`);
  acts.push(`<button class="btn sm" data-act="open">🗂 Script & plan</button>`);
  acts.push(`<button class="btn sm ghost" data-act="delete" title="Supprimer la vidéo et tous ses fichiers">🗑</button>`);
  return `<article class="vcard" data-id="${p.id}">
    <div class="vthumb">${media}</div>
    <div class="vbody"><div class="vtitle">${esc(p.title)}</div><div class="vmeta">${meta}</div>${prog}${err}
      <div class="vactions">${acts.join('')}</div></div></article>`;
}

async function load() {
  clearTimeout(S.pollT);
  const r = await guard(() => api('GET', '/projects'));
  if (r) {
    S.projects = r.projects;
    $('#list').innerHTML = S.projects.length ? S.projects.map(card).join('') : '<div class="card faint">Aucune vidéo pour l\'instant.</div>';
    $('#count').textContent = S.projects.length ? `${S.projects.length} vidéo(s)` : '';
    if (S.open) refreshModal();
  }
  const running = S.projects.some(p => p.job && p.job.status === 'running');
  S.pollT = setTimeout(load, running ? 3000 : 20000);
}

$('#list').onclick = async e => {
  const b = e.target.closest('[data-act]'); if (!b) return;
  const id = b.closest('.vcard').dataset.id, act = b.dataset.act;
  if (act === 'play') { S.playing.add(id); load(); return; }
  if (act === 'open') { S.open = id; refreshModal(); return; }
  if (act === 'cancel') { await guard(() => api('POST', `/projects/${id}/cancel`), 'Arrêt demandé'); load(); return; }
  if (act === 'resume') { await guard(() => api('POST', `/projects/${id}/autopilot`), 'Reprise lancée'); load(); return; }
  if (act === 'delete') {
    if (!confirm('Supprimer cette vidéo et tous ses fichiers ?')) return;
    await guard(() => api('DELETE', `/projects/${id}`), 'Vidéo supprimée'); load();
  }
};

// ── Modale : script, plan visuel, refaire une étape / une image ────────────
function closeModal() { $('#modalRoot').innerHTML = ''; S.open = null; }
async function refreshModal() {
  const p = await guard(() => api('GET', `/projects/${S.open}`));
  if (!p || !S.open) return;
  const sc = p.script;
  const text = sc ? [sc.hook, ...sc.sections.map(s => `## ${s.heading}\n${s.text}`)].join('\n\n') : 'Pas encore de script.';
  const segs = (p.plan && p.plan.segments) || [];
  const plan = segs.map(s => {
    const [ic, name] = TYPE[s.type] || ['•', s.type];
    const img = s.src || s.image || s.terrain;
    const bg = img ? `style="background-image:url('${fileUrl(p.id, 'media/' + img)}')"` : '';
    const label = s.title || s.name || (s.text || '').replace(/\*/g, '') || name;
    return `<div class="seg"><div class="im" ${bg} ${img ? `data-zoom="${fileUrl(p.id, 'media/' + img)}"` : ''}>${img ? '' : ic}</div>
      <div class="cap"><b title="${esc(s._prompt || label)}">${ic} ${esc(label)}</b><span>${fmtDur(s.start)}</span>
      ${img ? `<button data-regen="${esc(img)}" title="Refaire cette image">↻</button>` : ''}</div></div>`;
  }).join('');
  $('#modalRoot').innerHTML = `<div class="modal-bg" id="mbg"><div class="modal wide">
    <div class="row between"><div><h2>${esc(p.title)}</h2><div class="sub" style="margin:0">Étape : ${esc(STEP[p.stage] || p.stage)}</div></div>
      <button class="btn sm ghost" id="mClose">✕</button></div>
    <div class="steps">${['script', 'voice', 'plan', 'images', 'render'].map(s => `<button class="btn sm" data-redo="${s}">↻ Refaire ${STEP[s].toLowerCase()}</button>`).join('')}</div>
    <h3 style="margin-top:14px">Plan visuel ${segs.length ? `<span class="faint small">(${segs.length} plans)</span>` : ''}</h3>
    <div class="plan">${plan || '<div class="faint">Le plan arrive après la voix off.</div>'}</div>
    <h3 style="margin-top:14px">Script</h3><div class="script">${esc(text)}</div></div></div>`;
  $('#mClose').onclick = closeModal;
  $('#mbg').onclick = e => { if (e.target.id === 'mbg') closeModal(); };
  $('#modalRoot').querySelectorAll('[data-zoom]').forEach(el => { el.onclick = () => lightbox(el.dataset.zoom); });
  $('#modalRoot').querySelectorAll('[data-regen]').forEach(el => {
    el.onclick = async () => { await guard(() => api('POST', `/projects/${p.id}/regen`, {file: el.dataset.regen}), 'Image relancée, puis nouveau montage'); load(); };
  });
  $('#modalRoot').querySelectorAll('[data-redo]').forEach(el => {
    el.onclick = async () => {
      if (!confirm(`Refaire « ${STEP[el.dataset.redo]} » ? Les étapes suivantes seront refaites aussi.`)) return;
      await guard(() => api('POST', `/projects/${p.id}/redo`, {step: el.dataset.redo}), 'Relancé'); load();
    };
  });
}

// ── Démarrage ──────────────────────────────────────────────────────────────
(async () => {
  S.cfg = await guard(() => api('GET', '/config'));
  if (S.cfg) {
    $('#voice').innerHTML = S.cfg.voices.map(v => `<option value="${v.provider}|${v.voice}">${esc(v.name)}</option>`).join('');
    $('#style').innerHTML = (S.cfg.styles || []).map(s => `<option value="${s.key}" ${s.key === S.cfg.defaults.image_style ? 'selected' : ''}>${esc(s.name)}</option>`).join('');
    const on = new Set(S.cfg.defaults.templates || []);
    $('#tpls').innerHTML = Object.entries(TYPE).filter(([k]) => k !== 'image')
      .map(([k, [ic, name]]) => `<label><input type="checkbox" value="${k}" ${on.has(k) ? 'checked' : ''}> ${ic} ${esc(name)}</label>`).join('');
    const warn = [];
    if (!S.cfg.ai) warn.push('proxy IA non configuré (.env)');
    if (!S.cfg.node) warn.push('Node.js manquant (rendu Remotion) : installe-le depuis nodejs.org');
    else if (!S.cfg.engine_deps) warn.push('moteur d\'animation : les dépendances s\'installeront au 1er rendu');
    if (!S.cfg.tts.algrow) warn.push('ALGROW_API_KEY absente : choisis une voix Edge');
    $('#envHint').innerHTML = warn.length ? `⚠ ${esc(warn.join(' · '))}` : '✔ Prêt : IA, voix, ffmpeg et moteur d\'animation.';
    $('#topInfo').innerHTML = `<span class="pill ${S.cfg.ai ? 'ok' : 'err'}">IA</span><span class="pill ${S.cfg.node ? 'ok' : 'err'}">Remotion</span>`
      + `<span class="pill ${S.cfg.ffmpeg ? 'ok' : 'err'}">ffmpeg</span>`;
  }
  onMinutes();
  load();
})();
