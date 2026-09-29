// ============================================================================
// Oddly Specific Lives — studio simplifié : titre + durée → vidéo finie.
// Tout tourne côté serveur (/api/pov/*) : on peut fermer l'onglet pendant une vidéo.
// ============================================================================
'use strict';

const STUDIO = new URLSearchParams(location.search).get('studio') || 'oddly_specific_en';
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
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
  if (body instanceof FormData) opt.body = body;
  else if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers['Content-Type'] = 'application/json'; }
  let r;
  try { r = await fetch('/api/pov' + path, opt); } catch (e) { throw new Error('Serveur injoignable — le studio tourne-t-il ?'); }
  if (r.status === 401) throw new Error('Session verrouillée — recharge la page et reconnecte-toi.');
  const data = (r.headers.get('Content-Type') || '').includes('json') ? await r.json() : null;
  if (!r.ok) throw new Error((data && data.error) || `Erreur ${r.status}`);
  return data;
}
const fileUrl = (pid, rel, v, dl) => `/api/pov/projects/${pid}/files/${rel}${v || dl ? '?' : ''}${v ? 'v=' + v : ''}${v && dl ? '&' : ''}${dl ? 'dl=1' : ''}`;
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

// ── État ────────────────────────────────────────────────────────────────────
const S = {ch: null, projects: [], pollT: null, playing: new Set(), thumbFor: null};
const JOB = {autopilot: 'Création de la vidéo', script: 'Script', voice: 'Voix off', images: 'Images', render: 'Montage',
  thumbnails: 'Miniatures', cast: 'Personnages', audit: 'Audit FacelessOS', regen: 'Image'};

// ── Formulaire « Nouvelle vidéo » ──────────────────────────────────────────
const CHIPS = [5, 8, 10, 14, 20, 25];
function renderChips() {
  const v = Number($('#minutes').value);
  $('#chips').innerHTML = CHIPS.map(m => `<span class="chip ${m === v ? 'on' : ''}" data-m="${m}">${m} min</span>`).join('');
}
$('#chips').onclick = e => { const c = e.target.closest('.chip'); if (!c) return; $('#minutes').value = c.dataset.m; onMinutes(); };
function onMinutes() {
  const m = Number($('#minutes').value), ch = S.ch || {wpm: 158, pacing: 6};
  $('#minOut').textContent = `${m} min`;
  renderChips();
  const words = m * (ch.wpm || 158), imgs = Math.ceil(m * 60 / (ch.pacing || 6));
  $('#est').innerHTML = `<span>≈ <b>${nf(words)}</b> mots</span><span>≈ <b>${nf(imgs)}</b> images</span>`
    + `<span>≈ <b>${nf(words * 5.9)}</b> caractères Algrow</span><span>≈ <b>${nf(25 + m * 3)} min</b> de fabrication</span>`;
}
$('#minutes').oninput = onMinutes;

$('#create').onclick = async e => {
  const title = $('#title').value.trim();
  if (title.length < 4) { toast('Écris le titre de la vidéo.', 'err'); $('#title').focus(); return; }
  const minutes = Number($('#minutes').value);
  const running = S.projects.filter(p => p.job && p.job.status === 'running' && p.job.kind === 'autopilot').length;
  if (running && !confirm(`${running} vidéo(s) déjà en cours. En lancer une autre en parallèle ? (les images se partagent le même quota)`)) return;
  busy(e.currentTarget, true, 'Lancement…');
  const r = await guard(() => api('POST', `/studio/${STUDIO}/videos`, {title, minutes, notes: $('#notes').value.trim()}));
  busy($('#create'), false);
  if (r) { $('#title').value = ''; $('#notes').value = ''; toast('C\'est parti : la vidéo se fabrique.', 'ok'); await load(); }
};
$('#title').addEventListener('keydown', e => { if (e.key === 'Enter') $('#create').click(); });

// ── Liste des vidéos ────────────────────────────────────────────────────────
function statusOf(p) {
  const j = p.job;
  if (j && j.status === 'running') return {k: 'run', label: JOB[j.kind] || j.kind, cls: 'acc'};
  if (p.render) return {k: 'done', label: 'Vidéo prête', cls: 'ok'};
  if (j && j.status === 'error') return {k: 'err', label: 'Erreur', cls: 'err'};
  if (j && j.status === 'cancelled') return {k: 'stop', label: 'Arrêtée', cls: 'warn'};
  return {k: 'idle', label: 'En attente', cls: ''};
}

