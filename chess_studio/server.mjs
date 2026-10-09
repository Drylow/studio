import express from 'express';
import multer from 'multer';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomUUID, createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {createServer as createViteServer} from 'vite';
import {PROFILES, newProject, validateProject, buildTimeline} from './model.mjs';
import {FFMPEG, FFPROBE, YTDLP, run, ingest, download} from './media.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
export const PUBLIC = path.join(here,'public');
export const LOCAL = path.resolve(here,'.local');
export const WORK = path.resolve(here,'../work/chess-studio');
for (const d of [LOCAL,WORK,path.join(WORK,'tmp'),path.join(WORK,'exports')]) fs.mkdirSync(d,{recursive:true});
const dbFile = path.join(LOCAL,'library.json');
let db = fs.existsSync(dbFile) ? JSON.parse(fs.readFileSync(dbFile,'utf8')) : {media:{},projects:{}};
function persist() {fs.writeFileSync(dbFile+'.tmp',JSON.stringify(db,null,2));fs.renameSync(dbFile+'.tmp',dbFile);}
const jobs = new Map();
function job(kind, task) {
  if ([...jobs.values()].some(j => j.kind === kind && j.state === 'running')) throw new Error('Une opération de ce type est déjà en cours.');
  const j = {id:randomUUID(),kind,state:'running',progress:0,logs:[],createdAt:new Date().toISOString()}; jobs.set(j.id,j);
  // Defer all mutations until the caller has persisted the new project/job.
  Promise.resolve().then(() => task(j, line => {j.logs.push(String(line).slice(0,2000));j.logs=j.logs.slice(-30);})).then(result => {
    j.state='done'; j.progress=1; j.result=result;
  }).catch(e => {j.state='failed';j.error=e.message;});
  return j;
}
function requireProject(id) {const p=db.projects[id]; if(!p) throw new Error('Projet introuvable.');return p;}
function prepareProps(project, stills = {}) {return {project,media:db.media,stills};}
async function freezes(project) {
  const stills = {};
  for (const seg of buildTimeline(project).segments.filter(x=>x.kind==='hold')) {
    const media = db.media[seg.mediaId];
    const key = createHash('sha256').update(`${media.id}:${project.fps}:${seg.sourceFrame}`).digest('hex').slice(0,24);
    const relative = `media/${media.id}/freeze-${key}.jpg`;
    const target = path.join(PUBLIC,relative);
    if (!fs.existsSync(target)) await run(FFMPEG,['-hide_banner','-loglevel','error','-y','-ss',String(seg.sourceFrame/project.fps),
      '-i',path.join(PUBLIC,media.original),'-frames:v','1','-q:v','1',target]);
    if (!fs.existsSync(target)) throw new Error('Image de pause introuvable : avancer le point de sortie du clip.');
    stills[seg.move.id]=relative;
  }
  return stills;
}
const app = express();
app.use((req,res,next)=>{
  const host = String(req.headers.host || '').split(':')[0];
  if (!['127.0.0.1','localhost'].includes(host)) return res.status(403).json({error:'Atelier accessible uniquement en local.'});
  if (req.method !== 'GET' && req.headers.origin) {
    let origin;try {origin=new URL(req.headers.origin);}catch{return res.sendStatus(403);}
    if (!['127.0.0.1','localhost'].includes(origin.hostname) || origin.host !== req.headers.host) return res.sendStatus(403);
  }
  next();
});
app.use(express.json({limit:'4mb'}));
const upload = multer({dest:path.join(WORK,'tmp'),limits:{fileSize:20*1024*1024*1024,files:1}});
app.get('/api/library',(req,res)=>res.json({profiles:PROFILES,media:db.media,projects:Object.values(db.projects).map(({id,title,profile,updatedAt})=>({id,title,profile,updatedAt}))}));
app.get('/api/health',async(req,res)=>{
  const checks = await Promise.all([FFMPEG,FFPROBE,YTDLP].map(async name=>{try {await run(name,[name===YTDLP?'--version':'-version'],()=>{},10000);return {name,ok:true};}catch{return {name,ok:false};}}));
  res.json({ok:true,application:'drylow-chess-studio',checks});
});
app.post('/api/projects',(req,res)=>{
  const p = {...newProject(req.body.profile,req.body.title),id:randomUUID(),updatedAt:new Date().toISOString()};
  validateProject(p,db.media);db.projects[p.id]=p;persist();res.json(prepareProps(p));
});
app.get('/api/projects/:id',(req,res)=>res.json(prepareProps(requireProject(req.params.id))));
app.put('/api/projects/:id',(req,res)=>{
  requireProject(req.params.id);const p=structuredClone(req.body);p.id=req.params.id;
  validateProject(p,db.media);p.updatedAt=new Date().toISOString();db.projects[p.id]=p;persist();res.json(prepareProps(p));
});
app.post('/api/prepare/:id',async(req,res)=>{const p=structuredClone(requireProject(req.params.id));validateProject(p,db.media);res.json(prepareProps(p,await freezes(p)));});
app.post('/api/import',upload.single('file'),(req,res)=>{
  if(!req.file) throw new Error('Sélectionner un fichier vidéo.');
  const file=req.file;
  try {
    const j=job('import',async(_,line)=>{try {const ext=path.extname(file.originalname);const named=file.path+ext;await fsp.rename(file.path,named);
      try {const m=await ingest(named,file.originalname,PUBLIC,line);db.media[m.id]=m;persist();return m;}finally{await fsp.rm(named,{force:true});}
    }finally{await fsp.rm(file.path,{force:true});}});res.json(j);
  }catch(e){fs.rmSync(file.path,{force:true});throw e;}
});
app.post('/api/download',(req,res)=>{
  const {url,language}=req.body;
  res.json(job('import',async(_,line)=>{const m=await download(url,PUBLIC,path.join(WORK,'tmp'),line,language || 'en');db.media[m.id]=m;persist();return m;}));
});
app.post('/api/portrait',upload.single('file'),async(req,res)=>{
  if(!req.file) throw new Error('Sélectionner un portrait.');
  const input=req.file.path;const relative=`portraits/${randomUUID()}.png`;await fsp.mkdir(path.join(PUBLIC,'portraits'),{recursive:true});
  try {await run(FFMPEG,['-hide_banner','-loglevel','error','-y','-i',input,'-frames:v','1','-vf','scale=512:512:force_original_aspect_ratio=increase,crop=512:512',path.join(PUBLIC,relative)]);res.json({path:relative});}
  finally{await fsp.rm(input,{force:true});}
});
app.get('/api/jobs/:id',(req,res)=>{const j=jobs.get(req.params.id);if(!j)return res.status(404).json({error:'Opération introuvable (atelier redémarré).'});res.json(j);});
app.post('/api/export/:id',(req,res)=>{
  const project=structuredClone(requireProject(req.params.id));validateProject(project,db.media);
  if(!project.shots.length) throw new Error('Ajouter au moins un extrait avant l’export.');
  const j=job('render',async(j,line)=>{
    const stills=await freezes(project);const props=prepareProps(project,stills);
    // The export freezes both edits AND media; later edits cannot change this render.
    const dir=path.join(WORK,'exports',j.id);const snapshot=path.join(dir,'public');await fsp.mkdir(snapshot,{recursive:true});
    await fsp.cp(path.join(PUBLIC,'chesscom'),path.join(snapshot,'chesscom'),{recursive:true});
    await fsp.cp(path.join(PUBLIC,'sfx'),path.join(snapshot,'sfx'),{recursive:true});
    const selected={};
    for(const shot of project.shots){const m=db.media[shot.mediaId];selected[m.id]={...m,src:m.original};}
    props.media=selected;
    const assets=new Set([...Object.values(selected).map(m=>m.original),...Object.values(stills),...project.players.map(p=>p.portrait).filter(Boolean)]);
    for(const asset of assets){const dest=path.join(snapshot,asset);await fsp.mkdir(path.dirname(dest),{recursive:true});await fsp.copyFile(path.join(PUBLIC,asset),dest);}
    await fsp.writeFile(path.join(dir,'props.json'),JSON.stringify(props,null,2));
    await new Promise((resolve,reject)=>{
      const child=spawn(process.execPath,[path.join(here,'render.mjs'),dir],{cwd:here,shell:false,windowsHide:true});let tail='';
      child.stdout.on('data',b=>{const t=String(b);tail=(tail+t).slice(-5000);line(t);for(const l of t.split('\n')){try {const data=JSON.parse(l);if(data.progress!==undefined)j.progress=data.progress;}catch{}}});
      child.stderr.on('data',b=>{tail=(tail+b).slice(-5000);line(String(b));});
      child.on('error',reject);child.on('close',c=>c===0?resolve():reject(new Error('Export interrompu : '+tail)));
    });
    return {url:`/exports/${j.id}/video.mp4`,path:path.join(dir,'video.mp4')};
  });res.json(j);
});
app.use('/exports',express.static(path.join(WORK,'exports'),{index:false,dotfiles:'deny'}));
app.use(express.static(PUBLIC));
if(fs.existsSync(path.join(here,'dist','index.html'))){app.use(express.static(path.join(here,'dist')));app.get('/',(_,res)=>res.sendFile(path.join(here,'dist','index.html')));}
else {const vite=await createViteServer({root:here,server:{middlewareMode:true},appType:'spa'});app.use(vite.middlewares);}
app.use((err,req,res,next)=>{console.error(err.message);res.status(400).json({error:err.message || 'Opération impossible.'});});
const port=Number(process.env.CHESS_PORT || 4317);
app.listen(port,'127.0.0.1',()=>console.log(`Chess Studio http://127.0.0.1:${port}`));
