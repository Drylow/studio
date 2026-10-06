"""Public handle lookup, observed history, cache races and private API-key storage."""
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
from studio.security import trusted_client
from studio import public_statistics as stats

KEY = "public-reading-fixture-" + "x" * 25
YOUTUBE_ID = "UC" + "a" * 22


class PublicStatisticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {name: "" for name in ("YOUTUBE_API_KEY", "YOUTUBE_DATA_API_KEY", "GOOGLE_API_KEY")})
        self.env.start()
        self.app = create_app(dict(TESTING=True, PREVIEW=True, HOSTED=False, WORKER_ENABLED=False,
                                   SECRET_KEY="public-statistics-private-fixture", IMPORT_PRODUCTIONS=False,
                                   DB_PATH=Path(self.tmp.name) / "public.db"))
        self.store = self.app.extensions["studio_store"]
        self.client = self.app.test_client()
        self.csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        self.app.config["PREVIEW"] = False
        self.channel = next(c for c in self.store.channels() if c["key"] == "mma_en")
        self.public = dict(youtube_id=YOUTUBE_ID, handle="@FixtureChannel", name="Fixture channel",
                           uploads="UU" + "a" * 22, views=1000, subscribers=None, videos=2)
        with self.store.db() as c:
            c.execute("UPDATE studio_public_settings SET api_key=? WHERE id=1", (KEY,))

    def tearDown(self):
        stats._cleaned.pop(str(self.store.path), None)
        self.env.stop()
        self.tmp.cleanup()

    def post(self, path, data=None, client=None, csrf=None):
        return (client or self.client).post("/api/studio/statistics" + path, json=data or {},
                                           headers={"X-CSRF-Token": csrf or self.csrf})

    def add(self, studio=True):
        with patch.object(stats, "lookup", return_value=self.public):
            identity, created = stats.add(self.store, "@FixtureChannel", self.channel["id"] if studio else None)
        self.assertTrue(created)
        return identity

    def samples(self, identity, values):
        with self.store.db() as c:
            c.execute("DELETE FROM studio_public_samples WHERE track_id=?", (identity,))
            for hours, views, subscribers in values:
                stamp = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
                c.execute("INSERT INTO studio_public_samples VALUES(?,?,?,?,?)", (identity, stamp, views, subscribers, 2))

    def read(self, hours=48):
        return self.client.get(f"/api/studio/statistics?hours={hours}").json

    def test_handles_and_urls_do_not_allow_arbitrary_network_destinations(self):
        for value in ("@Foo.bar", "Foo.bar", "https://www.youtube.com/@Foo.bar?si=test", "youtube.com/@Foo.bar/", "@ChaîneÉté"):
            self.assertTrue(stats.normalize_handle(value).startswith("@"))
        for value in (None, "", "@@bad", "https://evil.example/@Foo", "https://www.youtube.com.evil.example/@Foo",
                      "http://youtube.com/@Foo", "https://user@youtube.com/@Foo", "https://youtube.com:bad/@Foo",
                      "https://youtube.com/watch?v=abcdefghijk", "@Foo/../Bar", "a" * 101):
            with self.subTest(value=value), self.assertRaises(ValueError):
                stats.normalize_handle(value)

    def test_public_key_is_header_only_and_handle_lookup_has_no_oauth(self):
        payload = {"items": [{"id": YOUTUBE_ID, "snippet": {"title": "Fixture", "customUrl": "@Fixture"},
                    "statistics": {"viewCount": "123", "subscriberCount": "456", "hiddenSubscriberCount": True, "videoCount": "2"},
                    "contentDetails": {"relatedPlaylists": {"uploads": "UU" + "a" * 22}}}]}
        with patch.object(stats.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(payload).encode())) as open_url:
            result = stats.lookup(KEY, "@Fixture")
        req = open_url.call_args.args[0]
        self.assertEqual(urlsplit(req.full_url).netloc, "www.googleapis.com")
        self.assertEqual(parse_qs(urlsplit(req.full_url).query)["forHandle"], ["@Fixture"])
        self.assertEqual(req.get_header("X-goog-api-key"), KEY)
        self.assertNotIn(KEY, req.full_url)
        self.assertFalse(any(name.lower() == "authorization" for name in req.headers))
        self.assertEqual(result["views"], 123)
        self.assertIsNone(result["subscribers"])

    def test_provider_errors_are_sanitized_and_never_disclose_key(self):
        for reason, expected in (("API_KEY_INVALID", "invalide"), ("SERVICE_DISABLED", "Active"), ("quotaExceeded", "quota")):
            body = {"error": {"message": KEY, "details": [{"reason": reason}]}}
            failure = urllib.error.HTTPError("https://www.googleapis.com", 400, KEY, {}, io.BytesIO(json.dumps(body).encode()))
            with patch.object(stats.urllib.request, "urlopen", side_effect=failure), self.assertRaises(ValueError) as err:
                stats.api_read(KEY, "channels", part="statistics", forHandle="@Fixture")
            self.assertIn(expected, str(err.exception))
            self.assertNotIn(KEY, str(err.exception))

    def test_private_gate_csrf_and_owner_key_permissions(self):
        with patch.object(stats, "lookup") as lookup:
            anonymous = self.app.test_client()
            for path in ("/statistics", "/statistics/channels/missing", "/statistics/export"):
                self.assertEqual(anonymous.get("/api/studio" + path).status_code, 401)
            self.assertEqual(self.client.post("/api/studio/statistics/key", json={"api_key": KEY}).status_code, 403)
            editor = next(u for u in self.store.users() if u["role"] == "editor")
            with trusted_client(self.store, editor["id"]) as (client, csrf, _):
                self.assertEqual(self.post("/key", {"api_key": KEY}, client, csrf).status_code, 403)
                self.assertEqual(client.get("/api/studio/statistics").status_code, 200)
            lookup.assert_not_called()

    def test_key_is_validated_before_persistence_and_not_returned(self):
        with patch.object(stats, "lookup", side_effect=ValueError("Clé invalide")):
            self.assertEqual(self.post("/key", {"api_key": "invalid-reading-fixture-" + "y" * 25}).status_code, 400)
        self.assertEqual(stats.api_key(self.store), KEY)
        with patch.object(stats, "lookup", return_value=self.public) as lookup:
            response = self.post("/key", {"api_key": KEY})
        self.assertEqual(response.status_code, 200)
        lookup.assert_called_once_with(KEY, "@GoogleDevelopers")
        self.assertNotIn(KEY, response.get_data(as_text=True))
        self.assertNotIn(KEY, json.dumps(self.read()))
        self.assertTrue(self.read()["configuration"]["verified_at"])

    def test_missing_key_and_preview_prevent_real_reads(self):
        with self.store.db() as c:
            c.execute("UPDATE studio_public_settings SET api_key='' WHERE id=1")
        with patch.object(stats.urllib.request, "urlopen") as open_url:
            self.assertFalse(self.read()["configuration"]["configured"])
            self.assertEqual(self.post("/channels", {"handle": "@Fixture"}).status_code, 400)
            self.app.config["PREVIEW"] = True
            self.assertEqual(self.post("/key", {"api_key": KEY}).status_code, 400)
            self.assertEqual(self.post("/channels", {"handle": "@Fixture"}).status_code, 400)
            stats.tick(self.store)
            open_url.assert_not_called()

    def test_first_public_snapshot_and_duplicate_do_not_need_google_connection(self):
        identity = self.add()
        self.assertFalse(self.store.channel(self.channel["id"])["connected"])
        record = self.read()["channels"][0]
        self.assertEqual(record["totals"]["views"], 1000)
        self.assertIsNone(record["gain"])
        self.assertIsNone(record["totals"]["subscribers"])
        with patch.object(stats, "lookup", return_value=self.public):
            self.assertEqual(stats.add(self.store, "@RenamedAlias"), (identity, False))
        self.assertEqual(len(self.read()["channels"]), 1)
        self.assertEqual(len(record["history"]), 1)

    def test_association_rejects_wrong_google_identity_and_retired_project(self):
        with self.store.db() as c:
            c.execute("UPDATE delamain_projects SET yt_channel_id=? WHERE id=?", ("UC" + "b" * 22, self.channel["id"]))
        with patch.object(stats, "lookup", return_value=self.public), self.assertRaises(ValueError):
            stats.add(self.store, "@Fixture", self.channel["id"])
        self.store.retire_channel(self.channel["id"], self.channel["revision"])
        with patch.object(stats, "lookup") as lookup, self.assertRaises(ValueError):
            stats.add(self.store, "@Fixture", self.channel["id"])
        lookup.assert_not_called()

    def test_periods_use_observed_baselines_partial_history_and_negative_corrections(self):
        identity = self.add()
        self.samples(identity, [(169, 1000, 200), (49, 3000, 300), (25, 4000, 300), (0, 5000, 400)])
        self.assertEqual(self.read(168)["channels"][0]["gain"], 4000)
        self.assertFalse(self.read(168)["channels"][0]["partial"])
        self.assertEqual(self.read(48)["channels"][0]["gain"], 2000)
        self.assertEqual(self.read(24)["channels"][0]["gain"], 1000)
        self.assertTrue(self.read(672)["channels"][0]["partial"])
        self.assertEqual(self.client.get("/api/studio/statistics?hours=1").status_code, 400)
        self.samples(identity, [(22, 2400, None), (1, 2300, None)])
        row = self.read()["channels"][0]
        self.assertTrue(row["partial"])
        self.assertEqual(row["gain"], -100)
        self.assertIsNone(row["subscriber_gain"])
        self.samples(identity, [(25, 2400, None), (10, 2600, None)])
        self.assertTrue(self.read()["channels"][0]["stale"])

    def test_refresh_is_cached_gets_do_not_read_google_and_pause_does_not_stop_public_tick(self):
        identity = self.add()
        with patch.object(stats, "api_read") as read, patch.object(stats.threading, "Thread") as thread:
            for _ in range(3):
                self.read()
                self.client.get(f"/api/studio/statistics/channels/{identity}")
            self.assertEqual(self.post(f"/channels/{identity}/refresh").status_code, 202)
            with self.store.db() as c:
                c.execute("UPDATE studio_settings SET paused=1")
            stats.tick(self.store)
            thread.return_value.start.assert_called_once()
            read.assert_not_called()
        stats._threads.pop(str(self.store.path), None)
        with self.store.db() as c:
            c.execute("UPDATE studio_public_sync SET last_attempt=? WHERE track_id=?", (stats.now(), identity))
        self.assertEqual(self.post(f"/channels/{identity}/refresh").json["status"], "cached")
        with self.store.db() as c:
            c.execute("UPDATE studio_public_sync SET lease_until=? WHERE track_id=?", ((datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat(), identity))
        self.assertEqual(self.post(f"/channels/{identity}/refresh").json["status"], "running")

    def test_sync_caches_public_videos_but_preserves_counts_on_video_failure(self):
        identity = self.add()
        item = {"id": YOUTUBE_ID, "snippet": {"title": "Renamed", "customUrl": "@NewHandle"}, "statistics": {"viewCount": "1500", "videoCount": "2"}}
        with patch.object(stats, "api_read", return_value={"items": [item]}), patch.object(stats, "video_data", side_effect=ValueError("unavailable")):
            stats.sync(self.store, identity)
        row = self.read()["channels"][0]
        self.assertEqual(row["name"], "Renamed")
        self.assertEqual(row["totals"]["views"], 1500)
        self.assertEqual(row["gain"], 500)
        self.assertIn("liste des vidéos", row["error"])
        before = self.store.rows("SELECT * FROM studio_public_samples")
        with self.store.db() as c:
            c.execute("UPDATE studio_public_sync SET next_check='' WHERE track_id=?", (identity,))
        with patch.object(stats, "api_read", side_effect=ValueError("Quota atteint")):
            stats.sync(self.store, identity)
        self.assertEqual(self.store.rows("SELECT * FROM studio_public_samples"), before)
        self.assertEqual(self.read()["channels"][0]["error"], "Quota atteint")

    def test_deleted_track_or_invalidated_lease_cannot_be_resurrected_by_inflight_sync(self):
        identity = self.add()
        def deleted(*args, **kwargs):
            with self.store.db() as c:
                c.execute("DELETE FROM studio_public_channels WHERE id=?", (identity,))
            return {"items": []}
        with patch.object(stats, "api_read", side_effect=deleted):
            stats.sync(self.store, identity)
        self.assertEqual(self.read()["channels"], [])
        identity = self.add()
        def invalidated(*args, **kwargs):
            with self.store.db() as c:
                c.execute("UPDATE studio_public_sync SET lease_id='' WHERE track_id=?", (identity,))
            return {"items": [{"id": YOUTUBE_ID, "snippet": {}, "statistics": {"viewCount": "99999"}}]}
        with patch.object(stats, "api_read", side_effect=invalidated), patch.object(stats, "video_data", return_value=([], False)):
            stats.sync(self.store, identity)
        self.assertEqual(self.read()["channels"][0]["totals"]["views"], 1000)

    def test_public_video_selection_is_bounded_and_ignores_other_channels_and_private_videos(self):
        identity = "abcdefghijk"
        calls = []
        def provider(key, resource, **params):
            calls.append(resource)
            if resource == "playlistItems":
                return {"items": [{"contentDetails": {"videoId": identity}}], "nextPageToken": "more"}
            return {"items": [
                {"id": identity, "snippet": {"title": "Public", "channelId": YOUTUBE_ID, "publishedAt": "2026-10-01T10:00:00Z"},
                 "status": {"privacyStatus": "public"}, "statistics": {"viewCount": "123", "commentCount": "0"}, "contentDetails": {"duration": "PT4M30S"}},
                {"id": identity, "snippet": {"channelId": "another"}, "status": {"privacyStatus": "public"}},
                {"id": identity, "snippet": {"channelId": YOUTUBE_ID}, "status": {"privacyStatus": "private"}},
            ]}
        with patch.object(stats, "api_read", side_effect=provider):
            videos, more = stats.video_data(KEY, self.public)
        self.assertTrue(more)
        self.assertEqual(calls.count("playlistItems"), 4)
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]["duration"], 270)
        self.assertIsNone(videos[0]["likes"])
        self.assertEqual(videos[0]["comments"], 0)

    def test_video_period_gains_do_not_confuse_publication_date_or_missing_baseline(self):
        identity = self.add()
        old = (datetime.now(timezone.utc)-timedelta(hours=49)).isoformat()
        recent = (datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
        with self.store.db() as c:
            c.execute("UPDATE studio_public_sync SET videos_at=? WHERE track_id=?", (recent, identity))
            c.execute("INSERT INTO studio_public_videos VALUES(?,?,?,?,?,?,?,?)", (identity,"abcdefghijk","Recent",recent,270,5000,100,10))
            c.execute("INSERT INTO studio_public_video_samples VALUES(?,?,?,?)", (identity,"abcdefghijk",old,4000))
            c.execute("INSERT INTO studio_public_video_samples VALUES(?,?,?,?)", (identity,"abcdefghijk",recent,5000))
        video = stats.videos_report(self.store, identity, 48)[0]
        self.assertEqual(video["gain"], 1000)
        self.assertTrue(video["published_in_period"])
        self.assertFalse(video["partial"])
        self.assertEqual(video["engagement"], 2.2)
        with self.store.db() as c:
            c.execute("UPDATE studio_public_video_samples SET views=NULL WHERE captured_at=?", (old,))
        self.assertIsNone(stats.videos_report(self.store, identity, 48)[0]["gain"])

    def test_delete_and_oauth_disconnect_are_independent_and_retention_is_bounded(self):
        identity = self.add()
        self.samples(identity, [(30*24, 500, None), (2, 800, None), (0, 1000, None)])
        stats._cleaned.pop(str(self.store.path), None)
        stats.cleanup(self.store)
        self.assertEqual(len(self.read()["channels"][0]["history"]), 2)
        self.assertEqual(self.client.post(f"/api/studio/youtube/{self.channel['id']}/disconnect", json={"revision": self.channel["revision"]}, headers={"X-CSRF-Token": self.csrf}).status_code, 200)
        self.assertEqual(len(self.read()["channels"]), 1)
        self.assertEqual(self.client.delete(f"/api/studio/statistics/channels/{identity}", headers={"X-CSRF-Token": self.csrf}).status_code, 200)
        self.assertEqual(self.store.rows("SELECT * FROM studio_public_samples"), [])
        self.assertIsNotNone(self.store.channel(self.channel["id"]))

    def test_csv_is_private_and_formula_safe_and_chart_keeps_real_endpoints(self):
        identity = self.add()
        with self.store.db() as c:
            c.execute("UPDATE studio_public_channels SET name='=FORMULA()' WHERE id=?", (identity,))
        text = self.client.get("/api/studio/statistics/export").get_data(as_text=True)
        self.assertIn("'=FORMULA()", text)
        self.assertNotIn(KEY, text)
        history = [{"captured_at": str(i), "views": i} for i in range(700)]
        chart = stats.chart_history(history)
        self.assertLessEqual(len(chart), 121)
        self.assertEqual(chart[0], history[0])
        self.assertEqual(chart[-1], history[-1])


if __name__ == "__main__":
    unittest.main()
