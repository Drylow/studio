"""Warn before Google ends a channel's access.

While the Google app is in Testing, Google ends every YouTube authorization a few
days after consent (7 days today). YOUTUBE_TOKEN_DAYS states that lifetime; the
studio then warns on the site and once on the channel's Discord, a day ahead.
"""

from datetime import datetime, timedelta, timezone
import json
import os
import time
import urllib.request

from studio.store import now

NOTICE = timedelta(days=1)
_last = {}


def lifetime():
    try:
        days = float(os.getenv("YOUTUBE_TOKEN_DAYS", "") or 0)
    except ValueError:
        return None
    return timedelta(days=days) if days > 0 else None


def expiry(channel):
    life = lifetime()
    if not life or not channel.get("connected") or not channel.get("yt_connected_at"):
        return None
    try:
        start = datetime.fromisoformat(channel["yt_connected_at"])
    except ValueError:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return start + life


def local(moment):
    try:
        from zoneinfo import ZoneInfo

        moment = moment.astimezone(ZoneInfo("Europe/Paris"))
    except Exception:
        pass
    return moment.strftime("le %d/%m à %H h %M")


HOW = "Chaînes → Connecter YouTube → Autre méthode : API Google → Reconnecter avec Google."


def message(channel, ends, at):
    if at >= ends:
        return f"La connexion YouTube a expiré {local(ends)} : aucune publication possible avant de reconnecter."
    return f"La connexion YouTube expire {local(ends)}. Reconnecte avant pour ne rater aucune publication."


def tick(store, at=None, send=None):
    """At most every five minutes; one Discord reminder per authorization."""
    at = at or datetime.now(timezone.utc)
    key = str(store.path)
    if send is None and time.monotonic() - _last.get(key, -1e9) < 300:
        return
    _last[key] = time.monotonic()
    if not lifetime():
        return
    with store.db() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS studio_youtube_reminders(channel_id INTEGER NOT NULL, connected_at TEXT NOT NULL, sent_at TEXT NOT NULL, PRIMARY KEY(channel_id, connected_at))"
        )
    for channel in store.channels():
        ends = expiry(channel)
        if not ends or at < ends - NOTICE:
            continue
        url = os.getenv("DISCORD_WEBHOOK_" + channel["key"].upper()) or os.getenv(
            "DISCORD_WEBHOOK_URL", ""
        )
        if not url:
            continue
        with store.db() as c:
            # Claim before sending: a crash may lose one reminder, never repeat it.
            if not c.execute(
                "INSERT OR IGNORE INTO studio_youtube_reminders VALUES(?,?,?)",
                (channel["id"], channel["yt_connected_at"], now()),
            ).rowcount:
                continue
        site = os.getenv("STUDIO_PUBLIC_URL", "https://edgerunners.fr").rstrip("/")
        text = (
            f"⏰ **{channel['name']}** : {message(channel, ends, at)}\n"
            f"Google coupe l’accès tous les 7 jours tant que l’application Google est en mode test.\n"
            f"{site}/channels → {channel['name']} → {HOW.split(' → ', 1)[1]}"
        )
        try:
            (send or post)(url, text)
        except (OSError, ValueError):
            store.log("Studio", "youtube", "Rappel Discord non envoyé : " + channel["name"])


def post(url, text):
    req = urllib.request.Request(
        url,
        data=json.dumps({"content": text, "allowed_mentions": {"parse": []}}).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "EdgerunnersStudio (https://edgerunners.fr, 1.0)",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20):
        pass
