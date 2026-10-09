"""Deliver a reviewed preview or publication kit to Scene Analysis Guy's Discord.

Usage: python experiments/conversation-chess/deliver-discord.py delivery.json [--dry-run]
The dedicated webhook stays in .env; there is no fallback to another channel.
"""
import argparse
import fcntl
import hashlib
import json
import mimetypes
import os
import re
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
WEBHOOK_VARIABLE = "DISCORD_WEBHOOK_SCENE_ANALYSIS_GUY"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def prepare(manifest):
    folder = manifest.parent
    data = json.loads(manifest.read_text(encoding="utf-8"))
    resolve = lambda name: (folder / data[name]).resolve()
    kind = data["kind"]
    if kind not in ("preview", "final", "youtube-test"):
        raise ValueError("Le paquet doit être un aperçu, une vidéo finale ou une version à tester sur YouTube.")
    video = resolve("video")
    video_hash = digest(video)
    review = json.loads(resolve("review").read_text(encoding="utf-8"))
    if review.get("sha256") != video_hash or not review.get("full_video_audio_decode_ok") \
            or not review.get("finished_render_visual_reviewed"):
        raise ValueError("Le contrôle doit correspondre au fichier vidéo envoyé.")
    link = data["gofile_url"]
    uploaded = json.loads(resolve("upload_receipt").read_text(encoding="utf-8"))
    if not re.fullmatch(r"https://gofile\.io/d/[A-Za-z0-9]+", link) or uploaded.get("url") != link:
        raise ValueError("Le lien doit correspondre au reçu GoFile vérifié.")
    if not any(f.get("sha256") == video_hash and f.get("bytes") == video.stat().st_size
               for f in uploaded.get("files", [])):
        raise ValueError("La vidéo ne correspond pas au reçu GoFile.")
    title = data["title"].strip()
    if not title or len(title) > 100:
        raise ValueError("Titre YouTube absent ou trop long.")
    description = resolve("description").read_text(encoding="utf-8").strip()
    credits = resolve("music_credits").read_text(encoding="utf-8").strip()
    if not description or not credits:
        raise ValueError("Description et crédits musicaux requis.")
    if data.get("chapters"):
        description += "\n\nChapters\n" + "\n".join(data["chapters"])
    description += "\n\nMusic credits\n" + credits
    if len(description) > 5000:
        raise ValueError("Description trop longue pour YouTube.")
    status = {"preview": "APERÇU — à regarder, pas destiné à publication",
              "final": "Vidéo vérifiée — à publier manuellement",
              "youtube-test": "VERSION À TESTER SUR YOUTUBE — épisode 8 retiré"}[kind]
    kit = f"Scene Analysis Guy\n{status}\n\nDOWNLOAD\n{link}\n\nTITLE\n{title}\n\nDESCRIPTION\n{description}\n"
    if data.get("tags"):
        kit += "\nTAGS\n" + ", ".join(data["tags"]) + "\n"
    if data.get("pinned_comment"):
        kit += "\nPINNED COMMENT\n" + data["pinned_comment"] + "\n"
    kit_path = folder / "Kit_publication.txt"
    kit_path.write_text(kit, encoding="utf-8")
    files = [kit_path, resolve("music_credits")]
    cover = {"title": "Scene Analysis Guy — " + title, "url": link, "color": 0x81B64C}
    if kind in ("final", "youtube-test"):
        if not review.get("source_quality", {}).get("accepted_for_final"):
            raise ValueError("La qualité des sources doit être acceptée avant la livraison finale.")
        thumbnail = resolve("thumbnail")
        if thumbnail.suffix.lower() not in (".png", ".jpg", ".jpeg") or not thumbnail.is_file():
            raise ValueError("Miniature finale absente ou invalide.")
        files.append(thumbnail)
        cover["image"] = {"url": "attachment://" + thumbnail.name}
    embeds = [cover]
    if len(description) <= 4096:
        embeds.append({"title": "Description et crédits à copier", "description": description,
                       "color": 0x81B64C})
    payload = {"content": f"🎬 **Scene Analysis Guy**\n**{status}**\n🔗 <{link}>\n"
               "Titre, description et crédits dans le kit joint.",
               "embeds": embeds, "allowed_mentions": {"parse": []}}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()
                                 + "".join(digest(p) for p in files).encode()).hexdigest()
    return payload, files, fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    payload, paths, fingerprint = prepare(manifest)
    if args.dry_run:
        print(json.dumps({"payload": payload, "attachments": [p.name for p in paths]},
                         indent=2, ensure_ascii=False))
        return
    load_dotenv(ROOT / ".env")
    url = os.environ.get(WEBHOOK_VARIABLE, "")
    match = re.fullmatch(r"https://discord\.com/api/webhooks/(\d+)/[A-Za-z0-9_.-]+", url)
    if not match:
        raise ValueError("Webhook propre à Scene Analysis Guy absent ou invalide.")
    receipt_path = manifest.parent / "discord_receipt.json"
    pending_path = manifest.parent / "discord_pending.json"
    lock_path = ROOT / "work/discord.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if receipt_path.exists():
            previous = json.loads(receipt_path.read_text())
            if previous.get("fingerprint") == fingerprint and previous.get("webhook_id") == match[1]:
                print("Discord : ce paquet est déjà envoyé.")
                return
        if pending_path.exists():
            raise ValueError("Envoi précédent incertain : contrôler le salon avant de renvoyer.")
        save(pending_path, {"fingerprint": fingerprint, "webhook_id": match[1]})
        with ExitStack() as stack:
            files = {f"files[{i}]": (p.name, stack.enter_context(p.open("rb")),
                     mimetypes.guess_type(p.name)[0] or "application/octet-stream") for i, p in enumerate(paths)}
            try:
                response = requests.post(url, params={"wait": "true"},
                                         data={"payload_json": json.dumps(payload)}, files=files,
                                         timeout=(10, 40))
            except requests.RequestException:
                raise RuntimeError("Confirmation Discord indisponible : aucun renvoi automatique.") from None
        if response.status_code != 200:
            if 400 <= response.status_code < 500:
                pending_path.unlink()
            raise RuntimeError(f"Envoi Discord refusé ou incertain (HTTP {response.status_code}).")
        message = response.json()
        names = {a["filename"] for a in message.get("attachments", [])}
        for embed in message.get("embeds", []):
            image = embed.get("image", {}).get("url", "")
            names.update(p.name for p in paths if urlparse(image).path.endswith("/" + p.name)
                         or image == "attachment://" + p.name)
        if not message.get("id") or not {p.name for p in paths}.issubset(names):
            raise RuntimeError("Confirmation Discord incomplète : aucun renvoi automatique.")
        save(receipt_path, {"message_id": message["id"], "channel_id": message["channel_id"],
                           "webhook_id": match[1], "fingerprint": fingerprint,
                           "attachments": sorted(names),
                           "sent_at": datetime.now(timezone.utc).isoformat()})
        pending_path.unlink()
        print("Discord : message et pièces jointes confirmés.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
