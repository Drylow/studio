"""Observed counters, Google identity, bounded reads, cache races and private access."""
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error
from urllib.parse import parse_qs, urlsplit
from studio.web import create_app
from studio import channel_stats as stats


class ChannelStatsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "stats-fixture-client", "GOOGLE_CLIENT_SECRET": "stats-fixture-secret"})
        self.env.start()
        self.app = create_app(dict(TESTING=True, PREVIEW=True, WORKER_ENABLED=False,
                                   SECRET_KEY="stats-session", IMPORT_PRODUCTIONS=False,
                                   DB_PATH=Path(self.tmp.name) / "stats.db"))
        self.store = self.app.extensions["studio_store"]
        self.client = self.app.test_client()
        self.csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        self.app.config["PREVIEW"] = False
        self.channel = next(c for c in self.store.channels() if c["key"] == "mma_en")
        self.cid = self.channel["id"]
        self.yt = "UCStatsFixture"
        self.link(self.cid, self.yt)
        self.values = {"views": 2300, "subscribers": None, "videos": 3}

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def link(self, cid, identity):
        with self.store.db() as c:
            c.execute("UPDATE delamain_projects SET yt_refresh_token='stats-fixture-refresh',yt_channel_id=? WHERE id=?", (identity, cid))

    def snapshot(self, hours, views, cid=None, youtube_id=None):
        when = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self.store.db() as c:
            c.execute("INSERT INTO studio_channel_snapshots VALUES(?,?,?,?,?,?)", (cid or self.cid, youtube_id or self.yt, when, views, None, 3))
        return when

    def refresh(self, csrf=True):
        return self.client.post(f"/api/studio/channels/{self.cid}/stats/refresh", json={}, headers={"X-CSRF-Token": self.csrf} if csrf else {})

    def read(self, days=7):
        return self.client.get(f"/api/studio/channels/{self.cid}/stats?days={days}").json

    def test_private_gate_and_csrf_block_provider(self):
        with patch.object(stats, "provider") as provider:
            anonymous = self.app.test_client()
            for path in ("/api/studio/channel-stats", f"/api/studio/channels/{self.cid}/stats"):
                self.assertEqual(anonymous.get(path).status_code, 401)
            self.assertEqual(self.refresh(csrf=False).status_code, 403)
            provider.assert_not_called()

    def test_first_snapshot_has_totals_but_no_fabricated_growth(self):
        with patch.object(stats, "provider", return_value=(self.values, [])) as provider:
            r = self.refresh()
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json["totals"], self.values)
            self.assertIsNone(r.json["gain"])
            self.assertEqual(self.client.get("/api/studio/channel-stats").json["ranking"], [])
            for _ in range(3):
                self.read()
                self.refresh()
            self.assertEqual(provider.call_count, 1)
            self.assertEqual(self.refresh().json["status"], "cached")
            text = self.client.get("/api/studio/channel-stats").get_data(as_text=True)
            for secret in ("stats-fixture-refresh", "stats-fixture-secret", "lease_id", "proxy"):
                self.assertNotIn(secret, text)

    def test_partial_tracking_negative_corrections_and_stale_exclusion(self):
        self.snapshot(22, 2400)
        self.snapshot(1, 2300)
        r = self.read()
        self.assertEqual(r["gain"], -100)
        self.assertTrue(r["partial"])
        self.assertEqual(self.client.get("/api/studio/channel-stats").json["ranking"][0]["gain"], -100)
        with self.store.db() as c:
            c.execute("DELETE FROM studio_channel_snapshots")
        self.snapshot(24, 2400)
        self.snapshot(10, 2600)
        self.assertTrue(self.read()["stale"])
        self.assertEqual(self.client.get("/api/studio/channel-stats").json["ranking"], [])

    def test_period_baseline_and_channel_ranking_use_observed_window(self):
        self.snapshot(8 * 24, 100)
        self.snapshot(7 * 24 + 1, 500)
        self.snapshot(25, 900)
        self.snapshot(0, 1500)
        self.assertEqual(self.read()["gain"], 1000)
        self.assertFalse(self.read()["partial"])
        self.assertEqual(self.read(1)["gain"], 600)
        self.assertEqual(self.read(28)["gain"], 1400)
        second = next(c for c in self.store.channels() if c["key"] == "football_en")
        self.link(second["id"], "UCStatsFootball")
        self.snapshot(7 * 24 + 1, 50, second["id"], "UCStatsFootball")
        self.snapshot(0, 1200, second["id"], "UCStatsFootball")
        ranking = self.client.get("/api/studio/channel-stats").json["ranking"]
        self.assertEqual([r["channel_id"] for r in ranking], [second["id"], self.cid])
        self.assertEqual(self.client.get("/api/studio/channel-stats?days=365").status_code, 400)

    def test_disconnect_purges_stats_and_no_unconnected_remote_reads(self):
        self.snapshot(1, 100)
        with patch.object(stats, "provider", return_value=(self.values, [])):
            self.refresh()
        r = self.client.post(f"/api/studio/youtube/{self.cid}/disconnect", json={"revision": self.store.channel(self.cid)["revision"]}, headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(self.read()["connected"])
        self.assertEqual(self.store.rows("SELECT * FROM studio_channel_snapshots"), [])
        self.assertEqual(self.store.rows("SELECT * FROM studio_channel_sync"), [])
        with patch.object(stats, "provider") as provider:
            self.assertEqual(self.refresh().status_code, 400)
            provider.assert_not_called()

    def test_retired_and_preview_channels_cannot_refresh(self):
        self.app.config["PREVIEW"] = True
        with patch.object(stats, "provider") as provider:
            self.assertEqual(self.refresh().status_code, 400)
            self.app.config["PREVIEW"] = False
            self.snapshot(1, 100)
            ch = self.store.channel(self.cid)
            self.store.retire_channel(self.cid, ch["revision"])
            self.assertEqual(self.refresh().status_code, 400)
            self.assertEqual(self.store.rows("SELECT * FROM studio_channel_snapshots"), [])
            provider.assert_not_called()

    def test_provider_failure_preserves_cache_and_sanitizes_error(self):
        self.snapshot(1, 100)
        failure = urllib.error.HTTPError("https://oauth2.googleapis.com/token", 400, "stats-fixture-refresh", {}, io.BytesIO(b"stats-fixture-secret"))
        with patch.object(stats, "provider", side_effect=failure):
            r = self.refresh()
        self.assertEqual(r.json["status"], "error")
        self.assertEqual(r.json["totals"]["views"], 100)
        self.assertIn("Reconnecte", r.json["error"])
        self.assertNotIn("stats-fixture", r.get_data(as_text=True))

    def test_atomic_lease_and_disconnect_during_refresh_reject_result(self):
        with self.store.db() as c:
            c.execute("INSERT INTO studio_channel_sync(channel_id,lease_until,lease_id) VALUES(?,?,?)", (self.cid, (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(), "other-run"))
        with patch.object(stats, "provider") as provider:
            self.assertEqual(self.refresh().json["status"], "running")
            provider.assert_not_called()
        with self.store.db() as c:
            c.execute("DELETE FROM studio_channel_sync")
        def disconnect(_):
            with self.store.db() as c:
                c.execute("UPDATE delamain_projects SET yt_refresh_token='' WHERE id=?", (self.cid,))
                stats.clear(c, self.cid)
            return self.values, []
        with patch.object(stats, "provider", side_effect=disconnect):
            self.assertEqual(self.refresh().status_code, 409)
        self.assertEqual(self.store.rows("SELECT * FROM studio_channel_snapshots"), [])

    def test_background_read_runs_while_publishing_paused_and_respects_interval(self):
        with self.store.db() as c:
            c.execute("UPDATE studio_settings SET paused=1")
        with patch.object(stats, "provider", return_value=(self.values, [])) as provider:
            stats.tick(self.store)
            stats.tick(self.store)
            provider.assert_called_once()
        self.assertEqual(self.read()["totals"]["views"], 2300)
        self.assertEqual(self.store.settings()["paused"], 1)
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])

    def test_retention_and_changed_identity_do_not_display_old_counters(self):
        self.snapshot(30 * 24, 100)
        self.snapshot(1, 999, youtube_id="UCPreviousAccount")
        self.assertIsNone(self.read()["totals"]["views"])
        self.assertEqual(len(self.store.rows("SELECT * FROM studio_channel_snapshots")), 1)

    def test_google_calls_identify_channel_and_filter_foreign_videos(self):
        responses = [
            {"access_token": "stats-fixture-access"},
            {"items": [{"id": self.yt, "statistics": {"viewCount": "420", "videoCount": "2", "subscriberCount": "1400", "hiddenSubscriberCount": True}, "contentDetails": {"relatedPlaylists": {"uploads": "UUFIXTURE"}}}]},
            {"items": [{"contentDetails": {"videoId": "abcdefghijk"}}, {"contentDetails": {"videoId": "lmnopqrstuv"}}, {"contentDetails": {"videoId": "invalid?url"}}]},
            {"items": [{"id": "abcdefghijk", "snippet": {"channelId": self.yt, "title": "Fixture video", "publishedAt": "2026-10-01T10:00:00Z"}, "statistics": {"viewCount": "41"}}, {"id": "lmnopqrstuv", "snippet": {"channelId": "OTHER"}, "statistics": {"viewCount": "999"}}]},
        ]
        opener = Mock()
        opener.open.side_effect = [io.StringIO(json.dumps(r)) for r in responses]
        project = self.store.one("SELECT * FROM delamain_projects WHERE id=?", (self.cid,))
        with patch("routes.youtube._opener", return_value=opener):
            totals, videos = stats.provider(project)
        self.assertEqual(totals, dict(views=420, subscribers=None, videos=2))
        self.assertEqual([v["id"] for v in videos], ["abcdefghijk"])
        calls = [call.args[0] for call in opener.open.call_args_list]
        self.assertEqual(calls[0].get_method(), "POST")
        self.assertEqual(parse_qs(urlsplit(calls[1].full_url).query)["mine"], ["true"])
        self.assertTrue(all(call.get_method() == "GET" for call in calls[1:]))
        self.assertTrue(all("stats-fixture-access" not in call.full_url for call in calls))

    def test_wrong_google_channel_identity_is_rejected(self):
        opener = Mock()
        opener.open.side_effect = [io.StringIO(json.dumps(r)) for r in ({"access_token": "fixture"}, {"items": [{"id": "OTHER", "statistics": {"viewCount": "999"}}]})]
        with patch("routes.youtube._opener", return_value=opener):
            r = self.refresh()
        self.assertEqual(r.json["status"], "error")
        self.assertIsNone(r.json["totals"]["views"])
        self.assertEqual(len(opener.open.call_args_list), 2)


if __name__ == "__main__":
    unittest.main()
