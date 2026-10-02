"""Rendu Remotion réparti sur des pods CPU RunPod (format Histoire) : quelques minutes au lieu de plusieurs heures.

Actif si RUNPOD_API_KEY est dans le .env. Le rendu local par morceaux (history.job_render) appelle render() avant de
rendre lui-même : chaque pod reçoit le moteur + les médias, rend sa liste de morceaux (render.mjs --chunks), et les
morceaux sont rapatriés dans le même dossier ; ce qui manque encore est rendu en local. Les pods sont toujours
supprimés à la fin (et ceux d'un rendu interrompu, notés dans pods.json, au rendu suivant).

Coût : le gros du prix venait du démarrage des machines (image, npm, moteur), pas du calcul. Par défaut UNE seule
machine de 32 cœurs, qui travaille en même temps que le rendu local (history.job_render : RunPod part du premier
morceau, la machine cloud du dernier) ; le son se fait en local. ≈ 0,3-0,5 $ par vidéo de 36 min au lieu de ~2 $.

Réglages (.env, facultatifs) : RUNPOD_PODS (1), RUNPOD_VCPU (32), RUNPOD_CPU_FLAVOR (cpu5c), RUNPOD_IMAGE,
RUNPOD_MAX_MIN (30 : au-delà, on arrête et le reste se fait en local). Chaque pod se supprime aussi tout seul
s'il n'est plus piloté pendant 10 min (garde-fou de runpod_worker.js)."""
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


def _create(name, vcpu, extra_env=None):
    """Un pod CPU ; si le type demandé est épuisé, essaie les autres types (puis moins de cœurs)."""
    worker = base64.b64encode(open(WORKER, "rb").read()).decode()
    flavors = [os.getenv("RUNPOD_CPU_FLAVOR") or "cpu5c"] + ["cpu5c", "cpu3c", "cpu5g", "cpu3g"]
    last = ""
    for cores in dict.fromkeys([vcpu, 32, 16]):
        if cores > vcpu:
            continue
        for flavor in dict.fromkeys(flavors):
            body = {"name": name, "imageName": os.getenv("RUNPOD_IMAGE") or IMAGE, "computeType": "CPU",
                    "cpuFlavorIds": [flavor], "vcpuCount": cores, "containerDiskInGb": 20, "ports": ["8000/http"],
                    "env": dict({"WORKER_JS": worker}, **(extra_env or {})),
                    "dockerStartCmd": ["bash", "-c", 'echo "$WORKER_JS" | base64 -d > /w.js && node /w.js']}
            r = requests.post(f"{API}/pods", headers=_h(), json=body, timeout=60)
            if r.status_code < 300:
                return r.json()["id"], cores
            last = f"RunPod {r.status_code} : {r.text[:200]}"
            if "no longer any instances" not in r.text and "available" not in r.text:
                raise RuntimeError(last)
    raise RuntimeError(last)


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


def _unclaim(path):
    try:
        os.remove(path)
    except OSError:
        pass


