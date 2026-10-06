"""Immediate sports releases must keep every existing publication control."""

from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

from studio.web import create_app
from studio.auto_publication import tick
from studio.publishing import publish
from studio.store import ROOT, now
from studio.imports import digest


class AutoPublicationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"YOUTUBE_PUBLICATION_FLOW": ""})
        self.env.start()
        (ROOT / "work/studio").mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / "work/studio")
        self.app = create_app(
            dict(
                TESTING=True,
                PREVIEW=True,
                HOSTED=False,
                WORKER_ENABLED=False,
                IMPORT_PRODUCTIONS=False,
                SECRET_KEY="publication-fixture",
                DB_PATH=Path(self.tmp.name) / "release.db",
            )
        )
        self.store = self.app.extensions["studio_store"]
        self.app.config["PREVIEW"] = False
        self.app.config["DEVELOPMENT_MAINTENANCE_PATH"] = str(
            Path(self.tmp.name) / "maintenance.json"
        )
        self.channels = [
            c for c in self.store.channels() if c["key"] in {"mma_en", "football_en"}
        ]
        self.path = Path(self.tmp.name) / "video.mp4"
        self.path.write_bytes(b"prechecked publication fixture")
        self.thumb = Path(self.tmp.name) / "thumbnail.png"
        self.thumb.write_bytes(b"prechecked thumbnail fixture")
        with self.store.db() as c:
            c.execute("UPDATE studio_settings SET paused=0")
            for ch in self.channels:
                c.execute(
                    "UPDATE studio_channels SET enabled=1,paused=0,publication_mode='news' WHERE project_id=?",
                    (ch["id"],),
                )
                c.execute(
                    "UPDATE delamain_projects SET autonomy='auto',yt_refresh_token='fixture',yt_channel_id='UCfixturePublication' WHERE id=?",
                    (ch["id"],),
                )

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def video(self, ch=None, **override):
        data = dict(
            channel_id=(ch or self.channels[0])["id"],
            title="A checked sports story",
            status="ready",
            video_path=str(self.path.relative_to(ROOT)),
            thumb_path=str(self.thumb.relative_to(ROOT)),
            quality_status="verified",
            rights_status="verified",
            render_digest=digest(self.path),
            event_at=now(),
        )
        data.update(override)
        return self.store.add_video(data)

    def test_two_news_channels_publish_without_any_hour_and_tick_does_not_duplicate_jobs(
        self,
    ):
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
        scenarios = [
            "UPDATE studio_settings SET paused=1",
            "UPDATE studio_channels SET paused=1",
            "UPDATE studio_channels SET enabled=0",
            "UPDATE delamain_projects SET yt_refresh_token=''",
        ]
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
        for override in [
            dict(quality_status="technical"),
            dict(rights_status="unknown"),
            dict(thumb_path=""),
            dict(video_path=""),
            dict(render_digest=""),
            dict(status="blocked"),
            dict(status="review"),
            dict(status="published"),
            dict(status="reported"),
            dict(
                event_at=(datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
            ),
        ]:
            self.video(**override)
        self.assertEqual(tick(self.store), [])

    def test_explicit_future_reservation_survives_immediate_news_mode(self):
        self.video(
            post_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        )
        self.assertEqual(tick(self.store), [])
        self.video(
            status="scheduled",
            post_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        )
        self.assertEqual(len(tick(self.store)), 1)

    def test_manual_and_calendar_channels_keep_their_reservations(self):
        with self.store.db() as c:
            c.execute(
                "UPDATE delamain_projects SET autonomy='manual' WHERE id=?",
                (self.channels[0]["id"],),
            )
            c.execute(
                "UPDATE studio_channels SET publication_mode='scheduled' WHERE project_id=?",
                (self.channels[1]["id"],),
            )
        self.video(self.channels[0], approved_digest=digest(self.path))
        self.video(self.channels[1])
        self.assertEqual(tick(self.store), [])
        self.video(
            self.channels[0],
            approved_digest=digest(self.path),
            status="scheduled",
            post_at=now(),
        )
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
        with patch("studio.review.recheck_rights"), patch(
            "routes.youtube._opener"
        ) as opener:
            for access, actual in [
                ("", ""),
                ("fixture-access", "UCdifferentChannel"),
                ("fixture-access", ""),
            ]:
                with self.subTest(actual=actual), patch(
                    "routes.youtube._access_token", return_value=access
                ), patch(
                    "routes.youtube._fetch_channel", return_value=("Fixture", actual)
                ):
                    with self.assertRaises(ValueError):
                        publish(self.store, self.store.video(identity), ch, object())
            opener.assert_not_called()

    def legacy_upload(self, identity, opener, job=None):
        channel = self.store.channel(self.store.video(identity)["channel_id"])
        with patch.dict(os.environ, {"YOUTUBE_PUBLICATION_FLOW": "legacy-news"}), patch(
            "routes.youtube._access_token", return_value="fixture-access"
        ), patch(
            "routes.youtube._fetch_channel",
            return_value=(channel["name"], channel["yt_channel_id"]),
        ), patch(
            "routes.youtube._opener", return_value=opener
        ), patch(
            "studio.review.recheck_rights"
        ):
            return publish(
                self.store, self.store.video(identity), channel, job or Mock()
            )

    class Opener:
        def __init__(
            self,
            visibility="public",
            channel_id="UCfixturePublication",
            lose_response=False,
            fail_thumbnail=False,
        ):
            self.calls = []
            self.visibility = visibility
            self.channel_id = channel_id
            self.lose_response = lose_response
            self.fail_thumbnail = fail_thumbnail

        def open(self, request, timeout=None):
            self.calls.append(request)
            response = io.BytesIO()
            response.headers = {}
            if "uploadType=resumable" in request.full_url:
                response.headers["Location"] = (
                    "https://www.googleapis.com/upload/fixture-session"
                )
                payload = {}
            elif request.full_url.endswith("fixture-session"):
                if self.lose_response:
                    self.lose_response = False
                    raise urllib.error.URLError("lost response")
                payload = {"id": "fixtureYTId"}
            elif "thumbnails/set" in request.full_url:
                if self.fail_thumbnail:
                    raise urllib.error.URLError("thumbnail refused")
                payload = {
                    "items": [{"default": {"url": "https://i.ytimg.com/fixture"}}]
                }
            else:
                payload = {
                    "items": [
                        {
                            "id": "fixtureYTId",
                            "snippet": {"channelId": self.channel_id},
                            "status": {"privacyStatus": self.visibility},
                        }
                    ]
                }
            response.write(json.dumps(payload).encode())
            response.seek(0)
            return response

    def test_historical_news_sends_metadata_and_thumbnail_without_visibility_permission(
        self,
    ):
        for channel in self.channels:
            with self.subTest(channel=channel["key"]):
                identity = self.video(
                    channel, description="Source links", tags=["news", "sport"]
                )
                opener = self.Opener()
                result = self.legacy_upload(identity, opener)
                self.assertTrue(result["published"])
                self.assertEqual(self.store.video(identity)["status"], "published")
                meta = json.loads(
                    next(
                        r.data
                        for r in opener.calls
                        if "uploadType=resumable" in r.full_url
                    )
                )
                self.assertEqual(meta["status"]["privacyStatus"], "public")
                self.assertEqual(meta["snippet"]["description"], "Source links")
                self.assertEqual(meta["snippet"]["tags"], ["news", "sport"])
                self.assertEqual(
                    next(
                        r.data for r in opener.calls if "thumbnails/set" in r.full_url
                    ),
                    self.thumb.read_bytes(),
                )
                self.assertFalse(
                    any(
                        r.get_method() == "PUT" and "/youtube/v3/videos" in r.full_url
                        for r in opener.calls
                    )
                )

    def test_direct_upload_does_not_claim_forced_private_or_wrong_destination_is_published(
        self,
    ):
        for visibility, channel_id in [
            ("private", "UCfixturePublication"),
            ("public", "UCotherChannel"),
        ]:
            with self.subTest(visibility=visibility, channel_id=channel_id):
                identity = self.video()
                opener = self.Opener(visibility=visibility, channel_id=channel_id)
                with self.assertRaises(ValueError):
                    self.legacy_upload(identity, opener)
                self.assertNotEqual(self.store.video(identity)["status"], "published")
                self.assertEqual(
                    self.store.video(identity)["youtube_id"], "fixtureYTId"
                )
                with self.assertRaises(ValueError):
                    self.legacy_upload(identity, opener)
                self.assertEqual(
                    sum("uploadType=resumable" in r.full_url for r in opener.calls), 1
                )

    def test_direct_upload_recovers_lost_response_and_thumbnail_failure_without_duplication(
        self,
    ):
        for lost, thumbnail in [(True, False), (False, True)]:
            with self.subTest(lost=lost, thumbnail=thumbnail):
                identity = self.video()
                opener = self.Opener(lose_response=lost, fail_thumbnail=thumbnail)
                with self.assertRaises((ValueError, urllib.error.URLError)):
                    self.legacy_upload(identity, opener)
                self.assertNotEqual(self.store.video(identity)["status"], "published")
                opener.fail_thumbnail = False
                self.assertTrue(self.legacy_upload(identity, opener)["published"])
                self.assertEqual(
                    sum("uploadType=resumable" in r.full_url for r in opener.calls), 1
                )

    def test_direct_upload_rechecks_pause_rights_and_modified_bytes_before_completion(
        self,
    ):
        for change in ["pause", "rights", "file"]:
            with self.subTest(change=change):
                identity = self.video()
                opener = self.Opener()

                def update(*args):
                    if change == "pause":
                        with self.store.db() as c:
                            c.execute("UPDATE studio_settings SET paused=1")
                    elif change == "rights":
                        self.store.update(
                            "studio_videos", identity, {"rights_status": "unknown"}
                        )
                    else:
                        self.path.write_bytes(b"changed after the initial checks")

                with self.assertRaises(ValueError):
                    self.legacy_upload(identity, opener, Mock(update=update))
                self.assertFalse(
                    any(r.full_url.endswith("fixture-session") for r in opener.calls)
                )
                with self.store.db() as c:
                    c.execute("UPDATE studio_settings SET paused=0")
                self.path.write_bytes(b"prechecked publication fixture")

    def test_direct_upload_rejects_oversized_thumbnail_and_future_slot_before_remote_call(
        self,
    ):
        identity = self.video(
            post_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        )
        opener = self.Opener()
        with self.assertRaises(ValueError):
            self.legacy_upload(identity, opener)
        self.thumb.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
        identity = self.video()
        with self.assertRaises(ValueError):
            self.legacy_upload(identity, opener)
        self.assertEqual(opener.calls, [])

    def test_resume_keeps_original_public_mode_when_configuration_changes(self):
        identity = self.video()
        opener = self.Opener(lose_response=True)
        with self.assertRaises(urllib.error.URLError):
            self.legacy_upload(identity, opener)
        channel = self.store.channel(self.store.video(identity)["channel_id"])
        with patch(
            "routes.youtube._access_token", return_value="fixture-access"
        ), patch(
            "routes.youtube._fetch_channel",
            return_value=(channel["name"], channel["yt_channel_id"]),
        ), patch(
            "routes.youtube._opener", return_value=opener
        ), patch(
            "studio.review.recheck_rights"
        ):
            self.assertTrue(
                publish(self.store, self.store.video(identity), channel, Mock())[
                    "published"
                ]
            )
        self.assertFalse(
            any(
                r.get_method() == "PUT" and "/youtube/v3/videos" in r.full_url
                for r in opener.calls
            )
        )


if __name__ == "__main__":
    unittest.main()
