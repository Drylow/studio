"""Planning de publication : chaque short d'une chaîne reçoit un créneau (jour + heure).

Les shorts sont rangés dans l'ordre de création sur les créneaux libres de la chaîne (ex. 12:30 et 19:00
chaque jour à partir de demain). L'export prépare un dossier par publication : la vidéo, la légende à
copier-coller (avec les hashtags) et une image de couverture.
"""
import csv
import datetime as dt
import io
import shutil
import subprocess
from pathlib import Path

from . import channels, config, store

FMT = "%Y-%m-%d %H:%M"
EXPORTS = config.ROOT / "exports"
MAX_HASHTAGS = 8


def _start_day(ch: dict) -> dt.date:
    today = dt.date.today()
    try:
        d = dt.date.fromisoformat(ch.get("start_date") or "")
    except ValueError:
        d = today + dt.timedelta(days=1)
    return max(d, today)


def _slots(ch: dict):
    day = _start_day(ch)
    while True:
        for t in ch["post_times"]:
            yield f"{day.isoformat()} {t}"
        day += dt.timedelta(days=1)


def _sorted(ps: list[dict]) -> list[dict]:
    return sorted(ps, key=lambda p: ((p.get("post") or {}).get("slot") or "9999", p.get("created", 0)))


def assign(ch: dict, reset: bool = False) -> int:
    """Donne un créneau aux shorts qui n'en ont pas (reset = tout replanifier, sauf ce qui est déjà publié)."""
    ps = sorted(channels.projects_of(ch["id"]), key=lambda p: p.get("created", 0))
    now_s = dt.datetime.now().strftime(FMT)
    if reset:
        for p in ps:
            po = p.get("post") or {}
            if not po.get("posted") and po.pop("slot", None):
                store.save_project(p)
    taken = {p["post"]["slot"] for p in ps if (p.get("post") or {}).get("slot")}
    it, n = _slots(ch), 0
    for p in ps:
        po = p.setdefault("post", {})
        if po.get("slot") or po.get("posted"):
            continue
        slot = next(it)
        while slot in taken or slot <= now_s:
            slot = next(it)
        po["slot"] = slot
        taken.add(slot)
        n += 1
        store.save_project(p)
    return n


def hashtags(p: dict, ch: dict | None) -> list[str]:
    out, seen = [], set()
    for h in ((ch or {}).get("hashtags") or []) + ((p.get("short") or {}).get("hashtags") or []):  # ceux de la chaîne d'abord
        h = str(h).strip().lstrip("#").replace(" ", "")
        if h and h.lower() not in seen:
            seen.add(h.lower())
            out.append(h)
    return out[:MAX_HASHTAGS]


def caption_text(p: dict, ch: dict | None) -> str:
    cap = ((p.get("short") or {}).get("caption") or p.get("title") or "").strip()
    tags = " ".join(f"#{h}" for h in hashtags(p, ch))
    return f"{cap}\n\n{tags}".strip()


def video_file(p: dict) -> Path | None:
    """La vidéo à publier : le rendu Resolve s'il est terminé et à jour, sinon le rendu automatique."""
    pdir = store.project_dir(p["id"])
    auto = pdir / "render" / "final.mp4"
    res = p.get("resolve") or {}
    rf = pdir / "render" / "resolve_final.mp4"
    if res.get("render_status") == "Complete" and rf.exists() and (not auto.exists()
                                                                    or rf.stat().st_mtime >= auto.stat().st_mtime):
        return rf
    return auto if auto.exists() and p.get("render") else None


def status(p: dict) -> str:
    if (p.get("post") or {}).get("posted"):
        return "posted"
    if p.get("error"):
        return "error"
    if p.get("render") and video_file(p):
        return "ready"
    return "production"


def items(ch: dict) -> list[dict]:
    from . import pipeline
    out = []
    for p in _sorted(channels.projects_of(ch["id"])):
        po = p.get("post") or {}
        first = next((s.get("image") for s in p.get("scenes") or [] if s.get("image")), None)
        st = status(p)
        vf = video_file(p)
        running = pipeline.is_running(p["id"])
        step = next((k for k, s in p["steps"].items() if s.get("state") == "running"), None)
        out.append({
            "id": p["id"], "title": p.get("title") or "(title in progress…)", "slot": po.get("slot"),
            "posted": po.get("posted"), "status": st, "running": running, "step": step,
            "kind": (p.get("short") or {}).get("kind") or "standalone",
            "parent_title": (p.get("short") or {}).get("parent_title"),
            "hook": (p.get("short") or {}).get("hook_text"), "caption": caption_text(p, ch),
            "thumb": first, "duration": (p.get("render") or {}).get("duration")
            or (p.get("voiceover") or {}).get("duration"),
            "resolve": bool((p.get("resolve") or {}).get("render_status") == "Complete"),
            "error": p.get("error"), "exported": po.get("export_dir"),
            "video": vf.relative_to(store.project_dir(p["id"])).as_posix() if vf else None,
            "video_ts": int(vf.stat().st_mtime) if vf else None,
        })
    return out


