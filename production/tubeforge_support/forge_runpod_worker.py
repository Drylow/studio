"""Single-job authenticated RunPod worker. All media operations happen in this pod."""
import hashlib,hmac,json,os,subprocess,tarfile,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

ROOT=Path('/job');ROOT.mkdir(exist_ok=True)
TOKEN=os.environ['WORKER_TOKEN'];state={'state':'ready','host':'RunPod','started_at':time.time()};lock=threading.Lock()
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def execute():
 try:
  with tarfile.open(ROOT/'input.tar') as tar:
   for m in tar.getmembers():
    if not m.isfile() or Path(m.name).is_absolute() or '..' in Path(m.name).parts:raise ValueError('Invalid bundle member')
   tar.extractall(ROOT/'input',filter='data')
  q=ROOT/'input';manifest=json.loads((q/'bundle-hashes.json').read_text())
  for rel,wanted in manifest.items():
   p=(q/rel).resolve();assert p.is_relative_to(q.resolve()) and digest(p)==wanted
  with (ROOT/'worker.log').open('wb') as log:
   p=subprocess.run(['python','render_worker.py','run'],cwd=ROOT/'input',stdout=log,stderr=log,timeout=2100,env=os.environ|{'RUNPOD_RENDER_HOST':'1'})
  if p.returncode:raise RuntimeError('Render worker failed; inspect private log')
  q=ROOT/'input';report=json.loads((q/'run/render-report.json').read_text())
  files=[q/'run/render-report.json',q/'project'/report['file'],ROOT/'worker.log']+[q/'project'/s['path']for s in report['sheets']]
  with tarfile.open(ROOT/'output.tar','w') as tar:
   for f in files:tar.add(f,arcname=f.relative_to(q).as_posix()if f.is_relative_to(q)else'worker.log')
  state.update(state='complete',sha256=digest(ROOT/'output.tar'),bytes=(ROOT/'output.tar').stat().st_size)
 except Exception as e:state.update(state='failed',error=type(e).__name__+': '+str(e))

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def auth(self):return hmac.compare_digest(self.headers.get('X-Worker-Token',''),TOKEN)
 def reply(self,code,data):
  b=json.dumps(data).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if not self.auth():return self.reply(401,{'error':'unauthorized'})
  if self.path=='/status':return self.reply(200,state)
  if self.path=='/log' and (ROOT/'worker.log').exists():
   b=(ROOT/'worker.log').read_bytes()[-100000:];self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  if self.path=='/result' and state['state']=='complete':
   f=ROOT/'output.tar';self.send_response(200);self.send_header('Content-Length',str(f.stat().st_size));self.end_headers()
   with f.open('rb')as src:
    for chunk in iter(lambda:src.read(1024*1024),b''):self.wfile.write(chunk)
   return
  return self.reply(404,{'error':'not ready'})
 def do_PUT(self):
  if not self.auth():return self.reply(401,{'error':'unauthorized'})
  if self.path!='/bundle':return self.reply(404,{})
  with lock:
   wanted=self.headers.get('X-SHA256','');f=ROOT/'input.tar'
   if f.exists():return self.reply(200 if digest(f)==wanted else 409,{'sha256':digest(f)})
   if state['state']!='ready':return self.reply(409,{'error':'already active'})
   remaining=int(self.headers.get('Content-Length','0'))
   if remaining<=0 or remaining>2*1024**3:return self.reply(400,{'error':'size'})
   tmp=ROOT/'input.partial'
   with tmp.open('wb')as out:
    while remaining:
     chunk=self.rfile.read(min(1024*1024,remaining))
     if not chunk:raise ConnectionError('Incomplete bundle')
     out.write(chunk);remaining-=len(chunk)
   if digest(tmp)!=wanted:return self.reply(400,{'error':'hash mismatch'})
   tmp.replace(f);state.update(state='uploaded',input_sha256=wanted);return self.reply(200,state)
 def do_POST(self):
  if not self.auth():return self.reply(401,{'error':'unauthorized'})
  if self.path!='/start':return self.reply(404,{})
  with lock:
   if state['state']=='uploaded':
    state['state']='rendering';threading.Thread(target=execute,daemon=True).start()
   return self.reply(200,state)

ThreadingHTTPServer(('0.0.0.0',8000),Handler).serve_forever()
