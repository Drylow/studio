// ============================================================================
// 2D Videos — interface (vanilla JS). Tout le travail lourd tourne côté serveur
// (Flask local, /api/pov/*) : on peut fermer l'onglet pendant une génération.
// ============================================================================
'use strict';

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const clone = o => JSON.parse(JSON.stringify(o));
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
function fmtDur(sec) {
  if (sec == null || isNaN(sec)) return '–';
  sec = Math.round(sec); const m = Math.floor(sec / 60), s = sec % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}
function fmtTs(sec) { return fmtDur(sec) + '.' + String(Math.floor((sec % 1) * 10)); }
function ago(iso) {
  if (!iso) return ''; const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 60) return 'à l\'instant'; if (d < 3600) return `il y a ${Math.floor(d / 60)} min`;
  if (d < 86400) return `il y a ${Math.floor(d / 3600)} h`; return new Date(iso).toLocaleDateString();
}

// ── API ─────────────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opt = {method, headers: {Accept: 'application/json'}};
  if (body instanceof FormData) opt.body = body;
  else if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers['Content-Type'] = 'application/json'; }
  let r;
  try { r = await fetch('/api/pov' + path, opt); }
  catch (e) { throw new Error('Serveur injoignable — le studio tourne-t-il ?'); }
  if (r.status === 401) throw new Error('Session verrouillée — recharge la page et reconnecte-toi.');
  const ct = r.headers.get('Content-Type') || '';
  const data = ct.includes('json') ? await r.json() : await r.blob();
  if (!r.ok) throw new Error((data && data.error) || `Erreur ${r.status}`);
  return data;
}
const fileUrl = (pid, rel, v) => rel ? `/api/pov/projects/${pid}/files/${rel}${v ? '?v=' + v : ''}` : '';
const chFileUrl = (cid, rel) => rel ? `/api/pov/channels/${cid}/files/${rel}` : '';

function toast(msg, kind = '') {
  const el = document.createElement('div');
  el.className = 'toast ' + kind; el.textContent = msg;
  $('#toasts').appendChild(el);
  setTimeout(() => el.remove(), kind === 'err' ? 7000 : 3500);
}
async function guard(fn, okMsg) {
  try { const r = await fn(); if (okMsg) toast(okMsg, 'ok'); return r; }
  catch (e) { toast(e.message || String(e), 'err'); return null; }
}
function busy(btn, on, label) {
  if (!btn) return;
  if (on) { btn.dataset.label = btn.innerHTML; btn.disabled = true; btn.innerHTML = `<span class="spin"></span>${label || ''}`; }
  else { btn.disabled = false; if (btn.dataset.label) btn.innerHTML = btn.dataset.label; }
}

// ── État ────────────────────────────────────────────────────────────────────
const S = {cfg: null, channels: [], project: null, step: 'script', pollT: null, listT: null, editing: new Set()};
const STEPS = [['script', 'Script'], ['voice', 'Voix off'], ['storyboard', 'Storyboard'], ['export', 'Montage & export']];
const JOB_LABEL = {script: 'Écriture du script', rewrite: 'Réécriture', audit: 'Audit FacelessOS', voice: 'Voix off', replan: 'Scènes', cast: 'Personnages', images: 'Images',
  regen: 'Image', render: 'Montage MP4', pack: 'Pack montage', metadata: 'Métadonnées', autopilot: 'Autopilot', thumbnails: 'Miniatures'};

async function loadConfig() {
  S.cfg = await api('GET', '/config');
  const d = S.cfg;
  $('#statusDots').innerHTML =
    `<span title="${esc(d.ai.base || 'non configuré')}"><i class="dot ${d.ai.configured ? 'ok' : 'bad'}"></i>IA</span>` +
    `<span><i class="dot ${d.ffmpeg ? 'ok' : 'bad'}"></i>ffmpeg</span>` +
    `<span><i class="dot ${d.tts.edge || d.tts.elevenlabs || d.tts.openai ? 'ok' : 'bad'}"></i>Voix</span>`;
}
async function loadChannels() { S.channels = (await api('GET', '/channels')).channels; return S.channels; }
const chById = id => S.channels.find(c => c.id === id);

// ── Router ──────────────────────────────────────────────────────────────────
function go(hash) { if (location.hash === hash) route(); else location.hash = hash; }
window.addEventListener('hashchange', route);
function stopPolls() { clearTimeout(S.pollT); clearTimeout(S.listT); S.pollT = S.listT = null; }
async function route() {
  stopPolls();
  window.onbeforeunload = null;
  $('#view').oninput = null;
  closeModal(); closeViewer();
  const parts = (location.hash || '#/projects').slice(2).split('/');
  const tab = {project: 'projects', projects: 'projects', channel: 'channels', channels: 'channels', settings: 'settings'}[parts[0]] || 'projects';
  $$('.tab').forEach(t => t.classList.toggle('on', t.dataset.tab === tab));
  const v = $('#view');
  try {
    if (!S.cfg) await loadConfig();
    if (parts[0] === 'project' && parts[1]) return await viewProject(parts[1], parts[2]);
    if (parts[0] === 'channels') return await viewChannels();
    if (parts[0] === 'channel' && parts[1]) return await viewChannel(parts[1]);
    if (parts[0] === 'settings') return await viewSettings();
    return await viewProjects();
  } catch (e) {
    v.innerHTML = `<div class="empty"><h2>Oups</h2><p>${esc(e.message)}</p></div>`;
  }
}

// ── Modales ─────────────────────────────────────────────────────────────────
function modal(html, cls = '') {
  $('#modalRoot').innerHTML = `<div class="modal-bg" onclick="if(event.target===this)closeModal()"><div class="modal ${cls}">${html}</div></div>`;
  return $('#modalRoot .modal');
}
function closeModal() { $('#modalRoot').innerHTML = ''; }
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeModal(); closeViewer(); }
  if ($('.viewer') && (e.key === 'ArrowRight' || e.key === 'ArrowLeft') && !['TEXTAREA', 'INPUT'].includes(document.activeElement.tagName)) viewerNav(e.key === 'ArrowRight' ? 1 : -1);
});

// ============================================================================
// VIDÉOS (liste)
// ============================================================================
async function viewProjects() {
  const [{projects}] = await Promise.all([api('GET', '/projects'), loadChannels()]);
  const v = $('#view');
  const running = projects.some(p => p.job);
  v.innerHTML = `
    <div class="hero">
      <div><h1>Tes vidéos</h1><p>Un titre → script calibré pour ta chaîne → voix off → images 2D cohérentes → vidéo montée, ou pack de clips calés pour CapCut.</p></div>
      <div class="row"><button class="btn primary big" onclick="newProjectModal()">＋ Nouvelle vidéo</button></div>
    </div>
    ${!S.channels.length ? `<div class="card" style="margin-bottom:18px"><div class="row between"><div><h2>Commence par créer une chaîne</h2>
      <div class="sub" style="margin:4px 0 0">Une chaîne = niche + format de script + style d'image + voix. Pars d'un modèle basé sur les chaînes 2D qui percent en ce moment.</div></div>
      <button class="btn primary" onclick="go('#/channels')">Créer une chaîne</button></div></div>` : ''}
    ${projects.length ? `<div class="pgrid">${projects.map(projectCard).join('')}</div>`
      : `<div class="empty"><h2>Aucune vidéo pour l'instant</h2><p>Crée ta première vidéo : l'autopilot peut tout faire d'un clic.</p></div>`}`;
  if (running) S.listT = setTimeout(() => { if ((location.hash || '#/projects').startsWith('#/projects') || location.hash === '') viewProjects(); }, 4000);
}
function projectCard(p) {
  const ch = chById(p.channel_id);
  const stage = {idea: ['Idée', ''], script: ['Script', 'acc'], voice: ['Voix', 'acc'], storyboard: ['Images prêtes', 'warn'], rendered: ['Exportée', 'ok']}[p.stage] || ['', ''];
  return `<div class="pcard" onclick="go('#/project/${p.id}')">
    <div class="pthumb">${p.thumb ? `<img src="${fileUrl(p.id, p.thumb)}" loading="lazy">` : '<span style="font-size:30px">🎬</span>'}
      <div class="badge">${p.job ? `<span class="pill acc"><span class="spin" style="width:10px;height:10px"></span>${esc(JOB_LABEL[p.job.kind] || p.job.kind)}</span>` : `<span class="pill ${stage[1]}">${stage[0]}</span>`}</div>
      ${p.duration ? `<div class="dur">${fmtDur(p.duration)}</div>` : ''}</div>
    <div class="pbody"><div class="t">${esc(p.title)}</div>
      <div class="row small muted"><span>${esc(ch ? ch.name : 'Chaîne supprimée')}</span>·<span>${p.words} mots</span>·<span>${p.images}/${p.scenes} img</span></div>
      ${p.job ? `<div class="minibar"><i style="width:${Math.round(p.job.progress * 100)}%"></i></div>` : `<div class="tiny faint">${ago(p.updated)}</div>`}
    </div></div>`;
}

async function newProjectModal(prefill = {}) {
  if (!S.channels.length) await loadChannels();
  if (!S.channels.length) { toast('Crée d\'abord une chaîne.', 'err'); go('#/channels'); return; }
  let chId = prefill.channel_id || localStorage.getItem('pov2.lastChannel') || S.channels[0].id;
  if (!chById(chId)) chId = S.channels[0].id;
  const m = modal(`
    <h2>Nouvelle vidéo</h2><div class="sub">Choisis la chaîne : le script, les images et la voix suivront son ADN.</div>
    <div class="stack">
      <div class="chips" id="npCh">${S.channels.map(c => `<div class="chip ${c.id === chId ? 'on' : ''}" data-id="${c.id}">${esc(c.name)}</div>`).join('')}</div>
      <label class="f"><span class="lbl">Titre / sujet de la vidéo <a href="#" id="npIdeasBtn" class="small">💡 Idées de titres</a></span>
        <input type="text" id="npTitle" placeholder="Your Life as Every Rank of Airline Pilot" value="${esc(prefill.title || '')}"></label>
      <div id="npIdeas" class="stack hidden"></div>
      <div class="grid2">
        <label class="f"><span class="lbl">Durée cible <b id="npMinOut"></b></span><input type="range" id="npMin" min="1" max="40" step="1"></label>
        <label class="f"><span class="lbl">Mode</span><div class="seg" id="npMode"><button data-v="auto" class="on">⚡ Autopilot</button><button data-v="step">Étape par étape</button></div></label>
      </div>
      <label class="f"><span class="lbl">Consignes pour ce script (optionnel)</span>
        <textarea id="npNotes" rows="2" placeholder="Angle, faits à inclure, public, niveau de détail…"></textarea></label>
      <details class="adv"><summary>J'ai déjà mon script</summary>
        <textarea id="npScript" rows="8" placeholder="Colle ton script. Les lignes « ## Titre » deviennent des titres de section à l'écran (non lus)."></textarea></details>
    </div>
    <div class="foot"><button class="btn ghost" onclick="closeModal()">Annuler</button><button class="btn primary" id="npGo">Créer la vidéo</button></div>`);
  const min = $('#npMin', m), out = $('#npMinOut', m);
  const showIdeas = ideas => {
    const box = $('#npIdeas', m);
    box.classList.toggle('hidden', !ideas.length);
    box.innerHTML = ideas.map(i => `<div class="idea" data-t="${esc(i.title)}"><b>${esc(i.title)}</b>${i.angle ? `<span>${esc(i.angle)}</span>` : ''}</div>`).join('');
    box.onclick = ev => { const it = ev.target.closest('.idea'); if (it) { $('#npTitle', m).value = it.dataset.t; box.classList.add('hidden'); } };
  };
  const setCh = id => {
    chId = id; $$('#npCh .chip', m).forEach(x => x.classList.toggle('on', x.dataset.id === id));
    min.value = chById(id).default_minutes || 10; out.textContent = min.value + ' min';
    let saved = []; try { saved = JSON.parse(localStorage.getItem('pov2.ideas.' + id) || '[]'); } catch (e) {}
    showIdeas(saved.map(t => ({title: t})));
  };
  setCh(chId);
  min.oninput = () => out.textContent = min.value + ' min';
  $('#npCh', m).onclick = e => { const c = e.target.closest('.chip'); if (c) setCh(c.dataset.id); };
  let mode = 'auto';
  $('#npMode', m).onclick = e => { const b = e.target.closest('button'); if (!b) return; mode = b.dataset.v; $$('#npMode button', m).forEach(x => x.classList.toggle('on', x === b)); };
  $('#npIdeasBtn', m).onclick = async e => {
    e.preventDefault(); const box = $('#npIdeas', m); box.classList.remove('hidden');
    box.innerHTML = '<div class="row muted small"><span class="spin"></span>L\'IA cherche des idées adaptées à la chaîne…</div>';
    const r = await guard(() => api('POST', `/channels/${chId}/ideas`, {hint: $('#npTitle', m).value}));
    if (!r) { box.classList.add('hidden'); return; }
    showIdeas(r.ideas);
  };
  $('#npGo', m).onclick = async ev => {
    const title = $('#npTitle', m).value.trim();
    if (!title) { toast('Donne un titre ou un sujet.', 'err'); return; }
    busy(ev.target, true, 'Création…');
    localStorage.setItem('pov2.lastChannel', chId);
    const pr = await guard(() => api('POST', '/projects', {channel_id: chId, title, minutes: Number(min.value), notes: $('#npNotes', m).value, script: $('#npScript', m).value}));
    busy(ev.target, false);
    if (!pr) return;
    if (mode === 'auto') await guard(() => api('POST', `/projects/${pr.id}/autopilot`, {}));
    else if (!$('#npScript', m).value.trim()) await guard(() => api('POST', `/projects/${pr.id}/script`, {}));
    closeModal(); go(`#/project/${pr.id}/script`);
  };
  setTimeout(() => $('#npTitle', m).focus(), 50);
}

