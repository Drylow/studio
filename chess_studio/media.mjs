import {spawn} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';

export function run(command, args, onLine = () => {}, timeout = 30*60*1000) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {shell: false, windowsHide: true});
    let output = '', tail = '', done = false;
    const timer = setTimeout(() => {child.kill(); finish(new Error('Opération trop longue.'));}, timeout);
    const finish = (err) => {if (done) return; done = true; clearTimeout(timer); err ? reject(err) : resolve(output);};
    child.stdout.on('data', b => {output += b; if(output.length > 2e6) output = output.slice(-2e6); onLine(String(b));});
    child.stderr.on('data', b => {tail = (tail+String(b)).slice(-5000); onLine(String(b));});
    child.on('error', e => finish(new Error(`${command} : ${e.message}`)));
    child.on('close', code => finish(code === 0 ? null : new Error(`${command} a échoué (${code}) : ${tail}`)));
  });
}
export const FFMPEG = process.env.CHESS_FFMPEG || 'ffmpeg';
export const FFPROBE = process.env.CHESS_FFPROBE || 'ffprobe';
export const YTDLP = process.env.CHESS_YTDLP || 'yt-dlp';
export async function probe(file) {
  const data = JSON.parse(await run(FFPROBE, ['-v','error','-show_streams','-show_format','-of','json',file]));
  const video = data.streams.find(x => x.codec_type === 'video');
  if (!video) throw new Error('Ce fichier ne contient pas de vidéo.');
  const fraction = String(video.avg_frame_rate || '0/1').split('/').map(Number);
  const duration = Number(data.format.duration || video.duration);
  if (!Number.isFinite(duration) || duration <= 0) throw new Error('Durée du clip illisible.');
  return {duration, width: video.width, height: video.height, fps: fraction[0]/fraction[1],
    codec: video.codec_name, hasAudio: data.streams.some(x => x.codec_type === 'audio')};
}
export function youtubeUrl(input) {
  let u; try {u = new URL(input);} catch {throw new Error('Lien YouTube invalide.');}
  if (u.protocol !== 'https:' || !['www.youtube.com','youtube.com','youtu.be'].includes(u.hostname) || u.username || u.password || u.port) throw new Error('Importer un lien vidéo YouTube HTTPS.');
  const id = u.hostname === 'youtu.be' ? u.pathname.slice(1) : u.searchParams.get('v') || /^\/(?:shorts|embed)\/([\w-]+)/.exec(u.pathname)?.[1];
  if (!/^[\w-]{11}$/.test(id || '')) throw new Error('Lien vers une vidéo individuelle requis.');
  return `https://www.youtube.com/watch?v=${id}`;
}
export async function ingest(file, name, publicDir, onLine = () => {}, sourceUrl = '') {
  const id = randomUUID(); const dir = path.join(publicDir, 'media', id);
  const info = await probe(file);
  await fs.mkdir(dir, {recursive: true});
  const ext = path.extname(file).toLowerCase() || '.mp4';
  const original = path.join(dir, `original${ext}`);
  await fs.copyFile(file, original);
  const previewTranscoded = !(info.codec === 'h264' && ext === '.mp4');
  const preview = previewTranscoded ? path.join(dir, 'preview.mp4') : original;
  if (previewTranscoded) {
    onLine('Préparation de l’aperçu compatible navigateur, sans réduire la résolution…');
    await run(FFMPEG, ['-hide_banner','-loglevel','error','-y','-i',original,'-map','0:v:0','-map','0:a:0?',
      ...(info.codec==='h264'?['-c:v','copy']:['-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p']),
      '-c:a','aac','-b:a','256k','-movflags','+faststart',preview],onLine);
  }
  await run(FFMPEG, ['-hide_banner','-loglevel','error','-y','-ss',String(Math.min(2, info.duration/3)),
    '-i',original,'-frames:v','1','-vf','scale=480:-2','-q:v','3',path.join(dir,'thumbnail.jpg')]);
  return {id, name: String(name).slice(0,180), ...info, src: `media/${id}/${path.basename(preview)}`,
    original: `media/${id}/${path.basename(original)}`, thumbnail: `media/${id}/thumbnail.jpg`, sourceUrl, previewTranscoded};
}
export async function download(input, publicDir, tempDir, onLine = () => {}, language = 'en') {
  const url = youtubeUrl(input);
  if (!['en','fr'].includes(language)) throw new Error('Audio : anglais ou français.');
  const dir = path.join(tempDir, randomUUID()); await fs.mkdir(dir,{recursive:true});
  try {
    await run(YTDLP, ['--no-playlist','--no-progress','--newline','--socket-timeout','25','--retries','2',
      '--match-filter','!is_live & duration <= 1800', '-f', `bv*+ba[language^=${language}]/bv*+ba/b`,
      '-S', `res,lang:${language},vcodec:h264`, '--merge-output-format','mkv','--write-info-json','-o',path.join(dir,'clip.%(ext)s'),url], onLine);
    const files = await fs.readdir(dir);
    const video = files.find(f => /^clip\.(mp4|webm|mkv|mov)$/.test(f));
    if (!video) throw new Error('Clip non téléchargé : utiliser une vidéo publique de moins de 30 minutes.');
    let meta = {}; try {meta = JSON.parse(await fs.readFile(path.join(dir,'clip.info.json'),'utf8'));} catch {}
    const media = await ingest(path.join(dir,video),meta.title || url,publicDir,onLine,url);
    // Preserve useful provenance, never expiring signed URLs or cookies.
    const audio=(meta.requested_formats || meta.requested_downloads?.[0]?.requested_formats || []).find(f=>f.acodec && f.acodec!=='none');
    media.audioLanguage = audio?.language || meta.language || 'unknown';
    if(!media.audioLanguage.startsWith(language))onLine(`Audio importé : ${media.audioLanguage}. La langue ${language} demandée n’est pas disponible dans les flux reçus.`);
    return media;
  } finally {await fs.rm(dir,{recursive:true,force:true});}
}
