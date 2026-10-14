"""Verified HTTP/2 HTTPS transport; uses the supplied personal client auth selector."""
import io,json,os,subprocess,tempfile,urllib.error,urllib.parse
from pathlib import Path
class Response(io.BytesIO):
 def __init__(self,data,status):super().__init__(data);self.status=status
 def __enter__(self):return self
 def __exit__(self,*args):self.close()
def bind(forge):
 def request(method,url,data=None,content_type='application/json',login=False):
  parsed=urllib.parse.urlparse(url)
  if parsed.scheme!='https' or parsed.netloc!=urllib.parse.urlparse(forge.HOST).netloc:
   raise ValueError('Refusing portal auth outside the authorized HTTPS portal')
  if login:raise ValueError('This transport is for existing authenticated sessions only')
  config='header = '+json.dumps('Authorization: Bearer '+forge.token())+'\n'
  config+='header = "Accept: application/json"\n'
  bodyfile=None
  command=['curl','--http2','--silent','--show-error','--max-time','90','--config','-','--request',method,'--write-out','\n%{http_code}\n',url]
  try:
   if data is not None:
    fd,bodyfile=tempfile.mkstemp(prefix='http2-body-',dir=os.environ.get('FORGE_PRIVATE_TMPDIR'))
    with os.fdopen(fd,'wb') as out:out.write(data)
    config+='header = '+json.dumps('Content-Type: '+content_type)+'\n'
    command+=['--data-binary','@'+bodyfile]
   result=subprocess.run(command,input=config.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   if result.returncode:
    raise OSError('HTTPS transport failed; curl exit '+str(result.returncode))
   payload,status=result.stdout.rsplit(b'\n',2)[:2]
   code=int(status)
   if code<200 or code>=300:
    raise urllib.error.HTTPError(url,code,'HTTP response',None,io.BytesIO(payload))
   return Response(payload,code)
  finally:
   if bodyfile:Path(bodyfile).unlink(missing_ok=True)
 return request
