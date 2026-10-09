#!/usr/bin/env node
// Local preview renderer only. It does not access the studio, Google or a publisher.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const require = createRequire(path.join(root, 'frontend/package.json'));
const { chromium } = require('playwright');
const args = process.argv.slice(2);
function option(name, fallback) {
  const i = args.indexOf(name);
  if (i < 0) return fallback;
  if (!args[i + 1] || args[i + 1].startsWith('--')) throw new Error(`Missing value after ${name}`);
  return args[i + 1];
}
const output = path.resolve(option('--out', '/tmp/edgerunners-conversation-chess'));
const introOnly = true;
const fps = Number(option('--fps', '30'));
const ratingSchema = JSON.parse(await fs.readFile(path.join(here, 'ratings.json'), 'utf8'));
const seconds = Number(option('--duration', introOnly ? String(ratingSchema.intro_seconds) : '14'));
const mascot = option('--tony', path.join(here, 'assets/tony-pawn.png'));
const overlayMascot = option('--tony-overlay', path.join(here, 'assets/tony-pawn-overlay.png'));
const overlayMascotSource = `data:image/png;base64,${(await fs.readFile(path.resolve(overlayMascot))).toString('base64')}`;
const backgroundImage = option('--background', '');
const backgroundSource = backgroundImage ? `data:image/png;base64,${(await fs.readFile(path.resolve(backgroundImage))).toString('base64')}` : '';
if (!Number.isFinite(fps) || fps < 1 || fps > 60 || !Number.isFinite(seconds) || seconds < 11 || seconds > 30) {
  throw new Error('Expected fps 1–60 and duration 11–30 seconds.');
}
await fs.mkdir(path.join(output, 'frames'), { recursive: true });
let mascotSource = '';
if (mascot) {
  const data = await fs.readFile(path.resolve(mascot));
  if (!data.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) throw new Error('--tony must be a PNG');
  mascotSource = `data:image/png;base64,${data.toString('base64')}`;
}
const iconAssets = {};
for (const rating of ratingSchema.categories) {
  const bytes = await fs.readFile(path.join(here, rating.icon_file));
  if (createHash('sha256').update(bytes).digest('hex') !== rating.icon_sha256) throw new Error(`Official icon hash mismatch: ${rating.id}`);
  iconAssets[rating.id] = `data:image/svg+xml;base64,${bytes.toString('base64')}`;
}
const browser = await chromium.launch({ executablePath: option('--chromium', '/usr/bin/chromium'), headless: true,
  args: ['--disable-dev-shm-usage'] });
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  // Offline synthetic content: prohibit all network access during the render.
  await page.route('**/*', route => route.abort());
  await page.setContent('<!doctype html><html><head><meta charset="UTF-8"><style>html,body{margin:0;background:#161a1e}canvas{display:block}</style></head><body><canvas width="1920" height="1080"></canvas></body></html>');
  await page.evaluate(({ schema, icons }) => { window.ConversationRatingSchema = schema; window.ConversationRatingAssets = icons; }, { schema: ratingSchema, icons: iconAssets });
  await page.addScriptTag({ content: await fs.readFile(path.join(here, 'scene.js'), 'utf8') });
  await page.evaluate(({ mascot, backdrop, overlayMascot }) => window.ConversationChess.init(mascot, backdrop, overlayMascot), { mascot: mascotSource, backdrop: backgroundSource, overlayMascot: overlayMascotSource });
  const total = Math.round(fps * seconds);
  for (let i = 0; i < total; i++) {
    const data = await page.evaluate(({ t, introOnly }) => introOnly ? window.ConversationChess.introFrame(t) : window.ConversationChess.frame(t), { t: i / fps, introOnly });
    await fs.writeFile(path.join(output, 'frames', `frame_${String(i).padStart(5, '0')}.png`), Buffer.from(data.split(',')[1], 'base64'));
    if (i % fps === 0) process.stdout.write(`Rendered ${i / fps}/${seconds} s\n`);
  }
} finally {
  await browser.close();
}
function command(bin, cmd) {
  const result = spawnSync(bin, cmd, { stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${bin} exited ${result.status}`);
}
const video = path.join(output, 'preview.mp4');
command('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'warning', '-y', '-framerate', String(fps),
  '-i', path.join(output, 'frames/frame_%05d.png'), '-frames:v', String(Math.round(fps * seconds)),
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', video]);
command('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'warning', '-y', '-i', video,
  '-vf', `fps=8/${seconds},scale=640:360,tile=4x2:padding=8:margin=8:color=0x161a1e`, '-frames:v', '1',
  '-update', '1',
  path.join(output, 'contact-sheet.jpg')]);
await fs.copyFile(path.join(output, 'frames', `frame_${String(Math.round(3 * fps)).padStart(5, '0')}.png`), path.join(output, 'legend.png'));
await fs.copyFile(path.join(output, 'frames', `frame_${String(Math.round(10 * fps)).padStart(5, '0')}.png`), path.join(output, 'example.png'));
await fs.writeFile(path.join(output, 'render.json'), JSON.stringify({ width: 1920, height: 1080, fps,
  duration: seconds, intro_only: introOnly, audio: false, supplied_background: Boolean(backgroundImage),
  internal_design_draft: true, icon_set: ratingSchema.icon_set, reference_guide_observed: true, reference_guide_id: 'InM2zft-iQs', supplied_tony_png: Boolean(mascot), supplied_tony_overlay: Boolean(overlayMascot),
  files: { video, sheet: path.join(output, 'contact-sheet.jpg') } }, null, 2));
process.stdout.write(`Preview: ${video}\n`);
