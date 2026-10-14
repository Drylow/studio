"""Resume only genuinely reviewed shots through the unchanged native renderer.

This executor does no creative writing, image generation or publication. It
retains each completed clip and refuses final assembly until all 108 pass.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import av
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'app'
EPISODE = Path('/workspace/samurai-chapters-regeneration/episode-01')
sys.path.insert(0,str(APP))
from app import store

FPS, WIDTH, HEIGHT = 24, 1920, 1080
MOTIONS = {'zoom_in','zoom_out','pan_left','pan_right','pan_up','pan_down','static'}

def digest(path):
    hasher = hashlib.sha256()
    with open(path,'rb') as stream:
        for data in iter(lambda: stream.read(1024*1024),b''):
            hasher.update(data)
    return hasher.hexdigest()

def atomic_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n')
    temporary.replace(path)

def frame_info(path):
    with av.open(str(path)) as container:
        stream=container.streams.video[0]
        return {'frames':stream.frames,'fps':float(stream.average_rate),
                'width':stream.codec_context.width,'height':stream.codec_context.height,
                'codec':stream.codec_context.name}

def read_plan(path, expected_sha, project):
    assert digest(path)==expected_sha,'Root release plan hash changed'
    data=json.loads(path.read_text())
    scenes=data['scenes']
    assert len(scenes)==108 and [s['id'] for s in scenes]==list(range(1,109))
    assert data.get('project_id')==project['id'],'Plan bound to another project'
    native=data.get('native',{})
    if native.get('project_id'):
        assert native['project_id']==project['id'],'Plan bound to another project'
    frames=0
    for source,current in zip(scenes,project['scenes'],strict=True):
        assert source['id']==current['id'] and source['text']==current['text']
        assert abs(source['start']-current['start'])<1e-6
        assert abs(source['end']-current['end'])<1e-6
        assert source['prompt'].strip() and source.get('prompt_author')=='codex'
        assert source['motion'] in MOTIONS,'Root must select a supported native motion'
        assert source.get('references'),'Explicit references required'
        for reference in source['references']:
            assert digest(reference['path'])==reference['sha256'],'Bound reference changed'
        start=round(source['start']*FPS);end=round(source['end']*FPS)
        assert start==frames and end>start
        frames=end
    assert frames==round(project['voiceover']['duration']*FPS)==28297
    return data,scenes

def reviewed_sources(path,scenes):
    data=json.loads(path.read_text())
    selected={}
    by_id={s['id']:s for s in scenes}
    for record in data['records']:
        sid=record['id']
        if record.get('state')!='pass':
            continue
        assert sid in by_id and sid not in selected
        assert record.get('reviewer') and record.get('notes'),'Actual reviewer and findings required'
        image=Path(record['image']).resolve()
        assert image.is_file() and digest(image)==record['image_sha256']
        assert record.get('request_sha256') or record.get('tool_provenance'), 'Actual generation provenance required'
        selected[sid]=dict(record,image=str(image))
    return selected

def native_integrity():
    evidence=json.loads((ROOT/'native-source-integrity.json').read_text())
    for row in evidence['render_implementation']:
        assert digest(APP/'app'/row['file'])==row['installed_sha256']
    return evidence['render_implementation']

def render_one(scene,record,implementation,clips,preset,crf):
    n=round(scene['end']*FPS)-round(scene['start']*FPS)
    binding={'scene_id':scene['id'],'image_sha256':record['image_sha256'],
             'frames':n,'fps':FPS,'width':WIDTH,'height':HEIGHT,
             'motion':scene['motion'],'strength':1.0,'preset':preset,'crf':crf,
             'implementation':implementation}
    signature=hashlib.sha256(json.dumps(binding,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    directory=clips/f"{scene['id']:04d}"/signature
    directory.mkdir(parents=True,exist_ok=True)
    output=directory/'clip.mp4'
    receipt=directory/'completion.json'
    if output.is_file() and receipt.is_file():
        completion=json.loads(receipt.read_text())
        assert completion['binding']==binding
        assert digest(output)==completion['clip_sha256']
        info=frame_info(output)
        assert info['frames']==n and info['width']==WIDTH and info['height']==HEIGHT and info['fps']==24
        return completion | {'reused':True}
    job={'width':WIDTH,'height':HEIGHT,'fps':FPS,'out':str(output),
         'ffmpeg':imageio_ffmpeg.get_ffmpeg_exe(),'strength':1.0,
         'captions':[],'per_scene':True,'preset':preset,'crf':crf,
         'scenes':[{'image':record['image'],'frames':n,'motion':scene['motion'],
                    'f0':round(scene['start']*FPS),'out':str(output)}]}
    job_path=directory/'native-job.json';atomic_json(job_path,job)
    started=time.time()
    with (directory/'native-render.log').open('wb') as log:
        subprocess.run([str(ROOT/'venv/bin/python'),'-m','app.render_worker',str(job_path)],
                       cwd=APP,stdout=log,stderr=subprocess.STDOUT,check=True)
    info=frame_info(output)
    assert info['frames']==n and info['width']==WIDTH and info['height']==HEIGHT and info['fps']==24
    result={'binding':binding,'scene_id':scene['id'],'clip':str(output),
            'clip_sha256':digest(output),'info':info,'elapsed_seconds':time.time()-started,
            'review_record':record,'completed_at_epoch':time.time()}
    atomic_json(receipt,result)
    return result | {'reused':False}

def import_reviewed(project,scenes,selected):
    pdir=store.project_dir(project['id'])
    for scene in scenes:
        current=project['scenes'][scene['id']-1]
        current.update(scene)
        record=selected.get(scene['id'])
        if not record:
            if current.get('image'):
                current.setdefault('reviewed_image_history',[]).append(current['image'])
                current['image']=None
                current['human_review']={'state':'unreviewed'}
            continue
        target=pdir/'reviewed-images'/f"{scene['id']:04d}-{record['image_sha256']}.png"
        target.parent.mkdir(exist_ok=True)
        if not target.exists():
            os.link(record['image'],target)
        assert digest(target)==record['image_sha256']
        current.update(image=target.relative_to(pdir).as_posix(),
                       human_review={'state':'verified','image_sha256':record['image_sha256'],
                                     'reviewer':record['reviewer'],'notes':record['notes']},
                       selected_source_provenance=record,status='done')
    store.save_project(project)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--plan-sha256',required=True)
    parser.add_argument('--reviews',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--crf',type=int,default=18)
    parser.add_argument('--preset',default='veryfast')
    parser.add_argument('--validate-only',action='store_true')
    parser.add_argument('--assemble',action='store_true')
    args=parser.parse_args()
    assert 1<=args.workers<=4 and 0<=args.crf<=28
    metadata=json.loads((EPISODE/'native-project-bootstrap.json').read_text())
    project=store.get_project(metadata['project_id'])
    data,scenes=read_plan(args.plan,args.plan_sha256,project)
    selected=reviewed_sources(args.reviews,scenes)
    implementation=native_integrity()
    if args.validate_only:
        print(json.dumps({'valid_plan':True,'reviewed_pass_count':len(selected),'total_scenes':108,
                          'native_implementation_unchanged':True,'render_started':False}))
        return
    clips=EPISODE/'native-scene-clips'
    clips.mkdir(exist_ok=True)
    render_lock=(clips/'native-render.lock').open('a')
    fcntl.flock(render_lock,fcntl.LOCK_EX)
    import_reviewed(project,scenes,selected)
    progress_path=clips/'progress.json'
    completed={}
    if progress_path.exists():
        previous=json.loads(progress_path.read_text())
        for item in previous.get('clips',[]):
            sid=item['scene_id']
            if sid not in selected:
                continue
            binding=item['binding'];scene=scenes[sid-1]
            if (binding['image_sha256']==selected[sid]['image_sha256']
                    and binding['motion']==scene['motion']
                    and binding['frames']==round(scene['end']*FPS)-round(scene['start']*FPS)
                    and binding['crf']==args.crf and binding['preset']==args.preset
                    and binding['implementation']==implementation
                    and Path(item['clip']).is_file()
                    and digest(item['clip'])==item['clip_sha256']):
                completed[sid]=item
    atomic_json(progress_path,{'state':'rendering','selected_pass_count':len(selected),
                              'completed':len(completed),'total':108,'plan_sha256':args.plan_sha256,
                              'clips':sorted(completed.values(),key=lambda r:r['scene_id'])})
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending=[pool.submit(render_one,s,selected[s['id']],implementation,clips,args.preset,args.crf)
                 for s in scenes if s['id'] in selected]
        for future in as_completed(pending):
            result=future.result();completed[result['scene_id']]=result
            atomic_json(progress_path,{'state':'rendering','selected_pass_count':len(selected),
                                      'completed':len(completed),'total':108,
                                      'plan_sha256':args.plan_sha256,'clips':sorted(completed.values(),key=lambda r:r['scene_id'])})
            if not result.get('reused'):
                print(f"Native clips verified {len(completed)}/{len(selected)} reviewed",flush=True)
    results=sorted(completed.values(),key=lambda r:r['scene_id'])
    atomic_json(progress_path,{'state':'reviewed_clips_complete','selected_pass_count':len(selected),
                              'completed':len(results),'total':108,'plan_sha256':args.plan_sha256,'clips':results})
    if not args.assemble:
        return
    assert len(selected)==len(results)==108,'Final assembly requires every actual image PASS'
    assert [r['scene_id'] for r in results]==list(range(1,109))
    out=store.project_dir(project['id'])/'render';out.mkdir(exist_ok=True)
    concat=out/'native-clips-concat.txt'
    concat.write_text(''.join("file '"+r['clip'].replace("'","'\\''")+"'\n" for r in results))
    audio=store.project_dir(project['id'])/project['voiceover']['file']
    assert digest(audio)==metadata['derived_voice_sha256']
    target=out/'final.mp4'
    release_path=EPISODE/'native-export-completion.json'
    clip_hashes=[r['clip_sha256'] for r in results]
    if target.exists():
        assert release_path.exists(),'Existing final export has no completion proof; preserve it'
        previous=json.loads(release_path.read_text())
        assert previous['source_plan_sha256']==args.plan_sha256
        assert previous['clip_sha256s']==clip_hashes
        assert previous['sha256']==digest(target)
        print(json.dumps(previous | {'assembly_reused':True}))
        return
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-nostdin','-y','-f','concat',
                    '-safe','0','-i',str(concat),'-i',str(audio),'-map','0:v','-map','1:a',
                    '-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',str(target)],check=True)
    info=frame_info(target);assert info['frames']==28297
    movie={'file':'render/final.mp4','duration':28297/FPS,'width':WIDTH,'height':HEIGHT,
           'sha256':digest(target),'source_plan_sha256':args.plan_sha256,'actual_qa_state':'pending',
           'clip_sha256s':clip_hashes}
    project['render']=movie;project['steps']['render'].update(state='done',done=108,total=108,
                      msg='Native export complete; final image and audio review still pending')
    store.save_project(project)
    atomic_json(release_path,movie | {'absolute_file':str(target),'info':info})
    print(json.dumps(movie))

if __name__=='__main__':
    main()