// ============================================================================
// PROJET
// ============================================================================
async function viewProject(pid, step) {
  await loadChannels();
  S.project = await api('GET', '/projects/' + pid);
  S.step = STEPS.some(s => s[0] === step) ? step : defaultStep(S.project);
  S.editing.clear();
  renderProject();
  pollProject();
}
function defaultStep(p) { return {idea: 'script', script: 'script', voice: 'storyboard', storyboard: 'export', rendered: 'export'}[p.stage] || 'script'; }
function stepDone(p, k) {
  if (k === 'script') return !!(p.script || '').trim();
  if (k === 'voice') return !!p.voice && !p.voice_outdated;
  if (k === 'storyboard') return p.scenes.length > 0 && p.scenes.every(s => s.image);
  return !!(p.render && p.render.file);
}
function jobRunning() { return S.project && S.project.job && S.project.job.status === 'running'; }

function renderProject() {
  const p = S.project, ch = chById(p.channel_id);
  $('#view').innerHTML = `
    <div class="phead">
      <div class="grow"><input class="title-in" id="pTitle" value="${esc(p.title)}" style="width:100%">
        <div class="row small muted" style="margin-top:2px">
          <span class="pill acc">📺 ${esc(ch ? ch.name : '?')}</span>
          <span>${p.words_count} mots</span>·<span>cible ${p.minutes} min</span>
          ${p.voice ? `·<span>voix ${fmtDur(p.voice.duration)}</span>` : ''}
          ${p.scenes.length ? `·<span>${p.scenes.filter(s => s.image).length}/${p.scenes.length} images</span>` : ''}
        </div></div>
      <div class="row">
        <button class="btn" onclick="go('#/projects')">← Vidéos</button>
        <button class="btn primary" id="autoBtn" title="Enchaîne automatiquement toutes les étapes restantes">⚡ Autopilot</button>
        <button class="btn danger sm" id="delBtn">Supprimer</button>
      </div>
    </div>
    <div class="steps">${STEPS.map(([k, l], i) => `<div class="step ${k === S.step ? 'on' : ''} ${stepDone(p, k) ? 'done' : ''}" data-k="${k}"><span class="num">${stepDone(p, k) ? '✓' : i + 1}</span>${l}</div>`).join('')}</div>
    <div id="jobbar"></div>
    <div id="stepBody"></div>`;
  $('.steps').onclick = e => { const s = e.target.closest('.step'); if (s) { S.step = s.dataset.k; history.replaceState(null, '', `#/project/${p.id}/${S.step}`); renderProject(); } };
  $('#pTitle').onchange = e => savePatch({title: e.target.value, title_locked: true});
  $('#delBtn').onclick = async () => { if (confirm(`Supprimer « ${p.title} » et tous ses fichiers ?`)) { await guard(() => api('DELETE', '/projects/' + p.id)); go('#/projects'); } };
  $('#autoBtn').onclick = () => action('autopilot', {});
  $('#autoBtn').disabled = jobRunning();
  renderJobBar();
  ({script: stepScript, voice: stepVoice, storyboard: stepStoryboard, export: stepExport})[S.step]();
}

const _dismissedJobs = new Set();
function renderJobBar() {
  const j = S.project.job, el = $('#jobbar');
  if (!el) return;
  if (!j || _dismissedJobs.has(j.id) || (j.status === 'done' && Date.now() - new Date(j.finished).getTime() > 8000) || j.status === 'cancelled') { el.innerHTML = ''; return; }
  const running = j.status === 'running';
  el.innerHTML = `<div class="jobbar ${j.status === 'error' ? 'error' : ''}">
    ${running ? '<span class="spin"></span>' : (j.status === 'error' ? '⚠️' : '✅')}
    <b class="small" style="white-space:nowrap">${esc(JOB_LABEL[j.kind] || j.kind)}</b>
    <div class="msg ${j.status === 'error' ? '' : 'muted'}" title="${esc(j.error || j.message)}">${esc(j.status === 'error' ? j.error : j.message)}</div>
    ${running ? `<div class="bar"><i style="width:${Math.round(j.progress * 100)}%"></i></div><b class="small">${Math.round(j.progress * 100)}%</b>
      <button class="btn xs danger" onclick="action('cancel')">Annuler</button>` : `<button class="btn xs ghost" onclick="_dismissedJobs.add('${esc(j.id)}');this.closest('.jobbar').remove()">✕</button>`}
  </div>`;
}

async function pollProject() {
  clearTimeout(S.pollT);
  const p = S.project;
  if (!p || !location.hash.startsWith('#/project/' + p.id)) return;
  const was = jobRunning();
  S.pollT = setTimeout(async () => {
    let np;
    try { np = await api('GET', '/projects/' + p.id); } catch (e) { return pollProject(); }
    if (!location.hash.startsWith('#/project/' + p.id)) return;
    const prevUpdated = S.project.updated;
    S.project = np;
    const now = jobRunning();
    renderJobBar();
    if (was && !now) {                                  // job terminé → rafraîchissement complet
      if (np.job && np.job.status === 'done') toast((JOB_LABEL[np.job.kind] || 'Tâche') + ' terminé(e) ✔', 'ok');
      if (np.job && np.job.status === 'error') toast(np.job.error, 'err');
      renderProject();
    } else if (now && prevUpdated !== np.updated) liveUpdate();
    pollProject();
  }, was ? 1500 : 6000);
}
function liveUpdate() {
  const p = S.project;
  if (S.step === 'script' && p.job && ['script', 'rewrite', 'autopilot'].includes(p.job.kind)) {
    const ta = $('#scriptEd'); if (ta && p.script_draft) { ta.value = p.script_draft; ta.scrollTop = ta.scrollHeight; }
  }
  if (S.step === 'storyboard') { renderCast(); renderScenes(); }
}
async function action(name, body = {}) {
  const p = S.project;
  if (name === 'cancel') { await guard(() => api('POST', `/projects/${p.id}/cancel`, {})); return; }
  const r = await guard(() => api('POST', `/projects/${p.id}/${name}`, body));
  if (!r) return;
  S.project.job = r.job;
  renderProject();
  pollProject();
}
const savePatch = async patch => {
  const r = await guard(() => api('PUT', '/projects/' + S.project.id, patch));
  if (r) { const job = S.project.job; S.project = r; S.project.job = r.job || job; }
  return r;
};

// ── Étape 1 : Script ────────────────────────────────────────────────────────
const VERDICT_LABEL = {PASS: 'PASS', 'FIX-THEN-PASS': 'FIX-THEN-PASS', HOLD: 'HOLD', ERROR: 'audit interrompu'};
function fosCard(rv) {
  const b = rv.block || {}, rounds = rv.rounds || [], cls = rv.verdict === 'PASS' ? 'ok' : (rv.verdict === 'HOLD' || rv.verdict === 'ERROR' ? 'err' : 'warn');
  const line = (k, v) => v ? `<div class="fosl"><b>${k}</b> ${esc(typeof v === 'string' ? v : JSON.stringify(v))}</div>` : '';
  const a = b.A || {}, d = b.D || {}, d7 = b.D7 || {}, e = b.E || {};
  return `<div class="card"><div class="row between"><div><h3>Audit FacelessOS</h3><div class="tiny faint">${rounds.length} passe(s) greenlight · ${rounds.reduce((n, r) => n + (r.fixes || []).length, 0)} fix(es) appliqué(s)</div></div><span class="pill ${cls}">${esc(VERDICT_LABEL[rv.verdict] || rv.verdict)}</span></div>
    <div class="stack" style="margin-top:8px;gap:6px">
      ${rounds.map(r => `<details class="issue"><summary><b>Passe ${r.round} : ${esc(r.verdict)}</b> <span class="faint">· ${(r.fixes || []).length} fix(es)${r.words ? ' · ' + r.words + ' mots' : ''}</span></summary>
        ${r.hold_reason ? `<div class="muted" style="margin-top:6px">HOLD : ${esc(r.hold_reason)}</div>` : ''}
        ${(r.fixes || []).map(f => `<div class="muted" style="margin-top:6px"><b>${esc(f.check || '')}</b> ${f.quote ? '« ' + esc(f.quote) + ' » ' : ''}— ${esc(f.problem || '')}<br>→ ${esc(f.fix || '')}</div>`).join('')}
        ${r.error ? `<div class="muted">${esc(r.error)}</div>` : ''}</details>`).join('')}
      <details class="issue"><summary><b>Bloc verdict (dernière passe)</b></summary><div style="margin-top:6px">
        ${line('A Hook', a.sentence_one ? `« ${a.sentence_one} » · ${a.hook_words || '?'} mots · turn : ${a.turn || '?'} · A4 : ${a.a4 || '?'}` : '')}
        ${line('B Boucles', (b.B || {}).loop_ledger ? (b.B.loop_ledger || []).join(' / ') : '')}
        ${line('Promesse', b.promise_map)}
        ${line('D Voix', d.anchor ? `${d.anchor} · ${(d.shapes_quoted || []).map(x => '« ' + x + ' »').join(' ')} · ${d.matched_line || ''}` : '')}
        ${line('D5 Faits', (b.D5 || []).join(' / '))}
        ${line('D7', d7.result)}
        ${line('E Authenticité', e.score ? `${e.score} · ${e.missing || ''}` : '')}
      </div></details>
      ${rv.brief ? `<details class="issue"><summary><b>Brief (research)</b></summary><div class="muted" style="margin-top:6px"><b>Angle :</b> ${esc(rv.brief.angle || '')}<br>${(rv.brief.proof_bank || []).map(x => '→ ' + esc(x.item || x) + (x.basis ? ` <span class="faint">(${esc(x.basis)})</span>` : '')).join('<br>')}</div></details>` : ''}
      ${rv.hooks && (rv.hooks.options || []).length ? `<details class="issue"><summary><b>Hooks proposés</b> <span class="faint">· retenu : n°${(rv.hooks.winner || 0) + 1}</span></summary>${rv.hooks.options.map((o, i) => `<div class="muted" style="margin-top:6px"><b>${i + 1}. ${esc(o.move || '')}</b>${i === rv.hooks.winner ? ' ✓' : ''}<br>${esc(o.text)}</div>`).join('')}${rv.hooks.why ? `<div class="faint tiny" style="margin-top:6px">${esc(rv.hooks.why)}</div>` : ''}</details>` : ''}
    </div></div>`;
}

