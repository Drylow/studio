// Place the verified original SVG grades on a separately generated clean plate.
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
const base = option('--base'), layout = option('--layout'), out = option('--out');
if (!/\.(png|jpe?g)$/i.test(out)) throw new Error('Output must be PNG or JPEG');
for (const destination of [out, out+'.json']) {
  try { await fs.access(destination); throw new Error('Preserve existing proposals and receipts: use a new output path'); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
}
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const bytes = await fs.readFile(base);
const spec = JSON.parse(await fs.readFile(layout, 'utf8'));
const schema = JSON.parse(await fs.readFile(path.join(here, 'ratings.json'), 'utf8'));
if (!Array.isArray(spec.badges) || spec.badges.length < 1 || spec.badges.length > 2) throw new Error('Supply one or two original grade badges');
const icons = [];
for (const placement of spec.badges) {
  const rating = schema.categories.find(r => r.id === placement.id && r.active !== false);
  if (!rating || ['miss', 'interesting'].includes(placement.id)) throw new Error(`Unsupported active grade: ${placement.id}`);
  const icon = await fs.readFile(path.join(here, rating.icon_file));
  if (sha256(icon) !== rating.icon_sha256) throw new Error(`Original SVG hash differs: ${placement.id}`);
  for (const key of ['x', 'y', 'width']) if (!Number.isFinite(placement[key])) throw new Error(`Invalid ${key}`);
  if (placement.x < 0 || placement.y < 0 || placement.width <= 0) throw new Error('Badge coordinates must be positive normalized values');
  const rotation = placement.rotation_degrees ?? 0;
  if (!Number.isFinite(rotation) || Math.abs(rotation) > 15) throw new Error('Badge rotation must be within 15 degrees');
  icons.push({...placement, rotation_degrees:rotation, sha256:sha256(icon), source:`data:image/svg+xml;base64,${icon.toString('base64')}`});
}
const format = /\.jpe?g$/i.test(out) ? 'image/jpeg' : 'image/png';
const browser = await loadChromium().launch(browserOptions(''));
try {
  const page = await browser.newPage();
  await page.route('**/*', route => route.abort());
  await page.setContent('<!doctype html><meta charset="UTF-8"><canvas></canvas>');
  const result = await page.evaluate(async ({base, icons, format}) => {
    const load = source => new Promise((resolve, reject) => {
      const image = new Image(); image.onload = () => resolve(image); image.onerror = reject; image.src = source;
    });
    const [artwork, ...assets] = await Promise.all([load(base), ...icons.map(icon => load(icon.source))]);
    if (artwork.width < 1280 || artwork.height < 720 || Math.abs(artwork.width / artwork.height - 16/9) > .005) throw new Error('Use a clean 16:9 plate of at least 1280×720');
    const canvas = document.querySelector('canvas'); canvas.width = artwork.width; canvas.height = artwork.height;
    const context = canvas.getContext('2d'); context.drawImage(artwork, 0, 0);
    const before = context.getImageData(0,0,canvas.width,canvas.height).data;
    const placements = icons.map((icon, i) => {
      const w = icon.width * canvas.width, h = w * assets[i].height / assets[i].width;
      const x = icon.x * canvas.width, y = icon.y * canvas.height;
      const angle = icon.rotation_degrees * Math.PI / 180;
      const bw = Math.abs(w * Math.cos(angle)) + Math.abs(h * Math.sin(angle));
      const bh = Math.abs(w * Math.sin(angle)) + Math.abs(h * Math.cos(angle));
      const bounds = {left:Math.floor(x+w/2-bw/2)-1, top:Math.floor(y+h/2-bh/2)-1, right:Math.ceil(x+w/2+bw/2)+1, bottom:Math.ceil(y+h/2+bh/2)+1};
      if (bounds.left < 0 || bounds.top < 0 || bounds.right > canvas.width || bounds.bottom > canvas.height) throw new Error('A badge would be cut by the image edge');
      context.save(); context.translate(x+w/2,y+h/2); context.rotate(angle);
      context.drawImage(assets[i], -w/2, -h/2, w, h); context.restore();
      return {id:icon.id, x, y, width:w, height:h, rotation_degrees:icon.rotation_degrees, bounds};
    });
    const after = context.getImageData(0,0,canvas.width,canvas.height).data;
    let changedOutsideBadges = 0;
    for (let y=0;y<canvas.height;y++) for (let x=0;x<canvas.width;x++) {
      if (placements.some(p => x >= p.bounds.left && x < p.bounds.right && y >= p.bounds.top && y < p.bounds.bottom)) continue;
      const offset = (y*canvas.width+x)*4;
      for (let c=0;c<4;c++) if (before[offset+c] !== after[offset+c]) changedOutsideBadges++;
    }
    if (changedOutsideBadges) throw new Error('Artwork changed outside the original badge overlays');
    return {dataUrl:canvas.toDataURL(format,.95),width:canvas.width,height:canvas.height,placements,changedOutsideBadges};
  }, {base:`data:image/png;base64,${bytes.toString('base64')}`,icons,format});
  const output = Buffer.from(result.dataUrl.split(',')[1], 'base64');
  await fs.mkdir(path.dirname(out),{recursive:true}); await fs.writeFile(out,output,{flag:'wx'});
  const {dataUrl,...geometry} = result;
  const receipt = {base,base_sha256:sha256(bytes),layout,output_sha256:sha256(output),bytes:output.length,format,...geometry,icons:icons.map(({source,...icon})=>icon),pixel_comparison_stage:'Decoded canvas before file encoding; JPEG is lossy',visually_reviewed:false};
  await fs.writeFile(out+'.json',JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({output:out,bytes:output.length,width:result.width,height:result.height,original_svg_icons_verified:true,unchanged_artwork_outside_badges:true}));
} finally {await browser.close();}
