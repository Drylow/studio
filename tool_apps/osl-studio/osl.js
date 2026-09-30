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
const S = {ch: null, projects: [], pollT: null, playing: new Set(), thumbFor: null, regen: null, usage: null, pubOpen: new Set()};
const JOB = {autopilot: 'Création de la vidéo', metadata: 'Titre & description', script: 'Script', voice: 'Voix off', images: 'Images', render: 'Montage',
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
    + `<span>≈ <b>${nf(words * 5.9)}</b> caractères Algrow</span><span>≈ <b>${nf((fast() ? 6 : 12) + m * (fast() ? 1.6 : 1.9))} min</b> de fabrication</span>`;
}
const fast = () => !$('#fast') || $('#fast').checked;
$('#minutes').oninput = onMinutes;
$('#fast').onchange = onMinutes;

$('#create').onclick = async e => {
  const title = $('#title').value.trim();
  if (title.length < 4) { toast('Écris le titre de la vidéo.', 'err'); $('#title').focus(); return; }
  const minutes = Number($('#minutes').value);
  const running = S.projects.filter(p => p.job && p.job.status === 'running' && p.job.kind === 'autopilot').length;
  if (running && !confirm(`${running} vidéo(s) déjà en cours. En lancer une autre en parallèle ? (les images se partagent le même quota)`)) return;
  busy(e.currentTarget, true, 'Lancement…');
  const r = await guard(() => api('POST', `/studio/${STUDIO}/videos`, {title, minutes, notes: $('#notes').value.trim(), fast: fast()}));
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
  const pub = p.render ? pubPanel(p) : '';
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
      ${pub}
    </div></div>`;
}

// ── Publication : titre, description, tags, commentaire épinglé à copier ───
function pubPanel(p) {
  const md = p.metadata, j = p.job || {}, gen = j.status === 'running' && (j.kind === 'metadata' || (j.message || '').includes('Publication'));
  const open = S.pubOpen.has(p.id) ? 'open' : '';
  if (!md || !md.description) {
    return `<details class="pub" data-pub ${open}><summary>📝 Titre & description YouTube</summary>
      <div class="pubbody"><div class="hint">${gen ? '<span class="spin" style="display:inline-block;width:12px;height:12px;vertical-align:-2px"></span> Rédaction en cours…' : 'Pas encore générés pour cette vidéo.'}</div>
      <button class="btn sm primary" data-act="meta" ${gen || j.status === 'running' ? 'disabled' : ''}>📝 Générer titre & description</button></div></details>`;
  }
  const tags = (md.tags || []).join(', ');
  const field = (label, key, value, rows) => `<div class="pubf"><div class="row between"><span class="lbl">${label}</span>
      <button class="btn xs" data-copy="${key}">📋 Copier</button></div>
      ${rows ? `<textarea readonly rows="${rows}" data-val="${key}">${esc(value)}</textarea>` : `<input type="text" readonly data-val="${key}" value="${esc(value)}">`}</div>`;
  const others = (md.titles || []).slice(1).map((t, i) => `<div class="alt"><span>${esc(t)}</span><button class="btn xs" data-copy="alt${i}">📋</button><input type="hidden" data-val="alt${i}" value="${esc(t)}"></div>`).join('');
  return `<details class="pub" data-pub ${open}><summary>📝 Titre & description YouTube <span class="pill ok" style="margin-left:6px">prêts</span></summary>
    <div class="pubbody">
      ${field('Titre', 'title', (md.titles || [p.title])[0])}
      ${others ? `<div class="pubf"><span class="lbl">Autres idées de titre</span>${others}</div>` : ''}
      ${field('Description', 'desc', md.description, 9)}
      ${field(`Tags <span class="faint">(${tags.length}/500 caractères)</span>`, 'tags', tags, 3)}
      ${md.pinned_comment ? field('Commentaire à épingler', 'pin', md.pinned_comment, 3) : ''}
      <div class="row"><button class="btn xs ghost" data-act="meta" ${j.status === 'running' ? 'disabled' : ''}>↻ Regénérer</button>
        <span class="tiny faint">Rédigés avec la skill packaging de FacelessOS, dans le style de tes descriptions.</span></div>
    </div></details>`;
}
async function copyText(text, btn) {
  try { await navigator.clipboard.writeText(text); }
  catch (_) { const t = document.createElement('textarea'); t.value = text; document.body.appendChild(t); t.select(); document.execCommand('copy'); t.remove(); }
  if (btn) { const o = btn.textContent; btn.textContent = '✓ Copié'; setTimeout(() => { btn.textContent = o; }, 1400); }
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

$('#list').addEventListener('toggle', e => {
  const d = e.target.closest && e.target.closest('[data-pub]'); if (!d) return;
  const id = d.closest('.vcard').dataset.id; if (d.open) S.pubOpen.add(id); else S.pubOpen.delete(id);
}, true);
$('#list').onclick = async e => {
  const zoom = e.target.closest('[data-zoom]'); if (zoom) { lightbox(zoom.dataset.zoom); return; }
  const cp = e.target.closest('[data-copy]');
  if (cp) { const el = cp.closest('.pubbody').querySelector(`[data-val="${cp.dataset.copy}"]`); if (el) copyText(el.value, cp); return; }
  const b = e.target.closest('[data-act]'); if (!b) return;
  const id = b.closest('.vcard').dataset.id, p = S.projects.find(x => x.id === id);
  const act = b.dataset.act;
  if (act === 'edit') { try { localStorage.setItem('pov.openProject', id); } catch (_) {} return; }
  e.preventDefault();
  if (act === 'play') { S.playing.add(id); const el = b.closest('.vcard'); el.outerHTML = card(p); return; }
  if (act === 'thumbs') { openThumbs(p); return; }
  if (act === 'meta') { S.pubOpen.add(id); await guard(() => api('POST', `/projects/${id}/metadata`, {}), 'Rédaction du titre et de la description…'); load(); return; }
  if (act === 'cancel') { if (confirm('Arrêter la fabrication ? Tu pourras la reprendre là où elle s\'est arrêtée.')) { await guard(() => api('POST', `/projects/${id}/cancel`)); load(); } return; }
  if (act === 'resume') { await guard(() => api('POST', `/projects/${id}/autopilot`, {}), 'Reprise lancée'); load(); return; }
  if (act === 'del') {
    if (!confirm(`Supprimer DÉFINITIVEMENT « ${p.title} » ?\n\nLa vidéo, les images, la voix, les miniatures et le script sont effacés du disque. Impossible d'annuler.`)) return;
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
  if (!run) S.regen = null;
  $('#tGrid').innerHTML = (p.thumbnails || []).map(t => `<div class="tshot ${run && S.regen === t.file ? 'busy' : ''}" data-file="${esc(t.file)}">
      <img src="${fileUrl(p.id, t.file)}" alt="">${run && S.regen === t.file ? '<span class="spin sp"></span>' : ''}
      <div class="bar"><a class="btn xs" href="${fileUrl(p.id, t.file, 0, true)}" title="Télécharger">⬇</a>
        <button class="btn xs" data-t="regen" title="Regénérer cette miniature (même prompt, mêmes références)" ${run || busyOther ? 'disabled' : ''}>↻</button>
        <button class="btn xs danger" data-t="del" title="Supprimer cette miniature" ${run ? 'disabled' : ''}>🗑</button></div></div>`).join('')
    || '<div class="hint">Les miniatures générées apparaîtront ici.</div>';
  $$('#tGrid img').forEach(im => im.onclick = () => lightbox(im.src));
  $$('#tGrid [data-t]').forEach(b => b.onclick = async () => {
    const file = b.closest('.tshot').dataset.file;
    if (b.dataset.t === 'regen') {
      S.regen = file;
      const r = await guard(() => api('POST', `/projects/${p.id}/thumbs/regen`, {file}));
      if (!r) S.regen = null; load(); return;
    }
    if (!confirm('Supprimer cette miniature ?')) return;
    await guard(() => api('POST', `/projects/${p.id}/thumbs/delete`, {file})); load();
  });
}