function stepScript() {
  const p = S.project, ch = chById(p.channel_id) || {};
  const wpm = ch.wpm || 150, target = Math.round(p.minutes * wpm);
  const running = jobRunning() && ['script', 'rewrite', 'audit', 'autopilot'].includes(p.job.kind);
  const rv = p.review;
  $('#stepBody').innerHTML = `
    <div class="split">
      <div class="stack">
        <div class="card" style="padding:14px">
          <div class="row between" style="margin-bottom:10px">
            <div class="counter"><span><b id="wc">${p.words_count}</b> / ${target} mots</span><span>≈ <b id="estDur">${fmtDur(p.words_count / wpm * 60)}</b> de voix</span><span id="saveState" class="faint"></span></div>
            <div class="row">
              <button class="btn sm" id="auditBtn" title="Greenlight FacelessOS en boucle sur le script actuel (après une retouche ou un script collé)">🛡 Audit FacelessOS</button>
              <button class="btn sm" id="genScript">${(p.script || '').trim() ? '↻ Régénérer' : '✨ Écrire le script'}</button>
            </div>
          </div>
          <textarea id="scriptEd" class="script-ed" spellcheck="false" ${running ? 'readonly' : ''} placeholder="Clique « Écrire le script » : l'IA fait le plan, écrit chaque section puis relit tout. Tu peux aussi coller ton propre script. Les lignes « ## Titre » = titres de section à l'écran (non lus).">${esc(running ? (p.script_draft || '') : (p.script || ''))}</textarea>
          <div class="gauge"><i id="gauge" style="width:${Math.min(100, p.words_count / Math.max(1, target) * 100)}%"></i></div>
        </div>
        <div class="card"><h3>Réécrire avec une consigne</h3><div class="sub">Ex : « hook plus choc », « raccourcis le niveau 3 », « ton plus sombre », « ajoute des chiffres ».</div>
          <div class="row nowrap"><input type="text" id="rwIn" placeholder="Ta consigne…"><button class="btn" id="rwBtn">Réécrire</button></div></div>
      </div>
      <div class="side">
        <div class="card"><h3>Paramètres</h3>
          <div class="stack" style="margin-top:10px">
            <label class="f"><span class="lbl">Durée cible <b id="minOut">${p.minutes} min</b></span><input type="range" id="minIn" min="1" max="40" step="0.5" value="${p.minutes}"></label>
            <label class="f"><span class="lbl">Consignes</span><textarea id="notesIn" rows="3" placeholder="Angle, faits, public…">${esc(p.notes || '')}</textarea></label>
            <div class="hint">Format : <b>${esc((S.cfg.formats[ch.format] || {}).name || ch.format || '?')}</b> · débit voix ${wpm} mots/min (calibré automatiquement).</div>
          </div></div>
        ${!(ch.reference_scripts || '').trim() ? `<div class="card warnbox"><b>Pas de vidéo de référence pour ce format.</b><div class="tiny" style="margin-top:4px">Le script suivra juste le ton de la chaîne. Ajoute une vidéo populaire de la niche dans <a href="#/channel/${ch.id}">Chaîne → Vidéo de référence</a>.</div></div>` : ''}
        ${rv && rv.engine === 'facelessos' ? fosCard(rv) : ''}
        ${rv && rv.engine !== 'facelessos' && (rv.score || (rv.issues || []).length) ? `<div class="card"><div class="row between"><div><h3>Relecture IA</h3><div class="tiny faint">note du 1er jet · ${(rv.issues || []).length} point(s) corrigé(s)</div></div>${rv.score ? `<span class="score">${esc(rv.score)}<span class="small muted">/10</span></span>` : ''}</div>
          <div class="stack" style="margin-top:8px;gap:8px">${(rv.issues || []).map(i => `<details class="issue"><summary><b>${esc(i.problem)}</b></summary><div class="muted" style="margin-top:6px">→ corrigé : ${esc(i.fix)}</div></details>`).join('') || '<div class="hint">Aucun problème majeur.</div>'}</div></div>` : ''}
        ${(p.script_history || []).length ? `<div class="card"><h3>Historique</h3><div style="margin-top:6px">${p.script_history.slice().reverse().map((h, ri) => {
          const i = p.script_history.length - 1 - ri;
          return `<div class="hist-item"><span>${esc(h.label)}<br><span class="faint tiny">${ago(h.at)}</span></span><button class="btn xs" data-restore="${i}">Restaurer</button></div>`; }).join('')}</div></div>` : ''}
        <button class="btn primary big" id="toVoice" ${(p.script || '').trim() ? '' : 'disabled'}>Suivant : voix off →</button>
      </div>
    </div>`;
  const ta = $('#scriptEd');
  const count = () => {
    const words = ta.value.split('\n').filter(l => !l.trim().startsWith('#')).join(' ').split(/\s+/).filter(Boolean).length;
    $('#wc').textContent = words; $('#estDur').textContent = fmtDur(words / wpm * 60);
    gaugeColor(words);
  };
  const gaugeColor = w => { const r = w / Math.max(1, target), g = $('#gauge'); g.style.width = Math.min(100, r * 100) + '%'; g.style.background = r > 1.15 || r < 0.6 ? 'var(--s-warn)' : 'var(--s-ok)'; };
  gaugeColor(p.words_count);
  const autosave = debounce(async () => { $('#saveState').textContent = 'Enregistrement…'; const r = await savePatch({script: ta.value}); $('#saveState').textContent = r ? '✓ enregistré' : ''; }, 1200);
  ta.oninput = () => { count(); $('#saveState').textContent = '…'; autosave(); };
  $('#genScript').disabled = running;
  $('#genScript').onclick = async () => {
    if ((p.script || '').trim() && !confirm('Régénérer tout le script ? (l\'actuel reste dans l\'historique)')) return;
    await savePatch({minutes: Number($('#minIn').value), notes: $('#notesIn').value});
    action('script', {});
  };
  $('#auditBtn').disabled = running || !(p.script || '').trim();
  $('#auditBtn').onclick = () => action('audit', {rounds: 2});
  $('#rwBtn').disabled = running || !(p.script || '').trim();
  $('#rwBtn').onclick = () => { const v = $('#rwIn').value.trim(); if (v) action('rewrite', {instruction: v}); };
  $('#minIn').oninput = e => $('#minOut').textContent = e.target.value + ' min';
  $('#minIn').onchange = e => savePatch({minutes: Number(e.target.value)});
  $('#notesIn').onchange = e => savePatch({notes: e.target.value});
  $$('[data-restore]').forEach(b => b.onclick = async () => { if (confirm('Restaurer cette version ?')) { await savePatch({restore: Number(b.dataset.restore)}); renderProject(); } });
  $('#toVoice').onclick = () => { S.step = 'voice'; history.replaceState(null, '', `#/project/${p.id}/voice`); renderProject(); };
}

// ── Formulaire voix (partagé chaîne / projet) ───────────────────────────────
function voiceForm(v, lang, onChange) {
  const box = document.createElement('div');
  box.className = 'stack';
  const st = S.cfg.tts;
  box.innerHTML = `
    <label class="f"><span class="lbl">Fournisseur</span><div class="seg" data-k="provider">
      <button data-v="edge">Edge (gratuit)</button>
      <button data-v="elevenlabs" ${st.elevenlabs ? '' : 'disabled title="ELEVENLABS_API_KEY absente du .env"'}>ElevenLabs</button>
      <button data-v="openai" ${st.openai ? '' : 'disabled title="OPENAI_TTS_KEY absente du .env"'}>OpenAI</button>
      <button data-v="algrow" ${st.algrow ? '' : 'disabled title="ALGROW_API_KEY absente du .env"'}>Algrow · ElevenLabs</button>
      <button data-v="algrow_stealth" ${st.algrow_stealth ? '' : 'disabled title="ALGROW_API_KEY absente du .env"'}>Algrow · Stealth</button></div></label>
    <div class="hint hidden" data-el="credits"></div>
    <label class="f"><span class="lbl">Voix <a href="#" class="small" data-act="all">toutes les langues</a></span><select data-k="voice"></select>
      <input type="text" data-k="voice_custom" placeholder="ID de voix ElevenLabs" class="hidden"></label>
    <label class="f"><span class="lbl">Vitesse <b data-out="speed"></b></span><input type="range" min="0.8" max="1.3" step="0.02" data-k="speed"></label>
    <label class="f hidden" data-only="openai"><span class="lbl">Direction de jeu (OpenAI)</span><input type="text" data-k="instructions" placeholder="Calm, deep documentary narrator"></label>
    <div class="row"><button class="btn sm" data-act="preview">▶ Écouter</button><audio data-el="audio" class="hidden" controls></audio></div>`;
  const q = s => $(s, box);
  let allLangs = false;
  const setSeg = () => $$('[data-k=provider] button', box).forEach(b => b.classList.toggle('on', b.dataset.v === v.provider));
  const loadVoices = async () => {
    const sel = q('[data-k=voice]'), custom = q('[data-k=voice_custom]');
    $$('[data-only]', box).forEach(x => x.classList.toggle('hidden', x.dataset.only !== v.provider));
    if (v.provider === 'elevenlabs') { sel.classList.add('hidden'); custom.classList.remove('hidden'); custom.value = v.voice || ''; return; }
    sel.classList.remove('hidden'); custom.classList.add('hidden');
    sel.innerHTML = '<option>Chargement…</option>';
    const algrow = v.provider.startsWith('algrow');
    const cr = q('[data-el=credits]'); cr.classList.toggle('hidden', !algrow);
    if (algrow) api('GET', '/algrow/credits').then(c => { cr.textContent = `Crédits Algrow : ${Number(c.elevenlabs || 0).toLocaleString('fr-FR')} caractères ElevenLabs · ${Number(c.stealth || 0).toLocaleString('fr-FR')} Stealth. « Écouter » joue l'extrait officiel de la voix (gratuit).`; }).catch(() => {});
    const r = await guard(() => api('GET', `/voices?provider=${v.provider}&lang=${allLangs ? '' : lang}&current=${encodeURIComponent(v.voice || '')}`));
    const list = r ? r.voices : [];
    S.voiceList = list;
    const featured = new Set((S.cfg.edge_featured || {})[lang] || []);
    const opts = list.map(x => `<option value="${esc(x.id)}">${featured.has(x.id) ? '★ ' : ''}${esc(algrow ? (x.name || x.id) : x.id)}${x.gender ? ' · ' + x.gender : ''}${x.accent ? ' · ' + x.accent : ''}</option>`);
    if (v.voice && !list.some(x => x.id === v.voice)) opts.unshift(`<option value="${esc(v.voice)}">${esc(v.voice)} (choisie)</option>`);
    sel.innerHTML = opts.join('');
    if (v.voice) sel.value = v.voice;
    else if (list.length) { v.voice = sel.value; onChange(v); }
  };
  setSeg();
  q('[data-k=speed]').value = v.speed || 1; q('[data-out=speed]').textContent = (v.speed || 1).toFixed(2) + '×';
  q('[data-k=instructions]').value = v.instructions || '';
  q('[data-k=provider]').onclick = e => { const b = e.target.closest('button'); if (!b || b.disabled) return; v.provider = b.dataset.v; v.voice = ''; setSeg(); loadVoices(); onChange(v); };
  q('[data-k=voice]').onchange = e => { v.voice = e.target.value; onChange(v); };
  q('[data-k=voice_custom]').onchange = e => { v.voice = e.target.value.trim(); onChange(v); };
  q('[data-k=speed]').oninput = e => { v.speed = Number(e.target.value); q('[data-out=speed]').textContent = v.speed.toFixed(2) + '×'; };
  q('[data-k=speed]').onchange = () => onChange(v);
  q('[data-k=instructions]').onchange = e => { v.instructions = e.target.value; onChange(v); };
  q('[data-act=all]').onclick = e => { e.preventDefault(); allLangs = !allLangs; e.target.textContent = allLangs ? 'langue de la chaîne' : 'toutes les langues'; loadVoices(); };
  q('[data-act=preview]').onclick = async e => {
    if (v.provider.startsWith('algrow')) {  // extrait officiel : ne consomme aucun crédit
      const x = (S.voiceList || []).find(y => y.id === v.voice);
      if (!x || !x.preview_url) return toast('Pas d\'extrait disponible pour cette voix.', 'err');
      const a = q('[data-el=audio]'); a.src = x.preview_url; a.classList.remove('hidden'); a.play(); return;
    }
    busy(e.target, true, '');
    const sample = lang === 'fr' ? 'Niveau un. Tu as dix-huit ans, et personne ne t\'a prévenu de ce qui t\'attend.' : 'Level one. You are eighteen years old, and nobody warned you about what comes next.';
    const blob = await guard(() => api('POST', '/voices/preview', {...v, text: sample}));
    busy(e.target, false);
    if (blob) { const a = q('[data-el=audio]'); a.src = URL.createObjectURL(blob); a.classList.remove('hidden'); a.play(); }
  };
  loadVoices();
  return box;
}

// ── Étape 2 : Voix ──────────────────────────────────────────────────────────
function stepVoice() {
  const p = S.project, ch = chById(p.channel_id) || {};
  const vs = clone(p.voice_settings || {provider: 'edge'});
  const pause = Number((p.montage || {}).pause_max || 0);
  $('#stepBody').innerHTML = `
    <div class="split">
      <div class="stack">
        <div class="card pad-lg">
          <h2>Voix off</h2><div class="sub">Voix Edge gratuites (FR/EN/…, timings mot à mot), ElevenLabs ou OpenAI si tu mets une clé dans le .env.</div>
          ${p.voice ? `<audio controls src="${fileUrl(p.id, p.voice.file, p.voice.v)}"></audio>
            <div class="row small muted" style="margin-top:8px"><span>Durée <b>${fmtDur(p.voice.duration)}</b></span>·<span>${p.voice.words} mots synchronisés</span>
            ${p.voice_outdated ? '<span class="pill warn">script ou réglages modifiés → régénère la voix</span>' : '<span class="pill ok">à jour</span>'}</div>`
            : `<div class="empty" style="padding:30px">Pas encore de voix off.</div>`}
          <div class="row" style="margin-top:14px"><button class="btn primary" id="genVoice" ${(p.script || '').trim() ? '' : 'disabled'}>${p.voice ? '↻ Régénérer la voix' : '🎙 Générer la voix off'}</button></div>
        </div>
        <div class="card"><h3>Silences</h3><div class="sub">Raccourcit les pauses trop longues entre les phrases (plus de rythme = meilleure rétention).</div>
          <div class="seg" id="pauseSeg">${[[0, 'Off'], [0.75, 'Doux 0,75 s'], [0.45, 'Naturel 0,45 s'], [0.3, 'Nerveux 0,3 s']].map(([x, l]) => `<button data-v="${x}" class="${Math.abs(x - pause) < 0.01 ? 'on' : ''}">${l}</button>`).join('')}</div></div>
      </div>
      <div class="side"><div class="card"><h3>Réglages de voix</h3><div id="vform" style="margin-top:10px"></div></div>
        <button class="btn primary big" id="toSb" ${p.voice ? '' : 'disabled'}>Suivant : storyboard →</button></div>
    </div>`;
  $('#vform').appendChild(voiceForm(vs, ch.language || 'fr', v => savePatch({voice_settings: v})));
  $('#genVoice').disabled = jobRunning() || !(p.script || '').trim();
  $('#genVoice').onclick = () => {
    if (p.scenes.some(s => s.image) && !confirm('Les scènes seront recalées sur la nouvelle voix (les images des phrases inchangées sont conservées). Continuer ?')) return;
    action('voice');
  };
  $('#pauseSeg').onclick = async e => { const b = e.target.closest('button'); if (!b) return; $$('#pauseSeg button').forEach(x => x.classList.toggle('on', x === b)); await savePatch({montage: {pause_max: Number(b.dataset.v)}}); };
  $('#toSb').onclick = () => { S.step = 'storyboard'; history.replaceState(null, '', `#/project/${p.id}/storyboard`); renderProject(); };
}

