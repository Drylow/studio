// Rendu d'une vidéo du format Histoire.
//   node render.mjs --project <dossier> [--out video.mp4] [--concurrency 4] [--still 12.5 --still-out f.jpg]
//   node render.mjs --project <dossier> --chunk-dir <dossier> [--chunk-frames 2700]   (par morceaux, reprise)
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
  process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith('--') ? [...acc, [a.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : '']] : acc), []),
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
} else if (args['chunk-dir']) {
  // rendu par morceaux, repris là où il s'est arrêté : une vidéo longue survit à un redémarrage de la machine
  //   --chunk-dir <dossier> [--chunk-frames 2700]  → part_000.mp4… (vidéo sans son) + audio.wav
  const dir = path.resolve(args['chunk-dir']);
  fs.mkdirSync(dir, {recursive: true});
  const total = composition.durationInFrames;
  const size = parseInt(args['chunk-frames'] || '2700', 10);
  const n = Math.ceil(total / size);
  const concurrency = parseInt(args.concurrency || String(Math.max(1, Math.floor(os.cpus().length / 2))), 10);
  const part = (i) => path.join(dir, `part_${String(i).padStart(3, '0')}.mp4`);
  // --chunks "3,4,9" : seulement ces morceaux (rendu réparti sur plusieurs machines) ; --no-audio / --audio-only
  const only = args.chunks ? new Set(String(args.chunks).split(',').filter(Boolean).map(Number)) : null;
  // --reverse : du dernier morceau au premier (rendu local pendant qu'une machine RunPod part du début)
  const order = [...Array(n).keys()];
  if (args.reverse !== undefined) order.reverse();
  // --skip-claimed : laisse les morceaux qu'une machine RunPod est en train de rendre (claim_XXX.rp) ; les siens sont
  // signalés par claim_XXX.local pour que RunPod ne les prenne pas
  const claim = (i, who) => path.join(dir, `claim_${String(i).padStart(3, '0')}.${who}`);
  for (const i of order) {
    if (args['audio-only'] !== undefined || (only && !only.has(i)) || fs.existsSync(part(i))) continue;
    if (args['skip-claimed'] !== undefined && fs.existsSync(claim(i, 'rp'))) continue;
    if (args['skip-claimed'] !== undefined) fs.writeFileSync(claim(i, 'local'), '');
    const tmp = part(i).replace('.mp4', '.tmp.mp4');
    const frameRange = [i * size, Math.min(total, (i + 1) * size) - 1];
    let last = -1;
    await renderMedia({
      composition, serveUrl, codec: 'h264', crf: parseInt(args.crf || '20', 10), x264Preset: args.preset || 'veryfast',
      muted: true, frameRange, outputLocation: tmp, inputProps: timeline, browserExecutable, concurrency,
      ...(args.gl ? {chromiumOptions: {gl: args.gl}} : {}),
      onProgress: ({progress}) => {
        const p = Math.floor(progress * 100);
        if (p !== last) {
          last = p;
          const done = frameRange[0] + progress * (frameRange[1] - frameRange[0] + 1);
          say({stage: 'render', progress: done / total, renderedFrames: Math.round(done), total, chunk: i + 1, chunks: n});
        }
      },
    });
    fs.renameSync(tmp, part(i));
    fs.rmSync(claim(i, 'local'), {force: true});
  }
  const wav = path.join(dir, 'audio.wav');
  if (args['no-audio'] === undefined && !fs.existsSync(wav)) {
    say({stage: 'audio'});
    await renderMedia({composition, serveUrl, codec: 'wav', outputLocation: wav + '.tmp.wav', inputProps: timeline,
      browserExecutable, concurrency});
    fs.renameSync(wav + '.tmp.wav', wav);
  }
  say({stage: 'done', chunks: n});
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
