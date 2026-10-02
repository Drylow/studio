"""Vidéos d'actu sport (format Fight Night MMA, toutes les chaînes d'actu : MMA, boxe, foot…).

Un dossier par vidéo dans le dépôt : news/<chaîne>/<AAAA-MM-JJ>_<sujet>/ (plan, voix off, miniature,
planches de contrôle, résultat). Les sous-titres des sources (sources/) restent hors de git.

  # dans le cloud (ou sur PC)
  python production/news.py new mma_en "Gaethje vs Topuria: the rematch saga"      → crée le dossier
  python production/news.py add <dossier> <id_youtube> [<id> …]                   → sous-titres (yt-dlp, PC)
  python production/news.py import <dossier> <fichier_nexlev.json> [meta.json]    → sous-titres NexLev (cloud)
  python production/news.py moments <dossier>                                     → moments.json (IA)
  python production/news.py plan <dossier> [--context "faits vérifiés"]           → plan.json (IA, citations vérifiées)
  python production/news.py voice <dossier>                                       → narration/nXXX.mp3 (Algrow)
  python production/news.py thumb <dossier>                                       → miniatures (planche)

  # sur le PC (YouTube y laisse télécharger) — ou double-clic sur NEWS_PC.bat
  python production/news.py pc        → git pull, monte chaque vidéo prête (plan + voix) sans résultat,
                                         Gofile, supprime les clips, git push du résultat et des planches
  python production/news.py build <dossier> [--no-upload] [--keep]

  # dans le cloud, après avoir regardé les planches check/
  python production/news.py send <dossier>                                        → paquet Discord
"""
import datetime
import json
import os
import re
import subprocess
import sys

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
    print(json.dumps({"titles": plan["titles"], "thumb": plan["thumb"], "minutes": plan["estimated_minutes"]},
                     ensure_ascii=False, indent=1))


def cmd_voice(job):
    from services import tts
    with open(os.path.join(job, "plan.json"), "r", encoding="utf-8") as f:
        plan = json.load(f)
    d = os.path.join(job, "narration")
    os.makedirs(d, exist_ok=True)
    v = plan.get("voice") or {}
    for i, seg in enumerate(plan["segments"]):
        if seg["type"] != "narration":
            continue
        dest = os.path.join(d, f"n{i:03d}.mp3")
        if os.path.isfile(dest):
            continue
        tmp = dest + ".tmp.mp3"
        tts.synthesize(seg["text"], tmp, provider=v.get("provider") or "algrow", voice=v.get("id") or "", lang="en")
        from services import media  # mono 96 kb/s : léger dans git, largement assez pour une voix
        media.run(["-i", tmp, "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k", dest])
        os.remove(tmp)
        print(f"voix {i} ok")


def cmd_build(job, upload=True, keep=False):
    from services import newsvid_render as R
    res = R.build(job, WORK, upload=upload, keep=keep)
    print(json.dumps(res, indent=1))
    return res


def git(*args, check=False):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=check)


def cmd_pc():
    """PC : récupère les vidéos à monter, les monte, renvoie le résultat (lien + planches) dans git."""
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp"], check=False)
    r = git("pull", "--ff-only")
    print(r.stdout.strip() or r.stderr.strip())
    todo = []
    for root, dirs, files in os.walk(NEWS):
        if "plan.json" in files and "result.json" not in files and os.path.isdir(os.path.join(root, "narration")):
            todo.append(root)
    if not todo:
        print("Rien à monter.")
        return
    for job in sorted(todo):
        rel = os.path.relpath(job, REPO)
        print(f"=== {rel}")
        try:
            cmd_build(job)
        except Exception as e:  # noqa: BLE001  (le journal part quand même dans git)
            with open(os.path.join(job, "build.log"), "a", encoding="utf-8") as f:
                f.write(f"ERREUR : {e}\n")
            print("ERREUR :", e)
        git("add", "-A", "--", os.path.join(rel, "result.json"), os.path.join(rel, "check"),
            os.path.join(rel, "build.log"))
        git("commit", "-q", "-m", f"News video built on PC: {os.path.basename(job)}")
        p = git("push", "-q", "origin", "HEAD")
        print("push :", "ok" if p.returncode == 0 else p.stderr.strip()[:300])


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
    with open(os.path.join(job, "discord_done"), "w") as f:
        f.write(res["link"])
    print("Discord : envoyé")


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    c, rest = argv[0], argv[1:]
    flags = [a for a in rest if a.startswith("--")]
    args = [a for a in rest if not a.startswith("--")]
    if c == "new":
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
    elif c == "voice":
        cmd_voice(job_path(args[0]))
    elif c == "thumb":
        from services import newsvid_thumb as T
        T.make(job_path(args[0]))
    elif c == "build":
        cmd_build(job_path(args[0]), upload="--no-upload" not in flags, keep="--keep" in flags)
    elif c == "pc":
        cmd_pc()
    elif c == "send":
        cmd_send(job_path(args[0]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
