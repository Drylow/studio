// Compose the original rating SVGs onto a clean illustration without redrawing them.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {loadChromium, browserOptions} from './runtime.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
function option(name) {
  const i = args.indexOf(name);
  if (i < 0 || !args[i + 1] || args[i + 1].startsWith('--')) throw new Error(`Missing ${name}`);
  return path.resolve(args[i + 1]);
}
const basePath = option('--base'), out = option('--out');
const layoutPath = args.includes('--layout') ? option('--layout') : null;
const placements = layoutPath ? JSON.parse(await fs.readFile(layoutPath, 'utf8')).placements : [
  {x:24, y:20, width:192, height:192 * 19 / 18, rotation:10},
  {x:1280 - 216, y:20, width:192, height:192 * 19 / 18, rotation:-10}
];
if (!Array.isArray(placements) || placements.length !== 2) throw new Error('Place Brilliant then Blunder.');
for (const p of placements) {
  if (![p.x, p.y, p.width, p.height, p.rotation].every(Number.isFinite)
      || p.width < 96 || p.width > 240 || Math.abs(p.rotation) > 20
      || Math.abs(p.height / p.width - 19 / 18) > .001) throw new Error('Invalid original badge geometry.');
  const angle = p.rotation * Math.PI / 180;
  const halfX = (Math.abs(p.width * Math.cos(angle)) + Math.abs(p.height * Math.sin(angle))) / 2;
  const halfY = (Math.abs(p.width * Math.sin(angle)) + Math.abs(p.height * Math.cos(angle))) / 2;
  const cx = p.x + p.width / 2, cy = p.y + p.height / 2;
  if (cx - halfX < 0 || cy - halfY < 0 || cx + halfX > 1280 || cy + halfY > 720)
    throw new Error('Keep the complete tilted badges inside the thumbnail.');
}
if (!/\.jpe?g$/i.test(out)) throw new Error('Output must be a JPEG thumbnail.');
for (const file of [out, out + '.json']) {
  try {await fs.access(file); throw new Error(`Preserve existing output: ${file}`);}
  catch (error) {if (error.code !== 'ENOENT') throw error;}
}
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const baseBytes = await fs.readFile(basePath);
const schema = JSON.parse(await fs.readFile(path.join(here, 'ratings.json'), 'utf8'));
const icons = [];
for (const id of ['brilliant', 'blunder']) {
  const rating = schema.categories.find(r => r.id === id);
  const bytes = await fs.readFile(path.join(here, rating.icon_file));
  if (hash(bytes) !== rating.icon_sha256) throw new Error(`Original SVG mismatch: ${id}`);
  icons.push({id, file:rating.icon_file, sha256:hash(bytes), source:`data:image/svg+xml;base64,${bytes.toString('base64')}`});
}
const browser = await loadChromium().launch(browserOptions(''));
try {
  const page = await browser.newPage();
  await page.route('**/*', route => route.abort());
  await page.setContent('<!doctype html><meta charset="UTF-8"><canvas></canvas>');
  const result = await page.evaluate(async ({base, icons, placements, customLayout}) => {
    const load = source => new Promise((resolve, reject) => {
      const image = new Image(); image.onload = () => resolve(image); image.onerror = reject; image.src = source;
    });
    const [art, ...badges] = await Promise.all([load(base), ...icons.map(i => load(i.source))]);
    const width = 1280, height = 720;
    const canvas = document.querySelector('canvas'); canvas.width = width; canvas.height = height;
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
    const scale = Math.max(width / art.width, height / art.height);
    const crop = {x:(width - art.width * scale) / 2, y:(height - art.height * scale) / 2, width:art.width * scale, height:art.height * scale};
    ctx.drawImage(art, crop.x, crop.y, crop.width, crop.height);
    const original = ctx.getImageData(0, 0, width, height).data;
    const badgeBounds = placements.map(p => {
      const a = p.rotation * Math.PI / 180;
      const halfX = (Math.abs(p.width * Math.cos(a)) + Math.abs(p.height * Math.sin(a))) / 2 + 3;
      const halfY = (Math.abs(p.width * Math.sin(a)) + Math.abs(p.height * Math.cos(a))) / 2 + 3;
      return {left:p.x + p.width / 2 - halfX, right:p.x + p.width / 2 + halfX,
              top:p.y + p.height / 2 - halfY, bottom:p.y + p.height / 2 + halfY};
    });
    badges.forEach((badge, i) => {
      const p = placements[i]; ctx.save(); ctx.translate(p.x + p.width / 2, p.y + p.height / 2);
      ctx.rotate(p.rotation * Math.PI / 180); ctx.drawImage(badge, -p.width / 2, -p.height / 2, p.width, p.height); ctx.restore();
    });
    const final = ctx.getImageData(0, 0, width, height).data;
    let changesOutsideBadges = 0;
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
      if (badgeBounds.some(b => x >= b.left && x <= b.right && y >= b.top && y <= b.bottom)) continue;
      const offset = (y * width + x) * 4;
      for (let channel = 0; channel < 4; channel++) if (original[offset + channel] !== final[offset + channel]) changesOutsideBadges++;
    }
    if (changesOutsideBadges) throw new Error('Artwork changed outside badge bounds');
    return {dataUrl:canvas.toDataURL('image/jpeg', .96), width, height, sourceWidth:art.width, sourceHeight:art.height, crop,
            placements, changesOutsideBadges, ...(customLayout ? {badgeBounds} : {changesOutsideCorners:0})};
  }, {base:`data:image/png;base64,${baseBytes.toString('base64')}`, icons, placements, customLayout:!!layoutPath});
  const {dataUrl, ...geometry} = result;
  const bytes = Buffer.from(dataUrl.split(',')[1], 'base64');
  await fs.mkdir(path.dirname(out), {recursive:true});
  await fs.writeFile(out, bytes);
  const receipt = {base_file:path.basename(basePath), base_sha256:hash(baseBytes), output_file:path.basename(out), output_sha256:hash(bytes), bytes:bytes.length, ...geometry, icons:icons.map(({source, ...icon}) => icon), comparison_stage:'Before lossy JPEG encoding'};
  await fs.writeFile(out + '.json', JSON.stringify(receipt, null, 2) + '\n');
  console.log(JSON.stringify({output:out, ...geometry, bytes:bytes.length, original_svg_icons_verified:true}));
} finally {await browser.close();}
