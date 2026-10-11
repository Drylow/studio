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
  const result = await page.evaluate(async ({base, icons}) => {
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
    const placements = [
      {x:24, y:20, width:192, height:192 * 19 / 18, rotation:10},
      {x:width - 216, y:20, width:192, height:192 * 19 / 18, rotation:-10}
    ];
    badges.forEach((badge, i) => {
      const p = placements[i]; ctx.save(); ctx.translate(p.x + p.width / 2, p.y + p.height / 2);
      ctx.rotate(p.rotation * Math.PI / 180); ctx.drawImage(badge, -p.width / 2, -p.height / 2, p.width, p.height); ctx.restore();
    });
    const final = ctx.getImageData(0, 0, width, height).data;
    let changesOutsideCorners = 0;
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
      if (y < 250 && (x < 240 || x >= width - 240)) continue;
      const offset = (y * width + x) * 4;
      for (let channel = 0; channel < 4; channel++) if (original[offset + channel] !== final[offset + channel]) changesOutsideCorners++;
    }
    if (changesOutsideCorners) throw new Error('Artwork changed outside badge corners');
    return {dataUrl:canvas.toDataURL('image/jpeg', .96), width, height, sourceWidth:art.width, sourceHeight:art.height, crop, placements, changesOutsideCorners};
  }, {base:`data:image/png;base64,${baseBytes.toString('base64')}`, icons});
  const {dataUrl, ...geometry} = result;
  const bytes = Buffer.from(dataUrl.split(',')[1], 'base64');
  await fs.mkdir(path.dirname(out), {recursive:true});
  await fs.writeFile(out, bytes);
  const receipt = {base_file:path.basename(basePath), base_sha256:hash(baseBytes), output_file:path.basename(out), output_sha256:hash(bytes), bytes:bytes.length, ...geometry, icons:icons.map(({source, ...icon}) => icon), comparison_stage:'Before lossy JPEG encoding'};
  await fs.writeFile(out + '.json', JSON.stringify(receipt, null, 2) + '\n');
  console.log(JSON.stringify({output:out, ...geometry, bytes:bytes.length, original_svg_icons_verified:true}));
} finally {await browser.close();}
