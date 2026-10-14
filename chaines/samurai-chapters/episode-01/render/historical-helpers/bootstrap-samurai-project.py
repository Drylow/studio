"""Create one isolated manual Samurai project; never generate content."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'app'
OUTPUT = Path('/workspace/samurai-chapters-regeneration/episode-01')
SCRIPT = Path('/workspace/recovery/text-history/narration-spoken.txt')
SCRIPT_SHA = 'f2d0e1be63b96bb524de524b61f35623ae2618c25f09645afe619e76d1fde3a9'
VOICE = Path('/workspace/recovery/voice-history/samurai-native-derived-voice.mp3')
VOICE_SHA = '976f1493619e9266301dc772af362f5a7fe5602433f2a8b66cc728fd1e3a2671'
DERIVED = ROOT / 'voice-derived/samurai-original-level-normalized.flac'
TITLE = 'Why Being a Samurai Was Worse Than You Think'
sys.path.insert(0,str(APP))
from app import config,store
from app.util import now,read_json,write_json

assert hashlib.sha256(SCRIPT.read_bytes()).hexdigest() == SCRIPT_SHA
assert hashlib.sha256(VOICE.read_bytes()).hexdigest() == VOICE_SHA
proof = OUTPUT / 'native-project-bootstrap.json'
if proof.exists():
    saved = json.loads(proof.read_text())
    assert store.get_project(saved['project_id']) is not None
    print(json.dumps(saved))
    raise SystemExit(0)
OUTPUT.mkdir(parents=True,exist_ok=True)
sid='samurai-regeneration-style-'+uuid.uuid4().hex[:8]
cid='samurai-regeneration-channel-'+uuid.uuid4().hex[:8]
style=store.default_style(sid,'Samurai Chapters — regeneration')
style.update(workspace_managed=True,workspace_authoring_mode='codex_directed',
             workspace_image_provider='cli_proxy',language='English')
# The root director supplies every literal scene prompt and inspected identity.
# No generic style prompt is adopted for automatic planning or generation.
style['visuals'].update(art_style='',aspect='16:9',captions=False,auto_characters=False,
                       render_backend='native',motion_strength=1.0,image_provider='cli_proxy',
                       use_character_refs=True,image_model='')
style['voice'].update(provider='algrow',voice_id='rU18Fk3uSDhmg5Xh41o4',
                      voice_name='Existing original narrator',speed=1.0)
style['thumbnail'].update(count=0,image_provider='cli_proxy',model='')
store.save_style(style)
channels_file=config.DATA/'channels.json'
channels=read_json(channels_file,[])
channels.append({'id':cid,'name':'Samurai Chapters','language':'English','kind':'long',
                 'style_id':sid,'workspace_managed':True,'archived':False,
                 'auto_resolve':False,'target_minutes':20,'created':now(),
                 'voice':copy.deepcopy(style['voice'])})
write_json(channels_file,channels)
project=store.create_project(TITLE,sid,mode='review',custom_script=SCRIPT.read_text().strip())
pid=project['id']
pdir=store.project_dir(pid)
audio=pdir/'voiceover';audio.mkdir(exist_ok=True)
for src,dst in ((VOICE,audio/'original.mp3'),(DERIVED,audio/'narration.flac')):
    os.link(src,dst)
normalization=json.loads((DERIVED.parent/'normalization-proof.json').read_text())
write_json(audio/'normalization-proof.json',normalization)
project.update(codex_directed=True,channel_id=cid,channel_name='Samurai Chapters',
               workspace_authoring_mode='codex_directed',regenerated_after_environment_loss=True,
               original_source_script_sha256=SCRIPT_SHA)
project['voiceover']={'file':'voiceover/narration.flac','path':'voiceover/narration.flac','duration':1179.0367346938776,
                     'provider':'algrow','voice_id':'rU18Fk3uSDhmg5Xh41o4',
                     'source_original_path':'voiceover/original.mp3',
                     'source_original_sha256':VOICE_SHA,
                     'sha256':normalization['derived_sha256'],
                     'restored_original_voice':True,'new_paid_tts_calls':0,
                     'level_only_derivation':normalization}
project['steps']['voiceover'].update(state='done',msg='Original voice restored; exact duration and decode verified',done=1,total=1)
project['steps']['visuals'].update(state='idle',msg='Awaiting root-authored bound plan and actual image reviews',done=0,total=108)
store.save_project(project)
result={'schema':'samurai-native-regeneration-bootstrap-v1','project_id':pid,
        'project_dir':str(pdir),'style_id':sid,'channel_id':cid,'title':TITLE,
        'native_root':str(APP),'native_python':str(ROOT/'venv/bin/python'),
        'script_sha256':SCRIPT_SHA,'original_voice_sha256':VOICE_SHA,
        'derived_voice_sha256':normalization['derived_sha256'],
        'source_duration_seconds':1179.0367346938776,'fps':24,
        'width':1920,'height':1080,'new_paid_calls':0,
        'model_and_cast_binding':'Pending root final plan; no model selection or auto rewriting'}
proof.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
