import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { mediaBinary, loadChromium, browserOptions } from './runtime.mjs';
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
      show_source_quality_label:false,
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
test('analysis graphics identify the player and remove the optional preview label', async () => {
  const schema = JSON.parse(await fs.readFile(path.join(here, 'ratings.json')));
  const icons = Object.fromEntries(await Promise.all(schema.categories.map(async r =>
    [r.id, 'data:image/svg+xml;base64,' + (await fs.readFile(path.join(here, r.icon_file))).toString('base64')])));
  const browser = await loadChromium().launch(browserOptions(''));
  try {
    const page = await browser.newPage();
    await page.setContent('<canvas width="1920" height="1080"></canvas>');
    await page.evaluate(({schema,icons}) => {window.ConversationRatingSchema=schema;window.ConversationRatingAssets=icons;}, {schema,icons});
    await page.addScriptTag({content:await fs.readFile(path.join(here,'scene.js'),'utf8')});
    await page.evaluate(() => window.ConversationChess.init(''));
    const samples = await page.evaluate(() => {
      const draw = speaker => {
        window.ConversationChess.clipFrame({evaluation:{rating:'best',comment:'A reviewed move.',speaker},analysis_pawn_by_speaker:true,reveal_seconds:7});
        return [...document.querySelector('canvas').getContext('2d').getImageData(417,623,1,1).data];
      };
      const white=draw('white'), black=draw('black');
      const labelPixels = show => {
        window.ConversationChess.clipFrame({low_res_preview:true,source_height:720,show_source_quality_label:show});
        const data=document.querySelector('canvas').getContext('2d').getImageData(900,0,970,55).data;
        let count=0;for(let i=3;i<data.length;i+=4) if(data[i]) count++;
        return count;
      };
      return {white,black,shown:labelPixels(true),hidden:labelPixels(false)};
    });
    assert.deepEqual(samples.white,[255,255,255,255]);
    assert.deepEqual(samples.black,[64,60,56,255]);
    assert.ok(samples.shown>0);
    assert.equal(samples.hidden,0);
  } finally {await browser.close();}
});
