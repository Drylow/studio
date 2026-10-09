// Local, documented sound assets for the silent analysis blocks only.
// This helper never accepts source dialogue or downloads audio.
import fs from 'node:fs/promises';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mediaBinary } from './runtime.mjs';
import { randomUUID } from 'node:crypto';

const execute = promisify(execFile);
const sampleRate = 48_000;
const assetNames = ['typewriter', 'move', 'brilliant', 'error', 'blunder'];
const loadedManifests = new WeakSet();

async function run(bin, args) {
  try {
    const { stdout } = await execute(bin, args, { encoding: 'utf8', maxBuffer: 2_000_000 });
    return stdout;
  } catch (error) {
    throw new Error(`${path.basename(bin)} failed: ${String(error.stderr || error.message).slice(-1200)}`);
  }
}

function localPath(value, name) {
  if (typeof value !== 'string' || !value.trim() || value.includes('\0') || (!path.isAbsolute(value) && /^[a-z][a-z0-9+.-]*:/i.test(value))) {
    throw new Error(`${name} must be a local filesystem path.`);
  }
  return value;
}

async function probe(file) {
  const info = JSON.parse(await run(mediaBinary('ffprobe'), [
    '-v', 'error', '-protocol_whitelist', 'file,pipe', '-select_streams', 'a:0',
    '-show_streams', '-show_format', '-of', 'json', file,
  ]));
  const audio = info.streams?.[0];
  const duration = Number(audio?.duration ?? info.format?.duration);
  if (!audio || audio.codec_type !== 'audio' || !Number.isFinite(duration) || duration <= 0
      || !Number.isFinite(Number(audio.sample_rate)) || Number(audio.sample_rate) <= 0
      || !Number.isInteger(audio.channels) || audio.channels < 1) {
    throw new Error(`No usable local audio in ${path.basename(file)}.`);
  }
  return { duration, sample_rate: Number(audio.sample_rate), channels: audio.channels,
    codec: audio.codec_name, samples: Number(audio.duration_ts), time_base: audio.time_base };
}

/**
 * Read version 1: each required asset has { file, gain, provenance, license }.
 * Typewriter may instead use files: [relative local paths] for discrete clacks.
 * Optional comedy is a map of named assets with the same single-file contract.
 * Asset files are relative to the manifest; provenance/license are documentation,
 * not a claim that this helper has independently verified reuse rights.
 */
export async function loadSfxManifest(manifestPath) {
  const resolved = path.resolve(localPath(manifestPath, 'manifestPath'));
  const document = JSON.parse(await fs.readFile(resolved, 'utf8'));
  if (!document || document.version !== 1 || Array.isArray(document)) throw new Error('Unknown SFX manifest version.');
  const manifest = { version: 1, manifest_path: resolved };
  async function loadAsset(name, asset, multipleAllowed = false) {
    if (!asset || typeof asset !== 'object' || Array.isArray(asset)) throw new Error(`SFX manifest requires ${name}.`);
    if (typeof asset.gain !== 'number' || !Number.isFinite(asset.gain) || asset.gain < 0 || asset.gain > 1) {
      throw new Error(`${name}.gain must be between 0 and 1.`);
    }
    for (const field of ['provenance', 'license']) {
      if (typeof asset[field] !== 'string' || !asset[field].trim()) throw new Error(`${name}.${field} is required.`);
    }
    const multiple = multipleAllowed && asset.files != null;
    if (multiple && (asset.file != null || !Array.isArray(asset.files) || !asset.files.length)) {
      throw new Error('typewriter needs either file or a nonempty files array.');
    }
    const variants = [];
    for (const entry of multiple ? asset.files : [asset.file]) {
      const relative = localPath(entry, `${name}.file`);
      if (path.isAbsolute(relative)) throw new Error(`${name}.file must be relative to the manifest.`);
      const file = await fs.realpath(path.resolve(path.dirname(resolved), relative));
      if (!(await fs.stat(file)).isFile()) throw new Error(`${name}.file must be a regular local file.`);
      variants.push(Object.freeze({ file, relative_file: relative, ...(await probe(file)) }));
    }
    return Object.freeze({ gain: asset.gain, provenance: asset.provenance, license: asset.license,
      ...(multiple ? { files: Object.freeze(variants.map(v => v.file)), variants: Object.freeze(variants) } : variants[0]) });
  }
  for (const name of assetNames) manifest[name] = await loadAsset(name, document[name], name === 'typewriter');
  const comedy = Object.create(null);
  if (document.comedy != null) {
    if (typeof document.comedy !== 'object' || Array.isArray(document.comedy)) throw new Error('comedy must be a named asset map.');
    for (const [name, asset] of Object.entries(document.comedy)) {
      if (!/^[a-z][a-z0-9_-]{0,40}$/.test(name)) throw new Error('Unknown comedy asset name.');
      comedy[name] = await loadAsset(`comedy.${name}`, asset);
    }
  }
  manifest.comedy = Object.freeze(comedy);
  Object.freeze(manifest);
  loadedManifests.add(manifest);
  return manifest;
}

