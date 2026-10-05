"""Persistent one-at-a-time runner, with renewable leases independent of browser polling."""

from datetime import datetime, timedelta, timezone
import json
import os
import threading
import time
from studio.store import Store, ROOT, now, uid

_threads = {}


def start(store):
    key = str(store.path)
    if key not in _threads or not _threads[key].is_alive():
        t = threading.Thread(
            target=run, args=(store,), daemon=True, name="studio-worker"
        )
        _threads[key] = t
        t.start()


def run(store, once=False):
    owner = uid()
    while True:
        with store.db() as c:
            c.execute(
                "UPDATE studio_worker SET heartbeat=?,message=? WHERE id=1",
                (now(), "Disponible"),
            )
        row = store.claim(owner)
        if row:
            stop = threading.Event()

            def heartbeat():
                while not stop.wait(10):
                    lease = (
                        datetime.now(timezone.utc) + timedelta(minutes=3)
                    ).isoformat()
                    with store.db() as c:
                        c.execute(
                            "UPDATE studio_jobs SET lease_until=?,updated_at=? WHERE id=? AND owner=? AND status='running'",
                            (lease, now(), row["id"], owner),
                        )
                        c.execute(
                            "UPDATE studio_worker SET heartbeat=?,message=? WHERE id=1",
                            (now(), "Travail en cours"),
                        )

            pulse = threading.Thread(target=heartbeat, daemon=True)
            pulse.start()
            try:
                from studio.jobs import execute

                result = execute(store, row)
                with store.db() as c:
                    c.execute(
                        "UPDATE studio_jobs SET status='done',progress=1,result=?,message='Terminé',updated_at=? WHERE id=? AND owner=?",
                        (
                            json.dumps(result or {}, ensure_ascii=False),
                            now(),
                            row["id"],
                            owner,
                        ),
                    )
            except Exception as e:
                from studio.jobs import Cancelled

                cancelled = isinstance(e, Cancelled) or bool(
                    store.one(
                        "SELECT cancel_requested FROM studio_jobs WHERE id=?",
                        (row["id"],),
                    )["cancel_requested"]
                )
                # Never include provider secrets or raw responses in user-visible errors.
                text = str(e)[:800]
                for value in (
                    os.getenv(k)
                    for k in [
                        "AI_API_KEY",
                        "ALGROW_API_KEY",
                        "AI33_API_KEY",
                        "NEWS_WORKER_TOKEN",
                    ]
                ):
                    if value:
                        text = text.replace(value, "[confidentiel]")
                with store.db() as c:
                    c.execute(
                        "UPDATE studio_jobs SET status=?,error=?,message=?,updated_at=? WHERE id=? AND owner=?",
                        (
                            "cancelled" if cancelled else "failed",
                            text,
                            "Annulé" if cancelled else "À reprendre",
                            now(),
                            row["id"],
                            owner,
                        ),
                    )
                    if row["video_id"]:
                        c.execute(
                            "UPDATE studio_videos SET status='blocked',error=?,revision=revision+1,updated_at=? WHERE id=? AND status NOT IN ('published','reported')",
                            (text, now(), row["video_id"]),
                        )
                store.log("Studio", "error", text)
            finally:
                stop.set()
                pulse.join(timeout=1)
        if once:
            return
        # Publication scheduling uses server time and the same release gate as manual publication.
        if not store.settings()["paused"]:
            from studio.domain import blockers

            for v in store.videos():
                ch = store.channel(v["channel_id"])
                if (
                    v["status"] == "scheduled"
                    and v["post_at"]
                    and v["post_at"] <= now()
                ):
                    if not blockers(v, ch, store.settings(), automatic=True):
                        store.enqueue("publish", v["id"], {"actor": "Delamain"})
        time.sleep(3)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    store = Store(os.getenv("DB_PATH") or ROOT / "drylow_studio.db")
    store.migrate()
    run(store)
