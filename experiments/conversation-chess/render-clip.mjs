#!/usr/bin/env node
// Offline compositor for a supplied local source and explicitly reviewed source timestamps.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const require = createRequire(path.join(root, 'frontend/package.json'));
const { chromium } = require('playwright');
const args = process.argv.slice(2);
function option(name, fallback = '') {
  const i = args.indexOf(name);
  if (i < 0) return fallback;
  if (!args[i + 1] || args[i + 1].startsWith('--')) throw new Error(`Missing value after ${name}`);
  return args[i + 1];
}
function run(bin, cmd, capture = false) {
  const result = spawnSync(bin, cmd, { stdio: capture ? 'pipe' : 'inherit', encoding: 'utf8', maxBuffer: 5_000_000 });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${bin} failed (${result.status}): ${capture ? result.stderr.slice(-1200) : 'see output'}`);
  return result.stdout;
}
const sourceArg = option('--source');
const timelineArg = option('--timeline');
if (!sourceArg || !timelineArg) throw new Error('Use --source /local/video.mp4 --timeline /local/review.json');
if (/^[a-z]+:\/\//i.test(sourceArg)) throw new Error('Only an existing local source file is accepted.');
const source = path.resolve(sourceArg), timelinePath = path.resolve(timelineArg);
if (!(await fs.stat(source)).isFile()) throw new Error('Source must be a regular local file.');
const output = path.resolve(option('--out', '/tmp/edgerunners-conversation-chess-clip'));
await fs.mkdir(output, { recursive: true });
const refreshIntro = args.includes('--refresh-intro');
const refreshProjectIntro = args.includes('--refresh-project-intro');
const prepareProject = args.includes('--prepare-project') || refreshProjectIntro;
const validateOnly = args.includes('--validate-only');
if (prepareProject && refreshIntro) throw new Error('--prepare-project and --refresh-intro cannot be combined.');
const graphicsFps = 30;
const previousRender = refreshIntro ? JSON.parse(await fs.readFile(path.join(output, 'render-report.json'), 'utf8')) : null;
const spec = JSON.parse(await fs.readFile(timelinePath, 'utf8'));
const outroSeconds = spec.outro_seconds ?? 0;
if (!Number.isFinite(outroSeconds) || (outroSeconds !== 0 && (outroSeconds < 6 || outroSeconds > 20))) throw new Error('outro_seconds must be 0 or 6–20 seconds.');
if (!Number.isInteger(outroSeconds * 30)) throw new Error('outro_seconds must align to a 30fps frame.');
if (spec.outro_subtitle != null && (typeof spec.outro_subtitle !== 'string' || spec.outro_subtitle.length > 70)) throw new Error('Supply a short outro_subtitle.');
if ((outroSeconds || spec.music) && !prepareProject && !validateOnly) throw new Error('Music and recap use the native editor workflow: add --prepare-project.');
if ((outroSeconds || spec.music) && refreshProjectIntro) throw new Error('Build a complete project when adding music or a recap.');
const ratingSchema = JSON.parse(await fs.readFile(path.join(here, 'ratings.json'), 'utf8'));
const meta = JSON.parse(run('/usr/bin/ffprobe', ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', source], true));
const sourceDuration = Number(meta.format.duration);
const hasAudio = meta.streams.some(s => s.codec_type === 'audio');
const video = meta.streams.find(s => s.codec_type === 'video');
if (!video || !Number.isFinite(sourceDuration)) throw new Error('Source has no usable video/duration.');
const archiveSource = args.includes('--allow-legacy-opening');
const minimumSourceHeight = spec.source_quality?.quality_target ?? (spec.demo === true || archiveSource ? 720 : 1080);
if (![720, 1080, 1440, 2160].includes(minimumSourceHeight)) throw new Error('Source quality target must be 720, 1080, 1440 or 2160.');
if (spec.demo !== true && !archiveSource && minimumSourceHeight < 1080) throw new Error('New real videos require at least a 1080p source target.');
const sourceQualityReviewed = spec.source_quality?.accepted_for_final === true;
const lowResPreview = video.height < minimumSourceHeight || spec.source_quality?.accepted_for_final === false
  || (spec.demo !== true && !archiveSource && !sourceQualityReviewed);
if (lowResPreview && !args.includes('--allow-low-res-preview') && !validateOnly) throw new Error(`Source quality is not accepted: ${video.width}×${video.height}, target at least ${minimumSourceHeight}p. Replace and visually review the original source, then set source_quality.accepted_for_final=true. --allow-low-res-preview is only for a clearly marked technical draft.`);
const outroLayoutReviewed = outroSeconds === 0 || spec.outro_layout_reviewed === true
  || (spec.outro_layout_reviewed == null && (spec.demo === true || archiveSource));
if (!outroLayoutReviewed && !validateOnly) throw new Error('This outro layout was rejected or has not been reviewed. Check the actual reference end card and update the layout before export.');
if (spec.schema !== 'conversation-chess-clip-v1') throw new Error('Unknown timeline schema.');
if (spec.intro_seconds !== ratingSchema.intro_seconds) throw new Error(`The complete legend intro is ${ratingSchema.intro_seconds} seconds.`);
const start = Number(spec.source_in), end = Number(spec.source_out);
if (![start, end].every(Number.isFinite) || start < 0 || end <= start || end > sourceDuration + .05) throw new Error('source_in/source_out must be inside the supplied source.');
const demo = spec.demo === true;
const analysisBackground = spec.analysis_background || 'replay';
if (!['replay','loop','freeze'].includes(analysisBackground)) throw new Error('analysis_background must be replay, loop or freeze.');
if (!hasAudio && !demo) throw new Error('Real dialogue footage must contain its original audio.');
if (!demo && spec.source_reviewed !== true) throw new Error('Real footage requires source_reviewed=true after review.');
const ratings = new Set(ratingSchema.categories.map(v => v.id));
const controls = new Set(['balanced', 'black', 'white', 'tony', 'ralph']);
const sides = { black: spec.black_label || 'Other speaker', white: spec.white_label || 'Tony' };
if (Object.values(sides).some(v => typeof v !== 'string' || !v.trim() || v.length > 32)) throw new Error('Supply short black_label/white_label names.');
// The opening dialogue may be ungraded: do not infer the opener from the first annotation.
// Old review files can be reproduced only with an explicit archive override; invalid
// opening evidence cannot use that override to evade the White-first rule.
const opening = spec.opening ?? null;
let legacyOpeningOverride = false;
if (opening) {
  if (typeof opening !== 'object' || Array.isArray(opening) || opening.reviewed !== true) throw new Error('opening requires reviewed=true after checking the first dialogue in the selected source.');
  if (opening.speaker !== 'white') throw new Error('White must open the conversation: assign the first speaker to White.');
  if (opening.label !== sides.white) throw new Error('The reviewed opening.label must match white_label.');
} else if (!demo) {
  if (!args.includes('--allow-legacy-opening')) throw new Error('Real footage requires opening:{speaker:"white",label:<white_label>,reviewed:true}. Review the opening dialogue, including ungraded lines. --allow-legacy-opening is only for reproducing an archived timeline.');
  legacyOpeningOverride = true;
  console.warn('ARCHIVE ONLY: opening dialogue has no reviewed White-first evidence.');
}
const isControl = c => (typeof c === 'number' && Number.isFinite(c) && c >= 0 && c <= 1) || controls.has(c);
const scoreValue = value => (typeof value === 'string' && /^[-+]?\d{1,2}(?:\.\d)?$/.test(value)) ? Number(value) : NaN;
const initialScoreText = spec.initial_score_text ?? (demo ? '0.0' : null);
if (!Number.isFinite(scoreValue(initialScoreText))) throw new Error('Supply reviewed initial_score_text, e.g.0.0; score is editorial, never engine output.');
let scoreText = initialScoreText;
let control = spec.initial_control ?? .5;
if (!isControl(control)) throw new Error('Unknown initial_control.');
const annotations = spec.annotations || [];
if (!Array.isArray(annotations)) throw new Error('annotations must be an array.');
let previous = start, reviewedControl = control, reviewedScore = scoreValue(initialScoreText);
const controlFraction = c => typeof c === 'number' ? c : ({ balanced: .5, black: .72, white: .28, tony: .72, ralph: .28 })[c];
for (const a of annotations) {
  if (!Number.isFinite(a.source_at) || a.source_at <= previous || a.source_at >= end) throw new Error('Annotations need strictly ordered SOURCE timestamps inside the selected clip.');
  if (a.hold_seconds < 3 || a.hold_seconds > 9 || !Number.isFinite(a.hold_seconds)) throw new Error('Each analysis hold must last 3–9 seconds.');
  if (!ratings.has(a.rating) || !isControl(a.control_after)) throw new Error('Unknown rating/control_after.');
  const rating = ratingSchema.categories.find(v => v.id === a.rating);
  if (!Number.isFinite(scoreValue(a.score_text))) throw new Error('Every annotation needs reviewed score_text in White-positive / Black-negative convention.');
  const score = scoreValue(a.score_text);
  if (rating.bar_effect === 'neutral' && score !== reviewedScore) throw new Error('Best/Great must leave the conversation score unchanged.');
  if (a.speaker) {
    const speakerScoreShift = (score - reviewedScore) * (a.speaker === 'white' ? 1 : -1);
    const gains = ['gain','small_gain'].includes(rating.bar_effect);
    if (rating.bar_effect !== 'neutral' && ((gains && speakerScoreShift < 0) || (!gains && speakerScoreShift > 0))) throw new Error('Conversation score contradicts the rating for this speaker.');
  }
  reviewedScore = score;
  if (rating.bar_effect === 'neutral' && Math.abs(controlFraction(a.control_after) - controlFraction(reviewedControl)) > 1e-7) throw new Error('Best/Great must leave the bar unchanged.');
  if (a.replay_seconds != null && (!Number.isFinite(a.replay_seconds) || a.replay_seconds < 2 || a.replay_seconds > 4)) throw new Error('replay_seconds must be 2–4 seconds.');
  if (a.speaker && !['black','white'].includes(a.speaker)) throw new Error('speaker must be black or white.');
  if (a.speaker && rating.bar_effect !== 'neutral') {
    const speakerDirection = a.speaker === 'black' ? 1 : -1;
    const shift = (controlFraction(a.control_after) - controlFraction(reviewedControl)) * speakerDirection;
    const gains = ['gain','small_gain'].includes(rating.bar_effect);
    if ((gains && shift < 0) || (!gains && shift > 0)) throw new Error('Bar change contradicts this rating for the named speaker.');
  }
  reviewedControl = a.control_after;
  if (typeof a.comment !== 'string' || !a.comment.trim() || a.comment.length > 260) throw new Error('Supply an editorial English explanation, at most 260 characters.');
  if (a.hold_seconds < a.comment.length / ratingSchema.typewriter_cps + ratingSchema.bubble_delay_seconds + ratingSchema.minimum_reading_seconds) throw new Error('Allow the typewriter to finish plus at least 2.5 seconds of reading.');
  if (!demo && a.reviewed !== true) throw new Error('Every real annotation requires reviewed=true; do not invent source timestamps.');
  previous = a.source_at;
}
if (outroSeconds && annotations.some(a => !a.speaker)) throw new Error('Every recap move requires its reviewed black/white speaker.');
const recapCounts = Object.fromEntries(ratingSchema.categories.map(v => [v.id, {black:0, white:0}]));
for (const a of annotations) if (a.speaker) recapCounts[a.rating][a.speaker]++;
const sourceHash = createHash('sha256').update(await fs.readFile(source)).digest('hex');
if (spec.source_sha256 && sourceHash !== spec.source_sha256) throw new Error('Timeline source_sha256 does not match the supplied media.');
if (validateOnly) {
  console.log(JSON.stringify({ valid: true, demo, source_sha256: sourceHash,
    source_dimensions: [video.width, video.height], opening, legacy_opening_override: legacyOpeningOverride,
    source_quality_accepted:!lowResPreview, minimum_source_height:minimumSourceHeight,
    source_quality_reviewed:sourceQualityReviewed, outro_layout_reviewed:outroLayoutReviewed,
    side_colors: sides, annotation_count: annotations.length, recap_counts: recapCounts,
    rating_schema_version: ratingSchema.version, final_video_exported: false }));
  process.exit(0);
}
if (refreshProjectIntro) {
  const existing = JSON.parse(await fs.readFile(path.join(output, 'project-manifest.json'), 'utf8'));
  const pastAnnotations = existing.segments.filter(v => v.kind === 'analysis');
  const pastSource = existing.segments.filter(v => v.kind === 'source');
  const expected = spec.intro_seconds + end - start + annotations.reduce((sum, a) => sum + a.hold_seconds, 0);
  if (existing.source_sha256 !== sourceHash || existing.icon_set !== ratingSchema.icon_set || existing.bar?.side !== ratingSchema.bar.side
    || existing.duration !== expected || pastSource[0]?.source_in !== start || pastSource.at(-1)?.source_out !== end
    || (existing.side_colors && JSON.stringify(existing.side_colors) !== JSON.stringify(sides))
    || (existing.initial_score_text && existing.initial_score_text !== initialScoreText)
    || pastAnnotations.length !== annotations.length || pastAnnotations.some((v, i) => {
      const a = annotations[i]; return v.source_at !== a.source_at || v.duration !== a.hold_seconds || v.rating !== a.rating || v.comment !== a.comment || v.score_text !== a.score_text;
    })) throw new Error('Existing project media differs; project-intro refresh refused.');
}
if (refreshIntro) {
  if (previousRender.rating_schema_version !== ratingSchema.version || previousRender.bar?.side !== 'left') throw new Error('The old layout or icon set differs; a complete render is required.');
  const pastAnnotations = previousRender.events.filter(v => v.kind === 'analysis');
  const pastSource = previousRender.events.filter(v => v.kind === 'source');
  if (previousRender.source_sha256 !== sourceHash || previousRender.expected_duration !== ratingSchema.intro_seconds + end - start + annotations.reduce((sum, v) => sum + v.hold_seconds, 0)
    || pastSource[0]?.source_in !== start || pastSource.at(-1)?.source_out !== end
    || JSON.stringify(previousRender.side_colors) !== JSON.stringify(sides)
    || pastAnnotations.length !== annotations.length || pastAnnotations.some((v, i) => { const a = annotations[i]; return v.source_at !== a.source_at || v.duration !== a.hold_seconds || v.rating !== a.rating || v.comment !== a.comment || v.control !== a.control_after || v.score_text !== a.score_text; })) throw new Error('Existing montage does not match this source/timeline; intro-only refresh refused.');
}
const mascot = path.resolve(option('--tony', path.join(here, 'assets/tony-pawn.png')));
const mascotBytes = await fs.readFile(mascot);
if (!mascotBytes.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) throw new Error('--tony must be a PNG');
const overlayMascot = path.resolve(option('--tony-overlay', path.join(here, 'assets/tony-pawn-overlay.png')));
const overlayMascotBytes = await fs.readFile(overlayMascot);
if (!overlayMascotBytes.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) throw new Error('--tony-overlay must be a PNG');
const iconAssets = {};
for (const rating of ratingSchema.categories) {
  const bytes = await fs.readFile(path.join(here, rating.icon_file));
  if (createHash('sha256').update(bytes).digest('hex') !== rating.icon_sha256) throw new Error(`Official icon hash mismatch: ${rating.id}`);
  iconAssets[rating.id] = `data:image/svg+xml;base64,${bytes.toString('base64')}`;
}
const { loadSfxManifest, renderAnalysisAudio } = await import('./sfx.mjs');
const sfxManifestPath = path.resolve(option('--sfx-manifest', path.join(here, 'assets/sfx/manifest.json')));
const sfxManifest = await loadSfxManifest(sfxManifestPath);
const browser = await chromium.launch({ executablePath: '/usr/bin/chromium', headless: true, args: ['--disable-dev-shm-usage'] });
const overlays = [], annotationFrames = [];
const introFrameDirectory = path.join(output, 'intro-overlay-frames');
const introBackground = path.join(output, 'intro-source-frame.png');
const outroFrameDirectory = path.join(output, 'outro-frames');
run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-ss', String(start), '-i', source, '-frames:v', '1', '-update', '1', introBackground]);
const introBytes = await fs.readFile(introBackground);
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.route('**/*', route => route.abort());
  await page.setContent('<!doctype html><html><body style="margin:0"><canvas width="1920" height="1080"></canvas></body></html>');
  await page.evaluate(({ schema, icons }) => { window.ConversationRatingSchema = schema; window.ConversationRatingAssets = icons; }, { schema: ratingSchema, icons: iconAssets });
  await page.addScriptTag({ content: await fs.readFile(path.join(here, 'scene.js'), 'utf8') });
  await page.evaluate(({ mascot, backdrop, overlayMascot }) => window.ConversationChess.init(mascot, backdrop, overlayMascot), { mascot: `data:image/png;base64,${mascotBytes.toString('base64')}`, backdrop: `data:image/png;base64,${introBytes.toString('base64')}`, overlayMascot: `data:image/png;base64,${overlayMascotBytes.toString('base64')}` });
  async function overlay(name, options) {
    const data = await page.evaluate(o => window.ConversationChess.clipFrame(o), { ...options, sides, low_res_preview: lowResPreview, source_height: video.height });
    const dest = path.join(output, name + '.png');
    await fs.writeFile(dest, Buffer.from(data.split(',')[1], 'base64')); return dest;
  }
  overlays.push(await overlay('intro-symbols', { phase: 'intro', t: 3 }));
  overlays.push(await overlay('intro-bar', { phase: 'intro', t: 9 }));
  if (prepareProject) {
    await fs.mkdir(introFrameDirectory, { recursive: true });
    for (let frame = 0; frame < spec.intro_seconds * graphicsFps; frame++) {
      const data = await page.evaluate(o => window.ConversationChess.clipFrame(o), { phase: 'intro', t: frame / graphicsFps, intro_overlay: true });
      await fs.writeFile(path.join(introFrameDirectory, `frame_${String(frame).padStart(5, '0')}.png`), Buffer.from(data.split(',')[1], 'base64'));
    }
  }
  if (!refreshIntro && !refreshProjectIntro) {
  overlays.push(await overlay('overlay-initial', { control, score_text: scoreText, demo, showSides: true }));
  for (let i = 0; i < annotations.length; i++) {
    const a = annotations[i];
    overlays.push(await overlay(`overlay-freeze-${i}`, { control: a.control_after, score_text: a.score_text, evaluation: a, demo }));
    const frameDir = path.join(output, `overlay-freeze-${i}-frames`);
    await fs.mkdir(frameDir, { recursive: true });
    for (let frame = 0; frame < Math.ceil(a.hold_seconds * graphicsFps); frame++) {
      const data = await page.evaluate(o => window.ConversationChess.clipFrame(o), { control: a.control_after, score_text: a.score_text, evaluation: a, demo, sides, low_res_preview: lowResPreview, source_height: video.height, previous_control: i ? annotations[i - 1].control_after : control, previous_score_text: i ? annotations[i - 1].score_text : initialScoreText, reveal_seconds: frame / graphicsFps });
      await fs.writeFile(path.join(frameDir, `frame_${String(frame).padStart(5, '0')}.png`), Buffer.from(data.split(',')[1], 'base64'));
    }
    annotationFrames.push(frameDir);
    overlays.push(await overlay(`overlay-after-${i}`, { control: a.control_after, score_text: a.score_text, demo }));
  }
  }
  if (prepareProject && outroSeconds) {
    await fs.mkdir(outroFrameDirectory, { recursive: true });
    for (let frame = 0; frame < outroSeconds * graphicsFps; frame++) {
      const data = await page.evaluate(o => window.ConversationChess.clipFrame(o), {
        phase:'outro', t:frame / graphicsFps, duration:outroSeconds, counts:recapCounts, sides, subtitle:spec.outro_subtitle,
      });
      await fs.writeFile(path.join(outroFrameDirectory, `frame_${String(frame).padStart(5, '0')}.png`), Buffer.from(data.split(',')[1], 'base64'));
    }
  }
} finally { await browser.close(); }

if (prepareProject) {
  // Interchange media only. The actual final export belongs to Kdenlive/MLT;
  // source, muted replay, alpha graphics, dialogue and SFX stay separate.
  const projectSegments = [];
  const fps = 30;
  let projectCursor = start, projectElapsed = 0, projectControl = control, projectScore = initialScoreText;
  function addProjectSegment(segment) {
    const startFrame = Math.round(projectElapsed * fps), endFrame = Math.round((projectElapsed + segment.duration) * fps);
    projectSegments.push({ ...segment, output_in: projectElapsed, start_frame: startFrame, end_frame: endFrame, duration_frames: endFrame - startFrame });
    projectElapsed += segment.duration;
  }
  function alphaMovie(directory, duration, name) {
    const dest = path.join(output, name + '.mov');
    run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-framerate', String(graphicsFps), '-i', path.join(directory, 'frame_%05d.png'),
      '-an', '-vf', 'format=argb', '-c:v', 'qtrle', '-threads', '2', '-r', String(fps), '-t', String(duration), dest]);
    return dest;
  }
  async function musicPart(name, duration) {
    const config = spec.music?.[name];
    if (!config) return {};
    if (typeof config.file !== 'string' || /^[a-z]+:\/\//i.test(config.file) || path.isAbsolute(config.file)) throw new Error('Music file must be relative to this renderer, never a remote URL.');
    const file = path.resolve(here, config.file), bytes = await fs.readFile(file);
    if (!/^[a-f0-9]{64}$/.test(config.sha256 || '') || createHash('sha256').update(bytes).digest('hex') !== config.sha256) throw new Error(`Music hash mismatch: ${name}`);
    const gain = config.gain ?? .28, offset = config.start_seconds ?? 0;
    if (!Number.isFinite(gain) || gain < 0 || gain > 1 || !Number.isFinite(offset) || offset < 0) throw new Error('Supply music gain0–1 and a nonnegative start_seconds.');
    const audio = JSON.parse(run('/usr/bin/ffprobe', ['-v','error','-show_streams','-show_format','-of','json',file], true));
    if (!audio.streams.some(s => s.codec_type === 'audio') || Number(audio.format.duration) < offset + duration) throw new Error(`Music is too short: ${name}`);
    const dest = path.join(output, `music-${name}.wav`);
    run('/usr/bin/ffmpeg', ['-hide_banner','-loglevel','error','-y','-ss',String(offset),'-i',file,'-vn','-af',
      `aresample=48000,volume=${gain},afade=t=in:st=0:d=0.18,afade=t=out:st=${duration-1}:d=1,apad,atrim=end_sample=${Math.round(duration*48000)}`,
      '-c:a','pcm_s16le','-ar','48000','-ac','2',dest]);
    return {music_file:dest, music_title:config.title, music_license:config.license, music_source_sha256:config.sha256, music_gain:gain, music_offset_seconds:offset};
  }
  const introBackgroundFile = path.join(output, 'project-background-intro.png');
  run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-i', introBackground,
    '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black', '-frames:v', '1', '-update', '1', introBackgroundFile]);
  addProjectSegment({ kind: 'intro', duration: spec.intro_seconds, background_file: introBackgroundFile,
    graphics_file: alphaMovie(introFrameDirectory, spec.intro_seconds, 'project-graphics-intro'), graphics_type: 'alpha_mov', graphics_frames: introFrameDirectory,
    ...(await musicPart('intro', spec.intro_seconds)) });
  if (refreshProjectIntro) {
    const projectManifest = path.join(output, 'project-manifest.json');
    const existing = JSON.parse(await fs.readFile(projectManifest, 'utf8'));
    existing.segments[0] = projectSegments[0];
    await fs.writeFile(projectManifest, JSON.stringify(existing, null, 2));
    console.log(JSON.stringify({ project_manifest: projectManifest, intro_refreshed: true, scene_media_unchanged: true, final_video_exported: false }));
    process.exit(0);
  }
  const sourceVideoFilter = 'scale=1848:1080:force_original_aspect_ratio=decrease,pad=1848:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1,pad=1920:1080:72:0:black';
  const videoEncoding = ['-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '17', '-threads', '4', '-pix_fmt', 'yuv420p', '-r', String(fps)];
  function prepareNormal(until, overlayFile) {
    const duration = until - projectCursor;
    if (duration <= 0) return;
    const label = `project-source-${String(projectSegments.length).padStart(3, '0')}`;
    const backgroundFile = path.join(output, label + '.mkv'), dialogueAudioFile = path.join(output, label + '-dialogue.wav');
    run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-ss', String(projectCursor), '-i', source, '-vf', sourceVideoFilter, '-t', String(duration), ...videoEncoding, backgroundFile]);
    const audioInput = hasAudio ? ['-ss', String(projectCursor), '-i', source] : ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'];
    run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', ...audioInput, '-vn', '-af',
      `aresample=48000,apad,afade=t=in:st=0:d=0.035,afade=t=out:st=${Math.max(0, duration - .035)}:d=0.035,atrim=end_sample=${Math.round(duration * 48000)}`,
      '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2', dialogueAudioFile]);
    addProjectSegment({ kind: 'source', duration, source_in: projectCursor, source_out: until, background_file: backgroundFile,
      graphics_file: overlayFile, graphics_type: 'alpha_png', dialogue_audio_file: dialogueAudioFile, control: projectControl, score_text: projectScore });
    projectCursor = until;
  }
  let normalOverlay = overlays[2];
  for (let i = 0; i < annotations.length; i++) {
    const a = annotations[i]; prepareNormal(a.source_at, normalOverlay);
    const replayStart = Math.max(start, a.source_at - (a.replay_seconds || 3));
    const history = a.source_at - replayStart, replaySpeed = history / a.hold_seconds;
    const backgroundFile = path.join(output, `project-replay-${i}.mkv`), sfxFile = path.join(output, `analysis-sfx-${i}.wav`);
    const input = analysisBackground === 'freeze' ? ['-ss', String(a.source_at), '-i', source] : ['-ss', String(replayStart), '-t', String(history), '-i', source];
    const stretch = analysisBackground === 'freeze' ? 'select=eq(n\\,0),tpad=stop_mode=clone:stop_duration=9,' : `setpts=${a.hold_seconds / history}*(PTS-STARTPTS),tpad=stop_mode=clone:stop_duration=0.5,`;
    if (analysisBackground === 'loop') throw new Error('--prepare-project supports replay or freeze, not the legacy loop mode.');
    run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', ...input, '-vf', `${stretch}gblur=sigma=13,${sourceVideoFilter}`, '-t', String(a.hold_seconds), ...videoEncoding, backgroundFile]);
    await renderAnalysisAudio({ manifest: sfxManifest, annotation: a, schema: ratingSchema, outputPath: sfxFile });
    addProjectSegment({ kind: 'analysis', duration: a.hold_seconds, source_at: a.source_at, rating: a.rating, speaker: a.speaker,
      comment: a.comment, score_text: a.score_text, control: a.control_after, background_file: backgroundFile,
      replay_range: { source_in: replayStart, source_out: a.source_at }, replay_speed: replaySpeed, original_dialogue_progression_paused: true,
      graphics_file: alphaMovie(annotationFrames[i], a.hold_seconds, `project-graphics-analysis-${i}`), graphics_type: 'alpha_mov', graphics_frames: annotationFrames[i], sfx_file: sfxFile });
    projectControl = a.control_after; projectScore = a.score_text; normalOverlay = overlays[4 + i * 2];
  }
  prepareNormal(end, normalOverlay);
  if (outroSeconds) {
    const backgroundFile = path.join(output, 'project-background-outro.png');
    await fs.copyFile(path.join(outroFrameDirectory,'frame_00030.png'),backgroundFile);
    addProjectSegment({kind:'outro', duration:outroSeconds, background_file:backgroundFile,
      graphics_file:alphaMovie(outroFrameDirectory,outroSeconds,'project-graphics-outro'), graphics_type:'alpha_mov',
      graphics_frames:outroFrameDirectory, recap_counts:recapCounts, ...(await musicPart('outro',outroSeconds))});
  }
  const projectManifest = path.join(output, 'project-manifest.json');
  await fs.writeFile(projectManifest, JSON.stringify({ schema: 'conversation-chess-kdenlive-interchange-v1', version: 1,
    original_source: source, source_sha256: sourceHash, source_dimensions: [video.width, video.height], source_quality: { minimum_height: minimumSourceHeight, low_res_preview: lowResPreview, accepted_for_final:!lowResPreview, visually_reviewed:sourceQualityReviewed },
    timeline_file: timelinePath, timeline_sha256: createHash('sha256').update(await fs.readFile(timelinePath)).digest('hex'), rating_schema_version: ratingSchema.version,
    fps, graphics_fps: graphicsFps, width: 1920, height: 1080, duration: projectElapsed, duration_frames: Math.round(projectElapsed * fps),
    icon_set: ratingSchema.icon_set, bar: ratingSchema.bar, scores_are_editorial: true, original_audio_present: hasAudio, voiceover: false,
    demo, side_colors: sides, opening, legacy_opening_override: legacyOpeningOverride, initial_score_text: initialScoreText,
    outro_layout_reviewed:outroLayoutReviewed,
    final_export_engine: 'Kdenlive / MLT required', sfx_manifest: sfxManifestPath, published: false, segments: projectSegments }, null, 2));
  console.log(JSON.stringify({ project_manifest: projectManifest, duration: projectElapsed, final_video_exported: false, tracks_are_separate: true }));
  process.exit(0);
}

const fps = 30, intro = spec.intro_seconds, segments = [], events = [];
const encoding = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '17', '-threads', '4', '-pix_fmt', 'yuv420p',
  '-r', String(fps), '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2'];
function segment(kind, duration, argv, filter, audioMap, afilter, details) {
  // PCM avoids an AAC encoder delay at every editorial freeze/cut.
  const dest = path.join(output, `segment-${String(segments.length).padStart(3, '0')}.mkv`);
  run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', ...argv,
    '-filter_complex', filter, '-map', '[out]', '-map', audioMap,
    ...(afilter ? ['-af', afilter] : []), '-t', String(duration), ...encoding, dest]);
  segments.push(dest); events.push({ kind, duration, ...details });
}
segment('intro-symbols', ratingSchema.symbols_seconds, ['-loop', '1', '-framerate', String(fps), '-i', overlays[0],
  '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'], '[0:v]format=yuv420p[out]', '1:a', '', { output_in: 0 });
const barSeconds = intro - ratingSchema.symbols_seconds;
segment('intro-bar', barSeconds, ['-loop', '1', '-framerate', String(fps), '-i', overlays[1],
  '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'],
  `[0:v]format=yuv420p,fade=t=out:st=${barSeconds - ratingSchema.fade_seconds}:d=${ratingSchema.fade_seconds}[out]`, '1:a', '', { output_in: ratingSchema.symbols_seconds });
function layout(freeze = false, replayStretch = 1) {
  // Preserve every source pixel, reserving a 72px LEFT gutter for the chess-style bar.
  return `[0:v]${replayStretch !== 1 ? `setpts=${replayStretch}*(PTS-STARTPTS),tpad=stop_mode=clone:stop_duration=0.5,` : ''}scale=1848:1080:force_original_aspect_ratio=decrease${freeze ? ',gblur=sigma=13' : ''},pad=1848:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1,pad=1920:1080:72:0:black[base];[base][1:v]overlay=0:0:shortest=1:format=auto[out]`;
}
let cursor = start, elapsed = intro, overlayIndex = 2;
function normal(until) {
  const duration = until - cursor;
  if (duration <= 0) return;
  const argv = ['-ss', String(cursor), '-i', source, '-loop', '1', '-framerate', String(fps), '-i', overlays[overlayIndex]];
  if (!hasAudio) argv.push('-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo');
  const fadeOut = Math.max(0, duration - .035);
  segment('source', duration, argv, layout(), hasAudio ? '0:a:0' : '2:a',
    `aresample=48000,apad,afade=t=in:st=0:d=0.035,afade=t=out:st=${fadeOut}:d=0.035`,
    { source_in: cursor, source_out: until, output_in: elapsed, control, score_text: scoreText });
  elapsed += duration; cursor = until;
}
if (refreshIntro) {
  for (let i = 2; i < previousRender.events.length; i++) {
    const existing = path.join(output, `segment-${String(i).padStart(3, '0')}.mkv`);
    if (!(await fs.stat(existing)).isFile()) throw new Error('Existing montage segment is missing.');
    segments.push(existing); events.push(previousRender.events[i]);
  }
  elapsed = previousRender.expected_duration;
} else {
for (let i = 0; i < annotations.length; i++) {
  const a = annotations[i]; normal(a.source_at);
  const still = path.join(output, `source-freeze-${i}.png`);
  run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-ss', String(a.source_at), '-i', source,
    '-frames:v', '1', '-update', '1', still]);
  if (!(await fs.stat(still)).size) throw new Error('Could not extract the reviewed source frame.');
  overlayIndex = 3 + i * 2;
  let backgroundInput = ['-loop', '1', '-framerate', String(fps), '-i', still];
  let loopRange = null, replayStretch = 1;
  if (['loop','replay'].includes(analysisBackground)) {
    const contextSeconds = analysisBackground === 'replay' ? (a.replay_seconds || 3) : .8;
    const loopStart = Math.max(start, a.source_at - contextSeconds), loopDuration = a.source_at - loopStart;
    const moving = path.join(output, `source-loop-${i}.mkv`);
    run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-ss', String(loopStart), '-i', source,
      '-t', String(loopDuration), '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-r', String(fps),
      '-threads', '2', '-pix_fmt', 'yuv420p', moving]);
    backgroundInput = analysisBackground === 'loop' ? ['-stream_loop', '-1', '-i', moving] : ['-i', moving];
    if (analysisBackground === 'replay') replayStretch = a.hold_seconds / loopDuration;
    loopRange = { source_in: loopStart, source_out: a.source_at };
  }
  const analysisAudio = path.join(output, `analysis-sfx-${i}.wav`);
  await renderAnalysisAudio({ manifest: sfxManifest, annotation: a, schema: ratingSchema, outputPath: analysisAudio });
  segment('analysis', a.hold_seconds, [...backgroundInput,
    '-framerate', String(graphicsFps), '-i', path.join(annotationFrames[i], 'frame_%05d.png'),
    '-i', analysisAudio], layout(true, replayStretch), '2:a', '',
    { source_at: a.source_at, output_in: elapsed, rating: a.rating, speaker: a.speaker || null,
      comment: a.comment, control: a.control_after, score_text: a.score_text, sfx_file: analysisAudio, background: analysisBackground, replay_range: loopRange, replay_speed: 1 / replayStretch,
      original_dialogue_progression_paused: true });
  elapsed += a.hold_seconds; control = a.control_after; scoreText = a.score_text; overlayIndex += 1;
}
normal(end);
}
const concat = path.join(output, 'segments.txt');
await fs.writeFile(concat, segments.map(p => `file '${p.replace(/'/g, "'\\''")}'`).join('\n') + '\n');
const result = path.join(output, 'clip.mp4');
run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', concat,
  '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', result]);
