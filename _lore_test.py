# Test end-to-end du worker Lore Maxxing (worker.kanye.studio) via le contrat du studio.
import json, os, time, urllib.request
env={}
for l in open(".env",encoding="utf-8"):
    l=l.strip()
    if l and not l.startswith("#") and "=" in l:
        k,v=l.split("=",1); env[k.strip()]=v.strip()
URL=env["LORE_WORKER_URL"].rstrip("/"); TOK=env["LORE_WORKER_TOKEN"]
H={"x-worker-token":TOK}
def req(path, method="GET", body=None):
    data=json.dumps(body).encode() if body is not None else None
    h=dict(H)
    if body is not None: h["Content-Type"]="application/json"
    r=urllib.request.Request(URL+path, data=data, method=method, headers=h)
    with urllib.request.urlopen(r, timeout=60) as x: return json.loads(x.read().decode())

body={"title":"5 Useless Facts About Eric Cartman","franchise":"southpark","facts":5,"lang":"en","clip":True}
print("SUBMIT:", json.dumps(body), flush=True)
job=req("/render","POST",body).get("jobId")
print("jobId:", job, flush=True)
last=None
for i in range(120):
    time.sleep(15)
    s=req("/jobs/"+job)
    st=s.get("status")
    if st!=last: print(f"[{i*15}s] status={st}"+(f" mp4={s.get('mp4')}" if s.get('mp4') else ""), flush=True); last=st
    if st=="done":
        os.makedirs("out",exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(URL+s["mp4"],headers=H),timeout=300) as x, open("out/lore_test.mp4","wb") as f:
            f.write(x.read())
        print("DONE out/lore_test.mp4", os.path.getsize("out/lore_test.mp4")//1024//1024,"Mo", flush=True)
        try: req("/jobs/"+job,"DELETE"); print("DELETE ok (espace worker libéré)", flush=True)
        except Exception as e: print("delete err", e, flush=True)
        break
    if st=="failed":
        print("FAILED:", s.get("error"), flush=True); break
else:
    print("TIMEOUT", flush=True)
