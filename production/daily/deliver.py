"""Livre une vidéo TubeForge finie au Claude du PC : MP4 vérifié, son mis au niveau, Gofile, fiche de publication.

    python production/daily/deliver.py <video_id> --channel "Viking Chapters" --episode chaines/viking-chapters/episode-02 \
        --title "…" --thumbnail chaines/…/thumbnail.jpg [--visibility public|scheduled --publish-at 2026-10-15T10:00]

Le dossier d'épisode doit contenir `description.txt` (description finale avec chapitres). Le script :
1. télécharge le MP4 rendu sur le VPS et ses sous-titres (dans work/daily/<video_id>/, ignoré par git) ;
2. mesure le volume ; sous -18 LUFS, refait seulement l'audio à -14 LUFS (image copiée telle quelle) ;
3. vérifie le décodage complet, envoie sur Gofile (MD5 vérifié) ;
4. écrit `English-Captions.srt` dans le dossier d'épisode et la fiche `production/publish/queue/…json`.
Ne commit rien : relire, puis commit + push sur main.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "production"))
sys.path.insert(0, str(ROOT / "production" / "daily"))
import forge_flow as ff  # noqa: E402
from common import gofile_upload  # noqa: E402
import imageio_ffmpeg  # noqa: E402

FF = imageio_ffmpeg.get_ffmpeg_exe()
CHANNELS = {c["name"] for c in json.loads((ROOT / "production/publish/channels.json").read_text())["channels"]}


def download(video_id, kind, out):
    if out.exists() and out.stat().st_size:
        return out
    with ff.forge.request("GET", ff.vid(video_id) + "/download?kind=" + kind) as res, open(out, "wb") as f:
        while chunk := res.read(1 << 20):
            f.write(chunk)
    return out


def loudness(path):
    err = subprocess.run([FF, "-hide_banner", "-i", str(path), "-vn", "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    return float(m[-1]) if m else None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--channel", required=True)
    ap.add_argument("--episode", required=True, type=Path)
    ap.add_argument("--title", required=True)
    ap.add_argument("--thumbnail", required=True, type=Path)
    ap.add_argument("--visibility", default="public", choices=["public", "unlisted", "private", "scheduled"])
    ap.add_argument("--publish-at")
    a = ap.parse_args()
    if a.channel not in CHANNELS:
        raise SystemExit(f"chaîne inconnue : {a.channel}")
    if a.visibility == "scheduled" and not a.publish_at:
        raise SystemExit("--publish-at obligatoire pour une vidéo programmée")
    episode = (ROOT / a.episode) if not a.episode.is_absolute() else a.episode
    description = episode / "description.txt"
    thumb = (ROOT / a.thumbnail) if not a.thumbnail.is_absolute() else a.thumbnail
    for need in (description, thumb):
        if not need.exists():
            raise SystemExit(f"manquant : {need}")
    work = ROOT / "work" / "daily" / a.video_id
    work.mkdir(parents=True, exist_ok=True)
    raw = download(a.video_id, "video", work / "render.mp4")
    srt = download(a.video_id, "subtitles", work / "captions.srt")
    level = loudness(raw)
    final = work / "final.mp4"
    if level is not None and level < -18:
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "copy", "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                        "-movflags", "+faststart", str(final)], check=True)
    elif not final.exists():
        final.write_bytes(raw.read_bytes())
    check = subprocess.run([FF, "-v", "error", "-i", str(final), "-f", "null", "-"], capture_output=True, text=True)
    if check.stderr.strip():
        raise SystemExit("décodage en erreur : " + check.stderr[:300])
    after = loudness(final)
    digest = sha256(final)
    # Un lien par empreinte : un nouveau montage est toujours renvoyé, jamais remplacé par l'ancien lien.
    link = gofile_upload(str(final), str(work / f"gofile_link-{digest[:16]}.txt"), lambda *m: print(*m))
    (episode / "English-Captions.srt").write_bytes(srt.read_bytes())
    slug = re.sub(r"[^a-z0-9]+", "-", a.channel.lower()).strip("-") + "--" + episode.name
    fiche = {
        "channel": a.channel,
        "title": a.title,
        "description_file": str(description.relative_to(ROOT)),
        "video": {"gofile": link, "file": final.name, "sha256": digest},
        "thumbnail": str(thumb.relative_to(ROOT)),
        "captions": str((episode / "English-Captions.srt").relative_to(ROOT)),
        **({"tags_file": str((episode / "tags.txt").relative_to(ROOT))} if (episode / "tags.txt").exists() else {}),
        "visibility": a.visibility,
        **({"publish_at": a.publish_at} if a.publish_at else {}),
        "tubeforge_video_id": a.video_id,
    }
    out = ROOT / "production/publish/queue" / f"{slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fiche, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"son {level} → {after} LUFS | sha256 {digest[:16]}… | {link} | fiche {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
