"""Deliver a reviewed news analysis to its channel's Discord webhook on request."""
import datetime
import fcntl
import hashlib
import json
import os
import re
import time
import zipfile
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlparse

import requests

from services import newsvid
from services.news_brief import save_json


def confirmed_files(message):
    names = {a["filename"] for a in message.get("attachments", [])}
    # Discord can move an image used by an embed out of attachments[].
    if any(urlparse(e.get("image", {}).get("url", "")).path.endswith("/miniature.jpg")
           or e.get("image", {}).get("url") == "attachment://miniature.jpg"
           for e in message.get("embeds", [])):
        names.add("miniature.jpg")
    if not message.get("id") or not {"miniature.jpg", "Kit_publication.zip"}.issubset(names):
        raise RuntimeError("L'envoi Discord doit être contrôlé : confirmation des pièces jointes incomplète.")
    return sorted(names)


def prepare(job, work_root):
    job = Path(job)
    plan = json.loads((job / "brief.json").read_text(encoding="utf-8"))
    result = json.loads((job / "result.json").read_text(encoding="utf-8"))
    if not (job / "review_ok").exists() or result.get("review_required") is not False:
        raise ValueError("La vidéo doit être vérifiée avant l'envoi Discord.")
    link = result.get("link", "")
    if not re.fullmatch(r"https://gofile\.io/d/[A-Za-z0-9]+", link):
        raise ValueError("Lien Gofile absent ou invalide.")
    channel = newsvid.channel(plan["channel"])
    color = int(channel["accent"].lstrip("#"), 16)
    titles = plan.get("title_options") or [plan["title"]]
    choice = (job / "thumb_choice.txt").read_text().strip()
    if choice not in ("thumb_A.jpg", "thumb_B.jpg"):
        raise ValueError("Miniature validée absente.")
    thumb = job / "thumb.jpg"
    if thumb.read_bytes() != (job / choice).read_bytes():
        raise ValueError("La miniature ne correspond pas au choix validé.")
    fields = [{"name": "Titres proposés", "value": "\n".join(
        f"{i + 1}. {title}" for i, title in enumerate(titles))}]
    embeds = [{"title": channel["brand"] + " — " + titles[0], "url": link,
               "color": color, "fields": fields,
               "image": {"url": "attachment://miniature.jpg"}},
              {"title": "Description et chapitres", "color": color,
               "description": (job / "description.txt").read_text().strip()},
              {"title": "Tags", "color": color,
               "description": (job / "tags.txt").read_text().strip()}]
    if plan.get("pinned_comment"):
        embeds.append({"title": "Commentaire épinglé proposé", "color": color,
                       "description": plan["pinned_comment"]})
    for embed in embeds:
        if len(embed.get("title", "")) > 256 or len(embed.get("description", "")) > 4096:
            raise ValueError("Texte trop long pour Discord : ajuster avant l'envoi.")
        if any(len(f["value"]) > 1024 for f in embed.get("fields", [])):
            raise ValueError("Titres trop longs pour Discord.")
    size = sum(len(e.get("title", "")) + len(e.get("description", "")) +
               sum(len(f["name"]) + len(f["value"]) for f in e.get("fields", [])) for e in embeds)
    if size > 5900:
        raise ValueError("Le paquet dépasse la limite Discord.")
    payload = {"content": f"🎬 **{channel['brand']} — {titles[0]}**\n"
               f"✅ Vérifiée, à publier manuellement — {result['minutes']} min\n"
               f"🔗 **Vidéo MP4** : <{link}>\n"
               "🖼️ Miniature validée et kit de publication joints.",
               "embeds": embeds, "allowed_mentions": {"parse": []}}
    work = Path(work_root) / "news_brief" / job.name
    work.mkdir(parents=True, exist_ok=True)
    kit = work / "Kit_publication_Discord.zip"
    with zipfile.ZipFile(kit, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ("thumb.jpg", "publication.md", "description.txt", "tags.txt",
                     "captions.srt", "thumbnail_credits.json", "script.txt"):
            archive.write(job / name, name)
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode() +
                                 thumb.read_bytes()).hexdigest()
    return plan, payload, thumb, kit, fingerprint


def send(job, work_root, dry_run=False):
    job, work_root = Path(job), Path(work_root)
    plan, payload, thumb, kit, fingerprint = prepare(job, work_root)
    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    url = os.environ.get("DISCORD_WEBHOOK_" + plan["channel"].upper(), "")
    match = re.fullmatch(r"https://discord\.com/api/webhooks/(\d+)/[A-Za-z0-9_.-]+", url)
    if not match:
        raise ValueError("Webhook Discord de cette chaîne absent ou invalide dans .env.")
    receipt_path = job / "discord_receipt.json"
    with (work_root / "discord.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            if receipt.get("fingerprint") == fingerprint and receipt.get("webhook_id") == match[1]:
                print("Discord : ce paquet est déjà envoyé.")
                return receipt
        for _ in range(3):
            with ExitStack() as stack:
                files = {"files[0]": ("miniature.jpg", stack.enter_context(thumb.open("rb")), "image/jpeg"),
                         "files[1]": ("Kit_publication.zip", stack.enter_context(kit.open("rb")), "application/zip")}
                try:
                    response = requests.post(url, params={"wait": "true"},
                                             data={"payload_json": json.dumps(payload)}, files=files,
                                             timeout=(15, 90))
                except requests.RequestException:
                    raise RuntimeError("Réponse Discord indisponible : vérifier le salon avant une relance.") from None
            if response.status_code == 429:
                delay = float(response.json().get("retry_after", 1)) + 0.2
                if delay > 45:
                    raise RuntimeError("Discord limite les envois : réessayer plus tard.")
                time.sleep(delay)
                continue
            if response.status_code != 200:
                raise RuntimeError(f"Discord refuse le paquet (HTTP {response.status_code}).")
            message = response.json()
            save_json(work_root / "news_brief" / job.name / "discord_response.json",
                      {"id": message.get("id"), "channel_id": message.get("channel_id"),
                       "attachments": [{"id": a.get("id"), "filename": a.get("filename")}
                                       for a in message.get("attachments", [])],
                       "embed_images": [e.get("image", {}).get("url") for e in message.get("embeds", [])
                                        if e.get("image")]})
            attachments = confirmed_files(message)
            receipt = {"sent_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       "channel": plan["channel"], "channel_id": message["channel_id"],
                       "message_id": message["id"], "webhook_id": match[1],
                       "fingerprint": fingerprint, "link": json.loads((job / "result.json").read_text())["link"],
                       "attachments": attachments}
            save_json(receipt_path, receipt)
            (job / "discord_done").write_text(receipt["link"] + "\n")
            print(f"Discord : {newsvid.channel(plan['channel'])['brand']} — paquet et pièces jointes confirmés.")
            return receipt
        raise RuntimeError("Discord limite encore les envois : réessayer plus tard.")
