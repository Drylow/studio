"""Rendu Remotion réparti sur des machines distantes (format Histoire) : le VPS de l'utilisateur et/ou RunPod.

history.job_render rend en local (gratuit, du dernier morceau au premier) et appelle render() en même temps : les
machines distantes reçoivent le moteur + les médias, rendent leurs lots de morceaux (render.mjs --chunks) en partant
du premier, et les morceaux sont rapatriés dans le même dossier ; les deux se rejoignent au milieu (marques
claim_XXX.rp / .local). Le son se fait en local.

Machines, dans l'ordre de préférence :
1. le VPS de l'utilisateur (gratuit : 18 vCPU EPYC) : RENDER_WORKERS=https://… et RENDER_WORKER_TOKEN dans le .env
   (installé par production/vps_setup.sh, qui affiche les deux). Une vidéo à la fois (verrou $STUDIO_WORK/vps.lock) :
   une 2e vidéo rendue en même temps prend RunPod.
2. RunPod (payant), seulement si aucun VPS n'est libre et que RUNPOD_API_KEY est là : UNE machine de 32 cœurs par
   défaut. Le gros du prix venait du démarrage des machines, pas du calcul : ≈ 0,3-0,5 $ par vidéo de 36 min (au lieu
   de ~2 $ avec 8 machines). Les pods sont toujours supprimés à la fin (et ceux d'un rendu interrompu, notés dans
   pods.json, au rendu suivant) ; chacun se supprime aussi tout seul s'il n'est plus piloté pendant 10 min.

Réglages (.env, facultatifs) : RUNPOD_PODS (1), RUNPOD_VCPU (32), RUNPOD_CPU_FLAVOR (cpu5c), RUNPOD_IMAGE,
RUNPOD_MAX_MIN (30 : au-delà, on arrête et le reste se fait en local), RUNPOD_WITH_VPS=1 (RunPod en plus du VPS)."""
import base64
import fcntl
import io
import json
import math
import os
import secrets
import tarfile
import time

import requests

API = "https://rest.runpod.io/v1"
IMAGE = "mcr.microsoft.com/playwright:v1.49.1-noble"  # Node + Chromium headless shell + ses bibliothèques
PART = 16 * 1024 * 1024  # proxys (RunPod, Traefik v3 : 60 s par requête) : le paquet part en petits morceaux
HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(os.path.dirname(HERE), "production", "runpod_worker.js")
ENGINE = os.path.join(os.path.dirname(HERE), "history_engine")
WORK = os.path.abspath(os.environ.get("STUDIO_WORK") or os.path.join(os.path.dirname(HERE), "work"))


def _vps_urls():
    return [u.strip().rstrip("/") for u in (os.getenv("RENDER_WORKERS") or "").split(",") if u.strip()]


def available():
    return bool(os.getenv("RUNPOD_API_KEY") or _vps_urls())


def vps_only():
    """Tout le rendu (morceaux + son) sur le VPS, la machine cloud ne fait que l'assemblage final (demande de
    l'utilisateur, 2 oct. : « utilise 100 % le VPS »). RENDER_LOCAL=1 dans le .env remet le rendu local en parallèle."""
    return bool(_vps_urls()) and os.getenv("RENDER_LOCAL", "0") != "1"


def _h():
    return {"Authorization": "Bearer " + os.environ["RUNPOD_API_KEY"], "Content-Type": "application/json"}


def _create(name, vcpu, token):
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
                    "env": {"WORKER_JS": worker, "WORKER_TOKEN": token},
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


def _status(w):
    try:
        r = requests.get(w["url"] + "/status", headers=w["h"], timeout=20)
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


BUSY = ("bundle", "render", "audio", "unpack", "npm", "fetch")


