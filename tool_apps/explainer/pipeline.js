// ============================================================
// Explainer pipeline — browser port of explainer-videos-src/generation_pipeline.py.
// Step order is identical to the Python `generate_project`:
//   1. chapter outline            (OpenRouter, json mode)
//   2. chapter scripts            (OpenRouter, 3 in parallel)
//      + icon specs + icon images (OpenRouter json + Replicate via relay)
//   3. per-chapter "chunks": voiceover (ElevenLabs direct) -> duration ->
//      SRT (Replicate whisper via relay, text fallback) -> segment plan
//      (OpenRouter json) -> scene images (Replicate via relay)
//   4. render: upload assets -> POST {renderApi}/render/explainer -> poll job
// Requires app.js (loaded before this file).
// ============================================================

const _cancelledProjects = new Set();
const _runningProjects = new Set();

function isProjectRunning(id) { return _runningProjects.has(id); }
function requestCancel(id) { _cancelledProjects.add(id); }

class ProjectCancelled extends Error {}
function _raiseIfCancelled(projectId) {
  if (_cancelledProjects.has(projectId)) throw new ProjectCancelled('Génération arrêtée par l\'utilisateur.');
}

// Simple concurrency limiter (replaces asyncio.Semaphore).
function pLimit(max) {
  let active = 0;
  const queue = [];
  const next = () => {
    if (active >= max || !queue.length) return;
    active++;
    const {fn, resolve, reject} = queue.shift();
    fn().then(resolve, reject).finally(() => { active--; next(); });
  };
  return fn => new Promise((resolve, reject) => { queue.push({fn, resolve, reject}); next(); });
}

// ============================================================
// Project CRUD (IndexedDB)
// ============================================================

async function createProject({topic, video_length_minutes, chapter_count, fps, width, height}) {
  const projects = await listProjects();
  const project = {
    id: newId('proj'),
    topic: String(topic || '').trim(),
    title: String(topic || '').trim(),
    video_length_minutes: Number(video_length_minutes) || 20,
    chapter_count_mode: chapter_count === 'auto' ? 'auto' : 'fixed',
    chapter_count: chapter_count === 'auto' ? null : Number(chapter_count),
    fps: Number(fps) || 24,
    width: Number(width) || 1920,
    height: Number(height) || 1080,
    position: projects.length,
    status: 'idle',
    current_step: 'Créé. Lancez la génération depuis la page projet.',
    error: null,
    progress: 0,
    created_at: new Date().toISOString(),
    settings: null,
    chapters: [],
    render: null,
  };
  await saveProject(project);
  await logEvent(project.id, 'info', 'project_created', `Projet créé: ${project.topic}`);
  return project;
}

function computeProjectProgress(project) {
  // outline 5% / scripts 20% / icons 20% / chunks 55%
  let progress = 0;
  const chapters = project.chapters || [];
  if (chapters.length) progress += 5;
  const total = Math.max(1, chapters.length);
  progress += 20 * chapters.filter(c => c.status === 'done').length / total;
  progress += 20 * chapters.filter(c => c.icon && c.icon.status === 'done').length / total;
  progress += 55 * chapters.filter(c => c.chunk && c.chunk.status === 'done').length / total;
  project.progress = Math.round(progress);
}

async function _step(project, event, message, level = 'info') {
  project.current_step = message;
  await saveProject(project);
  await logEvent(project.id, level, event, message);
}

// ============================================================
// 1. Chapter outline — port of generation_pipeline.py:prepare_project (510-543)
//    and _generate_chapter_outline (546-567)
// ============================================================

const PLACEHOLDER_CHAPTER_RE = /^(part|chapter|section|item|key idea)\s*#?\s*\d+$/i;
const PLACEHOLDER_TOPIC_MARKERS = ['key idea number', 'explained simply with concrete details', 'this part is about'];