function card(p) {
  const st = statusOf(p), j = p.job || {};
  const pct = Math.round((j.progress || 0) * 100);
  const poster = p.thumbnails && p.thumbnails[0] ? fileUrl(p.id, p.thumbnails[0].file) : (p.thumb ? fileUrl(p.id, p.thumb) : '');
  const playing = S.playing.has(p.id) && p.render;
  const media = playing
    ? `<video src="${fileUrl(p.id, p.render.file, p.render.v)}" controls autoplay preload="metadata"></video>`
    : (poster ? `<img src="${poster}" alt="">` : '🎬') + (p.render ? `<button class="play" data-act="play" title="Regarder">▶</button>` : '');
  const meta = [
    `<span class="pill ${st.cls}">${st.k === 'run' ? '<span class="spin" style="width:10px;height:10px"></span>' : ''}${esc(st.label)}</span>`,
    `<span>${esc(p.minutes)} min visées</span>`,
    p.render ? `<span>durée ${fmtDur(p.render.duration)}</span>` : (p.duration ? `<span>voix ${fmtDur(p.duration)}</span>` : ''),
    p.scenes ? `<span>${p.images}/${p.scenes} images</span>` : '',
    p.verdict ? `<span class="pill ${p.verdict === 'PASS' ? 'ok' : 'warn'}" title="Verdict de l'audit FacelessOS du script">FacelessOS ${esc(p.verdict)}</span>` : '',
    `<span class="faint">${esc(ago(p.created))}</span>`,
  ].filter(Boolean).join('');
  const prog = st.k === 'run'
    ? `<div class="prog"><i style="width:${pct}%"></i></div><div class="pmsg">${pct}% · ${esc(j.message || '')}</div>` : '';
  const err = st.k === 'err' ? `<div class="perr">${esc(j.error || j.message || 'Erreur')}</div>` : '';
  const thumbs = (p.thumbnails || []).length
    ? `<div class="vthumbs">${p.thumbnails.slice(0, 4).map(t => `<img src="${fileUrl(p.id, t.file)}" data-zoom="${fileUrl(p.id, t.file)}" alt="">`).join('')}</div>` : '';
  const acts = [];
  if (p.render) acts.push(`<a class="btn sm primary" href="${fileUrl(p.id, p.render.file, p.render.v, true)}">⬇ Télécharger la vidéo</a>`);
  acts.push(`<button class="btn sm" data-act="thumbs">🖼 Miniatures</button>`);
  if (st.k === 'run') acts.push(`<button class="btn sm" data-act="cancel">■ Arrêter</button>`);
  if (st.k === 'err' || st.k === 'stop' || st.k === 'idle') acts.push(`<button class="btn sm ok" data-act="resume">↻ Reprendre</button>`);
  acts.push(`<a class="btn sm ghost" href="/tools/pov-studio" target="_top" data-act="edit" title="Ouvrir dans l'éditeur complet (retoucher le script, une image…)">✎ Éditeur</a>`);
  if (st.k !== 'run') acts.push(`<button class="btn sm danger" data-act="del">Supprimer</button>`);
  return `<div class="vcard" data-id="${p.id}">
    <div class="vthumb">${media}</div>
    <div class="vbody">
      <div class="vtitle">${esc(p.title)}</div>
      <div class="vmeta">${meta}</div>
      ${prog}${err}${thumbs}
      <div class="vactions">${acts.join('')}</div>
    </div></div>`;
}

function renderList() {
  const list = $('#list');
  $('#count').textContent = S.projects.length ? `${S.projects.length} vidéo(s)` : '';
  if (!S.projects.length) {
    list.innerHTML = `<div class="empty"><h2>Aucune vidéo pour l'instant</h2>Mets un titre au-dessus, choisis la durée, et lance la première.</div>`;
    return;
  }
  // ne recrée pas une carte dont la vidéo est en lecture (sinon la lecture s'arrête à chaque rafraîchissement)
  const keep = new Map($$('.vcard', list).filter(c => S.playing.has(c.dataset.id)).map(c => [c.dataset.id, c]));
  const html = S.projects.map(p => keep.has(p.id) ? `<div data-keep="${p.id}"></div>` : card(p)).join('');
  list.innerHTML = html;
  keep.forEach((el, id) => { const slot = $(`[data-keep="${id}"]`, list); if (slot) slot.replaceWith(el); });
}

