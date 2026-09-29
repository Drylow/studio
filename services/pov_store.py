"""Stockage disque + jobs de fond pour 2D Videos (POV Studio).

Tout vit dans POV_DATA_DIR (défaut : <app>/data/pov) :

  channels/<id>/channel.json      profil de chaîne (niche, format, style, voix, montage)
  channels/<id>/refs/*.png        image de style + personnages de référence
  projects/<id>/project.json      projet vidéo (script, scènes, rendu)
  projects/<id>/voice.mp3 …       médias générés
  music/*.mp3                     bibliothèque de musiques de fond

Les jobs tournent dans des threads du serveur Flask : la génération continue
même si l'onglet est fermé. Un seul job à la fois par projet.
"""
import copy
import json
import os
import re
import shutil
import threading
import time
import traceback
import uuid

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_dir():
    d = (os.getenv("POV_DATA_DIR") or "").strip() or os.path.join(APP_DIR, "data", "pov")
    return d


def _p(*parts):
    return os.path.join(data_dir(), *parts)


def ensure_dirs():
    for sub in ("channels", "projects", "music"):
        os.makedirs(_p(sub), exist_ok=True)


def new_id(prefix):
    return f"{prefix}_{time.strftime('%y%m%d')}{uuid.uuid4().hex[:8]}"


_ID_RE = re.compile(r"^[a-z]{2,4}_[0-9a-f]{14}$")


def valid_id(value):
    return bool(value) and bool(_ID_RE.match(value))


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ── JSON atomique + verrous ─────────────────────────────────────────────────

_locks = {}
_locks_guard = threading.Lock()


def lock_for(key):
    with _locks_guard:
        if key not in _locks:
            _locks[key] = threading.RLock()
        return _locks[key]


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ── Chaînes ─────────────────────────────────────────────────────────────────

def channel_dir(cid):
    return _p("channels", cid)


def channel_path(cid):
    return _p("channels", cid, "channel.json")


def list_channels():
    ensure_dirs()
    out = []
    for cid in os.listdir(_p("channels")):
        path = channel_path(cid)
        if valid_id(cid) and os.path.isfile(path):
            try:
                out.append(_read_json(path))
            except Exception:
                continue
    out.sort(key=lambda c: c.get("created", ""))
    return out


def get_channel(cid):
    if not valid_id(cid) or not os.path.isfile(channel_path(cid)):
        return None
    return _read_json(channel_path(cid))


def save_channel(ch):
    with lock_for(ch["id"]):
        ch["updated"] = now()
        _write_json(channel_path(ch["id"]), ch)
    return ch


def delete_channel(cid):
    if valid_id(cid) and os.path.isdir(channel_dir(cid)):
        shutil.rmtree(channel_dir(cid), ignore_errors=True)


# ── Projets ─────────────────────────────────────────────────────────────────

def project_dir(pid):
    return _p("projects", pid)


def project_path(pid):
    return _p("projects", pid, "project.json")


def list_projects():
    ensure_dirs()
    out = []
    for pid in os.listdir(_p("projects")):
        path = project_path(pid)
        if valid_id(pid) and os.path.isfile(path):
            try:
                out.append(_read_json(path))
            except Exception:
                continue
    out.sort(key=lambda p: p.get("updated", ""), reverse=True)
    return out


def get_project(pid):
    if not valid_id(pid) or not os.path.isfile(project_path(pid)):
        return None
    with lock_for(pid):
        return _read_json(project_path(pid))


def save_project(pr):
    with lock_for(pr["id"]):
        pr["updated"] = now()
        _write_json(project_path(pr["id"]), pr)
    return pr


def update_project(pid, fn):
    """Lecture-modification-écriture atomique (sûr entre threads)."""
    with lock_for(pid):
        pr = _read_json(project_path(pid))
        fn(pr)
        pr["updated"] = now()
        _write_json(project_path(pid), pr)
        return pr


def delete_project(pid):
    if valid_id(pid) and os.path.isdir(project_dir(pid)):
        shutil.rmtree(project_dir(pid), ignore_errors=True)


# ── Musique ─────────────────────────────────────────────────────────────────

_AUDIO_EXT = (".mp3", ".m4a", ".wav", ".ogg", ".aac", ".flac")


def list_music():
    ensure_dirs()
    return sorted(f for f in os.listdir(_p("music")) if f.lower().endswith(_AUDIO_EXT))


def music_path(name):
    if not name:
        return None
    name = os.path.basename(name)
    path = _p("music", name)
    return path if os.path.isfile(path) else None


def music_dir():
    return _p("music")


# ── Jobs ────────────────────────────────────────────────────────────────────

_jobs = {}
_jobs_guard = threading.Lock()


class JobCancelled(Exception):
    pass


class Job:
    def __init__(self, project_id, kind):
        self.id = new_id("job")
        self.project_id = project_id
        self.kind = kind
        self.status = "running"
        self.progress = 0.0
        self.message = "Démarrage…"
        self.error = None
        self.started = now()
        self.finished = None
        self.cancel_flag = False

    def update(self, progress=None, message=None):
        if progress is not None:
            self.progress = max(0.0, min(1.0, float(progress)))
        if message:
            self.message = message
        if self.cancel_flag:
            raise JobCancelled("Annulé.")

    def cancelled(self):
        return self.cancel_flag

    def as_dict(self):
        return {"id": self.id, "project_id": self.project_id, "kind": self.kind, "status": self.status,
                "progress": round(self.progress, 4), "message": self.message, "error": self.error,
                "started": self.started, "finished": self.finished}


def running_job(project_id):
    with _jobs_guard:
        for j in _jobs.values():
            if j.project_id == project_id and j.status == "running":
                return j
    return None


def get_job(job_id):
    with _jobs_guard:
        return _jobs.get(job_id)


def last_job(project_id):
    with _jobs_guard:
        js = [j for j in _jobs.values() if j.project_id == project_id]
    return max(js, key=lambda j: j.started + j.id) if js else None


def start_job(project_id, kind, fn):
    """Lance fn(job) dans un thread. Refuse si un job tourne déjà sur le projet."""
    with _jobs_guard:
        for j in _jobs.values():
            if j.project_id == project_id and j.status == "running":
                raise RuntimeError(f"Une tâche est déjà en cours sur ce projet ({j.kind}).")
        job = Job(project_id, kind)
        _jobs[job.id] = job
        # purge des vieux jobs terminés (mémoire)
        done = [j for j in _jobs.values() if j.status != "running"]
        for old in sorted(done, key=lambda j: j.finished or "")[:-50]:
            _jobs.pop(old.id, None)

    def runner():
        try:
            fn(job)
            job.status = "done"
            job.progress = 1.0
        except JobCancelled:
            job.status = "cancelled"
            job.message = "Annulé."
        except Exception as e:  # noqa: BLE001 — message lisible pour l'UI
            job.status = "error"
            job.error = str(e) or e.__class__.__name__
            job.message = "Erreur : " + job.error[:300]
            traceback.print_exc()
        finally:
            job.finished = now()

    threading.Thread(target=runner, name=f"pov-{kind}-{job.id}", daemon=True).start()
    return job


def cancel_job(project_id):
    j = running_job(project_id)
    if j:
        j.cancel_flag = True
    return j


def deep(o):
    return copy.deepcopy(o)
