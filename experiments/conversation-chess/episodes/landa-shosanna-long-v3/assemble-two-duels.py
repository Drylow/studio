import argparse, copy, hashlib, importlib.util, json, subprocess
from collections import Counter
from pathlib import Path

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576), b''): h.update(block)
    return h.hexdigest()

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-threads','4','-show_streams','-show_format','-of','json',str(path)]))

spec=importlib.util.spec_from_file_location('source_edit','experiments/conversation-chess/prepare-source-edit.py')
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)

p=argparse.ArgumentParser()
p.add_argument('--farm',type=Path,required=True)
p.add_argument('--restaurant',type=Path,required=True)
p.add_argument('--farm-captions',type=Path,required=True)
p.add_argument('--restaurant-captions',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
if a.out.exists(): p.error('Preserve old preparations; choose a new folder.')
chapters=[]
for folder in (a.farm,a.restaurant):
    source=folder/'scene-edit-1920x1080.mkv'
    timeline=json.loads((folder/'timeline.json').read_text())
    if sha(source)!=timeline['source_sha256']: raise ValueError('Prepared source changed.')
    meta=probe(source)
    video=next(s for s in meta['streams'] if s['codec_type']=='video')
    frames=round(timeline['source_out']*30)
    if timeline['source_in']!=0 or (video['width'],video['height'])!=(1920,1080) or video['r_frame_rate']!='30/1':
        raise ValueError('Need two frame-verified native 1080p, 30fps edited sources beginning at zero.')
    cut_map=json.loads((folder/'cut-map.json').read_text())
    clock=cut_map['clock_verification']['combined']
    if Path(cut_map['edited_source']).resolve()!=source.resolve() or cut_map['frames']!=frames or clock['video_frames']!=frames or clock['audio_samples_per_channel']!=frames*1600 or clock['maximum_timestamp_error_seconds']>.0011:
        raise ValueError('Each unchanged, hash-verified input needs its completed decoded clock receipt.')
    if timeline['opening']['speaker']!='white' or timeline['opening']['label']!='Landa': raise ValueError('Landa must actually open both retained conversations.')
    chapters.append((source,timeline,frames))
total_frames=sum(row[2] for row in chapters)
merged=copy.deepcopy(chapters[0][1])
merged.update(source_in=0,source_out=total_frames/30,annotations=[],conversations=[],source_sha256=None,initial_score_text='0.0',initial_control=.5)
cursor=0
for source,timeline,frames in chapters:
    opening=copy.deepcopy(timeline['opening'])
    opening['source_at']=cursor/30
    merged['conversations'].append({'source_at':cursor/30,'white_label':timeline['white_label'],'black_label':timeline['black_label'],'opening':opening,'initial_score_text':'0.0','initial_control':.5})
    for annotation in timeline['annotations']:
        grade=copy.deepcopy(annotation)
        grade['source_at']=(cursor+round(annotation['source_at']*30))/30
        merged['annotations'].append(grade)
    cursor+=frames
merged['opening']=copy.deepcopy(merged['conversations'][0]['opening'])
expected=total_frames/30+16+12+sum(x['hold_seconds'] for x in merged['annotations'])
if expected<600: raise ValueError(f'The authorised long video is still too short: {expected}')
merged.update(intro_seconds=16,outro_seconds=12,outro_style='recap',outro_layout_reviewed=False,
              dialogue_gain=0.7943282347242815,title='Landa’s Mind Games Analyzed Like Chess | Inglourious Basterds')
merged['outro_summary']=chapters[1][1]['outro_summary']
layout_path=Path('output/conversation-chess/landa-shosanna-long-v3-layout-review/layout-still-preflight-receipt.json')
layout=json.loads(layout_path.read_text())
counts=Counter(grade['rating'] for grade in merged['annotations'])
if not layout['visual_review']['graphics_layout_still_preflight_passed'] or any(counts[key]!=value for key,value in layout['combined_counts'].items()) or merged['outro_summary']!=layout['outro_summary']:
    raise ValueError('The actual reviewed recap layout/counts no longer match.')
merged['outro_layout_reviewed']=True
merged['outro_layout_review_evidence']={'file':str(layout_path),'sha256':sha(layout_path),'method':'Native recap and longest-comment stills actually opened by root; graphics layout only, final video review pending.'}
merged['source_quality']={'quality_target':1080,'accepted_for_final':True,'source_not_upscaled':True,'source_metadata_note':'Two visually sampled source chapters, both retained at1920x1080: official native1080p RT farmhouse footage and actual4K public-player excerpts downsampled to1080p. Original multilingual dialogue; no artificial upscale, mirror, concealment crop or pitch change. Public acquisition does not establish reuse rights or Content ID acceptance.'}
merged['source_edit']={'chapter_count':2,'chapters':[{'source':str(source),'source_sha256':timeline['source_sha256'],'source_frames':frames,'source_edit':timeline.get('source_edit')} for source,timeline,frames in chapters]}
merged['review_evidence']='Two reviewed, authored source edits; separate Landa/LaPadite and Landa/Shosanna conversation scopes. Sources and pause stills sampled visually; final-render review and private YouTube Checks remain required.'
merged['youtube_clearance_verified']=False
a.out.mkdir(parents=True)
listing=a.out/'parts.txt'
listing.write_text(''.join(f"file '{source.resolve()}'\nduration {frames/30:.12f}\n" for source,_,frames in chapters))
movie=a.out/'source-two-duels-1920x1080.mkv'
subprocess.run(['ffmpeg','-nostdin','-v','error','-n','-f','concat','-safe','0','-i',str(listing),'-map','0:v:0','-map','0:a:0','-c:v','copy','-r:v','30','-af',f'aresample=48000,asetpts=N/SR/TB,apad,atrim=end_sample={total_frames*1600}','-enc_time_base:a','1:48000','-c:a','pcm_s16le','-ar','48000','-ac','2',str(movie)],check=True)
meta=probe(movie)
video=next(s for s in meta['streams'] if s['codec_type']=='video')
if abs(float(meta['format']['duration'])-total_frames/30)>.002:
    raise ValueError('Combined picture duration/frame count drifted.')
clock_receipt=helper.verify_clock(movie,total_frames)
subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(movie),'-f','null','-'],check=True)
audio=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-i',str(movie),'-vn','-c:a','pcm_s16le','-f','s16le','-'],stdout=subprocess.PIPE)
audio_bytes=0
for block in iter(lambda:audio.stdout.read(1048576),b''): audio_bytes+=len(block)
if audio.wait()!=0 or audio_bytes!=total_frames*1600*4: raise ValueError('Combined PCM is not exactly frame-aligned.')
merged['source_sha256']=sha(movie)
(a.out/'timeline.json').write_text(json.dumps(merged,indent=2,ensure_ascii=False)+'\n')
subprocess.run(['.venv/bin/python','experiments/conversation-chess/merge-source-captions.py','--first',str(a.farm_captions),'--second',str(a.restaurant_captions),'--second-offset-frames',str(chapters[0][2]),'--fps','30','--out',str(a.out/'captions.source.en.srt')],check=True)
receipt={'source_file':str(movie),'source_sha256':merged['source_sha256'],'source_frames':total_frames,'source_audio_samples_per_channel':total_frames*1600,'clock_verification':clock_receipt,'restaurant_source_offset_frames':chapters[0][2],'full_decode_ok':True,'expected_final_seconds':expected,'annotation_count':len(merged['annotations']),'final_render_reviewed':False,'human_audio_listening':False,'youtube_clearance_verified':False}
(a.out/'assembly-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