// ── Projets : place disque, alléger, supprimer ─────────────────────────────
const fmtSize = b => b >= 1e9 ? (b / 1e9).toFixed(2).replace('.', ',') + ' Go' : b >= 1e6 ? Math.round(b / 1e6) + ' Mo'
  : b > 0 ? Math.max(1, Math.round(b / 1e3)) + ' Ko' : '0';
const STAGE = {rendered: 'Vidéo prête', storyboard: 'Images faites', voice: 'Voix faite', script: 'Script écrit', idea: 'À faire'};
function showView(v) {
  $$('.tab').forEach(t => t.classList.toggle('on', t.dataset.view === v));
  $('#viewVideos').classList.toggle('hidden', v !== 'videos');
  $('#viewProjects').classList.toggle('hidden', v !== 'projects');
  if (v === 'projects') loadUsage();
}
$$('.tab').forEach(t => t.onclick = () => showView(t.dataset.view));
async function loadUsage() {
  $('#ptable').innerHTML = '<tr class="empty-row"><td><span class="spin" style="display:inline-block"></span></td></tr>';
  const r = await guard(() => api('GET', `/studio/${STUDIO}/usage`));
  if (!r) return;
  S.usage = r.projects;
  $('#usageTotal').innerHTML = `<b>${fmtSize(r.total)}</b>utilisés par ${r.projects.length} vidéo(s)`;
  const work = r.projects.reduce((n, p) => n + (p.running ? 0 : p.work), 0);
  $('#slimAll').disabled = !work; $('#slimAll').textContent = work ? `🧹 Tout alléger (−${fmtSize(work)})` : '🧹 Rien à alléger';
  $('#ptable').innerHTML = r.projects.length ? `<tr><th>Vidéo</th><th>Créée</th><th>État</th><th>Durée</th><th>Place</th><th></th></tr>`
    + r.projects.map(p => `<tr data-id="${p.id}">
      <td class="t">${esc(p.title)}</td>
      <td class="num faint">${esc(ago(p.created))}</td>
      <td>${p.running ? '<span class="pill acc">En cours</span>' : `<span class="pill ${p.stage === 'rendered' ? 'ok' : ''}">${STAGE[p.stage] || p.stage}</span>`}</td>
      <td class="num">${p.duration ? fmtDur(p.duration) : '–'}</td>
      <td class="num"><b>${fmtSize(p.total)}</b>${p.work ? `<div class="tiny faint">dont ${fmtSize(p.work)} de travail</div>` : ''}</td>
      <td class="acts">${p.work && !p.running ? `<button class="btn xs" data-pact="slim">🧹 Alléger</button>` : ''}
        <button class="btn xs danger" data-pact="del" ${p.running ? 'title="Arrête d\'abord la fabrication"' : ''}>🗑 Supprimer</button></td></tr>`).join('')
    : '<tr class="empty-row"><td>Aucune vidéo.</td></tr>';
}
$('#usageRefresh').onclick = loadUsage;
$('#slimAll').onclick = async e => {
  const todo = (S.usage || []).filter(p => p.work && !p.running);
  if (!todo.length || !confirm(`Alléger ${todo.length} vidéo(s) ? Les vidéos finales, images, voix et miniatures restent.`)) return;
  busy(e.currentTarget, true, 'Nettoyage…');
  let freed = 0;
  for (const p of todo) { const r = await guard(() => api('POST', `/projects/${p.id}/slim`)); if (r) freed += r.freed; }
  busy($('#slimAll'), false); toast(`${fmtSize(freed)} libérés`, 'ok'); loadUsage();
};
$('#ptable').onclick = async e => {
  const b = e.target.closest('[data-pact]'); if (!b) return;
  const id = b.closest('tr').dataset.id, p = (S.usage || []).find(x => x.id === id);
  if (b.dataset.pact === 'slim') {
    busy(b, true, ''); const r = await guard(() => api('POST', `/projects/${id}/slim`));
    if (r) toast(`${fmtSize(r.freed)} libérés`, 'ok'); loadUsage(); return;
  }
  const warn = p.running ? '\n\nElle est en cours de fabrication : elle sera arrêtée.' : '';
  if (!confirm(`Supprimer DÉFINITIVEMENT « ${p.title} » ?\n\nLa vidéo, les images, la voix, les miniatures et le script sont effacés du disque (${fmtSize(p.total)}). Impossible d'annuler.${warn}`)) return;
  busy(b, true, '');
  const r = await guard(() => api('DELETE', `/projects/${id}`));
  if (r) { S.playing.delete(id); toast(`« ${p.title} » supprimée (${fmtSize(p.total)} libérés)`, 'ok'); }
  loadUsage(); load();
};

// ── Démarrage ───────────────────────────────────────────────────────────────
renderChips(); onMinutes(); load(); credits();
