"""Vidéos d'actu sport (format Fight Night MMA, toutes les chaînes d'actu : MMA, boxe, foot…).

Un dossier par vidéo dans le dépôt : news/<chaîne>/<AAAA-MM-JJ>_<sujet>/ (plan, voix off, miniature,
planches de contrôle, résultat). Les sous-titres des sources (sources/) restent hors de git.

  # dans le cloud (ou sur PC)
  python production/news.py today mma_en [--hours 48]                            → histoires du jour (RSS + IA)
  python production/news.py new mma_en "Gaethje vs Topuria: the rematch saga"      → crée le dossier
  python production/news.py add <dossier> <id_youtube> [<id> …]                   → sous-titres (yt-dlp, PC)
  python production/news.py import <dossier> <fichier_nexlev.json> [meta.json]    → sous-titres NexLev (cloud)
  python production/news.py moments <dossier>                                     → moments.json (IA)
  python production/news.py plan <dossier> [--context "faits vérifiés"]           → plan.json (IA, citations vérifiées)
  python production/news.py headlines <dossier>                                  → bandeaux + fil d'actu (IA)
  python production/news.py voice <dossier>                                       → narration/nXXX.mp3 (Algrow)
  python production/news.py thumb <dossier>                                       → miniatures (planche)

  # sur le PC (YouTube y laisse télécharger) — ou double-clic sur NEWS_PC.bat
  python production/news.py pc        → git pull, monte chaque vidéo prête (plan + voix) sans résultat,
                                         Gofile, supprime les clips, git push du résultat et des planches
  python production/news.py build <dossier> [--no-upload] [--keep]

  # sur le VPS de l'utilisateur (production/vps_news_setup.sh) : tout depuis le cloud, rien à faire sur le PC
  python production/news.py vps-check                 → YouTube laisse-t-il télécharger depuis le VPS ?
  python production/news.py vps <dossier> [--no-wait] → envoie, monte, rapatrie lien + planches check/
  python production/news.py vps-fetch <dossier> [--wait]
  python production/news.py vps <dossier> --pc [--no-wait] → montage sur le PC de l'utilisateur (relais du VPS,
                                                    agent standalone/pc_agent, toutes les 15 min)
  python production/news.py pc-fetch <dossier> [--wait] → état du montage PC, rapatrie lien + planches

  # dans le cloud, après avoir regardé les planches check/
  python production/news.py send <dossier>                                        → paquet Discord
"""
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import time

from common import REPO, WORK

from services import newsvid as N

NEWS = os.path.join(REPO, "news")


def job_path(arg):
    p = arg if os.path.isabs(arg) else os.path.join(REPO, arg)
    if not os.path.isdir(p):
        p = os.path.join(NEWS, arg)
    if not os.path.isdir(p):
        raise SystemExit(f"Dossier introuvable : {arg}")
    return os.path.abspath(p)


def job_meta(job):
    with open(os.path.join(job, "job.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48]


def cmd_new(key, topic):
    ch = N.channel(key)
    d = os.path.join(NEWS, key, f"{datetime.date.today():%Y-%m-%d}_{slug(topic)}")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "job.json"), "w", encoding="utf-8") as f:
        json.dump({"channel": key, "topic": topic, "created": datetime.datetime.utcnow().isoformat(timespec="minutes")},
                  f, indent=1)
    print(os.path.relpath(d, REPO), "—", ch["name"])


def cmd_today(key, hours=48):
    """Histoires du jour (flux RSS des chaînes sources + classement IA)."""
    ch = N.channel(key)
    vids = N.discover(ch, hours)
    print(f"{len(vids)} vidéos en {hours} h sur {len(ch.get('sources') or {})} chaînes")
    for k, st in enumerate(N.stories(ch, vids), 1):
        print(f"\n{k}. {st.get('story')} — {', '.join(st.get('people') or [])}\n   {st.get('why', '')}")
        for i in st.get("videos") or []:
            try:
                v = vids[int(i)]
            except (ValueError, IndexError, TypeError):
                continue
            print(f"   - {v['id']}  {v['published'][:16]}  {v['channel']}: {v['title']}")


def cmd_add(job, ids):
    for vid in ids:
        info = N.video_info(vid) or {"id": vid}
        lines = N.fetch_captions(vid, os.path.join(WORK, "news_captions"))
        if not lines:
            print(f"{vid} : pas de sous-titres")
            continue
        N.save_source(job, info, lines)
        print(f"{vid} : {len(lines)} lignes — {info.get('title')}")


