#!/usr/bin/env python3
"""Clearly labeled offline transport fixtures; no network and no real delivery claims."""
import contextlib,hashlib,importlib.util,io,json,pathlib,tempfile,types
from unittest.mock import patch
BASE=pathlib.Path(__file__).resolve().parent
TOOLS=BASE.parent
spec=importlib.util.spec_from_file_location('delivery',TOOLS/'gofile_delivery.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
class Reply:
 status_code=200
 def __init__(self,data):self.data=data
 def json(self):return {'status':'ok','data':self.data}
class Session:
 def __init__(self,kit,mode):self.kit=kit;self.mode=mode;self.posts=[];self.gets=[]
 def get(self,url,**kw):self.gets.append(url);return Reply({'servers':[{'name':'storefixture','zone':'eu'}]})
 def post(self,url,**kw):
  name=kw['files']['file'][0];self.posts.append(name)
  if self.mode=='uncertain':raise m.requests.Timeout('offline fixture')
  row=next(r for r in self.kit['files'] if r['filename']==name)
  data={'size':row['bytes'],'md5':'0'*32 if self.mode=='upload-md5' else row['md5'],'parentFolder':'fixture-folder','downloadPage':'https://gofile.io/d/Fixture7'}
  if self.mode=='changed-after-first' and len(self.posts)==1:pathlib.Path(self.kit['files'][1]['path']).write_bytes(b'changed offline fixture')
  return Reply(data)
def fixture(state):
 state.mkdir();state.chmod(0o700);rows=[]
 for role in ['video','thumbnail_a','thumbnail_b','thumbnail_c','thumbnail_d','upload_text','captions']:
  p=state/f'fixture-{role}.bin';p.write_bytes(('OFFLINE TRANSPORT FIXTURE '+role).encode());rows.append({'role':role,'path':str(p),**m.hashes(p)})
 m.save(state/'owner-private.json',{'owner_token':'offline-fixture-token'},private=True)
 m.save(state/'normal-site-preflight.json',{'listing_observed':True,'owner_private_file_present':True,'normal_guest_creation_posts':0,'file_uploads':0,'blocked_mutations':[]})
 return {'files':rows,'frozen':{r['path']:r['sha256'] for r in rows},'fingerprint':'fixture-fingerprint','manifest_sha256':'a'*64,'episode':'viking','movie_sha256':rows[0]['sha256']}
def run_case(state,mode):
 kit=fixture(state);session=Session(kit,mode)
 def site(command,**kwargs):
  expected=json.loads((state/'expected-listing-files.json').read_text());assert expected==[r['filename'] for r in kit['files']]
  png=state/'final-normal-site-readback.png';png.write_bytes(b'OFFLINE SCREENSHOT FIXTURE')
  files=[{'name':r['filename'],'type':'file','size':r['bytes'],'md5':r['md5']} for r in kit['files']]
  if mode=='readback-md5':files[-1]['md5']='0'*32
  listing={'folder_id':'fixture-folder','folder_type':'folder','folder_public':mode!='private-folder','http_status':200,'api_status':'ok','files':files,'metadata':{'totalCount':7,'totalPages':1,'page':1,'pageSize':100,'hasNextPage':False}}
  m.save(state/'final-normal-site-readback.json',{'public_url':'https://gofile.io/d/Fixture7','listing':listing,'listing_observed':True,'proof_verified':True,'complete_listing_observed':True,'all_expected_filenames_painted':True,'screenshot_created_this_run':True,'blocked_mutations':[],'blocked_authorization_requests':[],'normal_guest_creation_posts':0,'screenshot':str(png),'screenshot_sha256':m.hashes(png)['sha256']})
  return types.SimpleNamespace(returncode=0)
 if mode=='existing-pending':m.save(state/'pending-private.json',{'explicit':'offline old pending'},private=True)
 if mode=='changed-before-first':pathlib.Path(kit['files'][0]['path']).write_bytes(b'changed offline fixture')
 failed=False
 with patch.object(m.subprocess,'run',side_effect=site),contextlib.redirect_stdout(io.StringIO()):
  try:m.upload(kit,state,session)
  except (ValueError,RuntimeError):failed=True
  if mode=='success':assert m.existing_confirmed(kit,state) is True
 expected_posts={'success':7,'uncertain':1,'upload-md5':1,'readback-md5':7,'private-folder':7,'changed-before-first':0,'changed-after-first':1,'existing-pending':0}[mode]
 assert len(session.posts)==expected_posts and failed==(mode!='success')
 if mode!='success':assert not (state/'receipt.json').exists()
 if mode=='uncertain':
  assert (state/'pending-private.json').exists();before=len(session.posts)
  try:m.upload(kit,state,session)
  except ValueError:pass
  else:raise AssertionError('Uncertain upload incorrectly resumed')
  assert len(session.posts)==before
 checks.append({'case':mode,'passed':True,'mock_post_count':len(session.posts),'real_network_calls':0})
with tempfile.TemporaryDirectory(prefix='history-gofile-offline-',dir=BASE) as tmp:
 root=pathlib.Path(tmp)
 for mode in ['success','uncertain','upload-md5','readback-md5','private-folder','changed-before-first','changed-after-first','existing-pending']:run_case(root/mode,mode)
 state=root/'root-gate';kit=fixture(state)
 for expected in [None,'b'*64]:
  args=['helper','--manifest','fixture.json','--profile','fixture-profile.json','--state-dir',str(state),'--upload']+(['--manifest-sha256',expected] if expected else [])
  with patch('sys.argv',args),patch.object(m,'prepare',return_value=kit),patch.object(m.requests,'Session',side_effect=AssertionError('Network created before root SHA gate')):
   try:m.main()
   except ValueError:pass
   else:raise AssertionError('Missing/wrong ROOT SHA gate accepted')
  checks.append({'case':'missing-root-SHA' if expected is None else 'wrong-root-SHA','passed':True,'mock_post_count':0,'real_network_calls':0})
proof={'label':'OFFLINE MOCK TRANSPORT CHECKS; not actual uploads or remote proof','passed':len(checks),'failed':0,'real_network_calls':0,'real_uploads':0,'real_account_posts':0,'checks':checks};print(json.dumps(proof))
