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
const spec = JSON.parse(await fs.readFile(timelinePath, 'utf8'));
const meta = JSON.parse(run('/usr/bin/ffprobe', ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', source], true));
const sourceDuration = Number(meta.format.duration);
const hasAudio = meta.streams.some(s => s.codec_type === 'audio');
const video = meta.streams.find(s => s.codec_type === 'video');
if (!video || !Number.isFinite(sourceDuration)) throw new Error('Source has no usable video/duration.');
if (spec.schema !== 'conversation-chess-clip-v1') throw new Error('Unknown timeline schema.');
if (spec.intro_seconds !== 12) throw new Error('The reviewed four-badge intro is 12 seconds.');
const start = Number(spec.source_in), end = Number(spec.source_out);
if (![start, end].every(Number.isFinite) || start < 0 || end <= start || end > sourceDuration + .05) throw new Error('source_in/source_out must be inside the supplied source.');
const demo = spec.demo === true;
if (!hasAudio && !demo) throw new Error('Real dialogue footage must contain its original audio.');
if (!demo && spec.source_reviewed !== true) throw new Error('Real footage requires source_reviewed=true after review.');
const ratings = new Set(['brilliant', 'best', 'mistake', 'blunder']);
const controls = new Set(['balanced', 'tony', 'ralph']);
let control = spec.initial_control || 'balanced';
if (!controls.has(control)) throw new Error('Unknown initial_control.');
const annotations = spec.annotations || [];
if (!Array.isArray(annotations)) throw new Error('annotations must be an array.');
let previous = start;
for (const a of annotations) {
  if (!Number.isFinite(a.source_at) || a.source_at <= previous || a.source_at >= end) throw new Error('Annotations need strictly ordered SOURCE timestamps inside the selected clip.');
  if (a.hold_seconds < 3 || a.hold_seconds > 4 || !Number.isFinite(a.hold_seconds)) throw new Error('Each freeze must last 3–4 seconds.');
  if (!ratings.has(a.rating) || !controls.has(a.control_after)) throw new Error('Unknown rating/control_after.');
  if (typeof a.comment !== 'string' || !a.comment.trim() || a.comment.length > 110) throw new Error('Supply a short editorial English comment.');
  if (!demo && a.reviewed !== true) throw new Error('Every real annotation requires reviewed=true; do not invent source timestamps.');
  previous = a.source_at;
}
const sourceHash = createHash('sha256').update(await fs.readFile(source)).digest('hex');
if (spec.source_sha256 && sourceHash !== spec.source_sha256) throw new Error('Timeline source_sha256 does not match the supplied media.');
const mascot = path.resolve(option('--tony', path.join(here, 'assets/tony-pawn.png')));
const mascotBytes = await fs.readFile(mascot);
if (!mascotBytes.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) throw new Error('--tony must be a PNG');
const browser = await chromium.launch({ executablePath: '/usr/bin/chromium', headless: true, args: ['--disable-dev-shm-usage'] });
const overlays = [];
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.route('**/*', route => route.abort());
  await page.setContent('<!doctype html><html><body style="margin:0"><canvas width="1920" height="1080"></canvas></body></html>');
  await page.addScriptTag({ content: await fs.readFile(path.join(here, 'scene.js'), 'utf8') });
  await page.evaluate(src => window.ConversationChess.init(src), `data:image/png;base64,${mascotBytes.toString('base64')}`);
  async function overlay(name, options) {
    const data = await page.evaluate(o => window.ConversationChess.clipFrame(o), options);
    const dest = path.join(output, name + '.png');
    await fs.writeFile(dest, Buffer.from(data.split(',')[1], 'base64')); return dest;
  }
  overlays.push(await overlay('intro', { phase: 'intro' }));
  overlays.push(await overlay('overlay-initial', { control, demo }));
  for (let i = 0; i < annotations.length; i++) {
    const a = annotations[i];
    overlays.push(await overlay(`overlay-freeze-${i}`, { control: a.control_after, evaluation: a, demo }));
    overlays.push(await overlay(`overlay-after-${i}`, { control: a.control_after, demo }));
  }
} finally { await browser.close(); }

const fps = 30, intro = 12, segments = [], events = [];
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
segment('intro', intro, ['-loop', '1', '-framerate', String(fps), '-i', overlays[0],
  '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'], '[0:v]format=yuv420p[out]', '1:a', '', { output_in: 0 });
function layout(freeze = false) {
  const [width, height] = freeze ? [1280,720] : [1600,900];
  return `[0:v]scale=${width}:${height}:force_original_aspect_ratio=decrease,pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,pad=1920:1080:72:72:color=0x161a1e[base];[base][1:v]overlay=0:0:shortest=1:format=auto[out]`;
}
let cursor = start, elapsed = intro, overlayIndex = 1;
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
for (let i = 0; i < annotations.length; i++) {
  const a = annotations[i]; normal(a.source_at);
  const still = path.join(output, `source-freeze-${i}.png`);
  run('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-ss', String(a.source_at), '-i', source,
    '-frames:v', '1', '-update', '1', still]);
  if (!(await fs.stat(still)).size) throw new Error('Could not extract the reviewed source frame.');
  overlayIndex = 2 + i * 2;
  segment('freeze', a.hold_seconds, ['-loop', '1', '-framerate', String(fps), '-i', still,
    '-loop', '1', '-framerate', String(fps), '-i', overlays[overlayIndex],
    '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'], layout(true), '2:a', '',
    { source_at: a.source_at, output_in: elapsed, rating: a.rating, comment: a.comment, control: a.control_after });
  elapsed += a.hold_seconds; control = a.control_after; overlayIndex += 1;
}
normal(end);
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
await fs.writeFile(path.join(output, 'render-report.json'), JSON.stringify({ schema: spec.schema, demo,
  original_audio_present: hasAudio, voiceover: false, source_sha256: sourceHash,
  source_dimensions: [video.width, video.height], output_dimensions: [1920,1080],
  expected_duration: elapsed, duration: actual, fps, events, file: result,
  published: false, source_timestamps_require_editorial_review: true }, null, 2));
console.log(JSON.stringify({ file: result, duration: actual, demo, original_audio: hasAudio, published: false }));
