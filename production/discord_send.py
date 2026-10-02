"""Envoie le paquet de publication d'une vidéo sur Discord : lien vidéo + miniature, titre, description
(+ chapitres), tags, commentaire épinglé. Marque = nom du studio de la chaîne (Oddly Specific Lives…).

  python production/discord_send.py <folder> <lien_gofile> [--link-only] [--dry-run]

Le dossier doit avoir meta.json (écrit au rendu) et thumb_choice.txt (chemin de la miniature choisie).
Miniature pas encore choisie : thumb_options.txt (une ligne par variante : « chemin<TAB>MOT ») joint toutes les
variantes au même message (10 max), la première en couverture, pour que l'utilisateur choisisse en programmant.
Webhook : DISCORD_WEBHOOK_URL dans .env (jamais dans git)."""
import fcntl
import json
import os
import re
import sys
import time

import requests

from common import WORK, folder, webhook
from services import pov_engine as E

D = folder(sys.argv[1])
link = sys.argv[2] if len(sys.argv) > 2 else ""
URL = webhook() + "?wait=true"
info = json.load(open(os.path.join(D, "video.json"))) if os.path.isfile(os.path.join(D, "video.json")) else {}
BRAND = info.get("brand") or ((E.TEMPLATES.get(info.get("template") or "", {}).get("studio") or {}).get("brand")) or "Video"
meta = json.load(open(os.path.join(D, "meta.json")))
OPTIONS = os.path.join(D, "thumb_options.txt")
if os.path.isfile(OPTIONS):  # [(chemin, nom du fichier joint)] : toutes les variantes, numérotées
    rows = [ln.split("\t") for ln in open(OPTIONS).read().splitlines() if ln.strip()][:10]
    thumbs = [(r[0], f"miniature_{k}_{re.sub(r'[^A-Za-z0-9]+', '_', r[1] if len(r) > 1 else str(k)).strip('_')}.jpg")
              for k, r in enumerate(rows, 1)]
else:
    thumbs = [(open(os.path.join(D, "thumb_choice.txt")).read().strip(), "miniature.jpg")]


COLOR = 0xE63946
EMBED_LIMIT = 5900  # Discord : 6 000 caractères au total pour les embeds d'un message


def post(content, embeds=(), files=()):
    """Un seul message (contenu + embeds + miniatures jointes) : un paquet ne peut plus être coupé par un autre."""
    data = {"content": content, "embeds": list(embeds), "allowed_mentions": {"parse": []}}
    for _ in range(4):
        if DRY:
            print(json.dumps(data, ensure_ascii=False, indent=1))
            return
        if files:
            r = requests.post(URL, data={"payload_json": json.dumps(data)}, timeout=120,
                              files={f"files[{k}]": (name, open(path, "rb"), "image/jpeg")
                                     for k, (path, name) in enumerate(files)})
        else:
            r = requests.post(URL, json=data, timeout=30)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 1)) + 0.2)
            continue
        r.raise_for_status()
        return
    raise RuntimeError("Discord : trop de requêtes")


def embed(title, text):
    return {"title": title, "description": text[:4096], "color": COLOR}


def size(e):
    return len(e.get("title") or "") + len(e.get("description") or "") + sum(
        len(f["name"]) + len(f["value"]) for f in e.get("fields") or []) + len((e.get("footer") or {}).get("text") or "")


DRY = "--dry-run" in sys.argv
# un paquet à la fois, en plus du message unique (deux scripts lancés ensemble ne se croisent jamais)
_lock = open(os.path.join(WORK, "discord.lock"), "w")
fcntl.flock(_lock, fcntl.LOCK_EX)

title = meta["titles"][0]
head = f"🎬 **{BRAND} — {title}** ✅ vérifiée, à poster\n🔗 **Vidéo** : <{link}>"  # <…> : pas d'aperçu du lien
if "--link-only" in sys.argv:
    post(head.replace(" ✅ vérifiée, à poster", ""))
    sys.exit()
desc = meta["description"].strip()
if meta.get("chapters"):
    desc += "\n\nChapters\n" + "\n".join(meta["chapters"])
if len(thumbs) > 1:
    head += f"\n🖼️ **{len(thumbs)} miniatures au choix** (jointes, numérotées)"
cover = {"title": f"{BRAND} — {title}", "url": link or None, "color": COLOR, "image": {"url": f"attachment://{thumbs[0][1]}"},
         "fields": [{"name": "📌 Titre", "value": title[:1024]}]}
if len(meta["titles"]) > 1:
    cover["fields"].append({"name": "Autres titres", "value": "\n".join(meta["titles"][1:4])[:1024]})
blocks = [cover, embed("📝 Description", desc), embed("🏷️ Tags", ", ".join(meta["tags"])),
          embed("💬 Commentaire épinglé", meta.get("pinned_comment") or "")]
blocks = [b for b in blocks if b.get("description") or b.get("fields")]
if sum(size(b) for b in blocks) <= EMBED_LIMIT:
    post(head, blocks, thumbs)
else:  # description très longue : deux messages à la suite, toujours sous le verrou
    post(head, blocks[:2], thumbs)
    post(f"🎬 **{title}** (suite)", blocks[2:])
print("Discord OK")