// ── Étape 3 : Storyboard ────────────────────────────────────────────────────
function stepStoryboard() {
  const p = S.project, m = p.montage || {};
  const nImg = p.scenes.filter(s => s.image).length, nErr = p.scenes.filter(s => s.status === 'error').length;
  $('#stepBody').innerHTML = `<div id="castPanel"></div>` + (!p.voice ? `<div class="empty"><h2>Génère d'abord la voix off</h2><p>Les scènes sont découpées sur la voix : chaque image tombe pile sur sa phrase.</p>
      <button class="btn primary" onclick="S.step='voice';renderProject()">Aller à la voix off</button></div>` : `
    <div class="toolbar">
      <div class="row"><span class="small muted">Rythme</span>
        <div class="seg" id="paceSeg">${[[2.2, 'Rapide ~2 s'], [3.5, 'Dynamique ~3,5 s'], [5, 'Moyen ~5 s'], [7, 'Lent ~7 s']].map(([x, l]) => `<button data-v="${x}" class="${Math.abs(x - (m.pacing || 5)) < 0.3 ? 'on' : ''}">${l}</button>`).join('')}</div>
        <label class="check small" title="Images plus rapides pendant les ${m.hook_seconds || 30} premières secondes (le hook)"><input type="checkbox" id="hookFast" ${(m.hook_pacing || 0) < (m.pacing || 5) ? 'checked' : ''}> hook plus rapide</label>
        <button class="btn sm" id="replan" title="Redécoupe les scènes avec ce rythme (garde les images des phrases identiques)">Appliquer</button></div>
      <div class="grow"></div>
      <span class="small muted"><b>${nImg}</b>/${p.scenes.length} images${nErr ? ` · <span style="color:var(--s-err)">${nErr} échec(s)</span>` : ''}</span>
      ${nImg === 0 ? `<button class="btn" id="testImg" title="Génère seulement la 1re image pour valider le style avant de lancer tout le lot">🧪 Tester le style (1 image)</button>` : ''}
      ${nErr ? `<button class="btn" id="retryErr">↻ Relancer les échecs</button>` : ''}
      <button class="btn primary" id="genAll" ${nImg === p.scenes.length ? 'disabled' : ''}>🎨 Générer ${nImg ? 'les images manquantes' : 'toutes les images'}</button>
    </div>
    <div class="sgrid" id="sgrid"></div>
    ${nImg === p.scenes.length && p.scenes.length ? `<div class="savebar"><span class="muted small" style="margin-right:auto;align-self:center">Toutes les images sont prêtes.</span><button class="btn primary big" onclick="S.step='export';renderProject()">Suivant : montage →</button></div>` : ''}`);
  renderCast(true);
  if (!p.voice) return;
  renderScenes(true);
  const dis = jobRunning();
  $$('#testImg,#retryErr,#genAll,#replan').forEach(b => b && (b.disabled = b.disabled || dis));
  $('#paceSeg').onclick = e => { const b = e.target.closest('button'); if (b) $$('#paceSeg button').forEach(x => x.classList.toggle('on', x === b)); };
  $('#replan').onclick = async () => {
    const pace = Number(($('#paceSeg button.on') || {}).dataset?.v || m.pacing || 5);
    const hookFast = $('#hookFast').checked;
    await savePatch({montage: {pacing: pace, hook_pacing: hookFast ? Math.max(1.8, Math.round(pace * 0.6 * 10) / 10) : pace}});
    action('replan');
  };
  if ($('#testImg')) $('#testImg').onclick = () => action('images', {first_only: true});
  if ($('#retryErr')) $('#retryErr').onclick = () => action('images', {only: p.scenes.filter(s => s.status === 'error').map(s => s.i)});
  $('#genAll').onclick = () => action('images', {});
}
// ── Personnages de la vidéo (casting consistant, façon TubeGen) ─────────────
const castSig = p => JSON.stringify([p.cast, (p.job || {}).status === 'running' && (p.job || {}).kind]);
function castCard(p, c) {
  const busy = jobRunning() && ['cast', 'images', 'autopilot'].includes(p.job.kind) && !c.image;
  return `<div class="castc" data-cid="${c.id}">
    <div class="castimg">${c.image ? `<img src="${fileUrl(p.id, c.image)}" data-cview="${c.id}">` : `<div class="refbox">${busy ? '<span class="spin"></span>' : 'Pas d\'image'}</div>`}</div>
    <div class="stack" style="gap:6px;min-width:0">
      <input type="text" data-cf="name" value="${esc(c.name)}" placeholder="Nom (ex : Her, Her Father)">
      <input type="text" data-cf="aliases" value="${esc((c.aliases || []).join(', '))}" placeholder="Appelé aussi… (your wife, Ji-woo)">
      <textarea rows="3" data-cf="description" placeholder="Look fixe : cheveux, tenue et couleurs, âge, accessoire">${esc(c.description || '')}</textarea>
      <div class="row" style="gap:6px"><button class="btn xs" data-cregen="${c.id}" title="Régénérer l'image de référence depuis la description">↻ Image</button>
        <label class="btn xs">⬆ Importer<input type="file" accept="image/*" data-cup="${c.id}" hidden></label>
        <button class="btn xs danger" data-cdel="${c.id}">✕</button></div></div></div>`;
}
function renderCast(force) {
  const p = S.project, box = $('#castPanel');
  if (!box) return;
  const sig = castSig(p);
  if (!force && box.dataset.sig === sig) return;
  if (!force && box.contains(document.activeElement)) return;  // pas d'écrasement pendant la saisie
  box.dataset.sig = sig;
  const cast = p.cast || [];
  const own = new Set(cast.map(c => c.name.trim().toLowerCase()));
  const chan = (p.channel_cast || []).filter(c => !own.has(c.name.trim().toLowerCase()));
  const dis = jobRunning() ? 'disabled' : '';
  box.innerHTML = `<div class="card castpanel"><div class="row" style="margin-bottom:10px">
      <h3 style="margin:0">👥 Personnages de la vidéo</h3>
      <span class="hint">Chaque perso a une image de référence envoyée à chaque scène où il apparaît : même look du début à la fin.</span>
      <div class="grow"></div>
      <button class="btn sm" id="castDetect" ${dis} ${(p.script || '').trim() ? '' : 'disabled'}>🔍 ${p.cast ? 'Re-détecter' : 'Détecter'} depuis le script</button>
      ${cast.some(c => !c.image) ? `<button class="btn sm" id="castGen" ${dis}>✨ Images manquantes</button>` : ''}
      <button class="btn sm" id="castAdd">＋ Ajouter</button></div>
    ${chan.length ? `<div class="row small muted" style="margin-bottom:8px;gap:8px">Persos de la chaîne : ${chan.map(c => `<span class="pill" title="${esc(c.description)}">${c.image ? `<img src="${chFileUrl(p.channel_id, c.image)}" style="width:18px;height:18px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:4px">` : ''}${esc(c.name)}</span>`).join('')}</div>` : ''}
    ${p.cast == null ? '<div class="hint">Pas encore de casting : il sera détecté automatiquement au lancement des images (ou clique « Détecter »).</div>'
      : `<div class="castgrid">${cast.map(c => castCard(p, c)).join('') || '<div class="hint">Aucun personnage : les scènes n\'auront que les persos de la chaîne.</div>'}</div>`}</div>`;
  const collect = () => $$('.castc', box).map(el => {
    const c = (p.cast || []).find(x => x.id === el.dataset.cid) || {id: el.dataset.cid};
    return {id: c.id, role: c.role || '', name: $('[data-cf=name]', el).value, description: $('[data-cf=description]', el).value,
      aliases: $('[data-cf=aliases]', el).value.split(',').map(x => x.trim()).filter(Boolean)};
  });
  const saveCast = async list => { const r = await savePatch({cast: list}); if (r) renderCast(true); };
  const autosave = debounce(() => savePatch({cast: collect()}), 900);
  box.oninput = e => { if (e.target.dataset.cf) autosave(); };
  if ($('#castDetect', box)) $('#castDetect', box).onclick = () => {
    if (!p.cast || !p.cast.length || confirm('Re-détecter les persos depuis le script ? (les images des persos au même nom sont gardées)')) action('cast', {redetect: true});
  };
  if ($('#castGen', box)) $('#castGen', box).onclick = () => action('cast', {});
  $('#castAdd', box).onclick = () => saveCast([...collect(), {id: null, name: 'Nouveau perso', aliases: [], description: ''}]);
  box.onclick = async e => {
    const t = e.target;
    if (t.dataset.cregen) { await savePatch({cast: collect()}); action('cast', {only: [t.dataset.cregen]}); }
    if (t.dataset.cdel && confirm('Retirer ce personnage de la vidéo ?')) saveCast(collect().filter(c => c.id !== t.dataset.cdel));
    if (t.dataset.cview) window.open(t.src, '_blank');
  };
  box.onchange = async e => {
    const t = e.target; if (!t.dataset.cup) return;
    await savePatch({cast: collect()});
    const fd = new FormData(); fd.append('file', t.files[0]);
    const r = await guard(() => api('POST', `/projects/${p.id}/cast/${t.dataset.cup}/upload`, fd), 'Image du perso importée');
    if (r) { const job = S.project.job; S.project = r; S.project.job = job; renderCast(true); }
  };
}
function castNames(p) {
  const names = (p.cast || []).map(c => c.name);
  for (const c of p.channel_cast || []) if (!names.some(n => n.toLowerCase() === c.name.toLowerCase())) names.push(c.name);
  return names;
}
const cardSig = s => JSON.stringify([s.image, s.status, s.prompt, s.start, s.end, s.error, s.motion || '', s.chars || []]);
function sceneCard(p, s) {
  const state = s.status === 'queued' || s.status === 'running' ? '<div class="state"><span class="spin"></span>génération…</div>'
    : s.status === 'error' ? '<div class="state" style="color:var(--s-err)">⚠ échec</div>' : (!s.image ? '<div class="state">en attente</div>' : '');
  return `<div class="scard ${s.status === 'error' ? 'err' : ''}" data-i="${s.i}" data-sig="${esc(cardSig(s))}">
    <div class="img" data-view="${s.i}">${s.image ? `<img src="${fileUrl(p.id, s.image)}" loading="lazy">` : ''}${state}
      <span class="num">#${s.i + 1}</span><span class="tm">${fmtTs(s.start)} · ${(s.end - s.start).toFixed(1)}s</span></div>
    <div class="body"><div class="txt">« ${esc(s.text)} »</div>
      <div class="prompt" data-edit="${s.i}" title="Cliquer pour éditer le prompt">🎨 ${esc(s.prompt || 'prompt généré automatiquement')}</div>
      ${(s.chars || []).length ? `<div class="chars" data-edit="${s.i}" title="Persos de la scène (cliquer pour modifier)">👥 ${s.chars.map(esc).join(' · ')}</div>` : ''}
      ${s.error ? `<div class="errtxt">${esc(s.error)}</div>` : ''}
      <div class="acts"><button class="btn xs" data-regen="${s.i}">↻ Refaire</button><button class="btn xs" data-edit="${s.i}">✎ Prompt</button>
        <label class="btn xs">⬆ Mon image<input type="file" accept="image/*" data-up="${s.i}" hidden></label>
        <select class="btn xs" data-motion="${s.i}" style="width:auto;padding:4px 6px" title="Mouvement de caméra">${motionOpts(s.motion)}</select></div>
    </div></div>`;
}
function renderScenes(force) {
  const p = S.project, grid = $('#sgrid');
  if (!grid) return;
  const layout = p.scenes.map(s => s.i + ':' + (s.first ? s.heading : '')).join('|');
  if (!force && grid.dataset.layout === layout) {         // mise à jour carte par carte
    for (const s of p.scenes) {
      const el = grid.querySelector(`.scard[data-i="${s.i}"]`);
      if (!el || S.editing.has(s.i) || el.dataset.sig === cardSig(s)) continue;
      el.outerHTML = sceneCard(p, s);
    }
    return;
  }
  grid.dataset.layout = layout;
  const html = [];
  for (const s of p.scenes) {
    if (s.first && s.heading) html.push(`<div class="sec-break">${esc(s.heading)}</div>`);
    html.push(sceneCard(p, s));
  }
  grid.innerHTML = html.join('') || '<div class="empty" style="grid-column:1/-1">Aucune scène.</div>';
  grid.onclick = e => {
    const t = e.target;
    if (t.closest('[data-view]')) return openViewer(Number(t.closest('[data-view]').dataset.view));
    if (t.dataset.regen) return action('regen', {i: Number(t.dataset.regen)});
    if (t.dataset.edit) return editPrompt(Number(t.dataset.edit));
  };
  grid.onchange = async e => {
    const t = e.target;
    if (t.dataset.up) {
      const fd = new FormData(); fd.append('file', t.files[0]);
      const r = await guard(() => api('POST', `/projects/${p.id}/scenes/${t.dataset.up}/upload`, fd), 'Image remplacée');
      if (r) { S.project = r; renderScenes(true); }
    }
    if (t.dataset.motion !== undefined) await savePatch({scenes: [{i: Number(t.dataset.motion), motion: t.value || null}]});
  };
}
function motionOpts(cur) {
  return [['', '🎥 auto'], ['none', 'fixe'], ['zoom_in', 'zoom +'], ['zoom_out', 'zoom −'], ['pan_right', 'pan →'], ['pan_left', 'pan ←'], ['pan_up', 'pan ↑'], ['pan_down', 'pan ↓']]
    .map(([v, l]) => `<option value="${v}" ${(cur || '') === v ? 'selected' : ''}>${l}</option>`).join('');
}
function editPrompt(i) {
  const card = $(`.scard[data-i="${i}"] .body`), s = S.project.scenes.find(x => x.i === i);
  if (!card || card.querySelector('textarea')) return;
  S.editing.add(i);
  const box = document.createElement('div');
  box.className = 'stack';
  const names = castNames(S.project), cur = new Set((s.chars || []).map(x => x.toLowerCase()));
  box.innerHTML = `<textarea>${esc(s.prompt || '')}</textarea>
    ${names.length ? `<div class="row small" style="gap:8px;flex-wrap:wrap">👥 ${names.map(n => `<label class="check small"><input type="checkbox" data-char="${esc(n)}" ${cur.has(n.toLowerCase()) ? 'checked' : ''}> ${esc(n)}</label>`).join('')}</div>` : ''}
    <div class="row"><button class="btn xs primary">Régénérer</button><button class="btn xs">Enregistrer</button><button class="btn xs ghost">Annuler</button></div>`;
  card.insertBefore(box, card.querySelector('.acts'));
  const [bGen, bSave, bCancel] = $$('.row button', box);
  const chars = () => $$('[data-char]', box).filter(x => x.checked).map(x => x.dataset.char);
  const done = () => { S.editing.delete(i); const el = $(`.scard[data-i="${i}"]`); if (el) el.outerHTML = sceneCard(S.project, S.project.scenes.find(x => x.i === i)); };
  bCancel.onclick = done;
  bSave.onclick = async () => { await savePatch({scenes: [{i, prompt: $('textarea', box).value, chars: chars()}]}); done(); };
  bGen.onclick = async () => { S.editing.delete(i); await savePatch({scenes: [{i, chars: chars()}]}); await action('regen', {i, prompt: $('textarea', box).value}); };
}

