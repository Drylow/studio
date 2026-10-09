// Insert the reviewed original Chess.com SVG assets into an approved thumbnail.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {loadChromium, browserOptions} from './runtime.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
function option(name) {
  const i = args.indexOf(name);
  if (i < 0 || !args[i+1] || args[i+1].startsWith('--')) throw new Error(`Missing ${name}`);
  return path.resolve(args[i+1]);
}
const original = option('--original'), clean = option('--clean'), out = option('--out');
const tiltIndex = args.indexOf('--tilt');
const tilt = tiltIndex < 0 ? 0 : Number(args[tiltIndex+1]);
if (!Number.isFinite(tilt) || Math.abs(tilt) > 15) throw new Error('--tilt must be a number between -15 and 15 degrees.');
const format = /\.jpe?g$/i.test(out) ? 'image/jpeg' : 'image/png';
try {await fs.access(out); throw new Error('Preserve the previous thumbnail: choose a new --out filename.');}
catch (error) {if (error.code !== 'ENOENT') throw error;}
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const originalBytes = await fs.readFile(original), cleanBytes = await fs.readFile(clean);
const schema = JSON.parse(await fs.readFile(path.join(here, 'ratings.json'), 'utf8'));
const icons = [];
for (const id of ['brilliant','blunder']) {
  const rating = schema.categories.find(r => r.id === id);
  const bytes = await fs.readFile(path.join(here, rating.icon_file));
  if (hash(bytes) !== rating.icon_sha256) throw new Error(`Original icon hash mismatch: ${id}`);
  icons.push({id, sha256:hash(bytes), source:`data:image/svg+xml;base64,${bytes.toString('base64')}`});
}
const browser = await loadChromium().launch(browserOptions(''));
try {
  const page = await browser.newPage();
  await page.route('**/*', route => route.abort());
  await page.setContent('<!doctype html><meta charset="UTF-8"><canvas></canvas>');
  const result = await page.evaluate(async ({original, clean, icons, format, tilt}) => {
    const load = source => new Promise((resolve,reject) => {
      const image = new Image(); image.onload = () => resolve(image); image.onerror = reject; image.src = source;
    });
    const [base, plate, brilliant, blunder] = await Promise.all([load(original),load(clean),...icons.map(i=>load(i.source))]);
    if (base.width !== plate.width || base.height !== plate.height || base.width !== 1672 || base.height !== 941) throw new Error('Use the reviewed 1672×941 thumbnail B and its matching clean plate.');
    const canvas = document.querySelector('canvas'); canvas.width=base.width; canvas.height=base.height;
    const ctx = canvas.getContext('2d'); ctx.drawImage(base,0,0);
    const originalPixels = ctx.getImageData(0,0,canvas.width,canvas.height).data;
    // Only the old badge corner regions come from the edited plate. All faces,
    // hand, expressions, costumes and framing retain their approved original pixels.
    const patches = [{x:0,y:0,w:280,h:288},{x:canvas.width-280,y:0,w:280,h:288}];
    for (const p of patches) ctx.drawImage(plate,p.x,p.y,p.w,p.h,p.x,p.y,p.w,p.h);
    const placements = [{x:4,y:3,w:250,h:250*19/18,rotation_degrees:tilt},{x:canvas.width-254,y:3,w:250,h:250*19/18,rotation_degrees:-tilt}];
    [brilliant,blunder].forEach((image,i) => {
      const p=placements[i]; ctx.save();
      ctx.translate(p.x+p.w/2,p.y+p.h/2);
      ctx.rotate(p.rotation_degrees*Math.PI/180);
      ctx.drawImage(image,-p.w/2,-p.h/2,p.w,p.h); ctx.restore();
    });
    const finalPixels = ctx.getImageData(0,0,canvas.width,canvas.height).data;
    let differencesOutsidePatches=0;
    for(let y=0;y<canvas.height;y++) for(let x=0;x<canvas.width;x++) {
      if(patches.some(p=>x>=p.x && x<p.x+p.w && y>=p.y && y<p.y+p.h)) continue;
      const offset=(y*canvas.width+x)*4;
      for(let channel=0;channel<4;channel++) if(originalPixels[offset+channel]!==finalPixels[offset+channel]) differencesOutsidePatches++;
    }
    if(differencesOutsidePatches) throw new Error('Approved artwork changed outside the badge corners');
    return {dataUrl:canvas.toDataURL(format,.95), width:canvas.width,height:canvas.height,patches,placements,differencesOutsidePatches};
  }, {original:`data:image/png;base64,${originalBytes.toString('base64')}`,clean:`data:image/png;base64,${cleanBytes.toString('base64')}`,icons,format,tilt});
  await fs.mkdir(path.dirname(out),{recursive:true});
  const output = Buffer.from(result.dataUrl.split(',')[1],'base64'); await fs.writeFile(out,output);
  const {dataUrl,...geometry}=result;
  const receipt={original,original_sha256:hash(originalBytes),clean,clean_sha256:hash(cleanBytes),output_sha256:hash(output),bytes:output.length,format,pixel_comparison_stage:'Canvas composition before file encoding; JPEG is lossy.',...geometry,icons:icons.map(({source,...item})=>item)};
  await fs.writeFile(out+'.json',JSON.stringify(receipt,null,2));
  console.log(JSON.stringify({output:out,bytes:output.length,width:result.width,height:result.height,unchanged_artwork_outside_badges:true,original_svg_icons_verified:true}));
} finally {await browser.close();}
