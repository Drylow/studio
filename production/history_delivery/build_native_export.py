#!/usr/bin/env python3
"""Build the final native-export binding from completed actual root proofs, offline only."""
import argparse,importlib.util,json,pathlib
BASE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('delivery',BASE/'gofile_delivery.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def artifact(path):
 p=pathlib.Path(path).resolve();return {'path':str(p),'sha256':m.hashes(p)['sha256']}
def json_file(entry):
 p=pathlib.Path(entry['path']).resolve();m.require(m.hashes(p)['sha256']==entry['sha256'],'Actual proof SHA differs');return json.loads(p.read_text())
def pin(path,expected):
 p=pathlib.Path(path).resolve();m.require(m.hashes(p)['sha256']==expected,'Actual artifact SHA differs');return p
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',type=pathlib.Path,required=True);p.add_argument('--provider-proof',type=pathlib.Path,required=True);p.add_argument('--download-receipt',type=pathlib.Path,required=True);p.add_argument('--mastering-proof',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args()
cfg=json.loads(a.profile.read_text());ep=pathlib.Path(cfg['base']);master_path=a.mastering_proof or ep/'delivery/audio-only-mastering.json';master=json_file(artifact(master_path));provider=json_file(artifact(a.provider_proof));combined=ep/'combined-actual-source-review.json';source=json_file(artifact(combined));selected=sorted(source['records'],key=lambda x:x['id'])
plan=ep/'vps-adoption/exact-authored-scenes-new-vps-clock.json';adoption=ep/'vps-adoption/voice-adoption.json';import_entry=provider['source_artifacts']['native_import_manifest'];import_manifest=json_file(import_entry)
raw=provider['official_native_render']['raw_native_api_base'];final=provider['official_native_render']['final_derived_movie'];observed_frames=int(final['ffprobe']['video_streams'][0]['nb_frames']);m.require(observed_frames==cfg['frames'],'Observed final native frames differ')
result={'state':'complete','engine':'tubeforge-native-api+audio-mastering','project_id':cfg['project_id'],
 'absolute_file':str(pathlib.Path(master['final_path']).resolve()),'sha256':master['final_sha256'],
 'scene_count':cfg['scenes'],'source_plan_sha256':artifact(plan)['sha256'],'source_review_sha256':artifact(combined)['sha256'],
 'scene_image_sha256s':[r['image_sha256'] for r in selected],'info':{'frames':observed_frames},
 'native_import':{'path':import_entry['path'],'sha256':import_entry['sha256']},'provider_render_proof':artifact(a.provider_proof),
 'native_base':{'path':str(pathlib.Path(master['native_base_path']).resolve()),'sha256':master['native_base_sha256'],'download_receipt':artifact(a.download_receipt)},
 'audio_mastering':artifact(master_path),'voice_adoption_sha256':artifact(adoption)['sha256'],
 'delivery_notice':'Native VPS visual render, then separately authorized audio level mastering and audio-only remux. Video packets/timing copied exactly; delivered SHA is the mastered final, not the raw API base.'}
pin(result['absolute_file'],result['sha256']);clock=json.loads((ep/'vps-adoption/native-aligned-words.json').read_text());m.MASTERING.validate(result,cfg,cfg['scenes'],cfg['frames'],pin,json_file,m.require,import_manifest,provider,clock)
out=a.output or ep/'delivery/native-export-binding.json'
if out.exists():m.require(json.loads(out.read_text())==result,'Existing native export binding differs; inspect before replacing')
else:m.save(out,result)
print(json.dumps({'state':'actual_native_base_and_mastered_final_bound','episode':cfg['episode'],'output':str(out),'sha256':m.hashes(out)['sha256'],'network_calls':0,'uploads':0}))
