"""Rendu Remotion réparti sur des pods CPU RunPod (format Histoire) : quelques minutes au lieu de plusieurs heures.

Actif si RUNPOD_API_KEY est dans le .env. Le rendu local par morceaux (history.job_render) appelle render() avant de
rendre lui-même : chaque pod reçoit le moteur + les médias, rend sa liste de morceaux (render.mjs --chunks), et les
morceaux sont rapatriés dans le même dossier ; ce qui manque encore est rendu en local. Les pods sont toujours
supprimés à la fin (et ceux d'un rendu interrompu, notés dans pods.json, au rendu suivant).

Réglages (.env, facultatifs) : RUNPOD_PODS (8), RUNPOD_VCPU (32), RUNPOD_CPU_FLAVOR (cpu5c), RUNPOD_IMAGE."""
import base64
import io
import json
import math
import os
import tarfile
import time

import requests

API = "https://rest.runpod.io/v1"
IMAGE = "mcr.microsoft.com/playwright:v1.49.1-noble"  # Node + Chromium headless shell + ses bibliothèques
PART = 40 * 1024 * 1024  # le proxy RunPod refuse les envois trop gros : le paquet part en morceaux
HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(os.path.dirname(HERE), "production", "runpod_worker.js")
ENGINE = os.path.join(os.path.dirname(HERE), "history_engine")


def available():
    return bool(os.getenv("RUNPOD_API_KEY"))


def _h():
    return {"Authorization": "Bearer " + os.environ["RUNPOD_API_KEY"], "Content-Type": "application/json"}


def _url(pod_id):
    return f"https://{pod_id}-8000.proxy.runpod.net"


def _create(name, vcpu):
    worker = base64.b64encode(open(WORKER, "rb").read()).decode()
    body = {"name": name, "imageName": os.getenv("RUNPOD_IMAGE") or IMAGE, "computeType": "CPU",
            "cpuFlavorIds": [os.getenv("RUNPOD_CPU_FLAVOR") or "cpu5c"], "vcpuCount": vcpu,
            "containerDiskInGb": 20, "ports": ["8000/http"], "env": {"WORKER_JS": worker},
            "dockerStartCmd": ["bash", "-c", 'echo "$WORKER_JS" | base64 -d > /w.js && node /w.js']}
    r = requests.post(f"{API}/pods", headers=_h(), json=body, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"RunPod {r.status_code} : {r.text[:300]}")
    return r.json()["id"]


def _delete(pod_id):
    try:
        requests.delete(f"{API}/pods/{pod_id}", headers=_h(), timeout=60)
    except requests.RequestException:
        pass


def _status(pod_id):
    try:
        r = requests.get(_url(pod_id) + "/status", timeout=20)
        return r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


