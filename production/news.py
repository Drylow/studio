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
import glob
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
    todo = [(i, seg["text"]) for i, seg in enumerate(plan["segments"]) if seg["type"] == "narration"]
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
    for _s in (sys.stdout, sys.stderr):  # Python embarqué (PC) : console en cp1252, pas de plantage sur un accent
        try:
            _s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    main(sys.argv[1:])