def render(job, media_dir, chunks, size, total, p0=0.05, p1=0.9, audio=False, stop=None):
    """Rend sur RunPod les morceaux absents de `chunks` (et audio.wav si audio=True) ; ne lève pas d'erreur si un pod
    échoue. Les morceaux peuvent aussi arriver d'ailleurs (rendu local en parallèle) : la liste est relue sur le disque.
    stop() → True : on arrête et on supprime les machines (le rendu local a fini)."""
    n = math.ceil(total / size)
    part = lambda i: os.path.join(chunks, f"part_{i:03d}.mp4")  # noqa: E731
    claim = lambda i, who: os.path.join(chunks, f"claim_{i:03d}.{who}")  # noqa: E731  (voir render.mjs --skip-claimed)
    todo = [i for i in range(n) if not os.path.isfile(part(i))]
    need_audio = audio and not os.path.isfile(os.path.join(chunks, "audio.wav"))
    if not todo and not need_audio:
        return
    record = os.path.join(chunks, "pods.json")
    if os.path.isfile(record):  # pods d'un rendu interrompu (redémarrage de la machine) : on ne paie pas pour rien
        for pid in json.load(open(record)):
            _delete(pid)
    count = max(1, min(int(os.getenv("RUNPOD_PODS") or 1), math.ceil(len(todo) / 3) or 1))
    vcpu = int(os.getenv("RUNPOD_VCPU") or 32)
    pods = []
    try:
        job.update(p0, f"RunPod : démarrage de {count} machine(s) de {vcpu} cœurs…")
        for k in range(count):
            try:
                pid, cores = _create(f"drylow-render-{k}", vcpu)
                pods.append(pid)
                vcpu = min(vcpu, cores)
            except RuntimeError as e:
                print(f"[runpod] {e}", flush=True)
                if not pods:
                    raise
                break
            json.dump(pods, open(record, "w"))
        t0 = time.time()
        finished = lambda: (stop and stop()) or all(os.path.isfile(part(i)) for i in range(n))  # noqa: E731
        while time.time() - t0 < 900 and _status(pods[0]) is None and not finished():
            time.sleep(8)
        if finished():  # le rendu local a tout fait pendant le démarrage de la machine
            return
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
        alive, deadline, batch = set(pods), time.time() + 60 * int(os.getenv("RUNPOD_MAX_MIN") or 30), 4
        while time.time() < deadline and alive and (len(got) < n or not audio_done):
            if stop and stop():
                break
            got |= set(i for i in range(n) if os.path.isfile(part(i)))  # morceaux faits en local entre-temps
            queue = [i for i in queue if i not in got and not os.path.isfile(claim(i, "local"))]
            first = _status(pods[0])
            for pid in list(alive):
                st = first if pid == pods[0] else _status(pid)
                if st is None:
                    if time.time() - seen.get(pid, t0) > 900:  # ne répond plus (ou jamais) : abandonné
                        alive.discard(pid)
                        back = [i for i in inflight.pop(pid, []) if i not in got]
                        for i in back:
                            _unclaim(claim(i, "rp"))
                        queue[:0] = back
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
                    back = [i for i in inflight.pop(pid) if i not in got]
                    for i in back:
                        _unclaim(claim(i, "rp"))
                    queue[:0] = back
                    audio_pod = None if audio_pod == pid and not audio_done else audio_pod
                    if st.get("stage") == "failed":
                        print(f"[runpod] {pid} : {st.get('error')} {st.get('log', [])[-2:]}", flush=True)
                if not busy and not queue and pid != audio_pod and (audio_done or audio_pod):
                    _delete(pid)  # plus rien à lui donner : on arrête de payer cette machine tout de suite
                    alive.discard(pid)
                    continue
                if not busy:
                    audio = "0"
                    if not audio_done and audio_pod is None:  # le son (long) occupe une machine à lui seul
                        audio, audio_pod, mine = "only", pid, []
                    else:
                        mine, queue = queue[:batch], queue[batch:]
                        for i in mine:
                            open(claim(i, "rp"), "w").close()
                    if mine or audio != "0":
                        requests.post(f"{_url(pid)}/render?chunks={','.join(map(str, mine)) or 'none'}&frames={size}"
                                      f"&audio={audio}&conc={max(1, vcpu * 3 // 4)}", timeout=60)
                        inflight[pid] = mine
            job.update(p0 + (p1 - p0) * len(got) / n, f"RunPod : {len(got)}/{n} morceaux rendus sur {len(alive)} machine(s)")
            time.sleep(10)
    finally:
        for pid in pods:
            _delete(pid)
        for f in os.listdir(chunks):
            if f.endswith(".rp"):
                _unclaim(os.path.join(chunks, f))
        try:
            os.remove(record)
        except OSError:
            pass
