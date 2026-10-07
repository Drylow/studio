"""Trial of the Cage/Pitch autopilot on the hosted server, without publishing.

    python production/autonews_trial.py mma_en          # best fresh story
    python production/autonews_trial.py mma_en <item>   # a given radar item

Adds the checked feeds, scans them, scores the fresh headlines and produces one
video in trial mode (status `review`, nothing uploaded). Progress goes to stdout.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    os.environ["NEWS_AUTO_DRY"] = "1"
    from studio.worker import worker_application
    from studio import autonews
    from studio.newsroom import DEFAULTS, scan
    from studio.store import uid

    key = sys.argv[1] if len(sys.argv) > 1 else "mma_en"
    store = worker_application().extensions["studio_store"]
    autonews.initialize(store)
    ch = next(c for c in store.channels() if (c["template_key"] or c["key"]) == key)
    with store.db() as c:
        for name, url in DEFAULTS.get(key, []):
            c.execute(
                "INSERT OR IGNORE INTO studio_news_feeds(id,channel_id,name,url) VALUES(?,?,?,?)",
                (uid(), ch["id"], name, url),
            )
    # Explicit trial: the studio pause stops automatic work, not this manual run.
    settings, channel = store.settings, store.channel
    store.settings = lambda: dict(settings(), paused=0)
    store.channel = lambda cid: dict(channel(cid), paused=0) if channel(cid) else None
    try:
        print("Radar :", scan(store, ch["id"]), flush=True)
    finally:
        store.settings, store.channel = settings, channel
    at = datetime.now(timezone.utc)
    if len(sys.argv) > 2:
        item = store.one("SELECT * FROM studio_news_items WHERE id=?", (sys.argv[2],))
    else:
        items = store.rows(
            "SELECT * FROM studio_news_items WHERE channel_id=? AND status='new' ORDER BY published DESC LIMIT 30",
            (ch["id"],),
        )
        ranked = autonews.score(store, ch, items, at, autonews.Tools())
        for row in ranked[:8]:
            print(f"  {row['score']:>2}/10  {row['title'][:90]}  — {row['why'][:80]}", flush=True)
        item = ranked[0] if ranked else None
    if not item:
        raise SystemExit("Aucune info fraîche à traiter.")
    print("Sujet :", item["title"], flush=True)

    class Job:
        def update(self, progress=None, message=None):
            if message:
                stamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{stamp}] {message}", flush=True)

    result = autonews.produce(store, {"channel_id": ch["id"], "item_id": item["id"]}, Job())
    v = store.video(result["video_id"])
    print("Vidéo :", v["id"], v["status"], v["title"], flush=True)
    print("Dossier :", v["engine_ref"].get("job"), flush=True)


if __name__ == "__main__":
    main()
