"""Helpers ffmpeg partagés (voix off + montage).

Binaire : FFMPEG_BIN du .env s'il existe, sinon celui du PATH, sinon celui
embarqué par le paquet pip `imageio-ffmpeg` (aucune install manuelle sur PC).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

_FFMPEG = None


class MediaError(Exception):
    pass


def ffmpeg_bin():
    global _FFMPEG
    if _FFMPEG:
        return _FFMPEG
    cand = (os.getenv("FFMPEG_BIN") or "").strip()
    if cand and (os.path.isfile(cand) or shutil.which(cand)):
        _FFMPEG = shutil.which(cand) or cand
        return _FFMPEG
    found = shutil.which("ffmpeg")
    if found:
        _FFMPEG = found
        return _FFMPEG
    try:
        import imageio_ffmpeg
        _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
        return _FFMPEG
    except Exception:
        raise MediaError("ffmpeg introuvable : installe-le ou fais `pip install imageio-ffmpeg`.")


def available():
    try:
        ffmpeg_bin()
        return True
    except MediaError:
        return False


_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0  # pas de console qui clignote


class Cancelled(Exception):
    """Opération ffmpeg interrompue à la demande (bouton Annuler)."""


def capped(args):
    """FFMPEG_THREADS caps ffmpeg's threads: shared hosting shows many cores but
    limits processes per account, and ffmpeg's automatic choice then fails (EAGAIN)."""
    try:
        n = int(os.environ.get("FFMPEG_THREADS", "0"))
    except ValueError:
        n = 0
    if n <= 0 or not args:
        return args
    return (["-filter_threads", str(n), "-filter_complex_threads", str(n)]
            + args[:-1] + ["-threads", str(n), args[-1]])


def run(args, cwd=None, timeout=None, cancelled=None):
    """Lance ffmpeg ; lève MediaError avec la fin de stderr en cas d'échec.

    `cancelled` (callable) est interrogé pendant l'exécution : s'il renvoie True,
    le process ffmpeg est tué et Cancelled est levée (annulation immédiate)."""
    cmd = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-y"] + capped(list(args))
    if cancelled is None:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout, creationflags=_NO_WINDOW)
        if p.returncode != 0:
            tail = p.stderr.decode("utf-8", "replace").strip().splitlines()[-12:]
            raise MediaError("ffmpeg a échoué:\n" + "\n".join(tail))
        return p
    # stderr dans un fichier temporaire : pas de pipe plein qui bloquerait ffmpeg
    with tempfile.TemporaryFile() as err:
        p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=err, creationflags=_NO_WINDOW)
        t0 = time.time()
        while p.poll() is None:
            if cancelled() or (timeout and time.time() - t0 > timeout):
                p.kill()
                p.wait()
                raise Cancelled("Annulé.")
            time.sleep(0.25)
        if p.returncode != 0:
            err.seek(0)
            tail = err.read().decode("utf-8", "replace").strip().splitlines()[-12:]
            raise MediaError("ffmpeg a échoué:\n" + "\n".join(tail))
    return p


_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def duration(path):
    """Durée exacte (décodage complet → fiable même pour du MP3 VBR)."""
    p = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostdin", "-i", path, "-f", "null", "-"],
                       capture_output=True, creationflags=_NO_WINDOW)
    err = p.stderr.decode("utf-8", "replace")
    times = _TIME_RE.findall(err)
    if times:
        h, m, s = times[-1]
        return int(h) * 3600 + int(m) * 60 + float(s)
    d = _DUR_RE.search(err)
    if d:
        h, m, s = d.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)
    raise MediaError("Durée illisible pour " + os.path.basename(path))


def concat_audio(paths, dest, bitrate="192k"):
    """Concatène des fichiers audio (réencodage → timings exacts) en MP3."""
    if len(paths) == 1:
        run(["-i", paths[0], "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", bitrate, dest])
        return dest
    args = []
    for p in paths:
        args += ["-i", p]
    n = len(paths)
    graph = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    run(args + ["-filter_complex", graph, "-map", "[a]", "-ar", "44100", "-ac", "1",
                "-c:a", "libmp3lame", "-b:a", bitrate, dest])
    return dest