/**
 * Return the absolute path of a PCM WAV matching this analysis hold.
 * One move OR rating accent starts at zero, never a redundant tick over an accent.
 * Typing starts with the bubble and ends with its text;
 * files variants ignore spaces and cap keypresses at 16/s; file alone loops.
 * Optional annotation.comedy_sfx is { name, at_seconds, gain? } or an array of
 * up to three cues. Only explicitly placed local assets can be used. They start
 * after the rating and finish before the reading hold, which stays silent.
 * The mix is limited to -2 dBFS. No dialogue
 * input can enter this mix. Durations round to the nearest 48 kHz sample.
 */
export async function renderAnalysisAudio({ manifest, annotation, schema, outputPath }) {
  if (!loadedManifests.has(manifest)) throw new Error('Use loadSfxManifest before rendering analysis audio.');
  if (!annotation || !Number.isFinite(annotation.hold_seconds) || annotation.hold_seconds <= 0
      || typeof annotation.comment !== 'string' || !annotation.comment.trim()) {
    throw new Error('Supply a positive analysis hold and a nonempty comment.');
  }
  if (!schema || !Number.isFinite(schema.typewriter_cps) || schema.typewriter_cps <= 0
      || !Number.isFinite(schema.bubble_delay_seconds) || schema.bubble_delay_seconds < 0
      || !Array.isArray(schema.categories) || !schema.categories.some(v => v.id === annotation.rating)) {
    throw new Error('Supply the shared rating schema and a known annotation rating.');
  }
  const samples = Math.round(annotation.hold_seconds * sampleRate);
  if (!Number.isSafeInteger(samples) || samples < 1) throw new Error('Analysis hold exceeds the supported sample range.');
  const typingStart = Math.round(schema.bubble_delay_seconds * sampleRate);
  const typingSamples = Math.round(annotation.comment.length / schema.typewriter_cps * sampleRate);
  if (typingStart + typingSamples > samples) throw new Error('Analysis hold ends before its text finishes typing.');
  const comedyCues = annotation.comedy_sfx == null ? []
    : Array.isArray(annotation.comedy_sfx) ? annotation.comedy_sfx : [annotation.comedy_sfx];
  if (comedyCues.length > 3) throw new Error('Use at most three explicitly placed comedy cues per hold.');
  const comedyEvents = comedyCues.map(cue => {
    if (!cue || typeof cue !== 'object' || Array.isArray(cue) || typeof cue.name !== 'string'
        || !Object.hasOwn(manifest.comedy, cue.name)) throw new Error('Unknown local comedy sound.');
    if (!Number.isFinite(cue.at_seconds) || cue.at_seconds < .5) {
      throw new Error('Place comedy cues at least half a second after the rating onset.');
    }
    const gain = cue.gain ?? 1;
    if (!Number.isFinite(gain) || gain < 0 || gain > 1) throw new Error('Comedy gain must be between 0 and 1.');
    const asset = manifest.comedy[cue.name];
    const start = Math.round(cue.at_seconds * sampleRate), length = Math.round(asset.duration * sampleRate);
    if (start + length > typingStart + typingSamples) throw new Error('Comedy cues must finish before the silent reading hold.');
    return { asset, start, length, gain };
  });
  const result = path.resolve(localPath(outputPath, 'outputPath'));
  if (path.extname(result).toLowerCase() !== '.wav') throw new Error('outputPath must name a WAV file.');
  await fs.mkdir(path.dirname(result), { recursive: true });
  const directory = await fs.realpath(path.dirname(result));
  const destination = path.join(directory, path.basename(result));
  if ([...assetNames.map(name => manifest[name]), ...Object.values(manifest.comedy)]
    .some(asset => asset.file === destination || asset.files?.includes(destination))) {
    throw new Error('Do not overwrite a source sound asset.');
  }
  const temporary = path.join(directory, `.${path.basename(result)}.${randomUUID()}.tmp`);
  const inputs = [], filters = [`anullsrc=r=${sampleRate}:cl=stereo,atrim=end_sample=${samples}[bed]`];
  let inputCount = 0;
  const mix = ['[bed]'];
  function input(file, loop = false) {
    inputs.push('-protocol_whitelist', 'file,pipe', ...(loop ? ['-stream_loop', '-1'] : []), '-i', file);
    return inputCount++;
  }
  function effect(name, start, length, loop = false, asset = manifest[name], gain = 1) {
    if (asset.gain * gain === 0 || length < 1) return;
    const index = input(asset.file, loop);
    const seconds = length / sampleRate;
    const fadeIn = Math.min(.004, seconds / 3), fadeOut = Math.min(.008, seconds / 3);
    filters.push(`[${index}:a:0]aresample=${sampleRate},aformat=sample_fmts=fltp:channel_layouts=stereo,`
      + `atrim=end_sample=${length},asetpts=PTS-STARTPTS,volume=${asset.gain * gain},`
      + `afade=t=in:st=0:d=${fadeIn},afade=t=out:st=${seconds - fadeOut}:d=${fadeOut},`
      + `adelay=delays=${start}S:all=1[${name}]`);
    mix.push(`[${name}]`);
  }
  const accent = annotation.rating === 'brilliant' ? 'brilliant' : annotation.rating === 'blunder' ? 'blunder'
    : ['mistake', 'inaccuracy'].includes(annotation.rating) ? 'error' : null;
  const ratingCue = accent || 'move';
  effect(ratingCue, 0, Math.min(samples, Math.round(Math.min(accent ? .8 : .35, manifest[ratingCue].duration) * sampleRate)));
  comedyEvents.forEach((event, i) => effect(`comedy${i}`, event.start, event.length, false, event.asset, event.gain));
  if (!manifest.typewriter.files) {
    effect('typewriter', typingStart, typingSamples, true);
  } else if (manifest.typewriter.gain > 0) {
    const events = [], typingEnd = typingStart + typingSamples;
    let lastStart = -Infinity;
    for (let i = 0; i < annotation.comment.length; i++) {
      if (/\s/.test(annotation.comment[i])) continue;
      // A keypress starts the glyph's interval; the canvas completes it one cps
      // tick later. This keeps even the final keystroke inside the typing window.
      const start = typingStart + Math.round(i / schema.typewriter_cps * sampleRate);
      if (start - lastStart < sampleRate / 16) continue;
      const variant = events.length % manifest.typewriter.variants.length;
      const length = Math.min(typingEnd - start, Math.round(manifest.typewriter.variants[variant].duration * sampleRate));
      if (length < 1) continue;
      events.push({ start, length, variant });
      lastStart = start;
    }
    for (let variant = 0; variant < manifest.typewriter.variants.length; variant++) {
      const selected = events.map((event, i) => ({ ...event, i })).filter(event => event.variant === variant);
      if (!selected.length) continue;
      const index = input(manifest.typewriter.variants[variant].file);
      filters.push(`[${index}:a:0]aresample=${sampleRate},aformat=sample_fmts=fltp:channel_layouts=stereo,`
        + `asetpts=PTS-STARTPTS,asplit=${selected.length}${selected.map(event => `[clacksrc${event.i}]`).join('')}`);
      for (const event of selected) {
        const seconds = event.length / sampleRate, fadeIn = Math.min(.002, seconds / 3), fadeOut = Math.min(.004, seconds / 3);
        filters.push(`[clacksrc${event.i}]atrim=end_sample=${event.length},asetpts=PTS-STARTPTS,volume=${manifest.typewriter.gain},`
          + `afade=t=in:st=0:d=${fadeIn},afade=t=out:st=${seconds - fadeOut}:d=${fadeOut},`
          + `adelay=delays=${event.start}S:all=1[clack${event.i}]`);
        mix.push(`[clack${event.i}]`);
      }
    }
  }
  filters.push(`${mix.join('')}amix=inputs=${mix.length}:duration=longest:dropout_transition=0:normalize=0,`
    + `alimiter=limit=0.7943282347242815:level=false:attack=1:release=50:latency=true,`
    + `apad=whole_len=${samples},atrim=end_sample=${samples},asetpts=PTS-STARTPTS[out]`);
  try {
    await run(mediaBinary('ffmpeg'), ['-hide_banner', '-loglevel', 'error', '-nostdin', '-y', ...inputs,
      '-filter_complex', filters.join(';'), '-map', '[out]', '-c:a', 'pcm_s16le',
      '-ar', String(sampleRate), '-ac', '2', '-f', 'wav', temporary]);
    const audio = await probe(temporary);
    if (audio.codec !== 'pcm_s16le' || audio.sample_rate !== sampleRate || audio.channels !== 2
        || audio.time_base !== `1/${sampleRate}` || audio.samples !== samples) {
      throw new Error('SFX render did not produce the exact stereo analysis hold.');
    }
    await fs.rename(temporary, destination);
    return result;
  } finally {
    await fs.rm(temporary, { force: true });
  }
}