// Visionneuse plein écran (flèches ← →)
let _vi = 0;
function openViewer(i) {
  _vi = i;
  const el = document.createElement('div');
  el.className = 'viewer';
  el.innerHTML = `<button class="nav prev">‹</button><div class="vimg"><img></div><div class="vside card"></div><button class="nav next">›</button><button class="close">✕</button>`;
  document.body.appendChild(el);
  el.onclick = e => { if (e.target === el || e.target.classList.contains('close')) closeViewer(); };
  $('.prev', el).onclick = () => viewerNav(-1); $('.next', el).onclick = () => viewerNav(1);
  drawViewer();
}
function closeViewer() { const v = $('.viewer'); if (v) v.remove(); }
function viewerNav(d) { const n = S.project.scenes.length; _vi = (_vi + d + n) % n; drawViewer(); }
function drawViewer() {
  const v = $('.viewer'); if (!v) return;
  const p = S.project, s = p.scenes[_vi];
  $('.vimg img', v).src = s.image ? fileUrl(p.id, s.image) : '';
  $('.vside', v).innerHTML = `<div class="small muted">Scène <b>${_vi + 1}/${p.scenes.length}</b> · ${fmtTs(s.start)} → ${fmtTs(s.end)} (${(s.end - s.start).toFixed(1)} s)${s.heading ? ' · ' + esc(s.heading) : ''}</div>
    <p style="font-size:15px;line-height:1.55">« ${esc(s.text)} »</p>
    <label class="f"><span class="lbl">Prompt</span><textarea rows="7" id="vPrompt">${esc(s.prompt || '')}</textarea></label>
    <div class="row" style="margin-top:10px"><button class="btn sm primary" id="vRegen">↻ Régénérer</button><span class="hint">← → pour naviguer</span></div>`;
  $('#vRegen').onclick = async () => { const pr = $('#vPrompt').value; closeViewer(); await action('regen', {i: s.i, prompt: pr}); };
}

// ── Formulaire montage (partagé chaîne / projet) ────────────────────────────
function montageForm(m, onChange, opts = {}) {
  const c = m.captions = Object.assign({mode: 'karaoke', font: 'Poppins ExtraBold', size: 64, color: '#FFFFFF', highlight: '#FFD60A', outline: '#000000', position: 'bottom', uppercase: false}, m.captions || {});
  const box = document.createElement('div');
  box.className = 'stack';
  const music = opts.music || [];
  box.innerHTML = `
    <label class="f"><span class="lbl">Mise en page</span><select data-k="layout">
      <option value="full">Plein écran (l'image remplit la vidéo)</option>
      <option value="board">Tableau : fond quadrillé + panneau + prof en bas à gauche (16:9)</option></select></label>
    <div class="grid2">
      <label class="f"><span class="lbl">Mouvement de caméra</span><select data-k="motion">
        <option value="auto">Auto (zooms + pans variés)</option><option value="zoom_in">Zoom avant partout</option><option value="none">Aucun (images fixes)</option></select></label>
      <label class="f"><span class="lbl">Intensité <b data-out="ms"></b></span><input type="range" min="0.04" max="0.25" step="0.01" data-k="motion_strength"></label>
      <label class="f"><span class="lbl">Transition</span><select data-k="transition"><option value="fade">Fondu enchaîné</option><option value="cut">Coupe franche</option></select></label>
      <label class="f"><span class="lbl">Durée du fondu <b data-out="td"></b></span><input type="range" min="0.1" max="1" step="0.05" data-k="transition_dur"></label>
    </div>
    <label class="check"><input type="checkbox" data-k="section_titles"> Titres de section à l'écran (« Level 3 — … »)</label>
    <h3 style="margin-top:6px">Sous-titres</h3>
    <div class="seg" data-k="capmode"><button data-v="karaoke">Karaoké (mot surligné)</button><button data-v="phrase">Phrases</button><button data-v="none">Aucun</button></div>
    <div class="grid2" data-caps>
      <label class="f"><span class="lbl">Police</span><select data-c="font">${(S.cfg.fonts || []).map(f => `<option>${f}</option>`).join('')}</select></label>
      <label class="f"><span class="lbl">Taille <b data-out="sz"></b></span><input type="range" min="36" max="110" step="2" data-c="size"></label>
      <label class="f"><span class="lbl">Position</span><select data-c="position"><option value="bottom">Bas</option><option value="middle">Centre</option></select></label>
      <div class="row" style="align-items:flex-end;gap:14px">
        <label class="f"><span class="lbl">Texte</span><input type="color" data-c="color"></label>
        <label class="f"><span class="lbl">Surlignage</span><input type="color" data-c="highlight"></label>
        <label class="f"><span class="lbl">Contour</span><input type="color" data-c="outline"></label>
        <label class="check small"><input type="checkbox" data-c="uppercase"> MAJUSCULES</label></div>
    </div>
    <div class="preview-cap" data-el="capprev"></div>
    <h3 style="margin-top:6px">Musique de fond</h3>
    <div class="grid2">
      <label class="f"><span class="lbl">Piste (baissée automatiquement sous la voix)</span><select data-k="music"><option value="">— Aucune —</option><option value="auto" ${m.music === 'auto' ? 'selected' : ''}>🎲 Auto : une musique de la bibliothèque par vidéo</option>${music.map(x => `<option ${x === m.music ? 'selected' : ''}>${esc(x)}</option>`).join('')}</select></label>
      <label class="f"><span class="lbl">Volume <b data-out="mv"></b></span><input type="range" min="0.03" max="0.4" step="0.01" data-k="music_volume"></label>
    </div>
    <div class="row"><label class="btn sm">⬆ Ajouter une musique<input type="file" accept="audio/*" data-el="mup" hidden></label><span class="hint">Mets-y des morceaux sans droits (bibliothèque audio de YouTube Studio = zéro réclamation). Si la bibliothèque est vide, 3 ambiances lofi 100 % originales sont générées automatiquement.</span></div>
    <details class="adv"><summary>Avancé</summary><div class="grid3" style="margin-top:8px">
      <label class="f"><span class="lbl">Images/s</span><select data-k="fps"><option>24</option><option>25</option><option>30</option><option>60</option></select></label>
      <label class="f"><span class="lbl">Qualité</span><select data-k="quality"><option value="fast">Rapide</option><option value="high">Haute</option></select></label>
      <label class="f"><span class="lbl">Format</span><select data-k="aspect"><option value="16:9">16:9 (YouTube)</option><option value="9:16">9:16 (Shorts)</option></select></label>
      <label class="f"><span class="lbl">Durée min d'une scène (s)</span><input type="number" step="0.1" min="0.8" data-k="min_scene"></label>
      <label class="f"><span class="lbl">Durée max d'une scène (s)</span><input type="number" step="0.5" min="3" data-k="max_scene"></label>
      <label class="f"><span class="lbl">Durée du hook rapide (s)</span><input type="number" step="5" min="0" data-k="hook_seconds"></label>
    </div></details>`;
  const set = (k, val) => { const el = $(`[data-k="${k}"]`, box); if (el) { if (el.type === 'checkbox') el.checked = !!val; else el.value = val; } };
  if (!m.layout) m.layout = 'full';
  ['layout', 'motion', 'motion_strength', 'transition', 'transition_dur', 'section_titles', 'music_volume', 'fps', 'quality', 'aspect', 'min_scene', 'max_scene', 'hook_seconds'].forEach(k => set(k, m[k]));
  for (const k of ['font', 'size', 'position', 'color', 'highlight', 'outline', 'uppercase']) { const el = $(`[data-c="${k}"]`, box); if (el.type === 'checkbox') el.checked = !!c[k]; else el.value = c[k]; }
  const outs = () => {
    $('[data-out=ms]', box).textContent = Math.round(m.motion_strength * 100) + '%';
    $('[data-out=td]', box).textContent = Number(m.transition_dur).toFixed(2) + ' s';
    $('[data-out=mv]', box).textContent = Math.round(m.music_volume * 100) + '%';
    $('[data-out=sz]', box).textContent = c.size;
    $$('[data-k=capmode] button', box).forEach(b => b.classList.toggle('on', b.dataset.v === c.mode));
    $('[data-caps]', box).classList.toggle('hidden', c.mode === 'none');
    const pv = $('[data-el=capprev]', box);
    pv.classList.toggle('hidden', c.mode === 'none');
    const base = (opts.lang || 'fr') === 'fr' ? 'Tu as dix-huit ans' : 'You are eighteen now';
    const t = c.uppercase ? base.toUpperCase() : base;
    const w = t.split(' ');
    pv.style.fontFamily = /Bangers/.test(c.font) ? 'Impact, sans-serif' : '';
    pv.style.color = c.color; pv.style.webkitTextStrokeColor = c.outline;
    pv.innerHTML = c.mode === 'karaoke' ? w.map((x, i) => i === 1 ? `<span style="color:${c.highlight}">${x}</span>` : x).join(' ') : t;
  };
  outs();
  const fire = debounce(() => onChange(m), 500);
  box.addEventListener('input', e => {
    const k = e.target.dataset.k, ck = e.target.dataset.c;
    if (k) { const el = e.target; m[k] = el.type === 'checkbox' ? el.checked : (el.type === 'range' || el.type === 'number' || k === 'fps') ? Number(el.value) : el.value; }
    if (ck) { const el = e.target; c[ck] = el.type === 'checkbox' ? el.checked : el.type === 'range' ? Number(el.value) : el.value; }
    outs(); if (k || ck) fire();
  });
  $('[data-k=capmode]', box).onclick = e => { const b = e.target.closest('button'); if (!b) return; c.mode = b.dataset.v; outs(); fire(); };
  $('[data-el=mup]', box).onchange = async e => {
    const fd = new FormData(); fd.append('file', e.target.files[0]);
    const r = await guard(() => api('POST', '/music', fd), 'Musique ajoutée');
    if (r) { const sel = $('[data-k=music]', box); sel.innerHTML = '<option value="">— Aucune —</option><option value="auto">🎲 Auto : une musique de la bibliothèque par vidéo</option>' + r.music.map(x => `<option>${esc(x)}</option>`).join(''); sel.value = e.target.files[0].name; m.music = sel.value; fire(); }
  };
  return box;
}