def summary(ch: dict) -> dict:
    its = items(ch)
    todo = [i for i in its if i["status"] != "posted"]
    ready = [i for i in todo if i["status"] == "ready"]
    last_ready = max((i["slot"] for i in ready if i["slot"]), default=None)
    return {"total": len(its), "ready": len(ready), "production": sum(i["status"] == "production" for i in todo),
            "errors": sum(i["status"] == "error" for i in todo), "posted": sum(i["status"] == "posted" for i in its),
            "covered_until": last_ready, "late": sum(1 for i in todo if i["slot"] and i["slot"] < dt.datetime.now()
                                                    .strftime(FMT))}


def move(p: dict, direction: int) -> None:
    """Échange le créneau d'un short avec son voisin (direction -1 = plus tôt, +1 = plus tard)."""
    ch = channels.get(p.get("channel_id"))
    if not ch:
        raise ValueError("This short is not linked to any channel")
    seq = [x for x in _sorted(channels.projects_of(ch["id"]))
           if (x.get("post") or {}).get("slot") and not x["post"].get("posted")]
    idx = next((i for i, x in enumerate(seq) if x["id"] == p["id"]), None)
    if idx is None or not 0 <= idx + direction < len(seq):
        return
    other = seq[idx + direction]
    a, b = seq[idx], other
    a["post"]["slot"], b["post"]["slot"] = b["post"]["slot"], a["post"]["slot"]
    store.save_project(a)
    store.save_project(b)


def set_posted(p: dict, posted: bool) -> None:
    po = p.setdefault("post", {})
    po["posted"] = dt.datetime.now().strftime(FMT) if posted else None
    if posted and not po.get("slot"):
        po["slot"] = po["posted"]
    store.save_project(p)


def channel_dir(ch: dict) -> Path:
    from .resolve_export import safe_name
    return EXPORTS / safe_name(ch["name"], 40)


def export(ch: dict) -> dict:
    """Dossier prêt à publier : exports/<chaîne>/<date heure - titre>/ (video.mp4, legende.txt, cover.jpg)."""
    from .resolve_export import safe_name
    root = channel_dir(ch)
    root.mkdir(parents=True, exist_ok=True)
    rows, n = [], 0
    for it in items(ch):
        p = store.get_project(it["id"])
        if it["status"] != "ready" or not it["slot"]:
            continue
        src = video_file(p)
        name = f"{it['slot'][:10]} {it['slot'][11:].replace(':', 'h')} - {safe_name(it['title'], 50)}"
        dst = root / name
        old = (p.get("post") or {}).get("export_dir")
        if old and Path(old) != dst and Path(old).exists() and Path(old).parent == root:
            shutil.rmtree(old, ignore_errors=True)  # le créneau a changé : on déplace le dossier
        dst.mkdir(exist_ok=True)
        target = dst / "video.mp4"
        if not target.exists() or target.stat().st_mtime < src.stat().st_mtime or target.stat().st_size != src.stat().st_size:
            shutil.copy2(src, target)
            n += 1
        (dst / "legende.txt").write_text(it["caption"], encoding="utf-8")
        cover = dst / "cover.jpg"
        if not cover.exists() or cover.stat().st_mtime < target.stat().st_mtime:
            subprocess.run([config.get("FFMPEG"), "-y", "-v", "error", "-ss", "0.9", "-i", str(target),
                            "-frames:v", "1", "-q:v", "2", str(cover)], check=False)
        p["post"]["export_dir"] = str(dst)
        store.save_project(p)
        rows.append([it["slot"], it["title"], it["caption"].replace("\n", " "), str(target)])
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["creneau", "title", "legende", "fichier"])
    w.writerows(rows)
    (root / "planning.csv").write_text(buf.getvalue(), encoding="utf-8-sig")
    return {"dir": str(root), "count": len(rows), "copied": n}