def _bundle(media_dir):
    """moteur (sans node_modules) + médias (sans les anciennes images *.old) → .tgz en mémoire."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=1) as tar:
        for name in os.listdir(ENGINE):
            if name != "node_modules":
                tar.add(os.path.join(ENGINE, name), arcname=f"engine/{name}")
        tar.add(media_dir, arcname="media", filter=lambda ti: None if ".old" in ti.name else ti)
    return buf.getvalue()


def render(job, media_dir, chunks, size, total, p0=0.05, p1=0.9):
    """Rend sur RunPod les morceaux absents de `chunks` (et audio.wav) ; ne lève pas d'erreur si un pod échoue."""
    n = math.ceil(total / size)
    part = lambda i: os.path.join(chunks, f"part_{i:03d}.mp4")  # noqa: E731
    todo = [i for i in range(n) if not os.path.isfile(part(i))]
    need_audio = not os.path.isfile(os.path.join(chunks, "audio.wav"))
    if not todo and not need_audio:
        return
    record = os.path.join(chunks, "pods.json")
    if os.path.isfile(record):  # pods d'un rendu interrompu (redémarrage de la machine) : on ne paie pas pour rien
        for pid in json.load(open(record)):
            _delete(pid)
    count = max(1, min(int(os.getenv("RUNPOD_PODS") or 8), math.ceil(len(todo) / 3) or 1))
    vcpu = int(os.getenv("RUNPOD_VCPU") or 32)
    pods = []
    try:
        job.update(p0, f"RunPod : démarrage de {count} machine(s) de {vcpu} cœurs…")
        for k in range(count):
            try:
                pods.append(_create(f"drylow-render-{k}", vcpu))
            except RuntimeError as e:
                print(f"[runpod] {e}", flush=True)
                if not pods:
                    raise
                break
            json.dump(pods, open(record, "w"))
        t0 = time.time()
        while time.time() - t0 < 900 and _status(pods[0]) is None:
            time.sleep(8)
        if _status(pods[0]) is None:
            raise RuntimeError("RunPod : la première machine ne répond pas")
        job.update(p0, "RunPod : envoi des images et du moteur…")
        blob = _bundle(media_dir)
        parts = [blob[i:i + PART] for i in range(0, len(blob), PART)]
        for k, chunk in enumerate(parts):
            requests.put(f"{_url(pods[0])}/bundle?part={k}", data=chunk, timeout=600).raise_for_status()
        requests.post(f"{_url(pods[0])}/unpack?parts={len(parts)}", timeout=60).raise_for_status()
        # file d'attente : chaque pod prend un petit lot de morceaux, puis le suivant ; un pod perdu rend son lot
        queue, inflight, fetched, seen = list(todo), {}, set(), {}
        got = set(i for i in range(n) if os.path.isfile(part(i)))
        audio_done, audio_pod = not need_audio, None
        alive, deadline, batch = set(pods), time.time() + 2700, 4
        while time.time() < deadline and alive and (len(got) < n or not audio_done):
            first = _status(pods[0])
            for pid in list(alive):
                st = first if pid == pods[0] else _status(pid)
                if st is None:
                    if time.time() - seen.get(pid, t0) > 900:  # ne répond plus (ou jamais) : abandonné
                        alive.discard(pid)
                        queue[:0] = [i for i in inflight.pop(pid, []) if i not in got]
                        audio_pod = None if audio_pod == pid else audio_pod
                    continue
                seen[pid] = time.time()
                if not st.get("ready"):
                    if pid not in fetched and st.get("stage") == "idle" and pid != pods[0] and first and first.get("ready"):
                        requests.post(f"{_url(pid)}/fetch?from={_url(pods[0])}", timeout=60)
                        fetched.add(pid)
                    if st.get("stage") == "failed":
                        print(f"[runpod] {pid} : {st.get('error')} {st.get('log', [])[-2:]}", flush=True)
                        alive.discard(pid)
                    continue
                for f in st.get("files") or []:
                    dest = os.path.join(chunks, f)
                    if os.path.isfile(dest):
                        continue
                    r = requests.get(f"{_url(pid)}/file/{f}", timeout=600)
                    if r.status_code == 200:
                        open(dest + ".dl", "wb").write(r.content)
                        os.replace(dest + ".dl", dest)
                        if f == "audio.wav":
                            audio_done = True
                        else:
                            got.add(int(f[5:8]))
                busy = pid in inflight and st.get("stage") not in ("done", "failed")
                if pid in inflight and not busy:
                    queue[:0] = [i for i in inflight.pop(pid) if i not in got]
                    audio_pod = None if audio_pod == pid and not audio_done else audio_pod
                    if st.get("stage") == "failed":
                        print(f"[runpod] {pid} : {st.get('error')} {st.get('log', [])[-2:]}", flush=True)
                if not busy:
                    mine, queue = queue[:batch], queue[batch:]
                    audio = "0"
                    if not audio_done and audio_pod is None:
                        audio, audio_pod = ("1" if mine else "only"), pid
                    if mine or audio != "0":
                        requests.post(f"{_url(pid)}/render?chunks={','.join(map(str, mine)) or 'none'}&frames={size}"
                                      f"&audio={audio}&conc={max(1, vcpu * 3 // 4)}", timeout=60)
                        inflight[pid] = mine
            job.update(p0 + (p1 - p0) * len(got) / n, f"RunPod : {len(got)}/{n} morceaux rendus sur {len(alive)} machine(s)")
            time.sleep(10)
    finally:
        for pid in pods:
            _delete(pid)
        try:
            os.remove(record)
        except OSError:
            pass
