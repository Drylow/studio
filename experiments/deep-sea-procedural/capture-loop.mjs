import http from 'node:http';
import { readFile, writeFile, mkdir, stat, rename, rm } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
import { chromium } from 'playwright';

const here=path.dirname(fileURLToPath(import.meta.url)), args=process.argv.slice(2);
const arg=(name,fallback)=>{const i=args.indexOf(name);return i<0?fallback:args[i+1];};
const out=path.resolve(arg('--out',path.join(here,'renders/sleep-5m.mp4')));
const dist=path.resolve(here,arg('--dist','dist-sleep'));
const sound=arg('--audio',null), resume=args.includes('--resume');
const fps=30,duration=300,chunkSeconds=10,chunkFrames=fps*chunkSeconds,frames=fps*duration;
const ffmpeg=process.env.DEEPSEA_FFMPEG||'ffmpeg';
const work=out+'.chunks',lock=out+'.render-lock';
const hash=async file=>{const value=createHash('sha256');for await(const buffer of createReadStream(file))value.update(buffer);return value.digest('hex');};
async function exists(file){try{await stat(file);return true;}catch(error){if(error.code==='ENOENT')return false;throw error;}}
async function command(binary,argv,options={}){
  const process=spawn(binary,argv,{stdio:['ignore','pipe','pipe'],...options});let stdout='',stderr='';
  process.stdout.on('data',b=>{stdout+=b;});process.stderr.on('data',b=>{stderr+=b;});
  await new Promise((resolve,reject)=>{process.once('error',reject);process.once('close',code=>code===0?resolve():reject(new Error(stderr.slice(-2000)||`${binary} exited ${code}`)));});
  return stdout;
}
await mkdir(path.dirname(out),{recursive:true});
if(await exists(out))throw new Error('Existing delivery preserved. Choose another --out.');
try{await mkdir(lock);}catch(error){if(error.code==='EEXIST')throw new Error('Render locked. Confirm the old process stopped before removing its lock.');throw error;}
let browser,encoder,server,encoderError;
const errors=[];const started=Date.now();
try{
  const identity={version:1,width:1920,height:1080,fps,duration,chunkSeconds,crf:17,
    scene_sha256:await hash(path.join(dist,'scene.js')),page_sha256:await hash(path.join(dist,'index.html')),
    capture_sha256:await hash(fileURLToPath(import.meta.url)),audio_sha256:sound?await hash(path.resolve(sound)):null};
  if(sound){
    const probe=JSON.parse(await command('ffprobe',['-v','error','-show_format','-of','json',path.resolve(sound)]));
    if(Math.abs(Number(probe.format.duration)-duration)>.001)throw new Error('Ambient master must be exactly300 seconds.');
  }
  const manifestFile=path.join(work,'manifest.json');let manifest;
  if(await exists(manifestFile)){
    if(!resume)throw new Error('Checkpoints exist. Use --resume or choose another output.');
    manifest=JSON.parse(await readFile(manifestFile,'utf8'));
    if(JSON.stringify(manifest.identity)!==JSON.stringify(identity))throw new Error('Checkpoint settings/source changed; choose a new output to avoid mixing versions.');
  }else{
    await mkdir(work,{recursive:true});manifest={identity,chunks:[]};await writeFile(manifestFile,JSON.stringify(manifest,null,2));
  }
  server=http.createServer(async(req,res)=>{
    const pathname=new URL(req.url,'http://localhost').pathname;
    const file=pathname==='/'||pathname==='/index.html'?'index.html':pathname==='/scene.js'?'scene.js':null;
    if(!file){res.writeHead(404);res.end();return;}
    try{res.writeHead(200,{'Content-Type':file.endsWith('.js')?'application/javascript':'text/html; charset=utf-8'});res.end(await readFile(path.join(dist,file)));}
    catch{res.writeHead(500);res.end('Build the sleep loop first.');}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin=`http://127.0.0.1:${server.address().port}`;
  browser=await chromium.launch({executablePath:process.env.DEEPSEA_CHROMIUM||'/usr/bin/chromium',headless:true,
    args:['--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1});
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  await page.addInitScript(()=>{window.__CAPTURE_MODE__=true;});
  await page.goto(origin);await page.waitForFunction(()=>window.DeepSeaFilm,null,{timeout:120000});
  const sceneInfo=await page.evaluate(()=>({duration:DeepSeaFilm.duration,width:DeepSeaFilm.width,height:DeepSeaFilm.height,
    antialias:DeepSeaFilm.antialias,renderer:DeepSeaFilm.renderer,layout:DeepSeaFilm.layout}));
  if(sceneInfo.duration!==duration||sceneInfo.width!==1920||sceneInfo.height!==1080||!sceneInfo.antialias)throw new Error('Expected antialiased native1080p300-second scene.');
  console.log(JSON.stringify({stage:'initialized',scene:sceneInfo,checkpointed_chunks:manifest.chunks.length}));
  for(let chunk=0;chunk<duration/chunkSeconds;chunk++){
    const name=`chunk-${String(chunk).padStart(3,'0')}.mp4`,destination=path.join(work,name);
    const checkpoint=manifest.chunks.find(item=>item.index===chunk);
    if(checkpoint){
      if(!await exists(destination)||await hash(destination)!==checkpoint.sha256)throw new Error(`Invalid checkpoint ${name}.`);
      console.log(JSON.stringify({stage:'resumed',chunk:chunk+1,frame:(chunk+1)*chunkFrames,frames}));continue;
    }
    const temporary=destination+'.partial.mp4';encoderError=null;
    encoder=spawn(ffmpeg,['-hide_banner','-v','error','-y','-f','image2pipe','-framerate',String(fps),'-vcodec','mjpeg','-i','pipe:0',
      '-an','-frames:v',String(chunkFrames),'-vf','scale=in_range=full:out_range=limited:out_color_matrix=bt709',
      '-c:v','libx264','-preset','medium','-crf','17','-pix_fmt','yuv420p','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709',
      '-g','30','-keyint_min','30','-sc_threshold','0','-threads','2',temporary],{stdio:['pipe','ignore','pipe']});
    let stderr='';encoder.stderr.on('data',b=>{stderr+=b;});
    const finished=new Promise((resolve,reject)=>{encoder.once('error',reject);encoder.once('close',code=>code===0?resolve():reject(new Error(stderr.slice(-2000)||`Encoder exited ${code}`)));});
    finished.catch(error=>{encoderError=error;});encoder.stdin.on('error',error=>{encoderError=error;});
    for(let local=0;local<chunkFrames;local++){
      if(encoderError)throw encoderError;const frame=chunk*chunkFrames+local;
      const base64=await page.evaluate(t=>{DeepSeaFilm.render(t);return document.getElementById('film').toDataURL('image/jpeg',.97).split(',')[1];},frame/fps);
      if(errors.length)throw new Error(errors.join('; '));
      if(!encoder.stdin.write(Buffer.from(base64,'base64')))await once(encoder.stdin,'drain');
      if(frame%30===0||local===chunkFrames-1)console.log(JSON.stringify({stage:'capturing',frame:frame+1,frames,elapsed_seconds:Math.round((Date.now()-started)/1000)}));
    }
    encoder.stdin.end();await finished;encoder=null;
    const probe=JSON.parse(await command('ffprobe',['-v','error','-count_frames','-select_streams','v:0','-show_streams','-of','json',temporary]));
    const stream=probe.streams[0];
    if(Number(stream.nb_read_frames)!==chunkFrames||stream.width!==1920||stream.height!==1080||stream.avg_frame_rate!=='30/1')throw new Error('Checkpoint frame validation failed.');
    await rename(temporary,destination);
    manifest.chunks.push({index:chunk,file:name,frames:chunkFrames,sha256:await hash(destination),bytes:(await stat(destination)).size});
    await writeFile(manifestFile+'.tmp',JSON.stringify(manifest,null,2));await rename(manifestFile+'.tmp',manifestFile);
    console.log(JSON.stringify({stage:'checkpoint',chunk:chunk+1,chunks:30}));
  }
  await browser.close();browser=null;
  const list=manifest.chunks.sort((a,b)=>a.index-b.index).map(item=>`file '${item.file}'`).join('\n')+'\n';
  await writeFile(path.join(work,'concat.txt'),list);
  const temporary=out+'.partial.mp4';
  const mux=['-hide_banner','-v','error','-y','-f','concat','-safe','1','-i',path.join(work,'concat.txt')];
  if(sound)mux.push('-i',path.resolve(sound),'-map','0:v:0','-map','1:a:0','-c:a','aac','-b:a','192k','-ar','48000','-ac','2');
  else mux.push('-map','0:v:0','-an');
  mux.push('-c:v','copy','-t','300','-movflags','+faststart',temporary);
  await command(ffmpeg,mux);
  const final=JSON.parse(await command('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',temporary]));
  const video=final.streams.find(s=>s.codec_type==='video');
  if(Number(video.nb_read_frames)!==frames||Math.abs(Number(video.duration)-duration)>.001)throw new Error('Final frame count or duration changed.');
  await rename(temporary,out);
  const report={schema:'deep-sea-sleep-loop-render-v1',file:path.basename(out),width:1920,height:1080,fps,frames,duration_seconds:duration,
    bytes:(await stat(out)).size,sha256:await hash(out),elapsed_seconds:(Date.now()-started)/1000,
    scene:sceneInfo,checkpoint_chunks:30,source:identity,paid_generation_calls:0,external_images:0,
    browser_errors:errors,finished_visual_reviewed:false,full_av_decode_ok:false,
    ambient_audio:sound?'Original periodic underwater ambience, no music/samples/speech':'None'};
  await writeFile(out+'.render.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{
  if(encoder&&encoder.exitCode===null)encoder.kill('SIGTERM');
  if(browser)await browser.close();
  if(server)await new Promise(resolve=>server.close(resolve));
  await rm(lock,{recursive:true,force:true});
}