// ── Étape 4 : Montage & export ──────────────────────────────────────────────
async function stepExport() {
  const p = S.project, m = clone(p.montage || {});
  const ready = p.voice && p.scenes.length && p.scenes.every(s => s.image);
  const r = p.render, pk = p.pack, meta = p.metadata;
  $('#stepBody').innerHTML = `
    <div class="split">
      <div class="stack">
        <div class="card pad-lg">
          <div class="row between"><div><h2>Vidéo finale</h2><div class="sub" style="margin:2px 0 0">Montage local ffmpeg : zooms/pans, fondus, sous-titres, titres, musique avec ducking, volume normalisé (-14 LUFS).</div></div>
            <button class="btn primary big" id="renderBtn" ${ready ? '' : 'disabled'}>🎬 ${r ? 'Ré-exporter' : 'Exporter la vidéo'}</button></div>
          ${!ready ? '<div class="hint" style="margin-top:10px">⚠ Il faut la voix off et toutes les images du storyboard.</div>' : ''}
          ${r ? `<video class="player" controls src="${fileUrl(p.id, r.file, r.v)}" style="margin-top:14px"></video>
            <div class="row" style="margin-top:10px"><a class="btn ok" href="${fileUrl(p.id, r.file, r.v)}&dl=1">⬇ Télécharger le MP4</a><span class="small muted">${fmtDur(r.duration)} · ${ago(r.at)}</span></div>` : ''}
        </div>
        <div class="card pad-lg">
          <div class="row between"><div><h2>Pack montage (CapCut / Premiere)</h2><div class="sub" style="margin:2px 0 0">Chaque image devient un clip MP4 qui dure <b>exactement</b> sa phrase. Glisse les clips dans l'ordre + la voix off → tout est calé.</div></div>
            <div class="row"><select id="packMotion" style="width:auto"><option value="none">Images fixes</option><option value="auto">Avec zoom/pan</option></select>
            <button class="btn" id="packBtn" ${ready ? '' : 'disabled'}>📦 Générer le pack</button></div></div>
          ${pk ? `<div class="row" style="margin-top:12px"><a class="btn ok" href="${fileUrl(p.id, pk.file, pk.v)}&dl=1">⬇ Télécharger le ZIP (${pk.clips} clips)</a><span class="small muted">${pk.motion === 'none' ? 'images fixes' : 'avec mouvement'} · ${ago(pk.at)}</span></div>
            <div class="hint" style="margin-top:8px">Contenu : clips/001.mp4…, voiceover.mp3, subtitles.srt, timestamps.txt, script.txt, images/, LISEZMOI.txt</div>` : ''}
        </div>
        <div class="card pad-lg">
          <div class="row between"><div><h2>Miniatures</h2><div class="sub" style="margin:2px 0 0">Dans le style de la chaîne, avec ton perso et 2-4 mots en gros — pensées pour le CTR.</div></div>
            <div class="row"><input type="text" id="thIdea" placeholder="Idée (optionnel)" style="width:200px"><button class="btn" id="thBtn" ${p.script ? '' : 'disabled'}>🖼 Générer 2 miniatures</button></div></div>
          ${(p.thumbnails || []).length ? `<div class="grid2" style="margin-top:14px">${p.thumbnails.map(t => `<div class="stack" style="gap:6px">
            <img class="refimg" src="${fileUrl(p.id, t.file)}" style="cursor:zoom-in" onclick="window.open(this.src)">
            <div class="row between"><span class="small muted">« ${esc(t.text)} »</span><a class="btn xs" href="${fileUrl(p.id, t.file)}?dl=1">⬇</a></div></div>`).join('')}</div>` : ''}
        </div>
        <div class="card pad-lg">
          <div class="row between"><div><h2>Publication</h2><div class="sub" style="margin:2px 0 0">Titres alternatifs, description SEO, tags et chapitres horodatés.</div></div>
            <button class="btn" id="metaBtn" ${p.script ? '' : 'disabled'}>✍ ${meta ? 'Régénérer' : 'Générer'}</button></div>
          ${meta ? metaHtml(meta) : ''}
        </div>
      </div>
      <div class="side"><div class="card"><h3>Réglages du montage</h3><div id="mform" style="margin-top:10px"></div></div></div>
    </div>`;
  const music = (await guard(() => api('GET', '/music'))) || {music: []};
  if (S.step !== 'export') return;
  $('#mform').appendChild(montageForm(m, v => savePatch({montage: v}), {music: music.music, lang: (chById(p.channel_id) || {}).language}));
  const dis = jobRunning();
  $('#renderBtn').disabled = !ready || dis; $('#packBtn').disabled = !ready || dis; $('#metaBtn').disabled = !p.script || dis;
  $('#renderBtn').onclick = () => action('render');
  $('#packBtn').onclick = () => action('pack', {motion: $('#packMotion').value});
  $('#metaBtn').onclick = () => action('metadata');
  $('#thBtn').disabled = !p.script || dis;
  $('#thBtn').onclick = () => action('thumbnails', {idea: $('#thIdea').value, count: 2});
  $$('[data-copy]').forEach(b => b.onclick = () => { navigator.clipboard.writeText($('#' + b.dataset.copy).value); toast('Copié', 'ok'); });
}
function metaHtml(meta) {
  const desc = (meta.description || '') + (meta.chapters && meta.chapters.length ? '\n\n' + meta.chapters.join('\n') : '');
  return `<div class="stack" style="margin-top:12px">
    <div><div class="small muted" style="margin-bottom:6px">Titres</div>${(meta.titles || []).map(t => `<div class="idea" onclick="navigator.clipboard.writeText(this.innerText);toast('Titre copié','ok')"><b>${esc(t)}</b></div>`).join('')}</div>
    <div class="copybox"><div class="small muted" style="margin-bottom:6px">Description (+ chapitres)</div><textarea id="metaDesc" rows="9">${esc(desc)}</textarea><button class="btn xs" data-copy="metaDesc" style="top:30px">Copier</button></div>
    <div class="copybox"><div class="small muted" style="margin-bottom:6px">Tags</div><textarea id="metaTags" rows="3">${esc((meta.tags || []).join(', '))}</textarea><button class="btn xs" data-copy="metaTags" style="top:30px">Copier</button></div>
  </div>`;
}

// ============================================================================
// CHAÎNES
// ============================================================================
async function viewChannels() {
  await loadChannels();
  $('#view').innerHTML = `
    <div class="hero"><div><h1>Tes chaînes</h1><p>Chaque chaîne garde son ADN : niche, format de script, bible de style, direction artistique, personnages, voix et montage.</p></div>
      <div class="row"><button class="btn big" onclick="nicheBendModal()">🧪 Niche bending</button><button class="btn primary big" onclick="newChannelModal()">＋ Nouvelle chaîne</button></div></div>
    ${S.channels.length ? `<div class="cgrid">${S.channels.map(c => `
      <div class="ccard" onclick="go('#/channel/${c.id}')">
        <div class="cimg">${c.style && c.style.ref ? `<img src="${chFileUrl(c.id, c.style.ref)}">` : ''}</div>
        <div class="cb"><div class="row between"><b style="font-size:15px">${esc(c.name)}</b><span class="pill">${esc((c.language || '').toUpperCase())}</span></div>
          <div class="small muted">${esc((S.cfg.formats[c.format] || {}).name || c.format)}</div>
          <div class="row">${c.bible ? '<span class="pill ok">bible ✓</span>' : '<span class="pill">pas de bible</span>'}
            ${c.style && c.style.ref ? '<span class="pill ok">style ✓</span>' : '<span class="pill warn">sans image de style</span>'}
            <span class="pill">${(c.style.characters || []).length} perso</span></div></div></div>`).join('')}</div>`
      : `<div class="empty"><h2>Aucune chaîne</h2><p>Pars d'un modèle inspiré des chaînes 2D qui percent en ce moment.</p><button class="btn primary" onclick="newChannelModal()">Créer ma première chaîne</button></div>`}`;
}
function newChannelModal() {
  const T = S.cfg.templates;
  const m = modal(`<h2>Nouvelle chaîne</h2><div class="sub">Modèles tirés de l'étude NexLev (chaînes 2D en forte croissance, sept. 2026). Tout est modifiable ensuite.</div>
    <div class="grid2">${Object.entries(T).map(([k, t]) => `<div class="tpl" data-t="${k}"><b>${esc(t.name)}</b><span>${esc(S.cfg.formats[t.format].name)} · ${t.language.toUpperCase()}</span><span>${esc(t.niche)}</span></div>`).join('')}
      <div class="tpl" data-t=""><b>Partir de zéro</b><span>Chaîne vierge, format POV par défaut.</span></div></div>
    <div class="foot"><button class="btn ghost" onclick="closeModal()">Annuler</button></div>`, 'wide');
  m.onclick = async e => {
    const t = e.target.closest('.tpl'); if (!t) return;
    const ch = await guard(() => api('POST', '/channels', {template: t.dataset.t || null}));
    if (ch) { closeModal(); go('#/channel/' + ch.id); }
  };
}

function nicheBendModal() {
  const m = modal(`<h2>🧪 Niche bending</h2><div class="sub">Garde ce qui marche (format, titres, rythme, style) et transpose-le sur une niche moins saturée ou mieux payée.</div>
    <div class="stack">
      <label class="f"><span class="lbl">Format / chaîne qui cartonne</span><textarea id="nbSrc" rows="3" placeholder="Ex : POVrank — « Your Life as Every Rank in North Korea's Army », 2e personne, 8-10 niveaux, cartoon vectoriel, 579K vues"></textarea></label>
      <div class="grid2"><label class="f"><span class="lbl">Domaine visé (optionnel)</span><input type="text" id="nbTgt" placeholder="finance, médecine, aviation… (vide = l'IA propose)"></label>
        <label class="f"><span class="lbl">Langue / marché</span><select id="nbLang">${S.cfg.languages.map(l => `<option value="${l}">${l.toUpperCase()}</option>`).join('')}</select></label></div>
      <div class="row"><button class="btn primary" id="nbGo">Trouver des niches</button></div>
      <div id="nbOut" class="stack"></div>
    </div>
    <div class="foot"><button class="btn ghost" onclick="closeModal()">Fermer</button></div>`, 'wide');
  const out = $('#nbOut', m);
  $('#nbGo', m).onclick = async e => {
    busy(e.target, true, 'Analyse…'); out.innerHTML = '';
    const r = await guard(() => api('POST', '/nichebend', {source: $('#nbSrc', m).value, target: $('#nbTgt', m).value, language: $('#nbLang', m).value}));
    busy(e.target, false);
    if (!r) return;
    out.innerHTML = r.concepts.map((c, i) => `<div class="card" style="padding:14px">
      <div class="row between"><div><b style="font-size:15px">${esc(c.name)}</b> <span class="pill ${c.rpm === 'high' ? 'ok' : c.rpm === 'low' ? '' : 'acc'}">RPM ${esc(c.rpm || '?')}</span>
        <span class="pill">${esc((S.cfg.formats[c.format] || {}).name || c.format)}</span></div>
        <button class="btn sm primary" data-nb="${i}">Créer cette chaîne</button></div>
      <div class="small" style="margin-top:6px">${esc(c.niche)}</div>
      <div class="small muted" style="margin-top:4px">${esc(c.why)}</div>
      <ul class="small" style="margin:8px 0 0;padding-left:18px">${(c.titles || []).map(t => `<li>${esc(t)}</li>`).join('')}</ul></div>`).join('');
    out.onclick = async ev => {
      const b = ev.target.closest('[data-nb]'); if (!b) return;
      const c = r.concepts[Number(b.dataset.nb)], st = S.cfg.styles[c.style] || S.cfg.styles.rank_vector;
      const ch = await guard(() => api('POST', '/channels', {name: c.name, language: $('#nbLang', m).value, format: c.format, niche: c.niche,
        audience: c.audience || '', tone: c.tone || '', rules: '', style: {preset: S.cfg.styles[c.style] ? c.style : 'rank_vector', prompt: st.prompt},
        voice: {voice: S.cfg.defaults.voice_by_lang[$('#nbLang', m).value] || ''}}), 'Chaîne créée');
      if (ch) { localStorage.setItem('pov2.ideas.' + ch.id, JSON.stringify(c.titles || [])); closeModal(); go('#/channel/' + ch.id); }
    };
  };
}

