// Rendu d'une vidéo du format Histoire.
//   node render.mjs --project <dossier> [--out video.mp4] [--concurrency 4] [--still 12.5 --still-out f.jpg]
// Le dossier du projet contient timeline.json + ses médias (servi comme publicDir).
// Chrome : REMOTION_BROWSER (sinon Remotion télécharge chrome-headless-shell au 1er lancement).
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith('--') ? [...acc, [a.slice(2), all[i + 1]]] : acc), []),
);
const project = path.resolve(args.project || '.');
const timeline = JSON.parse(fs.readFileSync(path.join(project, args.timeline || 'timeline.json'), 'utf8'));
const browserExecutable = process.env.REMOTION_BROWSER || null;
const say = (o) => process.stdout.write(JSON.stringify(o) + '\n');

say({stage: 'bundle'});
const serveUrl = await bundle({entryPoint: path.join(here, 'src', 'index.ts'), publicDir: project});
const composition = await selectComposition({serveUrl, id: 'History', inputProps: timeline, browserExecutable});

if (args.stills !== undefined) {
  // aperçus : --stills "3,12.5,40" --stills-dir <dossier>  (une image JPEG par instant, en secondes)
  const dir = path.resolve(args['stills-dir'] || path.join(project, 'stills'));
  fs.mkdirSync(dir, {recursive: true});
  for (const t of String(args.stills).split(',').filter(Boolean)) {
    const frame = Math.min(composition.durationInFrames - 1, Math.round(parseFloat(t) * composition.fps));
    const output = path.join(dir, `still_${String(t).replace('.', '_')}.jpg`);
    await renderStill({composition, serveUrl, output, frame, inputProps: timeline, browserExecutable, imageFormat: 'jpeg', jpegQuality: 88});
    say({stage: 'still', t, output});
  }
  say({stage: 'done'});
} else {
  let last = -1;
  await renderMedia({
    composition,
    serveUrl,
    codec: 'h264',
    crf: 23,
    x264Preset: 'medium',
    audioBitrate: '192k',
    outputLocation: path.resolve(args.out || path.join(project, 'render.mp4')),
    inputProps: timeline,
    browserExecutable,
    concurrency: parseInt(args.concurrency || String(Math.max(1, Math.floor(os.cpus().length / 2))), 10),
    onProgress: ({progress, renderedFrames, encodedFrames}) => {
      const p = Math.floor(progress * 100);
      if (p !== last) {
        last = p;
        say({stage: 'render', progress, renderedFrames, encodedFrames, total: composition.durationInFrames});
      }
    },
  });
  say({stage: 'done'});
}
