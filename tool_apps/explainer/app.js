// ============================================================
// Shared runtime for the static Explainer Videos frontend.
// The whole workflow runs IN THE BROWSER:
//   - LLM (outline, scripts, plans)  -> OpenRouter, direct fetch
//   - TTS voiceover                  -> ElevenLabs, direct fetch
//   - Images (icons, scenes)         -> Replicate, via the render-API relay
//   - ffmpeg assembly                -> render API (POST /render/explainer)
// ../config.js must be loaded BEFORE this file: it defines
// window.VIDEO_TOOLS = { renderApi, keys: {...} }.
// Projects/assets/events live in IndexedDB; settings/prompts in localStorage.
// ============================================================

const VT = window.VIDEO_TOOLS || { renderApi: '', keys: {} };
const RENDER_API = String(VT.renderApi || '').replace(/\/+$/, '');
const RENDER_READY = Boolean(RENDER_API);
const KEYS = VT.keys || {};
const RENDER_TOKEN = String(VT.renderToken || '');
// OpenAI-compatible LLM proxy base (cliwebproxy, not openrouter.ai).
const LLM_BASE = String(VT.llmBase || 'https://openrouter.ai/api/v1').replace(/\/+$/, '');

// Secret token required by the render API. Returns the X-Render-Token header
// when configured, or an empty object so callers can spread it unconditionally.
function renderTokenHeader() {
  return RENDER_TOKEN ? {'X-Render-Token': RENDER_TOKEN} : {};
}

// --- Degraded-mode messages (French, per page contract) ---
const MSG_NO_RENDER_API = '⚠️ Render API non configurée — renseignez config.js';
const MSG_NO_OPENROUTER = '⚠️ Clé OpenRouter manquante — renseignez config.js';
const MSG_NO_ELEVENLABS = '⚠️ Clé ElevenLabs manquante — renseignez config.js';
const MSG_NO_REPLICATE = '⚠️ Clé Replicate manquante — renseignez config.js';
const MSG_NO_VOICE_ID = '⚠️ Voice ID ElevenLabs manquant — renseignez-le dans Settings';

class StepError extends Error {}