// generation_pipeline.py:_validate_generated_outline (584-596)
function validateGeneratedOutline(chapters, topic) {
  if (!Array.isArray(chapters) || !chapters.length) throw new StepError('Le modèle n\'a renvoyé aucun chapitre.');
  const bad = [];
  for (const item of chapters) {
    const chapter = String((item || {}).chapter || '').trim();
    const chapterTopic = String((item || {}).chapter_topic || '').trim().toLowerCase();
    const normalized = chapter.toLowerCase().replace(/[^a-z0-9# ]+/g, ' ').trim();
    if (!chapter || PLACEHOLDER_CHAPTER_RE.test(normalized) || PLACEHOLDER_TOPIC_MARKERS.some(m => chapterTopic.includes(m))) {
      bad.push(chapter || '<missing>');
    }
  }
  if (bad.length) throw new StepError(`Le plan de chapitres pour "${topic}" contient des chapitres placeholder: ${bad.slice(0, 5).join(', ')}.`);
}

// generation_pipeline.py:_validate_or_choose_count (599-608)
function validateOrChooseCount(project, chapters) {
  if (project.chapter_count_mode === 'fixed' && project.chapter_count) {
    const count = Number(project.chapter_count);
    if (!VALID_CHAPTER_COUNTS.includes(count)) throw new StepError(`Nombre de chapitres invalide: ${count}`);
    return count;
  }
  const count = chapters.length;
  if (VALID_CHAPTER_COUNTS.includes(count)) return count;
  if (!count) return 12;
  return VALID_CHAPTER_COUNTS.reduce((best, item) => Math.abs(item - count) < Math.abs(best - count) ? item : best);
}

async function generateOutline(project, settings) {
  const requested = (project.chapter_count_mode === 'fixed' && project.chapter_count)
    ? `- The user selected exactly ${project.chapter_count} chapters. Return exactly that many chapters.`
    : '';
  const rendered = renderTemplate(getPrompt('chapter_outline'), {
    title: project.topic,
    valid_chapter_counts: VALID_CHAPTER_COUNTS.join(', '),
    requested_chapter_count_instruction: requested,
  });
  const model = settings.outline_model || settings.chat_model;
  const data = extractJsonObject(await openrouterComplete(model, rendered, {jsonMode: true}));
  let chapters = data.chapters || [];
  validateGeneratedOutline(chapters, project.topic);
  const selectedCount = validateOrChooseCount(project, chapters);
  if (chapters.length < selectedCount) {
    throw new StepError(`Le plan a renvoyé ${chapters.length} chapitres, mais ${selectedCount} sont requis.`);
  }
  chapters = chapters.slice(0, selectedCount);
  // prepare_project: total chars = minutes * wpm * 5.5; per chapter min 400.
  const totalCharacters = Math.floor(project.video_length_minutes * Number(settings.words_per_minute) * 5.5);
  const perChapter = Math.max(400, Math.round(totalCharacters / selectedCount));
  project.chapters = chapters.map((item, idx) => ({
    id: newId('chap'),
    chapter_number: idx + 1,
    chapter: String(item.chapter || `Chapter ${idx + 1}`).slice(0, 100),
    chapter_topic: String(item.chapter_topic || project.topic),
    output_length: perChapter,
    script_text: null,
    status: 'outlined',
    error: null,
    icon: null,
    chunk: null,
  }));
  project.chapter_count = selectedCount;
  await saveProject(project);
  await logEvent(project.id, 'info', 'chapters_ready', `${selectedCount} chapitres créés.`);
}

// ============================================================
// 2a. Chapter scripts — port of generation_pipeline.py:generate_scripts (611-661)
// ============================================================

// generation_pipeline.py:_ensure_script_starts_with_chapter (675-682)
function ensureScriptStartsWithChapter(text, chapterTitle) {
  const cleaned = String(text || '').trim();
  const title = String(chapterTitle || '').trim();
  if (!title) return cleaned;
  if (cleaned.toLowerCase().startsWith(title.toLowerCase())) return cleaned;
  return `${title}. ${cleaned}`;
}

async function generateScripts(project, settings) {
  const promptBody = getPrompt('chapter_script');
  const model = settings.script_model || settings.chat_model;
  const limit = pLimit(3); // asyncio.Semaphore(3) in generate_scripts
  await Promise.all(project.chapters.map(chapter => limit(async () => {
    if (chapter.script_text && chapter.status === 'done') return; // resume support
    try {
      _raiseIfCancelled(project.id);
      await _step(project, 'script_chapter_started', `Écriture du script du chapitre ${chapter.chapter_number}: ${chapter.chapter}.`);
      const wordTarget = Math.round(chapter.output_length / 5.5);
      const rendered = renderTemplate(promptBody, {
        chapter_number: chapter.chapter_number,
        chapter: chapter.chapter,
        chapter_topic: chapter.chapter_topic,
        word_target: wordTarget,
        min_words: Math.round(wordTarget * 0.8),
        max_words: Math.round(wordTarget * 1.2),
      });
      const text = ensureScriptStartsWithChapter((await openrouterComplete(model, rendered)).trim(), chapter.chapter);
      chapter.script_text = text;
      chapter.status = 'done';
      chapter.error = null;
      await saveProject(project);
      await logEvent(project.id, 'info', 'script_chapter_done', `Script du chapitre ${chapter.chapter_number} prêt.`);
    } catch (error) {
      if (error instanceof ProjectCancelled) throw error;
      chapter.status = 'failed';
      chapter.error = String(error.message || error);
      await saveProject(project);
      await logEvent(project.id, 'error', 'script_chapter_failed', `Chapitre ${chapter.chapter_number}: ${chapter.error}`);
    }
  })));
}

// ============================================================
// 2b. Icons — port of generation_pipeline.py:generate_thumbnail_assets (685-768)
//     and _generate_icon_specs (771-801)
// ============================================================

async function generateIconSpecs(project, settings) {
  const chaptersJson = JSON.stringify(
    project.chapters.map(c => ({chapter_number: c.chapter_number, chapter: c.chapter, chapter_topic: c.chapter_topic})),
    null, 2,
  );
  const rendered = renderTemplate(getPrompt('icon_prompts'), {
    total_chapters: project.chapters.length,
    chapters_json: chaptersJson,
  });
  const model = settings.visual_planning_model || settings.chat_model;
  const data = extractJsonObject(await openrouterComplete(model, rendered, {jsonMode: true}));
  const specs = data.image_prompts || [];
  if (!specs.length) throw new StepError('Le modèle n\'a renvoyé aucun prompt d\'icône.');
  return specs;
}

async function generateIcons(project, settings) {
  const allDone = project.chapters.every(c => c.icon && c.icon.status === 'done');
  if (allDone) return;
  const specs = await generateIconSpecs(project, settings);
  const retryPromptBody = getPrompt('sensitive_rewrite');
  const chatModel = settings.visual_planning_model || settings.chat_model;
  for (const chapter of project.chapters) {
    _raiseIfCancelled(project.id);
    if (chapter.icon && chapter.icon.status === 'done') continue; // resume support
    await _step(project, 'icon_started', `Rendu de l'icône du chapitre ${chapter.chapter_number}: ${chapter.chapter}.`);
    const spec = specs.find(item => Number(item.chapter_number || 0) === chapter.chapter_number) || {};
    let prompt = spec.image_prompt || `flat black pictogram for ${chapter.chapter} on cyan background`;
    const color = spec.circle_color || 'cyan';
    let done = false;
    let lastError = '';
    const retryCount = Number(settings.image_retry_count) || 5;
    for (let attempt = 1; attempt <= retryCount; attempt++) {
      _raiseIfCancelled(project.id);
      try {
        // Icons are always generated at 1024x1024 (generation_pipeline.py:711).
        const outputUrl = await replicateGenerateImage(settings.icon_image_model, prompt, {width: 1024, height: 1024});
        const blob = await tryFetchBlob(outputUrl);
        const name = `icons/icon_${chapter.chapter_number}.png`;
        await saveAsset(project.id, name, {blob, mime: blob ? blob.type : 'image/png', remoteUrl: outputUrl});
        chapter.icon = {circle_color: color, icon_description: spec.icon_description || 'simple black pictogram', image_prompt: prompt, status: 'done', asset_name: name, error: null};
        done = true;
        break;
      } catch (error) {
        if (error instanceof ProjectCancelled) throw error;
        lastError = String(error.message || error);
        // Configuration errors will not improve by retrying.
        if (lastError.startsWith('⚠️')) break;
        await logEvent(project.id, 'error', 'icon_attempt_failed', `Icône ${chapter.chapter_number} tentative ${attempt}/${retryCount}: ${lastError}`);
        // Sensitive prompt rewrite (generation_pipeline.py:724-736).
        try {
          const rewrite = renderTemplate(retryPromptBody, {prompt, chapter_number: chapter.chapter_number});
          const rewritten = (await openrouterComplete(chatModel, rewrite)).trim();
          if (rewritten) prompt = rewritten;
        } catch (rewriteError) {
          await logEvent(project.id, 'error', 'icon_rewrite_failed', `Réécriture sûre de l'icône ${chapter.chapter_number} échouée: ${rewriteError.message || rewriteError}`);
        }
      }
    }
    if (!done) {
      chapter.icon = {circle_color: color, icon_description: spec.icon_description || 'simple black pictogram', image_prompt: prompt, status: 'failed', asset_name: null, error: `Génération d'icône échouée pour ${chapter.chapter}: ${lastError || 'erreur fournisseur inconnue'}`};
      await logEvent(project.id, 'error', 'icon_failed', chapter.icon.error);
    } else {
      await logEvent(project.id, 'info', 'icon_done', `Icône ${chapter.chapter_number} prête.`);
    }
    await saveProject(project);
  }
}

// generation_pipeline.py:_missing_required_icons / _ensure_required_icons_ready (243-262)
function missingRequiredIcons(project) {
  return project.chapters.filter(c => !(c.icon && c.icon.status === 'done' && c.icon.asset_name));
}
function ensureRequiredIconsReady(project) {
  const missing = missingRequiredIcons(project);
  if (!missing.length) return;
  // If the failures come from a missing render API / provider key, surface
  // that message directly (degraded mode, no crash).
  const configError = missing.map(c => c.icon && c.icon.error || '').find(e => e.includes('⚠️'));
  if (configError) throw new StepError(configError);
  const labels = missing.slice(0, 5).map(c => `${c.chapter_number}. ${c.chapter}`).join(', ');
  const suffix = missing.length <= 5 ? '' : ` et ${missing.length - 5} de plus`;
  throw new StepError(`Icône(s) requise(s) manquante(s) ou en échec: ${labels}${suffix}. Relancez la génération des icônes avant les chunks.`);
}

// ============================================================
// 3. Chunks — port of generation_pipeline.py:generate_chunks/render_chunk (843-1027)
// ============================================================

// generation_pipeline.py:_parse_srt_start_times (1214-1224)
function parseSrtStartTimes(srt) {
  const starts = {};
  const pattern = /^\s*(\d+)\s*\n\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->/gm;
  let match;
  while ((match = pattern.exec(srt || '')) !== null) {
    starts[Number(match[1])] = Number(match[2]) * 3600 + Number(match[3]) * 60 + Number(match[4]) + Number(match[5]) / 1000;
  }
  return starts;
}

// generation_pipeline.py:_coerce_srt_start_line (1227-1231)
function coerceSrtStartLine(value) {
  const parsed = parseInt(value, 10);
  return Number.isFinite(parsed) ? Math.max(1, parsed) : 1;
}

// generation_pipeline.py:_apply_srt_segment_durations (1175-1211)
function applySrtSegmentDurations(segments, srt, totalAudio) {
  const srtStarts = parseSrtStartTimes(srt);
  if (!segments.length || !Object.keys(srtStarts).length || totalAudio <= 0) return false;
  const computed = [];
  for (let idx = 0; idx < segments.length; idx++) {
    const startLine = coerceSrtStartLine(segments[idx].srt_start_line);
    const startTime = idx === 0 ? 0 : srtStarts[startLine];
    if (startTime === undefined) return false;
    let endTime = totalAudio;
    for (const later of segments.slice(idx + 1)) {
      const laterStartLine = coerceSrtStartLine(later.srt_start_line);
      if (laterStartLine !== startLine) {
        endTime = srtStarts[laterStartLine];
        if (endTime === undefined) return false;
        break;
      }
    }
    let firstInGroup = idx;
    while (firstInGroup > 0 && coerceSrtStartLine(segments[firstInGroup - 1].srt_start_line) === startLine) firstInGroup--;
    let lastInGroup = idx;
    while (lastInGroup < segments.length - 1 && coerceSrtStartLine(segments[lastInGroup + 1].srt_start_line) === startLine) lastInGroup++;
    const sharingCount = lastInGroup - firstInGroup + 1;
    const segmentDuration = Math.max(0.25, (endTime - startTime) / Math.max(1, sharingCount));
    computed.push([startLine, Math.round(segmentDuration * 1000) / 1000]);
  }
  segments.forEach((segment, i) => {
    segment.srt_start_line = computed[i][0];
    segment.duration_sec = computed[i][1];
  });
  return true;
}

// generation_pipeline.py:_fallback_segment_plan (1101-1127)
function fallbackSegmentPlan(chunkNumber, chapter, duration) {
  const remaining = Math.max(4.0, duration - 3.0);
  const sceneCount = Math.max(1, Math.ceil(remaining / 6.0));
  const segments = [{segment_id: 1, type: 'intro_animation', duration_sec: 3.0, srt_start_line: 1, image_filename: 'image_1', chapter_title: chapter.chapter}];
  for (let idx = 0; idx < sceneCount; idx++) {
    segments.push({
      segment_id: idx + 2,
      type: idx % 3 !== 1 ? 'ai_image' : 'b_roll',
      duration_sec: remaining / sceneCount,
      srt_start_line: idx + 1,
      image_filename: `image_${idx + 2}`,
      chapter_title: chapter.chapter,
      prompt: `A clear educational illustration of ${chapter.chapter}: ${chapter.chapter_topic}. Cinematic documentary style, clean composition.`,
      search_query: `${chapter.chapter} historical image`,
    });
  }
  return {chunk_id: chunkNumber, total_segments: segments.length, total_images: segments.length, segments};
}

// generation_pipeline.py:_fallback_scene_prompt (1497-1500)
function fallbackScenePrompt(chapter, segment) {
  if (segment.type === 'b_roll' && segment.search_query) {
    return `A clear documentary-style educational image showing ${segment.search_query} for the chapter ${chapter.chapter}.`;
  }
  return `A clear educational illustration of ${chapter.chapter}: ${chapter.chapter_topic}. Clean composition, concrete visual details.`;
}

// generation_pipeline.py:_convert_broll_to_ai_images (1165-1172).
// The browser build has no web image-search API, so it always runs the Python
// "ai_images_only" path: every planned b_roll becomes an AI image.
function convertBrollToAiImages(segments, chapterTitle) {
  for (const segment of segments) {
    if (segment.type !== 'b_roll') continue;
    segment.type = 'ai_image';
    if (!segment.prompt) {
      const subject = String(segment.search_query || '').trim() || chapterTitle;
      segment.prompt = `A clear documentary-style educational image showing ${subject} for the chapter ${chapterTitle}.`;
    }
  }
}

const SEGMENT_TYPES = new Set(['intro_animation', 'ai_image', 'b_roll', 'composite']);

// generation_pipeline.py:_normalize_segments (1130-1162), with ai_images_only=true.
function normalizeSegments(plan, duration, chapterTitle, srt) {
  let raw = plan.segments || [];
  if (!raw.length) raw = fallbackSegmentPlan(1, {chapter: chapterTitle, chapter_topic: chapterTitle}, duration).segments;
  if (raw[0].type !== 'intro_animation') {
    raw.unshift({type: 'intro_animation', srt_start_line: 1, image_filename: 'image_1', chapter_title: chapterTitle});
  }
  if (!(srt && applySrtSegmentDurations(raw, srt, duration))) {
    const totalKnown = raw.reduce((sum, item) => sum + (Number(item.duration_sec) || 0), 0);
    if (totalKnown <= 0) {
      raw[0].duration_sec = Math.min(3.0, duration);
      const remaining = Math.max(0.1, duration - raw[0].duration_sec);
      const each = remaining / Math.max(1, raw.length - 1);
      for (const item of raw.slice(1)) item.duration_sec = each;
    } else {
      const scale = duration / totalKnown;
      for (const item of raw) item.duration_sec = Math.max(0.25, (Number(item.duration_sec) || 3) * scale);
    }
  }
  const normalized = raw.map((item, i) => {
    if (!SEGMENT_TYPES.has(item.type)) item.type = 'ai_image';
    item.segment_id = i + 1;
    item.image_filename = item.image_filename || `image_${i + 1}`;
    item.chapter_title = item.chapter_title || chapterTitle;
    item.status = 'queued';
    item.error = null;
    item.asset_name = null;
    item.remote_url = null;
    return item;
  });
  convertBrollToAiImages(normalized, chapterTitle);
  return normalized;
}

// generation_pipeline.py:_create_transcription_srt (1046-1062) — whisper via
// relay when available, otherwise the same text-based fallback.
async function createTranscriptionSrt(settings, audioBlob, duration, fallbackSourceText) {
  const fallback = buildSrtFromText(fallbackSourceText, duration);
  if (!settings.transcription_enabled) return fallback;
  if (!RENDER_READY || !KEYS.replicate) return fallback; // mirrors `if not client.available: return fallback_text`
  try {
    const dataUrl = await blobToDataUrl(audioBlob);
    const output = await replicateTranscribeWords(dataUrl);
    return buildSrtFromWordTimestamps(output, duration);
  } catch (_) {
    return fallback;
  }
}

// generation_pipeline.py:_create_segment_plan (1076-1098)
async function createSegmentPlan(project, chapter, chunkNumber, srt, duration, settings) {
  const rendered = renderTemplate(getPrompt('segment_planner'), {
    chunk_id: chunkNumber,
    chapter_number: chapter.chapter_number,
    chapter: chapter.chapter,
    chapter_topic: chapter.chapter_topic,
    script: chapter.script_text || '',
    srt,
    audio_duration: Math.round(duration * 100) / 100,
  });
  const model = settings.visual_planning_model || settings.chat_model;
  const data = extractJsonObject(await openrouterComplete(model, rendered, {jsonMode: true}));
  if (!data.segments || !data.segments.length) throw new StepError(`Le planificateur n'a renvoyé aucun segment pour ${chapter.chapter}.`);
  return data;
}

// generation_pipeline.py:render_segment/_render_segment_image (1303-1485), browser side:
// generate the raw scene image only — framing/encoding happens on the render API.
async function renderSegmentImage(project, chapter, chunk, segment, settings) {
  if (segment.type === 'intro_animation') { segment.status = 'done'; return; }
  if (segment.status === 'done' && (segment.asset_name || segment.remote_url)) return; // resume
  segment.status = 'running';
  const prompt = segment.prompt || fallbackScenePrompt(chapter, segment);
  segment.prompt = prompt;
  let referenceUrl = null;
  if (segment.type === 'composite' && segment.reference_filename) {
    // Python: _public_or_data_url(previous image) (generation_pipeline.py:1558-1562).
    const previous = chunk.segments.find(item => item.image_filename === segment.reference_filename);
    if (previous) {
      const previousAsset = previous.asset_name ? await getAsset(project.id, previous.asset_name) : null;
      if (previousAsset && previousAsset.blob) referenceUrl = await blobToDataUrl(previousAsset.blob);
      else if (previous.remote_url) referenceUrl = previous.remote_url;
    }
  }
  const model = segment.type === 'composite' ? settings.edit_image_model : settings.scene_image_model;
  const outputUrl = await replicateGenerateImage(model, prompt, {width: project.width, height: project.height, referenceUrl});
  const blob = await tryFetchBlob(outputUrl);
  const name = `chunks/chunk_${chunk.chunk_number}/${segment.image_filename}.png`;
  await saveAsset(project.id, name, {blob, mime: blob ? blob.type : 'image/png', remoteUrl: outputUrl});
  segment.asset_name = name;
  segment.remote_url = outputUrl;
  segment.status = 'done';
  segment.error = null;
}

// generation_pipeline.py:render_chunk (882-1027), without the local ffmpeg
// assembly (the render API does framing + still-to-video + concat + mux).
async function renderChunk(project, chapter, settings) {
  _raiseIfCancelled(project.id);
  if (!chapter.chunk) {
    chapter.chunk = {chunk_number: chapter.chapter_number, status: 'queued', error: null, audio_duration: null, voice_asset: null, srt: null, segments: []};
  }
  const chunk = chapter.chunk;
  chunk.status = 'running';
  chunk.error = null;
  await saveProject(project);
  try {
    // --- Voiceover (ElevenLabs direct) ---
    if (!chunk.voice_asset || !chunk.audio_duration) {
      await _step(project, 'chunk_voiceover_started', `Chunk ${chunk.chunk_number}: création de la voix off.`);
      const audioBlob = await elevenlabsTts(settings, chapter.script_text || chapter.chapter_topic);
      const voiceName = `chunks/chunk_${chunk.chunk_number}/voiceover.mp3`;
      await saveAsset(project.id, voiceName, {blob: audioBlob, mime: 'audio/mpeg'});
      chunk.voice_asset = voiceName;
      chunk.audio_duration = await blobAudioDuration(audioBlob);
      await saveProject(project);
    }
    _raiseIfCancelled(project.id);
    const voiceAsset = await getAsset(project.id, chunk.voice_asset);
    if (!voiceAsset || !voiceAsset.blob) throw new StepError('Voix off introuvable en stockage local.');

    // --- Transcription SRT ---
    if (!chunk.srt) {
      await _step(project, 'chunk_transcription_started', `Chunk ${chunk.chunk_number}: création de la transcription.`);
      chunk.srt = await createTranscriptionSrt(settings, voiceAsset.blob, chunk.audio_duration, chapter.script_text || '');
      await saveProject(project);
    }
    _raiseIfCancelled(project.id);

    // --- Segment plan ---
    if (!chunk.segments || !chunk.segments.length) {
      await _step(project, 'chunk_segment_plan_started', `Chunk ${chunk.chunk_number}: planification des segments visuels.`);
      const plan = await createSegmentPlan(project, chapter, chunk.chunk_number, chunk.srt, chunk.audio_duration, settings);
      chunk.segments = normalizeSegments(plan, chunk.audio_duration, chapter.chapter, chunk.srt);
      await saveProject(project);
      await logEvent(project.id, 'info', 'chunk_segments_ready', `Chunk ${chunk.chunk_number}: ${chunk.segments.length} segments planifiés.`);
    }
    _raiseIfCancelled(project.id);

    // --- Segment images: independent ones in parallel, composites after ---
    const failures = [];
    const firstWave = chunk.segments.filter(item => item.type !== 'composite');
    const composites = chunk.segments.filter(item => item.type === 'composite');
    const limit = pLimit(Number(settings.segment_parallelism) || 4);
    const runOne = async segment => {
      try {
        _raiseIfCancelled(project.id);
        await _step(project, 'segment_started', `Chunk ${chunk.chunk_number}: rendu du segment ${segment.segment_id} (${segment.type}).`);
        await renderSegmentImage(project, chapter, chunk, segment, settings);
        await saveProject(project);
      } catch (error) {
        if (error instanceof ProjectCancelled) throw error;
        segment.status = 'failed';
        segment.error = String(error.message || error);
        failures.push(segment);
        await saveProject(project);
        await logEvent(project.id, 'error', 'segment_failed', `Chunk ${chunk.chunk_number} segment ${segment.segment_id}: ${segment.error}`);
      }
    };
    await Promise.all(firstWave.map(segment => limit(() => runOne(segment))));
    for (const segment of composites) { _raiseIfCancelled(project.id); await runOne(segment); }

    if (failures.length) {
      chunk.status = 'failed';
      chunk.error = `${failures.length} segment(s) en échec. Relancez pour terminer ce chunk.`;
      await saveProject(project);
      await logEvent(project.id, 'error', 'chunk_partial', `Chunk ${chunk.chunk_number}: ${chunk.error}`);
      return;
    }
    chunk.status = 'done';
    chunk.error = null;
    await saveProject(project);
    await logEvent(project.id, 'info', 'chunk_done', `Chunk ${chunk.chunk_number}: assets prêts.`);
  } catch (error) {
    if (error instanceof ProjectCancelled) {
      chunk.status = 'cancelled';
      chunk.error = 'Arrêté par l\'utilisateur.';
      await saveProject(project);
      throw error;
    }
    chunk.status = 'failed';
    chunk.error = String(error.message || error);
    await saveProject(project);
    await logEvent(project.id, 'error', 'chunk_failed', `Chunk ${chunk.chunk_number} en échec: ${chunk.error}`);
  }
}

// ============================================================
// Full project generation — port of generation_pipeline.py:generate_project (396-431)
// ============================================================

function allChunksReady(project) {
  return project.chapters.length > 0 && project.chapters.every(c =>
    c.chunk && c.chunk.status === 'done' && c.chunk.segments.length &&
    c.chunk.segments.every(s => s.status === 'done'));
}

function incompleteGenerationMessage(project) {
  const failedScripts = project.chapters.filter(c => c.status === 'failed').length;
  const failedIcons = project.chapters.filter(c => c.icon && c.icon.status === 'failed').length;
  const failedChunks = project.chapters.filter(c => c.chunk && c.chunk.status === 'failed').length;
  const incompleteChunks = project.chapters.filter(c => !c.chunk || c.chunk.status !== 'done').length;
  const parts = [];
  if (failedScripts) parts.push(`${failedScripts} script(s) en échec`);
  if (failedIcons) parts.push(`${failedIcons} icône(s) en échec`);
  if (failedChunks) parts.push(`${failedChunks} chunk(s) en échec`);
  if (incompleteChunks && !failedChunks) parts.push(`${incompleteChunks} chunk(s) incomplet(s)`);
  if (!parts.length) parts.push('assemblage final incomplet');
  return 'Génération terminée avec un résultat partiel: ' + parts.join(', ') + '. Relancez les éléments en échec.';
}

async function generateProject(projectId) {
  if (_runningProjects.has(projectId)) return;
  _runningProjects.add(projectId);
  _cancelledProjects.delete(projectId);
  const project = await getProject(projectId);
  const settings = project.settings && project.status !== 'idle' ? Object.assign({}, loadSettings(), project.settings) : loadSettings();
  project.settings = settings;
  project.status = 'running';
  project.error = null;
  project.started_at = new Date().toISOString();
  await _step(project, 'project_started', 'Génération du projet démarrée.');
  try {
    // 1. Outline
    if (!project.chapters.length) {
      await _step(project, 'outline_started', 'Préparation des chapitres.');
      await generateOutline(project, settings);
    }
    _raiseIfCancelled(project.id);
    computeProjectProgress(project);

    // 2. Scripts + icons (parallel, like asyncio.gather in generate_project:404)
    await _step(project, 'scripts_started', 'Génération des scripts et des icônes.');
    const stageResults = await Promise.allSettled([generateScripts(project, settings), generateIcons(project, settings)]);
    _raiseIfCancelled(project.id);
    for (const [stage, result] of [['scripts', stageResults[0]], ['icons', stageResults[1]]]) {
      if (result.status === 'rejected') {
        if (result.reason instanceof ProjectCancelled) throw result.reason;
        await logEvent(project.id, 'error', `${stage}_failed`, String(result.reason && result.reason.message || result.reason), );
      }
    }
    computeProjectProgress(project);
    ensureRequiredIconsReady(project);

    // 3. Chunks (worker_count in parallel, like generate_chunks:860)
    await _step(project, 'chunks_started', 'Génération des chunks vidéo.');
    const limit = pLimit(Number(settings.worker_count) || 2);
    await Promise.all(project.chapters.map(chapter => limit(async () => {
      _raiseIfCancelled(project.id);
      if (!chapter.script_text) {
        chapter.chunk = {chunk_number: chapter.chapter_number, status: 'failed', error: 'Script manquant.', segments: [], voice_asset: null, srt: null, audio_duration: null};
        await saveProject(project);
        return;
      }
      await renderChunk(project, chapter, settings);
      computeProjectProgress(project);
      await saveProject(project);
    })));
    _raiseIfCancelled(project.id);

    computeProjectProgress(project);
    if (allChunksReady(project)) {
      project.status = 'assets_ready';
      project.error = null;
      await _step(project, 'assets_ready', 'Tous les assets sont prêts. Lancez le rendu MP4.');
    } else {
      project.status = 'needs_attention';
      project.error = incompleteGenerationMessage(project);
      await _step(project, 'project_partial', project.error, 'error');
    }
  } catch (error) {
    if (error instanceof ProjectCancelled) {
      project.status = 'cancelled';
      project.error = 'Génération arrêtée par l\'utilisateur.';
      await _step(project, 'project_cancelled', 'Arrêté. Relancez pour reprendre le travail restant.');
    } else {
      project.status = 'needs_attention';
      project.error = String(error.message || error);
      await _step(project, 'project_failed', project.error, 'error');
    }
  } finally {
    project.finished_at = new Date().toISOString();
    computeProjectProgress(project);
    await saveProject(project);
    _runningProjects.delete(projectId);
    _cancelledProjects.delete(projectId);
  }
  return project;
}

async function cancelProject(projectId) {
  requestCancel(projectId);
  const project = await getProject(projectId);
  if (!_runningProjects.has(projectId) && project.status === 'running') {
    project.status = 'cancelled';
    project.error = 'Génération arrêtée par l\'utilisateur.';
    await saveProject(project);
  }
  await logEvent(projectId, 'info', 'project_cancel_requested', 'Arrêt demandé.');
}

// ============================================================
// 4. Render — upload assets + POST /render/explainer + poll /jobs/{id}
//    Manifest shape: see website-tools/CONTRACT-explainer.md.
// ============================================================

async function _assetRef(project, name, remoteUrl, filename) {
  const asset = name ? await getAsset(project.id, name) : null;
  if (asset && asset.blob) {
    const uploadId = await uploadBlob(asset.blob, filename);
    return `upload:${uploadId}`;
  }
  const url = (asset && asset.remote_url) || remoteUrl || '';
  if (!url) throw new StepError(`Asset manquant: ${name || filename}`);
  return url;
}

async function buildRenderManifest(project) {
  const settings = project.settings || loadSettings();
  const chapters = [];
  for (const chapter of project.chapters) {
    const chunk = chapter.chunk;
    const iconRef = await _assetRef(project, chapter.icon && chapter.icon.asset_name, chapter.icon && chapter.icon.remote_url, `icon_${chapter.chapter_number}.png`);
    const voiceRef = await _assetRef(project, chunk.voice_asset, null, `voiceover_${chapter.chapter_number}.mp3`);
    const segments = [];
    for (const segment of chunk.segments) {
      const entry = {
        segment_id: segment.segment_id,
        type: segment.type,
        duration_sec: Math.round(Number(segment.duration_sec) * 1000) / 1000,
      };
      if (segment.type !== 'intro_animation') {
        entry.image = await _assetRef(project, segment.asset_name, segment.remote_url, `${segment.image_filename}_${chapter.chapter_number}.png`);
      }
      segments.push(entry);
    }
    chapters.push({
      chapter_number: chapter.chapter_number,
      chapter: chapter.chapter,
      icon: iconRef,
      voiceover: voiceRef,
      audio_duration: Math.round(Number(chunk.audio_duration) * 1000) / 1000,
      segments,
    });
  }
  return {
    version: 1,
    tool: 'explainer',
    project: {
      title: project.title,
      topic: project.topic,
      width: project.width,
      height: project.height,
      fps: project.fps,
    },
    style: {
      frame_style: settings.frame_style,
      background_color: settings.background_color,
      border_color: settings.border_color,
      border_width: Number(settings.border_width),
      font_color: settings.font_color,
    },
    thumbnail: {enabled: true, width: project.width, height: project.height},
    chapters,
  };
}

async function renderProject(projectId, onProgress = null) {
  const project = await getProject(projectId);
  if (!RENDER_READY) throw new StepError(MSG_NO_RENDER_API);
  if (!allChunksReady(project)) throw new StepError('Tous les chunks ne sont pas prêts — terminez la génération d\'abord.');
  ensureRequiredIconsReady(project);
  project.render = {status: 'uploading', job_id: null, progress: 0, message: 'Upload des assets...', output_url: null, thumbnail_url: null, error: null, started_at: new Date().toISOString()};
  project.status = 'rendering';
  await _step(project, 'render_upload_started', 'Upload des assets vers la render API.');
  try {
    const manifest = await buildRenderManifest(project);
    project.render.status = 'submitting';
    project.render.message = 'Lancement du job de rendu...';
    await saveProject(project);
    const jobId = await startRenderJob(manifest);
    project.render.job_id = jobId;
    project.render.status = 'running';
    await _step(project, 'render_job_started', `Job de rendu lancé: ${jobId}.`);
    while (true) {
      _raiseIfCancelled(project.id);
      await sleep(2000);
      const job = await getJobStatus(jobId);
      project.render.progress = Number(job.progress) || 0;
      project.render.message = job.message || job.status;
      await saveProject(project);
      if (onProgress) onProgress(project.render);
      if (job.status === 'done') {
        project.render.status = 'done';
        project.render.output_url = absoluteRenderUrl(job.output_url || `/jobs/${jobId}/output`);
        if (job.thumbnail_url) project.render.thumbnail_url = absoluteRenderUrl(job.thumbnail_url);
        project.render.finished_at = new Date().toISOString();
        project.status = 'done';
        project.progress = 100;
        await _step(project, 'project_done', 'MP4 final prêt.');
        return project.render;
      }
      if (job.status === 'error') {
        throw new StepError(`Rendu en échec: ${job.message || 'erreur inconnue'}`);
      }
    }
  } catch (error) {
    project.render = project.render || {};
    if (error instanceof ProjectCancelled) {
      project.render.status = 'cancelled';
      project.status = 'assets_ready';
      project.render.error = 'Rendu interrompu côté navigateur (le job serveur peut continuer).';
    } else {
      project.render.status = 'error';
      project.render.error = String(error.message || error);
      project.status = 'needs_attention';
      project.error = project.render.error;
    }
    await saveProject(project);
    await logEvent(project.id, 'error', 'render_failed', String(error.message || error));
    throw error;
  }
}
