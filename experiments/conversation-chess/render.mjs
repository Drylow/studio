#!/usr/bin/env node
// Local preview renderer only. It does not access the studio, Google or a publisher.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
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
const fps = Number(option('--fps', '30'));
const seconds = Number(option('--duration', '14'));
const mascot = option('--tony', '');
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
const browser = await chromium.launch({ executablePath: option('--chromium', '/usr/bin/chromium'), headless: true,
  args: ['--disable-dev-shm-usage'] });
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  // Offline synthetic content: prohibit all network access during the render.
  await page.route('**/*', route => route.abort());
  await page.setContent('<!doctype html><html><head><meta charset="UTF-8"><style>html,body{margin:0;background:#161a1e}canvas{display:block}</style></head><body><canvas width="1920" height="1080"></canvas></body></html>');
  await page.addScriptTag({ content: await fs.readFile(path.join(here, 'scene.js'), 'utf8') });
  await page.evaluate(src => window.ConversationChess.init(src), mascotSource);
  const total = Math.round(fps * seconds);
  for (let i = 0; i < total; i++) {
    const data = await page.evaluate(t => window.ConversationChess.frame(t), i / fps);
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
  '-vf', 'fps=1/2,scale=640:360,tile=4x2:padding=8:margin=8:color=0x161a1e', '-frames:v', '1',
  '-update', '1',
  path.join(output, 'contact-sheet.jpg')]);
await fs.copyFile(path.join(output, 'frames', `frame_${String(Math.round(2 * fps)).padStart(5, '0')}.png`), path.join(output, 'legend.png'));
await fs.copyFile(path.join(output, 'frames', `frame_${String(Math.round(10 * fps)).padStart(5, '0')}.png`), path.join(output, 'example.png'));
await fs.writeFile(path.join(output, 'render.json'), JSON.stringify({ width: 1920, height: 1080, fps,
  duration: seconds, audio: false, real_scene_footage: false, supplied_tony_png: Boolean(mascot),
  files: { video, sheet: path.join(output, 'contact-sheet.jpg') } }, null, 2));
process.stdout.write(`Preview: ${video}\n`);
