"""Deliver the requested channel kit to its dedicated Discord webhook once."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
import requests


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ENV_NAME = "DISCORD_WEBHOOK_QUIET_LITTLE_WORLDS"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true", help="Post after reviewing dry-run output")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    avatar = HERE / "branding/avatar-fern-moon.png"
    bio_file = HERE / "bio-en.txt"
    manifest = json.loads((HERE / "branding-proposals.json").read_text())
    assert manifest["brand_name_user_approved"]
    assert manifest["avatar_delivery_user_authorized"]
    expected = next(a for a in manifest["assets"] if a["proposal"] == "avatar")
    assert expected["root_full_image_viewed"] and sha256(avatar) == expected["sha256"]
    assert avatar.stat().st_size < 10_000_000
    bio = bio_file.read_text().strip()
    assert 0 < len(bio) <= 1000
    names = ["Quiet_Little_Worlds_Avatar.png", "Description_chaine.txt", "Nom_et_handle.txt"]
    payload = {
        "username": "Quiet Little Worlds",
        "content": "Kit de chaîne — Quiet Little Worlds",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": "Quiet Little Worlds",
            "description": bio,
            "color": 4489042,
            "fields": [{"name": "Handle proposé", "value": "@QuietLittleWorlds — disponibilité à confirmer dans YouTube", "inline": False}],
            "image": {"url": "attachment://" + names[0]},
        }],
        "attachments": [{"id": i, "filename": name} for i, name in enumerate(names)],
    }
    label = "Name: Quiet Little Worlds\nProposed handle: @QuietLittleWorlds\nHandle availability: not confirmed.\n"
    fingerprint = hashlib.sha256((json.dumps(payload, sort_keys=True) + sha256(avatar)).encode()).hexdigest()
    out = ROOT / "output/nature-sleep/branding-delivery"
    out.mkdir(parents=True, exist_ok=True)
    (out / "payload-review.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    if not args.send:
        print(json.dumps({"payload": payload, "avatar_sha256": sha256(avatar), "fingerprint": fingerprint}, ensure_ascii=False, indent=2))
        return
    webhook = os.environ.get(ENV_NAME, "")
    if not webhook.startswith("https://discord.com/api/webhooks/"):
        raise SystemExit("Webhook dédié absent ou invalide ; aucun fallback autorisé.")
    receipt_file = out / "discord-receipt.json"
    pending = out / "discord-pending.json"
    with (out / "discord.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if receipt_file.exists():
            receipt = json.loads(receipt_file.read_text())
            same_confirmed_content = (
                receipt.get("user_confirmed_name_bio_avatar")
                and receipt.get("avatar_sha256") == sha256(avatar)
                and receipt.get("bio_sha256") == sha256(bio_file)
                and receipt.get("name") == "Quiet Little Worlds"
            )
            if receipt["fingerprint"] == fingerprint or same_confirmed_content:
                print("Kit déjà confirmé sur Discord ; aucun nouvel envoi.")
                return
            raise SystemExit("Un autre kit est déjà livré ; ne pas remplacer sans décision explicite.")
        if pending.exists():
            raise SystemExit("Envoi précédent incertain : vérifier son état avant toute nouvelle tentative.")
        try:
            preflight = requests.get(webhook, timeout=30)
            preflight.raise_for_status()
            target = preflight.json()
            assert target["id"] == webhook.rstrip("/").split("/")[-2]
        except Exception as exc:
            raise SystemExit("Préflight Discord refusé : " + type(exc).__name__) from None
        pending.write_text(json.dumps({"fingerprint": fingerprint, "started_utc": datetime.now(timezone.utc).isoformat()}))
        try:
            with ExitStack() as stack:
                files = [
                    ("files[0]", (names[0], stack.enter_context(avatar.open("rb")), "image/png")),
                    ("files[1]", (names[1], (bio + "\n").encode(), "text/plain; charset=utf-8")),
                    ("files[2]", (names[2], label.encode(), "text/plain; charset=utf-8")),
                ]
                response = requests.post(webhook, params={"wait": "true"}, data={"payload_json": json.dumps(payload, ensure_ascii=False)}, files=files, timeout=90)
            response.raise_for_status()
            message = response.json()
            # Preserve the actual response before validating its presentation;
            # a successful POST must never become an untraceable uncertain send.
            (out / "discord-response-private.json").write_text(json.dumps(message, ensure_ascii=False, indent=2) + "\n")
            actual = [a["filename"] for a in message.get("attachments", [])]
            assert str(message["id"]).isdigit() and sorted(actual) == sorted(names)
        except Exception as exc:
            raise SystemExit("Envoi non confirmé : " + type(exc).__name__ + ". Marqueur pending conservé ; ne pas réessayer à l’aveugle.") from None
        receipt = {
            "message_id": str(message["id"]),
            "channel_id": str(message["channel_id"]),
            "fingerprint": fingerprint,
            "attachments": actual,
            "avatar_sha256": sha256(avatar),
            "bio_sha256": sha256(bio_file),
            "confirmed_utc": datetime.now(timezone.utc).isoformat(),
        }
        receipt_file.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        pending.unlink()
        print("Discord : nom, description et avatar confirmés, message " + receipt["message_id"] + ".")


if __name__ == "__main__":
    main()
