# Soumet la game-review Kasparov-Topalov 1999 au render worker du pote (/render-game),
# poll le job, télécharge le MP4. Lit URL+token depuis le .env du studio.
import json, time, os, urllib.request, urllib.error

env = {}
for l in open(".env", encoding="utf-8"):
    l = l.strip()
    if l and not l.startswith("#") and "=" in l:
        k, v = l.split("=", 1); env[k.strip()] = v.strip()
BASE = env["REMOTION_WORKER_URL"].rstrip("/")
TOK = env["REMOTION_WORKER_TOKEN"]
HDR = {"Authorization": "Bearer " + TOK, "Content-Type": "application/json"}

MOVES = ("1.e4 d6 2.d4 Nf6 3.Nc3 g6 4.Be3 Bg7 5.Qd2 c6 6.f3 b5 7.Nge2 Nbd7 8.Bh6 Bxh6 "
         "9.Qxh6 Bb7 10.a3 e5 11.O-O-O Qe7 12.Kb1 a6 13.Nc1 O-O-O 14.Nb3 exd4 15.Rxd4 c5 "
         "16.Rd1 Nb6 17.g3 Kb8 18.Na5 Ba8 19.Bh3 d5 20.Qf4+ Ka7 21.Rhe1 d4 22.Nd5 Nbxd5 "
         "23.exd5 Qd6 24.Rxd4 cxd4 25.Re7+ Kb6 26.Qxd4+ Kxa5 27.b4+ Ka4 28.Qc3 Qxd5 29.Ra7 "
         "Bb7 30.Rxb7 Qc4 31.Qxf6 Kxa3 32.Qxa6+ Kxb4 33.c3+ Kxc3 34.Qa1+ Kd2 35.Qb2+ Kd1 "
         "36.Bf1 Rd2 37.Rd7 Rxd7 38.Bxc4 bxc4 39.Qxh8 Rd3 40.Qa8 c3 41.Qa4+ Ke1 42.f4 f5 "
         "43.Kc1 Rd2 44.Qa7")

# Labels chess.com figés (= scripts/_overrides.mjs KASPAROV_TOPALOV_1999), ply 0-based.
OVERRIDES = {"46": "excellent", "48": "brilliant", "50": "best", "52": "excellent",
             "54": "brilliant", "56": "excellent", "58": "brilliant", "60": "best",
             "61": "blunder", "70": "brilliant", "72": "brilliant", "74": "best", "76": "best"}

body = {
    "white": {"name": "Garry Kasparov", "elo": 2812, "country": "ru"},
    "black": {"name": "Veselin Topalov", "elo": 2700, "country": "bg"},
    "result": "1-0",
    "event": "Wijk aan Zee 1999",
    "moves": MOVES,
    "fr": True,
    "overrides": OVERRIDES,
}

req = urllib.request.Request(BASE + "/render-game", data=json.dumps(body).encode(), method="POST")
for k, v in HDR.items():
    req.add_header(k, v)
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        sub = json.loads(r.read().decode())
except urllib.error.HTTPError as e:
    print("SUBMIT FAIL", e.code, e.read().decode()[:500]); raise SystemExit(1)
job = sub.get("jobId")
print("SUBMITTED job=", job, "->", sub, flush=True)
if not job:
    raise SystemExit(1)

last = None
for i in range(180):   # ~45 min max @ 15s
    time.sleep(15)
    jr = urllib.request.Request(BASE + "/jobs/" + job, headers={"Authorization": "Bearer " + TOK})
    try:
        with urllib.request.urlopen(jr, timeout=30) as r:
            st = json.loads(r.read().decode())
    except Exception as e:
        print("poll err", e); continue
    s = st.get("status")
    if s != last:
        print(f"[{i*15}s] status={s}" + (f" slug={st.get('slug')}" if st.get("slug") else ""), flush=True)
        last = s
    if s == "done":
        os.makedirs("out", exist_ok=True)
        out = "out/kasparov_topalov_review.mp4"
        vr = urllib.request.Request(BASE + "/jobs/" + job + "/video", headers={"Authorization": "Bearer " + TOK})
        with urllib.request.urlopen(vr, timeout=300) as r, open(out, "wb") as f:
            f.write(r.read())
        print("DONE ->", out, os.path.getsize(out) // 1024, "KB", flush=True)
        break
    if s == "error":
        print("ERROR:", st.get("error"), "\nlog tail:", (st.get("log") or "")[-800:], flush=True)
        break
else:
    print("TIMEOUT waiting for render", flush=True)
