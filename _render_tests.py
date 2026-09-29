# Tests end-to-end des nouveaux types chess via le worker du pote.
# Corps = ce que routes/worker.py _render_body produit (compilation / opening short).
import json, os, time, urllib.request, urllib.error

env = {}
for l in open(".env", encoding="utf-8"):
    l = l.strip()
    if l and not l.startswith("#") and "=" in l:
        k, v = l.split("=", 1); env[k.strip()] = v.strip()
BASE = env["REMOTION_WORKER_URL"].rstrip("/"); TOK = env["REMOTION_WORKER_TOKEN"]
HDR = {"Authorization": "Bearer " + TOK}

def get(path):
    r = urllib.request.Request(BASE + path, headers=HDR)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())

def post(path, body):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                               method="POST", headers={**HDR, "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read().decode())

print("HEALTH:", get("/health"), flush=True)

# count:3 sur la compilation = test plus rapide (la prod utilise le défaut 6).
TESTS = [
    ("out/en_game.mp4",
     {"type": "game", "query": "Opera Game - Morphy vs Duke of Brunswick 1858", "lang": "en"}),
    ("out/en_compilation.mp4",
     {"type": "compilation", "query": "the most beautiful queen sacrifices in chess history",
      "lang": "en", "depth": "highlight", "count": 3}),
    ("out/en_compilation_short.mp4",
     {"type": "compilation", "query": "the most shocking checkmate in chess history",
      "lang": "en", "depth": "highlight", "count": 1, "short": True}),
    ("out/en_opening.mp4",
     {"type": "opening", "query": "the Sicilian Najdorf", "lang": "en"}),
    ("out/en_opening_short.mp4",
     {"type": "opening", "query": "the Fried Liver Attack trap", "lang": "en", "short": True}),
]

jobs = []
for out, body in TESTS:
    try:
        r = post("/render-game", body)
        print("SUBMITTED", out, "->", r, flush=True)
        jobs.append((out, r.get("jobId")))
    except urllib.error.HTTPError as e:
        print("SUBMIT FAIL", out, e.code, e.read().decode()[:400], flush=True)

os.makedirs("out", exist_ok=True)
for out, job in jobs:
    if not job:
        continue
    last = None
    for i in range(200):   # ~50 min/job max
        time.sleep(15)
        try:
            st = get("/jobs/" + job)
        except Exception as e:
            print("poll err", e, flush=True); continue
        s = st.get("status")
        if s != last:
            print(f"[{out}] {i*15}s status={s}", flush=True); last = s
        if s == "done":
            with urllib.request.urlopen(urllib.request.Request(BASE + "/jobs/" + job + "/video", headers=HDR), timeout=300) as resp, open(out, "wb") as f:
                f.write(resp.read())
            print("DONE", out, os.path.getsize(out)//1024, "KB", flush=True); break
        if s == "error":
            print("ERROR", out, st.get("error"), "| log:", (st.get("log") or "")[-500:], flush=True); break
    else:
        print("TIMEOUT", out, flush=True)
print("ALL DONE", flush=True)
