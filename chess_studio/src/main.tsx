import React, {useEffect,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Player, type PlayerRef} from '@remotion/player';
import {ChessReview,RatingIcon} from './ChessReview';
import {buildTimeline,PROFILES,RATINGS,timecode,validateProject} from '../model.mjs';
import {sourceReview} from '../quality.mjs';
import type {Project,VideoProps,Media,Move,Shot,Segment} from './types';
import './style.css';
type Job={id:string;state:string;kind:string;progress:number;logs:string[];error?:string;result?:{url?:string;path?:string}};
async function api(url:string,options:RequestInit={}) {const r=await fetch(url,options);const data=await r.json();if(!r.ok)throw new Error(data.error || 'Opération impossible.');return data;}
const json=(data:unknown)=>({headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const uid=()=>crypto.randomUUID();
function App(){
  const [library,setLibrary]=useState<{media:Record<string,Media>;projects:Project[]}>({media:{},projects:[]});
  const [props,setProps]=useState<VideoProps|null>(null);const [shotId,setShotId]=useState('');const [moveId,setMoveId]=useState('');
  const [frame,setFrame]=useState(0);const [dirty,setDirty]=useState(false);const [notice,setNotice]=useState('');const [busy,setBusy]=useState(false);
  const [job,setJob]=useState<Job|null>(null);const [link,setLink]=useState('');const [language,setLanguage]=useState('en');
  const [reviewMedia,setReviewMedia]=useState<Media|null>(null);const [sheet,setSheet]=useState('');
  const [reviewChecks,setReviewChecks]=useState({watchedEntirely:false,noLogo:false,noText:false});const [reviewNotes,setReviewNotes]=useState('');const [showRejected,setShowRejected]=useState(false);
  const player=useRef<PlayerRef>(null);const videoInput=useRef<HTMLInputElement>(null);const [tools,setTools]=useState<{name:string;ok:boolean}[]>([]);
  const project=props?.project;const timeline=project?buildTimeline(project):{segments:[],durationInFrames:1};
  const shot=project?.shots.find(s=>s.id===shotId);const move=shot?.moves.find(m=>m.id===moveId);
  const guarded=async(fn:()=>Promise<unknown>)=>{setNotice('');setBusy(true);try{await fn();}catch(e){setNotice((e as Error).message);}finally{setBusy(false);}};
  const refresh=async()=>{const data=await api('/api/library');setLibrary(data);return data;};
  const openProject=async(id:string)=>{
    if(dirty && !window.confirm('Des modifications ne sont pas sauvegardées. Changer de projet ?'))return;
    const data=await api(`/api/projects/${id}`);setProps(data);setDirty(false);setShotId(data.project.shots[0]?.id || '');setMoveId('');setFrame(0);
  };
  useEffect(()=>{guarded(async()=>{const data=await refresh();if(data.projects.length)await openProject(data.projects[0].id);const h=await api('/api/health');setTools(h.checks);});},[]);
  useEffect(()=>{const ref=player.current;if(!ref)return;const update=(event:{detail:{frame:number}})=>setFrame(event.detail.frame);ref.addEventListener('frameupdate',update);return()=>ref.removeEventListener('frameupdate',update);},[project?.id]);
  useEffect(()=>{const h=(e:BeforeUnloadEvent)=>{if(dirty){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',h);return()=>window.removeEventListener('beforeunload',h);},[dirty]);
  useEffect(()=>{
    if(!job || job.state!=='running')return;
    const timer=setInterval(async()=>{try{const j=await api(`/api/jobs/${job.id}`);setJob(j);if(j.state==='done'){await refresh();setNotice(j.kind==='render'?'Export terminé.':'Clip ajouté à la bibliothèque.');}
      if(j.state==='failed')setNotice(j.error || 'Opération interrompue.');}catch(e){setNotice((e as Error).message);setJob({...job,state:'failed'});}},1500);
    return()=>clearInterval(timer);
  },[job?.id,job?.state]);
  const edit=(fn:(p:Project)=>void)=>{if(!props)return;const p=structuredClone(props.project);fn(p);setProps({...props,project:p,media:library.media,stills:{}});setDirty(true);};
  const editShot=(changes:Partial<Shot>)=>edit(p=>{const s=p.shots.find(s=>s.id===shotId)!;Object.assign(s,changes);});
  const editMove=(changes:Partial<Move>)=>edit(p=>{const s=p.shots.find(s=>s.id===shotId)!;Object.assign(s.moves.find(m=>m.id===moveId)!,changes);s.moves.sort((a,b)=>a.at-b.at);});
  const save=async()=>{
    if(!project)return;validateProject(project,library.media);
    await api(`/api/projects/${project.id}`,{method:'PUT',...json(project)});
    const data=await api(`/api/prepare/${project.id}`,{method:'POST'});setProps(data);setDirty(false);await refresh();setNotice('Montage sauvegardé.');return data;
  };
  const create=async(profile:string)=>{if(dirty&&!window.confirm('Changer de projet sans sauvegarder ?'))return;
    const data=await api('/api/projects',{method:'POST',...json({profile,title:profile==='animation'?'Nouvelle analyse animée':'Nouvelle analyse · Game of Thrones'})});setProps(data);setDirty(false);setShotId('');setMoveId('');await refresh();};
  const importFile=async(file:File)=>{const form=new FormData();form.append('file',file);setJob(await api('/api/import',{method:'POST',body:form}));};
  const addShot=(m:Media)=>{if(!project)return;if(sourceReview(m).status!=='approved'){setNotice('Vérifie cette source avant de l’ajouter : sans logo ni texte incrusté.');return;}const id=uid();edit(p=>p.shots.push({id,mediaId:m.id,in:0,out:Math.min(m.duration,30),volume:1,moves:[]}));setShotId(id);setMoveId('');};
  const inspectSource=async(m:Media)=>{setReviewMedia(m);setSheet('');setReviewNotes(m.review?.notes || '');setReviewChecks({watchedEntirely:false,noLogo:false,noText:false});const r=await api(`/api/media/${m.id}/contact-sheet`,{method:'POST'});setSheet(r.path);};
  const recordReview=async(status:string)=>{if(!reviewMedia)return;await api(`/api/media/${reviewMedia.id}/review`,{method:'POST',...json({status,...reviewChecks,notes:reviewNotes})});await refresh();setReviewMedia(null);setNotice(status==='approved'?'Source propre validée.':'Source écartée du montage.');};
  const sourceTime=()=>{const seg=(timeline.segments as Segment[]).find(s=>frame>=s.from && frame<s.from+s.duration);return seg?{shotId:seg.shotId,time:(seg.sourceFrame+(seg.kind==='play'?frame-seg.from:1))/project!.fps}:null;};
  const addMove=()=>{
    if(!project || !shot)return;
    const current=sourceTime();const at=current?.shotId===shot.id?current.time:shot.in+(shot.out-shot.in)/2;
    const id=uid();edit(p=>{const s=p.shots.find(s=>s.id===shotId)!;s.moves.push({id,at:Math.min(shot.out-1/project.fps,Math.max(shot.in,at)),rating:'good',player:0,title:'Nom du coup',comment:'Écris ici ce que ce coup change dans la scène.',quote:'',hold:6,score:0,zoom:1,placement:'right'});s.moves.sort((a,b)=>a.at-b.at);});setMoveId(id);
  };
  const seekMove=(s:Shot,m:Move)=>{setShotId(s.id);setMoveId(m.id);const segment=(timeline.segments as Segment[]).find(x=>x.move?.id===m.id);if(segment)player.current?.seekTo(segment.from+Math.round(project!.fps*.35));};
  const downloadProject=()=>{if(!project)return;const blob=new Blob([JSON.stringify(project,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='montage.json';a.click();URL.revokeObjectURL(url);};
  return <div className="app">
    <header><div className="brand"><span className="mark">♟</span><div><strong>Chess Studio</strong><small>Atelier de montage local</small></div></div>
      <div className="project-picker"><select aria-label="Projet" value={project?.id || ''} onChange={e=>guarded(()=>openProject(e.target.value))}><option value="" disabled>Choisir un projet</option>{library.projects.map(p=><option key={p.id} value={p.id}>{p.title}</option>)}</select>
        <button onClick={()=>guarded(()=>create('animation'))}>+ Animation</button><button onClick={()=>guarded(()=>create('thrones'))}>+ Thrones</button></div>
      <div className="header-actions"><span className={`save-state ${dirty?'dirty':''}`}>{dirty?'Modifications en cours':'Sauvegardé'}</span><button disabled={!project || busy} onClick={()=>guarded(save)}>Sauvegarder</button>
        <button className="primary" disabled={!project?.shots.length || busy || job?.state==='running'} onClick={()=>guarded(async()=>{await save();setJob(await api(`/api/export/${project!.id}`,{method:'POST'}));})}>Exporter le film ↗</button></div>
    </header>
    {notice && <div className="notice" role="status">{notice}<button aria-label="Fermer le message" onClick={()=>setNotice('')}>×</button></div>}
    <main>
      <aside className="library"><div className="section-head"><h2>Clips sources</h2><span>{Object.values(library.media).filter(m=>sourceReview(m).status!=='rejected').length}</span></div>
        <button className="import-button" disabled={busy || job?.state==='running'} onClick={()=>videoInput.current?.click()}>＋ Importer un fichier</button>
        <input ref={videoInput} type="file" accept="video/*,.mkv" hidden onChange={e=>{const f=e.target.files?.[0];if(f)guarded(()=>importFile(f));e.target.value='';}}/>
        <details className="download-box"><summary>Importer depuis YouTube</summary><label>Lien du clip<input value={link} onChange={e=>setLink(e.target.value)} placeholder="https://www.youtube.com/watch?v=…"/></label>
          <label>Audio préféré<select value={language} onChange={e=>setLanguage(e.target.value)}><option value="en">Anglais</option><option value="fr">Français</option></select></label>
          <p>Meilleure définition disponible. Choisis une source sans texte incrusté.</p><button disabled={!link || busy || job?.state==='running'} onClick={()=>guarded(async()=>setJob(await api('/api/download',{method:'POST',...json({url:link,language})})))}>Télécharger le clip</button></details>
        <label className="checkbox"><input type="checkbox" checked={showRejected} onChange={e=>setShowRejected(e.target.checked)}/>Afficher les sources écartées</label>
        <div className="media-list">{Object.values(library.media).filter(m=>showRejected || sourceReview(m).status!=='rejected').map(m=><article key={m.id} className="media-card"><img src={`/${m.thumbnail}`} alt="Aperçu du clip"/><strong>{m.name}</strong>
          <small>{m.width} × {m.height} · {timecode(m.duration)} · {Math.round(m.fps)} i/s{m.audioLanguage?` · audio ${m.audioLanguage}`:''}</small>
          <span className={`source-status ${sourceReview(m).status}`}>{sourceReview(m).status==='approved'?'✓ Source propre vérifiée':sourceReview(m).status==='rejected'?'Source écartée':'À vérifier : logo et texte'}</span>
          <div className="media-actions"><button disabled={!project || sourceReview(m).status!=='approved'} onClick={()=>addShot(m)}>Ajouter au montage</button><a href={`/${m.original}`} download>Original ↗</a></div><button onClick={()=>guarded(()=>inspectSource(m))}>Vérifier la source</button></article>)}
          {!Object.keys(library.media).length && <p className="muted">Importe le premier clip pour commencer.</p>}</div>
        <div className="tool-status">{tools.map(t=><span key={t.name} className={t.ok?'ok':'bad'}>● {t.name}</span>)}</div>
      </aside>
      <section className="workspace">
        <div className="workspace-top"><div><span className="eyebrow">{project?PROFILES[project.profile as keyof typeof PROFILES].name:'Animation & Game of Thrones'}</span>
          <input className="title-input" aria-label="Titre de la vidéo" value={project?.title || ''} placeholder="Ton prochain duel" disabled={!project} onChange={e=>edit(p=>{p.title=e.target.value;})}/></div><span className="duration">{timecode(timeline.durationInFrames/(project?.fps || 30))}</span></div>
        <div className="preview">{props && project!.shots.length ? <Player ref={player} component={ChessReview} inputProps={{...props,media:library.media}} durationInFrames={timeline.durationInFrames} fps={project!.fps} compositionWidth={1920} compositionHeight={1080} controls style={{width:'100%',aspectRatio:'16/9'}} clickToPlay={false} doubleClickToFullscreen/> :
          <div className="empty-preview"><span>♟</span><h1>Chaque réplique est un coup.</h1><p>Crée un projet, ajoute un clip, puis place tes analyses.</p><button onClick={()=>guarded(()=>create('animation'))}>Créer une analyse animée</button></div>}</div>
        <div className="timeline-head"><h2>Montage</h2><span>{project?.shots.length || 0} extraits · {project?.shots.reduce((n,s)=>n+s.moves.length,0) || 0} coups</span><button disabled={!shot} onClick={addMove}>＋ Ajouter un coup au curseur</button></div>
        <div className="timeline-track">{(timeline.segments as Segment[]).map((seg,i)=><button key={i} className={`timeline-segment ${seg.kind}`} style={{flexGrow:seg.duration,borderColor:seg.move?RATINGS[seg.move.rating as keyof typeof RATINGS].color:undefined}}
          onClick={()=>{setShotId(seg.shotId);setMoveId(seg.move?.id || '');player.current?.seekTo(seg.from);}} title={seg.move?.title || library.media[seg.mediaId]?.name}>{seg.move?RATINGS[seg.move.rating as keyof typeof RATINGS].symbol:'▶'}</button>)}</div>
        <div className="shots">{project?.shots.map((s,i)=><article key={s.id} className={`shot ${s.id===shotId?'selected':''}`}>
          <div className="shot-head"><button onClick={()=>{setShotId(s.id);setMoveId('');const seg=(timeline.segments as Segment[]).find(x=>x.shotId===s.id);if(seg)player.current?.seekTo(seg.from);}}><b>{String(i+1).padStart(2,'0')}</b> {library.media[s.mediaId]?.name}</button>
            <span>{timecode(s.in)} → {timecode(s.out)}</span><button aria-label="Déplacer l’extrait vers le haut" disabled={i===0} onClick={()=>edit(p=>{[p.shots[i-1],p.shots[i]]=[p.shots[i],p.shots[i-1]];})}>↑</button>
            <button aria-label="Déplacer l’extrait vers le bas" disabled={i===project.shots.length-1} onClick={()=>edit(p=>{[p.shots[i+1],p.shots[i]]=[p.shots[i],p.shots[i+1]];})}>↓</button>
            <button aria-label="Supprimer l’extrait" onClick={()=>{edit(p=>{p.shots=p.shots.filter(x=>x.id!==s.id);});if(shotId===s.id){setShotId('');setMoveId('');}}}>×</button></div>
          <div className="move-list">{s.moves.map(m=><button key={m.id} className={m.id===moveId?'active':''} onClick={()=>seekMove(s,m)}><RatingIcon rating={m.rating} size={24} editor/><span>{m.title}</span><small>{timecode(m.at)}</small></button>)}{!s.moves.length && <span className="muted">Sélectionne cet extrait et ajoute un coup.</span>}</div>
        </article>)}</div>
        {job && <div className="job"><div><strong>{job.kind==='render'?'Export du film':'Import du clip'}</strong><span>{job.state==='running'?'En cours…':job.state==='done'?'Terminé':'Interrompu'}</span></div>{job.state==='running' && <progress value={job.kind==='render'?job.progress:undefined} max="1"/>}
          {job.result?.url && <a className="primary" href={job.result.url} download>Télécharger le MP4</a>}<details><summary>Détails</summary><pre>{job.error || job.logs.join('\n')}</pre></details></div>}
      </section>
      <aside className="inspector"><div className="section-head"><h2>{move?'Analyse du coup':'Réglages'}</h2>{move && <button aria-label="Revenir aux réglages" onClick={()=>setMoveId('')}>×</button>}</div>
        {project && <>{move && shot ? <>
          <label>Nom du coup<input value={move.title} maxLength={60} onChange={e=>editMove({title:e.target.value})}/></label>
          <div className="rating-grid">{Object.entries(RATINGS).map(([key,r])=><button key={key} className={move.rating===key?'selected':''} onClick={()=>editMove({rating:key})}><RatingIcon rating={key} size={30} editor/><span>{r.label}</span></button>)}</div>
          <label>Personnage<select value={move.player} onChange={e=>editMove({player:Number(e.target.value)})}>{project.players.map((p,i)=><option key={i} value={i}>{p.name}</option>)}</select></label>
          <label>Ton analyse<textarea rows={5} value={move.comment} maxLength={240} onChange={e=>editMove({comment:e.target.value})}/><small>{move.comment.length}/240 · court, précis, lié à la scène</small></label>
          <label>Réplique exacte · facultatif<input value={move.quote} maxLength={180} onChange={e=>editMove({quote:e.target.value})}/></label>
          <label>Tags · séparés par des virgules<input value={move.tags || ''} maxLength={120} onChange={e=>editMove({tags:e.target.value})}/></label>
          <label>Meilleur coup possible · facultatif<input value={move.betterMove || ''} maxLength={120} onChange={e=>editMove({betterMove:e.target.value})}/></label>
          <div className="two-cols"><label>Instant source (s)<input type="number" step="0.01" min={shot.in} max={shot.out} value={move.at} onChange={e=>editMove({at:Number(e.target.value)})}/></label><label>Pause (s)<input type="number" step="0.1" min="1" max="20" value={move.hold} onChange={e=>editMove({hold:Number(e.target.value)})}/></label></div>
          <label>Avantage des blancs : {move.score>0?'+':''}{move.score.toFixed(1)}<input type="range" min="-10" max="10" step="0.1" value={move.score} onChange={e=>editMove({score:Number(e.target.value)})}/><small>Évaluation éditoriale, choisie à la main.</small></label>
          <div className="two-cols"><label>Carte<select value={move.placement} onChange={e=>editMove({placement:e.target.value as 'left'|'right',cardX:undefined,cardY:undefined,cardWidth:undefined,iconX:undefined,iconY:undefined})}><option value="right">À droite</option><option value="left">À gauche</option></select></label><label>Zoom de pause<input type="number" step="0.005" min="1" max="1.12" value={move.zoom} onChange={e=>editMove({zoom:Number(e.target.value)})}/></label></div>
          <details><summary>Placement précis · en % de l’image</summary>{([['cardX','Carte · horizontal',move.placement==='right'?68.2:12],['cardY','Carte · vertical',move.placement==='right'?33.3:22.2],['cardWidth','Largeur de carte',move.placement==='right'?29.2:26],['iconX','Icône · horizontal',move.placement==='right'?60.2:79.3],['iconY','Icône · vertical',move.placement==='right'?12.8:31]] as const).map(([key,label,fallback])=><label key={key}>{label}<input type="number" min={key==='cardWidth'?20:0} max={key==='cardWidth'?45:90} step="0.1" value={move[key] ?? fallback} onChange={e=>editMove({[key]:Number(e.target.value)})}/></label>)}</details>
          <button className="danger" onClick={()=>{editShot({moves:shot.moves.filter(m=>m.id!==move.id)});setMoveId('');}}>Supprimer ce coup</button>
        </> : <>
          <label>Chaîne<select value={project.profile} onChange={e=>edit(p=>{p.profile=e.target.value;})}>{Object.entries(PROFILES).map(([key,v])=><option key={key} value={key}>{v.name}</option>)}</select></label>
          {project.players.map((p,i)=><div key={i} className="player-settings"><label>{i===0?'Pièces blanches':'Pièces noires'}<input value={p.name} maxLength={36} onChange={e=>edit(x=>{x.players[i].name=e.target.value;})}/></label><div className="portrait-upload">
            {p.portrait?<img src={`/${p.portrait}`} alt={p.name}/>:<span>♟</span>}<label className="file-label">Choisir une tête<input type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={e=>{const f=e.target.files?.[0];if(f)guarded(async()=>{const form=new FormData();form.append('file',f);const r=await api('/api/portrait',{method:'POST',body:form});edit(x=>{x.players[i].portrait=r.path;});});}}/></label>{p.portrait&&<button aria-label="Retirer le portrait" onClick={()=>edit(x=>{x.players[i].portrait='';})}>×</button>}</div></div>)}
          {shot && <div className="shot-trim"><h3>Extrait sélectionné</h3><div className="two-cols"><label>Entrée (s)<input type="number" step="0.01" value={shot.in} onChange={e=>editShot({in:Number(e.target.value)})}/></label><label>Sortie (s)<input type="number" step="0.01" value={shot.out} onChange={e=>editShot({out:Number(e.target.value)})}/></label></div>
            <label>Volume original<input type="range" min="0" max="1" step="0.05" value={shot.volume} onChange={e=>editShot({volume:Number(e.target.value)})}/></label>
            <small>Place les pauses à la fin des répliques.</small><button onClick={addMove}>Ajouter une analyse</button></div>}
          <div className="two-cols"><label>Export<select value={project.resolution} onChange={e=>edit(p=>{p.resolution=Number(e.target.value);})}><option value="1080">1080p</option><option value="2160">4K</option></select></label><label>Cadence<select value={project.fps} onChange={e=>edit(p=>{p.fps=Number(e.target.value);})}>{[24,25,30,50,60].map(f=><option key={f} value={f}>{f} i/s</option>)}</select></label></div>
          <label>Icônes<select value={project.iconSet} onChange={e=>edit(p=>{p.iconSet=e.target.value;})}><option value="chesscom">Chess.com · SVG originaux</option><option value="notation">Notation classique</option></select></label>
          <label className="checkbox"><input type="checkbox" checked={project.sfx} onChange={e=>edit(p=>{p.sfx=e.target.checked;})}/> Bruitages discrets</label>
          <label className="checkbox"><input type="checkbox" checked={!!project.showPawn} onChange={e=>edit(p=>{p.showPawn=e.target.checked;})}/> Ajouter le pion de commentaire</label>
          <button onClick={downloadProject}>Enregistrer le découpage JSON</button>
        </>}</>}
        {!project && <p className="muted">Crée un projet pour préparer les personnages et le montage.</p>}
      </aside>
    </main>
    {reviewMedia && <div className="source-modal-backdrop"><section className="source-modal" role="dialog" aria-modal="true" aria-label="Vérifier la source"><div className="section-head"><h2>Vérifier la source</h2><button aria-label="Fermer la vérification" onClick={()=>setReviewMedia(null)}>×</button></div><strong>{reviewMedia.name}</strong>
      <video src={`/${reviewMedia.src}`} controls preload="metadata"/>
      <p>Regarde le clip entier, y compris les quatre coins. La planche donne seulement un aperçu ; elle ne garantit pas l’absence de marquage entre deux images.</p>
      {sheet && <a href={`/${sheet}`} target="_blank" rel="noreferrer"><img src={`/${sheet}`} alt="Douze images de la source"/></a>}
      {([['watchedEntirely','J’ai regardé tout le clip'],['noLogo','Aucun logo ni watermark incrusté'],['noText','Aucun texte ni sous-titre incrusté']] as const).map(([key,label])=><label className="checkbox" key={key}><input type="checkbox" checked={reviewChecks[key]} onChange={e=>setReviewChecks({...reviewChecks,[key]:e.target.checked})}/>{label}</label>)}
      <label>Notes<textarea value={reviewNotes} onChange={e=>setReviewNotes(e.target.value)} maxLength={500}/></label><div className="review-actions"><button className="danger" onClick={()=>guarded(()=>recordReview('rejected'))}>Écarter cette source</button><button className="primary" disabled={busy || !Object.values(reviewChecks).every(Boolean)} onClick={()=>guarded(()=>recordReview('approved'))}>Valider la source propre</button></div>
    </section></div>}
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
