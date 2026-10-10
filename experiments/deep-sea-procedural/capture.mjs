import http from 'node:http';
import { readFile, writeFile, mkdir, stat, rename, rm } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
import { chromium } from 'playwright';

const here=path.dirname(fileURLToPath(import.meta.url));
const args=process.argv.slice(2);
function arg(name,fallback){const i=args.indexOf(name);return i<0?fallback:args[i+1];}
const distribution=path.resolve(here,arg('--dist','dist'));
const out=path.resolve(arg('--out',path.join(here,'renders/preview.mp4')));
const stills=arg('--stills','');
const fps=Number(arg('--fps','30')), duration=Number(arg('--duration','24'));
if(!Number.isInteger(fps)||fps<1||fps>60||!Number.isFinite(duration)||duration<=0||duration>30)throw new Error('This prototype supports 0–30 seconds and 1–60 fps.');
const executablePath=process.env.DEEPSEA_CHROMIUM || '/usr/bin/chromium';
let lock;
if(!stills){
  await mkdir(path.dirname(out),{recursive:true});
  lock=out+'.render-lock';
  try{await mkdir(lock);}catch(error){if(error.code==='EEXIST')throw new Error('This output has an active or interrupted render lock. Choose a new --out filename.');throw error;}
}
const files=new Map([
  ['/',['index.html','text/html; charset=utf-8']],
  ['/index.html',['index.html','text/html; charset=utf-8']],
  ['/scene.js',['scene.js','application/javascript']],
  ['/creatures.js',['creatures.js','application/javascript']],
]);
const server=http.createServer(async(req,res)=>{
  const file=files.get(new URL(req.url,'http://localhost').pathname);
  if(!file){res.writeHead(404);res.end();return;}
  try{const bytes=await readFile(path.join(distribution,file[0]));res.writeHead(200,{'Content-Type':file[1]});res.end(bytes);}
  catch{res.writeHead(500);res.end('Build the prototype first.');}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin=`http://127.0.0.1:${server.address().port}`;
let browser,encoder;
const errors=[];
try{
  browser=await chromium.launch({executablePath,headless:true,args:['--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1});
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  await page.addInitScript(()=>{window.__CAPTURE_MODE__=true;});
  await page.goto(origin);await page.waitForFunction(()=>window.DeepSeaFilm);
  const sceneInfo=await page.evaluate(()=>({duration:window.DeepSeaFilm.duration,antialias:window.DeepSeaFilm.antialias,renderer:window.DeepSeaFilm.renderer,layout:window.DeepSeaFilm.layout}));
  const filmDuration=sceneInfo.duration;
  if(duration>filmDuration)throw new Error(`The current scene lasts ${filmDuration} seconds.`);
  async function grab(t,format='image/jpeg'){
    const result=await page.evaluate(({t,format})=>{
      const rendered=window.DeepSeaFilm.render(t);
      return {rendered,base64:document.getElementById('film').toDataURL(format,.97).split(',')[1]};
    },{t,format});
    if(errors.length)throw new Error(errors.join('; '));
    return {data:Buffer.from(result.base64,'base64'),rendered:result.rendered};
  }
  if(stills){
    const directory=path.resolve(arg('--stills-dir',path.dirname(out)));await mkdir(directory,{recursive:true});
    for(const t of stills.split(',').map(Number)){
      if(!Number.isFinite(t)||t<0||t>filmDuration)throw new Error('Invalid still time.');
      const frame=await grab(t,'image/png');
      await writeFile(path.join(directory,`frame-${t.toFixed(2)}.png`),frame.data);
      console.log(JSON.stringify({frame:t,...frame.rendered}));
    }
  }else{
    await mkdir(path.dirname(out),{recursive:true});
    try{await stat(out);throw new Error('Existing render is preserved; choose another --out filename.');}catch(error){if(error.code!=='ENOENT')throw error;}
    const temporary=out+'.partial.mp4';
    const sound=arg('--audio',null);
    const cmd=['-hide_banner','-v','error','-y','-f','image2pipe','-framerate',String(fps),'-vcodec','mjpeg','-i','pipe:0'];
    if(sound)cmd.push('-i',path.resolve(sound),'-map','0:v:0','-map','1:a:0','-c:a','aac','-b:a','192k','-ar','48000','-ac','2');
    else cmd.push('-an');
    const frames=Math.round(duration*fps);
    cmd.push('-frames:v',String(frames),'-t',String(frames/fps),'-c:v','libx264','-preset','medium','-crf','17','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',temporary);
    encoder=spawn(process.env.DEEPSEA_FFMPEG||'ffmpeg',cmd,{stdio:['pipe','ignore','pipe']});
    let stderr='';encoder.stderr.on('data',buffer=>{stderr+=buffer;});
    const finished=new Promise((resolve,reject)=>{encoder.once('error',reject);encoder.once('close',code=>code===0?resolve():reject(new Error(stderr.slice(-1500)||`Encoder exited ${code}`)));});
    // Observe asynchronous encoder errors while the browser is producing frames.
    let encoderError;finished.catch(error=>{encoderError=error;});
    encoder.stdin.on('error',error=>{encoderError=error;});
    const started=Date.now();let lastInfo;
    for(let i=0;i<frames;i++){
      if(encoderError)throw encoderError;
      const frame=await grab(i/fps);lastInfo=frame.rendered;
      if(!encoder.stdin.write(frame.data))await once(encoder.stdin,'drain');
      if(i%60===0||i===frames-1)console.log(JSON.stringify({frame:i+1,frames,elapsed_seconds:Math.round((Date.now()-started)/1000)}));
    }
    encoder.stdin.end();await finished;await rename(temporary,out);
    const bytes=await readFile(out);
    const report={schema:'deep-sea-procedural-render-v1',file:path.basename(out),width:1920,height:1080,fps,frames,duration_seconds:frames/fps,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex'),elapsed_seconds:(Date.now()-started)/1000,scene:sceneInfo,paid_generation_calls:0,external_images:0,browser_errors:errors,frame_info:lastInfo,finished_visual_reviewed:false,full_av_decode_ok:false,ambient_audio:sound?'Original procedurally synthesized ambience':'None; visual study'};
    await writeFile(out+'.render.json',JSON.stringify(report,null,2));
    console.log(JSON.stringify(report));
  }
}finally{
  if(encoder&&encoder.exitCode===null)encoder.kill('SIGTERM');
  if(browser)await browser.close();
  await new Promise(resolve=>server.close(resolve));
  if(lock)await rm(lock,{recursive:true});
}