$('#list').onclick = async e => {
  const zoom = e.target.closest('[data-zoom]'); if (zoom) { lightbox(zoom.dataset.zoom); return; }
  const b = e.target.closest('[data-act]'); if (!b) return;
  const id = b.closest('.vcard').dataset.id, p = S.projects.find(x => x.id === id);
  const act = b.dataset.act;
  if (act === 'edit') { try { localStorage.setItem('pov.openProject', id); } catch (_) {} return; }
  e.preventDefault();
  if (act === 'play') { S.playing.add(id); const el = b.closest('.vcard'); el.outerHTML = card(p); return; }
  if (act === 'thumbs') { openThumbs(p); return; }
  if (act === 'cancel') { if (confirm('Arrêter la fabrication ? Tu pourras la reprendre là où elle s\'est arrêtée.')) { await guard(() => api('POST', `/projects/${id}/cancel`)); load(); } return; }
  if (act === 'resume') { await guard(() => api('POST', `/projects/${id}/autopilot`, {}), 'Reprise lancée'); load(); return; }
  if (act === 'del') {
    if (!confirm(`Supprimer « ${p.title} » et tous ses fichiers (vidéo, images, voix) ?`)) return;
    S.playing.delete(id); await guard(() => api('DELETE', `/projects/${id}`)); load();
  }
};

// ── Chargement + suivi ──────────────────────────────────────────────────────
async function load() {
  clearTimeout(S.pollT);
  const r = await guard(() => api('GET', `/studio/${STUDIO}`));
  if (r) {
    const first = !S.ch;
    S.ch = r.channel; S.projects = r.projects;
    if (first) { $('#minutes').value = Math.min(30, Math.max(3, Math.round(S.ch.default_minutes || 14))); onMinutes(); }
    $('#refHint').innerHTML = S.ch.has_reference ? '✓ Script calé sur la vidéo de référence (Female Yakuza) · audit FacelessOS'
      : '⚠ Pas de vidéo de référence pour cette chaîne.';
    renderList();
    if (S.thumbFor) refreshThumbModal();
  }
  const running = S.projects.some(p => p.job && p.job.status === 'running');
  S.pollT = setTimeout(load, running ? 3000 : 20000);
}
async function credits() {
  try {
    const c = await api('GET', '/algrow/credits');
    if (c && c.elevenlabs != null) $('#topInfo').innerHTML = `<span title="Crédits Algrow restants (voix ElevenLabs)">🎙 ${nf(c.elevenlabs)} caractères Algrow</span>`;
  } catch (_) { /* crédits : purement informatif */ }
}