// --- Small helpers ---
function escapeHtml(v) { return String(v ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function escapeAttr(v) { return escapeHtml(v).replace(/'/g, '&#39;'); }
function localTime(ts) {
  if (!ts) return '';
  const parsed = new Date(ts);
  return Number.isNaN(parsed.getTime()) ? String(ts) : parsed.toLocaleString(undefined, {dateStyle:'medium', timeStyle:'short'});
}
function newId(prefix) { return `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`; }
function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

// Render a Python-style {{variable}} prompt template.
// Port of template_engine.py:render_template.
function renderTemplate(template, values) {
  return String(template || '').replace(/{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}/g, (_, key) => {
    const value = values[key];
    return value === undefined || value === null ? '' : String(value);
  });
}

// Port of providers.py:extract_json_object — tolerant JSON extraction.
function extractJsonObject(text) {
  let raw = String(text || '').trim();
  if (raw.startsWith('```')) {
    raw = raw.replace(/^`+/, '').replace(/`+$/, '');
    if (raw.toLowerCase().startsWith('json')) raw = raw.slice(4).trim();
  }
  try { return JSON.parse(raw); } catch (_) {
    const start = raw.indexOf('{');
    const end = raw.lastIndexOf('}');
    if (start >= 0 && end > start) return JSON.parse(raw.slice(start, end + 1));
    throw new StepError('Réponse du modèle illisible (JSON attendu).');
  }
}

// --- Defaults (ported from explainer-videos-src/app_defaults.py) ---
const VALID_CHAPTER_COUNTS = [10, 12, 14, 15, 16, 18, 20, 21, 24, 25, 27, 28, 30, 32, 35, 36, 40];

const OPENROUTER_MODELS = [
  'anthropic/claude-opus-4.6',
  'openai/gpt-5.4-mini',
  'anthropic/claude-sonnet-4.5',
  'deepseek/deepseek-v4-flash',
  'moonshotai/kimi-k2.6',
  'google/gemini-3.1-pro-preview',
  'google/gemini-3.1-flash-lite',
];

const IMAGE_MODELS = [
  {label: 'Grok Imagine', value: 'xai/grok-imagine-image'},
  {label: 'Seedream 4.5', value: 'bytedance/seedream-4.5'},
  {label: 'Z Image Turbo', value: 'prunaai/z-image-turbo'},
  {label: 'GPT Image 2 Medium', value: 'openai/gpt-image-2'},
  {label: 'Wan 2.7 Image Pro', value: 'wan-video/wan-2.7-image-pro'},
];

const EDIT_MODELS = [
  {label: 'Grok Imagine', value: 'xai/grok-imagine-image'},
  {label: 'Seedream 4.5', value: 'bytedance/seedream-4.5'},
  {label: 'Nano Banana', value: 'google/nano-banana'},
  {label: 'GPT Image 2 Medium', value: 'openai/gpt-image-2'},
  {label: 'Wan 2.7 Image Pro', value: 'wan-video/wan-2.7-image-pro'},
];

const ELEVENLABS_TTS_MODELS = ['eleven_multilingual_v2', 'eleven_turbo_v2_5', 'eleven_flash_v2_5', 'eleven_v3'];

const DEFAULT_SETTINGS = {
  chat_model: 'openai/gpt-5.4-mini',
  outline_model: 'anthropic/claude-sonnet-4.5',
  script_model: 'anthropic/claude-sonnet-4.5',
  visual_planning_model: 'openai/gpt-5.4-mini',
  icon_image_model: 'prunaai/z-image-turbo',
  scene_image_model: 'prunaai/z-image-turbo',
  edit_image_model: 'google/nano-banana',
  elevenlabs_voice_id: '',
  elevenlabs_model_id: 'eleven_multilingual_v2',
  voice_stability: 0.75,
  voice_similarity: 0.5,
  voice_style: 0,
  voice_speed: 1,
  voice_speaker_boost: true,
  words_per_minute: 150,
  image_retry_count: 5,
  worker_count: 2,
  segment_parallelism: 4,
  transcription_enabled: true,
  frame_style: 'round',
  background_color: '#FFFFFF',
  border_color: '#000000',
  font_color: '#000000',
  border_width: 6,
  default_video_length: 20,
  default_fps: 24,
  default_width: 1920,
  default_height: 1080,
};

// --- Prompt templates (verbatim from explainer-videos-src/app_defaults.py PROMPT_DEFAULTS) ---
const PROMPT_DEFAULTS = {
  chapter_outline: {
    name: 'Chapter outline',
    body: `You are a chapter outline generator for educational explainer videos. Given a video title, you produce a structured list of chapters that will be displayed as a visual grid.

## YOUR TASK
Analyze the input title and generate an appropriate number of chapters, each with a short punchy name and a brief explanation of what the chapter covers. The chapters are the actual table of contents for the video.

## CHAPTER COUNT RULES
- The number of chapters must be based on how broad or specific the topic is.
- Broad "every X" or "worst X in history" topics -> more chapters.
- Specific topics with a naturally limited set -> fewer chapters.
- CRITICAL: The total chapter count MUST form a clean rectangular grid. Only use these valid counts: {{valid_chapter_counts}}.
{{requested_chapter_count_instruction}}

## CHAPTER NAMING STYLE
- Names must be SHORT, ideally 1-4 words, max 5 words.
- Be direct, concrete, and specific to the subject.
- No numbering in the chapter name itself.
- No generic filler chapters like "Introduction", "Conclusion", "Honorable Mentions", or "Summary".
- Never use placeholder names like "Part 1", "Chapter 1", "Key Idea 1", or "Item 1".
- For "Every major X explained simply" topics, each chapter name must be one real X. For example, "Every major human organ explained simply" should produce chapter names like Brain, Heart, Lungs, Liver, Kidneys, Stomach, Skin, Pancreas, and similar concrete organs.

## CHAPTER TOPIC EXPLANATION
- For each chapter, include a 1-3 sentence explanation of what this chapter covers.
- This explanation should be clear and factual so that a separate writing agent can understand exactly what to write about.

## OUTPUT FORMAT
Return a valid JSON object with a single key "chapters", an array of:
- "chapter_number": integer starting at 1
- "chapter": string
- "chapter_topic": string

IMPORTANT: Output ONLY the JSON object. No markdown, no backticks, no extra text.

Title: {{title}}`,
  },
  chapter_script: {
    name: 'Chapter script',
    body: `You are a scriptwriter for educational narration-style content. Your job is to write individual chapters/entries on a given topic in a specific voice and style.

## Writing Style
- Tone: Casual, conversational, and matter-of-fact.
- Vocabulary: Use simple, everyday language. Avoid jargon and formal phrasing.
- Sentence structure: Keep sentences short to medium length.
- Descriptive approach: Be vivid and specific. Walk through what actually happens step by step.
- Perspective: Write as a narrator speaking directly to the audience.
- Emotional register: Stay mostly neutral and informative.
- Historical context: Include brief context when useful, but do not turn it into a history lecture.
- Flow: Write in continuous prose. Do not use bullet points, numbered lists, headers, or formatting.
- Structure: Start by saying what the subject is. Then explain the main job, process, or cause. Then explain the visible effect. End with why it still matters.

## Output Rules
- Output ONLY the chapter text.
- The first words must be the exact chapter title followed by a period. Example: "{{chapter}}. ..."
- Do not include phrases like "Chapter 1:" or "Part 1:".
- Match the requested output length as closely as possible.

Write the following chapter.

Chapter number: {{chapter_number}}
Chapter title: {{chapter}}
Topic: {{chapter_topic}}

TARGET LENGTH: approximately {{word_target}} words. Do NOT exceed {{max_words}} words. Do NOT go under {{min_words}} words.

Output ONLY the chapter text, nothing else.`,
  },
  icon_prompts: {
    name: 'Icon prompts',
    body: `You are an expert image prompt engineer specializing in simple, bold, pictogram-style icons used in YouTube video thumbnails.

YOUR TASK
You receive a list of chapters. For EACH chapter, generate ONE image prompt that will produce a flat pictogram icon on a solid colored background.

ICON STYLE REFERENCE
The entire background is ONE solid flat color filling the image edge to edge. No white background, no drawn circle, no outline, no border, no ring.
Centered in the image: a single black silhouette pictogram representing the chapter topic.
The pictogram is pure flat black, completely flat 2D vector art like a traffic sign. It may be a simplified object, organ, tool, symbol, or human figure only when that is the most specific visual for the chapter.
No 3D, lighting, shadows, texture, photography, text, letters, or numbers.
Square format, 1:1 aspect ratio.

PROMPT STRUCTURE
Each prompt MUST follow this exact template:
"A square flat vector image where the entire background is solid [COLOR], filling the image edge to edge with no border or outline. Centered on the [COLOR] background, a black silhouette pictogram of [SIMPLE VISUAL DESCRIPTION]. The pictogram is simplified to bold geometric shapes and must clearly match the chapter topic. Completely flat 2D vector art like a traffic sign. No outlines around anything, no borders, no rings, no circles drawn, no gradients, no shadows, no 3D, no lighting, no photographic elements, no text. The silhouette occupies about 55% of the image. 1:1 aspect ratio."

VISUAL DESCRIPTION RULES
- The visual description must be concrete and chapter-specific.
- Do not default to a generic person pictogram.
- For human organs, draw the actual organ shape or a simple medical pictogram of that organ.

COLOR PALETTE
Bright orange, lime green, cyan, red, golden yellow, magenta, royal blue, purple, bright teal, deep orange

OUTPUT FORMAT
Return a JSON object with an "image_prompts" array. Each element must have:
- chapter_number
- chapter
- circle_color
- icon_description
- image_prompt

Return ONLY valid JSON. No commentary, no markdown, no backticks.

Here are the {{total_chapters}} chapters:
{{chapters_json}}`,
  },
  sensitive_rewrite: {
    name: 'Sensitive prompt rewrite',
    body: `The input or output was flagged as sensitive. Please rewrite the prompt so it can pass image generation safety filters while preserving the same simple visual meaning.

Prompt: {{prompt}}

chapter_number: {{chapter_number}}

Return ONLY the rewritten prompt.`,
  },
  segment_planner: {
    name: 'Segment planner',
    body: `You are a video segment planner for a YouTube explainer channel.
Your job is to analyze a chapter script and its SRT transcription, then produce a structured JSON segment plan that will be used to render a video chunk.

## CRITICAL - PROMPT & SEARCH QUALITY

### AI Image Prompts (ai_image and composite)
Before writing any image prompt, you MUST first reason about what the subject actually is.
Many historical, scientific, or cultural terms have names that sound like something completely different from what they actually are.
- "Crocodile Shears" = a medieval pincers-shaped metal tool heated and used to mutilate fingers, NOT a crocodile holding scissors.
- "Iron Maiden" = a hinged metal cabinet with interior spikes, NOT a woman made of iron.
- "The Rack" = a wooden frame with rollers that stretched the body, NOT a shelf or storage rack.

ALWAYS describe the object/scene based on what it ACTUALLY IS according to the script context - never interpret the name literally.

Your image prompts must:
1. Open with the actual visual subject clearly described in plain terms.
2. Include the historical period, materials, and setting from the script.
3. End with style/lighting/mood keywords.
4. NEVER use the colloquial name as the main visual descriptor - always describe what the thing literally looks like.

### B-Roll Search Queries
B-roll search queries are fed directly into a stock image / web image search engine.
They must be 3-6 words, SPECIFIC, and UNIQUE per segment.

Rules:
- Write search queries the way a human would type into Google Images.
- NEVER stuff multiple abstract concepts into one query.
- NEVER use the same query concept twice across segments in the same chapter.
- Each b_roll query must target a DIFFERENT specific visual subject mentioned in the script for that segment's timeframe.
- Include the specific name of the device/place/event + a concrete visual descriptor.
- If the segment discusses an effect on the body, search for a medical or anatomical term, not the same method again.

## SEGMENT RULES
- Segment 1 is ALWAYS type "intro_animation" with duration_sec 0 and srt_start_line 1.
- Occasionally, if a visual idea builds on the previous image, use type "composite" instead of "ai_image". The reference_filename must be the previous segment's image_filename.
- image_filename is always sequential: image_1, image_2, image_3, etc.
- duration_sec for each segment should be derived from the SRT by grouping lines logically so each segment covers a natural phrase or sentence.
- All durations combined, including the intro, must equal the total audio duration.
- b_roll segments still get an image_filename; the scraped image will be saved there.
- Segments must be 3-7 seconds long each whenever possible.
- Keep a balanced natural mix between ai_image, b_roll, and composite.
- Every visual prompt or search query must use concrete nouns from the chapter title and script. Never use generic placeholder phrasing like "Part 1", "key idea", or "explained simply with concrete details".

## SEGMENT TIMING RULES
- Target 3-7 seconds per segment. No segment should exceed 7 seconds.
- The intro animation segment starts at SRT line 1.
- For every other segment, specify which SRT line it starts at using "srt_start_line".
- If grouping SRT subtitles would result in a segment longer than 7 seconds, split it into multiple segments. When splitting within a single SRT line, use the SAME srt_start_line for both segments; the code will divide the duration evenly.
- You do NOT need to calculate durations. Leave duration_sec as 0. A downstream process will compute exact durations from SRT timestamps automatically.
- Focus your effort on creative decisions: segment grouping, types, prompts, and search queries.

## OUTPUT SCHEMA
{
  "chunk_id": number,
  "total_segments": number,
  "total_images": number,
  "segments": [
    {
      "segment_id": number,
      "type": "intro_animation" | "ai_image" | "b_roll" | "composite",
      "duration_sec": 0,
      "srt_start_line": number,
      "image_filename": "image_N",
      "chapter_title": "Title of Chapter",
      "prompt": "for ai_image and composite",
      "reference_filename": "image_N for composite",
      "search_query": "for b_roll"
    }
  ]
}

Chapter Number: {{chapter_number}}
Chapter Title: {{chapter}}
Chapter Topic: {{chapter_topic}}

Script:
{{script}}

SRT Transcription:
---
{{srt}}
---

Total Audio Duration: {{audio_duration}}

Output ONLY valid JSON, no explanation, no markdown fences.`,
  },
};

// --- Settings / prompts persistence (localStorage) ---
const SETTINGS_KEY = 'explainer.settings.v1';
const PROMPTS_KEY = 'explainer.prompts.v1';

function loadSettings() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}'); } catch (_) {}
  return Object.assign({}, DEFAULT_SETTINGS, saved);
}
function saveSettings(settings) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}
function loadPrompts() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(PROMPTS_KEY) || '{}'); } catch (_) {}
  const prompts = {};
  for (const key of Object.keys(PROMPT_DEFAULTS)) {
    prompts[key] = {name: PROMPT_DEFAULTS[key].name, body: (saved[key] && saved[key].body) || PROMPT_DEFAULTS[key].body};
  }
  return prompts;
}
function savePrompts(prompts) {
  localStorage.setItem(PROMPTS_KEY, JSON.stringify(prompts));
}
function getPrompt(key) {
  const prompts = loadPrompts();
  if (!prompts[key]) throw new StepError(`Prompt inconnu: ${key}`);
  return prompts[key].body;
}