const finalMeta = JSON.parse(run('/usr/bin/ffprobe', ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', result], true));
run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-i', result, '-f', 'null', '-']);
run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-i', result, '-vf',
  `fps=8/${elapsed},scale=640:360,tile=4x2:padding=8:margin=8:color=0x161a1e`, '-frames:v', '1', '-update', '1', path.join(output, 'contact-sheet.jpg')]);
const actual = Number(finalMeta.format.duration);
if (Math.abs(actual - elapsed) > .2) throw new Error(`Unexpected output duration ${actual}; expected ${elapsed}`);
await fs.writeFile(path.join(output, 'render-report.json'), JSON.stringify({ schema: spec.schema, demo, rating_schema_version: ratingSchema.version,
  reference_guide_observed: true, reference_guide_id: 'InM2zft-iQs',
  bar: ratingSchema.bar, initial_score_text: initialScoreText, conversation_score_editorial: true, icon_set: ratingSchema.icon_set,
  graphics_fps: graphicsFps,
  source_quality: { native_hd: video.height >= 720, minimum_height: minimumSourceHeight, low_res_preview: lowResPreview, accepted_for_final:!lowResPreview, visually_reviewed:sourceQualityReviewed },
  sfx_manifest: sfxManifestPath, sfx_added_during_analysis_only: true,
  side_colors: sides, opening, legacy_opening_override: legacyOpeningOverride, analysis_background: analysisBackground, transparent_mascot_in_guide: true,
  timeline_sha256: createHash('sha256').update(await fs.readFile(timelinePath)).digest('hex'),
  review_evidence: spec.review_evidence || null,
  original_audio_present: hasAudio, voiceover: false, source_sha256: sourceHash,
  source_dimensions: [video.width, video.height], output_dimensions: [1920,1080],
  expected_duration: elapsed, duration: actual, fps, events, file: result,
  published: false, source_timestamps_require_editorial_review: true }, null, 2));
console.log(JSON.stringify({ file: result, duration: actual, demo, original_audio: hasAudio, published: false }));
