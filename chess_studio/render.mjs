import path from 'node:path';
import fs from 'node:fs/promises';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia,renderStill,selectComposition} from '@remotion/renderer';
const here=path.dirname(fileURLToPath(import.meta.url));
const dir=path.resolve(process.argv[2]);
const props=JSON.parse(await fs.readFile(path.join(dir,'props.json'),'utf8'));
let browserExecutable=process.env.REMOTION_BROWSER || null;
if(!browserExecutable){
  const cache=path.join(os.homedir(),'.cache/hyperframes/chrome/chrome-headless-shell');
  try {for(const version of (await fs.readdir(cache)).sort().reverse()){
    const exe=path.join(cache,version,'chrome-headless-shell-win64/chrome-headless-shell.exe');
    try {await fs.access(exe);browserExecutable=exe;break;}catch{}
  }}catch{}
}
const say=data=>process.stdout.write(JSON.stringify(data)+'\n');
let serveUrl;
let bundleDirectory;
try {
  say({stage:'Préparation du montage',progress:0});
  serveUrl=await bundle({entryPoint:path.join(here,'src','index.tsx'),rootDir:here,publicDir:path.join(dir,'public'),enableCaching:false,
    onDirectoryCreated:directory=>{bundleDirectory=directory;},
    onProgress:p=>say({stage:'Préparation du montage',progress:p/100*0.05})});
  const composition=await selectComposition({serveUrl,id:'ChessReview',inputProps:props,browserExecutable});
  if(process.argv[3]==='--still'){
    await renderStill({serveUrl,composition,inputProps:props,output:path.join(dir,'preview.png'),frame:Number(process.argv[4] || 0),browserExecutable});
  }else{
    let last=-1;
    await renderMedia({serveUrl,composition,inputProps:props,codec:'h264',crf:16,x264Preset:'medium',pixelFormat:'yuv420p',audioCodec:'aac',audioBitrate:'256k',
      outputLocation:path.join(dir,'video.mp4'),browserExecutable,concurrency:2,
      onProgress:({progress})=>{const percent=Math.floor(progress*100);if(percent!==last){last=percent;say({stage:'Export',progress});}}});
  }
  say({stage:'Terminé',progress:1});
}catch(e){console.error(e);process.exitCode=1;}
finally{if(bundleDirectory || serveUrl)await fs.rm(bundleDirectory || serveUrl,{recursive:true,force:true});}
