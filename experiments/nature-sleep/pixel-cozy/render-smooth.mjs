// Render continuous articulated motion at the full export resolution.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {once} from 'node:events';

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'../../..');
const require=createRequire(path.join(root,'frontend/package.json'));
const {chromium}=require('playwright');
const output=path.resolve(process.argv[2]||path.join(root,'output/nature-sleep/pixel-cozy-smooth-preview'));
const movie=path.join(output,'Quiet-Little-Worlds-Living-Cottage-24s.mp4');
const duration=24,fps=30,frames=duration*fps;
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
await fs.mkdir(path.join(output,'qa'),{recursive:true});
try{await fs.access(movie);throw new Error('Existing output preserved: choose a fresh directory.');}catch(error){if(error.code!=='ENOENT')throw error;}
const source=path.join(here,'assets/cottage-clean-background.png');
const sourceBytes=await fs.readFile(source);
const foliage=path.join(here,'assets/willow-foreground.png');
const foliageBytes=await fs.readFile(foliage);
let html=await fs.readFile(path.join(here,'smooth-scene.html'),'utf8');
html=html.replace('const CAPTURE_MODE=false;','const CAPTURE_MODE=true;');
html=html.replace('__PIXEL_SOURCE__',`data:image/png;base64,${sourceBytes.toString('base64')}`);
html=html.replace('__WILLOW_SOURCE__',`data:image/png;base64,${foliageBytes.toString('base64')}`);
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--disable-dev-shm-usage','--enable-unsafe-swiftshader']});
let encoder;
const started=Date.now();
try{
 const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>route.abort());
 await page.setContent(html,{waitUntil:'load'});
 if(errors.length)throw new Error(errors.join('; '));
 const geometry=await page.evaluate(()=>window.pixelReady);
 const endpoints=[];
 for(const time of [0,duration]){
  const data=await page.evaluate(t=>{window.renderPixelAt(t);return window.pixelFramePNG();},time);
  const bytes=Buffer.from(data.split(',')[1],'base64');
  await fs.writeFile(path.join(output,'qa',`native-endpoint-${time}.png`),bytes);
  endpoints.push(sha(bytes));
 }
 if(endpoints[0]!==endpoints[1])throw new Error('The native loop endpoints differ.');
 if(process.argv.includes('--stills')){
  for(const time of [4,8.6,9.5,14,18.6,21]){
   const data=await page.evaluate(t=>{window.renderPixelAt(t);return window.pixelFramePNG();},time);
   await fs.writeFile(path.join(output,'qa',`still-${time}.png`),Buffer.from(data.split(',')[1],'base64'));
  }
  console.log(JSON.stringify({status:'stills-for-review',output}));
  await browser.close();process.exit(0);
 }
 encoder=spawn('/usr/bin/ffmpeg',['-hide_banner','-loglevel','error','-f','image2pipe','-vcodec','png','-framerate',String(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','medium','-crf','14','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart','-y',movie],{stdio:['pipe','ignore','pipe']});
 let log='';encoder.stderr.on('data',chunk=>{log+=chunk.toString();});
 const ended=new Promise((resolve,reject)=>{encoder.on('error',reject);encoder.on('close',code=>code===0?resolve():reject(new Error(`Encoder failed (${code}): ${log}`)));});
 for(let frame=0;frame<frames;frame++){
  const data=await page.evaluate(t=>{window.renderPixelAt(t);return window.pixelFramePNG();},frame/fps);
  const bytes=Buffer.from(data.split(',')[1],'base64');
  if(!encoder.stdin.write(bytes))await once(encoder.stdin,'drain');
  if(frame%120===0)console.log(JSON.stringify({frame,total:frames,elapsed_seconds:Math.round((Date.now()-started)/1000)}));
 }
 encoder.stdin.end();await ended;
 if(errors.length)throw new Error(errors.join('; '));
 const content=await fs.readFile(movie);
 const receipt={schema:'cozy-pixel-smooth-preview-render-v1',movie,sha256:sha(content),bytes:content.length,source,source_sha256:sha(sourceBytes),foliage,foliage_sha256:sha(foliageBytes),source_geometry:geometry,render_dimensions:[1920,1080],export_dimensions:[1920,1080],continuous_subpixel_motion:true,duration_seconds:duration,fps,frames,audio_streams:0,native_cycle_exact_match:true,endpoints_sha256:endpoints,elapsed_seconds:Math.round((Date.now()-started)/1000),effects:['Two rain depths','Pond rain ripples','Continuous water reflections','Transparent willow foliage with anchored sway and local flutter','Articulated breathing and hopping frog','Chimney smoke','Seven slow fireflies','One lantern moth'],browser_errors:errors};
 await fs.writeFile(path.join(output,'render-receipt.json'),JSON.stringify(receipt,null,2)+'\n');
 console.log(JSON.stringify({status:'encoded',movie,bytes:receipt.bytes,elapsed_seconds:receipt.elapsed_seconds}));
}catch(error){if(encoder)encoder.kill('SIGTERM');throw error;}finally{await browser.close();}