// --- IndexedDB: projects, assets (blobs), events ---
const DB_NAME = 'explainer-tools';
const DB_VERSION = 1;
let _dbPromise = null;

function openDb() {
  if (_dbPromise) return _dbPromise;
  _dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('projects')) db.createObjectStore('projects', {keyPath: 'id'});
      if (!db.objectStoreNames.contains('assets')) {
        const assets = db.createObjectStore('assets', {keyPath: 'key'});
        assets.createIndex('project_id', 'project_id');
      }
      if (!db.objectStoreNames.contains('events')) {
        const events = db.createObjectStore('events', {keyPath: 'id', autoIncrement: true});
        events.createIndex('project_id', 'project_id');
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return _dbPromise;
}

function idbRequest(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function dbPut(store, value) {
  const db = await openDb();
  return idbRequest(db.transaction(store, 'readwrite').objectStore(store).put(value));
}
async function dbGet(store, key) {
  const db = await openDb();
  return idbRequest(db.transaction(store, 'readonly').objectStore(store).get(key));
}
async function dbGetAll(store) {
  const db = await openDb();
  return idbRequest(db.transaction(store, 'readonly').objectStore(store).getAll());
}
async function dbDelete(store, key) {
  const db = await openDb();
  return idbRequest(db.transaction(store, 'readwrite').objectStore(store).delete(key));
}
async function dbGetAllByIndex(store, indexName, value) {
  const db = await openDb();
  return idbRequest(db.transaction(store, 'readonly').objectStore(store).index(indexName).getAll(value));
}
async function dbDeleteByIndex(store, indexName, value) {
  const items = await dbGetAllByIndex(store, indexName, value);
  for (const item of items) await dbDelete(store, store === 'assets' ? item.key : item.id);
}

// Projects
async function listProjects() {
  const projects = await dbGetAll('projects');
  return projects.sort((a, b) => (a.position ?? 0) - (b.position ?? 0) || String(a.created_at).localeCompare(String(b.created_at)));
}
async function getProject(id) {
  const project = await dbGet('projects', id);
  if (!project) throw new StepError('Projet introuvable.');
  return project;
}
async function saveProject(project) {
  project.updated_at = new Date().toISOString();
  await dbPut('projects', project);
  return project;
}
async function deleteProjectAndData(id) {
  await dbDeleteByIndex('assets', 'project_id', id);
  await dbDeleteByIndex('events', 'project_id', id);
  await dbDelete('projects', id);
}

// Assets: {key, project_id, mime, blob?, remote_url?, created_at}
function assetKey(projectId, name) { return `${projectId}/${name}`; }
async function saveAsset(projectId, name, {blob = null, mime = '', remoteUrl = ''} = {}) {
  const record = {key: assetKey(projectId, name), project_id: projectId, mime, blob, remote_url: remoteUrl, created_at: new Date().toISOString()};
  await dbPut('assets', record);
  return record;
}
async function getAsset(projectId, name) { return dbGet('assets', assetKey(projectId, name)); }
function assetObjectUrl(asset) {
  if (!asset) return '';
  if (asset.blob) return URL.createObjectURL(asset.blob);
  return asset.remote_url || '';
}

// Events (local activity log)
async function logEvent(projectId, level, event, message) {
  try {
    await dbPut('events', {project_id: projectId, level, event, message, created_at: new Date().toISOString()});
  } catch (_) {}
}
async function listEvents(projectId = null, limit = 400) {
  const events = projectId ? await dbGetAllByIndex('events', 'project_id', projectId) : await dbGetAll('events');
  return events.sort((a, b) => b.id - a.id).slice(0, limit);
}
async function clearEvents() {
  const db = await openDb();
  return idbRequest(db.transaction('events', 'readwrite').objectStore('events').clear());
}

// ============================================================
// Provider clients
// ============================================================

// OpenRouter — direct browser fetch.
// Port of providers.py:OpenRouterClient.complete (explainer-videos-src/providers.py:73-97).
async function openrouterComplete(model, prompt, {jsonMode = false} = {}) {
  if (!KEYS.openrouter) throw new StepError(MSG_NO_OPENROUTER);
  const payload = {model, messages: [{role: 'user', content: prompt}], temperature: 0.7};
  if (jsonMode) payload.response_format = {type: 'json_object'};
  const response = await fetch(`${LLM_BASE}/chat/completions`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${KEYS.openrouter}`,
      'Content-Type': 'application/json',
      'X-Title': 'Explainer Videos App',
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new StepError(`OpenRouter a échoué: ${response.status} ${(await response.text()).slice(0, 300)}`);
  const data = await response.json();
  return data.choices[0].message.content;
}

// ElevenLabs TTS — direct browser fetch, mp3_44100_128, retry on 429.
// Port of providers.py:VoiceoverClient._synthesize_elevenlabs (explainer-videos-src/providers.py:675-706).
async function elevenlabsTts(settings, text) {
  if (!KEYS.elevenlabs) throw new StepError(MSG_NO_ELEVENLABS);
  if (!settings.elevenlabs_voice_id) throw new StepError(MSG_NO_VOICE_ID);
  const payload = {
    text,
    model_id: settings.elevenlabs_model_id || 'eleven_multilingual_v2',
    voice_settings: {
      stability: Number(settings.voice_stability),
      similarity_boost: Number(settings.voice_similarity),
      style: Number(settings.voice_style),
      speed: Number(settings.voice_speed),
      use_speaker_boost: Boolean(settings.voice_speaker_boost),
    },
  };
  const url = `https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(settings.elevenlabs_voice_id)}?output_format=mp3_44100_128`;
  for (let attempt = 0; attempt < 6; attempt++) {
    const response = await fetch(url, {
      method: 'POST',
      headers: {'xi-api-key': KEYS.elevenlabs, 'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    if (response.status === 429) { await sleep(Math.min(30000, 2000 * (2 ** attempt))); continue; }
    if (!response.ok) throw new StepError(`ElevenLabs TTS a échoué: ${response.status} ${(await response.text()).slice(0, 300)}`);
    return response.blob();
  }
  throw new StepError('ElevenLabs TTS toujours limité (429) après 6 tentatives.');
}

// --- Replicate via the render-API relay ---
function relayUrl(path) { return `${RENDER_API}/relay/replicate/${String(path).replace(/^\/+/, '')}`; }
function replicateHeaders() {
  return {...renderTokenHeader(), 'X-Provider-Key': KEYS.replicate, 'Content-Type': 'application/json', 'Prefer': 'wait'};
}
function requireReplicateRelay() {
  if (!RENDER_READY) throw new StepError(MSG_NO_RENDER_API);
  if (!KEYS.replicate) throw new StepError(MSG_NO_REPLICATE);
}

// Port of providers.py:_extract_replicate_output_url (explainer-videos-src/providers.py:312-328).
function extractReplicateOutputUrl(data) {
  const output = data.output;
  if (typeof output === 'string') return output;
  if (Array.isArray(output) && output.length) {
    const first = output[0];
    if (typeof first === 'string') return first;
    if (first && typeof first === 'object') {
      for (const key of ['url', 'image', 'audio', 'src']) if (first[key]) return first[key];
    }
  }
  if (output && typeof output === 'object') {
    for (const key of ['url', 'image', 'audio', 'src']) if (output[key]) return output[key];
  }
  throw new StepError(`Impossible d'extraire l'URL de sortie Replicate: ${JSON.stringify(data).slice(0, 300)}`);
}

// Port of providers.py:_wait_for_replicate_output (explainer-videos-src/providers.py:331-355),
// polling through the relay instead of api.replicate.com directly.
async function waitForReplicateOutput(data) {
  let status = String(data.status || '').toLowerCase();
  for (let i = 0; i < 120; i++) {
    if (status === 'succeeded' || data.output) return extractReplicateOutputUrl(data);
    if (status === 'failed' || status === 'canceled') {
      throw new StepError(`Prédiction Replicate ${status}: ${JSON.stringify(data.error || data.logs || data).slice(0, 300)}`);
    }
    if (!data.id) break;
    await sleep(2000);
    const response = await fetch(relayUrl(`v1/predictions/${data.id}`), {headers: {...renderTokenHeader(), 'X-Provider-Key': KEYS.replicate}});
    if (!response.ok) throw new StepError(`Sondage Replicate a échoué: ${response.status}`);
    data = await response.json();
    status = String(data.status || '').toLowerCase();
  }
  throw new StepError(`La prédiction Replicate n'a pas produit de sortie: ${JSON.stringify(data).slice(0, 300)}`);
}

// Port of providers.py:_replicate_input_for_model (explainer-videos-src/providers.py:245-309).
function replicateInputForModel(model, prompt, width, height, referenceUrl = null) {
  if (model === 'xai/grok-imagine-image') {
    const data = {prompt, aspect_ratio: width >= height ? '16:9' : '1:1'};
    if (referenceUrl) data.image = referenceUrl;
    return data;
  }
  if (model === 'bytedance/seedream-4.5') {
    return {
      size: '4K',
      prompt,
      max_images: 1,
      image_input: referenceUrl ? [referenceUrl] : [],
      aspect_ratio: width > height ? '16:9' : '1:1',
      sequential_image_generation: 'disabled',
    };
  }
  if (model === 'openai/gpt-image-2') {
    let aspect;
    if (width === height) aspect = '1:1';
    else if (width > height) aspect = '2048x1152';
    else aspect = '2160x3840';
    return {
      prompt,
      quality: 'auto',
      background: 'auto',
      moderation: 'auto',
      aspect_ratio: aspect,
      input_images: referenceUrl ? [referenceUrl] : [],
      output_format: 'webp',
      number_of_images: 1,
      output_compression: 90,
    };
  }
  if (model === 'wan-video/wan-2.7-image-pro') {
    return {
      seed: 3333,
      size: width >= height ? '2048*1152' : '1024*1024',
      images: referenceUrl ? [referenceUrl] : [],
      prompt,
      num_outputs: 1,
      thinking_mode: true,
      image_set_mode: false,
    };
  }
  if (model === 'google/nano-banana') {
    return {
      prompt,
      image_input: referenceUrl ? [referenceUrl] : [],
      aspect_ratio: width > height ? '16:9' : '1:1',
      output_format: 'jpg',
    };
  }
  return {
    width,
    height,
    prompt,
    go_fast: false,
    output_format: 'jpg',
    guidance_scale: 0,
    output_quality: 80,
    num_inference_steps: 8,
  };
}

const TRANSIENT_REPLICATE_MARKERS = ['unavailable', 'high demand', 'try again', 'rate limit', 'timed out', 'timeout', 'overloaded', ' 429', ' 502', ' 503', ' 504'];
function isTransientReplicateError(message) {
  const msg = String(message).toLowerCase();
  return TRANSIENT_REPLICATE_MARKERS.some(marker => msg.includes(marker));
}

// Image generation with transient retries (5s, 10s, 20s).
// Port of providers.py:ReplicateClient.generate_image (explainer-videos-src/providers.py:386-440).
async function replicateGenerateImage(model, prompt, {width, height, referenceUrl = null} = {}) {
  requireReplicateRelay();
  let lastError = null;
  for (let attempt = 0; attempt < 4; attempt++) {
    if (attempt) await sleep(5000 * (2 ** (attempt - 1)));
    try {
      const response = await fetch(relayUrl(`v1/models/${model}/predictions`), {
        method: 'POST',
        headers: replicateHeaders(),
        body: JSON.stringify({input: replicateInputForModel(model, prompt, width, height, referenceUrl)}),
      });
      if (!response.ok) throw new StepError(`Replicate a échoué: ${response.status} ${(await response.text()).slice(0, 300)}`);
      return await waitForReplicateOutput(await response.json());
    } catch (error) {
      if (error instanceof StepError && !isTransientReplicateError(error.message)) throw error;
      lastError = error;
    }
  }
  throw lastError || new StepError('Génération d\'image Replicate échouée.');
}

// Whisper word-level transcription via the relay.
// Port of providers.py:ReplicateTranscriptionClient (explainer-videos-src/providers.py:443-488).
const WHISPER_VERSION = 'vaibhavs10/incredibly-fast-whisper:3ab86df6c8f54c11309d4d1f930ac292bad43ace52d10c80d87eb258b3c9f79c';
async function replicateTranscribeWords(audioDataUrl) {
  requireReplicateRelay();
  const payload = {
    version: WHISPER_VERSION,
    input: {task: 'transcribe', audio: audioDataUrl, language: 'None', timestamp: 'word', batch_size: 64, diarise_audio: false},
  };
  const response = await fetch(relayUrl('v1/predictions'), {method: 'POST', headers: replicateHeaders(), body: JSON.stringify(payload)});
  if (!response.ok) throw new StepError(`Transcription Replicate a échoué: ${response.status}`);
  let prediction = await response.json();
  for (let i = 0; i < 180; i++) {
    const status = prediction.status;
    if (status === 'succeeded') return prediction.output;
    if (status === 'failed' || status === 'canceled') throw new StepError(`Transcription Replicate ${status}: ${JSON.stringify(prediction.error || '').slice(0, 300)}`);
    await sleep(2000);
    const poll = await fetch(relayUrl(`v1/predictions/${prediction.id}`), {headers: {...renderTokenHeader(), 'X-Provider-Key': KEYS.replicate}});
    if (!poll.ok) throw new StepError(`Sondage transcription a échoué: ${poll.status}`);
    prediction = await poll.json();
  }
  throw new StepError("La transcription Replicate n'a pas terminé à temps.");
}

// ============================================================
// Render API: uploads, render job, polling
// ============================================================

async function uploadBlob(blob, filename) {
  if (!RENDER_READY) throw new StepError(MSG_NO_RENDER_API);
  const form = new FormData();
  form.append('file', blob, filename);
  const response = await fetch(`${RENDER_API}/uploads`, {method: 'POST', headers: renderTokenHeader(), body: form});
  if (!response.ok) throw new StepError(`Upload échoué: ${response.status} ${(await response.text()).slice(0, 300)}`);
  const data = await response.json();
  if (!data.upload_id) throw new StepError("L'upload n'a pas renvoyé d'upload_id.");
  return data.upload_id;
}

async function startRenderJob(manifest) {
  if (!RENDER_READY) throw new StepError(MSG_NO_RENDER_API);
  const response = await fetch(`${RENDER_API}/render/explainer`, {
    method: 'POST',
    headers: {...renderTokenHeader(), 'Content-Type': 'application/json'},
    body: JSON.stringify(manifest),
  });
  if (!response.ok) throw new StepError(`Lancement du rendu échoué: ${response.status} ${(await response.text()).slice(0, 300)}`);
  const data = await response.json();
  if (!data.job_id) throw new StepError("Le serveur n'a pas renvoyé de job_id.");
  return data.job_id;
}

async function getJobStatus(jobId) {
  const response = await fetch(`${RENDER_API}/jobs/${encodeURIComponent(jobId)}`, {headers: renderTokenHeader()});
  if (!response.ok) throw new StepError(`Statut du job indisponible: ${response.status}`);
  return response.json();
}

function absoluteRenderUrl(path) {
  const value = String(path || '');
  if (!value) return '';
  if (/^https?:\/\//i.test(value)) return value;
  return RENDER_API + (value.startsWith('/') ? value : '/' + value);
}

// ============================================================
// Audio / file utilities
// ============================================================

async function blobAudioDuration(blob) {
  const arrayBuffer = await blob.arrayBuffer();
  const Ctx = window.AudioContext || window.webkitAudioContext;
  const ctx = new Ctx();
  try {
    const decoded = await ctx.decodeAudioData(arrayBuffer);
    return decoded.duration;
  } finally {
    ctx.close();
  }
}

// Port of providers.py:file_to_data_url (explainer-videos-src/providers.py:1055-1058).
function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

// Download a provider output URL into a blob; returns null when CORS blocks it
// (the manifest then carries the http(s) URL and the server downloads it).
async function tryFetchBlob(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    return await response.blob();
  } catch (_) {
    return null;
  }
}

// ============================================================
// SRT helpers (ported from explainer-videos-src/providers.py)
// ============================================================

// providers.py:_format_srt_time (1046-1052)
function formatSrtTime(seconds) {
  const totalMs = Math.max(0, Math.round(seconds * 1000));
  const whole = Math.floor(totalMs / 1000);
  const ms = totalMs % 1000;
  const h = Math.floor(whole / 3600);
  const m = Math.floor((whole % 3600) / 60);
  const s = whole % 60;
  const pad = (v, n = 2) => String(v).padStart(n, '0');
  return `${pad(h)}:${pad(m)}:${pad(s)},${pad(ms, 3)}`;
}

// providers.py:build_srt_from_text (941-952) — fallback when transcription is unavailable.
function buildSrtFromText(text, duration) {
  let sentences = String(text || '').replace(/\n/g, ' ').split('.').map(part => part.trim()).filter(Boolean);
  if (!sentences.length) sentences = [String(text || '').slice(0, 120) || 'Silent placeholder'];
  const lineDuration = Math.max(1.5, duration / Math.max(1, sentences.length));
  const lines = [];
  sentences.forEach((sentence, i) => {
    const idx = i + 1;
    const start = i * lineDuration;
    const end = Math.min(duration, idx * lineDuration);
    lines.push(`${idx}\n${formatSrtTime(start)} --> ${formatSrtTime(end)}\n${sentence.trim()}.\n`);
  });
  return lines.join('\n');
}

// providers.py:_extract_word_timestamp_chunks (1003-1024)
function extractWordTimestampChunks(output) {
  let chunks = output && typeof output === 'object' && !Array.isArray(output) ? output.chunks : null;
  if (chunks == null && Array.isArray(output)) chunks = output;
  const words = [];
  if (!Array.isArray(chunks)) return words;
  for (const chunk of chunks) {
    if (!chunk || typeof chunk !== 'object') continue;
    const ts = chunk.timestamp;
    if (!Array.isArray(ts) || ts.length !== 2) continue;
    const start = Number(ts[0]);
    const end = Number(ts[1]);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) continue;
    words.push({text: String(chunk.text || ''), timestamp: [start, end]});
  }
  return words;
}

