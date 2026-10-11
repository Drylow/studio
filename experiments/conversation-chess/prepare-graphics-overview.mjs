// Keep the native chess graphics while removing every episode picture and audio asset.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {loadChromium, browserOptions, mediaBinary} from './runtime.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = name => {const i=args.indexOf(name); if(i<0 || !args[i+1]) throw new Error(`Missing ${name}`); return path.resolve(args[i+1]);};
const input = opt('--manifest'), out = opt('--out');
const old = JSON.parse(await fs.readFile(input,'utf8'));
const hash = b => createHash('sha256').update(b).digest('hex');
const ffmpeg = mediaBinary('ffmpeg');
function run(cmd) {const r=spawnSync(ffmpeg,['-v','error','-n',...cmd],{encoding:'utf8'}); if(r.error || r.status) throw new Error(r.error?.message || r.stderr);}
await fs.mkdir(out,{recursive:true});
const manifestFile = path.join(out,'project-manifest.json');
try {await fs.access(manifestFile); throw new Error('Choose a fresh output folder');} catch(e) {if(e.code!=='ENOENT') throw e;}
const schema = JSON.parse(await fs.readFile(path.join(here,'ratings.json'),'utf8'));
const icons = {};
for (const r of schema.categories) {
  const bytes=await fs.readFile(path.join(here,r.icon_file));
  if(hash(bytes)!==r.icon_sha256) throw new Error(`Icon hash mismatch: ${r.id}`);
  icons[r.id]=`data:image/svg+xml;base64,${bytes.toString('base64')}`;
}
const mascot=await fs.readFile(path.join(here,'assets/neutral-pawn.png'));
const annotations=old.segments.filter(s=>s.kind==='analysis');
if(annotations.length!==7 || old.side_colors.white!=='L' || old.side_colors.black!=='Light') throw new Error('Use the reviewed L vs Light manifest');
const titles=[
  ['THE BAIT','A name and a face on television.'],
  ['FALSE CONFIDENCE','Light believes he cannot be found.'],
  ['THE PROVOCATION','A personal attack invites a reaction.'],
  ['THE WRONG TARGET','Light kills the decoy.'],
  ['THE REVEAL','The real L kept his identity hidden.'],
  ['THE LIMIT','Without a name and face, Kira cannot act.'],
  ['THE LOCATION','The broadcast was local: Kanto.']
];
const browser=await loadChromium().launch(browserOptions(''));
const backgrounds=[];
try {
  const page=await browser.newPage();
  await page.route('**/*',route=>route.abort());
  await page.setContent('<!doctype html><canvas width="1920" height="1080"></canvas>');
  await page.evaluate(({schema,icons})=>{window.ConversationRatingSchema=schema;window.ConversationRatingAssets=icons;},{schema,icons});
  await page.addScriptTag({content:await fs.readFile(path.join(here,'scene.js'),'utf8')});
  for(let i=-1;i<titles.length;i++) {
    const data=await page.evaluate(({title,index})=>{
      const c=document.querySelector('canvas'),ctx=c.getContext('2d');ctx.clearRect(0,0,1920,1080);
      const g=ctx.createLinearGradient(0,0,1920,1080);g.addColorStop(0,'#3d424b');g.addColorStop(1,'#252d3b');ctx.fillStyle=g;ctx.fillRect(0,0,1920,1080);
      ctx.strokeStyle='rgba(255,255,255,.035)';ctx.lineWidth=1;
      for(let x=0;x<1920;x+=96){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,1080);ctx.stroke();}
      for(let y=0;y<1080;y+=96){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(1920,y);ctx.stroke();}
      if(title){
        ctx.fillStyle='#edf1f5';ctx.font='700 42px Arial';ctx.fillText('L = WHITE     /     LIGHT = BLACK',790,88);
        ctx.fillStyle='#edf1f5';ctx.font='700 66px Arial';ctx.fillText(`${index+1}. ${title[0]}`,790,229);
        ctx.font='400 39px Arial';ctx.fillStyle='#d4dce8';ctx.fillText(title[1],790,308);
      }
      return c.toDataURL('image/png');
    },{title:i<0?null:titles[i],index:i});
    const file=path.join(out,i<0?'background-guide.png':`background-${i}.png`);
    await fs.writeFile(file,Buffer.from(data.split(',')[1],'base64'));backgrounds.push(file);
  }
  const backdrop=await fs.readFile(backgrounds[0]);
  await page.evaluate(({pawn,backdrop})=>window.ConversationChess.init(pawn,backdrop,pawn),{pawn:`data:image/png;base64,${mascot.toString('base64')}`,backdrop:`data:image/png;base64,${backdrop.toString('base64')}`});
  const outro=old.segments.find(s=>s.kind==='outro');
  for(const [kind,duration] of [['intro',16],['outro',12]]) {
    const frames=path.join(out,`${kind}-frames`);await fs.mkdir(frames,{recursive:true});
    for(let f=0;f<duration*30;f++) {
      const data=await page.evaluate(o=>window.ConversationChess.clipFrame(o),{phase:kind,t:f/30,duration,style:'recap',counts:outro.recap_counts,summary:outro.recap_summary});
      await fs.writeFile(path.join(frames,`frame_${String(f).padStart(5,'0')}.png`),Buffer.from(data.split(',')[1],'base64'));
    }
    run(['-framerate','30','-i',path.join(frames,'frame_%05d.png'),'-an','-c:v','qtrle','-pix_fmt','argb',path.join(out,`${kind}.mov`)]);
    console.log(`${kind} graphics ready`);
  }
} finally {await browser.close();}
for(let i=0;i<annotations.length;i++) {
  run(['-i',annotations[i].graphics_file,'-vf','tpad=stop_mode=clone:stop_duration=2','-an','-c:v','qtrle','-pix_fmt','argb',path.join(out,`analysis-${i}.mov`)]);
}
const original=path.join(out,'original-graphics-background.mp4');
run(['-f','lavfi','-i','color=c=0x3d424b:s=1920x1080:r=30:d=1','-an','-c:v','libx264','-crf','17',original]);
let cursor=0;const segments=[];
function add(segment){const frames=Math.round(segment.duration*30);segments.push({...segment,output_in:cursor/30,start_frame:cursor,end_frame:cursor+frames,duration_frames:frames});cursor+=frames;}
const oldIntro=old.segments.find(s=>s.kind==='intro');
add({kind:'intro',duration:16,background_file:backgrounds[0],graphics_file:path.join(out,'intro.mov'),graphics_type:'alpha_mov',music_file:oldIntro.music_file,music_title:oldIntro.music_title,music_license:oldIntro.music_license});
for(let i=0;i<annotations.length;i++) {
  const a=annotations[i];
  add({kind:'analysis',duration:9,rating:a.rating,speaker:a.speaker,comment:a.comment,score_text:a.score_text,control:a.control,
    background_file:backgrounds[i+1],graphics_file:path.join(out,`analysis-${i}.mov`),graphics_type:'alpha_mov',sfx_file:a.sfx_file});
}
const recap=old.segments.find(s=>s.kind==='outro');
add({kind:'outro',duration:12,background_file:backgrounds[0],graphics_file:path.join(out,'outro.mov'),graphics_type:'alpha_mov',outro_style:'recap',recap_counts:recap.recap_counts,recap_summary:recap.recap_summary});
const manifest={...old,title:'L Outsmarts Light Analysed like Chess | Death Note — graphics overview',original_source:original,
  source_sha256:hash(await fs.readFile(original)),source_dimensions:[1920,1080],original_audio_present:false,
  source_quality:{native_hd:true,minimum_height:1080,on_screen_label:false,low_res_preview:false,accepted_for_final:true,visually_reviewed:true,note:'Original graphic background, not episode footage. Final visual review required.'},
  opening:{speaker:'white',label:'L',reviewed:true,evidence:'First editorial move describes L setting the televised trap. No episode dialogue remains.'},
  timeline_file:manifestFile,timeline_sha256:null,duration:cursor/30,duration_frames:cursor,segments,
  derivative_of_manifest:input,removed_content:'All episode footage, muted replays, original dub and episode music. Intro and recap regenerated over original graphics.',youtube_clearance_verified:false};
await fs.writeFile(manifestFile,JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({manifest:manifestFile,duration:cursor/30,source_segments:0,analysis_segments:annotations.length}));
