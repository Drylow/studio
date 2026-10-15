"""Met le MP4 d'une fiche sur le serveur du studio (media.edgerunners.fr) et ajoute `video.url` à la fiche.

    python production/daily/host_video.py production/publish/queue/<fiche>.json [...]
    python production/daily/host_video.py production/publish/queue/<fiche>.json --mp4 /chemin/video.mp4

Le PC télécharge `video.url` en priorité : un simple GET, sans page ni jeton (Gofile bloque les passages
automatiques depuis le 14 oct.). Le fichier part sous un nom imprévisible dans ~/media_files (sans liste du
dossier), puis il est retéléchargé ici et son SHA-256 comparé à celui de la fiche avant d'écrire le lien.
Le MP4 local vient de work/daily/<tubeforge_video_id>/final.mp4 (écrit par deliver.py), ou du fichier donné
avec --mp4 (une seule fiche ; vidéos montées hors TubeForge, ex. Scene Analysis Guy).
"""
import argparse
import hashlib
import json
import secrets
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "production"))
import cpanel  # noqa: E402

BASE = "http://media.edgerunners.fr"
PART = 400 * 1024 * 1024


def sha256_url(url):
    h = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=600) as r:
        while chunk := r.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def host(fiche_path, mp4=None):
    fiche_path = Path(fiche_path)
    fiche = json.loads(fiche_path.read_text(encoding="utf-8"))
    video = fiche["video"]
    local = Path(mp4).resolve() if mp4 else ROOT / "work/daily" / fiche["tubeforge_video_id"] / "final.mp4"
    work = local.parent
    if hashlib.sha256(local.read_bytes()).hexdigest() != video["sha256"]:
        raise SystemExit(f"{fiche_path.name} : le MP4 local ne correspond pas à la fiche")
    name = f"{fiche_path.stem}-{secrets.token_hex(8)}.mp4"
    data = local.read_bytes()
    # cPanel refuse un envoi de plus de ~512 Mo : au-delà, morceaux de 400 Mo recollés sur le serveur.
    parts = [data[i:i + PART] for i in range(0, len(data), PART)]
    names = [name] if len(parts) == 1 else [f"{name}.part{k}" for k in range(len(parts))]
    for part_name, chunk in zip(names, parts):
        tmp = work / part_name
        tmp.write_bytes(chunk)
        try:
            for attempt in range(4):   # cPanel renvoie parfois une redirection passagère (308)
                try:
                    status, errors = cpanel.put(str(tmp), "media_files")
                    break
                except Exception:  # noqa: BLE001
                    if attempt == 3:
                        raise
                    time.sleep(10)
        finally:
            tmp.unlink(missing_ok=True)
        if status != 1:
            raise SystemExit(f"{fiche_path.name} : envoi refusé {errors}")
    if len(parts) > 1:
        joined = " ".join(names)
        for attempt in range(8):   # le terminal cPanel répond parfois « Handshake 400 » : on réessaie
            try:
                cpanel.shell(f"cd ~/media_files && cat {joined} > {name} && rm -f {joined} && ls -l {name}", timeout=300)
                break
            except Exception:  # noqa: BLE001
                if attempt == 7:
                    raise
                time.sleep(5)
    url = f"{BASE}/{name}"
    if sha256_url(url) != video["sha256"]:
        raise SystemExit(f"{fiche_path.name} : le fichier en ligne ne correspond pas")
    video["url"] = url
    fiche_path.write_text(json.dumps(fiche, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{fiche_path.name} : {url} (SHA-256 vérifié)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Héberge le MP4 d'une ou plusieurs fiches sur media.edgerunners.fr")
    parser.add_argument("fiches", nargs="+")
    parser.add_argument("--mp4", help="MP4 local à envoyer (une seule fiche)")
    args = parser.parse_args()
    if args.mp4 and len(args.fiches) != 1:
        raise SystemExit("--mp4 s'utilise avec une seule fiche")
    for path in args.fiches:
        host(path, args.mp4)