// providers.py:_actual_speech_start (1027-1035)
function actualSpeechStart(word) {
  const start = word.timestamp[0];
  const end = word.timestamp[1];
  const measured = Math.max(0, end - start);
  const charCount = (String(word.text || '').trim().match(/[a-zA-Z0-9']/g) || []).length || 1;
  const expected = Math.max(0.2, charCount * 0.08);
  if (measured > expected + 0.5) return Math.round((end - expected) * 1000) / 1000;
  return start;
}

// providers.py:build_srt_from_word_timestamps (955-1000)
function buildSrtFromWordTimestamps(output, duration) {
  const words = extractWordTimestampChunks(output);
  if (!words.length) throw new StepError('La transcription Replicate n\'a pas renvoyé de timestamps par mot.');
  const minSegmentDuration = 2.5;
  const segments = [];
  let current = [];
  let segmentStart = words[0].timestamp[0];
  const isSentenceEnd = text => Boolean(text) && '.!?'.includes(text[text.length - 1]);
  const isClauseEnd = text => Boolean(text) && ',;:'.includes(text[text.length - 1]);
  for (const word of words) {
    current.push(word);
    const text = String(word.text || '').trim();
    const end = word.timestamp[1];
    const currentDuration = end - segmentStart;
    if (isSentenceEnd(text) || (isClauseEnd(text) && currentDuration >= minSegmentDuration)) {
      segments.push(current);
      current = [];
      segmentStart = end;
    }
  }
  if (current.length) segments.push(current);

  const totalDuration = Math.max(0, Number(duration) || 0);
  const lines = [];
  segments.forEach((segment, i) => {
    const idx = i + 1;
    let start = actualSpeechStart(segment[0]);
    let end;
    if (idx < segments.length) {
      end = actualSpeechStart(segments[idx][0]);
    } else {
      end = segment[segment.length - 1].timestamp[1];
      if (totalDuration > 0) end = Math.max(end, totalDuration);
    }
    if (totalDuration > 0) { start = Math.min(start, totalDuration); end = Math.min(end, totalDuration); }
    if (end <= start) end = Math.min(totalDuration || start + 0.25, start + 0.25);
    const text = segment.map(word => String(word.text || '')).join('').trim();
    if (!text) return;
    lines.push(`${idx}\n${formatSrtTime(start)} --> ${formatSrtTime(end)}\n${text}`);
  });
  if (!lines.length) throw new StepError('La transcription n\'a produit aucune ligne SRT utilisable.');
  return lines.join('\n\n') + '\n';
}

// ============================================================
// Render API warning banner (informative — direct steps still work)
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  if (RENDER_READY) return;
  const banner = document.createElement('div');
  banner.className = 'api-banner';
  banner.textContent = MSG_NO_RENDER_API + ' (les étapes script et voix off fonctionnent quand même)';
  document.body.prepend(banner);
});
