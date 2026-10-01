"""Envoie le paquet de publication d'une vidéo sur Discord : lien vidéo + miniature, titre, description
(+ chapitres), tags, commentaire épinglé. Marque = nom du studio de la chaîne (Oddly Specific Lives…).

  python production/discord_send.py <folder> <lien_gofile> [--link-only]

Le dossier doit avoir meta.json (écrit au rendu) et thumb_choice.txt (chemin de la miniature choisie).
Webhook : DISCORD_WEBHOOK_URL dans .env (jamais dans git)."""
import fcntl
import json
import os
import sys
import time

import requests

from common import WORK, folder, webhook
from services import pov_engine as E

D = folder(sys.argv[1])
link = sys.argv[2] if len(sys.argv) > 2 else ""
URL = webhook() + "?wait=true"
info = json.load(open(os.path.join(D, "video.json"))) if os.path.isfile(os.path.join(D, "video.json")) else {}
BRAND = ((E.TEMPLATES.get(info.get("template") or "", {}).get("studio") or {}).get("brand")) or "Video"
meta = json.load(open(os.path.join(D, "meta.json")))
thumb = open(os.path.join(D, "thumb_choice.txt")).read().strip()


def post(content, file=None):
    data = {"content": content, "flags": 4, "allowed_mentions": {"parse": []}}  # 4 = pas d'aperçu de lien
    for _ in range(4):
        if file:
            r = requests.post(URL, data={"payload_json": json.dumps(data)},
                              files={"files[0]": ("miniature.jpg", open(file, "rb"), "image/jpeg")}, timeout=60)
        else:
            r = requests.post(URL, json=data, timeout=30)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 1)) + 0.2)
            continue
        r.raise_for_status()
        time.sleep(0.7)
        return
    raise RuntimeError("Discord : trop de requêtes")


# un paquet à la fois : deux vidéos envoyées en même temps entremêlaient leurs messages sur Discord
# (titre de l'une, description et tags de l'autre). Le verrou tient jusqu'à la fin du script.
_lock = open(os.path.join(WORK, "discord.lock"), "w")
fcntl.flock(_lock, fcntl.LOCK_EX)

title = meta["titles"][0]
if "--link-only" in sys.argv:
    post(f"🎬 **{BRAND} — {title}**\n🔗 **Vidéo** : {link}")
    sys.exit()
post(f"🎬 **{BRAND} — {title}** ✅ vérifiée, à poster\n🔗 **Vidéo** : {link}\n🖼️ Miniature :", thumb)
post(f"📌 **Titre**\n{title}")
desc = meta["description"].strip()
if meta.get("chapters"):
    desc += "\n\nChapters\n" + "\n".join(meta["chapters"])
post(f"📝 **Description**\n{desc}")
post(f"🏷️ **Tags**\n{', '.join(meta['tags'])}")
post(f"💬 **Commentaire épinglé**\n{meta['pinned_comment']}")
print("Discord OK")