// ── Miniatures ──────────────────────────────────────────────────────────────
const T = {files: [], yt: ''};
function closeModal() { $('#modalRoot').innerHTML = ''; S.thumbFor = null; }
function defaultPrompt(p) {
  return `A beautiful stylized woman matching the premise of "${p.title}", confident knowing smile, iconic outfit of her culture, `
    + 'holding a bouquet of red roses, the most iconic landmark of her country behind her at golden hour.';
}
function openThumbs(p) {
  S.thumbFor = p.id; T.files = []; T.yt = '';
  $('#modalRoot').innerHTML = `<div class="modal-bg" id="mbg"><div class="modal wide">
    <div class="row between"><div><h2>Miniatures</h2><div class="sub" style="margin:0">${esc(p.title)}</div></div><button class="btn sm ghost" id="mClose">✕</button></div>
    <div class="grid2" style="margin-top:14px">
      <div class="stack">
        <label class="f"><span class="lbl">Lien d'une vidéo YouTube (sa miniature sert de modèle)</span>
          <input type="url" id="tYt" placeholder="https://www.youtube.com/watch?v=…"></label>
        <label class="filebtn">📁 Ajouter des images de référence (perso, objet, style…)<input type="file" id="tFiles" accept="image/*" multiple></label>
        <div class="refs" id="tRefs"></div>
        <label class="f"><span class="lbl">Prompt</span><textarea id="tPrompt" rows="5">${esc(defaultPrompt(p))}</textarea></label>
        <div class="row">
          <label class="f" style="width:140px"><span class="lbl">Nombre d'images</span>
            <select id="tCount"><option>1</option><option selected>2</option><option>3</option><option>4</option></select></label>
          <label class="row small muted" style="margin-top:18px"><input type="checkbox" id="tStyle" checked> Style miniature de la chaîne</label>
        </div>
        <div class="hint">Sans lien ni image, la miniature de référence de la chaîne sert de modèle. Avec un lien, c'est sa miniature qui est imitée (composition, style, couleurs) avec ton contenu.</div>
        <div class="row between"><button class="btn sm" id="tAuto" title="L'IA propose elle-même 2 concepts à partir du script">✨ 2 idées auto</button>
          <button class="btn primary" id="tGo">⚡ Générer</button></div>
      </div>
      <div><div class="row between"><h3>Résultats</h3><span class="small muted" id="tState"></span></div><div class="tgrid" id="tGrid"></div></div>
    </div></div></div>`;
  $('#mClose').onclick = closeModal;
  $('#mbg').onclick = e => { if (e.target.id === 'mbg') closeModal(); };
  $('#tYt').oninput = e => { T.yt = e.target.value.trim(); renderRefs(); };
  $('#tFiles').onchange = e => { T.files = [...T.files, ...e.target.files].slice(0, 4); e.target.value = ''; renderRefs(); };
  $('#tGo').onclick = () => genThumbs(p);
  $('#tAuto').onclick = async ev => {
    busy(ev.currentTarget, true, '');
    await guard(() => api('POST', `/projects/${p.id}/thumbnails`, {count: 2}), 'Miniatures auto lancées');
    busy($('#tAuto'), false); load();
  };
  refreshThumbModal();
}
function renderRefs() {
  const items = [];
  const id = (T.yt.match(/(?:v=|youtu\.be\/|shorts\/|embed\/)([A-Za-z0-9_-]{11})/) || [])[1];
  if (id) items.push(`<div class="ref"><img src="/api/pov/youtube-thumb?url=${encodeURIComponent(T.yt)}" alt=""><span class="tag">modèle</span></div>`);
  T.files.forEach((f, i) => items.push(`<div class="ref"><img src="${URL.createObjectURL(f)}" alt=""><button class="x" data-i="${i}">✕</button>${!id && i === 0 ? '<span class="tag">modèle</span>' : ''}</div>`));
  $('#tRefs').innerHTML = items.join('');
  $$('#tRefs .x').forEach(b => b.onclick = () => { T.files.splice(Number(b.dataset.i), 1); renderRefs(); });
}
async function genThumbs(p) {
  const prompt = $('#tPrompt').value.trim();
  if (!prompt) { toast('Écris un prompt.', 'err'); return; }
  const fd = new FormData();
  fd.append('prompt', prompt); fd.append('count', $('#tCount').value); fd.append('channel_style', $('#tStyle').checked ? '1' : '0');
  if (T.yt) fd.append('youtube_url', T.yt);
  T.files.forEach(f => fd.append('files', f));
  busy($('#tGo'), true, 'Envoi…');
  const r = await guard(() => api('POST', `/projects/${p.id}/thumbs/custom`, fd));
  busy($('#tGo'), false);
  if (r) { toast('Miniatures en cours…', 'ok'); load(); }
}
function refreshThumbModal() {
  const p = S.projects.find(x => x.id === S.thumbFor);
  if (!p || !$('#tGrid')) return;
  const j = p.job, run = j && j.status === 'running' && j.kind === 'thumbnails';
  $('#tState').innerHTML = run ? `<span class="spin" style="width:12px;height:12px;display:inline-block;vertical-align:-2px"></span> ${Math.round((j.progress || 0) * 100)}% · ${esc(j.message || '')}`
    : (j && j.kind === 'thumbnails' && j.status === 'error' ? `<span class="perr">${esc(j.error || '')}</span>` : '');
  const busyOther = j && j.status === 'running' && j.kind !== 'thumbnails';
  $('#tGo').disabled = run || busyOther; $('#tAuto').disabled = run || busyOther;
  if (busyOther) $('#tState').textContent = 'La vidéo est encore en fabrication : les miniatures se lancent après.';
  $('#tGrid').innerHTML = (p.thumbnails || []).map(t => `<div class="tshot"><img src="${fileUrl(p.id, t.file)}" data-zoom alt="">
      <div class="bar"><a class="btn xs" href="${fileUrl(p.id, t.file, 0, true)}">⬇</a></div></div>`).join('')
    || '<div class="hint">Les miniatures générées apparaîtront ici.</div>';
  $$('#tGrid img').forEach(im => im.onclick = () => lightbox(im.src));
}

// ── Démarrage ───────────────────────────────────────────────────────────────
renderChips(); onMinutes(); load(); credits();
