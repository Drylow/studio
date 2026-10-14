"""Download a completed own native VPS base and retain exact origin/byte proof."""

if not __debug__:
    raise RuntimeError('Evidence tools require normal Python; optimization disables critical checks')
import argparse,datetime,hashlib,importlib.util,json,os,re,subprocess,tempfile
from pathlib import Path
def digest(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--project-id',required=True)
p.add_argument('--output-dir',type=Path,required=True)
p.add_argument('--expected-frames',type=int,required=True)
a=p.parse_args();pid=a.project_id;slug=pid
folder=a.output_dir.resolve();folder.mkdir(parents=True,exist_ok=True);folder.chmod(0o700)
s=importlib.util.spec_from_file_location('forge',Path(__file__).resolve().parents[1]/'tubeforge_support/forge_docs/forge.py');f=importlib.util.module_from_spec(s);s.loader.exec_module(f)
s=importlib.util.spec_from_file_location('ct',Path(__file__).with_name('curl_transport.py'));ct=importlib.util.module_from_spec(s);s.loader.exec_module(ct);request=ct.bind(f)
url=f.BASE+'/videos/'+__import__('urllib.parse',fromlist=['quote']).quote(pid,safe='')+'/download?kind=video'
with request('GET',f.BASE+'/videos/'+pid) as response:project=json.load(response)
assert not project.get('running') and project.get('render') and project['steps']['render']['state']=='done','Native render not complete'
for kind,endpoint in [('project',f.BASE+'/videos/'+pid),('outputs',f.BASE+'/videos/'+pid+'/outputs')]:
 with request('GET',endpoint) as response:payload=json.load(response)
 out=folder/(kind+'.json');out.write_text(json.dumps(payload,indent=2));out.chmod(0o600)
reported_video=payload.get('video')
if isinstance(reported_video,str):
 url=f.HOST+reported_video if reported_video.startswith('/') else reported_video
 parsed=__import__('urllib.parse',fromlist=['urlparse']).urlparse(url)
 assert parsed.scheme=='https' and parsed.netloc==__import__('urllib.parse',fromlist=['urlparse']).urlparse(f.HOST).netloc,'Refusing media credentials outside portal'
final=folder/'native-base.mp4';receipt_path=folder/'native-base-download-receipt.json'
if final.exists() and receipt_path.exists():
 old=json.loads(receipt_path.read_text())
 if digest(final)==old['sha256'] and old.get('project_id')==pid and old.get('method')=='GET' and old.get('endpoint')==url and old.get('actual_video_frames')==a.expected_frames:
  print(slug,'verified native base already downloaded',final);raise SystemExit(0)
assert not final.exists(), 'Unproved final base exists; preserve it for inspection'
part=folder/'native-base.mp4.part';transfers=[];total=None
while total is None or part.stat().st_size<total:
 offset=part.stat().st_size if part.exists() else 0
 fd,header_name=tempfile.mkstemp(prefix='native-download-headers-',dir=folder);os.close(fd)
 chunk=folder/'native-base-download-chunk.part'
 config='header = '+json.dumps('Authorization: Bearer '+f.token())+'\n'
 config+='header = "Accept: video/mp4"\n'
 if offset:config+='header = '+json.dumps('Range: bytes='+str(offset)+'-')+'\n'
 try:
  result=subprocess.run(['curl','--http2','--silent','--show-error','--max-time','180','--config','-','--output',str(chunk),'--dump-header',header_name,'--write-out','%{http_code}',url],input=config.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  if result.returncode:raise RuntimeError('Official media download failed; curl exit '+str(result.returncode))
  code=int(result.stdout);raw=Path(header_name).read_text(errors='replace');blocks=re.split(r'\r?\n\r?\n',raw.strip());last=next((x for x in reversed(blocks) if x.startswith('HTTP/')),None)
  assert last,'Download headers absent'
  headers={}
  for line in last.splitlines()[1:]:
   if ':' in line:
    k,v=line.split(':',1);headers[k.lower().strip()]=v.strip()
  actual=chunk.stat().st_size;content_range=headers.get('content-range')
  if code==206:
   match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',content_range or '');assert match,'Partial response has no valid range'
   start,end,total=map(int,match.groups());assert start==offset and actual==end-start+1,'Official download range/size mismatch'
   with part.open('ab') as out,chunk.open('rb') as source:
    import shutil;shutil.copyfileobj(source,out)
  elif code==200:
   assert 'content-length' in headers,'Full download lacks byte length'
   total=int(headers['content-length']);assert actual==total,'Full response was truncated'
   chunk.replace(part)
  else:raise RuntimeError('Official media download returned HTTP '+str(code))
  transfers.append({'http_status':code,'offset':offset,'bytes':actual,'content_range':content_range,'reported_total':total})
  print(slug,'native base bytes received',part.stat().st_size,'of',total,flush=True)
 finally:
  Path(header_name).unlink(missing_ok=True);chunk.unlink(missing_ok=True)
assert part.stat().st_size==total
part.replace(final)
sha=digest(final)
probe=subprocess.check_output([os.environ.get('HISTORY_FFPROBE','ffprobe'),'-v','error','-show_streams','-show_format','-of','json',str(final)],text=True)
probe_data=json.loads(probe);video=next(s for s in probe_data['streams'] if s['codec_type']=='video')
assert video['width']==1920 and video['height']==1080 and video['avg_frame_rate']=='24/1'
expected=a.expected_frames
assert int(video['nb_frames'])==expected
receipt={'schema':'authenticated-native-vps-base-download-v1','project_id':pid,'official_get_endpoint':url,'endpoint':url,'method':'GET','local_path':str(final),'path':str(final),'sha256':sha,'bytes':total,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'transfers':transfers,'actual_video_frames':expected,'actual_video_fps':'24/1','actual_video_width':1920,'actual_video_height':1080,'audio_status':'Unmastered native base audio; final root audio-only mastering and actual final QA remain required.'}
receipt_path.write_text(json.dumps(receipt,indent=2));receipt_path.chmod(0o600)
(folder/'native-base-ffprobe.json').write_text(probe);(folder/'native-base-ffprobe.json').chmod(0o600)
print(slug,'native base fully downloaded',final,'bytes',total,'SHA256',sha,'observed1920x1080/24fps/frames',expected,flush=True)