async function viewChannel(cid) {
  await loadChannels();
  const ch = await api('GET', '/channels/' + cid);
  const d = clone(ch);
  const F = S.cfg.formats, ST = S.cfg.styles;
  const bd = d.board = Object.assign({bg_color: '#08A8E6', line_color: '#7DEAFF', border_color: '#FFFFFF', panel_width: 0.85,
    presenter_height: 0.37, bob: true, mascot: '', presenter: null}, d.board || {});
  const music = (await guard(() => api('GET', '/music'))) || {music: []};
  $('#view').innerHTML = `
    <div class="phead"><div class="grow"><input class="title-in" id="chName" value="${esc(d.name)}" style="width:100%"><div class="small muted">Profil de chaîne · utilisé par toutes ses vidéos</div></div>
      <div class="row"><button class="btn" onclick="go('#/channels')">← Chaînes</button><button class="btn primary" onclick="newProjectModal({channel_id:'${cid}'})">＋ Vidéo pour cette chaîne</button><button class="btn danger sm" id="chDel">Supprimer</button></div></div>

    <div class="section-title"><span class="n">1</span><h2>Identité & format</h2></div>
    <div class="card"><div class="grid2">
      <label class="f"><span class="lbl">Langue des vidéos</span><select id="chLang">${S.cfg.languages.map(l => `<option value="${l}" ${l === d.language ? 'selected' : ''}>${l.toUpperCase()}</option>`).join('')}</select></label>
      <label class="f"><span class="lbl">Format de vidéo</span><select id="chFormat">${Object.entries(F).map(([k, f]) => `<option value="${k}" ${k === d.format ? 'selected' : ''}>${esc(f.name)}</option>`).join('')}</select></label>
      <label class="f"><span class="lbl">Niche / sujet</span><textarea id="chNiche" rows="2">${esc(d.niche)}</textarea></label>
      <label class="f"><span class="lbl">Audience</span><textarea id="chAud" rows="2">${esc(d.audience)}</textarea></label>
      <label class="f"><span class="lbl">Narrateur & ton</span><textarea id="chTone" rows="3">${esc(d.tone)}</textarea></label>
      <label class="f"><span class="lbl">Règles de la chaîne</span><textarea id="chRules" rows="3" placeholder="À faire / à éviter…">${esc(d.rules)}</textarea></label>
      <label class="f"><span class="lbl">Outro / call-to-action (optionnel)</span><input type="text" id="chCta" value="${esc(d.cta)}"></label>
      <div class="grid2"><label class="f"><span class="lbl">Durée par défaut (min)</span><input type="number" id="chMin" min="1" max="60" value="${d.default_minutes || 10}"></label>
        <label class="f"><span class="lbl">Débit voix (mots/min)</span><input type="number" id="chWpm" min="90" max="220" value="${d.wpm}"></label></div>
    </div><div class="hint" id="fmtDesc" style="margin-top:10px">${esc((F[d.format] || {}).desc || '')}</div></div>

    <div class="section-title"><span class="n">2</span><h2>Vidéo de référence du format</h2></div>
    <div class="card"><div class="sub">Colle le lien d'une vidéo populaire de la niche, du même format (idéalement 1 à 3 du même style) → transcription → analyse FacelessOS (hook, rythme, découpage, dialogues, fin). Chaque script suit cette analyse et s'ancre sur un extrait mot pour mot de la narration : le style est repris, jamais le contenu. Sans référence, le script reste juste dans le ton de la chaîne. Si YouTube bloque, colle la transcription à la main.</div>
      <div class="row nowrap"><input type="text" id="chUrls" placeholder="https://youtu.be/… https://youtube.com/watch?v=…" value="${esc(d.reference_urls || '')}"><button class="btn" id="chFetch">Récupérer</button></div>
      <div class="grid2" style="margin-top:12px">
        <label class="f"><span class="lbl">Scripts / transcriptions de référence <span class="faint" id="refWc"></span></span><textarea id="chRefs" rows="10">${esc(d.reference_scripts)}</textarea></label>
        <label class="f"><span class="lbl">Analyse de la référence (bible) <button class="btn xs" id="chBible">🧬 Analyser la référence</button></span><textarea id="chBibleTxt" rows="10" placeholder="Générée depuis la transcription, modifiable.">${esc(d.bible)}</textarea></label>
      </div></div>

    <div class="section-title"><span class="n">3</span><h2>Direction artistique</h2></div>
    <div class="card"><div class="grid2">
      <div class="stack">
        <label class="f"><span class="lbl">Style de départ</span><select id="stPreset"><option value="">— personnalisé —</option>${Object.entries(ST).map(([k, s]) => `<option value="${k}" ${k === d.style.preset ? 'selected' : ''}>${esc(s.name)}</option>`).join('')}</select></label>
        <label class="f"><span class="lbl">Prompt de style (ajouté à chaque image)</span><textarea id="stPrompt" rows="7">${esc(d.style.prompt)}</textarea></label>
        <div class="row"><label class="btn sm">📷 Décrire depuis des captures<input type="file" id="stShots" accept="image/*" multiple hidden></label><span class="hint">1 à 4 captures d'une chaîne → l'IA écrit le prompt.</span></div>
        <label class="check"><input type="checkbox" id="stNoText" ${d.style.no_text !== false ? 'checked' : ''}> Interdire le texte dans les images <span class="faint">(décoché = 1 étiquette courte par image : chiffres clés, concepts)</span></label>
        <label class="f"><span class="lbl">Consignes de mise en scène <span class="faint">(pour le directeur artistique IA)</span></span><textarea id="stDir" rows="4" placeholder="Ex : alterner scènes avec persos et schémas (flèches, graphiques)…">${esc(d.style.direction || '')}</textarea></label>
        <label class="f"><span class="lbl">Style des miniatures <span class="faint">(peut être différent du style de la vidéo)</span></span><textarea id="chThumb" rows="3" placeholder="Fond, perso, drapeau, flèches, typo…">${esc(d.thumb_style || '')}</textarea></label>
        <label class="check"><input type="checkbox" id="chThumbText" ${d.thumb_text !== false ? 'checked' : ''}> Texte sur les miniatures</label>
        <div class="row" style="align-items:center">${d.thumb_ref ? `<img src="${chFileUrl(cid, d.thumb_ref)}" style="width:120px;border-radius:8px;border:1px solid var(--s-line)">` : ''}
          <label class="btn sm">⬆ ${d.thumb_ref ? 'Changer' : 'Importer'} une miniature de référence<input type="file" id="thUp" accept="image/*" hidden></label>${d.thumb_ref ? '<button class="btn sm danger" id="thDel">Retirer</button>' : ''}</div>
      </div>
      <div class="stack">
        <div class="small muted" style="font-weight:600">Image de référence du style <span class="faint">(envoyée à chaque génération → cohérence)</span></div>
        ${d.style.ref ? `<img class="refimg" src="${chFileUrl(cid, d.style.ref)}">` : '<div class="refbox">Aucune image de style : ajoute une capture de la chaîne à imiter, ou génère-en une à partir du prompt.</div>'}
        <div class="row"><label class="btn sm">⬆ Importer<input type="file" id="stUp" accept="image/*" hidden></label>
          <button class="btn sm" id="stGen">✨ Générer depuis le prompt</button>${d.style.ref ? '<button class="btn sm danger" id="stDel">Retirer</button>' : ''}</div>
      </div></div></div>


    <div class="section-title"><span class="n">4</span><h2>Mise en page tableau & prof animé</h2></div>
    <div class="card"><div class="sub">L'image de chaque scène est posée dans un panneau sur un fond (cahier, papier millimétré, fond sombre…), avec le prof de la chaîne en bas à gauche. Le prof est animé, calé sur la voix off : il tapote le panneau avec sa baguette sur les chiffres clés et fait des gestes quand il parle. Au repos, il ne bouge pas.</div>
      <label class="check" style="margin-bottom:12px"><input type="checkbox" id="bdOn" ${d.montage.layout === 'board' ? 'checked' : ''}> Utiliser cette mise en page pour les nouvelles vidéos de la chaîne</label>
      <div class="grid2">
        <div class="stack">
          <img class="refimg" id="bdPrev" src="/api/pov/channels/${cid}/board-preview?t=${Date.now()}" alt="Aperçu">
          <label class="f"><span class="lbl">Fond</span><select id="bdTheme">${Object.entries(S.cfg.board_themes || {}).map(([k, t]) => `<option value="${k}" ${k === bd.theme ? 'selected' : ''}>${esc(t.name)}</option>`).join('')}<option value="custom" ${bd.theme === 'custom' ? 'selected' : ''}>Personnalisé</option></select></label>
          <details class="adv"><summary>Couleurs et proportions</summary><div class="stack" style="margin-top:8px">
            <div class="row" style="gap:14px;align-items:flex-end">
              <label class="f"><span class="lbl">Fond</span><input type="color" id="bdBg" value="${esc(bd.bg_color)}"></label>
              <label class="f"><span class="lbl">Lignes</span><input type="color" id="bdLine" value="${esc(bd.line_color)}"></label>
              <label class="f"><span class="lbl">Contour</span><input type="color" id="bdBorder" value="${esc(bd.border_color)}"></label></div>
            <div class="grid2">
              <label class="f"><span class="lbl">Largeur du panneau <b id="bdPwOut"></b></span><input type="range" id="bdPw" min="0.7" max="0.95" step="0.01" value="${bd.panel_width}"></label>
              <label class="f"><span class="lbl">Taille du prof <b id="bdPhOut"></b></span><input type="range" id="bdPh" min="0.2" max="0.55" step="0.01" value="${bd.presenter_height}"></label>
              <label class="f"><span class="lbl">Contour du prof (px)</span><input type="number" id="bdOl" min="0" max="16" value="${bd.presenter_outline || 0}"></label>
              <label class="f"><span class="lbl">Halo derrière le prof</span><input type="range" id="bdSpot" min="0" max="0.6" step="0.02" value="${bd.spot || 0}"></label></div>
            <label class="check small"><input type="checkbox" id="bdBob" ${bd.bob ? 'checked' : ''}> Léger mouvement vertical (respiration)</label></div></details>
          <div class="row nowrap"><label class="f grow"><span class="lbl">Animation du prof</span><select id="bdAnim">
              <option value="poses" ${bd.anim !== 'none' ? 'selected' : ''}>Gestes de baguette (bras redessiné par l'IA, ~1 min)</option>
              <option value="none" ${bd.anim === 'none' ? 'selected' : ''}>Aucune (image fixe)</option></select></label>
            ${bd.presenter ? '<button class="btn sm" id="bdRebuild" style="align-self:flex-end">↻ Appliquer au prof</button>' : ''}</div>
        </div>
        <div class="stack">
          <div class="presrow">${bd.presenter ? `<img class="presimg" src="${chFileUrl(cid, bd.presenter)}">` : '<div class="refbox presimg">Pas encore de prof</div>'}
            <div class="stack grow"><label class="f"><span class="lbl">Le prof (mascotte) : description visuelle</span><textarea id="bdMascot" rows="5" placeholder="Ex : un chat noir en costard bleu marine, cravate rouge…">${esc(bd.mascot || '')}</textarea></label>
              <div class="row"><button class="btn sm" id="bdGen">✨ Générer le prof animé</button><label class="btn sm">⬆ Importer un PNG<input type="file" id="bdUp" accept="image/*" hidden></label>${bd.presenter ? '<button class="btn sm danger" id="bdDel">Retirer</button>' : ''}</div>
              <div class="hint">L'IA dessine le prof en pied avec sa baguette levée, sur fond transparent, puis redessine uniquement son bras dans 3 positions (mi-hauteur, pointé, tapotement). Les poses s'enchaînent comme dans un dessin animé, calées sur la voix. Relance si la pose ne te plaît pas.</div></div></div>
          ${bd.rig ? `<div class="rigrow">${['A', 'mid', 'point', 'tap'].map(k => `<img src="${chFileUrl(cid, bd.rig + '/' + k + '.png')}" title="${k}">`).join('')}</div>` : (bd.presenter ? '<div class="hint">Ce prof est une image fixe : choisis « Gestes de baguette » puis « Appliquer au prof ».</div>' : '')}
        </div></div></div>
    <div class="section-title"><span class="n">5</span><h2>Personnages récurrents</h2></div>
    <div class="card"><div class="sub">Le protagoniste (« toi ») garde le même visage dans toute la vidéo ; l'âge et la tenue peuvent évoluer selon le script. Génère une fiche perso pour verrouiller son look.</div>
      <div class="stack" id="chars"></div><button class="btn sm" id="addChar" style="margin-top:10px">＋ Ajouter un personnage</button></div>

    <div class="section-title"><span class="n">6</span><h2>Voix & montage par défaut</h2></div>
    <div class="grid2"><div class="card"><h3>Voix</h3><div id="chVoice" style="margin-top:10px"></div></div>
      <div class="card"><h3>Rythme & montage</h3>
        <div class="grid2" style="margin:10px 0"><label class="f"><span class="lbl">Secondes par image <b id="paceOut"></b></span><input type="range" id="chPace" min="1.8" max="9" step="0.1" value="${d.montage.pacing}"></label>
          <label class="f"><span class="lbl">Pendant le hook <b id="hpOut"></b></span><input type="range" id="chHookPace" min="1.5" max="9" step="0.1" value="${d.montage.hook_pacing}"></label></div>
        <div id="chMontage"></div></div></div>
    <div class="savebar"><span class="small muted" id="chSaveState" style="margin-right:auto;align-self:center"></span><button class="btn primary" id="chSave">Enregistrer la chaîne</button></div>`;

  const renderChars = () => {
    $('#chars').innerHTML = d.style.characters.map((c, i) => `<div class="charrow" data-ci="${i}">
      <div class="stack">${c.image ? `<img class="refimg" src="${chFileUrl(cid, c.image)}">` : '<div class="refbox">Pas d\'image</div>'}
        <div class="row"><label class="btn xs">⬆<input type="file" accept="image/*" data-cup="${i}" hidden></label><button class="btn xs" data-cgen="${i}" title="Générer une fiche perso depuis la description + le style">✨ Fiche</button>${c.image ? `<button class="btn xs danger" data-cdelimg="${i}">✕</button>` : ''}</div></div>
      <div class="stack"><div class="row nowrap"><input type="text" data-cn="${i}" value="${esc(c.name)}" placeholder="Nom (ex : You / Toi)"><button class="btn xs danger" data-cdel="${i}">Supprimer</button></div>
        <textarea rows="3" data-cd="${i}" placeholder="Description visuelle précise : âge, silhouette, cheveux, vêtements, signes distinctifs…">${esc(c.description)}</textarea></div></div>`).join('') || '<div class="hint">Aucun personnage récurrent (ok pour les formats liste / explication).</div>';
  };
  renderChars();
  $('#chVoice').appendChild(voiceForm(d.voice, d.language, v => { d.voice = v; dirty(); }));
  $('#chMontage').appendChild(montageForm(d.montage, v => { d.montage = v; dirty(); }, {music: music.music, lang: d.language}));
  const outs = () => { $('#paceOut').textContent = Number($('#chPace').value).toFixed(1) + ' s'; $('#hpOut').textContent = Number($('#chHookPace').value).toFixed(1) + ' s'; $('#refWc').textContent = $('#chRefs').value.split(/\s+/).filter(Boolean).length + ' mots';
    $('#bdPwOut').textContent = Math.round($('#bdPw').value * 100) + ' %'; $('#bdPhOut').textContent = Math.round($('#bdPh').value * 100) + ' %'; };
  outs();
  let isDirty = false;
  const dirty = () => { isDirty = true; $('#chSaveState').textContent = 'Modifications non enregistrées'; };
  const collect = () => {
    d.name = $('#chName').value.trim() || 'Chaîne'; d.language = $('#chLang').value; d.format = $('#chFormat').value;
    d.niche = $('#chNiche').value; d.audience = $('#chAud').value; d.tone = $('#chTone').value; d.rules = $('#chRules').value;
    d.cta = $('#chCta').value; d.default_minutes = Number($('#chMin').value) || 10; d.wpm = Number($('#chWpm').value) || 150;
    d.reference_urls = $('#chUrls').value; d.reference_scripts = $('#chRefs').value; d.bible = $('#chBibleTxt').value;
    d.style.prompt = $('#stPrompt').value; d.style.preset = $('#stPreset').value; d.style.no_text = $('#stNoText').checked;
    d.style.direction = $('#stDir').value; d.thumb_style = $('#chThumb').value; d.thumb_text = $('#chThumbText').checked;
    Object.assign(d.board, {bg_color: $('#bdBg').value, line_color: $('#bdLine').value, border_color: $('#bdBorder').value,
      panel_width: Number($('#bdPw').value), presenter_height: Number($('#bdPh').value), bob: $('#bdBob').checked,
      presenter_outline: Number($('#bdOl').value) || 0, spot: Number($('#bdSpot').value) || 0,
      anim: $('#bdAnim').value, animate: $('#bdAnim').value !== 'none', mascot: $('#bdMascot').value});
    d.montage.layout = $('#bdOn').checked ? 'board' : 'full';
    d.montage.pacing = Number($('#chPace').value); d.montage.hook_pacing = Number($('#chHookPace').value);
    $$('[data-cn]').forEach(el => d.style.characters[el.dataset.cn].name = el.value);
    $$('[data-cd]').forEach(el => d.style.characters[el.dataset.cd].description = el.value);
    return d;
  };
  const save = async (quiet) => {
    const r = await guard(() => api('PUT', '/channels/' + cid, collect()), quiet ? null : 'Chaîne enregistrée');
    if (r) { isDirty = false; $('#chSaveState').textContent = '✓ enregistré'; Object.assign(d, clone(r)); Object.assign(bd, r.board || {}); d.board = bd; await loadChannels(); prevBoard(); }
    return r;
  };
  const prevBoard = () => { const im = $('#bdPrev'); if (im) im.src = `/api/pov/channels/${cid}/board-preview?t=${Date.now()}`; };
  $('#view').oninput = e => { if (!e.target.closest('#chVoice,#chMontage')) { dirty(); outs(); } };
  $('#chFormat').onchange = e => $('#fmtDesc').textContent = (F[e.target.value] || {}).desc || '';
  $('#stPreset').onchange = e => { if (e.target.value && ST[e.target.value]) $('#stPrompt').value = ST[e.target.value].prompt; dirty(); };
  $('#chSave').onclick = () => save();
  $('#chDel').onclick = async () => { if (confirm(`Supprimer la chaîne « ${d.name} » ? (les vidéos restent)`)) { await guard(() => api('DELETE', '/channels/' + cid)); go('#/channels'); } };
  $('#chFetch').onclick = async e => {
    busy(e.target, true, ''); await save(true);
    const r = await guard(() => api('POST', `/channels/${cid}/transcripts`, {urls: $('#chUrls').value}));
    busy(e.target, false);
    if (r) { $('#chRefs').value = r.channel.reference_scripts; outs(); toast('Transcriptions récupérées' + (r.errors.length ? ` (${r.errors.length} échec)` : ''), 'ok'); }
  };
  $('#chBible').onclick = async e => {
    busy(e.target, true, 'Analyse…'); await save(true);
    const r = await guard(() => api('POST', `/channels/${cid}/bible`, {text: $('#chRefs').value}));
    busy(e.target, false);
    if (r) { $('#chBibleTxt').value = r.bible; d.bible = r.bible; toast('Analyse de la référence prête', 'ok'); }
  };
  $('#stShots').onchange = async e => {
    const fd = new FormData(); [...e.target.files].slice(0, 4).forEach(f => fd.append('files', f));
    toast('Analyse du style…');
    const r = await guard(() => api('POST', `/channels/${cid}/describe-style`, fd));
    if (r) { $('#stPrompt').value = r.prompt; $('#stPreset').value = ''; dirty(); toast('Prompt de style rempli — pense à enregistrer', 'ok'); }
  };
  const refresh = async r => { if (r) { await loadChannels(); viewChannel(cid); } };
  $('#stUp').onchange = async e => { const fd = new FormData(); fd.append('file', e.target.files[0]); await save(true); refresh(await guard(() => api('POST', `/channels/${cid}/style-image`, fd), 'Image de style importée')); };
  $('#stGen').onclick = async e => { busy(e.target, true, 'Génération (~30 s)…'); await save(true); refresh(await guard(() => api('POST', `/channels/${cid}/style-image`, {generate: true}), 'Image de style générée')); busy(e.target, false); };
  if ($('#stDel')) $('#stDel').onclick = async () => { refresh(await guard(() => api('DELETE', `/channels/${cid}/style-image`))); };
  $('#thUp').onchange = async e => { const fd = new FormData(); fd.append('file', e.target.files[0]); await save(true); refresh(await guard(() => api('POST', `/channels/${cid}/style-image?kind=thumb`, fd), 'Miniature de référence importée')); };
  if ($('#thDel')) $('#thDel').onclick = async () => { refresh(await guard(() => api('DELETE', `/channels/${cid}/style-image?kind=thumb`))); };
  $('#bdTheme').onchange = e => {
    const t = (S.cfg.board_themes || {})[e.target.value];
    if (t) { const {name, ...vals} = t; Object.assign(d.board, {presenter_outline: 0, spot: 0}, vals, {theme: e.target.value});
      $('#bdBg').value = t.bg_color; $('#bdLine').value = t.line_color; $('#bdBorder').value = t.border_color;
      $('#bdOl').value = d.board.presenter_outline || 0; $('#bdSpot').value = d.board.spot || 0; }
    save(true);
  };
  ['#bdBg', '#bdLine', '#bdBorder'].forEach(k => $(k).addEventListener('input', () => { d.board.theme = 'custom'; $('#bdTheme').value = 'custom'; }));
  if ($('#bdRebuild')) $('#bdRebuild').onclick = async e => { busy(e.target, true, $('#bdAnim').value === 'poses' ? 'Poses du bras (~1 min)…' : 'Calcul…'); await save(true); refresh(await guard(() => api('POST', `/channels/${cid}/presenter`, {rebuild: true, anim: $('#bdAnim').value}), 'Animation mise à jour')); busy(e.target, false); };
  $('#bdGen').onclick = async e => { busy(e.target, true, $('#bdAnim').value === 'poses' ? 'Génération du prof + poses (~2 min)…' : 'Génération du prof (~40 s)…'); await save(true); refresh(await guard(() => api('POST', `/channels/${cid}/presenter`, {generate: true}), 'Prof généré')); busy(e.target, false); };
  $('#bdUp').onchange = async e => { const fd = new FormData(); fd.append('file', e.target.files[0]); await save(true); refresh(await guard(() => api('POST', `/channels/${cid}/presenter`, fd), 'Prof importé (fond retiré)')); };
  if ($('#bdDel')) $('#bdDel').onclick = async () => { refresh(await guard(() => api('DELETE', `/channels/${cid}/presenter`))); };
  ['#bdBg', '#bdLine', '#bdBorder', '#bdPw', '#bdPh', '#bdOl', '#bdSpot'].forEach(k => $(k).addEventListener('change', debounce(() => save(true), 300)));
  $('#addChar').onclick = () => { collect(); d.style.characters.push({id: null, name: '', description: '', image: null}); renderChars(); dirty(); };
  $('#chars').onclick = async e => {
    const t = e.target;
    if (t.dataset.cdel !== undefined) { collect(); d.style.characters.splice(Number(t.dataset.cdel), 1); renderChars(); dirty(); }
    if (t.dataset.cgen !== undefined || t.dataset.cdelimg !== undefined) {
      const saved = await save(true); if (!saved) return;
      const c = saved.style.characters[Number(t.dataset.cgen ?? t.dataset.cdelimg)];
      if (!c) return;
      if (t.dataset.cdelimg !== undefined) return refresh(await guard(() => api('DELETE', `/channels/${cid}/characters/${c.id}/image`)));
      busy(t, true, ''); refresh(await guard(() => api('POST', `/channels/${cid}/characters/${c.id}/image`, {generate: true}), 'Fiche perso générée')); busy(t, false);
    }
  };
  $('#chars').onchange = async e => {
    const t = e.target; if (t.dataset.cup === undefined) return;
    const saved = await save(true); if (!saved) return;
    const c = saved.style.characters[Number(t.dataset.cup)];
    const fd = new FormData(); fd.append('file', t.files[0]);
    refresh(await guard(() => api('POST', `/channels/${cid}/characters/${c.id}/image`, fd), 'Image du perso importée'));
  };
  window.onbeforeunload = () => isDirty ? true : undefined;
}

