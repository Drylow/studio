/* TubeForge workspace: authored content, queue creation and explicit human review. */
'use strict';

(function () {
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const encode = encodeURIComponent;
  const base = typeof window !== 'undefined' ? (window.TUBEFORGE_BASE || '') : '';
  const backendPath = path => base && !path.startsWith(base + '/') ? base + path : path;
  const stateLabels = { idle: "Not started", queued: "Queued", pending: "Pending", running: "In progress", done: "Done", error: "Error", failed: "Failed", verified: "Verified", correct: "Needs correction", unreviewed: "Needs review", stale: "Review again", blocked: "Blocked", queued_for_authoring: "Queued · script needed", waiting_for_script: "Script needed", waiting_for_voiceover: "Voiceover needed", waiting_for_scenes: "Shots needed", waiting_for_images: "Images needed", ready_to_render: "Verified · ready to edit", awaiting_review: "Needs review", needs_correction: "Needs correction", rendered_awaiting_review: "Export available · needs review", publication_ready: "Approved for publishing" };
  const stateLabel = (state) => stateLabels[state] || (state ? String(state) : "Not specified");
  Object.assign(stateLabels, { technical_review_required: "Technical check required", rendered_qa_pending: "Export available · check pending", legacy_readonly: "Advanced project" });
  const stepState = (project, key) => project.steps?.[key]?.state || 'idle';
  function projectStatus(project) {
    if (typeof project.review_state === 'string' && project.review_state) return { state: project.review_state, label: stateLabel(project.review_state) };
    if (project.error) return { state: 'error', label: "Error" };
    if (project.running) return { state: 'running', label: "In progress" };
    if (project.publication_ready === true) return { state: 'verified', label: "Approved for publishing" };
    if (project.render?.file) return { state: 'unreviewed', label: "Export available · needs review" };
    const states = Object.values(project.steps || {}).map((step) => step.state);
    if (states.includes('error')) return { state: 'error', label: "Step failed" };
    const actual = typeof project.review_state === 'string' ? project.review_state : project.status || project.workspace_queue?.state || 'idle';
    return { state: actual, label: stateLabel(actual) };
  }
  function modelsFrom(catalog) {
    return (Array.isArray(catalog?.models) ? catalog.models : []).filter((m) => m && typeof m.id === 'string' && m.id.length);
  }
  function validateProject(row, models, profiles) {
    const profile = profiles.find(p => p.id === row.profile_id);
    if (!profile) throw new Error("Choose an available channel.");
    if (!row.title.trim()) throw new Error("Enter the video title.");
    if (row.title.trim().length > 240) throw new Error("The title is limited to 240 characters.");
    if (row.custom_script !== undefined) validateScript(row.custom_script);
    if (!row.custom_script?.trim() && (!Number.isFinite(row.duration_minutes) || row.duration_minutes < (profile.duration_minutes_min || 3) || row.duration_minutes > (profile.duration_minutes_max || 30))) throw new Error("The target duration must be between 3 and 30 minutes.");
    for (const key of ['text_model', 'image_model']) {
      const entry = models.find((m) => m.id === row[key] && (key !== 'image_model' || !row.image_provider || (m.provider || 'cli_proxy') === row.image_provider));
      if (!entry) throw new Error("Choose both models from the provider catalog.");
      if (entry.capabilities?.[key === 'text_model' ? 'text' : 'image'] === false) throw new Error("This model does not declare the selected capability. Select another model.");
    }
    return row;
  }
  function validateScript(text) {
    if (typeof text !== 'string' || text.includes('\0') || new TextEncoder().encode(text).length > 1024 * 1024) throw new Error("The script must be text under 1 MB, with no null characters.");
    return text;
  }
  function scriptDuration(text) {
    const words = String(text || '').trim().split(/\s+/).filter(Boolean).length;
    return { kind: words ? 'estimated' : 'unknown', seconds: words ? words * 60 / 145 : null, word_count: words, words_per_minute: 145 };
  }
  function durationLabel(info) {
    if (!info || !Number.isFinite(info.seconds) || info.seconds <= 0) return "Duration to be determined";
    const seconds = Math.max(1, Math.round(info.seconds));
    const time = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
    return `${info.kind === 'actual' ? "Actual duration" : info.kind === 'estimated' ? "Estimated duration: about" : "Target duration"}${info.kind === 'estimated' ? ' ' : ': '}${time}`;
  }
  function voiceProgressInfo(p) {
    const step = p?.steps?.voiceover || {};
    return { active: Boolean(p?.running && step.state === 'running'),
      percent: step.total > 1 && Number.isFinite(step.done) ? Math.max(0, Math.min(100, step.done * 100 / step.total)) : null,
      started: Number.isFinite(step.started) ? step.started : null };
  }
  async function readScriptFile(file) {
    if (!file || !/\.(txt|md)$/i.test(file.name) || file.size > 1024 * 1024) throw new Error("Choose a .txt or .md file under 1 MB.");
    let text;
    try { text = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer()); }
    catch { throw new Error("The file is unreadable. Use text saved in UTF-8."); }
    return validateScript(text);
  }
  function safeUrl(value) {
    if (typeof value !== 'string' || !value || /[\x00-\x20\\]/.test(value)) return '';
    if (value.startsWith('/') && !value.startsWith('//')) return backendPath(value);
    return '';
  }
  function mediaUrl(kind, id, file) {
    if (!file || typeof file !== 'string') return '';
    if (file.startsWith('/')) return safeUrl(file);
    const parts = file.split('/');
    if (parts.some((part) => part === '..' || part === '.') || file.includes('\\') || file.includes(':')) return '';
    return backendPath(`/${kind}/${encode(id)}/${parts.map(encode).join('/')}`);
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
    if (project?.codex_directed !== true || project.readonly || project.mode !== 'review') return "Generating an outline is reserved for guided projects.";
    if (project.running || (project.workspace_batch?.state !== 'interrupted' && ['running', 'queued'].includes(scene?.status))) return "An operation is already in progress on this project.";
    if (typeof scene?.prompt !== 'string' || !scene.prompt.trim() || /^renderer[- ]only\b/i.test(scene.prompt.trim())) return "This outline has no explicit generation prompt.";
    if (editedPrompt !== scene.prompt) return "Save the prompt before remaking this outline.";
    if (!sceneReferences(scene).length) return "Add the outline's ordered references before remaking it.";
    if (sceneReferences(scene).some((ref) => ref?.exists === false)) return "An outline reference is missing.";
    if (!project.model_snapshot?.image_model) return "The project's image model is not specified.";
    return '';
  }
  function generationBody(project, scene, editedPrompt = scene?.prompt) {
    const reason = generationBlockReason(project, scene, editedPrompt);
    if (reason) throw new Error(reason);
    const body = { confirm_prompt: scene.prompt, image_model: project.model_snapshot.image_model };
    if (project.model_snapshot.image_provider) body.image_provider = project.model_snapshot.image_provider;
    return body;
  }
  function referenceOrder(references) {
    return references.map((ref) => typeof ref === 'string' ? { path: ref, owner: 'project' } : { path: ref.path || ref.file || ref.image, owner: ref.owner || 'project', sha256: ref.sha256 || null });
  }
  const hasImage = (scene) => scene.image_available ?? Boolean(scene.image);
  function batchPlan(project, phase) {
    const scenes = project.scenes || [];
    const first = scenes.slice(0, 3);
    const candidates = phase === 'preview' ? first : scenes.slice(3);
    const targets = candidates.filter((scene) => scene.workspace_regeneration_required === true || phase !== 'corrections' && !hasImage(scene));
    let reason = '';
    if (!scenes.length) reason = "First save the breakdown, prompts, and references.";
    else if (project.running) reason = "Generation is already in progress.";
    else if (phase !== 'preview' && first.some((scene) => !hasImage(scene) || scene.human_review?.state !== 'verified')) reason = "Review and mark the first three shots as verified to continue.";
    else if (!targets.length) reason = phase === 'corrections' ? "No shots marked to remake." : "The images for this step already exist.";
    else reason = targets.map((scene) => generationBlockReason(project, scene)).find(Boolean) || '';
    if (!reason && !project.generation_confirmation) reason = "Refresh the project before generating its images.";
    return { first, targets, reason };
  }
  function createReadCache(read, ttl = 15000, now = Date.now, { staleWhileRevalidate = false, onError = () => {} } = {}) {
    const entries = new Map();
    let revision = 0;
    return {
      clear() { revision++; entries.clear(); },
      peek(path) { return entries.get(path)?.value; },
      get(path, refresh = false) {
        const previous = entries.get(path);
        if (!refresh && previous && (previous.pending || now() - previous.time < ttl)) return staleWhileRevalidate && previous.cachedPromise ? previous.cachedPromise : previous.promise;
        const version = revision;
        const entry = { pending: true, time: now(), promise: null, cachedPromise: previous?.cachedPromise || null, value: previous?.value };
        entry.promise = Promise.resolve().then(() => read(path)).then(value => {
          if (version === revision && entries.get(path) === entry) { entry.pending = false; entry.time = now(); entry.cachedPromise = entry.promise; entry.value = value; }
          return value;
        }, error => {
          if (entries.get(path) === entry) entries.delete(path);
          throw error;
        });
        entries.set(path, entry);
        if (!refresh && staleWhileRevalidate && entry.cachedPromise) {
          entry.promise.catch(onError);
          return entry.cachedPromise;
        }
        return entry.promise;
      }
    };
  }
  function scenePage(scenes, requested = 0, size = 24) {
    const pages = Math.max(1, Math.ceil(scenes.length / size));
    const page = Math.min(pages - 1, Math.max(0, Number.isFinite(requested) ? Math.floor(requested) : 0));
    const start = page * size;
    return { page, pages, start, end: Math.min(scenes.length, start + size), rows: scenes.slice(start, start + size) };
  }
  const helpers = { createReadCache, scenePage, escapeHtml, projectStatus, modelsFrom, validateProject, validateScript, readScriptFile, safeUrl, mediaUrl, stateLabel, referenceUrl, statusGroup, generationBlockReason, generationBody, referenceOrder, batchPlan, scriptDuration, durationLabel, voiceProgressInfo };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = helpers;
    if (require.main === module && process.argv.includes('--test')) {
      const assert = require('node:assert/strict');
      let checks = 0;
      const check = (test) => { test(); checks++; };
      check(() => assert.equal(projectStatus({ review_state: 'needs_correction', render: { file: 'video.mp4' } }).state, 'needs_correction'));
      check(() => assert.equal(projectStatus({ review_state: 'waiting_for_script' }).label, "Script needed"));
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
      const row = { profile_id: 'profile', title: "Video", duration_minutes: 22, text_model: 'catalog-text', image_model: 'catalog-image' };
      check(() => assert.equal(validateProject(row, models, profiles), row));
      check(() => assert.throws(() => validateProject({ ...row, duration_minutes: 31 }, models, profiles)));
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
      const approved = { ...authored, image: 'approved.png', human_review: { state: 'verified' } };
      const repair = { ...approved, id: 4, workspace_regeneration_required: true };
      check(() => assert.deepEqual(batchPlan({ ...directed, generation_confirmation: 'confirmed', scenes: [approved, approved, approved, repair, { ...approved, id: 5 }] }, 'remaining').targets.map((s) => s.id), [4]));
      const correctionProject = { ...directed, generation_confirmation: 'confirmed', scenes: [approved, approved, approved, repair, { ...authored, id: 5 }, { ...approved, id: 6 }] };
      check(() => assert.deepEqual(batchPlan(correctionProject, 'corrections').targets.map((s) => s.id), [4]));
      check(() => assert.equal(batchPlan(correctionProject, 'corrections').reason, ''));
      check(() => assert.match(batchPlan({ ...correctionProject, scenes: [authored, approved, approved, repair] }, 'corrections').reason, /first three/));
      process.stdout.write(`${checks} focused checks passed\n`);
    }
  }
  if (typeof document === 'undefined') return;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const main = $('#main');
  $('.primary-nav a[data-nav="styles"]')?.remove();
  const channelNavigation = $('.primary-nav a[data-nav="channels"]');
  if (channelNavigation) channelNavigation.textContent = 'Channels & presets';
  const esc = escapeHtml;
  const icon = (name) => `<span aria-hidden="true">${({ plus: '&#43;', refresh: '&#8635;', close: '&#215;', back: '&#8592;', next: '&#8594;', up: '&#8593;', down: '&#8595;', check: '&#10003;', edit: '&#9998;', download: '&#8595;', external: '&#8599;' })[name] || '&#183;'}</span>`;
  const badge = (state, label = stateLabel(state)) => `<span class="badge ${['verified', 'done', 'publication_ready'].includes(state) ? 'good' : ['error', 'failed'].includes(state) ? 'error' : ['correct', 'stale', 'blocked', 'needs_correction'].includes(state) ? 'warn' : ''}">${esc(label)}</span>`;
  const legacy = (route, label) => `<a class="button" href="${base}/legacy.html#/${route}">${icon('external')}${esc(label)}</a>`;
  const advanced = (items) => `<details class="advanced"><summary>Advanced tools</summary><div class="inline">${items.map(([path, label]) => legacy(path, label)).join('')}</div></details>`;
  const fmtTime = (seconds) => {
    if (!Number.isFinite(Number(seconds))) return "Not aligned";
    const total = Math.max(0, Math.round(Number(seconds)));
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
  };
  const fmtDate = (value) => value ? new Date(typeof value === 'number' ? value * 1000 : value).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
  const projectHref = (p) => p.readonly ? `${base}/legacy.html#/p/${encode(p.id)}/script` : `#/video/${encode(p.id)}/text`;
  const profileName = (id) => data.profiles.find((p) => p.id === id)?.name || id || "No channel";
  let data = { profiles: [], styles: [], projects: [], batches: [], models: { models: [] }, settings: {}, connection: {} };
  let project = null;
  const scenePages = new Map();
  let epoch = 0;
  let dirty = false;
  let submitting = false;
  let listFilters = { search: '', profile: '', status: '' };
  let batchRows = [];
  let management = { channels: [], styles: [] };
  let managementFilters = { channels: '', styles: '', archivedChannels: false, archivedStyles: false };
  let session = null;
  let dataReady = false;
  let workspaceScope = 'mine';
  function renderAccount() {
    $('#account').hidden = true;
    const name = $('#me-name'), avatar = $('#me-avatar');
    if (name && session) name.textContent = session.display_name;
    if (avatar && session) { avatar.textContent = session.display_name.split(/\s+/).slice(0,2).map(p => p[0]).join('').toUpperCase(); avatar.title = session.display_name; }
  }
  function renderLogin() {
    session = null; project = null;
    navigationReads.clear();
    data = { profiles: [], styles: [], projects: [], batches: [], models: { models: [] }, settings: {}, connection: {} };
    management = { channels: [], styles: [] };
    dataReady = false;
    $('#account').hidden = true;
    if (typeof window.kanyeRequireLogin === 'function') window.kanyeRequireLogin();
    main.innerHTML = '<div class="empty"><h2>Sign in to your studio</h2><p>Use your existing tools.kanye.studio access key.</p></div>';
    main.setAttribute('aria-busy','false');
  }
  function renderTeam() {
    main.innerHTML = header('Team','Accounts are managed by the existing portal.') + '<a class="button" href="/channels">Channels &amp; Team</a>';
  }
  const STEPS = [["text", "Script", 'script'], ["voice", "Voice", 'voiceover'], ['images', 'Images', 'visuals'], ['verification', "Verification", null], ['export', 'Export', 'render']];

  async function api(path, options = {}) {
    const request = { method: options.method || 'GET', headers: { Accept: 'application/json' }, cache: 'no-store' };
    if (options.body instanceof FormData) request.body = options.body;
    else if (options.body !== undefined) { request.body = JSON.stringify(options.body); request.headers['Content-Type'] = 'application/json'; }
    const response = await fetch(backendPath(path), request);
    let payload;
    try { payload = await response.json(); } catch { payload = null; }
    if (!response.ok) {
      if (response.status === 401 && !path.endsWith('/login')) { session = null; const error = new Error('Sign in to TubeForge.'); error.status = 401; throw error; }
      const detail = payload?.detail || payload?.error;
      const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((item) => item.msg || "Invalid data").join(' · ') : `Error ${response.status}`;
      throw new Error(`${message}${response.status === 404 ? " · This studio feature is unavailable. Refresh after it has been updated." : ''}`);
    }
    if (payload === null) throw new Error("Unreadable studio response. Check the server, then try again.");
    if (request.method !== 'GET') navigationReads.clear();
    return payload;
  }
  const navigationReads = createReadCache(path => api(path), 15000, Date.now, {
    staleWhileRevalidate: true,
    onError: error => { if (error.status === 401) renderLogin(); }
  });
  const projectReadPath = id => `/api/workspace/projects/${encode(id)}?view=ui`;
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
    catch (error) { notify(error.message || "Server unreachable. Check its connection, then try again.", true); }
    finally { submitting = false; if (button?.isConnected) button.disabled = false; }
  }
  async function refreshData(refresh = true) {
    const result = await navigationReads.get('/api/workspace', refresh);
    data = { ...data, ...result, profiles: result.profiles || [], projects: result.projects || [], models: result.models || { models: [] } };
    dataReady = true;
    const available = data.models.available === true;
    const flow = data.models.providers?.google_flow;
    $('#connection').textContent = flow?.available ? `Google Flow · ${flow.accounts.filter((a) => a.health === 'OK').length} comptes disponibles${data.models.providers?.cli_proxy?.available ? " · Text CLI Proxy" : ''}` : available ? `Proxy · ${modelsFrom(data.models).length} models` : data.connection?.has_proxy ? 'Proxy · catalogue indisponible' : "Proxy not connected";
  }
  function modelOptions(selected = '', kind = '', selectedProvider = '') {
    const imagePolicy = selectedProvider || data.models.image_provider_policy;
    const models = modelsFrom(data.models).filter((m) => kind !== 'image' || !imagePolicy || m.provider === imagePolicy);
      const renderOption = (m) => {
      const capability = m.capabilities?.[kind];
      const capabilityLabel = capability === false ? "Usage not declared" : capability == null ? "Capacity not confirmed" : "Capacity declared in the catalog";
      return `<option value="${esc(m.id)}" data-provider="${esc(m.provider || 'cli_proxy')}" title="${capabilityLabel}" ${m.id === selected && (!selectedProvider || (m.provider || 'cli_proxy') === selectedProvider) ? 'selected' : ''} ${capability === false ? 'disabled' : ''}>${esc(m.label || 'CLI Proxy · ' + m.id)}</option>`;
    };
    const likely = models.filter((m) => m.capabilities?.[kind] === true || m.capabilities?.[kind] == null && m.suggested_role === kind);
    const others = models.filter((m) => !likely.includes(m));
    const choices = `${likely.length ? `<optgroup label="${kind === 'image' ? 'Images' : "Text"} · declared or suggested usage">${likely.map(renderOption).join('')}</optgroup>` : ''}${others.length ? `<optgroup label="Other models / capacity to confirm">${others.map(renderOption).join('')}</optgroup>` : ''}`;
    const unavailable = selected && !models.some((m) => m.id === selected && (!selectedProvider || (m.provider || 'cli_proxy') === selectedProvider)) ? `<option value="" selected>${esc(selected)} · indisponible</option>` : '';
    return `${unavailable}<option value="" ${!selected ? 'selected' : ''}>${models.length ? "Choose a model" : 'Catalogue indisponible'}</option>${choices}`;
  }
  function catalogNotice() {
    return modelsFrom(data.models).length ? '' : `<div class="banner error">${esc(data.models.error || "The proxy provides no models. Check its connection in Settings, then refresh the catalog.")} <a href="#/settings">Settings</a></div>`;
  }
  function catalogStatus() {
    return modelsFrom(data.models).length ? "<p class=\"catalog-status small muted\">The chosen provider is saved with the video. Quotas depend on the connected account.</p>" : '';
  }
  function bindFormState(root = main) {
    $$('input, textarea, select', root).forEach((input) => {
      if (input.type !== 'file' && !input.hasAttribute('data-preview-select') && !input.closest('.toolbar') && !input.dataset.dirtyBound) {
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
  function profileOptions(selected = '', empty = "Choose a channel") {
    return `<option value="">${esc(empty)}</option>${data.profiles.map((p) => `<option value="${esc(p.id)}" ${p.id === selected ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}`;
  }
  function preview(src, label) {
    const url = safeUrl(src);
    return url ? `<button type="button" class="preview-open" data-preview="${esc(url)}" aria-label="Agrandir : ${esc(label)}"><img class="preview" src="${esc(url)}" alt="${esc(label)}" loading="lazy"></button>` : `<div class="preview-empty">No preview</div>`;
  }
  function bindPreviews(root = main) {
    $$('[data-preview]', root).forEach((button) => button.onclick = () => {
      const dialog = $('#preview-dialog');
      dialog.classList.remove('generation-dialog');
      dialog.setAttribute('aria-label', "Image preview");
      dialog.innerHTML = `<div class="dialog-head"><h2>Preview</h2><button class="icon-button" data-close title="Close" aria-label="Close">${icon('close')}</button></div><img src="${esc(button.dataset.preview)}" alt="Expanded preview">`;
      $('[data-close]', dialog).onclick = () => dialog.close();
      dialog.showModal();
    });
    $$('img', root).forEach((img) => img.addEventListener('error', () => {
      const message = document.createElement('span');
      message.className = 'preview-empty'; message.textContent = "Preview unavailable";
      img.replaceWith(message);
    }, { once: true }));
  }
  function header(title, subtitle, controls = '') {
    return `<div class="page-head"><div><h1>${esc(title)}</h1>${subtitle ? `<p>${esc(subtitle)}</p>` : ''}</div><div class="actions">${controls}</div></div>`;
  }
  function routeParts() {
    const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean).map((part) => { try { return decodeURIComponent(part); } catch { return part; } });
    if (parts[0] === 'video') parts[2] = ({texte:'text', voix:'voice'})[parts[2]] || parts[2];
    return parts;
  }
  function paintPage(page, parts, detail) {
    if (page === 'videos') renderDashboard();
    else if (page === 'queue') renderBatch();
    else if (page === 'video') { project = detail; renderProject(parts[2] || 'text'); }
    else if (page === 'channels') renderChannels(parts[1], parts[2]);
    else if (page === 'styles') renderStyles(parts[1]);
    else if (page === 'settings') renderSettings();
    else if (page === 'team') renderTeam();
    else main.innerHTML = `${header('Page not found', '')}<a href="#/videos">Back to videos</a>`;
    bindPreviews();
    bindFormState();
  }
  async function route({ refresh = true } = {}) {
    const currentEpoch = ++epoch;
    let parts = routeParts();
    if (parts[0] === 'batch') { history.replaceState(null, '', '#/queue'); parts = ['queue']; }
    if (parts[0] === 'projects') parts = ['videos'];
    if (parts[0] === 'p') parts = ['video', parts[1], ({ script: "text", voice: "voice", visuals: 'images', render: 'export', thumbs: 'export' })[parts[2]] || "text"];
    const page = parts[0] || 'videos';
    $$('.primary-nav a').forEach((link) => {
      const active = link.dataset.nav === (page === 'video' || page === 'queue' ? 'videos' : page === 'styles' ? 'channels' : page);
      if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    });
    main.setAttribute('aria-busy', 'true');
    let painted = false;
    if (!refresh && session && dataReady) {
      const cachedProject = page === 'video' ? navigationReads.peek(projectReadPath(parts[1] || '')) : null;
      const cachedManagement = navigationReads.peek('/api/workspace/management');
      if (cachedManagement) management = cachedManagement;
      if ((page !== 'video' || cachedProject) && (!['channels', 'styles'].includes(page) || cachedManagement)) {
        dirty = false;
        paintPage(page, parts, cachedProject);
        painted = true;
      }
    }
    if (!painted && (!refresh || !main.children.length)) {
      const title = page === 'video' ? data.projects.find(p => p.id === parts[1])?.title || 'Video' :
        ({ videos: 'Videos', queue: 'Video queue', channels: 'Channels', styles: 'Visual styles', settings: 'Settings', team: 'Team' })[page] || 'Studio';
      main.innerHTML = header(title, '') + '<div class="empty" role="status">Loading details…</div>';
    }
    try {
      if (!session) {
        session = await api('/api/workspace/session');
        document.body.classList.remove('signed-out'); renderAccount();
      }
      const [, detail, managed] = await Promise.all([
        refreshData(refresh),
        page === 'video' ? navigationReads.get(projectReadPath(parts[1] || ''), refresh) : null,
        ['channels', 'styles'].includes(page) ? navigationReads.get('/api/workspace/management', refresh) : null
      ]);
      if (currentEpoch !== epoch) return;
      if (painted && (dirty || $('#preview-dialog').open || $('#create-dialog').open)) return;
      if (managed) management = managed;
      dirty = false;
      paintPage(page, parts, detail);
      if (!refresh && painted) main.dataset.navigation = 'cached';
      navigationReads.get('/api/workspace/management').catch(error => { if (error.status === 401) renderLogin(); });
      document.title = `${page === 'video' ? project.title : ({ videos: "Videos", queue: "Video queue", channels: "Channels", styles: "Visual styles", settings: "Settings", team: 'Team' })[page] || 'Studio'} | TubeForge`;
    } catch (error) {
      if (currentEpoch === epoch) {
        if (error.status === 401) { renderLogin(); return; }
        main.innerHTML = `${header("Studio unavailable", '')}<div class="banner error">${esc(error.message)}</div><button id="retry">${icon('refresh')}Try again</button>`;
        $('#retry').onclick = () => route();
      }
    } finally { if (currentEpoch === epoch) main.setAttribute('aria-busy', 'false'); }
  }
  function projectTable(projects) {
    if (!projects.length) return "<div class=\"empty\"><h2>No videos</h2><p>Create a video or prepare a batch for this channel.</p></div>";
    return `<div class="table-wrap"><table><thead><tr><th scope="col">Video</th><th scope="col">Channel</th><th scope="col">Duration</th><th scope="col">Status</th><th scope="col">Updated</th></tr></thead><tbody>${projects.map((p) => {
      const status = projectStatus(p);
      const thumb = mediaUrl('media', p.id, p.thumb || p.thumbnail?.file);
      return `<tr><td><div class="project-cell">${thumb ? `<img src="${esc(thumb)}" alt="Thumbnail for ${esc(p.title)}" loading="lazy">` : '<span class="project-placeholder">No thumbnail</span>'}<div><a class="project-title" href="${esc(projectHref(p))}">${esc(p.title || "Untitled")}</a><div class="small muted">${p.scenes_count ?? (Array.isArray(p.scenes) ? p.scenes.length : p.scenes) ?? 0} shots${p.owner_id ? ` · ${esc(p.owner_id === session?.username ? session.display_name : p.owner_name || p.owner_id)}` : ''}</div></div></div></td><td>${esc(profileName(p.profile_id || p.channel_id))}</td><td>${esc(durationLabel(p.duration_info))}</td><td>${badge(status.state, status.label)}</td><td class="small muted">${esc(fmtDate(p.updated || p.created))}</td></tr>`;
    }).join('')}</tbody></table></div>`;
  }
  function renderDashboard() {
    main.innerHTML = `${header("Videos", "Projects and production queue", `<a class="button" href="#/queue">${icon('plus')}Create batch</a><button class="primary" id="new-video">${icon('plus')}New video</button>`)}<div class="toolbar"><label class="search">Search<input id="search" type="search" placeholder="Video title" value="${esc(listFilters.search)}"></label><label>Channel<select id="channel-filter">${profileOptions(listFilters.profile, "All channels")}</select></label><label>Status<select id="status-filter"><option value="">All statuses</option>${['queued', 'running', 'unreviewed', 'correct', 'verified', 'error', 'legacy_readonly'].map((s) => `<option value="${s}" ${listFilters.status === s ? 'selected' : ''}>${stateLabel(s)}</option>`).join('')}</select></label><button id="refresh" class="icon-button" title="Refresh projects" aria-label="Refresh projects">${icon('refresh')}</button><span id="project-count" class="count"></span></div><div id="project-list"></div>${advanced([['projects', "Advanced projects"], ['planning', "Schedule"], ['thumbs', "Thumbnails"]])}`;
    main.querySelector('.page-head p').textContent = 'Your production desk · Shared channels and styles';
    main.querySelector('.toolbar').insertAdjacentHTML('beforebegin', `<div class="workspace-tabs" role="group" aria-label="Video workspace"><button data-scope="mine" aria-pressed="${workspaceScope === 'mine'}">My videos</button><button data-scope="team" aria-pressed="${workspaceScope === 'team'}">Team videos</button></div>`);
    $$('[data-scope]').filter(b => b.matches('button')).forEach(button => button.onclick = () => { workspaceScope = button.dataset.scope; renderDashboard(); });
    const update = () => {
      listFilters = { search: $('#search').value, profile: $('#channel-filter').value, status: $('#status-filter').value };
      const projects = data.projects.filter((p) => (workspaceScope === 'team' || (p.owner_id || 'admin') === session?.username) && (!listFilters.search || (p.title || '').toLocaleLowerCase('en').includes(listFilters.search.toLocaleLowerCase('en'))) && (!listFilters.profile || (p.profile_id || p.channel_id) === listFilters.profile) && (!listFilters.status || statusGroup(projectStatus(p).state) === listFilters.status));
      $('#project-list').innerHTML = projectTable(projects);
      $('#project-count').textContent = `${projects.length} video${projects.length === 1 ? '' : 's'}`;
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
    return { profile_id: profile, title: '', duration_minutes: data.profiles.find((p) => p.id === profile)?.target_minutes || 15, text_model: data.models.defaults?.text_model || '', image_model: data.models.defaults?.image_model || '', image_provider: data.models.defaults?.image_provider || 'cli_proxy' };
  }
  function formRow(form) {
    const fields = new FormData(form);
    const row = { profile_id: fields.get('profile_id'), title: String(fields.get('title') || '').trim(), duration_minutes: Number(fields.get('duration_minutes')), text_model: fields.get('text_model'), image_model: fields.get('image_model') };
    if (fields.has('style_id')) row.style_id = fields.get('style_id');
    if (fields.has('custom_script')) row.custom_script = fields.get('custom_script');
    if (!fields.has('duration_minutes')) delete row.duration_minutes;
    row.image_provider = $('[name="image_model"]', form)?.selectedOptions[0]?.dataset.provider || 'cli_proxy';
    return row;
  }
  function scriptImportMarkup(id) {
    return `<div class="script-tools"><label class="file-picker">${icon('up')}Or import a file<input id="${id}" type="file" accept=".txt,.md,text/plain,text/markdown"></label><span class="small muted" data-script-count></span></div><p class="small muted import-status" data-import-status role="status"></p><p class="script-duration small" data-script-duration role="status" aria-live="polite" hidden></p>`;
  }
  function bindScriptImport(root, inputSelector) {
    const input = $(inputSelector, root);
    const fileInput = $('input[type="file"]', root);
    const count = () => {
      const estimate = scriptDuration(input.value);
      $('[data-script-count]', root).textContent = `${estimate.word_count} words`;
      const target = $('[name="duration_minutes"]', root);
      if (target) {
        target.closest('[data-target-duration]').hidden = estimate.word_count > 0;
        target.disabled = estimate.word_count > 0;
        target.required = estimate.word_count === 0;
      }
      const duration = $('[data-script-duration]', root);
      const info = root.id === 'script-form' && input.value === project.script ? project.duration_info : estimate;
      duration.hidden = !estimate.word_count;
      duration.textContent = durationLabel(info) + (info?.kind === 'estimated' ? " · estimate at 145 words/min; actual duration will depend on the voice." : '');
    };
    count(); input.addEventListener('input', count);
    fileInput.onchange = async () => {
      const file = fileInput.files[0];
      if (!file) return;
      const status = $('[data-import-status]', root);
      try {
        const text = await readScriptFile(file);
        if (input.value.trim() && !confirm("Replace the current text with the imported script?")) return;
        input.value = text;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        status.textContent = `${file.name} · imported`;
        status.classList.remove('error-text');
      } catch (error) { status.textContent = error.message; status.classList.add('error-text'); }
      finally { fileInput.value = ''; }
    };
  }
  function openCreate(profile = '') {
    if (dirty) { notify("Save your changes before creating a video.", true); return; }
    const dialog = $('#create-dialog');
    dialog.className = 'create-video-dialog';
    const row = defaultRow(profile);
    const defaultStyle = data.profiles.find((p) => p.id === profile)?.style_id || data.profiles[0]?.style_id;
    const previousDirty = dirty;
    let dialogEdited = false;
    dialog.innerHTML = `<div class="dialog-head"><h2 id="create-heading">New video</h2><button type="button" data-close class="icon-button" title="Close" aria-label="Close">${icon('close')}</button></div>${catalogNotice()}<form id="create-form"><div class="create-layout"><div><fieldset><legend>Project</legend><div class="form-grid"><label class="full">Video title<input name="title" placeholder="Zombie Outbreak: 30 Days Trapped in a Supermarket" required maxlength="240" autocomplete="off"></label><label>Channel<select name="profile_id" required>${profileOptions(row.profile_id)}</select></label><label data-target-duration>Target duration (minutes)<input type="number" name="duration_minutes" min="3" max="30" step="0.5" value="15" required></label></div></fieldset><fieldset class="create-section"><legend>Script</legend>${scriptImportMarkup('create-script-file')}<label>Paste your script here<textarea name="custom_script" rows="12" spellcheck="true" placeholder="Paste your full script here. No TXT file needed."></textarea></label></fieldset></div><div class="create-options"><fieldset><legend>Channel preset</legend><details class="advanced"><summary>Override drawing preset for this video</summary><label>Drawing preset<select name="style_id" required>${data.styles.map((s) => `<option value="${esc(s.id)}" ${s.id === defaultStyle ? 'selected' : ''}>${esc(s.name)}</option>`).join('')}</select></label></details><figure id="create-style-preview" class="create-style-preview"></figure></fieldset><fieldset class="create-section"><legend>Generation models</legend><div class="form-grid"><label class="full">Text model<select name="text_model" required>${modelOptions(row.text_model, 'text')}</select></label><label class="full">Image model<select name="image_model" required>${modelOptions(row.image_model, 'image', row.image_provider)}</select></label></div></fieldset>${catalogStatus()}</div></div><div id="create-error" role="alert"></div><div class="form-actions create-footer"><button type="button" data-close>Cancel</button><button class="primary" type="submit" ${!modelsFrom(data.models).length || !data.profiles.length || !data.styles.length ? 'disabled' : ''}>${icon('plus')}Create video</button></div></form>`;
    const close = () => { if (dialogEdited && !confirm("Discard this new video?")) return; dialog.close(); dirty = previousDirty; };
    $('#create-form', dialog).addEventListener('input', () => { dialogEdited = true; });
    $('#create-form', dialog).addEventListener('change', () => { dialogEdited = true; });
    $$('[data-close]', dialog).forEach((b) => b.onclick = close);
    dialog.oncancel = (event) => { event.preventDefault(); close(); };
    const updatePreview = () => {
      const sid = $('[name="style_id"]', dialog).value;
      const selectedProfile = data.profiles.find((p) => p.id === $('[name="profile_id"]', dialog).value);
      const owner = selectedProfile?.style_id === sid ? selectedProfile : data.profiles.find((p) => p.style_id === sid);
      const url = (owner ? profilePreview(owner, 'video') : '') || data.styles.find((s) => s.id === sid)?.video_preview_url || '';
      $('#create-style-preview', dialog).innerHTML = url ? `<img class="preview" src="${esc(safeUrl(url))}" alt="Video style preview"><figcaption>${esc(data.styles.find((s) => s.id === sid)?.name || '')}</figcaption>` : "<div class=\"preview-empty\">Preview unavailable</div>";
    };
    const applyStyleModel = () => {
      const selected = data.styles.find((s) => s.id === $('[name="style_id"]', dialog).value);
      if (selected?.image_provider && selected.image_model) $('[name="image_model"]', dialog).innerHTML = modelOptions(selected.image_model, 'image', selected.image_provider);
      updatePreview();
    };
    $('[name="style_id"]', dialog).onchange = applyStyleModel;
    $('[name="profile_id"]', dialog).onchange = () => { const selected = data.profiles.find((p) => p.id === $('[name="profile_id"]', dialog).value); if (selected) $('[name="style_id"]', dialog).value = selected.style_id; applyStyleModel(); };
    applyStyleModel();
    $('[name="duration_minutes"]', dialog).value = row.duration_minutes;
    $('[name="profile_id"]', dialog).addEventListener('change', () => { const selected = data.profiles.find((p) => p.id === $('[name="profile_id"]', dialog).value); if (selected) $('[name="duration_minutes"]', dialog).value = selected.target_minutes; });
    bindScriptImport($('#create-form', dialog), '[name="custom_script"]');
    $('#create-form', dialog).onsubmit = (event) => {
      event.preventDefault();
      action($('button[type="submit"]', dialog), async () => {
        try {
          const row = validateProject(formRow(event.target), modelsFrom(data.models), data.profiles);
          const created = await api('/api/workspace/projects', { method: 'POST', body: row });
          dialog.close(); dirty = false;
          location.hash = `#/video/${encode(created.id)}/text`;
        } catch (error) { $('#create-error', dialog).innerHTML = `<div class="banner error">${esc(error.message)}</div>`; throw error; }
      }, "Video created.");
    };
    dialog.showModal();
    bindFormState(dialog);
    $('[name="title"]', dialog).focus();
  }
  function captureBatch() {
    batchRows = $$('#batch-body tr').map((tr) => ({ profile_id: $('[name="profile_id"]', tr).value, title: $('[name="title"]', tr).value, duration_minutes: Number($('[name="duration_minutes"]', tr).value), text_model: $('[name="text_model"]', tr).value, image_model: $('[name="image_model"]', tr).value }));
    $$('#batch-body tr').forEach((tr, i) => { batchRows[i].image_provider = $('[name="image_model"]', tr).selectedOptions[0]?.dataset.provider || 'cli_proxy'; });
  }
  function renderBatch() {
    if (!batchRows.length) batchRows = [defaultRow(), defaultRow()];
    main.innerHTML = `${header("Video queue", "Prepare multiple projects", "<a class=\"button\" href=\"#/videos\">Videos</a>")}${catalogNotice()}<form id="batch-form"><div class="table-wrap"><table class="batch-table"><thead><tr><th>Channel</th><th>Title</th><th>Minutes</th><th>Text model</th><th>Image model</th><th><span class="small">Remove</span></th></tr></thead><tbody id="batch-body">${batchRows.map((row, index) => `<tr><td data-label="Channel"><select aria-label="Video channel ${index + 1}" name="profile_id" required>${profileOptions(row.profile_id)}</select></td><td data-label="Title"><input class="title-input" aria-label="Video title ${index + 1}" name="title" maxlength="240" required value="${esc(row.title)}"></td><td data-label="Target duration (minutes)"><input class="duration-input" aria-label="Video duration ${index + 1}" name="duration_minutes" type="number" min="3" max="30" step="0.5" required value="${row.duration_minutes}"></td><td data-label="Text model"><select aria-label="Video text model ${index + 1}" name="text_model" required>${modelOptions(row.text_model, 'text')}</select></td><td data-label="Image model"><select aria-label="Video image model ${index + 1}" name="image_model" required>${modelOptions(row.image_model, 'image', row.image_provider)}</select></td><td><button type="button" data-remove="${index}" class="icon-button" aria-label="Remove video ${index + 1}" title="Remove this row" ${batchRows.length === 1 ? 'disabled' : ''}>${icon('close')}</button></td></tr>`).join('')}</tbody></table></div>${catalogStatus()}<div class="form-actions"><button type="button" id="add-row">${icon('plus')}Add a row</button><button class="primary" type="submit" ${!modelsFrom(data.models).length || !data.profiles.length ? 'disabled' : ''}>${icon('plus')}Add batch to queue</button></div><div id="batch-error" role="alert"></div></form><section class="section"><h2>Saved batches</h2>${data.batches?.length ? `<div class="table-wrap"><table><thead><tr><th>Batch</th><th>Videos</th><th>Created</th></tr></thead><tbody>${data.batches.map((batch) => `<tr><td>${esc(batch.name || batch.id)}</td><td>${(batch.projects || []).length}</td><td>${esc(fmtDate(batch.created))}</td></tr>`).join('')}</tbody></table></div>` : "<p class=\"muted\">No saved batches.</p>"}</section>`;
    $('#batch-form').insertAdjacentHTML('beforebegin', `<section class="section"><h2>Production queue</h2><p class="muted">Voice first, then shots and images. Reviews remain required. Two image batches share the provider limit; renders wait their turn.</p><div class="toolbar"><label>Existing videos<select id="production-selection" multiple size="5">${data.projects.filter(p => p.codex_directed && !p.archived && !p.render).map(p => `<option value="${esc(p.id)}">${esc(p.title)}</option>`).join('')}</select></label><button id="enqueue-production" class="primary">Start selected videos</button></div><div id="production-jobs" aria-live="polite"><p role="status">Loading production queue…</p></div></section>`);
    $('#enqueue-production').onclick = event => action(event.currentTarget, async () => {
      const ids = Array.from($('#production-selection').selectedOptions, option => option.value);
      if (!ids.length) throw new Error('Choose at least one existing video.');
      await api('/api/forge/v1/queue', {method:'POST', body:{project_ids:ids}});
      await renderProductionQueue();
    }, 'Videos added to the production queue.');
    renderProductionQueue();
    $('#add-row').onclick = () => { captureBatch(); batchRows.push(defaultRow()); renderBatch(); };
    $$('#batch-body select[name="profile_id"]').forEach((select) => select.onchange = () => { const profile = data.profiles.find((p) => p.id === select.value); if (profile) $('[name="duration_minutes"]', select.closest('tr')).value = profile.target_minutes; });
    $$('[data-remove]').forEach((b) => b.onclick = () => { captureBatch(); batchRows.splice(Number(b.dataset.remove), 1); renderBatch(); });
    $('#batch-form').onsubmit = (event) => {
      event.preventDefault(); captureBatch();
      action($('button[type="submit"]', event.target), async () => {
        try {
          const rows = batchRows.map((row, i) => { try { return validateProject(row, modelsFrom(data.models), data.profiles); } catch (error) { throw new Error(`Ligne ${i + 1} : ${error.message}`); } });
          await api('/api/workspace/batches', { method: 'POST', body: { rows } });
          batchRows = []; dirty = false; location.hash = '#/videos';
        } catch (error) { $('#batch-error').innerHTML = `<div class="banner error">${esc(error.message)}</div>`; throw error; }
      }, "Batch added to queue.");
    };
    bindFormState();
  }
  let productionQueueReading = false;
  async function renderProductionQueue() {
    const box = $('#production-jobs');
    if (!box || productionQueueReading) return;
    productionQueueReading = true;
    try {
      const result = await api('/api/forge/v1/queue');
      if (!box.isConnected) return;
      box.innerHTML = `<p class="small muted">Voice: ${result.usage.voice}/${result.limits.voice} · Image batches: ${result.usage.images}/${result.limits.images} · Render: ${result.usage.render}/${result.limits.render}</p>${result.jobs.length ? `<div class="table-wrap"><table><thead><tr><th>Video</th><th>Status</th><th>Next step</th><th>Actions</th></tr></thead><tbody>${result.jobs.map(job => `<tr><td><a href="#/video/${encode(job.project_id)}/images">${esc(job.title)}</a></td><td>${job.state === 'running' ? '<span class="queue-spinner" aria-hidden="true"></span>' : ''}${esc(job.state.replaceAll('_',' '))}</td><td>${esc(job.message)}</td><td>${['failed','interrupted','changed','blocked'].includes(job.state) ? `<button data-resume-queue="${esc(job.id)}">Resume after checking</button>` : ''}${!['done','cancelled'].includes(job.state) ? `<button data-cancel-queue="${esc(job.id)}">Stop</button>` : ''}</td></tr>`).join('')}</tbody></table></div>` : '<p class="muted">No production jobs yet.</p>'}`;
      $$('[data-resume-queue]', box).forEach(button => button.onclick = event => action(event.currentTarget, async () => {
        await api(`/api/forge/v1/queue/${encode(button.dataset.resumeQueue)}/resume`, {method:'POST',body:{}}); await renderProductionQueue();
      }, 'Queue job resumed.'));
      $$('[data-cancel-queue]', box).forEach(button => button.onclick = event => action(event.currentTarget, async () => {
        await api(`/api/forge/v1/queue/${encode(button.dataset.cancelQueue)}/cancel`, {method:'POST',body:{}}); await renderProductionQueue();
      }, 'Queue job stopped.'));
    } catch (error) { if (box.isConnected) box.textContent = error.message; }
    finally { productionQueueReading = false; }
  }
  function reviewState(scene) {
    const review = scene.review || scene.human_review || {};
    return typeof review === 'string' ? review : review.state || scene.review_state || 'unreviewed';
  }
  function renderProject(selected) {
    if (!STEPS.some(([key]) => key === selected)) selected = "text";
    const status = projectStatus(project);
    const verification = project.review_state?.state || (typeof project.review_state === 'string' ? project.review_state : 'unreviewed');
    main.innerHTML = `<div class="breadcrumbs"><a href="#/videos">Videos</a><span>/</span><a href="#/channels/${encode(project.profile_id || project.channel_id || '')}">${esc(profileName(project.profile_id || project.channel_id))}</a></div>${header(project.title || "Untitled", `${esc(durationLabel(project.duration_info))} · ${profileName(project.profile_id || project.channel_id)}`, `${badge(status.state, status.label)}<button class="icon-button" id="refresh-project" title="Actualiser ce projet" aria-label="Actualiser ce projet">${icon('refresh')}</button>`)}${project.error ? `<div class="banner error">${esc(project.error)}</div>` : ''}<nav class="steps" aria-label="Video steps">${STEPS.map(([key, name, step], index) => `<a href="#/video/${encode(project.id)}/${key}" ${key === selected ? 'aria-current="step"' : ''}><span class="step-name"><span class="step-number">${index + 1}</span>${name}</span>${badge(key === 'verification' ? verification : stepState(project, step))}</a>`).join('')}</nav><div id="step-content"></div>${advanced([[`p/${encode(project.id)}/script`, "Advanced text"], [`p/${encode(project.id)}/voice`, "Advanced voice"], [`p/${encode(project.id)}/visuals`, "Advanced images"], [`p/${encode(project.id)}/render`, 'Montage'], [`p/${encode(project.id)}/thumbs`, "Thumbnails"]])}`;
    $('#refresh-project').onclick = (event) => action(event.currentTarget, () => route());
    if (project.style_name) $('.page-head p').textContent += ` · ${project.style_name}`;
    $('#refresh-project').insertAdjacentHTML('beforebegin', `<button id="rename-video" class="icon-button" title="Edit title" aria-label="Edit title">${icon('edit')}</button>`);
    $('#rename-video').onclick = openRename;
    $('#refresh-project').insertAdjacentHTML('beforebegin', '<button id="queue-video">Queue production</button>');
    $('#queue-video').onclick = event => action(event.currentTarget, async () => {
      if (dirty) throw new Error('Save your changes before queueing production.');
      await api('/api/forge/v1/queue', {method:'POST',body:{project_ids:[project.id]}});
      location.hash = '#/queue';
    }, 'Production queued.');
    if (selected === "text") renderText();
    if (selected === "voice") renderVoice();
    if (selected === 'images' || selected === 'verification') renderScenes(selected === 'verification');
    if (selected === 'export') renderExport();
  }
  function openRename() {
    if (dirty) { notify("Save your changes before changing the title.", true); return; }
    const dialog = $('#create-dialog');
    dialog.className = '';
    dialog.innerHTML = `<div class="dialog-head"><h2 id="create-heading">Edit title</h2><button type="button" data-close class="icon-button" aria-label="Close" title="Close">${icon('close')}</button></div><form id="rename-form"><label>Video title<input name="title" value="${esc(project.title)}" maxlength="240" required></label><div class="form-actions"><button type="button" data-close>Cancel</button><button type="submit" class="primary">Save title</button></div></form>`;
    const close = () => { if (dirty && !confirm("Discard title change?")) return; dirty = false; dialog.close(); };
    $$('[data-close]', dialog).forEach((button) => button.onclick = close);
    dialog.oncancel = (event) => { event.preventDefault(); close(); };
    $('#rename-form').onsubmit = (event) => {
      event.preventDefault();
      action(event.submitter, async () => {
        await api(`/api/workspace/projects/${encode(project.id)}/title`, { method: 'PUT', body: { title: $('[name="title"]', dialog).value } });
        dialog.close(); dirty = false; await route();
      }, "Title saved.");
    };
    bindFormState(dialog);
    dialog.showModal(); $('[name="title"]', dialog).focus();
  }
  function scopeReview(scope) {
    const entry = project.human_reviews?.[scope] || {};
    return `${badge(entry.state || 'unreviewed')}<form class="scope-review" data-scope="${scope}"><label>Review note<textarea name="notes" rows="2">${esc(entry.notes || '')}</textarea></label><div class="form-actions"><button type="submit" name="state" value="correct">${icon('edit')}Needs correction</button><button type="submit" name="state" value="verified" class="primary">${icon('check')}Mark verified</button></div></form>`;
  }
  function bindScopeReviews() {
    $$('.scope-review').forEach((form) => form.onsubmit = (event) => {
      event.preventDefault();
      const state = event.submitter?.value;
      action(event.submitter, async () => {
        const notes = $('[name="notes"]', form).value;
        if (form.dataset.scope === 'script' && $('[name="text"]')?.value !== project.script) throw new Error("Save the text before verifying it.");
        if (state === 'correct' && !notes.trim()) throw new Error("Specify the requested correction.");
        await api(`/api/workspace/projects/${encode(project.id)}/review`, { method: 'POST', body: { scope: form.dataset.scope, state, notes } });
        await route();
      }, state === 'verified' ? "Verification saved." : "Correction request saved.");
    });
  }
  function renderText() {
    const writer = project.workspace_script_writer || {};
    const draft = writer.draft;
    const busy = project.running || project.readonly;
    const applied = draft && writer.applied_draft_id === draft.id;
    const assets = project.voiceover || project.scenes?.length || project.render;
    const step = project.steps?.script || {};
    const writing = project.can_write_script ? `<section class="section"><h2>Write from a title</h2><p class="muted">The CLI Proxy writes the story with our Faceless OS guidelines and narration references, then checks it and adjusts its length if needed. The text of an existing project is preserved.</p><form id="script-writer-form"><fieldset ${busy ? 'disabled' : ''}><label>Title<input name="writing_title" value="${esc(project.title)}" maxlength="240" required></label><label>Desired duration (minutes)<input name="writing_minutes" type="number" min="3" max="30" step="0.5" value="15" required></label><label>Additional instructions (optional)<textarea name="writing_brief" rows="2" maxlength="8000" placeholder="Location, threat, characters, or angle…"></textarea></label><button type="submit" class="primary">${busy ? "Writing in progress…" : project.script?.trim() ? "Draft another script" : "Write from title"}</button></fieldset></form>${busy ? `<p role="status">${esc(step.msg || "Writing…")}</p><progress max="${Math.max(2, step.total || 2)}" value="${step.done || 0}" aria-label="Script writing"></progress>` : ''}${writer.state === 'error' ? "<p class=\"error-text\">Writing was interrupted. Your text is preserved; you can restart.</p>" : ''}${draft && !applied ? `<section class="section"><h3>Draft · ${draft.word_count} words</h3><p class="muted">${esc(durationLabel(scriptDuration(draft.script)))}</p><textarea class="script-editor" readonly aria-label="Generated draft">${esc(draft.script)}</textarea>${assets ? "<p class=\"muted\">This project already has media. Copy this draft to a new video to keep the current shots.</p>" : "<button id=\"apply-script-draft\" type=\"button\">Use this draft</button>"}${draft.audit?.issues?.length || draft.audit?.unsupported_claims?.length ? "<p class=\"muted\">The automatic check flags points to review in this draft.</p>" : ''}</section>` : ''}</section>` : '';
    $('#step-content').innerHTML = `${writing}<form id="script-form" class="editor"><fieldset ${busy ? 'disabled' : ''}><div class="page-head"><h2>Script</h2></div><label>Paste or edit your script<textarea name="text" class="script-editor" spellcheck="true" placeholder="Paste your full script here.">${esc(project.script || '')}</textarea></label>${scriptImportMarkup('edit-script-file')}<div class="form-actions"><button type="submit">Save text</button><button type="submit" name="action" value="next" class="primary">Save and go to voice →</button></div>${project.voiceover_stale ? "<div class=\"banner\">The voice matches an earlier version of the text.</div>" : ''}</fieldset></form>`;
    const input = $('[name="text"]');
    bindScriptImport($('#script-form'), '[name="text"]');
    $('#script-form').onsubmit = (event) => { event.preventDefault(); const next = event.submitter?.value === 'next'; action(event.submitter, async () => { const text = validateScript(input.value); if (next && !text.trim()) throw new Error("Paste your script to proceed to voice."); await api(`/api/workspace/projects/${encode(project.id)}/script`, { method: 'PUT', body: { text } }); dirty = false; if (next) location.hash = `/video/${encode(project.id)}/voice`; else await route(); }, "Text saved."); };
    const writerForm = $('#script-writer-form');
    if (writerForm) writerForm.onsubmit = (event) => {
      event.preventDefault();
      action(event.submitter, async () => {
        if (input.value !== (project.script || '')) throw new Error("Save the pasted or edited text before requesting a draft.");
        const fields = new FormData(writerForm);
        await api(`/api/workspace/projects/${encode(project.id)}/script/generate`, {method:'POST',body:{title:fields.get('writing_title'),minutes:Number(fields.get('writing_minutes')),brief:fields.get('writing_brief'),script_hash:project.script_hash}});
        dirty = false; await route();
      }, "Writing started.");
    };
    const applyDraft = $('#apply-script-draft');
    if (applyDraft) applyDraft.onclick = () => action(applyDraft, async () => {
      if (input.value !== (project.script || '')) throw new Error("Save your text before using the draft.");
      await api(`/api/workspace/projects/${encode(project.id)}/script/apply-draft`, {method:'POST',body:{draft_id:draft.id,script_hash:project.script_hash}});
      dirty = false; await route();
    }, "Draft saved as script.");
  }
  function renderVoice() {
    const voice = project.voiceover;
    const url = mediaUrl('media', project.id, voice?.file);
    const step = project.steps?.voiceover || {};
    const chosen = project.settings?.voice || {};
    const blocked = project.running || project.readonly || !project.script?.trim();
    $('#step-content').innerHTML = `${header("Voice", step.msg || '', badge(step.state || 'idle'))}${project.voiceover_stale ? "<div class=\"banner\">The voice must be redone: the text or voice choice has changed.</div>" : ''}<form id="voice-form" class="editor"><fieldset ${blocked ? 'disabled' : ''}><label>Voice provider<select name="provider"><option value="algrow" ${chosen.provider !== 'ai33' ? 'selected' : ''}>Algrow · ElevenLabs</option><option value="ai33" ${chosen.provider === 'ai33' ? 'selected' : ''}>AI33 Pro · ElevenLabs</option></select></label><label>ElevenLabs voice ID<input name="manual_voice_id" value="${esc(chosen.voice_id || '')}" placeholder="Paste your ElevenLabs voice ID" maxlength="200" required></label><label>Search for a voice<div class="actions"><input id="voice-search" placeholder="Voice name, accent…"><button id="search-voices" type="button">Search</button></div></label><label>Voice<select name="voice_id">${chosen.voice_id ? `<option value="${esc(chosen.voice_id)}">${esc(chosen.voice_name || chosen.voice_id)} · voice saved</option>` : "<option value=\"\">Choose a voice</option>"}</select></label><p id="voice-catalog-status" class="muted small" role="status">Loading catalog…</p><audio id="voice-sample" controls preload="none" hidden></audio><label>Speed<input type="number" name="speed" min="0.7" max="1.2" step="0.05" value="${esc(chosen.speed || 1)}"></label><p class="muted small">Language: ${esc(project.settings?.language || 'English')}. The preview is from the catalog; generation reads your saved script.</p><div class="form-actions"><button type="submit" name="action" value="save">Save project voice</button><button type="submit" name="action" value="default">Keep this voice for the channel</button><button type="submit" name="action" value="generate" class="primary">${project.running ? "Generating…" : voice ? "Regenerate voiceover" : "Generate narration"}</button></div></fieldset></form>${!project.script?.trim() ? "<p class=\"banner\">Paste and save your text in the Text step.</p>" : ''}${url ? `<section class="section"><h2>Narration ${esc(voice.voice || '')}</h2><audio controls preload="metadata" src="${esc(url)}"></audio><p class="muted small">${project.voiceover_stale ? "Previous voice duration" : "Actual duration"} : ${fmtTime(voice.duration)}</p></section><section class="section editor"><h2>Listen and check</h2>${scopeReview('voiceover')}</section>` : ''}<div class="form-actions"><a class="button" href="#/video/${encode(project.id)}/text">← Text</a>${url && !project.voiceover_stale && !project.running ? `<a class="button primary" href="#/video/${encode(project.id)}/images">Continue to images →</a>` : ''}</div>`;
    const id = project.id;
    const form = $('#voice-form');
    const select = $('[name="voice_id"]', form);
    const manual = $('[name="manual_voice_id"]', form);
    const provider = $('[name="provider"]', form);
    let entries = [];
    let request = 0;
    const showSample = () => {
      const sample = $('#voice-sample');
      const raw = entries.find((v) => v.id === select.value)?.preview_url;
      let src = '';
      try { const u = new URL(raw); if (u.protocol === 'https:' && !u.username && !u.password) src = u.href; } catch {}
      sample.hidden = !src;
      if (src) sample.src = src; else sample.removeAttribute('src');
    };
    const loadVoices = async () => {
      const token = ++request;
      const status = $('#voice-catalog-status');
      status.textContent = 'Chargement du catalogue…';
      try {
        const result = await api(`/api/workspace/voices?language=${encode(project.settings?.language || 'English')}&provider=${encode(provider.value)}&search=${encode($('#voice-search').value)}`);
        if (request !== token || project.id !== id || !form.isConnected) return;
        const current = { id: select.value, name: select.selectedOptions[0]?.textContent || chosen.voice_name };
        entries = result.voices || [];
        const options = current.id && !entries.some((v) => v.id === current.id) ? [current, ...entries] : entries;
        select.innerHTML = `<option value="">Choose a voice</option>${options.map((v) => `<option value="${esc(v.id)}">${esc(v.name)}${v.accent ? ` · ${esc(v.accent)}` : ''}</option>`).join('')}`;
        select.value = current.id || '';
        status.textContent = entries.length ? `${entries.length} voices available. Select a voice to hear its preview.` : "No voices found. Try another search.";
        showSample();
      } catch (error) { if (form.isConnected && request === token) status.textContent = error.message; }
    };
    $('#search-voices').onclick = loadVoices;
    $('#voice-search').onkeydown = (event) => { if (event.key === 'Enter') { event.preventDefault(); loadVoices(); } };
    select.onchange = () => { manual.value = select.value; showSample(); };
    manual.oninput = () => { select.value = manual.value.trim(); showSample(); };
    provider.onchange = loadVoices;
    form.onsubmit = (event) => {
      event.preventDefault();
      const mode = event.submitter?.value;
      action(event.submitter, async () => {
        if (!form.reportValidity()) return;
        const vid = manual.value.trim();
        const body = { provider: provider.value, voice_id: vid, voice_name: entries.find((v) => v.id === vid)?.name || (vid === chosen.voice_id ? chosen.voice_name : vid) || vid, speed: Number($('[name="speed"]', form).value) };
        const suffix = mode === 'generate' ? '/generate' : mode === 'default' ? '/channel-default' : '';
        if (mode === 'generate') body.script_hash = project.script_hash;
        await api(`/api/workspace/projects/${encode(id)}/voice${suffix}`, { method: mode === 'save' ? 'PUT' : 'POST', body });
        dirty = false; await route();
      }, mode === 'generate' ? "Narration generation started." : mode === 'default' ? "Voice saved for the channel’s next videos." : "Project voice saved.");
    };
    loadVoices();
    form.insertAdjacentHTML('beforebegin', voiceProgressMarkup(project));
    bindScopeReviews();
  }
  function voiceProgressMarkup(p) {
    const info = voiceProgressInfo(p);
    if (!info.active) return '<div id="voice-progress"></div>';
    const elapsed = info.started ? Math.max(0, Date.now() / 1000 - info.started) : 0;
    return `<section id="voice-progress" class="voice-progress" aria-label="Narration generation"><div class="inline"><strong>Narration in progress</strong><span data-voice-elapsed data-started="${info.started || ''}">Elapsed time: ${fmtTime(elapsed)}</span></div><progress max="100" ${info.percent !== null ? `value="${info.percent}"` : ''} aria-label="Voice progress"></progress><p class="small" role="status">${esc(p.steps?.voiceover?.msg || "Text-to-speech…")}${info.percent !== null ? ` · ${Math.round(info.percent)} %` : ''}</p><p class="muted small">${info.percent === null ? "The provider does not yet send a percentage. " : ''}The narration and its actual duration will appear here automatically.</p></section>`;
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
    return `<div class="actions"><button type="button" data-generate="${esc(scene.id)}">${icon('refresh')}${hasImage(scene) ? "Redo this shot" : "Generate this shot"}</button></div>`;
  }
  function batchMarkup(p = project) {
    if (!p.codex_directed || p.readonly) return '';
    const test = batchPlan(p, 'preview');
    const rest = batchPlan(p, 'remaining');
      const corrections = batchPlan(p, 'corrections');
    const job = p.workspace_batch;
    const active = ['queued', 'running', 'stopping'].includes(job?.state);
      const labels = { queued: "Starting", running: job?.phase === 'corrections' ? "Correcting shots" : "Generating images", stopping: "Stopping after active shots", done: "Images generated · needs review", done_with_errors: "Corrections complete · some shots need another attempt", stopped: "Generation stopped", failed: "Generation stopped on an error", interrupted: "Generation interrupted" };
      const correctionButton = corrections.targets.length ? `<button type="button" data-batch="corrections" ${corrections.reason ? 'disabled' : ''}>Redo incorrect shots · ${corrections.targets.length}</button>` : '';
      const failedCount = job?.failed_scene_ids?.length || 0;
      const processed = (job?.done || 0) + failedCount;
      const activeIds = job?.current_scene_ids?.length ? job.current_scene_ids : job?.current_scene_id != null ? [job.current_scene_id] : [];
    return `<section id="batch-workflow" class="section batch-workflow" aria-label="Test, then generate the images"><h2>Test the first 3, then generate the rest</h2><p class="muted">Check the character, settings, and style on the first three shots before launching the remaining images. Successful images are kept. Shots marked to redo are regenerated with their new references.</p><div class="actions"><button type="button" class="primary" data-batch="preview" ${test.reason ? 'disabled' : ''}>1. Test the ${test.first.length || 3} first images${test.targets.length ? ` · ${test.targets.length} to generate` : ''}</button><button type="button" class="primary" data-batch="remaining" ${rest.reason ? 'disabled' : ''}>2. Generate the remaining images${rest.targets.length ? ` · ${rest.targets.length}` : ''}</button>${correctionButton}${active ? `<button type="button" id="stop-images" ${job.stop_requested ? 'disabled' : ''}>Stop after current shots</button>` : ''}</div>${test.reason && !active ? `<p class="small muted">Test : ${esc(test.reason)}</p>` : ''}${rest.reason && !active ? `<p class="small muted">Suite : ${esc(rest.reason)}</p>` : ''}${job ? `<div class="batch-progress" role="status" aria-live="polite"><strong>${esc(labels[job.state] || job.state)}</strong><span>${processed}/${job.total} shots processed · ${job.concurrency || 1} images at once · ${job.done} images generated${failedCount ? ` · ${failedCount} failure(s)` : ''}${activeIds.length ? ` · shots in progress: ${activeIds.map(esc).join(', ')}` : ''}</span><progress max="${Math.max(1, job.total)}" value="${processed}" aria-label="Shots processed"></progress>${job.error ? `<p class="error-text">${esc(job.error)}</p>` : ''}${failedCount ? `<p class="small error-text">To redo: shots ${job.failed_scene_ids.map(esc).join(', ')}. The previous images are kept.</p>` : ''}</div>` : ''}<p class="small muted">After generation, check all images, then launch the edit in the Export tab. The voice and timings must be ready.</p></section>`;
  }
  function bindBatchControls() {
    $$('[data-batch]').forEach((button) => button.onclick = () => action(button, async () => {
      if (dirty) throw new Error("Save the prompts and your notes before launching generation.");
      const phase = button.dataset.batch;
      const plan = batchPlan(project, phase);
      if (plan.reason) throw new Error(plan.reason);
      project = await api(`/api/workspace/projects/${encode(project.id)}/images/generate`, { method: 'POST', body: {
        phase, confirmation: project.generation_confirmation, image_model: project.model_snapshot.image_model,
        image_provider: project.model_snapshot.image_provider || 'cli_proxy'
      } });
      renderScenes(routeParts()[2] === 'verification');
    }, "Generation started. You can leave this page and come back to check the result."));
    const stop = $('#stop-images');
    if (stop) stop.onclick = () => action(stop, async () => {
      project = await api(`/api/workspace/projects/${encode(project.id)}/images/stop`, { method: 'POST' });
      $('#batch-workflow').outerHTML = batchMarkup(); bindBatchControls();
    }, "Stop requested: the current image will be kept.");
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
    dialog.setAttribute('aria-label', "Confirm shot generation");
    dialog.innerHTML = `<div class="dialog-head"><h2>Redo this shot</h2><button type="button" data-cancel class="icon-button" title="Close" aria-label="Close">${icon('close')}</button></div><dl class="metadata"><dt>Shot</dt><dd>${esc(scene.id)}</dd><dt>Image model</dt><dd>${esc(body.image_model)}</dd></dl><section class="section"><h3>Exact saved prompt</h3><pre class="exact-prompt">${esc(body.confirm_prompt)}</pre></section><section class="section"><h3>References, in order</h3><ol class="refs">${references.map((ref) => referenceView(typeof ref === 'string' ? ref : { ...ref, label: `${ref.label || ref.role || "Reference"} · ${ref.path || ref.file || ref.image || ''}` })).join('')}</ol></section><p class="muted small">A new version of this image will be created. The previous version will be kept; the new result will need to be checked.</p><div id="generation-error" role="alert"></div><div class="form-actions"><button type="button" data-cancel>Cancel</button><button type="button" id="confirm-generation" class="primary">${icon('refresh')}Confirm and redo this shot</button></div>`;
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
        if (!latest) throw new Error("This shot no longer exists. Refresh the project.");
        const latestBody = generationBody(current, latest);
        if (latestBody.confirm_prompt !== body.confirm_prompt || latestBody.image_model !== body.image_model || JSON.stringify(referenceOrder(sceneReferences(latest))) !== JSON.stringify(confirmedOrder)) {
          throw new Error("The prompt, references, or model have changed. Refresh the project before confirming again.");
        }
        const promptInput = $('[name="prompt"]', article);
        if (promptInput && promptInput.value !== body.confirm_prompt) throw new Error("Save the prompt before remaking this outline.");
        await api(`/api/workspace/projects/${encode(projectId)}/scenes/${encode(scene.id)}/generate`, { method: 'POST', body });
        dialog.close();
        notify("New image requested for this shot.");
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
  function cameraPlanMarkup() {
    if (!project.scenes?.some((s) => s.location_view)) return '';
    const audit = project.workspace_camera_audit || {};
    const entries = Object.entries(audit.locations || {});
    const views = entries.reduce((sum, [, place]) => sum + (place.views?.length || 0), 0);
    const backed = Object.keys(project.workspace_location_registry || {}).length;
    return `<section class="section" aria-label="Location and camera continuity"><h2>Locations and camera views</h2><p>${entries.length} spaces · ${views} named viewpoints · ${backed} spaces with registered image masters</p><p class="small muted">A different view changes the camera position while keeping doors, windows and fixed objects in the same physical place. Each shot also needs a new action or detail. The images still need visual review.</p>${audit.warnings?.length ? `<ul class="small">${audit.warnings.map((w) => `<li>${esc(w)}</li>`).join('')}</ul>` : ''}<details><summary>View distribution</summary><ul>${entries.map(([name, place]) => `<li><strong>${esc(name)}</strong>: ${place.shots} shots · ${esc((place.views || []).join(', '))}</li>`).join('')}</ul></details></section>`;
  }
  function planningMarkup() {
    if (project.scenes?.length) return '';
    const step = project.steps?.planning || {};
    const active = project.running;
    return `<section class="section" id="planning-workflow"><h2>Prepare images</h2><p>Your script and voice are saved. Prepare the shots, their prompts, and the style references, then test the first three images.</p>${project.can_prepare_images ? `<button id="prepare-images" class="primary" ${active || project.duration_info?.kind !== 'actual' ? 'disabled' : ''}>${active ? "Preparing…" : "Prepare images"}</button>` : "<p>The breakdown for this history channel is still prepared by Codex.</p>"}${active ? `<p role="status">${esc(step.msg || "Starting preparation…")}</p><progress max="${Math.max(1, step.total || 1)}" ${step.total ? `value="${step.done || 0}"` : ''} aria-label="Shot preparation"></progress>` : ''}${step.state === 'error' ? `<p class="error-text">${esc(step.msg)}</p>` : ''}<p class="small muted">This step prepares the prompts. No images are generated yet.</p></section>`;
  }
  function renderScenes(verification) {
    const scenes = project.scenes || [];
    const verified = scenes.filter((s) => reviewState(s) === 'verified').length;
    const pageKey = project.id + ':' + Boolean(verification);
    const view = scenePage(scenes, scenePages.get(pageKey) || 0);
    const pages = scenes.length > 24 ? `<nav class="inline" aria-label="Shot pages"><button data-shot-page="${view.page - 1}" ${view.page === 0 ? 'disabled' : ''}>← Previous</button><label>Page<select id="shot-page">${Array.from({length:view.pages}, (_, i) => `<option value="${i}" ${i === view.page ? 'selected' : ''}>${i + 1} / ${view.pages}</option>`).join('')}</select></label><span class="small">Shots ${view.start + 1}–${view.end} of ${scenes.length}</span><button data-shot-page="${view.page + 1}" ${view.page === view.pages - 1 ? 'disabled' : ''}>Next →</button></nav>` : '';
    $('#step-content').innerHTML = `${header(verification ? "Image review" : "Shots and images", `${scenes.length} shots · ${verified} reviewed`)}${scenes.length ? batchMarkup() : planningMarkup()}${pages}${!scenes.length ? '' : view.rows.map((scene, localIndex) => {
      const index = view.start + localIndex;
      const references = sceneReferences(scene);
      const names = (scene.characters || []).map((id) => typeof id === 'object' ? id.name || id.id : project.characters?.find((c) => c.id === id)?.name || id);
      const image = safeUrl(scene.image_url) || mediaUrl('media', project.id, scene.image);
      return `<article class="scene" data-scene="${esc(scene.id)}"><div class="scene-media">${preview(image, `Shot ${index + 1}`)}<div class="inline">${badge(scene.status || 'idle', scene.image ? `Image · ${stateLabel(scene.status || 'done')}` : stateLabel(scene.status || 'idle'))}${badge(reviewState(scene))}</div>${scene.error ? `<div class="banner error">${esc(scene.error)}</div>` : ''}<details><summary>Character and style references</summary><h3>References planned for this shot, in order</h3>${references.length ? `<ol class="refs">${references.map(referenceView).join('')}</ol>` : "<p class=\"muted small\">No reference saved.</p>"}</details></div><div class="scene-data"><div class="scene-head"><h2>Shot ${index + 1}</h2><span class="small muted">${scene.start != null && scene.end != null ? `${fmtTime(scene.start)} → ${fmtTime(scene.end)}` : "Voice not aligned"}</span></div><div class="narration"><h3>Narration</h3><p>${esc(scene.text || scene.narration || "Missing excerpt")}</p></div><details><summary>Shot details and prompt</summary><dl class="metadata"><dt>Location</dt><dd>${esc(scene.location_id || scene.location || "Not specified")}</dd><dt>Personnages</dt><dd>${esc(names.join(', ') || "No named character")}</dd><dt>Variant</dt><dd>${esc([scene.location_view, scene.shot_type].filter(Boolean).join(" · ") || scene.variant || scene.camera_variant || "Not specified")}</dd></dl>${verification ? `<details><summary>Shot prompt</summary><p>${esc(scene.prompt || "Missing prompt")}</p></details>` : `<form class="scene-form"><label>Prompt exact<textarea name="prompt">${esc(scene.prompt || '')}</textarea></label><div class="form-actions"><button type="submit">Save prompt</button></div></form>`}</details>${generationControl(scene)}<form class="review-form"><label>Review note<textarea name="notes">${esc(scene.review?.notes || scene.human_review?.notes || '')}</textarea></label><div class="actions"><button type="submit" name="state" value="correct" ${!image ? 'disabled' : ''}>${icon('edit')}Needs fixing</button><button type="submit" name="state" value="verified" class="primary" ${!image ? 'disabled' : ''}>${icon('check')}Mark as reviewed</button><button type="submit" name="state" value="unreviewed" title="Remove approval">To review</button></div></form></div></article>`;
    }).join('')}`;
    $('#step-content').insertAdjacentHTML('afterbegin', cameraPlanMarkup());
    const changePage = page => {
      if (dirty) { notify('Save your prompts or notes before changing page.', true); return; }
      scenePages.set(pageKey, Number(page));
      renderScenes(verification);
      $('#step-content').scrollIntoView({block:'start'});
    };
    $$('[data-shot-page]').forEach(button => button.onclick = () => changePage(button.dataset.shotPage));
    const selectPage = $('#shot-page');
    if (selectPage) selectPage.onchange = () => {
      if (dirty) { selectPage.value = String(view.page); notify('Save your prompts or notes before changing page.', true); return; }
      changePage(selectPage.value);
    };
    bindBatchControls();
    const prepare = $('#prepare-images');
    if (prepare) prepare.onclick = () => action(prepare, async () => {
      if (dirty) throw new Error("Save your changes before preparing the shots.");
      project = await api(`/api/workspace/projects/${encode(project.id)}/images/prepare`, {method: 'POST', body: {script_hash: project.script_hash}});
      renderScenes(verification);
    }, "Preparation started. The images will be generated after your test.");
    $$('[data-generate]').forEach((button) => {
      const article = button.closest('[data-scene]');
      const scene = project.scenes.find((candidate) => String(candidate.id) === button.dataset.generate);
      button.onclick = () => openGeneration(scene, article);
      $('[name="prompt"]', article)?.addEventListener('input', (event) => {
        const reason = generationBlockReason(project, scene, event.target.value);
        button.disabled = Boolean(reason);
        button.title = reason || "Redo this shot only";
      });
    });
    $$('.scene-form').forEach((form) => form.onsubmit = (event) => {
      event.preventDefault();
      const sid = form.closest('[data-scene]').dataset.scene;
      action(event.submitter, async () => {
        const scenes = project.scenes.map((scene) => {
          const article = $$('[data-scene]').find((element) => element.dataset.scene === String(scene.id));
          const prompt = article ? $('[name="prompt"]', article) : null;
          return prompt ? { ...scene, prompt: prompt.value } : scene;
        });
        await api(`/api/workspace/projects/${encode(project.id)}/scenes`, { method: 'PUT', body: { scenes } }); await route();
      }, "Prompt saved.");
    });
    $$('.review-form').forEach((form) => form.onsubmit = (event) => {
      event.preventDefault();
      action(event.submitter, async () => {
        const notes = $('[name="notes"]', form).value;
        const state = event.submitter?.value;
        if (state === 'correct' && !notes.trim()) throw new Error("Specify the requested correction for this image.");
        const sid = form.closest('[data-scene]').dataset.scene;
        const scene = project.scenes.find((s) => String(s.id) === sid);
        const authored = $('[name="prompt"]', form.closest('[data-scene]'));
        if (authored && authored.value !== scene.prompt) throw new Error("Save the prompt before reviewing the image.");
        await api(`/api/workspace/projects/${encode(project.id)}/review`, { method: 'POST', body: { scene_id: scene.id, state, notes } }); await route();
      }, "Review status saved.");
    });
    bindFormState($('#step-content'));
    bindPreviews($('#step-content'));
  }
  function renderExport() {
    const render = project.render || {};
    const url = mediaUrl('media', project.id, render.file);
    const srt = mediaUrl('media', project.id, render.srt);
    const status = projectStatus(project);
    $('#step-content').innerHTML = `${header('Export', '', badge(status.state, status.label))}${project.technical_issues?.length ? `<div class="banner"><h3>Technical checks to complete</h3><ul>${project.technical_issues.map((issue) => `<li>${esc(issue)}</li>`).join('')}</ul></div>` : ''}${url ? `<video controls preload="metadata" src="${esc(url)}"></video><div class="actions"><a class="button" href="${esc(url)}" download>${icon('download')}Download the render</a>${srt ? `<a class="button" href="${esc(srt)}" download>${icon('download')}Sous-titres</a>` : ''}</div>${project.publication_ready !== true ? "<div class=\"banner\">Render available. Pre-publication review still needs to be completed.</div>" : "<div class=\"banner good\">Pre-publication approval saved.</div>"}<section class="section editor"><h2>Render review</h2>${scopeReview('render')}</section>` : "<div class=\"empty\"><h2>No render available</h2><p>The project is waiting for editing and export.</p></div>"}<section class="section"><h2>Project models</h2><dl class="definition-list"><div><dt>Text</dt><dd>${esc(project.model_snapshot?.text_model || project.settings?.script?.model || "Not specified")}</dd></div><div><dt>Images</dt><dd>${esc(project.model_snapshot?.image_model || project.settings?.visuals?.image_model || "Not specified")}</dd></div></dl></section>`;
    bindScopeReviews();
    const ready = project.technical_ready && project.scenes?.length && project.scenes.every((s) => s.human_review?.state === 'verified') && project.human_reviews?.voiceover?.state === 'verified';
    $('#step-content').insertAdjacentHTML('afterbegin', `<section class="section"><h2>Video editing</h2><button id="render-video" type="button" class="primary" ${!ready || project.running ? 'disabled' : ''}>${project.running ? "Editing in progress…" : "Generate video edit"}</button>${!ready ? "<p class=\"small muted\">Prepare the voice and timings, then check the voice and all images to start editing.</p>" : ''}</section>`);
    $('#render-video').onclick = (event) => action(event.currentTarget, async () => {
      if (dirty) throw new Error("Save your notes before starting the edit.");
      await api(`/api/workspace/projects/${encode(project.id)}/render`, { method: 'POST' }); await route();
    }, "Editing started.");
  }
  function profilePreview(profile, kind) {
    const value = profile[`${kind}_preview`] || profile[`${kind}_preview_url`];
    return value ? mediaUrl('style-media', profile.style_id, value) : '';
  }
  function countLabel(count, word) { return count + ' ' + word + (count === 1 ? '' : 's'); }
  function styleOptions(selected) {
    return data.styles.map((s) => '<option value="' + esc(s.id) + '"' + (s.id === selected ? ' selected' : '') + '>' + esc(s.name) + '</option>').join('');
  }
  function channelFields(c = {}, includeStyle = true) {
    const languages = {English: "English", French: "French", Spanish: "Spanish", German: "German", Italian: "Italian", Portuguese: "Portuguese", Japanese: "Japanese"};
    const markup = "<div class=\"form-grid\"><label>Channel name<input name=\"name\" value=\"" + esc(c.name || '') + '" maxlength="200" required></label><label>Handle<input name="handle" value="' + esc(c.handle || '') + "\" placeholder=\"@MyChannel\" maxlength=\"100\"></label><label>Language<select name=\"language\">" + Object.entries(languages).map(([key, label]) => '<option value="' + key + '"' + (key === (c.language || 'English') ? ' selected' : '') + '>' + label + '</option>').join('') + "</select></label><label>Target length (minutes)<input name=\"target_minutes\" type=\"number\" min=\"3\" max=\"30\" step=\"0.5\" value=\"" + (c.target_minutes || 22) + "\" required></label><label class=\"full\">Default style<select name=\"style_id\" required>" + (c.style_id && !data.styles.some((s) => s.id === c.style_id) ? "<option value=\"\" selected>Archived style · choose an active style</option>" : '') + styleOptions(c.style_id || data.styles[0]?.id) + '</select></label><label>Voice provider<select name="voice_provider"><option value="algrow"' + (c.voice?.provider !== 'ai33' ? ' selected' : '') + '>Algrow · ElevenLabs</option><option value="ai33"' + (c.voice?.provider === 'ai33' ? ' selected' : '') + ">AI33 Pro · ElevenLabs</option></select></label><label>ElevenLabs voice ID<input name=\"voice_id\" value=\"" + esc(c.voice?.voice_id || '') + "\" placeholder=\"Voice ID specific to this channel\" maxlength=\"200\" required></label><label class=\"full\">Setting and era<textarea name=\"setting\" rows=\"3\">" + esc(c.setting || '') + "</textarea></label><label class=\"full\">Channel description<textarea name=\"description\" rows=\"3\">" + esc(c.description || '') + '</textarea></label></div>';
    return includeStyle ? markup : markup.replace(/<label[^>]*>Default style<select name="style_id" required>[\s\S]*?<\/select><\/label>/, "");
  }
  function channelBody(form) {
    const fields = new FormData(form);
    return {name: fields.get('name'), handle: fields.get('handle'), language: fields.get('language'), target_minutes: Number(fields.get('target_minutes')), style_id: fields.get('style_id'), setting: fields.get('setting'), description: fields.get('description'), voice: {provider: fields.get('voice_provider'), voice_id: fields.get('voice_id'), voice_name: fields.get('voice_id') === form.dataset.savedVoiceId ? form.dataset.savedVoiceName : fields.get('voice_id'), speed: Number(form.dataset.savedVoiceSpeed || 1)}};
  }
  function channelPresetBody() {
    const body = channelBody($('#channel-settings'));
    delete body.style_id;
    const visual = $('#visual-style-form');
    body.preset = visual ? {...Object.fromEntries(new FormData(visual)), references:visual.orderedReferences} : {};
    const verify = $('#channel-settings').verifyCharacter;
    body.characters = $$('[data-character-form]').map(form => ({name:form.dataset.name, variant:form.dataset.variant,
      description:$('[name="description"]', form).value, is_main:$('[name="is_main"]', form).checked,
      verify:verify?.name === form.dataset.name && verify?.variant === form.dataset.variant}));
    $('#channel-settings').verifyCharacter = null;
    return body;
  }
  function managementDialog(title, fields, submit) {
    if (dirty) { notify("Save your changes before continuing.", true); return; }
    const dialog = $('#create-dialog');
    dialog.className = 'management-dialog';
    dialog.innerHTML = '<div class="dialog-head"><h2 id="create-heading">' + esc(title) + "</h2><button type=\"button\" data-close class=\"icon-button\" aria-label=\"Close\" title=\"Close\">" + icon('close') + '</button></div><form id="management-form">' + fields + "<div id=\"management-error\" role=\"alert\"></div><div class=\"form-actions\"><button type=\"button\" data-close>Cancel</button><button type=\"submit\" class=\"primary\">" + icon('plus') + "Create</button></div></form>";
    const close = () => { if (dirty && !confirm("Discard changes?")) return; dirty = false; dialog.close(); };
    $$('[data-close]', dialog).forEach((button) => button.onclick = close);
    dialog.oncancel = (event) => { event.preventDefault(); close(); };
    $('#management-form').onsubmit = (event) => {
      event.preventDefault();
      action(event.submitter, async () => {
        try { const destination = await submit(event.target); dialog.close(); dirty = false; location.hash = destination; }
        catch (error) { $('#management-error').innerHTML = '<div class="banner error">' + esc(error.message) + '</div>'; throw error; }
      }, "Creation saved.");
    };
    bindFormState(dialog); dialog.showModal(); $('input', dialog).focus();
  }
  function newChannel() {
    const fields = channelFields({}, false) + `<fieldset class="create-section"><legend>Drawing preset</legend><label>Start from<select name="template_style_id"><option value="">Blank preset</option>${data.styles.map(style => `<option value="${esc(style.id)}">${esc(style.name)}</option>`).join('')}</select></label><label>Drawing instructions<textarea name="preset_prompt" rows="5" required></textarea></label><label>Background direction<textarea name="preset_background_direction" rows="3"></textarea></label>${backgroundModeField()}<details class="advanced"><summary>Thumbnail instructions</summary><textarea name="preset_thumbnail_prompt" rows="3"></textarea></details></fieldset>`;
    managementDialog('New channel / preset', fields, async form => {
      const values = new FormData(form);
      const body = channelBody(form);
      delete body.style_id;
      body.template_style_id = values.get('template_style_id') || null;
      body.preset = {prompt:values.get('preset_prompt'), background_direction:values.get('preset_background_direction'),
        background_mode:values.get('background_mode'), thumbnail_prompt:values.get('preset_thumbnail_prompt')};
      const result = await api('/api/workspace/management/presets', {method:'POST', body});
      return '#/channels/' + encode(result.channel.id) + '/settings';
    });
    $('[name="template_style_id"]', $('#management-form')).onchange = event => {
      const selected = data.styles.find(style => style.id === event.target.value);
      for (const [field, value] of Object.entries({preset_prompt:selected?.prompt || '',
        preset_background_direction:selected?.background_direction || '', background_mode:selected?.background_mode || 'free',
        preset_thumbnail_prompt:selected?.thumbnail_prompt || ''})) $('[name="' + field + '"]', $('#management-form')).value = value;
    };
  }
  function archiveManaged(kind, item, archived) {
    if (dirty) { notify("Save your changes before continuing.", true); return; }
    if (!confirm((archived ? 'Archiver ' : "Restore ") + '« ' + item.name + ' » ?')) return;
    action(null, async () => { await api('/api/workspace/management/' + kind + '/' + encode(item.id), {method: 'PUT', body: {archived}}); await route(); }, archived ? "Archived. Files and videos are kept." : "Restored.");
  }
  function renderChannels(id, selected = 'videos') {
    const profile = management.channels.find((p) => p.id === id);
    if (profile) { renderChannel(profile, selected); return; }
    if (id) { main.innerHTML = header("Channel not found", '') + "<a href=\"#/channels\">Back to channels</a>"; return; }
    main.innerHTML = header("Channels / presets", '', '<button id="new-channel" class="primary">' + icon('plus') + "New channel / preset</button>") + "<div class=\"toolbar\"><label class=\"search\">Search a channel<input id=\"channel-search\" type=\"search\" value=\"" + esc(managementFilters.channels) + '"></label><label class="checkbox-label"><input id="archived-channels" type="checkbox"' + (managementFilters.archivedChannels ? ' checked' : '') + ">Show archives</label><span id=\"channels-count\" class=\"count\"></span></div><div id=\"channels-list\"></div>";
    const update = () => {
      managementFilters.channels = $('#channel-search').value;
      managementFilters.archivedChannels = $('#archived-channels').checked;
      const items = management.channels.filter((c) => !!c.archived === managementFilters.archivedChannels && (c.name + ' ' + c.handle).toLocaleLowerCase('en').includes(managementFilters.channels.toLocaleLowerCase('en')));
      $('#channels-count').textContent = items.length + " channel" + (items.length === 1 ? '' : 's');
      $('#channels-list').innerHTML = items.length ? "<div class=\"table-wrap\"><table class=\"management-table\"><thead><tr><th>Channel</th><th>Drawing preset</th><th>Language</th><th>Videos</th><th>Actions</th></tr></thead><tbody>" + items.map((c) => "<tr><td data-label=\"Channel\"><a class=\"project-title\" href=\"#/channels/" + encode(c.id) + '">' + esc(c.name) + '</a><div class="small muted">' + esc(c.handle || "Handle not provided") + '</div></td><td data-label="Drawing preset"><a href="#/styles/' + encode(c.style_id) + '">' + esc(c.style_name) + "</a></td><td data-label=\"Language\">" + esc(({English:"English",French:"French"})[c.language] || c.language) + "</td><td data-label=\"Videos\">" + data.projects.filter((p) => (p.profile_id || p.channel_id) === c.id).length + '</td><td data-label="Actions"><div class="actions"><a class="button icon-button" href="#/channels/' + encode(c.id) + "/settings\" title=\"Settings for " + esc(c.name) + "\" aria-label=\"Settings for " + esc(c.name) + '">' + icon('edit') + '</a>' + (!c.archived ? '<button class="icon-button" data-create-channel="' + esc(c.id) + "\" title=\"New video for " + esc(c.name) + "\" aria-label=\"New video for " + esc(c.name) + '">' + icon('plus') + '</button>' : '<button data-restore-channel="' + esc(c.id) + "\">Restore</button>") + '</div></td></tr>').join('') + '</tbody></table></div>' : "<div class=\"empty\">No channels in this list.</div>";
      $$('[data-create-channel]').forEach((button) => button.onclick = () => openCreate(button.dataset.createChannel));
      $$('[data-restore-channel]').forEach((button) => button.onclick = () => archiveManaged('channels', items.find((c) => c.id === button.dataset.restoreChannel), false));
    };
    $('#new-channel').onclick = newChannel;
    $('#channel-search').oninput = update; $('#archived-channels').onchange = update; update();
  }
  function renderChannel(profile, selected) {
    const settings = selected === 'settings';
    main.innerHTML = "<div class=\"breadcrumbs\"><a href=\"#/channels\">Channels &amp; presets</a><span>/</span>" + esc(profile.name) + '</div>' + header(profile.name, profile.handle || '', profile.archived ? "<button id=\"restore-channel\">Restore channel</button>" : '<button id="channel-create" class="primary">' + icon('plus') + "New video</button>") + "<nav class=\"view-tabs\" aria-label=\"Channel views\"><a href=\"#/channels/" + encode(profile.id) + '"' + (!settings ? ' aria-current="page"' : '') + ">Videos</a><a href=\"#/channels/" + encode(profile.id) + '/settings"' + (settings ? ' aria-current="page"' : '') + ">Preset &amp; settings</a></nav><div id=\"channel-content\"></div>";
    if (profile.archived) $('#restore-channel').onclick = () => archiveManaged('channels', profile, false);
    else $('#channel-create').onclick = () => openCreate(profile.id);
    if (!settings) {
      $('#channel-content').innerHTML = "<dl class=\"channel-summary\"><div><dt>Drawing preset</dt><dd><a href=\"#/styles/" + encode(profile.style_id) + '">' + esc(profile.style_name) + "</a></dd></div><div><dt>Language</dt><dd>" + esc(({English:"English", French:"French", Spanish:"Spanish", German:"German", Italian:"Italian", Portuguese:"Portuguese", Japanese:"Japanese"})[profile.language] || profile.language) + "</dd></div><div><dt>Target duration</dt><dd>" + profile.target_minutes + " min</dd></div><div><dt>Voice</dt><dd>Algrow</dd></div></dl>" + projectTable(data.projects.filter((p) => (p.profile_id || p.channel_id) === profile.id));
      return;
    }
    $('#channel-content').innerHTML = "<div class=\"management-editor\"><form id=\"channel-settings\"><h2>Identity and settings</h2>" + channelFields(profile, false) + "<div class=\"form-actions\"><button type=\"submit\" class=\"primary\">Save channel</button></div></form><aside><h2>Current previews</h2><figure>" + preview(profilePreview(profile, 'video'), "Video style") + "<figcaption>Video · " + esc(profile.style_name) + '</figcaption></figure><figure>' + preview(profilePreview(profile, 'thumbnail'), "Thumbnail") + "<figcaption>Thumbnail · proposal to approve</figcaption></figure><a class=\"button\" href=\"#/styles/" + encode(profile.style_id) + '">' + icon('edit') + "Edit this style</a></aside></div><section class=\"section\"><h2>Channel status</h2><div class=\"inline\">" + badge(profile.archived ? 'unreviewed' : 'verified', profile.archived ? "Archived" : "Active") + '<button id="archive-channel">' + (profile.archived ? "Restore" : "Archive channel") + '</button></div></section>';
    $('#channel-settings').dataset.savedVoiceId = profile.voice?.voice_id || '';
    $('#channel-settings').dataset.savedVoiceName = profile.voice?.voice_name || profile.voice?.voice_id || '';
    $('#channel-settings').dataset.savedVoiceSpeed = profile.voice?.speed || 1;
    const preset = management.styles.find(style => style.id === profile.style_id);
    const styleLink = $('#channel-content aside a[href^="#/styles/"]');
    styleLink?.remove();
    $('#channel-content > .management-editor > aside')?.remove();
    $('#channel-content > .management-editor')?.classList.add('channel-identity-editor');
    $('#channel-content').insertAdjacentHTML('beforeend', '<section id="channel-preset-editor"></section>');
    if (preset) renderStyle(preset, $('#channel-preset-editor'), profile);
    $('#channel-settings button[type="submit"]').remove();
    $('.page-head .actions').insertAdjacentHTML('beforeend', '<button type="submit" form="channel-settings" class="primary">Save channel / preset</button>');
    $('#channel-settings').onsubmit = event => {
      event.preventDefault();
      const visualForm = $('#visual-style-form');
      if (visualForm && !visualForm.reportValidity()) return;
      if ($$('[data-character-form]').some(form => !form.reportValidity())) return;
      action(event.submitter, async () => {
        const body = channelPresetBody();
        await api('/api/workspace/management/presets/' + encode(profile.id), {method:'PUT', body});
        await route();
      }, 'Channel / preset saved.');
    };
    $('#archive-channel').onclick = () => archiveManaged('channels', profile, !profile.archived);
  }
  function backgroundModeField(mode = 'free') {
    return `<label class="full">Background mode<select name="background_mode"><option value="free"${mode !== 'consistent' ? ' selected' : ''}>Free backgrounds — each image can use a different setting</option><option value="consistent"${mode === 'consistent' ? ' selected' : ''}>Consistent locations — same place, varied camera views</option></select><span class="small muted">Character references stay consistent in both modes. This choice applies to new videos; existing videos keep their settings.</span></label>`;
  }
  function newStyle() {
    const fields = "<div class=\"form-grid\"><label class=\"full\">Style name<input name=\"name\" maxlength=\"200\" required></label><label class=\"full\">Video prompt<textarea name=\"prompt\" rows=\"6\" required></textarea></label><label class=\"full\">Background direction<textarea name=\"background_direction\" rows=\"3\"></textarea></label><label class=\"full\">Thumbnail prompt<textarea name=\"thumbnail_prompt\" rows=\"3\"></textarea></label></div>";
    managementDialog('New visual style', fields.replace('</div>', backgroundModeField() + '</div>'), async (form) => { const result = await api('/api/workspace/management/styles', {method:'POST', body:Object.fromEntries(new FormData(form))}); return '#/styles/' + encode(result.id); });
  }
  function duplicateStyle(style) {
    if (dirty) { notify("Save the style before duplicating it.", true); return; }
    action(null, async () => { const result = await api('/api/workspace/management/styles', {method:'POST', body:{name:style.name + " (copy)", base_id:style.id}}); location.hash = '#/styles/' + encode(result.id); }, "Style duplicated with its references.");
  }
  function renderStyles(id) {
    const linked = management.channels.filter(channel => !channel.archived && channel.style_id === id);
    if (id && linked.length === 1) { renderChannel(linked[0], 'settings'); return; }
    const style = management.styles.find((s) => s.id === id);
    if (style) { renderStyle(style); return; }
    if (id) { main.innerHTML = header("Style not found", '') + '<a href="#/styles">Revenir aux styles</a>'; return; }
    main.innerHTML = header("Visual styles", '', '<button id="new-style" class="primary">' + icon('plus') + 'Nouveau style</button>') + "<div class=\"toolbar\"><label class=\"search\">Search for a style<input id=\"style-search\" type=\"search\" value=\"" + esc(managementFilters.styles) + '"></label><label class="checkbox-label"><input id="archived-styles" type="checkbox"' + (managementFilters.archivedStyles ? ' checked' : '') + ">Show archives</label><span id=\"styles-count\" class=\"count\"></span></div><div id=\"styles-list\"></div>";
    const update = () => {
      managementFilters.styles = $('#style-search').value;
      managementFilters.archivedStyles = $('#archived-styles').checked;
      const items = management.styles.filter((s) => !!s.archived === managementFilters.archivedStyles && s.name.toLocaleLowerCase('en').includes(managementFilters.styles.toLocaleLowerCase('en')));
      $('#styles-count').textContent = items.length + ' style' + (items.length === 1 ? '' : 's');
      $('#styles-list').innerHTML = items.length ? '<div class="style-grid">' + items.map((s) => '<article class="style-item"><a class="style-image" href="#/styles/' + encode(s.id) + '">' + (s.video_preview_url ? '<img src="' + esc(safeUrl(s.video_preview_url)) + "\" alt=\"Preview of " + esc(s.name) + '">' : "<span>No preview</span>") + '</a><div class="style-item-content"><h2><a href="#/styles/' + encode(s.id) + '">' + esc(s.name) + '</a></h2><p class="small muted">' + management.channels.filter((c) => !c.archived && c.style_id === s.id).length + " channel(s) · " + s.references.length + " reference(s)</p><div class=\"actions\"><a class=\"button\" href=\"#/styles/" + encode(s.id) + '">' + icon('edit') + "Edit</a>" + (!s.archived ? '<button data-duplicate="' + esc(s.id) + "\">Duplicate</button>" : '<button data-restore-style="' + esc(s.id) + "\">Restore</button>") + '</div></div></article>').join('') + '</div>' : "<div class=\"empty\">No styles in this list.</div>";
      $$('[data-duplicate]').forEach((button) => button.onclick = () => duplicateStyle(items.find((s) => s.id === button.dataset.duplicate)));
      $$('[data-restore-style]').forEach((button) => button.onclick = () => archiveManaged('styles', items.find((s) => s.id === button.dataset.restoreStyle), false));
    };
    $('#new-style').onclick = newStyle;
    $('#style-search').oninput = update; $('#archived-styles').onchange = update; update();
  }
  function renderStyle(style, root = main, channel = null) {
    const used = management.channels.filter((c) => !c.archived && c.style_id === style.id);
    const refs = style.references.map((r) => ({...r}));
    root.innerHTML = '<div class="breadcrumbs"><a href="#/styles">Visual styles</a><span>/</span>' + esc(style.name) + '</div>' + header(style.name, countLabel(used.length, "channel") + ' · ' + countLabel(refs.length, "reference"), !style.archived ? "<button id=\"duplicate-style\">Duplicate style</button>" : "<button id=\"restore-style\">Restore style</button>") + "<div class=\"management-editor\"><form id=\"visual-style-form\"><h2>Style settings</h2><div class=\"form-grid\"><label class=\"full\">Style name<input name=\"name\" value=\"" + esc(style.name) + "\" maxlength=\"200\" required></label><label class=\"full\">Video prompt<textarea name=\"prompt\" rows=\"10\" required>" + esc(style.prompt) + "</textarea></label><label class=\"full\">Background direction<textarea name=\"background_direction\" rows=\"4\">" + esc(style.background_direction) + '</textarea></label><label class="full">Thumbnail prompt<textarea name="thumbnail_prompt" rows="5">' + esc(style.thumbnail_prompt) + "</textarea></label></div><div class=\"form-actions\"><button type=\"submit\" class=\"primary\">Save style</button></div></form><aside><h2>Style previews</h2><figure>" + preview(style.video_preview_url, "Video style") + "<figcaption>Video</figcaption></figure><figure>" + preview(style.thumbnail_preview_url, "Thumbnail style") + "<figcaption>Thumbnail</figcaption></figure><h3>Linked channels</h3><ul class=\"linked-channels\">" + (used.map((c) => '<li><a href="#/channels/' + encode(c.id) + '/settings">' + esc(c.name) + '</a></li>').join('') || "<li>No linked channels</li>") + "</ul></aside></div><section class=\"section\"><div class=\"page-head\"><h2>Visual references</h2><button id=\"save-style-refs\">Save references</button></div><ol class=\"reference-list\" id=\"style-references\"></ol><form id=\"style-upload\"><label>Add images<input name=\"files\" type=\"file\" accept=\"image/png,image/jpeg,image/webp\" multiple required" + (style.archived ? ' disabled' : '') + '></label><div class="form-actions"><button type="submit"' + (style.archived ? ' disabled' : '') + '>' + icon('plus') + "Add references</button></div><p id=\"upload-progress\" class=\"small muted\" role=\"status\"></p></form></section><section class=\"section\"><h2>Style status</h2><div class=\"inline\">" + badge(style.archived ? 'unreviewed' : 'verified', style.archived ? "Archived" : "Active") + (!style.is_default ? '<button id="archive-style">' + (style.archived ? "Restore" : "Archive style") + '</button>' : '') + '</div></section>';
    $('#visual-style-form .form-grid').insertAdjacentHTML('beforeend', backgroundModeField(style.background_mode));
    if (!style.archived) $('#duplicate-style').onclick = () => duplicateStyle(style);
    else $('#restore-style').onclick = () => archiveManaged('styles', style, false);
    if ($('#archive-style')) $('#archive-style').onclick = () => archiveManaged('styles', style, !style.archived);
    $('#visual-style-form').onsubmit = (event) => {
      event.preventDefault();
      if (used.length > 1 && !confirm("Save this style shared by " + used.length + " channels? Videos already created keep their settings.")) return;
      action(event.submitter, async () => { await api('/api/workspace/management/styles/' + encode(style.id), {method:'PUT', body:{...Object.fromEntries(new FormData(event.target)), references:refs}}); await route(); }, "Style saved.");
    };
    const renderRefs = () => {
      $('#style-references').innerHTML = refs.length ? refs.map((ref, index) => '<li><span class="small muted">' + (index + 1) + '</span><img src="' + esc(safeUrl(ref.url)) + "\" alt=\"Reference " + (index + 1) + '"><span class="ref-label">' + esc(ref.label || ref.path) + (!ref.exists ? '<span class="error-text"> · missing file</span>' : '') + '</span><div class="actions"><button type="button" class="icon-button" data-move="' + index + "\" data-direction=\"-1\" title=\"Move up\" aria-label=\"Move reference up " + (index + 1) + '"' + (index === 0 ? ' disabled' : '') + '>' + icon('up') + '</button><button type="button" class="icon-button" data-move="' + index + "\" data-direction=\"1\" title=\"Move down\" aria-label=\"Move reference down " + (index + 1) + '"' + (index === refs.length - 1 ? ' disabled' : '') + '>' + icon('down') + '</button><select data-preview-select="' + index + "\" aria-label=\"Preview for reference " + (index + 1) + "\"><option value=\"\">Choose a preview</option><option value=\"video_preview\">Video</option><option value=\"thumbnail_preview\">Thumbnail</option><option value=\"drawing_reference_path\">Use as drawing guide</option></select><button type=\"button\" class=\"icon-button\" data-remove-ref=\"" + index + "\" title=\"Remove from list\" aria-label=\"Remove reference " + (index + 1) + '">' + icon('close') + '</button></div></li>').join('') : "<li class=\"muted\">No references saved.</li>";
      $$('[data-move]').forEach((button) => button.onclick = () => { const from = Number(button.dataset.move), to = from + Number(button.dataset.direction); [refs[from],refs[to]] = [refs[to],refs[from]]; dirty = true; renderRefs(); });
      $$('[data-remove-ref]').forEach((button) => button.onclick = () => { refs.splice(Number(button.dataset.removeRef), 1); dirty = true; renderRefs(); });
      $$('[data-preview-select]').forEach((select) => select.onchange = () => {
        const role = select.value;
        if (!role) return;
        action(select, async () => {
          const path = refs[Number(select.dataset.previewSelect)].path;
          if (channel) {
            const body = channelPresetBody(); body.preset[role] = path;
            await api('/api/workspace/management/presets/' + encode(channel.id), {method:'PUT',body});
          } else {
            await api('/api/workspace/management/styles/' + encode(style.id), {method:'PUT', body:{...Object.fromEntries(new FormData($('#visual-style-form'))), references:refs, [role]:path}});
          }
          await route();
        }, role === 'drawing_reference_path' ? "Drawing guide saved." : "Preview saved.");
      });
      if (style.drawing_reference_path) {
        const index = refs.findIndex(ref => ref.path === style.drawing_reference_path);
        if (index >= 0) $$('[data-preview-select]')[index].closest('li').querySelector('.ref-label').insertAdjacentHTML('beforeend', '<span class="badge verified">Drawing guide</span>');
      }
    };
    renderRefs();
    renderStyleCharacters(style, root);
    $('#save-style-refs').onclick = (event) => { if ($('#visual-style-form [name="background_mode"]').value !== (style.background_mode || "free") || $('#visual-style-form [name="prompt"]').value !== style.prompt || $('#visual-style-form [name="name"]').value !== style.name || $('#visual-style-form [name="background_direction"]').value !== style.background_direction || $('#visual-style-form [name="thumbnail_prompt"]').value !== style.thumbnail_prompt) { notify("Save the style settings before references.", true); return; } action(event.currentTarget, async () => { await api('/api/workspace/management/styles/' + encode(style.id), {method:'PUT', body:{references:refs}}); await route(); }, "References saved."); };
    $('#style-upload').onsubmit = (event) => {
      event.preventDefault();
      if (dirty) { notify("Save your changes before adding images.", true); return; }
      action(event.submitter, async () => {
        let uploaded = 0;
        const files = [...$('[name="files"]', event.target).files];
        for (const file of files) {
          const form = new FormData(); form.append('file',file); form.append('label',file.name);
          try { await api('/api/workspace/management/styles/' + encode(style.id) + '/references', {method:'POST',body:form}); }
          catch (error) { throw new Error(uploaded + '/' + files.length + " images saved. " + error.message); }
          uploaded++; $('#upload-progress').textContent = uploaded + '/' + files.length + " images saved";
        }
        await route();
      }, "Images added in order.");
    };
    $('#visual-style-form').orderedReferences = refs;
    if (channel) {
      $('.breadcrumbs', root)?.remove();
      $('.page-head', root)?.remove();
      const name = $('#visual-style-form [name="name"]');
      name.closest('label').hidden = true;
      $('#visual-style-form h2').textContent = 'Drawing and background';
      $('#visual-style-form [name="prompt"]').closest('label').firstChild.textContent = 'Drawing instructions';
      $('#visual-style-form button[type="submit"]').hidden = true;
      $('#visual-style-form').onsubmit = event => { event.preventDefault(); $('#channel-settings').requestSubmit(); };
      $('#save-style-refs').onclick = () => $('#channel-settings').requestSubmit();
      $$('[data-character-form]', root).forEach(form => form.onsubmit = event => {
        event.preventDefault();
        $('#channel-settings').verifyCharacter = event.submitter?.name === 'verify' ? {name:form.dataset.name, variant:form.dataset.variant} : null;
        $('#channel-settings').requestSubmit();
      });
      $('#style-upload').onsubmit = event => {
        event.preventDefault();
        const files = [...$('[name="files"]', event.target).files];
        action(event.submitter, async () => {
          const saved = await api('/api/workspace/management/presets/' + encode(channel.id), {method:'PUT',body:channelPresetBody()});
          for (const file of files) {
            const payload = new FormData(); payload.append('file', file); payload.append('label', file.name);
            await api('/api/workspace/management/styles/' + encode(saved.preset.id) + '/references', {method:'POST',body:payload});
          }
          await route();
        }, 'Drawing references imported.');
      };
      $('#style-character-upload').onsubmit = event => {
        event.preventDefault();
        const fields = new FormData(event.target), files = [...$('[name="files"]', event.target).files];
        action(event.submitter, async () => {
          const saved = await api('/api/workspace/management/presets/' + encode(channel.id), {method:'PUT',body:channelPresetBody()});
          for (const file of files) {
            const payload = new FormData(); payload.append('file',file);
            for (const key of ['name','variant','description']) payload.append(key,fields.get(key));
            payload.append('is_main',fields.has('is_main') ? 'true' : 'false');
            await api('/api/workspace/management/styles/' + encode(saved.preset.id) + '/characters', {method:'POST',body:payload});
          }
          await route();
        }, 'Character references imported. Review and validate them here.');
      };
      const linked = $('.linked-channels', root);
      linked?.previousElementSibling?.remove(); linked?.remove();
      $('#archive-style')?.closest('.section')?.remove();
    }

  }
  function renderStyleCharacters(style, root = main) {
    const characters = style.characters || [];
    const disabled = style.archived ? ' disabled' : '';
    $('.management-editor', root).insertAdjacentHTML('afterend', `<section class="section character-style-section"><h2>Character references</h2><p class="muted">One main character and recurring characters per style. Upload their images, check them, then validate their references. New projects keep their cast.</p><div class="style-character-list">${characters.map((character) => character.variants.map((variant) => `<form class="style-character-card" data-character-form data-name="${esc(character.name)}" data-variant="${esc(variant.id)}"><div class="inline"><h3>${esc(character.name)} · ${esc(variant.id)}</h3>${character.main ? "<span class=\"badge verified\">Main</span>" : ''}</div><div class="character-reference-images">${variant.references.map((ref) => `<figure><a href="${esc(safeUrl(ref.url))}" target="_blank" rel="noopener"><img src="${esc(safeUrl(ref.url))}" alt="Reference for ${esc(character.name)}"></a><figcaption>${ref.valid ? "Validated" : ref.exists ? "To review" : "Missing file"}</figcaption></figure>`).join('')}</div><label>Fixed description<textarea name="description" rows="3" required${disabled}>${esc(variant.description)}</textarea></label><label class="inline"><input name="is_main" type="checkbox"${character.main ? ' checked' : ''}${disabled}>Main character</label><div class="form-actions"><button type="submit"${disabled}>Save</button><button type="submit" name="verify" value="true"${disabled}>Validate these references</button></div></form>`).join('')).join('') || "<p class=\"muted\">No character saved.</p>"}</div><form id="style-character-upload"><h3>Add a character or reference</h3><div class="form-grid"><label>Character name<input name="name" maxlength="100" required${disabled}></label><label>Variant<input name="variant" value="default" pattern="[A-Za-z0-9_-]+" maxlength="100" required${disabled}></label><label class="full">Fixed description<textarea name="description" rows="3" required${disabled}></textarea></label><label class="full">Reference images<input name="files" type="file" accept="image/png,image/jpeg,image/webp" multiple required${disabled}></label><label class="inline"><input name="is_main" type="checkbox"${!characters.length ? ' checked' : ''}${disabled}>Main character</label></div><div class="form-actions"><button type="submit"${disabled}>Import character references</button></div><p class="small muted">Reuse the same name and variant to add an image to the existing character.</p></form></section>`);
    $$('[data-character-form]').forEach((form) => form.onsubmit = (event) => {
      event.preventDefault();
      const fields = new FormData(form);
      action(event.submitter, async () => {
        await api('/api/workspace/management/styles/' + encode(style.id) + '/characters', {method:'PUT',body:{name:form.dataset.name,variant:form.dataset.variant,description:fields.get('description'),is_main:fields.has('is_main'),verify:event.submitter?.name === 'verify'}});
        await route();
      }, event.submitter?.name === 'verify' ? "Character references approved." : "Character saved.");
    });
    $('#style-character-upload').onsubmit = (event) => {
      event.preventDefault();
      const fields = new FormData(event.target);
      const files = [...$('[name="files"]',event.target).files];
      action(event.submitter, async () => {
        for (const file of files) {
          const payload = new FormData(); payload.append('file',file); payload.append('name',fields.get('name')); payload.append('variant',fields.get('variant')); payload.append('description',fields.get('description')); payload.append('is_main',fields.has('is_main') ? 'true' : 'false');
          await api('/api/workspace/management/styles/' + encode(style.id) + '/characters', {method:'POST',body:payload});
        }
        await route();
      }, "References imported: review them, then approve them.");
    };
  }
  function renderSettings() {
    const catalog = data.models;
    main.innerHTML = `${header("Settings", "Studio models and connection", '<button id="reload-models">' + icon('refresh') + 'Refresh catalog</button>')}${catalogNotice()}<div class="settings-layout"><section class="section"><h2>Default models</h2><form id="defaults-form"><div class="form-grid"><label>Text<select name="text_model" required>${modelOptions(catalog.defaults?.text_model, 'text')}</select></label><label>Images<select name="image_model" required>${modelOptions(catalog.defaults?.image_model, 'image', catalog.defaults?.image_provider)}</select></label></div><div class="form-actions"><button type="submit" class="primary" ${!modelsFrom(catalog).length ? 'disabled' : ''}>Save models</button></div></form><section class="section"><h2>Provider catalog</h2><p class="muted small">Models available via CLI Proxy and Google Flow. Availability depends on accounts and quotas.</p>${modelsFrom(catalog).length ? `<div class="table-wrap"><table><thead><tr><th>Model</th><th>Provider</th><th>Text</th><th>Image</th></tr></thead><tbody>${modelsFrom(catalog).map((model) => `<tr><td>${esc(model.id)}</td><td>${model.provider === 'google_flow' ? 'Google Flow' : 'CLI Proxy'}</td><td>${model.capabilities?.text === true ? "Announced" : model.capabilities?.text === false ? "Unannounced" : "Unconfirmed"}</td><td>${model.capabilities?.image === true ? "Announced" : model.capabilities?.image === false ? "Unannounced" : "Unconfirmed"}</td></tr>`).join('')}</tbody></table></div>` : "<p class=\"muted\">No models available.</p>"}</section></section><aside class="section"><h2>Connection</h2><dl class="definition-list"><div><dt>CLI Proxy</dt><dd>${badge(catalog.providers?.cli_proxy?.available ? 'verified' : 'blocked', catalog.providers?.cli_proxy?.available ? 'Catalog available' : data.connection?.has_proxy ? "Configured · catalog unavailable" : "To connect")}</dd></div><div><dt>Catalogue</dt><dd>${modelsFrom(catalog).length} models available</dd></div><div><dt>Production</dt><dd>Shared team workspace</dd></div></dl>${advanced([['settings', "Connection and advanced tools"], ['voices', "Voice management"]])}</aside></div>`;
    const flow = catalog.providers?.google_flow || {};
    const connection = $('.settings-layout aside');
    connection.insertAdjacentHTML('beforeend', `<section class="section"><h2>Google Flow via useapi</h2>${badge(flow.available ? 'verified' : 'blocked', flow.available ? "Connected" : flow.configured ? 'Indisponible' : "To configure")}<p class="small muted">Distribution across available accounts · up to 3 simultaneous images · one image per shot.</p>${flow.error ? `<p class="error-text">${esc(flow.error)}</p>` : ''}${flow.accounts?.length ? `<ul>${flow.accounts.map((account) => `<li>${esc(account.email)} · ${account.health === 'OK' ? "Connected" : "To reconnect"}</li>`).join('')}</ul>` : ''}</section>`);
    $('#reload-models').onclick = (event) => action(event.currentTarget, async () => { data.models = await api('/api/workspace/models/refresh', {method: 'POST'}); renderSettings(); }, "Catalog updated.");
    $('#defaults-form').onsubmit = (event) => {
      event.preventDefault();
      action(event.submitter, async () => {
        const form = new FormData(event.target);
        await api('/api/workspace/settings', { method: 'PUT', body: { text_model: form.get('text_model'), image_model: form.get('image_model'), image_provider: $('[name="image_model"]', event.target).selectedOptions[0]?.dataset.provider || 'cli_proxy' } }); await route();
      }, "Default models saved.");
    };
    renderPerformance();
    bindFormState();
  }
  async function renderPerformance() {
    const root = $('.settings-layout > section');
    if (!root) return;
    root.insertAdjacentHTML('afterbegin', '<section class="section"><h2>Production speed</h2><p class="muted small">Images run in parallel across the team. Each shot keeps its own character and location references. The first three images are a separate preview.</p><div id="performance-settings" style="margin-top:18px">Loading concurrency settings…</div></section>');
    try {
      const limits = await api('/api/workspace/performance');
      if (!root.isConnected) return;
      const fields = [['IMAGE_CONCURRENCY','CLI Proxy images at once',36],['LLM_CONCURRENCY','Text requests at once',24],['WORKSPACE_PLAN_CONCURRENCY','Shot planning batches at once',8],['TTS_CONCURRENCY','Voice requests at once',6],['PROJECT_PARALLEL','Projects at once',12],['RENDER_CONCURRENCY','Video renders at once',2]];
      $('#performance-settings').innerHTML = `<form id="performance-form"><div class="form-grid">${fields.map(([key,label,max]) => `<label>${label}<input name="${key}" type="number" min="1" max="${max}" value="${limits[key]}" required></label>`).join('')}</div><p class="small muted" style="margin-top:16px">Google Flow: ${limits.flow_concurrency} images at once. Native rendering: ${limits.render_workers} workers per render. Provider queues and quotas can affect waiting time.</p><div class="form-actions"><button type="submit" class="primary">Save production speed</button></div></form>`;
      $('#performance-form').onsubmit = event => {
        event.preventDefault(); action(event.submitter, async () => {
          await api('/api/workspace/performance', {method:'PUT',body:Object.fromEntries([...new FormData(event.target)].map(([k,v]) => [k,Number(v)]))});
          dirty = false; await route();
        }, 'Concurrency saved. New jobs will use these limits.');
      };
      bindFormState($('#performance-form'));
    } catch (error) { if (root.isConnected) $('#performance-settings').textContent = error.message; }
  }
  window.addEventListener('hashchange', () => route({ refresh: false }));
  window.addEventListener('beforeunload', (event) => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href^="#/"]');
    if (link && dirty && !window.confirm("Leave this page without saving changes?")) event.preventDefault();
  });
  document.addEventListener('pointerover', event => {
    const href = event.target.closest('a[href^="#/"]')?.getAttribute('href');
    if (!session || !href) return;
    const parts = href.slice(2).split('/');
    const path = parts[0] === 'video' && parts[1] ? projectReadPath(decodeURIComponent(parts[1])) :
      ['styles', 'channels'].includes(parts[0]) ? '/api/workspace/management' : null;
    if (path) navigationReads.get(path).catch(error => { if (error.status === 401) renderLogin(); });
  });
  let batchPolling = false;
  let voicePolling = false;
  setInterval(async () => {
    const parts = routeParts();
    if (voicePolling || document.hidden || submitting || dirty || parts[0] !== 'video' || parts[2] !== "voice" || !project?.running) return;
    voicePolling = true;
    const id = project.id;
    try {
      const latest = await navigationReads.get(projectReadPath(id), true);
      if (routeParts()[1] !== id || routeParts()[2] !== "voice" || dirty) return;
      const finished = !latest.running || latest.steps?.voiceover?.state !== project.steps?.voiceover?.state;
      project = latest;
      if (finished) { renderProject("voice"); bindFormState(); }
      else if ($('#voice-progress')) $('#voice-progress').outerHTML = voiceProgressMarkup(latest);
    } catch { /* Read again on the next tick without launching another synthesis. */ }
    finally { voicePolling = false; }
  }, 3000);
  setInterval(() => {
    const timer = $('[data-voice-elapsed]');
    if (timer && timer.dataset.started) timer.textContent = `Elapsed time: ${fmtTime(Math.max(0, Date.now() / 1000 - Number(timer.dataset.started)))}`;
  }, 1000);
  setInterval(async () => {
    const parts = routeParts();
    if (batchPolling || document.hidden || submitting || parts[0] !== 'video' || !['images', 'verification'].includes(parts[2]) || !(project?.running && project?.can_prepare_images && !project?.scenes?.length || ['queued', 'running', 'stopping'].includes(project?.workspace_batch?.state))) return;
    batchPolling = true;
    const id = project.id;
    try {
      const latest = await navigationReads.get(projectReadPath(id), true);
      if (routeParts()[1] !== id || (!$('#batch-workflow') && !$('#planning-workflow'))) return;
      if (dirty || $('#preview-dialog').open || ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
        if ($('#batch-workflow')) { $('#batch-workflow').outerHTML = batchMarkup(latest); bindBatchControls(); }
      } else { project = latest; renderScenes(routeParts()[2] === 'verification'); }
    } catch { /* Keep the visible job and try reading its status on the next tick. */ }
    finally { batchPolling = false; }
  }, 3000);
  setInterval(() => {
    const page = routeParts()[0] || 'videos';
    if (!session || document.hidden || dirty || submitting || $('#create-dialog').open || $('#preview-dialog').open || !['videos', 'video'].includes(page)) return;
    if (main.contains(document.activeElement) && document.activeElement !== main) return;
    route();
  }, 15000);
  setInterval(() => {
    if (session && !document.hidden && !submitting && routeParts()[0] === 'queue') renderProductionQueue();
  }, 5000);
  route();
})();
