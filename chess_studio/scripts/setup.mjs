import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const dir=path.join(here,'../public/sfx');fs.mkdirSync(dir,{recursive:true});
// Quiet, short, original ticks. No external sound licensing or network at render time.
for(const [name,freq] of [['tick',740],['low',270]]){
  const file=path.join(dir,`${name}.wav`);if(fs.existsSync(file))continue;
  const rate=48000,n=5760,buf=Buffer.alloc(44+n*2);
  buf.write('RIFF',0);buf.writeUInt32LE(36+n*2,4);buf.write('WAVEfmt ',8);buf.writeUInt32LE(16,16);buf.writeUInt16LE(1,20);buf.writeUInt16LE(1,22);
  buf.writeUInt32LE(rate,24);buf.writeUInt32LE(rate*2,28);buf.writeUInt16LE(2,32);buf.writeUInt16LE(16,34);buf.write('data',36);buf.writeUInt32LE(n*2,40);
  for(let i=0;i<n;i++){const t=i/rate;const env=Math.min(1,i/180)*Math.exp(-t*42)*(1-i/n);buf.writeInt16LE(Math.round(Math.sin(t*Math.PI*2*freq)*env*14000),44+i*2);}
  fs.writeFileSync(file,buf);
}