// ============================================================================
// RÉGLAGES
// ============================================================================
async function viewSettings() {
  await loadConfig();
  const c = S.cfg;
  $('#view').innerHTML = `
    <div class="hero"><div><h1>Réglages</h1><p>Les clés restent dans le <span class="kbd">.env</span> du serveur — jamais dans le navigateur.</p></div>
      <button class="btn primary" id="testBtn">🔌 Tester les connexions</button></div>
    <div class="grid2">
      <div class="card"><h2>IA (texte + images)</h2><div class="sub">Proxy OpenAI-compatible (CLIProxyAPI / comptes Codex).</div>
        <div class="kv"><div>État</div><div>${c.ai.configured ? '<span class="pill ok">configuré</span>' : '<span class="pill err">AI_BASE_URL / AI_API_KEY manquants</span>'}</div>
          <div>Endpoint</div><div>${esc(c.ai.base || '–')}</div><div>Modèle script</div><div>${esc(c.ai.text_model)}</div>
          <div>Modèle rapide</div><div>${esc(c.ai.fast_model)}</div><div>Modèle image</div><div>${esc(c.ai.image_model)}</div></div>
        <div id="tAi" class="hint" style="margin-top:10px"></div></div>
      <div class="card"><h2>Voix & montage</h2><div class="sub">Edge TTS est gratuit et sans clé ; ElevenLabs / OpenAI s'activent avec leur clé.</div>
        <div class="kv"><div>Edge TTS</div><div>${c.tts.edge ? '<span class="pill ok">installé</span>' : '<span class="pill err">pip install edge-tts</span>'}</div>
          <div>ElevenLabs</div><div>${c.tts.elevenlabs ? '<span class="pill ok">clé présente</span>' : '<span class="pill">ELEVENLABS_API_KEY</span>'}</div>
          <div>OpenAI TTS</div><div>${c.tts.openai ? '<span class="pill ok">clé présente</span>' : '<span class="pill">OPENAI_TTS_KEY</span>'}</div>
          <div>ffmpeg</div><div>${c.ffmpeg ? '<span class="pill ok">OK</span>' : '<span class="pill err">introuvable</span>'}</div>
          <div>Données</div><div class="small">${esc(c.data_dir)}</div></div></div>
    </div>
    <div class="card" style="margin-top:16px"><h2>Comment ça marche</h2><div class="sub">Le pipeline, étape par étape.</div>
      <ol class="small" style="line-height:1.8;margin:0;padding-left:18px">
        <li><b>Chaîne</b> : niche + format (Every Rank, Your Life If, Ancient Life…) + bible de style tirée de vidéos de référence + direction artistique + perso + voix.</li>
        <li><b>Script</b> : plan (hook, sections, beats, budget de mots) → écriture section par section → relecture « script doctor » qui réécrit les passages faibles.</li>
        <li><b>Voix off</b> : synthèse avec timings au mot, silences raccourcis, débit mesuré pour viser la bonne durée la fois suivante.</li>
        <li><b>Storyboard</b> : découpage calé sur les fins de phrases (rythme réglable, hook plus rapide) → prompts d'images par un « directeur artistique » IA → images générées en parallèle avec l'image de style + la fiche perso en référence.</li>
        <li><b>Export</b> : MP4 monté (zooms/pans, fondus, sous-titres karaoké, titres de section, musique ducking, -14 LUFS) ou pack de clips calés pour CapCut/Premiere.</li>
      </ol></div>`;
  $('#testBtn').onclick = async e => {
    busy(e.target, true, 'Test…');
    const r = await guard(() => api('POST', '/test', {}));
    busy(e.target, false);
    if (r) $('#tAi').innerHTML = r.ai.ok ? `✅ IA OK — ${esc(r.ai.model)} en ${r.ai.latency}s` : `❌ ${esc(r.ai.error)}`;
  };
}

// ouverture directe d'un projet depuis un studio de chaîne (bouton « Éditeur »)
try {
  const open = localStorage.getItem('pov.openProject');
  if (open) { localStorage.removeItem('pov.openProject'); if (!location.hash) history.replaceState(null, '', '#/project/' + open); }
} catch (_) { /* stockage indisponible : ouverture normale */ }
route();
