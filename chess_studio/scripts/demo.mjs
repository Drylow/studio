import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';
import {newProject} from '../model.mjs';
import {FFMPEG,run,ingest} from '../media.mjs';
import './setup.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));const root=path.resolve(here,'..');
const dbFile=path.join(root,'.local/library.json');
await fs.mkdir(path.join(root,'.local'),{recursive:true});
let db;try{db=JSON.parse(await fs.readFile(dbFile,'utf8'));}catch{db={media:{},projects:{}};}
if(Object.values(db.projects).some(p=>p.demo)){console.log('Démo déjà présente.');process.exit(0);}
const file=path.join(root,'.local/demo-source.mp4');
await run(FFMPEG,['-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=1920x1080:rate=30:duration=8','-f','lavfi','-i','sine=frequency=220:sample_rate=48000:duration=8',
  '-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-shortest',file]);
const m=await ingest(file,'Mire de test · image et son',path.join(root,'public'));
const p={...newProject('animation','Démo technique · pauses et évaluations'),id:randomUUID(),demo:true,updatedAt:new Date().toISOString()};
p.players=[{name:'Personnage A',portrait:''},{name:'Personnage B',portrait:''}];
p.shots=[{id:randomUUID(),mediaId:m.id,in:0,out:8,volume:.18,moves:[
  {id:randomUUID(),at:2,rating:'book',player:0,title:'Opening move',comment:'Une pause de lecture. Le clip reprend exactement au point où il s’est arrêté.',quote:'',hold:3,score:.8,zoom:1.025,placement:'right'},
  {id:randomUUID(),at:5,rating:'brilliant',player:1,title:'The counterplay',comment:'Le personnage noir reprend l’avantage. Les notes et le rythme restent entre tes mains.',quote:'',hold:3.5,score:-2,zoom:1.035,placement:'left'}]}];
db.media[m.id]=m;db.projects[p.id]=p;await fs.writeFile(dbFile,JSON.stringify(db,null,2));await fs.rm(file,{force:true});console.log('Démo créée :',p.id);
