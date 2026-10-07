"""Persistent one-at-a-time runner, with renewable leases independent of browser polling."""

from datetime import datetime, timedelta, timezone
import json
import os
import threading
import time
from studio.store import ROOT, now, uid

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
    version = ROOT / "work/studio/runtime-revision"
    started_version = version.read_text() if version.exists() else ""
    if not once:
        from studio.public_statistics import start_monitor

        start_monitor(store)
    while True:
        if not once and version.exists() and version.read_text() != started_version:
            # The cron supervisor starts a fresh process with the newly deployed code.
            return
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
        from studio.newsroom import tick

        tick(store)
        if not row:
            from studio.channel_stats import tick as stats_tick

            stats_tick(store)
        from studio.auto_publication import tick as publication_tick

        publication_tick(store)
        try:
            from studio.youtube_renewal import tick as renewal_tick

            renewal_tick(store)
        except Exception as e:
            store.log("Studio", "error", "Rappel de connexion : " + str(e)[:300])
        time.sleep(3)


def worker_application(config=None):
    """A standalone worker also needs the guarded API used by Delamain actions."""
    from studio.web import create_app

    return create_app(dict(config or {}, WORKER_ENABLED=False))


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    app = worker_application()
    if app.config["PREVIEW"]:
        raise SystemExit("L’aperçu ne lance pas le moteur de production.")
    store = app.extensions["studio_store"]
    run(store)
