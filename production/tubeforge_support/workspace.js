/* TubeForge workspace: authored content, queue creation and explicit human review. */
'use strict';

(function () {
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const encode = encodeURIComponent;
  const stateLabels = { idle: 'À préparer', queued: 'En file', pending: 'En attente', running: 'En cours', done: 'Terminé', error: 'Erreur', failed: 'Échec', verified: 'Vérifié', correct: 'À corriger', unreviewed: 'À vérifier', stale: 'À revérifier', blocked: 'Bloqué', queued_for_authoring: 'En file · texte à préparer', waiting_for_script: 'Texte à préparer', waiting_for_voiceover: 'Voix à préparer', waiting_for_scenes: 'Découpage à préparer', waiting_for_images: 'Images à préparer', ready_to_render: 'Vérifié · montage à préparer', awaiting_review: 'À vérifier', needs_correction: 'À corriger', rendered_awaiting_review: 'Rendu disponible · à vérifier', publication_ready: 'Validé pour publication' };
  const stateLabel = (state) => stateLabels[state] || (state ? String(state) : 'Non renseigné');
  Object.assign(stateLabels, { technical_review_required: 'Contrôle technique requis', rendered_qa_pending: 'Rendu disponible · contrôle en attente', legacy_readonly: 'Projet de l’atelier avancé' });
  const stepState = (project, key) => project.steps?.[key]?.state || 'idle';
  function projectStatus(project) {
    if (typeof project.review_state === 'string' && project.review_state) return { state: project.review_state, label: stateLabel(project.review_state) };
    if (project.error) return { state: 'error', label: 'Erreur' };
    if (project.running) return { state: 'running', label: 'En cours' };
    if (project.publication_ready === true) return { state: 'verified', label: 'Validé pour publication' };
    if (project.render?.file) return { state: 'unreviewed', label: 'Rendu disponible · à vérifier' };
    const states = Object.values(project.steps || {}).map((step) => step.state);
    if (states.includes('error')) return { state: 'error', label: 'Étape en erreur' };
    const actual = typeof project.review_state === 'string' ? project.review_state : project.status || project.workspace_queue?.state || 'idle';
    return { state: actual, label: stateLabel(actual) };
  }
  function modelsFrom(catalog) {
    return (Array.isArray(catalog?.models) ? catalog.models : []).filter((m) => m && typeof m.id === 'string' && m.id.length);
  }
  function validateProject(row, models, profiles) {
    if (!profiles.some((p) => p.id === row.profile_id)) throw new Error('Choisissez une chaîne disponible.');
    if (!row.title.trim()) throw new Error('Indiquez le titre de la vidéo.');
    if (row.title.trim().length > 240) throw new Error('Le titre est limité à 240 caractères.');
    if (row.custom_script !== undefined) validateScript(row.custom_script);
    if (!Number.isFinite(row.duration_minutes) || row.duration_minutes < 20 || row.duration_minutes > 25) throw new Error('La durée cible doit être comprise entre 20 et 25 minutes.');
    for (const key of ['text_model', 'image_model']) {
      const entry = models.find((m) => m.id === row[key]);
      if (!entry) throw new Error('Choisissez les deux modèles dans le catalogue du proxy.');
      if (entry.capabilities?.[key === 'text_model' ? 'text' : 'image'] === false) throw new Error('Ce modèle n’annonce pas la capacité choisie. Sélectionnez un autre modèle.');
    }
    return row;
  }
  function validateScript(text) {
    if (typeof text !== 'string' || text.includes('\0') || new TextEncoder().encode(text).length > 1024 * 1024) throw new Error('Le script doit être un texte de moins de 1 Mo, sans caractère nul.');
    return text;
  }
  async function readScriptFile(file) {
    if (!file || !/\.(txt|md)$/i.test(file.name) || file.size > 1024 * 1024) throw new Error('Choisissez un fichier .txt ou .md de moins de 1 Mo.');
    let text;
    try { text = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer()); }
    catch { throw new Error('Le fichier est illisible. Utilisez un texte enregistré en UTF-8.'); }
    return validateScript(text);
  }
  function safeUrl(value) {
    if (typeof value !== 'string' || !value || /[\x00-\x20\\]/.test(value)) return '';
    if (value.startsWith('/') && !value.startsWith('//')) return value;
    return '';
  }
  function mediaUrl(kind, id, file) {
    if (!file || typeof file !== 'string') return '';
    if (file.startsWith('/')) return safeUrl(file);
    const parts = file.split('/');
    if (parts.some((part) => part === '..' || part === '.') || file.includes('\\') || file.includes(':')) return '';
    return `/${kind}/${encode(id)}/${parts.map(encode).join('/')}`;
  }
  function referenceUrl(reference, project) {
    if (reference && typeof reference === 'object' && reference.url) return safeUrl(reference.url);
    const file = typeof reference === 'string' ? reference : reference?.file || reference?.path || reference?.image || '';
    if (reference?.owner === 'studio') return '';
    return reference?.owner === 'style' ? mediaUrl('style-media', project.style_id, file) : mediaUrl('media', project.id, file);
  }
  function statusGroup(state) {
    return ({ waiting_for_script: 'queued', waiting_for_voiceover: 'queued', waiting_for_scenes: 'queued', waiting_for_images: 'queued', queued_for_authoring: 'queued', ready_to_render: 'queued', rendered_awaiting_review: 'unreviewed', rendered_qa_pending: 'unreviewed', technical_review_required: 'unreviewed', awaiting_review: 'unreviewed', needs_correction: 'correct', publication_ready: 'verified', failed: 'error' })[state] || state;
  }
  function generationBlockReason(project, scene, editedPrompt = scene?.prompt) {
    if (project?.codex_directed !== true || project.readonly || project.mode !== 'review') return 'La génération d’un plan est réservée aux projets dirigés.';
    if (project.running || ['running', 'queued'].includes(scene?.status)) return 'Une opération est déjà en cours sur ce projet.';
    if (typeof scene?.prompt !== 'string' || !scene.prompt.trim() || /^renderer[- ]only\b/i.test(scene.prompt.trim())) return 'Ce plan n’a pas de prompt de génération explicite.';
    if (editedPrompt !== scene.prompt) return 'Enregistrez le prompt avant de refaire ce plan.';
    if (!sceneReferences(scene).length) return 'Ajoutez les références ordonnées du plan avant de le refaire.';
    if (sceneReferences(scene).some((ref) => ref?.exists === false)) return 'Une référence du plan est manquante.';
    if (!project.model_snapshot?.image_model) return 'Le modèle image du projet n’est pas renseigné.';
    return '';
  }
  function generationBody(project, scene, editedPrompt = scene?.prompt) {
    const reason = generationBlockReason(project, scene, editedPrompt);
    if (reason) throw new Error(reason);
    return { confirm_prompt: scene.prompt, image_model: project.model_snapshot.image_model };
  }
  function referenceOrder(references) {
    return references.map((ref) => typeof ref === 'string' ? { path: ref, owner: 'project' } : { path: ref.path || ref.file || ref.image, owner: ref.owner || 'project', sha256: ref.sha256 || null });
  }
  const helpers = { escapeHtml, projectStatus, modelsFrom, validateProject, validateScript, readScriptFile, safeUrl, mediaUrl, stateLabel, referenceUrl, statusGroup, generationBlockReason, generationBody, referenceOrder };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = helpers;
    if (require.main === module && process.argv.includes('--test')) {
      const assert = require('node:assert/strict');
      let checks = 0;
      const check = (test) => { test(); checks++; };
      check(() => assert.equal(projectStatus({ review_state: 'needs_correction', render: { file: 'video.mp4' } }).state, 'needs_correction'));
      check(() => assert.equal(projectStatus({ review_state: 'waiting_for_script' }).label, 'Texte à préparer'));
      check(() => assert.notEqual(projectStatus({ render: { file: 'video.mp4' } }).state, 'verified'));
      check(() => assert.equal(projectStatus({ publication_ready: true }).state, 'verified'));
      for (const state of ['waiting_for_script', 'waiting_for_voiceover', 'waiting_for_scenes', 'waiting_for_images', 'ready_to_render', 'awaiting_review', 'needs_correction', 'rendered_awaiting_review', 'rendered_qa_pending', 'technical_review_required', 'legacy_readonly', 'publication_ready']) {
        check(() => assert.notEqual(stateLabel(state), state));
      }
      const owner = { id: 'project-id', style_id: 'style-id' };
      check(() => assert.equal(referenceUrl({ path: 'refs/shot.png', owner: 'project' }, owner), '/media/project-id/refs/shot.png'));
      check(() => assert.equal(referenceUrl({ path: 'refs/shot.png', owner: 'style' }, owner), '/style-media/style-id/refs/shot.png'));
      check(() => assert.equal(referenceUrl({ path: 'private/shot.png', owner: 'studio' }, owner), ''));
      check(() => assert.equal(referenceUrl({ url: '/api/workspace/media/master' }, owner), '/api/workspace/media/master'));
      for (const url of ['javascript:alert(1)', '//remote.test/x', '/x\\y', '/x y']) check(() => assert.equal(safeUrl(url), ''));
      check(() => assert.equal(mediaUrl('media', 'p', '../secret'), ''));
      const models = [{ id: 'catalog-text', capabilities: { text: true, image: false } }, { id: 'catalog-image', capabilities: { image: true, text: false } }, { id: 'catalog-unknown' }];
      const profiles = [{ id: 'profile' }];
      const row = { profile_id: 'profile', title: 'Vidéo', duration_minutes: 22, text_model: 'catalog-text', image_model: 'catalog-image' };
      check(() => assert.equal(validateProject(row, models, profiles), row));
      check(() => assert.throws(() => validateProject({ ...row, duration_minutes: 26 }, models, profiles)));
      check(() => assert.throws(() => validateProject({ ...row, image_model: 'catalog-text' }, models, profiles)));
      check(() => assert.throws(() => validateProject({ ...row, text_model: 'invented' }, models, profiles)));
      check(() => assert.equal(validateProject({ ...row, text_model: 'catalog-unknown' }, models, profiles).text_model, 'catalog-unknown'));
      check(() => assert.equal(statusGroup('needs_correction'), 'correct'));
      check(() => assert.equal(statusGroup('rendered_qa_pending'), 'unreviewed'));
      check(() => assert.equal(escapeHtml('<img src=x onerror=alert(1)>'), '&lt;img src=x onerror=alert(1)&gt;'));
      const directed = { id: 'directed', codex_directed: true, mode: 'review', model_snapshot: { image_model: 'catalog-image' } };
      const authored = { id: 1, prompt: '  Exact prompt.\nSecond line.  ', references: [{ path: 'refs/master.png', owner: 'project' }, { path: 'refs/character.png', owner: 'style' }] };
      check(() => assert.deepEqual(generationBody(directed, authored), { confirm_prompt: authored.prompt, image_model: 'catalog-image' }));
      check(() => assert.throws(() => generationBody(directed, authored, 'Unsaved prompt')));
      check(() => assert.throws(() => generationBody({ ...directed, codex_directed: false }, authored)));
      check(() => assert.throws(() => generationBody({ ...directed, readonly: true }, authored)));
      check(() => assert.throws(() => generationBody({ ...directed, mode: 'auto' }, authored)));
      check(() => assert.throws(() => generationBody({ ...directed, running: true }, authored)));
      check(() => assert.throws(() => generationBody(directed, { ...authored, status: 'queued' })));
      check(() => assert.throws(() => generationBody(directed, { ...authored, prompt: 'Renderer-only import. Original authoring retained.' })));
      check(() => assert.throws(() => generationBody(directed, { ...authored, prompt: '   ' })));
      check(() => assert.throws(() => generationBody(directed, { ...authored, references: [] })));
      check(() => assert.throws(() => generationBody(directed, { ...authored, references: [{ path: 'refs/missing.png', exists: false }] })));
      check(() => assert.throws(() => generationBody({ ...directed, model_snapshot: {} }, authored)));
      check(() => assert.deepEqual(referenceOrder(authored.references).map((ref) => ref.path), ['refs/master.png', 'refs/character.png']));
      check(() => assert.deepEqual(Object.keys(generationBody(directed, authored)), ['confirm_prompt', 'image_model']));
      process.stdout.write(`${checks} focused checks passed\n`);
    }
  }
  if (typeof document === 'undefined') return;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const main = $('#main');
  const esc = escapeHtml;
  const icon = (name) => `<span aria-hidden="true">${({ plus: '&#43;', refresh: '&#8635;', close: '&#215;', back: '&#8592;', next: '&#8594;', up: '&#8593;', down: '&#8595;', check: '&#10003;', edit: '&#9998;', download: '&#8595;', external: '&#8599;' })[name] || '&#183;'}</span>`;
  const badge = (state, label = stateLabel(state)) => `<span class="badge ${['verified', 'done', 'publication_ready'].includes(state) ? 'good' : ['error', 'failed'].includes(state) ? 'error' : ['correct', 'stale', 'blocked', 'needs_correction'].includes(state) ? 'warn' : ''}">${esc(label)}</span>`;
  const legacy = (route, label) => `<a class="button" href="/legacy.html#/${route}">${icon('external')}${esc(label)}</a>`;
  const advanced = (items) => `<details class="advanced"><summary>Outils avancés</summary><div class="inline">${items.map(([path, label]) => legacy(path, label)).join('')}</div></details>`;
  const fmtTime = (seconds) => {
    if (!Number.isFinite(Number(seconds))) return 'Non aligné';
    const total = Math.max(0, Math.round(Number(seconds)));
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
  };
  const fmtDate = (value) => value ? new Date(typeof value === 'number' ? value * 1000 : value).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
  const projectHref = (p) => p.readonly ? `/legacy.html#/p/${encode(p.id)}/script` : `#/video/${encode(p.id)}/texte`;
  const profileName = (id) => data.profiles.find((p) => p.id === id)?.name || id || 'Sans chaîne';
  let data = { profiles: [], styles: [], projects: [], batches: [], models: { models: [] }, settings: {}, connection: {} };
  let project = null;
  let epoch = 0;
  let dirty = false;
  let submitting = false;
  let listFilters = { search: '', profile: '', status: '' };
  let batchRows = [];
  const STEPS = [['texte', 'Texte', 'script'], ['voix', 'Voix', 'voiceover'], ['images', 'Images', 'visuals'], ['verification', 'Vérification', null], ['export', 'Export', 'render']];

  async function api(path, options = {}) {
    const request = { method: options.method || 'GET', headers: { Accept: 'application/json' }, cache: 'no-store' };
    if (options.body instanceof FormData) request.body = options.body;
    else if (options.body !== undefined) { request.body = JSON.stringify(options.body); request.headers['Content-Type'] = 'application/json'; }
    const response = await fetch(path, request);
    let payload;
    try { payload = await response.json(); } catch { payload = null; }
    if (!response.ok) {
      const detail = payload?.detail || payload?.error;
      const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((item) => item.msg || 'Donnée invalide').join(' · ') : `Erreur ${response.status}`;
      throw new Error(`${message}${response.status === 404 ? ' · Cette fonction du studio est indisponible. Actualisez après sa mise à jour.' : ''}`);
    }
    if (payload === null) throw new Error('Réponse du studio illisible. Vérifiez le serveur puis réessayez.');
    return payload;
  }
  function notify(message, error = false) {
    const element = document.createElement('div');
    element.className = `notification${error ? ' error' : ''}`;
    element.textContent = message;
    $('#notifications').append(element);
    setTimeout(() => element.remove(), error ? 9000 : 4500);
  }
  async function action(button, work, message) {
    if (submitting) return;
    submitting = true;
    if (button) button.disabled = true;
    try { await work(); if (message) notify(message); }
    catch (error) { notify(error.message || 'Serveur inaccessible. Vérifiez sa connexion puis réessayez.', true); }
    finally { submitting = false; if (button?.isConnected) button.disabled = false; }
  }
  async function refreshData() {
    const result = await api('/api/workspace');
    data = { ...data, ...result, profiles: result.profiles || [], projects: result.projects || [], models: result.models || { models: [] } };
    const available = data.models.available === true;
    $('#connection').textContent = available ? `Proxy · ${modelsFrom(data.models).length} modèles` : data.connection?.has_proxy ? 'Proxy · catalogue indisponible' : 'Proxy non connecté';
  }
  function modelOptions(selected = '', kind = '') {
    const models = modelsFrom(data.models);
    const renderOption = (m) => {
      const capability = m.capabilities?.[kind];
      const capabilityLabel = capability === false ? 'Usage non annoncé' : capability == null ? 'Capacité non confirmée' : 'Capacité annoncée dans le catalogue';
      return `<option value="${esc(m.id)}" title="${capabilityLabel}" ${m.id === selected ? 'selected' : ''} ${capability === false ? 'disabled' : ''}>${esc(m.id)}</option>`;
    };
    const likely = models.filter((m) => m.capabilities?.[kind] === true || m.capabilities?.[kind] == null && m.suggested_role === kind);
    const others = models.filter((m) => !likely.includes(m));
    const choices = `${likely.length ? `<optgroup label="${kind === 'image' ? 'Images' : 'Texte'} · usage annoncé ou suggéré">${likely.map(renderOption).join('')}</optgroup>` : ''}${others.length ? `<optgroup label="Autres modèles / capacité à confirmer">${others.map(renderOption).join('')}</optgroup>` : ''}`;
    const unavailable = selected && !models.some((m) => m.id === selected) ? `<option value="" selected>${esc(selected)} · indisponible</option>` : '';
    return `${unavailable}<option value="" ${!selected ? 'selected' : ''}>${models.length ? 'Choisir un modèle' : 'Catalogue indisponible'}</option>${choices}`;
  }
  function catalogNotice() {
    return modelsFrom(data.models).length ? '' : `<div class="banner error">${esc(data.models.error || 'Le proxy ne fournit aucun modèle. Vérifiez sa connexion dans Réglages, puis actualisez le catalogue.')} <a href="#/settings">Réglages</a></div>`;
  }
  function catalogStatus() {
    return modelsFrom(data.models).length ? '<p class="catalog-status small muted">Disponible dans le proxy · capacités selon le catalogue · génération non testée.</p>' : '';
  }
  function bindFormState(root = main) {
    $$('input, textarea, select', root).forEach((input) => {
      if (input.closest('main') && !input.closest('.toolbar') && !input.dataset.dirtyBound) {
        input.addEventListener('input', () => { dirty = true; });
        input.dataset.dirtyBound = 'true';
      }
    });
    $$('select[name="text_model"], select[name="image_model"]', root).forEach((select) => {
      if (select.nextElementSibling?.classList.contains('selected-model')) return;
      const output = document.createElement('span');
      output.className = 'selected-model';
      const update = () => { output.textContent = select.value; select.title = select.value; };
      select.insertAdjacentElement('afterend', output);
      select.addEventListener('change', update);
      update();
    });
  }
  function profileOptions(selected = '', empty = 'Choisir une chaîne') {
    return `<option value="">${esc(empty)}</option>${data.profiles.map((p) => `<option value="${esc(p.id)}" ${p.id === selected ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}`;
  }
  function preview(src, label) {
    const url = safeUrl(src);
    return url ? `<button type="button" class="preview-open" data-preview="${esc(url)}" aria-label="Agrandir : ${esc(label)}"><img class="preview" src="${esc(url)}" alt="${esc(label)}" loading="lazy"></button>` : `<div class="preview-empty">Aucun aperçu</div>`;
  }
  function bindPreviews(root = main) {
    $$('[data-preview]', root).forEach((button) => button.onclick = () => {
      const dialog = $('#preview-dialog');
      dialog.classList.remove('generation-dialog');
      dialog.setAttribute('aria-label', 'Aperçu de l’image');
      dialog.innerHTML = `<div class="dialog-head"><h2>Aperçu</h2><button class="icon-button" data-close title="Fermer" aria-label="Fermer">${icon('close')}</button></div><img src="${esc(button.dataset.preview)}" alt="Aperçu agrandi">`;
      $('[data-close]', dialog).onclick = () => dialog.close();
      dialog.showModal();
    });
    $$('img', root).forEach((img) => img.addEventListener('error', () => {
      const message = document.createElement('span');
      message.className = 'preview-empty'; message.textContent = 'Aperçu inaccessible';
      img.replaceWith(message);
    }, { once: true }));
  }
  function header(title, subtitle, controls = '') {
    return `<div class="page-head"><div><h1>${esc(title)}</h1>${subtitle ? `<p>${esc(subtitle)}</p>` : ''}</div><div class="actions">${controls}</div></div>`;
  }
  function routeParts() {
    return location.hash.replace(/^#\/?/, '').split('/').filter(Boolean).map((part) => { try { return decodeURIComponent(part); } catch { return part; } });
  }
  async function route({ refresh = true } = {}) {
    const currentEpoch = ++epoch;
    let parts = routeParts();
    if (parts[0] === 'batch') { history.replaceState(null, '', '#/queue'); parts = ['queue']; }
    if (parts[0] === 'styles') { history.replaceState(null, '', '#/channels'); parts = ['channels']; }
    if (parts[0] === 'projects') parts = ['videos'];
    if (parts[0] === 'p') parts = ['video', parts[1], ({ script: 'texte', voice: 'voix', visuals: 'images', render: 'export', thumbs: 'export' })[parts[2]] || 'texte'];
    const page = parts[0] || 'videos';
    $$('.primary-nav a').forEach((link) => {
      const active = link.dataset.nav === (page === 'video' || page === 'queue' ? 'videos' : page);
      if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    });
    main.setAttribute('aria-busy', 'true');
    if (!main.children.length) main.innerHTML = '<div class="empty">Chargement…</div>';
    try {
      if (refresh) await refreshData();
      let detail = null;
      if (page === 'video') detail = await api(`/api/workspace/projects/${encode(parts[1] || '')}`);
      if (currentEpoch !== epoch) return;
      dirty = false;
      if (page === 'videos') renderDashboard();
      else if (page === 'queue') renderBatch();
      else if (page === 'video') { project = detail; renderProject(parts[2] || 'texte'); }
      else if (page === 'channels') renderChannels(parts[1]);
      else if (page === 'settings') renderSettings();
      else main.innerHTML = `${header('Page introuvable', '')}<a href="#/videos">Revenir aux vidéos</a>`;
      bindPreviews();
      bindFormState();
      document.title = `${page === 'video' ? project.title : ({ videos: 'Vidéos', queue: 'File de vidéos', channels: 'Chaînes', settings: 'Réglages' })[page] || 'Studio'} | TubeForge`;
    } catch (error) {
      if (currentEpoch === epoch) {
        main.innerHTML = `${header('Studio indisponible', '')}<div class="banner error">${esc(error.message)}</div><button id="retry">${icon('refresh')}Réessayer</button>`;
        $('#retry').onclick = () => route();
      }
    } finally { if (currentEpoch === epoch) main.setAttribute('aria-busy', 'false'); }
  }
  function projectTable(projects) {
    if (!projects.length) return '<div class="empty"><h2>Aucune vidéo</h2><p>Créez une vidéo ou préparez un lot pour cette chaîne.</p></div>';
    return `<div class="table-wrap"><table><thead><tr><th scope="col">Vidéo</th><th scope="col">Chaîne</th><th scope="col">Durée cible</th><th scope="col">État</th><th scope="col">Mise à jour</th></tr></thead><tbody>${projects.map((p) => {
      const status = projectStatus(p);
      const thumb = mediaUrl('media', p.id, p.thumb || p.thumbnail?.file);
      const minutes = p.target_duration_seconds ? p.target_duration_seconds / 60 : p.duration_minutes;
      return `<tr><td><div class="project-cell">${thumb ? `<img src="${esc(thumb)}" alt="Miniature de ${esc(p.title)}" loading="lazy">` : '<span class="project-placeholder">Miniature absente</span>'}<div><a class="project-title" href="${esc(projectHref(p))}">${esc(p.title || 'Sans titre')}</a><div class="small muted">${p.scenes_count ?? (Array.isArray(p.scenes) ? p.scenes.length : p.scenes) ?? 0} plans</div></div></div></td><td>${esc(profileName(p.profile_id || p.channel_id))}</td><td>${Number.isFinite(minutes) ? `${minutes} min` : 'Non définie'}</td><td>${badge(status.state, status.label)}</td><td class="small muted">${esc(fmtDate(p.updated || p.created))}</td></tr>`;
    }).join('')}</tbody></table></div>`;
  }
  function renderDashboard() {
    main.innerHTML = `${header('Vidéos', 'Projets et file de production', `<a class="button" href="#/queue">${icon('plus')}Créer un lot</a><button class="primary" id="new-video">${icon('plus')}Nouvelle vidéo</button>`)}<div class="toolbar"><label class="search">Rechercher<input id="search" type="search" placeholder="Titre de la vidéo" value="${esc(listFilters.search)}"></label><label>Chaîne<select id="channel-filter">${profileOptions(listFilters.profile, 'Toutes les chaînes')}</select></label><label>État<select id="status-filter"><option value="">Tous les états</option>${['queued', 'running', 'unreviewed', 'correct', 'verified', 'error', 'legacy_readonly'].map((s) => `<option value="${s}" ${listFilters.status === s ? 'selected' : ''}>${stateLabel(s)}</option>`).join('')}</select></label><button id="refresh" class="icon-button" title="Actualiser les projets" aria-label="Actualiser les projets">${icon('refresh')}</button><span id="project-count" class="count"></span></div><div id="project-list"></div>${advanced([['projects', 'Projets avancés'], ['planning', 'Calendrier'], ['thumbs', 'Miniatures']])}`;
    const update = () => {
      listFilters = { search: $('#search').value, profile: $('#channel-filter').value, status: $('#status-filter').value };
      const projects = data.projects.filter((p) => (!listFilters.search || (p.title || '').toLocaleLowerCase('fr').includes(listFilters.search.toLocaleLowerCase('fr'))) && (!listFilters.profile || (p.profile_id || p.channel_id) === listFilters.profile) && (!listFilters.status || statusGroup(projectStatus(p).state) === listFilters.status));
      $('#project-list').innerHTML = projectTable(projects);
      $('#project-count').textContent = `${projects.length} vidéo${projects.length === 1 ? '' : 's'}`;
      bindPreviews($('#project-list'));
    };
    $('#new-video').onclick = () => openCreate();
    $('#refresh').onclick = (event) => action(event.currentTarget, () => route());
    $('#search').oninput = update;
    $('#channel-filter').onchange = update;
    $('#status-filter').onchange = update;
    update();
  }
  function defaultRow(profile = '') {
    return { profile_id: profile, title: '', duration_minutes: 22, text_model: data.models.defaults?.text_model || '', image_model: data.models.defaults?.image_model || '' };
  }
  function formRow(form) {
    const fields = new FormData(form);
    const row = { profile_id: fields.get('profile_id'), title: String(fields.get('title') || '').trim(), duration_minutes: Number(fields.get('duration_minutes')), text_model: fields.get('text_model'), image_model: fields.get('image_model') };
    if (fields.has('style_id')) row.style_id = fields.get('style_id');
    if (fields.has('custom_script')) row.custom_script = fields.get('custom_script');
    return row;
  }
  function scriptImportMarkup(id) {
    return `<div class="script-tools"><label class="file-picker">${icon('up')}Importer un script<input id="${id}" type="file" accept=".txt,.md,text/plain,text/markdown"></label><span class="small muted" data-script-count></span></div><p class="small muted import-status" data-import-status role="status"></p>`;
  }
  function bindScriptImport(root, inputSelector) {
    const input = $(inputSelector, root);
    const fileInput = $('input[type="file"]', root);
    const count = () => { $('[data-script-count]', root).textContent = `${input.value.trim().split(/\s+/).filter(Boolean).length} mots`; };
    count(); input.addEventListener('input', count);
    fileInput.onchange = async () => {
      const file = fileInput.files[0];
      if (!file) return;
      const status = $('[data-import-status]', root);
      try {
        const text = await readScriptFile(file);
        if (input.value.trim() && !confirm('Remplacer le texte actuel par le script importé ?')) return;
        input.value = text;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        status.textContent = `${file.name} · importé`;
        status.classList.remove('error-text');
      } catch (error) { status.textContent = error.message; status.classList.add('error-text'); }
      finally { fileInput.value = ''; }
    };
  }
  function openCreate(profile = '') {
    const dialog = $('#create-dialog');
    dialog.className = 'create-video-dialog';
    const row = defaultRow(profile);
    const defaultStyle = data.profiles.find((p) => p.id === profile)?.style_id || data.profiles[0]?.style_id;
    const previousDirty = dirty;
    let dialogEdited = false;
    dialog.innerHTML = `<div class="dialog-head"><h2 id="create-heading">Nouvelle vidéo</h2><button type="button" data-close class="icon-button" title="Fermer" aria-label="Fermer">${icon('close')}</button></div>${catalogNotice()}<form id="create-form"><div class="create-layout"><div><fieldset><legend>Projet</legend><div class="form-grid"><label class="full">Titre de la vidéo<input name="title" placeholder="What Did People in Edo Japan Actually Do All Day?" required maxlength="240" autocomplete="off"></label><label>Chaîne<select name="profile_id" required>${profileOptions(row.profile_id)}</select></label><label>Durée cible (minutes)<input type="number" name="duration_minutes" min="20" max="25" step="0.5" value="22" required></label></div></fieldset><fieldset class="create-section"><legend>Script</legend>${scriptImportMarkup('create-script-file')}<label>Texte de narration<textarea name="custom_script" rows="8" spellcheck="true"></textarea></label></fieldset></div><div class="create-options"><fieldset><legend>Style visuel</legend><label>Style de la vidéo<select name="style_id" required>${data.styles.map((s) => `<option value="${esc(s.id)}" ${s.id === defaultStyle ? 'selected' : ''}>${esc(s.name)}</option>`).join('')}</select></label><figure id="create-style-preview" class="create-style-preview"></figure></fieldset><fieldset class="create-section"><legend>Modèles de génération</legend><div class="form-grid"><label class="full">Modèle texte<select name="text_model" required>${modelOptions(row.text_model, 'text')}</select></label><label class="full">Modèle image<select name="image_model" required>${modelOptions(row.image_model, 'image')}</select></label></div></fieldset>${catalogStatus()}</div></div><div id="create-error" role="alert"></div><div class="form-actions create-footer"><button type="button" data-close>Annuler</button><button class="primary" type="submit" ${!modelsFrom(data.models).length || !data.profiles.length || !data.styles.length ? 'disabled' : ''}>${icon('plus')}Créer la vidéo</button></div></form>`;
    const close = () => { if (dialogEdited && !confirm('Abandonner cette nouvelle vidéo ?')) return; dialog.close(); dirty = previousDirty; };
    $('#create-form', dialog).addEventListener('input', () => { dialogEdited = true; });
    $('#create-form', dialog).addEventListener('change', () => { dialogEdited = true; });
    $$('[data-close]', dialog).forEach((b) => b.onclick = close);
    dialog.oncancel = (event) => { event.preventDefault(); close(); };
    const updatePreview = () => {
      const sid = $('[name="style_id"]', dialog).value;
      const selectedProfile = data.profiles.find((p) => p.id === $('[name="profile_id"]', dialog).value);
      const owner = selectedProfile?.style_id === sid ? selectedProfile : data.profiles.find((p) => p.style_id === sid);
      const url = owner ? profilePreview(owner, 'video') : '';
      $('#create-style-preview', dialog).innerHTML = url ? `<img class="preview" src="${esc(url)}" alt="Aperçu du style vidéo"><figcaption>${esc(data.styles.find((s) => s.id === sid)?.name || '')}</figcaption>` : '<div class="preview-empty">Aperçu non disponible</div>';
    };
    $('[name="style_id"]', dialog).onchange = updatePreview;
    $('[name="profile_id"]', dialog).onchange = () => { const selected = data.profiles.find((p) => p.id === $('[name="profile_id"]', dialog).value); if (selected) $('[name="style_id"]', dialog).value = selected.style_id; updatePreview(); };
    updatePreview();
    bindScriptImport($('#create-form', dialog), '[name="custom_script"]');
    $('#create-form', dialog).onsubmit = (event) => {
      event.preventDefault();
      action($('button[type="submit"]', dialog), async () => {
        try {
          const row = validateProject(formRow(event.target), modelsFrom(data.models), data.profiles);
          const created = await api('/api/workspace/projects', { method: 'POST', body: row });
          dialog.close(); dirty = false;
          location.hash = `#/video/${encode(created.id)}/texte`;
        } catch (error) { $('#create-error', dialog).innerHTML = `<div class="banner error">${esc(error.message)}</div>`; throw error; }
      }, 'Vidéo créée.');
    };
    dialog.showModal();
    bindFormState(dialog);
    $('[name="title"]', dialog).focus();
  }
  function captureBatch() {
    batchRows = $$('#batch-body tr').map((tr) => ({ profile_id: $('[name="profile_id"]', tr).value, title: $('[name="title"]', tr).value, duration_minutes: Number($('[name="duration_minutes"]', tr).value), text_model: $('[name="text_model"]', tr).value, image_model: $('[name="image_model"]', tr).value }));
  }
  function renderBatch() {
    if (!batchRows.length) batchRows = [defaultRow(), defaultRow()];
    main.innerHTML = `${header('File de vidéos', 'Préparer plusieurs projets', '<a class="button" href="#/videos">Vidéos</a>')}${catalogNotice()}<form id="batch-form"><div class="table-wrap"><table class="batch-table"><thead><tr><th>Chaîne</th><th>Titre</th><th>Minutes</th><th>Modèle texte</th><th>Modèle image</th><th><span class="small">Retirer</span></th></tr></thead><tbody id="batch-body">${batchRows.map((row, index) => `<tr><td data-label="Chaîne"><select aria-label="Chaîne de la vidéo ${index + 1}" name="profile_id" required>${profileOptions(row.profile_id)}</select></td><td data-label="Titre"><input class="title-input" aria-label="Titre de la vidéo ${index + 1}" name="title" maxlength="240" required value="${esc(row.title)}"></td><td data-label="Durée cible (minutes)"><input class="duration-input" aria-label="Durée de la vidéo ${index + 1}" name="duration_minutes" type="number" min="20" max="25" step="0.5" required value="${row.duration_minutes}"></td><td data-label="Modèle texte"><select aria-label="Modèle texte de la vidéo ${index + 1}" name="text_model" required>${modelOptions(row.text_model, 'text')}</select></td><td data-label="Modèle image"><select aria-label="Modèle image de la vidéo ${index + 1}" name="image_model" required>${modelOptions(row.image_model, 'image')}</select></td><td><button type="button" data-remove="${index}" class="icon-button" aria-label="Retirer la vidéo ${index + 1}" title="Retirer cette ligne" ${batchRows.length === 1 ? 'disabled' : ''}>${icon('close')}</button></td></tr>`).join('')}</tbody></table></div>${catalogStatus()}<div class="form-actions"><button type="button" id="add-row">${icon('plus')}Ajouter une ligne</button><button class="primary" type="submit" ${!modelsFrom(data.models).length || !data.profiles.length ? 'disabled' : ''}>${icon('plus')}Ajouter le lot à la file</button></div><div id="batch-error" role="alert"></div></form><section class="section"><h2>Lots enregistrés</h2>${data.batches?.length ? `<div class="table-wrap"><table><thead><tr><th>Lot</th><th>Vidéos</th><th>Création</th></tr></thead><tbody>${data.batches.map((batch) => `<tr><td>${esc(batch.name || batch.id)}</td><td>${(batch.projects || []).length}</td><td>${esc(fmtDate(batch.created))}</td></tr>`).join('')}</tbody></table></div>` : '<p class="muted">Aucun lot enregistré.</p>'}</section>`;
    $('#add-row').onclick = () => { captureBatch(); batchRows.push(defaultRow()); renderBatch(); };
    $$('[data-remove]').forEach((b) => b.onclick = () => { captureBatch(); batchRows.splice(Number(b.dataset.remove), 1); renderBatch(); });
    $('#batch-form').onsubmit = (event) => {
      event.preventDefault(); captureBatch();
      action($('button[type="submit"]', event.target), async () => {
        try {
          const rows = batchRows.map((row, i) => { try { return validateProject(row, modelsFrom(data.models), data.profiles); } catch (error) { throw new Error(`Ligne ${i + 1} : ${error.message}`); } });
          await api('/api/workspace/batches', { method: 'POST', body: { rows } });
          batchRows = []; dirty = false; location.hash = '#/videos';
        } catch (error) { $('#batch-error').innerHTML = `<div class="banner error">${esc(error.message)}</div>`; throw error; }
      }, 'Lot ajouté à la file.');
    };
    bindFormState();
  }
  function reviewState(scene) {
    const review = scene.review || scene.human_review || {};
    return typeof review === 'string' ? review : review.state || scene.review_state || 'unreviewed';
  }
  function renderProject(selected) {
    if (!STEPS.some(([key]) => key === selected)) selected = 'texte';
    const status = projectStatus(project);
    const verification = project.review_state?.state || (typeof project.review_state === 'string' ? project.review_state : 'unreviewed');
    main.innerHTML = `<div class="breadcrumbs"><a href="#/videos">Vidéos</a><span>/</span><a href="#/channels/${encode(project.profile_id || project.channel_id || '')}">${esc(profileName(project.profile_id || project.channel_id))}</a></div>${header(project.title || 'Sans titre', `${project.target_duration_seconds ? `${project.target_duration_seconds / 60} min · ` : ''}${profileName(project.profile_id || project.channel_id)}`, `${badge(status.state, status.label)}<button class="icon-button" id="refresh-project" title="Actualiser ce projet" aria-label="Actualiser ce projet">${icon('refresh')}</button>`)}${project.error ? `<div class="banner error">${esc(project.error)}</div>` : ''}<nav class="steps" aria-label="Étapes de la vidéo">${STEPS.map(([key, name, step], index) => `<a href="#/video/${encode(project.id)}/${key}" ${key === selected ? 'aria-current="step"' : ''}><span class="step-name"><span class="step-number">${index + 1}</span>${name}</span>${badge(key === 'verification' ? verification : stepState(project, step))}</a>`).join('')}</nav><div id="step-content"></div>${advanced([[`p/${encode(project.id)}/script`, 'Texte avancé'], [`p/${encode(project.id)}/voice`, 'Voix avancée'], [`p/${encode(project.id)}/visuals`, 'Images avancées'], [`p/${encode(project.id)}/render`, 'Montage'], [`p/${encode(project.id)}/thumbs`, 'Miniatures']])}`;
    $('#refresh-project').onclick = (event) => action(event.currentTarget, () => route());
    if (project.style_name) $('.page-head p').textContent += ` · ${project.style_name}`;
    $('#refresh-project').insertAdjacentHTML('beforebegin', `<button id="rename-video" class="icon-button" title="Modifier le titre" aria-label="Modifier le titre">${icon('edit')}</button>`);
    $('#rename-video').onclick = openRename;
    if (selected === 'texte') renderText();
    if (selected === 'voix') renderVoice();
    if (selected === 'images' || selected === 'verification') renderScenes(selected === 'verification');
    if (selected === 'export') renderExport();
  }
  function openRename() {
    if (dirty) { notify('Enregistrez vos modifications avant de changer le titre.', true); return; }
    const dialog = $('#create-dialog');
    dialog.className = '';
    dialog.innerHTML = `<div class="dialog-head"><h2 id="create-heading">Modifier le titre</h2><button type="button" data-close class="icon-button" aria-label="Fermer" title="Fermer">${icon('close')}</button></div><form id="rename-form"><label>Titre de la vidéo<input name="title" value="${esc(project.title)}" maxlength="240" required></label><div class="form-actions"><button type="button" data-close>Annuler</button><button type="submit" class="primary">Enregistrer le titre</button></div></form>`;
    const close = () => { if (dirty && !confirm('Abandonner la modification du titre ?')) return; dirty = false; dialog.close(); };
    $$('[data-close]', dialog).forEach((button) => button.onclick = close);
    dialog.oncancel = (event) => { event.preventDefault(); close(); };
    $('#rename-form').onsubmit = (event) => {
      event.preventDefault();
      action(event.submitter, async () => {
        await api(`/api/workspace/projects/${encode(project.id)}/title`, { method: 'PUT', body: { title: $('[name="title"]', dialog).value } });
        dialog.close(); dirty = false; await route();
      }, 'Titre enregistré.');
    };
    bindFormState(dialog);
    dialog.showModal(); $('[name="title"]', dialog).focus();
  }
  function scopeReview(scope) {
    const entry = project.human_reviews?.[scope] || {};
    return `${badge(entry.state || 'unreviewed')}<form class="scope-review" data-scope="${scope}"><label>Note de vérification<textarea name="notes" rows="2">${esc(entry.notes || '')}</textarea></label><div class="form-actions"><button type="submit" name="state" value="correct">${icon('edit')}À corriger</button><button type="submit" name="state" value="verified" class="primary">${icon('check')}Marquer vérifié</button></div></form>`;
  }
  function bindScopeReviews() {
    $$('.scope-review').forEach((form) => form.onsubmit = (event) => {
      event.preventDefault();
      const state = event.submitter?.value;
      action(event.submitter, async () => {
        const notes = $('[name="notes"]', form).value;
        if (form.dataset.scope === 'script' && $('[name="text"]')?.value !== project.script) throw new Error('Enregistrez le texte avant de le vérifier.');
        if (state === 'correct' && !notes.trim()) throw new Error('Précisez la correction demandée.');
        await api(`/api/workspace/projects/${encode(project.id)}/review`, { method: 'POST', body: { scope: form.dataset.scope, state, notes } });
        await route();
      }, state === 'verified' ? 'Vérification enregistrée.' : 'Demande de correction enregistrée.');
    });
  }
  function renderText() {
    $('#step-content').innerHTML = `<form id="script-form" class="editor"><div class="page-head"><h2>Script</h2></div>${scriptImportMarkup('edit-script-file')}<label>Texte de narration<textarea name="text" class="script-editor" spellcheck="true">${esc(project.script || '')}</textarea></label><div class="form-actions"><button type="submit" class="primary">Enregistrer le texte</button></div>${project.voiceover_stale ? '<div class="banner">La voix correspond à une version antérieure du texte.</div>' : ''}</form><section class="section editor"><h2>Relecture du texte</h2>${scopeReview('script')}</section>`;
    const input = $('[name="text"]');
    bindScriptImport($('#script-form'), '[name="text"]');
    $('#script-form').onsubmit = (event) => { event.preventDefault(); action(event.submitter, async () => { await api(`/api/workspace/projects/${encode(project.id)}/script`, { method: 'PUT', body: { text: validateScript(input.value) } }); await route(); }, 'Texte enregistré.'); };
    bindScopeReviews();
  }
  function renderVoice() {
    const voice = project.voiceover;
    const url = mediaUrl('media', project.id, voice?.file);
    const step = project.steps?.voiceover || {};
    $('#step-content').innerHTML = `${header('Voix', step.msg || '', badge(step.state || 'idle'))}${project.voiceover_stale ? '<div class="banner">La voix est à refaire : le texte a changé.</div>' : ''}${url ? `<audio controls preload="metadata" src="${esc(url)}"></audio><p class="muted small">Durée réelle : ${fmtTime(voice.duration)}</p><section class="section editor"><h2>Écoute et vérification</h2>${scopeReview('voiceover')}</section>` : '<div class="empty"><h2>Aucune voix enregistrée</h2><p>Le projet attend sa narration.</p></div>'}<dl class="definition-list"><div><dt>Voix du projet</dt><dd>${esc(project.settings?.voice?.voice_name || project.settings?.voice?.voice_id || 'Non définie')}</dd></div><div><dt>Langue</dt><dd>${esc(project.settings?.language || 'Non définie')}</dd></div></dl>`;
    bindScopeReviews();
  }
  function sceneReferences(scene) {
    if (scene.display_references?.length) return scene.display_references;
    if (scene.references?.length) return scene.references;
    if (scene.sent_references?.length) return scene.sent_references;
    if (scene.codex_receipt?.references?.length) return scene.codex_receipt.references.map((ref) => ({ ...ref, owner: ref.owner || 'studio' }));
    return scene.reference_images || [];
  }
  function referenceView(reference) {
    const file = typeof reference === 'string' ? reference : reference.file || reference.path || reference.image || '';
    const label = typeof reference === 'string' ? reference : reference.label || reference.role || file;
    const url = referenceUrl(reference, project);
    return `<li><div class="ref-item">${url ? `<a href="${esc(url)}" target="_blank" rel="noopener"><img src="${esc(url)}" alt="${esc(label)}" loading="lazy"></a>` : ''}<span>${esc(label)}${typeof reference === 'object' && reference.role ? `<small class="muted"> · ${esc(reference.role)}</small>` : ''}</span></div></li>`;
  }
  function generationControl(scene) {
    if (generationBlockReason(project, scene)) return '';
    return `<div class="actions"><button type="button" data-generate="${esc(scene.id)}">${icon('refresh')}Refaire ce plan</button></div>`;
  }
  function openGeneration(scene, article) {
    const editedPrompt = $('[name="prompt"]', article)?.value ?? scene.prompt;
    const reason = generationBlockReason(project, scene, editedPrompt);
    if (reason) { notify(reason, true); return; }
    const projectId = project.id;
    const body = generationBody(project, scene, editedPrompt);
    const references = sceneReferences(scene);
    const confirmedOrder = referenceOrder(references);
    const dialog = $('#preview-dialog');
    dialog.classList.add('generation-dialog');
    dialog.setAttribute('aria-label', 'Confirmer la génération du plan');
    dialog.innerHTML = `<div class="dialog-head"><h2>Refaire ce plan</h2><button type="button" data-cancel class="icon-button" title="Fermer" aria-label="Fermer">${icon('close')}</button></div><dl class="metadata"><dt>Plan</dt><dd>${esc(scene.id)}</dd><dt>Modèle image</dt><dd>${esc(body.image_model)}</dd></dl><section class="section"><h3>Prompt exact enregistré</h3><pre class="exact-prompt">${esc(body.confirm_prompt)}</pre></section><section class="section"><h3>Références, dans l’ordre</h3><ol class="refs">${references.map((ref) => referenceView(typeof ref === 'string' ? ref : { ...ref, label: `${ref.label || ref.role || 'Référence'} · ${ref.path || ref.file || ref.image || ''}` })).join('')}</ol></section><p class="muted small">Une nouvelle version de cette image sera créée. La version précédente sera conservée ; le nouveau résultat sera à vérifier.</p><div id="generation-error" role="alert"></div><div class="form-actions"><button type="button" data-cancel>Annuler</button><button type="button" id="confirm-generation" class="primary">${icon('refresh')}Confirmer et refaire ce plan</button></div>`;
    $$('[data-cancel]', dialog).forEach((button) => button.onclick = () => { if (!submitting) dialog.close(); });
    const preventBusyClose = (event) => { if (submitting) event.preventDefault(); };
    dialog.addEventListener('cancel', preventBusyClose);
    dialog.addEventListener('close', () => dialog.removeEventListener('cancel', preventBusyClose), { once: true });
    $('#confirm-generation', dialog).onclick = (event) => action(event.currentTarget, async () => {
      const cancelButtons = $$('[data-cancel]', dialog);
      cancelButtons.forEach((button) => { button.disabled = true; });
      try {
        const current = await api(`/api/workspace/projects/${encode(projectId)}`);
        const latest = current.scenes?.find((candidate) => candidate.id === scene.id);
        if (!latest) throw new Error('Ce plan n’existe plus. Actualisez le projet.');
        const latestBody = generationBody(current, latest);
        if (latestBody.confirm_prompt !== body.confirm_prompt || latestBody.image_model !== body.image_model || JSON.stringify(referenceOrder(sceneReferences(latest))) !== JSON.stringify(confirmedOrder)) {
          throw new Error('Le prompt, les références ou le modèle ont changé. Actualisez le projet avant de confirmer à nouveau.');
        }
        const promptInput = $('[name="prompt"]', article);
        if (promptInput && promptInput.value !== body.confirm_prompt) throw new Error('Enregistrez le prompt avant de refaire ce plan.');
        await api(`/api/workspace/projects/${encode(projectId)}/scenes/${encode(scene.id)}/generate`, { method: 'POST', body });
        dialog.close();
        notify('Nouvelle image demandée pour ce plan.');
        await route();
      } catch (error) {
        $('#generation-error', dialog).innerHTML = `<div class="banner error">${esc(error.message)}</div>`;
        throw error;
      } finally { cancelButtons.forEach((button) => { button.disabled = false; }); }
    });
    dialog.showModal();
    bindPreviews(dialog);
    $('[data-cancel]', dialog).focus();
  }
  function renderScenes(verification) {
    const scenes = project.scenes || [];
    const verified = scenes.filter((s) => reviewState(s) === 'verified').length;
    $('#step-content').innerHTML = `${header(verification ? 'Vérification des images' : 'Plans et images', `${scenes.length} plans · ${verified} vérifiés`)}${!scenes.length ? '<div class="empty"><h2>Aucun plan enregistré</h2><p>Le découpage et les prompts de ce projet restent à préparer.</p></div>' : scenes.map((scene, index) => {
      const references = sceneReferences(scene);
      const names = (scene.characters || []).map((id) => typeof id === 'object' ? id.name || id.id : project.characters?.find((c) => c.id === id)?.name || id);
      const image = safeUrl(scene.image_url) || mediaUrl('media', project.id, scene.image);
      return `<article class="scene" data-scene="${esc(scene.id)}"><div class="scene-media">${preview(image, `Plan ${index + 1}`)}<div class="inline">${badge(scene.status || 'idle', scene.image ? `Image · ${stateLabel(scene.status || 'done')}` : stateLabel(scene.status || 'idle'))}${badge(reviewState(scene))}</div>${scene.error ? `<div class="banner error">${esc(scene.error)}</div>` : ''}<h3>${scene.sent_references ? 'Références envoyées, dans l’ordre' : 'Références du plan, dans l’ordre'}</h3>${references.length ? `<ol class="refs">${references.map(referenceView).join('')}</ol>` : '<p class="muted small">Aucune référence enregistrée.</p>'}</div><div class="scene-data"><div class="scene-head"><h2>Plan ${index + 1}</h2><span class="small muted">${scene.start != null && scene.end != null ? `${fmtTime(scene.start)} → ${fmtTime(scene.end)}` : 'Voix non alignée'}</span></div><div class="narration"><h3>Narration</h3><p>${esc(scene.text || scene.narration || 'Extrait manquant')}</p></div><dl class="metadata"><dt>Lieu</dt><dd>${esc(scene.location_id || scene.location || 'Non renseigné')}</dd><dt>Personnages</dt><dd>${esc(names.join(', ') || 'Aucun personnage nommé')}</dd><dt>Variante</dt><dd>${esc(scene.variant || scene.camera_variant || 'Non renseignée')}</dd></dl>${verification ? `<details><summary>Prompt du plan</summary><p>${esc(scene.prompt || 'Prompt manquant')}</p></details>` : `<form class="scene-form"><label>Prompt exact<textarea name="prompt">${esc(scene.prompt || '')}</textarea></label><div class="form-actions"><button type="submit">Enregistrer le prompt</button></div></form>`}<form class="review-form"><label>Note de vérification<textarea name="notes">${esc(scene.review?.notes || scene.human_review?.notes || '')}</textarea></label><div class="actions"><button type="submit" name="state" value="correct" ${!image ? 'disabled' : ''}>${icon('edit')}À corriger</button><button type="submit" name="state" value="verified" class="primary" ${!image ? 'disabled' : ''}>${icon('check')}Marquer vérifié</button><button type="submit" name="state" value="unreviewed" title="Retirer la validation">À vérifier</button></div></form></div></article>`;
    }).join('')}`;
    $$('[data-generate]').forEach((button) => {
      const article = button.closest('[data-scene]');
      const scene = project.scenes.find((candidate) => String(candidate.id) === button.dataset.generate);
      button.onclick = () => openGeneration(scene, article);
      $('[name="prompt"]', article)?.addEventListener('input', (event) => {
        const reason = generationBlockReason(project, scene, event.target.value);
        button.disabled = Boolean(reason);
        button.title = reason || 'Refaire uniquement ce plan';
      });
    });
    $$('.scene-form').forEach((form) => form.onsubmit = (event) => {
      event.preventDefault();
      const sid = form.closest('[data-scene]').dataset.scene;
      action(event.submitter, async () => {
        const scenes = project.scenes.map((scene) => {
          const article = $$('[data-scene]').find((element) => element.dataset.scene === String(scene.id));
          const prompt = $('[name="prompt"]', article);
          return prompt ? { ...scene, prompt: prompt.value } : scene;
        });
        await api(`/api/workspace/projects/${encode(project.id)}/scenes`, { method: 'PUT', body: { scenes } }); await route();
      }, 'Prompt enregistré.');
    });
    $$('.review-form').forEach((form) => form.onsubmit = (event) => {
      event.preventDefault();
      action(event.submitter, async () => {
        const notes = $('[name="notes"]', form).value;
        const state = event.submitter?.value;
        if (state === 'correct' && !notes.trim()) throw new Error('Précisez la correction demandée pour cette image.');
        const sid = form.closest('[data-scene]').dataset.scene;
        const scene = project.scenes.find((s) => String(s.id) === sid);
        const authored = $('[name="prompt"]', form.closest('[data-scene]'));
        if (authored && authored.value !== scene.prompt) throw new Error('Enregistrez le prompt avant de vérifier l’image.');
        await api(`/api/workspace/projects/${encode(project.id)}/review`, { method: 'POST', body: { scene_id: scene.id, state, notes } }); await route();
      }, 'État de vérification enregistré.');
    });
  }
  function renderExport() {
    const render = project.render || {};
    const url = mediaUrl('media', project.id, render.file);
    const srt = mediaUrl('media', project.id, render.srt);
    const status = projectStatus(project);
    $('#step-content').innerHTML = `${header('Export', '', badge(status.state, status.label))}${project.technical_issues?.length ? `<div class="banner"><h3>Contrôles techniques à terminer</h3><ul>${project.technical_issues.map((issue) => `<li>${esc(issue)}</li>`).join('')}</ul></div>` : ''}${url ? `<video controls preload="metadata" src="${esc(url)}"></video><div class="actions"><a class="button" href="${esc(url)}" download>${icon('download')}Télécharger le rendu</a>${srt ? `<a class="button" href="${esc(srt)}" download>${icon('download')}Sous-titres</a>` : ''}</div>${project.publication_ready !== true ? '<div class="banner">Rendu disponible. La vérification avant publication reste à terminer.</div>' : '<div class="banner good">Validation avant publication enregistrée.</div>'}<section class="section editor"><h2>Vérification du rendu</h2>${scopeReview('render')}</section>` : '<div class="empty"><h2>Aucun rendu disponible</h2><p>Le projet attend son montage et son export.</p></div>'}<section class="section"><h2>Modèles du projet</h2><dl class="definition-list"><div><dt>Texte</dt><dd>${esc(project.model_snapshot?.text_model || project.settings?.script?.model || 'Non renseigné')}</dd></div><div><dt>Images</dt><dd>${esc(project.model_snapshot?.image_model || project.settings?.visuals?.image_model || 'Non renseigné')}</dd></div></dl></section>`;
    bindScopeReviews();
  }
  function profilePreview(profile, kind) {
    const value = profile[`${kind}_preview`] || profile[`${kind}_preview_url`];
    return value ? mediaUrl('style-media', profile.style_id, value) : '';
  }
  function renderChannels(id) {
    const profile = data.profiles.find((p) => p.id === id);
    if (profile) { renderChannel(profile); return; }
    main.innerHTML = `${header('Chaînes', `${data.profiles.length} chaînes de production`)}<div class="channels-grid">${data.profiles.map((p) => `<section class="channel-item"><h2><a href="#/channels/${encode(p.id)}">${esc(p.name)}</a></h2><div class="previews"><figure>${preview(profilePreview(p, 'video'), `Style vidéo · ${p.name}`)}<figcaption>Exemple commun de style vidéo · personnages blancs</figcaption></figure><figure>${preview(profilePreview(p, 'thumbnail'), `Proposition de miniature · ${p.name}`)}<figcaption>Miniature · humains expressifs · à valider</figcaption></figure></div><div class="inline"><span class="muted small">${data.projects.filter((v) => (v.profile_id || v.channel_id) === p.id).length} vidéos</span><a class="button" href="#/channels/${encode(p.id)}">Ouvrir la chaîne ${icon('next')}</a></div></section>`).join('')}</div>${!data.profiles.length ? '<div class="empty"><h2>Aucune chaîne disponible</h2><p>Les profils du studio doivent être initialisés.</p></div>' : ''}${advanced([['styles/pov-history', 'POV style avancé'], ['planning', 'Calendrier des chaînes']])}`;
  }
  function profileRefs(profile) { return profile.references || []; }
  function refFile(ref) { return typeof ref === 'string' ? ref : ref.file || ref.path || ''; }
  function renderChannel(profile) {
    const refs = profileRefs(profile);
    main.innerHTML = `<div class="breadcrumbs"><a href="#/channels">Chaînes</a><span>/</span>${esc(profile.name)}</div>${header(profile.name, profile.setting || '', `<button id="channel-create" class="primary">${icon('plus')}Nouvelle vidéo</button>`)}<div class="previews editor"><figure>${preview(profilePreview(profile, 'video'), 'Style vidéo')}<figcaption>Exemple commun de style vidéo · personnages blancs</figcaption></figure><figure>${preview(profilePreview(profile, 'thumbnail'), 'Proposition de miniature')}<figcaption>Proposition de miniature · à valider</figcaption></figure></div><section class="section editor"><h2>POV style · commun aux cinq chaînes</h2><form id="style-form"><div class="form-grid"><label class="full">Prompt de style vidéo<textarea name="style_prompt" rows="10">${esc(profile.style_prompt || '')}</textarea></label><label class="full">Prompt de style miniature<textarea name="thumbnail_prompt" rows="5">${esc(profile.thumbnail_prompt || '')}</textarea></label></div><div class="form-actions"><button type="submit" class="primary">Enregistrer le style</button></div></form></section><section class="section editor"><h2>Captures de style</h2>${profile.reference_status === 'pending' || profile.reference_status === 'waiting_for_user_references' || profile.reference_update_pending ? '<div class="banner">Nouvelles captures attendues. Références existantes : vidéos du 30 septembre au 2 octobre.</div>' : ''}<ol class="reference-list">${refs.map((ref, index) => `<li><span class="small muted">${index + 1}</span><img src="${esc(typeof ref === 'object' && ref.url ? safeUrl(ref.url) : mediaUrl('style-media', profile.style_id, refFile(ref)))}" alt="Capture de style ${index + 1}" loading="lazy"><span class="ref-label">${esc(typeof ref === 'object' ? ref.label || refFile(ref) : ref)}${typeof ref === 'object' && ref.observed ? `<span class="small muted"> · observée le ${esc(ref.observed)}</span>` : ''}</span><div class="actions"><button type="button" class="icon-button" data-move="${index}" data-direction="-1" title="Monter la référence" aria-label="Monter la référence ${index + 1}" ${index === 0 ? 'disabled' : ''}>${icon('up')}</button><button type="button" class="icon-button" data-move="${index}" data-direction="1" title="Descendre la référence" aria-label="Descendre la référence ${index + 1}" ${index === refs.length - 1 ? 'disabled' : ''}>${icon('down')}</button></div></li>`).join('')}</ol><form id="refs-upload"><label>Ajouter des captures, dans l’ordre<input name="files" type="file" accept="image/png,image/jpeg,image/webp" multiple required></label><div class="form-actions"><button type="submit">${icon('plus')}Ajouter les captures</button></div><p id="upload-progress" class="small muted" role="status"></p></form></section><section class="section"><h2>Vidéos de la chaîne</h2>${projectTable(data.projects.filter((p) => (p.profile_id || p.channel_id) === profile.id))}</section>${advanced([[`styles/${encode(profile.style_id)}`, 'Style avancé'], ['thumbs', 'Miniatures'], [`planning/${encode(profile.id)}`, 'Calendrier']])}`;
    $('#channel-create').onclick = () => openCreate(profile.id);
    $('#style-form').onsubmit = (event) => {
      event.preventDefault();
      action(event.submitter, async () => { await api(`/api/workspace/profiles/${encode(profile.id)}`, { method: 'PUT', body: { style_prompt: $('[name="style_prompt"]').value, thumbnail_prompt: $('[name="thumbnail_prompt"]').value } }); await route(); }, 'Style enregistré.');
    };
    $$('[data-move]').forEach((button) => button.onclick = () => action(button, async () => {
      const ordered = [...refs];
      const from = Number(button.dataset.move), to = from + Number(button.dataset.direction);
      [ordered[from], ordered[to]] = [ordered[to], ordered[from]];
      await api(`/api/workspace/profiles/${encode(profile.id)}`, { method: 'PUT', body: { references: ordered } }); await route();
    }, 'Ordre des références enregistré.'));
    $('#refs-upload').onsubmit = (event) => {
      event.preventDefault();
      action(event.submitter, async () => {
        const files = [...$('[name="files"]').files];
        let uploaded = 0;
        try {
          for (const file of files) {
            const form = new FormData(); form.append('file', file); form.append('label', file.name);
            await api(`/api/workspace/profiles/${encode(profile.id)}/references`, { method: 'POST', body: form });
            uploaded++; $('#upload-progress').textContent = `${uploaded}/${files.length} captures enregistrées`;
          }
          await route();
        } catch (error) {
          throw new Error(`${uploaded}/${files.length} captures enregistrées. ${error.message} Reprenez avec les fichiers restants.`);
        }
      }, 'Captures enregistrées dans l’ordre.');
    };
  }
  function renderSettings() {
    const catalog = data.models;
    main.innerHTML = `${header('Réglages', 'Modèles et connexion du studio', '<button id="reload-models">' + icon('refresh') + 'Actualiser le catalogue</button>')}${catalogNotice()}<div class="settings-layout"><section class="section"><h2>Modèles par défaut</h2><form id="defaults-form"><div class="form-grid"><label>Texte<select name="text_model" required>${modelOptions(catalog.defaults?.text_model, 'text')}</select></label><label>Images<select name="image_model" required>${modelOptions(catalog.defaults?.image_model, 'image')}</select></label></div><div class="form-actions"><button type="submit" class="primary" ${!modelsFrom(catalog).length ? 'disabled' : ''}>Enregistrer les modèles</button></div></form><section class="section"><h2>Catalogue du proxy</h2><p class="muted small">Disponible dans le proxy. Génération non testée ; capacités selon les métadonnées du catalogue.</p>${modelsFrom(catalog).length ? `<div class="table-wrap"><table><thead><tr><th>Modèle</th><th>Texte</th><th>Image</th></tr></thead><tbody>${modelsFrom(catalog).map((model) => `<tr><td>${esc(model.id)}</td><td>${model.capabilities?.text === true ? 'Annoncé' : model.capabilities?.text === false ? 'Non annoncé' : 'Non confirmé'}</td><td>${model.capabilities?.image === true ? 'Annoncé' : model.capabilities?.image === false ? 'Non annoncé' : 'Non confirmé'}</td></tr>`).join('')}</tbody></table></div>` : '<p class="muted">Aucun modèle disponible.</p>'}</section></section><aside class="section"><h2>Connexion</h2><dl class="definition-list"><div><dt>CLI Proxy</dt><dd>${badge(catalog.available ? 'verified' : 'blocked', catalog.available ? 'Catalogue accessible' : data.connection?.has_proxy ? 'Configuré · catalogue indisponible' : 'À connecter')}</dd></div><div><dt>Catalogue</dt><dd>${modelsFrom(catalog).length} modèles disponibles</dd></div><div><dt>Production</dt><dd>Dirigée par Codex</dd></div></dl>${advanced([['settings', 'Connexion et outils avancés'], ['voices', 'Gestion des voix']])}</aside></div>`;
    $('#reload-models').onclick = (event) => action(event.currentTarget, async () => { data.models = await api('/api/workspace/models?refresh=1'); renderSettings(); }, 'Catalogue actualisé.');
    $('#defaults-form').onsubmit = (event) => {
      event.preventDefault();
      action(event.submitter, async () => {
        const form = new FormData(event.target);
        await api('/api/workspace/settings', { method: 'PUT', body: { text_model: form.get('text_model'), image_model: form.get('image_model') } }); await route();
      }, 'Modèles par défaut enregistrés.');
    };
    bindFormState();
  }
  window.addEventListener('hashchange', () => route());
  window.addEventListener('beforeunload', (event) => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href^="#/"]');
    if (link && dirty && !window.confirm('Quitter cette page sans enregistrer les modifications ?')) event.preventDefault();
  });
  setInterval(() => {
    const page = routeParts()[0] || 'videos';
    if (document.hidden || dirty || submitting || $('#create-dialog').open || $('#preview-dialog').open || !['videos', 'video'].includes(page)) return;
    if (main.contains(document.activeElement) && document.activeElement !== main) return;
    route();
  }, 15000);
  route();
})();
