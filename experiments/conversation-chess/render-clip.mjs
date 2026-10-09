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
const previousRender = refreshIntro ? JSON.parse(await fs.readFile(path.join(output, 'render-report.json'), 'utf8')) : null;
const spec = JSON.parse(await fs.readFile(timelinePath, 'utf8'));
const ratingSchema = JSON.parse(await fs.readFile(path.join(here, 'ratings.json'), 'utf8'));
const meta = JSON.parse(run('/usr/bin/ffprobe', ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', source], true));
const sourceDuration = Number(meta.format.duration);
const hasAudio = meta.streams.some(s => s.codec_type === 'audio');
const video = meta.streams.find(s => s.codec_type === 'video');
if (!video || !Number.isFinite(sourceDuration)) throw new Error('Source has no usable video/duration.');
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
const sides = { black: spec.black_label || 'Tony', white: spec.white_label || 'Other speaker' };
if (Object.values(sides).some(v => typeof v !== 'string' || !v.trim() || v.length > 32)) throw new Error('Supply short black_label/white_label names.');
const isControl = c => (typeof c === 'number' && Number.isFinite(c) && c >= 0 && c <= 1) || controls.has(c);
let control = spec.initial_control ?? .5;
if (!isControl(control)) throw new Error('Unknown initial_control.');
const annotations = spec.annotations || [];
if (!Array.isArray(annotations)) throw new Error('annotations must be an array.');
let previous = start, reviewedControl = control;
const controlFraction = c => typeof c === 'number' ? c : ({ balanced: .5, black: .72, white: .28, tony: .72, ralph: .28 })[c];
for (const a of annotations) {
  if (!Number.isFinite(a.source_at) || a.source_at <= previous || a.source_at >= end) throw new Error('Annotations need strictly ordered SOURCE timestamps inside the selected clip.');
  if (a.hold_seconds < 3 || a.hold_seconds > 9 || !Number.isFinite(a.hold_seconds)) throw new Error('Each analysis hold must last 3–9 seconds.');
  if (!ratings.has(a.rating) || !isControl(a.control_after)) throw new Error('Unknown rating/control_after.');
  const rating = ratingSchema.categories.find(v => v.id === a.rating);
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
const sourceHash = createHash('sha256').update(await fs.readFile(source)).digest('hex');
if (spec.source_sha256 && sourceHash !== spec.source_sha256) throw new Error('Timeline source_sha256 does not match the supplied media.');
if (refreshIntro) {
  const pastAnnotations = previousRender.events.filter(v => v.kind === 'analysis');
  const pastSource = previousRender.events.filter(v => v.kind === 'source');
  if (previousRender.source_sha256 !== sourceHash || previousRender.expected_duration !== ratingSchema.intro_seconds + end - start + annotations.reduce((sum, v) => sum + v.hold_seconds, 0)
    || pastSource[0]?.source_in !== start || pastSource.at(-1)?.source_out !== end
    || JSON.stringify(previousRender.side_colors) !== JSON.stringify(sides)
    || pastAnnotations.length !== annotations.length || pastAnnotations.some((v, i) => { const a = annotations[i]; return v.source_at !== a.source_at || v.duration !== a.hold_seconds || v.rating !== a.rating || v.comment !== a.comment || v.control !== a.control_after; })) throw new Error('Existing montage does not match this source/timeline; intro-only refresh refused.');
}
const mascot = path.resolve(option('--tony', path.join(here, 'assets/tony-pawn.png')));
const mascotBytes = await fs.readFile(mascot);
if (!mascotBytes.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) throw new Error('--tony must be a PNG');
const overlayMascot = path.resolve(option('--tony-overlay', path.join(here, 'assets/tony-pawn-overlay.png')));
const overlayMascotBytes = await fs.readFile(overlayMascot);
if (!overlayMascotBytes.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) throw new Error('--tony-overlay must be a PNG');
const browser = await chromium.launch({ executablePath: '/usr/bin/chromium', headless: true, args: ['--disable-dev-shm-usage'] });
const overlays = [], annotationFrames = [];
const introBackground = path.join(output, 'intro-source-frame.png');
run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-ss', String(start), '-i', source, '-frames:v', '1', '-update', '1', introBackground]);
const introBytes = await fs.readFile(introBackground);
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.route('**/*', route => route.abort());
  await page.setContent('<!doctype html><html><body style="margin:0"><canvas width="1920" height="1080"></canvas></body></html>');
  await page.evaluate(schema => window.ConversationRatingSchema = schema, ratingSchema);
  await page.addScriptTag({ content: await fs.readFile(path.join(here, 'scene.js'), 'utf8') });
  await page.evaluate(({ mascot, backdrop, overlayMascot }) => window.ConversationChess.init(mascot, backdrop, overlayMascot), { mascot: `data:image/png;base64,${mascotBytes.toString('base64')}`, backdrop: `data:image/png;base64,${introBytes.toString('base64')}`, overlayMascot: `data:image/png;base64,${overlayMascotBytes.toString('base64')}` });
  async function overlay(name, options) {
    const data = await page.evaluate(o => window.ConversationChess.clipFrame(o), { ...options, sides });
    const dest = path.join(output, name + '.png');
    await fs.writeFile(dest, Buffer.from(data.split(',')[1], 'base64')); return dest;
  }
  overlays.push(await overlay('intro-symbols', { phase: 'intro', t: 3 }));
  overlays.push(await overlay('intro-bar', { phase: 'intro', t: 9 }));
  if (!refreshIntro) {
  overlays.push(await overlay('overlay-initial', { control, demo, showSides: true }));
  for (let i = 0; i < annotations.length; i++) {
    const a = annotations[i];
    overlays.push(await overlay(`overlay-freeze-${i}`, { control: a.control_after, evaluation: a, demo }));
    const frameDir = path.join(output, `overlay-freeze-${i}-frames`);
    await fs.mkdir(frameDir, { recursive: true });
    for (let frame = 0; frame < Math.ceil(a.hold_seconds * 15); frame++) {
      const data = await page.evaluate(o => window.ConversationChess.clipFrame(o), { control: a.control_after, evaluation: a, demo, sides, previous_control: i ? annotations[i - 1].control_after : control, reveal_seconds: frame / 15 });
      await fs.writeFile(path.join(frameDir, `frame_${String(frame).padStart(5, '0')}.png`), Buffer.from(data.split(',')[1], 'base64'));
    }
    annotationFrames.push(frameDir);
    overlays.push(await overlay(`overlay-after-${i}`, { control: a.control_after, demo }));
  }
  }
} finally { await browser.close(); }

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
  // Preserve every source pixel: full-height film with right-side 120px bar, no crop.
  return `[0:v]${replayStretch !== 1 ? `setpts=${replayStretch}*(PTS-STARTPTS),tpad=stop_mode=clone:stop_duration=0.5,` : ''}scale=1800:1080:force_original_aspect_ratio=decrease${freeze ? ',gblur=sigma=13' : ''},pad=1800:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1,pad=1920:1080:0:0:black[base];[base][1:v]overlay=0:0:shortest=1:format=auto[out]`;
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
    { source_in: cursor, source_out: until, output_in: elapsed, control });
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
  segment('analysis', a.hold_seconds, [...backgroundInput,
    '-framerate', '15', '-i', path.join(annotationFrames[i], 'frame_%05d.png'),
    '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'], layout(true, replayStretch), '2:a', '',
    { source_at: a.source_at, output_in: elapsed, rating: a.rating, speaker: a.speaker || null,
      comment: a.comment, control: a.control_after, background: analysisBackground, replay_range: loopRange, replay_speed: 1 / replayStretch,
      original_dialogue_progression_paused: true });
  elapsed += a.hold_seconds; control = a.control_after; overlayIndex += 1;
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
  side_colors: sides, analysis_background: analysisBackground, transparent_mascot_in_guide: true,
  timeline_sha256: createHash('sha256').update(await fs.readFile(timelinePath)).digest('hex'),
  review_evidence: spec.review_evidence || null,
  original_audio_present: hasAudio, voiceover: false, source_sha256: sourceHash,
  source_dimensions: [video.width, video.height], output_dimensions: [1920,1080],
  expected_duration: elapsed, duration: actual, fps, events, file: result,
  published: false, source_timestamps_require_editorial_review: true }, null, 2));
console.log(JSON.stringify({ file: result, duration: actual, demo, original_audio: hasAudio, published: false }));
