#!/usr/bin/env node
// Prepare editable portrait media; the final export stays in native Kdenlive.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {loadChromium,browserOptions,mediaBinary} from './runtime.mjs';
import {loadSfxManifest,renderAnalysisAudio} from './sfx.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
const args=process.argv.slice(2);
function opt(key){const i=args.indexOf(key);if(i<0||!args[i+1])throw new Error('Required '+key);return path.resolve(args[i+1]);}
function run(bin,args,capture=false){const r=spawnSync(bin,args,{encoding:'utf8',stdio:capture?'pipe':'inherit',maxBuffer:5e6});if(r.error)throw r.error;if(r.status)throw new Error(String(r.stderr||bin+' failed').slice(-1500));return r.stdout;}
const source=opt('--source'),timeline=opt('--timeline'),out=opt('--out');
const spec=JSON.parse(await fs.readFile(timeline,'utf8'));
const schema=JSON.parse(await fs.readFile(path.join(here,'ratings.json'),'utf8'));
const ffmpeg=mediaBinary('ffmpeg'),ffprobe=mediaBinary('ffprobe');
const meta=JSON.parse(run(ffprobe,['-v','error','-show_streams','-show_format','-of','json',source],true));
const video=meta.streams.find(s=>s.codec_type==='video');
const sha=createHash('sha256').update(await fs.readFile(source)).digest('hex');
if(spec.schema!=='conversation-chess-short-v1'||spec.source_sha256!==sha||spec.source_reviewed!==true)throw new Error('Supply the exact visually reviewed source and short timeline');
if(video.height<1080||spec.source_quality?.accepted_for_final!==true||!meta.streams.some(s=>s.codec_type==='audio'))throw new Error('Shorts need a reviewed HD source with original audio');
if(spec.opening?.speaker!=='white'||spec.opening.label!==spec.sides.white||spec.opening.reviewed!==true)throw new Error('Review the White-first opening');
if(!Array.isArray(spec.segments)||!spec.segments.length)throw new Error('Empty short timeline');
let score=0,lastSource=null;
for(const s of spec.segments){
  if(!['source','analysis','outro'].includes(s.kind))throw new Error('Unknown short segment');
  if(s.kind==='source'){
    if(!Number.isFinite(s.in)||!Number.isFinite(s.out)||s.in<0||s.out<=s.in||s.out>Number(meta.format.duration)||!s.boundary_review)throw new Error('Review source cuts and dialogue boundaries');
    if(s.mode!=='wide'&&(!Number.isFinite(s.center_x)||s.center_x<489||s.center_x>video.width-489))throw new Error('Portrait crop exceeds source frame');
    lastSource=s;
  }else{
    if(!lastSource||!Number.isInteger(s.seconds*30)||s.seconds<=0)throw new Error('Review frame-aligned hold after source footage');
    if(s.frame_source && (s.frame_source.reviewed!==true||!Number.isFinite(s.frame_source.at)||s.frame_source.at<0||s.frame_source.at>=Number(meta.format.duration)||!Number.isFinite(s.frame_source.center_x)||s.frame_source.center_x<489||s.frame_source.center_x>video.width-489))throw new Error('Review the explicit analysis/outro source frame and crop');
    if(s.kind==='analysis'){
      const a=s.analysis,r=schema.categories.find(r=>r.id===a.rating);
      if(!r||!['white','black'].includes(a.speaker)||!a.reviewed||a.comment.length>130||s.seconds<schema.bubble_delay_seconds+a.comment.length/schema.typewriter_cps+schema.minimum_reading_seconds)throw new Error('Analysis needs enough reading time and reviewed rating');
      const delta=(a.score-score)*(a.speaker==='white'?1:-1);
      if((['gain','small_gain'].includes(r.bar_effect)&&delta<0)||(['loss','small_loss'].includes(r.bar_effect)&&delta>0)||(r.bar_effect==='neutral'&&delta!==0))throw new Error('Score contradicts camp/rating');
      if(a.rating==='blunder'&&delta>0)throw new Error('Blunder cannot improve that player');
      score=a.score;
    }
  }
}
await fs.mkdir(out,{recursive:true});
const urls={};
for(const r of schema.categories){const b=await fs.readFile(path.join(here,r.icon_file));if(createHash('sha256').update(b).digest('hex')!==r.icon_sha256)throw new Error('Official icon hash changed');urls[r.id]='data:image/svg+xml;base64,'+b.toString('base64');}
const browser=await loadChromium().launch(browserOptions());
try{
 const page=await browser.newPage({viewport:{width:1080,height:1920}});
 await page.setContent('<canvas></canvas>');await page.evaluate(s=>window.ConversationRatingSchema=s,schema);
 await page.addScriptTag({path:path.join(here,'short-scene.js')});await page.evaluate(u=>window.ChessShort.init(u),urls);
 const sfx=await loadSfxManifest(path.join(here,'assets/sfx/manifest.json'));
 const rows=[];let cursor=0,currentScore=0,previous=null;
 for(const [i,s] of spec.segments.entries()){
  const seconds=s.kind==='source'?Math.round((s.out-s.in)*30)/30:s.seconds;
  const frames=Math.round(seconds*30),stem=path.join(out,String(i+1).padStart(2,'0'));
  const background=stem+'-background.mp4',graphics=stem+(s.kind==='source'?'-graphics.png':'-graphics.mov');
  const origin=s.kind==='source'?s:s.frame_source?{...s.frame_source,out:s.frame_source.at+.10}:previous;
  const cropWidth=Math.floor(video.height*940/1040/2)*2;
  // A reviewed central wide rectangle retains both actors in the action shots.
  const filter=origin.mode==='wide'?`crop=1728:972:96:0,scale=940:528,pad=1080:1920:68:648:color=0x151311`:
   `crop=${cropWidth}:${video.height}:${Math.round(origin.center_x-cropWidth/2)}:0,scale=940:1040,pad=1080:1920:68:392:color=0x151311`;
  const fade=s.kind==='outro'?`,fade=t=out:st=${seconds-.4}:d=0.4`:'';
  if(s.kind==='source')run(ffmpeg,['-v','error','-y','-ss',String(s.in),'-i',source,'-vf',filter+',setsar=1','-r','30','-frames:v',String(frames),'-an','-c:v','libx264','-crf','17','-preset','fast',background]);
  else {
   const still=stem+'-freeze.png';run(ffmpeg,['-v','error','-y','-ss',String(origin.out-.10),'-i',source,'-vf',filter+',setsar=1','-frames:v','1',still]);
   run(ffmpeg,['-v','error','-y','-loop','1','-framerate','30','-i',still,'-vf','eq=brightness=-.05'+fade,'-frames:v',String(frames),'-an','-c:v','libx264','-pix_fmt','yuv420p','-crf','17','-preset','fast',background]);
  }
  const before=currentScore;if(s.kind==='analysis')currentScore=s.analysis.score;
  const o={...s,series:spec.series,hook:spec.hook,sides:spec.sides,recap:spec.recap,score:currentScore,previous_score:before,seconds};
  const imageCount=s.kind==='source'?1:frames;
  const dir=stem+'-frames';if(imageCount>1)await fs.mkdir(dir,{recursive:true});
  for(let f=0;f<imageCount;f++){
   const data=await page.evaluate(o=>window.ChessShort.frame(o),{...o,time:f/30});
   await fs.writeFile(imageCount===1?graphics:path.join(dir,`${String(f).padStart(5,'0')}.png`),Buffer.from(data.split(',')[1],'base64'));
  }
  if(imageCount>1)run(ffmpeg,['-v','error','-y','-framerate','30','-i',path.join(dir,'%05d.png'),'-frames:v',String(frames),'-c:v','qtrle','-pix_fmt','argb',graphics]);
  const row={kind:s.kind,start_frame:cursor,end_frame:cursor+frames,duration_frames:frames,background_file:background,graphics_file:graphics};
  if(s.kind==='source'){
   const audio=stem+'-dialogue.wav';
   run(ffmpeg,['-v','error','-y','-ss',String(s.in),'-i',source,'-af',`apad,atrim=end_sample=${frames*1600},afade=t=in:d=0.006,afade=t=out:st=${seconds-.012}:d=0.012`,'-ar','48000','-ac','2','-c:a','pcm_s16le',audio]);
   row.dialogue_audio_file=audio;row.source_in=s.in;row.source_out=s.out;previous=s;
  }else if(s.kind==='analysis'){
   row.sfx_file=stem+'-sfx.wav';await renderAnalysisAudio({manifest:sfx,annotation:{...s.analysis,hold_seconds:seconds},schema,outputPath:row.sfx_file});
   row.speaker=s.analysis.speaker;row.rating=s.analysis.rating;row.comment=s.analysis.comment;
  }
  rows.push(row);cursor+=frames;console.log(`${i+1}/${spec.segments.length} ${s.kind} ${frames} frames`);
 }
 const manifest={schema:'conversation-chess-kdenlive-interchange-v1',title:spec.title,fps:30,width:1080,height:1920,duration_frames:cursor,original_source:source,source_sha256:sha,source_quality:{...spec.source_quality,minimum_height:1080,visually_reviewed:true},rating_schema_version:4,voiceover:false,demo:false,side_colors:spec.sides,opening:spec.opening,outro_layout_reviewed:true,segments:rows,published:false};
 await fs.writeFile(path.join(out,'project-manifest.json'),JSON.stringify(manifest,null,2)+'\n');
 await fs.copyFile(timeline,path.join(out,'authored-timeline.json'));
 console.log(`Prepared ${(cursor/30).toFixed(2)}s portrait project`);
}finally{await browser.close();}
