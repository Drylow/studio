// Deterministic browser animation, piped directly to the video encoder.
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
const output=path.resolve(process.argv[2]||path.join(root,'output/nature-sleep/light-preview'));
const movie=path.join(output,'Quiet-Little-Worlds-Garden-24s.mp4');
const source=path.join(here,'../branding/C-botanical-moss-garden.png');
const duration=24,fps=30,width=1920,height=1080,frames=duration*fps;
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
await fs.mkdir(path.join(output,'qa'),{recursive:true});
try {await fs.access(movie);throw new Error('Preserve prior exports: choose a fresh output directory.');}catch(error){if(error.code!=='ENOENT')throw error;}
const sourceBytes=await fs.readFile(source);
let html=await fs.readFile(path.join(here,'garden.html'),'utf8');
html=html.replace('const CAPTURE_MODE = false;','const CAPTURE_MODE = true;');
html=html.replace('__GARDEN_IMAGE_DATA_URL__',`data:image/png;base64,${sourceBytes.toString('base64')}`);
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
let encoder=null;
const began=Date.now();
try {
  const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
  const pageErrors=[];page.on('pageerror',error=>pageErrors.push(error.message));
  await page.route('**/*',route=>route.abort());
  await page.setContent(html,{waitUntil:'load'});
  if(pageErrors.length) throw new Error(`Browser initialization failed: ${pageErrors.join('; ')}`);
  const sourceGeometry=await page.evaluate(()=>window.gardenReady);
  const canvas=page.locator('canvas');
  const endpoint=[];
  for(const time of [0,duration]){
    await page.evaluate(time=>window.renderGardenAt(time),time);
    const bytes=await canvas.screenshot({type:'png'});
    const filename=`endpoint-${time}.png`;await fs.writeFile(path.join(output,'qa',filename),bytes);
    endpoint.push({time,sha256:sha(bytes),file:filename});
  }
  if(endpoint[0].sha256!==endpoint[1].sha256) throw new Error('The exact cycle endpoint differs from its start.');
  encoder=spawn('/usr/bin/ffmpeg',['-hide_banner','-loglevel','error','-f','image2pipe','-vcodec','mjpeg','-framerate',String(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','medium','-crf','16','-pix_fmt','yuv420p','-r',String(fps),'-movflags','+faststart','-threads','2','-y',movie],{stdio:['pipe','ignore','pipe']});
  let errors='';encoder.stderr.on('data',chunk=>{errors+=chunk.toString();});
  const finished=new Promise((resolve,reject)=>{encoder.on('error',reject);encoder.on('close',code=>code===0?resolve():reject(new Error(`Encoder failed (${code}): ${errors}`)));});
  // A screenshot only lives in memory until its bytes enter the pipe.
  for(let frame=0;frame<frames;frame++){
    const data=await page.evaluate(time=>{window.renderGardenAt(time);return document.querySelector('canvas').toDataURL('image/jpeg',.97);},frame/fps);
    const bytes=Buffer.from(data.split(',')[1],'base64');
    if(!encoder.stdin.write(bytes)) await once(encoder.stdin,'drain');
    if(frame%90===0)console.log(JSON.stringify({stage:'capture',frame,total:frames,elapsed_seconds:Math.round((Date.now()-began)/1000)}));
  }
  encoder.stdin.end();await finished;
  if(pageErrors.length)throw new Error(`Browser errors: ${pageErrors.join('; ')}`);
  const movieBytes=await fs.readFile(movie);
  const receipt={kind:'light-animation-preview',movie,bytes:movieBytes.length,sha256:sha(movieBytes),source,source_sha256:sha(sourceBytes),source_geometry:sourceGeometry,export_geometry:{width,height,fps,duration_seconds:duration,frames},native_4k:false,no_audio:true,cycle_endpoint_exact_match:true,endpoint,animation:{camera:'fixed',water:'soft regional optical movement below two pixels',foliage:'two local fern regions below 1.3 pixels',fireflies:'three continuously moving points with no flashing',animals:'original painted frog and snail stay unchanged'},page_errors:pageErrors,elapsed_seconds:Math.round((Date.now()-began)/1000)};
  await fs.writeFile(path.join(output,'render-receipt.json'),JSON.stringify(receipt,null,2)+'\n');
  console.log(JSON.stringify({stage:'encoded',movie,bytes:receipt.bytes,elapsed_seconds:receipt.elapsed_seconds}));
} catch(error){if(encoder)encoder.kill('SIGTERM');throw error;} finally{await browser.close();}