def _unclaim(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _lock_vps(wait=False, job=None):
    """Le VPS libre : [(worker, fichier verrou)] ; une vidéo à la fois par VPS. wait=True : on attend son tour."""
    out = []
    token = os.getenv("RENDER_WORKER_TOKEN") or ""
    for k, url in enumerate(_vps_urls()):
        lk = open(os.path.join(WORK, f"vps{k}.lock"), "w")
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if not wait:
                lk.close()
                continue
            if job:
                job.update(None, "VPS occupé par une autre vidéo : en attente de son tour…")
            fcntl.flock(lk, fcntl.LOCK_EX)
        w = {"id": f"vps{k}", "url": url, "h": {"X-Worker-Token": token}, "static": True}
        st = _status(w)
        if st is None:
            print(f"[render] VPS {url} injoignable : RunPod ou local à la place", flush=True)
            lk.close()
            continue
        w["cpus"] = int(st.get("cpus") or 8)
        # un rendu lancé par une vidéo précédente (boucle arrêtée, machine redémarrée) peut encore tourner sur le
        # VPS : il écrirait ses morceaux dans le dossier de la vidéo suivante (Gettysburg a reçu un morceau d'Adobe
        # Walls le 2 oct.). On attend qu'il ait fini avant d'envoyer quoi que ce soit.
        t0 = time.time()
        while st and st.get("stage") in BUSY and time.time() - t0 < 1800:
            if job:
                job.update(None, "VPS : un rendu précédent se termine…")
            time.sleep(15)
            st = _status(w) or st
        out.append((w, lk))
    return out


def render(job, media_dir, chunks, size, total, p0=0.05, p1=0.9, stop=None, audio=False, wait=False):
    """Rend à distance les morceaux absents de `chunks` ; ne lève pas d'erreur si une machine échoue. Les morceaux
    arrivent aussi du rendu local en parallèle : la liste est relue sur le disque. stop() → True : on arrête."""
    n = math.ceil(total / size)
    part = lambda i: os.path.join(chunks, f"part_{i:03d}.mp4")  # noqa: E731
    claim = lambda i, who: os.path.join(chunks, f"claim_{i:03d}.{who}")  # noqa: E731  (voir render.mjs --skip-claimed)
    todo = [i for i in range(n) if not os.path.isfile(part(i))]
    wav = os.path.join(chunks, "audio.wav")
    need_audio = audio and not os.path.isfile(wav)
    if not todo and not need_audio:
        return
    record = os.path.join(chunks, "pods.json")
    if os.path.isfile(record) and os.getenv("RUNPOD_API_KEY"):  # pods d'un rendu interrompu : on ne paie pas pour rien
        for pid in json.load(open(record)):
            _delete(pid)
    vps = _lock_vps(wait, job)
    workers = [w for w, _ in vps]
    pods = []
    finished = lambda: bool(stop and stop()) or (all(os.path.isfile(part(i)) for i in range(n))  # noqa: E731
                                                 and not (audio and not os.path.isfile(wav)))
    try:
        if os.getenv("RUNPOD_API_KEY") and (not workers or os.getenv("RUNPOD_WITH_VPS") == "1"):
            count = max(1, min(int(os.getenv("RUNPOD_PODS") or 1), math.ceil(len(todo) / 3) or 1))
            vcpu = int(os.getenv("RUNPOD_VCPU") or 32)
            token = secrets.token_hex(16)
            job.update(p0, f"RunPod : démarrage de {count} machine(s) de {vcpu} cœurs…")
            for k in range(count):
                try:
                    pid, cores = _create(f"drylow-render-{k}", vcpu, token)
                except RuntimeError as e:
                    print(f"[runpod] {e}", flush=True)
                    break
                pods.append(pid)
                vcpu = min(vcpu, cores)
                workers.append({"id": pid, "url": f"https://{pid}-8000.proxy.runpod.net", "h": {"X-Worker-Token": token},
                                "static": False, "cpus": cores})
                json.dump(pods, open(record, "w"))
        if not workers:
            return
        names = " + ".join("VPS" if w["static"] else "RunPod" for w in workers)
        t0 = time.time()
        first = workers[0]
        while time.time() - t0 < 900 and _status(first) is None and not finished():
            time.sleep(8)
        if finished():  # le rendu local a tout fait pendant le démarrage de la machine
            return
        if _status(first) is None:
            raise RuntimeError(f"{names} : la première machine ne répond pas")
        job.update(p0, f"{names} : envoi des images et du moteur…")
        blob = _bundle(media_dir)
        parts = [blob[i:i + PART] for i in range(0, len(blob), PART)]
        for k, chunk in enumerate(parts):
            requests.put(f"{first['url']}/bundle?part={k}", data=chunk, headers=first["h"], timeout=900).raise_for_status()
        requests.post(f"{first['url']}/unpack?parts={len(parts)}", headers=first["h"], timeout=60).raise_for_status()
        others = [w for w in workers[1:] if w["static"]]  # un VPS de plus : il reçoit le paquet directement
        for w in others:
            for k, chunk in enumerate(parts):
                requests.put(f"{w['url']}/bundle?part={k}", data=chunk, headers=w["h"], timeout=900).raise_for_status()
            requests.post(f"{w['url']}/unpack?parts={len(parts)}", headers=w["h"], timeout=60).raise_for_status()
        # file d'attente : chaque machine prend un petit lot de morceaux, puis le suivant ; une machine perdue rend son lot
        queue, inflight, fetched, seen = list(todo), {}, {first["id"]} | {w["id"] for w in others}, {}
        got = set(i for i in range(n) if os.path.isfile(part(i)))
        # limite de temps : RunPod est payant (RUNPOD_MAX_MIN, 30 min) ; le VPS est gratuit, il continue jusqu'au bout
        limit = int(os.getenv("RUNPOD_MAX_MIN") or 30) if pods else 240
        alive, deadline, batch = {w["id"] for w in workers}, time.time() + 60 * limit, 4
        by = {w["id"]: w for w in workers}
        audio_by = None  # la machine qui fait le son (une fois les morceaux distribués)
        while time.time() < deadline and alive and (len(got) < n or (need_audio and not os.path.isfile(wav))):
            if stop and stop():
                break
            got |= set(i for i in range(n) if os.path.isfile(part(i)))  # morceaux faits en local entre-temps
            queue = [i for i in queue if i not in got and not os.path.isfile(claim(i, "local"))]
            head = _status(first)
            for wid in list(alive):
                w = by[wid]
                st = head if wid == first["id"] else _status(w)
                if st is None:
                    if time.time() - seen.get(wid, t0) > 900:  # ne répond plus (ou jamais) : abandonnée
                        alive.discard(wid)
                        back = [i for i in inflight.pop(wid, []) if i not in got]
                        for i in back:
                            _unclaim(claim(i, "rp"))
                        queue[:0] = back
                    continue
                seen[wid] = time.time()
                if not st.get("ready"):
                    if wid not in fetched and st.get("stage") == "idle" and head and head.get("ready"):
                        requests.post(f"{w['url']}/fetch?from={first['url']}", headers=w["h"], timeout=60)
                        fetched.add(wid)
                    if st.get("stage") == "failed":
                        print(f"[render] {wid} : {st.get('error')} {st.get('log', [])[-2:]}", flush=True)
                        alive.discard(wid)
                    continue
                asked = set(inflight.get(wid) or [])
                for f in st.get("files") or []:
                    dest = os.path.join(chunks, f)
                    if os.path.isfile(dest) or (f == "audio.wav" and not (need_audio and audio_by == wid)):
                        continue
                    if f != "audio.wav" and int(f[5:8]) not in asked:
                        continue  # morceau qu'on n'a pas demandé à cette machine : pas le nôtre
                    r = requests.get(f"{w['url']}/file/{f}", headers=w["h"], timeout=600)
                    if r.status_code == 200:
                        open(dest + ".dl", "wb").write(r.content)
                        os.replace(dest + ".dl", dest)
                        if f != "audio.wav":
                            got.add(int(f[5:8]))
                busy = (wid in inflight or audio_by == wid) and st.get("stage") not in ("done", "failed")
                if audio_by == wid and not busy:
                    audio_by = None  # son fini (téléchargé ci-dessus) ou raté : redemandé plus bas si besoin
                if wid in inflight and not busy:
                    back = [i for i in inflight.pop(wid) if i not in got]
                    for i in back:
                        _unclaim(claim(i, "rp"))
                    queue[:0] = back
                    if st.get("stage") == "failed":
                        print(f"[render] {wid} : {st.get('error')} {st.get('log', [])[-2:]}", flush=True)
                if not busy and not queue and need_audio and not os.path.isfile(wav) and audio_by is None:
                    requests.post(f"{w['url']}/render?chunks=&frames={size}&audio=only&conc={max(1, w['cpus'] * 3 // 4)}",
                                  headers=w["h"], timeout=60)
                    audio_by = wid
                    continue
                if not busy and not queue and audio_by != wid:
                    if not w["static"]:
                        _delete(wid)  # plus rien à lui donner : on arrête de payer cette machine tout de suite
                    alive.discard(wid)
                    continue
                if not busy:
                    mine, queue = queue[:batch], queue[batch:]
                    for i in mine:
                        open(claim(i, "rp"), "w").close()
                    requests.post(f"{w['url']}/render?chunks={','.join(map(str, mine))}&frames={size}&audio=0"
                                  f"&conc={max(1, w['cpus'] * 3 // 4)}", headers=w["h"], timeout=60)
                    inflight[wid] = mine
            job.update(p0 + (p1 - p0) * len(got) / n, f"{names} : {len(got)}/{n} morceaux rendus")
            time.sleep(10)
    finally:
        for pid in pods:
            _delete(pid)
        for w, lk in vps:  # le VPS n'est libéré qu'une fois ses rendus en cours terminés (sinon : vidéos mélangées)
            t0 = time.time()
            while time.time() - t0 < 1800:
                st = _status(w)
                if not st or st.get("stage") not in BUSY:
                    break
                time.sleep(15)
            lk.close()
        for f in os.listdir(chunks):
            if f.endswith(".rp"):
                _unclaim(os.path.join(chunks, f))
        try:
            os.remove(record)
        except OSError:
            pass
