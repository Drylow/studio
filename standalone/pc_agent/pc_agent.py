"""Agent du PC de l'utilisateur : monte les vidéos d'actu que Claude prépare dans le cloud.

YouTube bloque les serveurs (cloud, VPS) mais pas une connexion de maison. Lancé toutes les 15 min par la tâche
Windows « Drylow Actu » (installée une fois, avec l'accord de l'utilisateur, par Installer.bat ; Desinstaller.bat
l'enlève), sans fenêtre (pythonw.exe). Chaque passage reste à l'écoute ~14 min (le suivant prend le relais) : toutes
les 20 s, demande au relais (VPS, config.json) s'il y a une vidéo à monter ; si oui la télécharge (code du montage +
plan + voix off), télécharge les extraits YouTube, monte, envoie sur Gofile, renvoie lien + planches de contrôle au
relais, efface tout (clips, segments, vidéo), puis passe tout de suite à la suivante.
(Mis à jour par le montage lui-même : news.py build recopie la dernière version de ce fichier.)
"""
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "work")
DENO_DIR = os.path.join(HERE, "tools", "deno")
LOG = os.path.join(HERE, "agent.log")
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
PY = os.path.join(os.path.dirname(sys.executable), "python.exe" if os.name == "nt" else os.path.basename(sys.executable))
if not os.path.isfile(PY):
    PY = sys.executable
with open(os.path.join(HERE, "config.json"), "r", encoding="utf-8") as _f:
    CFG = json.load(_f)


def log(*a):
    try:
        if os.path.isfile(LOG) and os.path.getsize(LOG) > 2_000_000:
            os.replace(LOG, LOG + ".old")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a) + "\n")
    except OSError:
        pass


def call(method, path, data=None, timeout=60):
    req = urllib.request.Request(CFG["url"].rstrip("/") + path, data=data, method=method,
                                 headers={"X-Worker-Token": CFG["token"]})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def single_instance():
    """Un seul agent à la fois (un montage dure jusqu'à 1 h, la tâche repasse toutes les 15 min)."""
    fh = open(os.path.join(HERE, "agent.lock"), "a+")
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return fh


def tools():
    """deno (moteur JavaScript dont yt-dlp a besoin pour YouTube) + yt-dlp à jour une fois par jour."""
    exe = os.path.join(DENO_DIR, "deno.exe" if os.name == "nt" else "deno")
    if not os.path.isfile(exe):
        os.makedirs(DENO_DIR, exist_ok=True)
        name = "deno-x86_64-pc-windows-msvc.zip" if os.name == "nt" else "deno-x86_64-unknown-linux-gnu.zip"
        with urllib.request.urlopen("https://github.com/denoland/deno/releases/latest/download/" + name,
                                    timeout=600) as r:
            zipfile.ZipFile(io.BytesIO(r.read())).extractall(DENO_DIR)
    stamp = os.path.join(HERE, "tools", "ytdlp_updated")
    if not os.path.isfile(stamp) or time.time() - os.path.getmtime(stamp) > 86400:
        subprocess.run([PY, "-m", "pip", "install", "-q", "-U", "--disable-pip-version-check",
                        "--no-warn-script-location", "yt-dlp[default]"], creationflags=NO_WINDOW, check=False)
        open(stamp, "w").close()


def send_results(name, jobdir):
    for rel in ["build.log", "result.json"] + [os.path.relpath(p, jobdir).replace("\\", "/")
                                               for p in sorted(glob.glob(os.path.join(jobdir, "check", "sheet_*.jpg")))]:
        p = os.path.join(jobdir, rel)
        if os.path.isfile(p):
            with open(p, "rb") as f:
                call("PUT", f"/pc/result?name={name}&path={rel}", data=f.read(), timeout=300)


def build(name):
    d = os.path.join(WORK, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    code, raw = call("GET", f"/pc/job?name={name}", timeout=900)
    if code != 200:
        raise RuntimeError(f"téléchargement de la vidéo préparée : {code}")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as t:
        for m in t.getmembers():
            if not (m.isfile() or m.isdir()) or m.name.startswith(("/", "..")) or "/../" in m.name:
                raise RuntimeError(f"entrée refusée : {m.name}")
        t.extractall(d)
    jobdir = os.path.join(d, name)                 # le nom du dossier = le nom du fichier envoyé sur Gofile
    os.replace(os.path.join(d, "job"), jobdir)
    src = os.path.join(d, "code")
    env = dict(os.environ, STUDIO_WORK=os.path.join(WORK, "build"))
    env["PATH"] = DENO_DIR + os.pathsep + env.get("PATH", "")
    # Python embarqué : le dossier du script n'est pas dans sys.path → on le met avant de lancer news.py
    runner = ("import sys, runpy; sys.path[:0] = [{0!r}, {1!r}]; sys.argv = ['news.py', 'build', {2!r}]; "
              "runpy.run_path({3!r}, run_name='__main__')").format(
        src, os.path.join(src, "production"), jobdir, os.path.join(src, "production", "news.py"))
    with open(os.path.join(jobdir, "agent_build.out"), "a", encoding="utf-8") as out:
        p = subprocess.Popen([PY, "-c", runner], cwd=src, env=env, stdout=out, stderr=subprocess.STDOUT,
                             creationflags=NO_WINDOW)
        while p.poll() is None:
            time.sleep(60)
            send_results(name, jobdir)            # build.log au fil de l'eau : Claude suit l'avancée
    log(f"{name} : montage terminé (code {p.returncode})")
    if p.returncode != 0:
        with open(os.path.join(jobdir, "build.log"), "a", encoding="utf-8") as f:
            f.write("ERREUR : montage arrêté, fin de la sortie :\n")
            with open(os.path.join(jobdir, "agent_build.out"), "r", encoding="utf-8", errors="replace") as o:
                f.write("".join(o.readlines()[-30:]))
    send_results(name, jobdir)
    ok = os.path.isfile(os.path.join(jobdir, "result.json"))
    call("POST", f"/pc/done?name={name}&ok={1 if ok else 0}")
    return ok


LISTEN = 14 * 60     # la tâche Windows relance l'agent toutes les 15 min : il écoute jusque-là
POLL = 20            # secondes entre deux questions au relais


def main():
    lock = single_instance()
    if lock is None:
        return
    shutil.rmtree(WORK, ignore_errors=True)        # restes d'un montage coupé (PC éteint) : jamais de clips qui traînent
    t0 = time.time()
    while time.time() - t0 < LISTEN:
        try:
            code, body = call("GET", "/pc/next", timeout=30)
        except (OSError, ValueError) as e:          # réseau coupé : on réessaie au prochain tour
            log("relais injoignable :", e)
            time.sleep(POLL)
            continue
        if code != 200:
            log("relais injoignable :", code, body[:200])
            time.sleep(POLL)
            continue
        name = json.loads(body).get("name")
        if not name:
            time.sleep(POLL)
            continue
        log(f"{name} : à monter")
        try:
            tools()
            build(name)
        except Exception as e:  # noqa: BLE001
            log(f"{name} : ERREUR {e}")
            call("PUT", f"/pc/result?name={name}&path=build.log", data=f"ERREUR agent PC : {e}\n".encode())
            call("POST", f"/pc/done?name={name}&ok=0")
        finally:
            shutil.rmtree(WORK, ignore_errors=True)    # rien ne reste sur le PC : clips, segments, vidéo, code
        t0 = time.time()                               # après un montage, on réécoute 14 min


if __name__ == "__main__":
    main()
