import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { mediaBinary } from './runtime.mjs';
import { loadSfxManifest } from './sfx.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
test('original Chess.com SVG bytes survive a Windows checkout', async () => {
  const ratings = JSON.parse(await fs.readFile(path.join(here, 'ratings.json')));
  for (const rating of ratings.categories) {
    const bytes = await fs.readFile(path.join(here, rating.icon_file));
    assert.equal(createHash('sha256').update(bytes).digest('hex'), rating.icon_sha256, rating.id);
  }
});
test('SFX accepts the absolute local path, including Windows drive and spaces', async () => {
  const result = await loadSfxManifest(path.join(here, 'assets/sfx/manifest.json'));
  assert.equal(result.typewriter.variants.length, 8);
  assert.ok(result.typewriter.variants.every(v => v.duration > 0));
});
test('quality and opening gates remain enforced before rendering', async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'chess regression spaces '));
  try {
    const source = path.join(temp, 'fixture.mp4');
    const make = spawnSync(mediaBinary('ffmpeg'), ['-v','error','-y','-f','lavfi','-i','color=c=blue:s=320x180:r=30',
      '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','1','-c:v','libx264','-c:a','aac',source], {encoding:'utf8'});
    assert.equal(make.status, 0, make.stderr);
    const timeline = path.join(temp, 'timeline.json');
    const spec = {schema:'conversation-chess-clip-v1', demo:false, source_reviewed:true,
      source_quality:{quality_target:1080, accepted_for_final:false}, source_in:0, source_out:1,
      intro_seconds:16, initial_score_text:'0.0', initial_control:.5, black_label:'Second', white_label:'First',
      opening:{speaker:'white',label:'First',reviewed:true}, annotations:[]};
    await fs.writeFile(timeline, JSON.stringify(spec));
    const args = [path.join(here,'render-clip.mjs'),'--source',source,'--timeline',timeline,'--out',path.join(temp,'out')];
    const check = spawnSync(process.execPath, [...args,'--validate-only'], {encoding:'utf8'});
    assert.equal(check.status, 0, check.stderr);
    assert.equal(JSON.parse(check.stdout).source_quality_accepted, false);
    const final = spawnSync(process.execPath, [...args,'--prepare-project'], {encoding:'utf8'});
    assert.notEqual(final.status, 0);
    assert.match(final.stderr, /Source quality is not accepted/);
    delete spec.opening;
    await fs.writeFile(timeline, JSON.stringify(spec));
    const missing = spawnSync(process.execPath, [...args,'--validate-only'], {encoding:'utf8'});
    assert.notEqual(missing.status, 0);
    assert.match(missing.stderr, /Real footage requires opening/);
  } finally { await fs.rm(temp, {recursive:true,force:true}); }
});