def cmd_import(job, path, meta_path=None):
    """Transcriptions NexLev (une seule ou en lot) + métadonnées {id: {title, channel, handle, date}}."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = {}
    if meta_path:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    items = []
    if isinstance(data, dict) and "transcripts" in data:
        for r in data["transcripts"].get("results") or []:
            if r.get("success") and r.get("data"):
                items.append((r["videoId"], r["data"]))
    elif isinstance(data, dict) and data.get("transcript"):
        items.append((data.get("videoId") or data.get("id"), data))
    for vid, d in items:
        lines = N.lines_from_nexlev(d)
        m = dict(meta.get(vid) or {}, id=vid)
        N.save_source(job, m, lines)
        print(f"{vid} : {len(lines)} lignes — {m.get('title', '')}")


def cmd_moments(job):
    j = job_meta(job)
    ch = N.channel(j["channel"])
    from concurrent.futures import ThreadPoolExecutor
    allm = []
    srcs = N.sources(job)
    with ThreadPoolExecutor(max_workers=4) as ex:
        for src, ms in zip(srcs, ex.map(lambda s: N.find_moments(s, j["topic"], ch), srcs)):
            print(f"{src['id']} ({src.get('channel', '')}) : {len(ms)} moments", flush=True)
            allm += ms
    allm.sort(key=lambda m: -m["heat"])
    with open(os.path.join(job, "moments.json"), "w", encoding="utf-8") as f:
        json.dump(allm, f, ensure_ascii=False, indent=1)
    print(f"{len(allm)} moments → moments.json")


def cmd_plan(job, context=""):
    j = job_meta(job)
    plan = N.make_plan(job, N.channel(j["channel"]), j["topic"], context=context or j.get("context", ""))
    plan = N.headlines(job)
    print(json.dumps({"titles": plan["titles"], "thumb": plan["thumb"], "minutes": plan["estimated_minutes"]},
                     ensure_ascii=False, indent=1))


def cmd_voice(job):
    """Toute la voix off en UNE fois (Algrow refuse les textes de moins de 200 caractères, et le ton reste
    le même), puis découpée en narration/nXXX.mp3 au milieu de la pause entre deux passages (timings au mot)."""
    from services import media, tts
    with open(os.path.join(job, "plan.json"), "r", encoding="utf-8") as f:
        plan = json.load(f)
    d = os.path.join(job, "narration")
    os.makedirs(d, exist_ok=True)
    todo = [(i, N.speakable(seg["text"])) for i, seg in enumerate(plan["segments"]) if seg["type"] == "narration"]
    if all(os.path.isfile(os.path.join(d, f"n{i:03d}.mp3")) for i, _ in todo):
        print("voix off déjà prête")
        return
    v = plan.get("voice") or {}
    full = os.path.join(WORK, "news_voice", os.path.basename(job) + ".mp3")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    res = tts.synthesize("\n\n".join(t for _, t in todo), full, provider=v.get("provider") or "algrow",
                         voice=v.get("id") or "", lang="en")
    words = sorted(res["words"], key=lambda w: w["s"])
    bounds, k = [0.0], 0
    for _, t in todo[:-1]:
        k += len(t.split())
        nxt = next((w for w in words if int(w.get("t", 0)) >= k), None)
        prv = [w for w in words if int(w.get("t", 0)) < k]
        if not nxt or not prv:
            raise SystemExit("découpage de la voix off impossible (timings)")
        bounds.append((prv[-1]["e"] + nxt["s"]) / 2)
    bounds.append(res["duration"])
    for (i, _), a, b in zip(todo, bounds[:-1], bounds[1:]):
        dest = os.path.join(d, f"n{i:03d}.mp3")
        media.run(["-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", full, "-af",
                   "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                   "silenceremove=start_periods=1:start_threshold=-45dB,areverse",
                   "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k", dest])
        print(f"voix {i} : {media.duration(dest):.1f} s")


def cmd_build(job, upload=True, keep=False):
    from services import newsvid_render as R
    if os.environ.get("NEWS_NO_UPLOAD"):  # tests : pas d'envoi sur Gofile
        upload = False
    res = R.build(job, WORK, upload=upload, keep=keep)
    print(json.dumps(res, indent=1))
    return res


def git(*args, check=False):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=check)


def push_result(rel):
    """Renvoie le résultat dans git (lien, planches, journal) ; si le cloud a poussé entre-temps : rebase puis
    nouvel essai. Ne prend que les planches (jamais les images de travail)."""
    paths = [os.path.join(rel, "result.json"), os.path.join(rel, "build.log")]
    paths += [os.path.relpath(p, REPO) for p in glob.glob(os.path.join(REPO, rel, "check", "sheet_*.jpg"))]
    git("add", "-f", "--", *[p for p in paths if os.path.exists(os.path.join(REPO, p))])
    git("commit", "-q", "-m", f"News video built on PC: {os.path.basename(rel)}")
    for k in range(4):
        p = git("push", "-q", "origin", "HEAD")
        if p.returncode == 0:
            print("Planches et lien envoyés à Claude : ok")
            return True
        err = p.stderr.strip()
        if "rejected" in err or "fetch first" in err or "non-fast-forward" in err:
            git("pull", "-q", "--rebase", "--autostash")
            continue
        break
    print("!! Envoi à Claude raté (connexion GitHub ?) :", err[:300])
    print("   Donne-lui le lien ci-dessus et glisse les images du dossier check dans le chat.")
    return False


def cmd_pc():
    """PC : récupère les vidéos à monter (marquées `ready` par Claude après relecture), les monte, renvoie le
    résultat (lien + planches) dans git. Lancé tout seul toutes les 15 min par la tâche planifiée du PC."""
    ahead = git("rev-list", "--count", "@{u}..HEAD").stdout.strip()
    if ahead.isdigit() and int(ahead) > 0:  # résultat d'une fois précédente pas encore envoyé (connexion ?)
        git("pull", "-q", "--rebase", "--autostash")
        git("push", "-q", "origin", "HEAD")
    r = git("pull", "-q", "--ff-only")
    if r.returncode != 0:
        print(r.stderr.strip()[:300])
    tries_path = os.path.join(WORK, "news_attempts.json")
    try:
        with open(tries_path, "r", encoding="utf-8") as f:
            tries = json.load(f)
    except (OSError, ValueError):
        tries = {}
    todo = []
    for root, dirs, files in os.walk(NEWS):
        if ("plan.json" in files and "ready" in files and "result.json" not in files
                and os.path.isdir(os.path.join(root, "narration"))):
            rel = os.path.relpath(root, REPO).replace("\\", "/")
            if tries.get(rel, 0) < 3:  # 3 échecs : on attend que Claude corrige (build.log est dans git)
                todo.append(root)
    if not todo:
        print("Rien à monter.")
        return
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "--disable-pip-version-check",
                    "--no-warn-script-location", "yt-dlp[default]"], check=False)
    for job in sorted(todo):
        rel = os.path.relpath(job, REPO)
        key = rel.replace("\\", "/")
        print(f"=== {rel}")
        tries[key] = tries.get(key, 0) + 1
        os.makedirs(WORK, exist_ok=True)
        with open(tries_path, "w", encoding="utf-8") as f:
            json.dump(tries, f)
        try:
            cmd_build(job)
        except Exception as e:  # noqa: BLE001  (le journal part quand même dans git)
            with open(os.path.join(job, "build.log"), "a", encoding="utf-8") as f:
                f.write(f"ERREUR : {e}\n")
            print("ERREUR :", e)
        rp = os.path.join(job, "result.json")
        if os.path.isfile(rp):
            with open(rp, "r", encoding="utf-8") as f:
                link = json.load(f).get("link")
            print(f"\n>>> LIEN DE LA VIDEO : {link or 'envoi Gofile raté (voir build.log)'}\n")
        push_result(rel)


VPS_CODE = ["production/news.py", "production/common.py", "services/__init__.py", "services/newsvid.py",
            "services/newsvid_render.py", "services/media.py", "services/music.py", "services/ai.py", "services/tts.py",
            "services/sfx.py"]


def vps_call(method, path, data=None, timeout=60):
    """Serveur de montage du VPS (production/news_worker.py) : NEWS_WORKER_URL + NEWS_WORKER_TOKEN dans .env."""
    import requests
    url = (os.environ.get("NEWS_WORKER_URL") or "").rstrip("/")
    tok = os.environ.get("NEWS_WORKER_TOKEN") or ""
    if not url or not tok:
        raise SystemExit("NEWS_WORKER_URL / NEWS_WORKER_TOKEN absents du .env (installer : production/vps_news_setup.sh)")
    return requests.request(method, url + path, data=data, timeout=timeout, headers={"X-Worker-Token": tok})


def job_tarball(job):
    """Le code du montage + la vidéo préparée (plan, voix off), en .tgz : pour le VPS ou le PC."""
    import io
    import tarfile
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for rel in VPS_CODE:
            t.add(os.path.join(REPO, rel), "code/" + rel)
        t.add(os.path.join(REPO, "static", "fonts"), "code/static/fonts")
        for f in ("plan.json", "job.json"):
            if os.path.isfile(os.path.join(job, f)):
                t.add(os.path.join(job, f), "job/" + f)
        for f in sorted(glob.glob(os.path.join(job, "narration", "n*.mp3"))):
            t.add(f, "job/narration/" + os.path.basename(f))
        idx = os.path.join(job, "photos", "photos.json")      # photos des combattants (fonds de la voix off)
        if os.path.isfile(idx):
            t.add(idx, "job/photos/photos.json")
            with open(idx, "r", encoding="utf-8") as f:
                for items in json.load(f).values():
                    for it in items:
                        p = os.path.join(job, "photos", it.get("file", ""))
                        if it.get("file") and os.path.isfile(p):
                            t.add(p, "job/photos/" + it["file"])
    return buf.getvalue()


def cmd_vps(job, wait=True, upload=True, pc=False):
    """Montage sur le VPS (ou, avec pc, sur le PC de l'utilisateur via le relais du VPS) : envoie le code + la
    vidéo préparée, suit le montage, rapatrie lien et planches."""
    name = os.path.basename(job.rstrip("/\\"))
    data = job_tarball(job)
    if pc:
        r = vps_call("PUT", f"/pcjob?name={name}", data=data, timeout=300)
    else:
        r = vps_call("PUT", f"/job?name={name}" + ("" if upload else "&upload=0"), data=data, timeout=300)
    if r.status_code != 200:
        raise SystemExit(f"VPS : {r.status_code} {r.text[:300]}")
    print(f"envoyé ({len(data) / 1e6:.1f} Mo) : " + ("en attente du PC (il passe toutes les 15 min)" if pc
                                                      else "montage lancé sur le VPS"))
    if wait:
        (pc_fetch if pc else vps_fetch)(job, wait=True)


def pc_fetch(job, wait=False):
    """Vidéo montée par le PC : état, puis rapatrie result.json, build.log et les planches."""
    name = os.path.basename(job.rstrip("/\\"))
    last = ""
    while True:
        s = vps_call("GET", f"/pc/state?name={name}").json()
        line = (s.get("log") or [""])[-1]
        if line and line != last:
            print(line, flush=True)
            last = line
        if s.get("state") == "done":
            break
        if not wait:
            seen = s.get("pc_seen")
            ago = f"il y a {int((time.time() - seen) / 60)} min" if seen else "jamais"
            print(f"état : {s.get('state')} — dernier passage du PC : {ago}")
            return None
        time.sleep(60)
    for rel in ["result.json", "build.log"] + [f"check/sheet_{k:02d}.jpg" for k in range(1, 40)]:
        r = vps_call("GET", f"/pc/file?name={name}&path={rel}", timeout=120)
        if r.status_code != 200:
            if rel.startswith("check/"):
                break
            continue
        dest = os.path.join(job, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(r.content)
    rp = os.path.join(job, "result.json")
    if os.path.isfile(rp):
        with open(rp, "r", encoding="utf-8") as f:
            res = json.load(f)
        print(f">>> LIEN DE LA VIDEO : {res.get('link')}  ({res.get('minutes')} min)")
        return res
    print("pas de result.json : voir build.log")
    return None


def vps_fetch(job, wait=False):
    """Attend la fin du montage (si wait) puis rapatrie result.json, build.log et les planches."""
    name = os.path.basename(job.rstrip("/\\"))
    last = ""
    while True:
        s = vps_call("GET", "/status").json()
        line = (s.get("log") or [""])[-1]
        if line and line != last:
            print(line, flush=True)
            last = line
        if not (s.get("busy") and s.get("job") == name):
            break
        if not wait:
            print("montage en cours :", s.get("stage"))
            return None
        time.sleep(30)
    for rel in ["result.json", "build.log"] + [f"check/sheet_{k:02d}.jpg" for k in range(1, 40)]:
        r = vps_call("GET", f"/file?name={name}&path={rel}", timeout=120)
        if r.status_code != 200:
            if rel.startswith("check/"):
                break
            continue
        dest = os.path.join(job, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(r.content)
    if s.get("error"):
        print("ERREUR VPS :", s["error"])
    rp = os.path.join(job, "result.json")
    if os.path.isfile(rp):
        with open(rp, "r", encoding="utf-8") as f:
            res = json.load(f)
        print(f">>> LIEN DE LA VIDEO : {res.get('link')}  ({res.get('minutes')} min)")
        return res
    print("pas de result.json : voir build.log")
    return None


def cmd_send(job):
    """Paquet Discord (après vérification des planches) : lien, miniature, titres, description, tags."""
    import requests
    from common import webhook
    with open(os.path.join(job, "plan.json"), "r", encoding="utf-8") as f:
        plan = json.load(f)
    with open(os.path.join(job, "result.json"), "r", encoding="utf-8") as f:
        res = json.load(f)
    if not res.get("link"):
        raise SystemExit("Pas de lien Gofile dans result.json.")
    thumb = os.path.join(job, "thumb.jpg")
    title = plan.get("title") or (plan.get("titles") or ["?"])[0]
    others = "\n".join(f"• {t}" for t in (plan.get("titles") or [])[1:4])
    content = (f"🎬 **{plan.get('brand', 'News')} — {title}** ✅ vérifiée, à poster\n"
               f"🔗 **Vidéo** : <{res['link']}> ({res.get('minutes', '?')} min)")
    embeds = [{"title": "Titre", "description": title + (f"\n\nAutres titres :\n{others}" if others else ""),
               "color": 0xE10600},
              {"title": "Description", "description": (plan.get("description") or "")[:4000], "color": 0xE10600},
              {"title": "Tags", "description": ", ".join(plan.get("tags") or [])[:4000], "color": 0xE10600},
              {"title": "Commentaire épinglé", "description": plan.get("pinned_comment") or "-", "color": 0xE10600}]
    data = {"content": content, "embeds": embeds, "allowed_mentions": {"parse": []}}
    url = webhook() + "?wait=true"
    if os.path.isfile(thumb):
        with open(thumb, "rb") as fh:
            r = requests.post(url, data={"payload_json": json.dumps(data)}, timeout=120,
                              files={"files[0]": ("miniature.jpg", fh, "image/jpeg")})
    else:
        r = requests.post(url, json=data, timeout=60)
    r.raise_for_status()
    with open(os.path.join(job, "discord_done"), "w", encoding="utf-8") as f:
        f.write(res["link"])
    print("Discord : envoyé")


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    c, rest = argv[0], argv[1:]
    flags = [a for a in rest if a.startswith("--")]
    args = [a for a in rest if not a.startswith("--")]
    if c == "today":
        hrs = 48
        if "--hours" in rest:
            k = rest.index("--hours")
            hrs = int(rest[k + 1])
            args = [a for a in args if a != rest[k + 1]]
        cmd_today(args[0] if args else "mma_en", hrs)
    elif c == "new":
        cmd_new(args[0], " ".join(args[1:]))
    elif c == "add":
        cmd_add(job_path(args[0]), args[1:])
    elif c == "import":
        cmd_import(job_path(args[0]), args[1], args[2] if len(args) > 2 else None)
    elif c == "moments":
        cmd_moments(job_path(args[0]))
    elif c == "plan":
        ctx = ""
        if "--context" in rest:
            k = rest.index("--context")
            ctx = rest[k + 1] if k + 1 < len(rest) else ""
            args = [a for a in args if a != ctx]
        cmd_plan(job_path(args[0]), ctx)
    elif c == "headlines":
        N.headlines(job_path(args[0]))
    elif c == "voice":
        cmd_voice(job_path(args[0]))
    elif c == "thumb":
        from services import newsvid_thumb as T
        T.make(job_path(args[0]))
    elif c == "build":
        cmd_build(job_path(args[0]), upload="--no-upload" not in flags, keep="--keep" in flags)
    elif c == "pc":
        cmd_pc()
    elif c == "vps":
        cmd_vps(job_path(args[0]), wait="--no-wait" not in flags, upload="--no-upload" not in flags,
                pc="--pc" in flags)
    elif c == "pc-fetch":
        pc_fetch(job_path(args[0]), wait="--wait" in flags)
    elif c == "vps-fetch":
        vps_fetch(job_path(args[0]), wait="--wait" in flags)
    elif c == "vps-check":
        print(vps_call("POST", "/ytcheck", timeout=320).json())
    elif c == "send":
        cmd_send(job_path(args[0]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):  # Python embarqué (PC) : console en cp1252, pas de plantage sur un accent
        try:
            _s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    main(sys.argv[1:])
