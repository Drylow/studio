"""Immediate sports releases must keep every existing publication control."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio.web import create_app
from studio.auto_publication import tick
from studio.publishing import publish
from studio.store import ROOT, now
from studio.imports import digest


class AutoPublicationTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "work/studio").mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / "work/studio")
        self.app = create_app(dict(TESTING=True, PREVIEW=True, HOSTED=False, WORKER_ENABLED=False,
                                   IMPORT_PRODUCTIONS=False, SECRET_KEY="publication-fixture",
                                   DB_PATH=Path(self.tmp.name) / "release.db"))
        self.store = self.app.extensions["studio_store"]
        self.app.config["PREVIEW"] = False
        self.app.config["DEVELOPMENT_MAINTENANCE_PATH"] = str(Path(self.tmp.name) / "maintenance.json")
        self.channels = [c for c in self.store.channels() if c["key"] in {"mma_en", "football_en"}]
        self.path = Path(self.tmp.name) / "video.mp4"
        self.path.write_bytes(b"prechecked publication fixture")
        self.thumb = Path(self.tmp.name) / "thumbnail.png"
        self.thumb.write_bytes(b"prechecked thumbnail fixture")
        with self.store.db() as c:
            c.execute("UPDATE studio_settings SET paused=0")
            for ch in self.channels:
                c.execute("UPDATE studio_channels SET enabled=1,paused=0,publication_mode='news' WHERE project_id=?", (ch["id"],))
                c.execute("UPDATE delamain_projects SET autonomy='auto',yt_refresh_token='fixture',yt_channel_id='UCfixturePublication' WHERE id=?", (ch["id"],))

    def tearDown(self):
        self.tmp.cleanup()

    def video(self, ch=None, **override):
        data = dict(channel_id=(ch or self.channels[0])["id"], title="A checked sports story", status="ready",
                    video_path=str(self.path.relative_to(ROOT)), thumb_path=str(self.thumb.relative_to(ROOT)),
                    quality_status="verified", rights_status="verified", render_digest=digest(self.path), event_at=now())
        data.update(override)
        return self.store.add_video(data)

    def test_two_news_channels_publish_without_any_hour_and_tick_does_not_duplicate_jobs(self):
        ids = [self.video(ch) for ch in self.channels]
        with patch("studio.publishing.publish") as remote:
            first = tick(self.store)
            second = tick(self.store)
            remote.assert_not_called()  # The durable worker executes the queue separately.
        self.assertEqual(len(first), 2)
        self.assertEqual(first, second)
        jobs = self.store.rows("SELECT kind,video_id FROM studio_jobs")
        self.assertEqual({row["video_id"] for row in jobs}, set(ids))
        self.assertTrue(all(row["kind"] == "publish" for row in jobs))

    def test_pause_disabled_connection_and_preview_cannot_release(self):
        self.video()
        scenarios = ["UPDATE studio_settings SET paused=1", "UPDATE studio_channels SET paused=1",
                     "UPDATE studio_channels SET enabled=0", "UPDATE delamain_projects SET yt_refresh_token=''",]
        for sql in scenarios:
            with self.subTest(sql=sql):
                with self.store.db() as c:
                    c.execute(sql)
                self.assertEqual(tick(self.store), [])
                with self.store.db() as c:
                    c.execute("UPDATE studio_settings SET paused=0")
                    c.execute("UPDATE studio_channels SET paused=0,enabled=1")
                    c.execute("UPDATE delamain_projects SET yt_refresh_token='fixture'")
        self.app.config["PREVIEW"] = True
        self.assertEqual(tick(self.store), [])
        self.app.config["PREVIEW"] = False
        Path(self.app.config["DEVELOPMENT_MAINTENANCE_PATH"]).write_text("{}")
        self.assertEqual(tick(self.store), [])

    def test_controls_stale_news_failed_and_published_work_never_release(self):
        for override in [dict(quality_status="technical"), dict(rights_status="unknown"), dict(thumb_path=""),
                         dict(video_path=""), dict(render_digest=""), dict(status="blocked"), dict(status="review"),
                         dict(status="published"), dict(status="reported"),
                         dict(event_at=(datetime.now(timezone.utc)-timedelta(days=10)).isoformat())]:
            self.video(**override)
        self.assertEqual(tick(self.store), [])

    def test_explicit_future_reservation_survives_immediate_news_mode(self):
        self.video(post_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
        self.assertEqual(tick(self.store), [])
        self.video(status="scheduled", post_at=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat())
        self.assertEqual(len(tick(self.store)), 1)

    def test_manual_and_calendar_channels_keep_their_reservations(self):
        with self.store.db() as c:
            c.execute("UPDATE delamain_projects SET autonomy='manual' WHERE id=?", (self.channels[0]["id"],))
            c.execute("UPDATE studio_channels SET publication_mode='scheduled' WHERE project_id=?", (self.channels[1]["id"],))
        self.video(self.channels[0], approved_digest=digest(self.path))
        self.video(self.channels[1])
        self.assertEqual(tick(self.store), [])
        self.video(self.channels[0], approved_digest=digest(self.path), status="scheduled", post_at=now())
        self.assertEqual(len(tick(self.store)), 1)

    def test_one_busy_video_does_not_get_an_additional_publication_job(self):
        identity = self.video()
        job = self.store.enqueue("verify", identity)
        tick(self.store)
        rows = self.store.rows("SELECT * FROM studio_jobs")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], job)
        self.assertEqual(rows[0]["kind"], "verify")

    def test_expired_access_or_wrong_google_identity_blocks_before_upload(self):
        identity = self.video()
        ch = self.store.channel(self.channels[0]["id"])
        with patch("studio.review.recheck_rights"), patch("routes.youtube._opener") as opener:
            for access, actual in [("", ""), ("fixture-access", "UCdifferentChannel"), ("fixture-access", "")]:
                with self.subTest(actual=actual), patch("routes.youtube._access_token", return_value=access), patch("routes.youtube._fetch_channel", return_value=("Fixture", actual)):
                    with self.assertRaises(ValueError):
                        publish(self.store, self.store.video(identity), ch, object())
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
