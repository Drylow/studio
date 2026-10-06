"""PC pairing safeguards; fixtures never authenticate or upload to YouTube."""

import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from production.pc_youtube import PairingError, authenticated_dashboard, dashboard_channel, validate_manifest
from studio.pc_youtube import apply_result, latest
from studio.worker import worker_application

CID = "UC" + "a" * 22


class PCPairingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"NEWS_WORKER_URL": "https://relay.example.org", "NEWS_WORKER_TOKEN": "fixture-relay-private"})
        self.env.start()
        self.app = worker_application(dict(TESTING=True, HOSTED=False, PREVIEW=True,
            SECRET_KEY="fixture-session", DB_PATH=Path(self.tmp.name) / "studio.db", IMPORT_PRODUCTIONS=False))
        self.store = self.app.extensions["studio_store"]
        self.client = self.app.test_client()
        self.csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        self.app.config["PREVIEW"] = False
        self.cid = next(c["id"] for c in self.store.channels() if c["key"] == "mma_en")
        self.relay = patch("studio.pc_youtube.relay", side_effect=lambda path, *args: {"pc_seen": time.time()} if path == "/status" else {"ok": True})
        self.remote = self.relay.start()
        self.lookup = patch("studio.public_statistics.lookup", return_value=dict(youtube_id=CID, name="Cage Dispatch"))
        self.lookup.start()

    def tearDown(self):
        self.lookup.stop(); self.relay.stop(); self.env.stop(); self.tmp.cleanup()

    def post(self, action="connect", revision=None):
        return self.client.post(f"/api/studio/youtube/{self.cid}/pc/{action}", json={"revision": self.store.channel(self.cid)["revision"] if revision is None else revision}, headers={"X-CSRF-Token": self.csrf})

    def result(self, **changes):
        row = latest(self.store, self.cid)
        return dict(version=1, action="connect", request_id=row["request_id"], nonce=row["nonce"],
            expected_channel_id=CID, channel_id=CID, dashboard_seen=True, device_id="d" * 32,
            status="ready", code="dashboard_confirmed", **changes)

    def test_payload_has_no_google_or_relay_credentials_and_pairing_does_not_activate(self):
        before = self.store.channel(self.cid)
        self.assertEqual(self.post().status_code, 202)
        raw = self.remote.call_args.args[2]
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            manifest = json.load(archive.extractfile("job/pc_request.json"))
            self.assertEqual(set(manifest), {"action", "request_id", "nonce", "channel_id", "deadline"})
            self.assertEqual(manifest["channel_id"], CID)
            all_bytes = b"".join(archive.extractfile(m).read() for m in archive.getmembers() if m.isfile())
            self.assertNotIn(b"fixture-relay-private", all_bytes)
            self.assertNotIn(b"GOOGLE_CLIENT_SECRET", all_bytes)
        apply_result(self.store, latest(self.store, self.cid), self.result())
        response = self.client.get(f"/api/studio/youtube/{self.cid}/pc").json
        self.assertEqual(response["status"], "ready")
        self.assertFalse(response["publication_validated"])
        self.assertNotIn("nonce", response)
        self.assertNotIn("device_id", response)
        self.assertEqual(self.store.channel(self.cid), before)
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])

    def test_duplicate_request_does_not_launch_a_second_browser(self):
        self.assertEqual(self.post().status_code, 202)
        calls = self.remote.call_count
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(self.remote.call_count, calls)
        self.assertEqual(len(self.store.rows("SELECT * FROM studio_pc_connections")), 1)

    def test_preview_revision_and_csrf_fail_without_remote_calls(self):
        self.app.config["PREVIEW"] = True
        self.assertEqual(self.post().status_code, 400)
        self.app.config["PREVIEW"] = False
        self.assertEqual(self.post(revision=-1).status_code, 409)
        self.assertEqual(self.client.post(f"/api/studio/youtube/{self.cid}/pc/connect", json={"revision": 1}).status_code, 403)
        self.remote.assert_not_called()

    def test_editor_and_anonymous_cannot_open_browser(self):
        with self.store.db() as c:
            c.execute("UPDATE studio_users SET role='editor'")
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.post("check").status_code, 403)
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.get(f"/api/studio/youtube/{self.cid}/pc").status_code, 401)
        self.assertEqual(self.post().status_code, 401)
        self.remote.assert_not_called()

    def test_offline_pc_and_wrong_existing_identity_are_rejected(self):
        self.remote.side_effect = lambda *args: {"pc_seen": time.time() - 400}
        self.assertEqual(self.post().status_code, 400)
        self.assertIsNone(latest(self.store, self.cid))
        self.remote.side_effect = lambda path, *args: {"pc_seen": time.time()} if path == "/status" else {"ok": True}
        with self.store.db() as c:
            c.execute("UPDATE delamain_projects SET yt_channel_id=? WHERE id=?", ("UC" + "b" * 22, self.cid))
        self.assertEqual(self.post().status_code, 400)
        self.assertIsNone(latest(self.store, self.cid))

    def test_concurrent_channel_edit_prevents_dispatch(self):
        def changed(*args):
            self.store.update_channel(self.cid, {"paused": 1}, self.store.channel(self.cid)["revision"])
            return dict(youtube_id=CID, name="Cage Dispatch")
        with patch("studio.public_statistics.lookup", side_effect=changed):
            self.assertEqual(self.post().status_code, 409)
        self.assertEqual(self.remote.call_count, 1)
        self.assertIsNone(latest(self.store, self.cid))

    def test_untrusted_results_cannot_pair(self):
        self.assertEqual(self.post().status_code, 202)
        row = latest(self.store, self.cid)
        for changes in [{"nonce": "wrong"}, {"channel_id": "UC" + "b" * 22},
                        {"dashboard_seen": False}, {"device_id": "../default"}, {"version": True},
                        {"status": []}, {"code": []}]:
            with self.subTest(changes=changes):
                with self.store.db() as c:
                    c.execute("UPDATE studio_pc_connections SET status='waiting' WHERE request_id=?", (row["request_id"],))
                result = self.result(); result.update(changes)
                apply_result(self.store, row, result)
                self.assertEqual(latest(self.store, self.cid)["status"], "failed")

    def test_retirement_and_expiration_ignore_a_late_success(self):
        self.post(); row = latest(self.store, self.cid); result = self.result()
        self.store.retire_channel(self.cid, self.store.channel(self.cid)["revision"])
        apply_result(self.store, row, result)
        self.assertEqual(latest(self.store, self.cid)["code"], "channel_changed")
        self.assertEqual(self.client.get(f"/api/studio/youtube/{self.cid}/pc").status_code, 400)

    def test_polling_records_results_without_publishing_and_is_bounded(self):
        self.post()
        result = self.result()
        self.remote.side_effect = lambda *args: result
        self.assertEqual(self.post("check").json["status"], "ready")
        self.assertFalse(self.store.channel(self.cid)["connected"])
        calls = self.remote.call_count
        self.post("check")
        self.assertEqual(self.remote.call_count, calls)
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])

    def test_waiting_response_is_throttled_and_expired_request_does_not_poll(self):
        self.post(); result = self.result(); result.update(status="waiting", code="sign_in")
        self.remote.side_effect = lambda *args: result
        self.assertEqual(self.post("check").json["status"], "waiting")
        calls = self.remote.call_count
        self.post("check"); self.assertEqual(self.remote.call_count, calls)
        with self.store.db() as c:
            c.execute("UPDATE studio_pc_connections SET expires_at='2000-01-01T00:00:00+00:00'")
        self.assertEqual(self.post("check").json["status"], "failed")
        self.assertEqual(self.remote.call_count, calls)

    def test_ambiguous_dispatch_cannot_submit_a_duplicate(self):
        self.remote.side_effect = lambda path, *args: {"pc_seen": time.time()} if path == "/status" else (_ for _ in ()).throw(ValueError("Temporary relay error"))
        self.assertEqual(self.post().status_code, 202)
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(self.remote.call_count, 2)


class BrowserTrustTests(unittest.TestCase):
    def test_studio_navigation_must_confirm_the_same_channel_as_the_url(self):
        page = Mock(url="https://studio.youtube.com/channel/" + CID)
        def locator(selector):
            if selector == "ytcp-channel-dashboard": return Mock(is_visible=Mock(return_value=False))
            if selector == "ytcp-app": return Mock(is_visible=Mock(return_value=True))
            return Mock(evaluate_all=Mock(return_value=["https://studio.youtube.com/channel/" + CID + suffix for suffix in ["/videos", "/analytics"]]))
        page.locator.side_effect = locator
        self.assertTrue(authenticated_dashboard(page, CID))
        page.url = "https://studio.youtube.com/channel/UC" + "b" * 22
        self.assertFalse(authenticated_dashboard(page, CID))
        page.url = "https://studio.youtube.com/channel/" + CID
        page.locator.side_effect = lambda selector: Mock(is_visible=Mock(return_value=selector == "ytcp-app"), evaluate_all=Mock(return_value=["https://studio.youtube.com/channel/UC" + "b" * 22 + suffix for suffix in ["/videos", "/analytics"]]))
        self.assertFalse(authenticated_dashboard(page, CID))
        page.locator.side_effect = RuntimeError("Navigation unavailable")
        self.assertFalse(authenticated_dashboard(page, CID))

    def test_only_real_https_studio_channel_urls_identify_a_channel(self):
        self.assertEqual(dashboard_channel("https://studio.youtube.com/channel/" + CID), CID)
        for value in ["https://accounts.google.com/channel/" + CID, "https://studio.youtube.com.evil.org/channel/" + CID,
                      "http://studio.youtube.com/channel/" + CID, "https://user@studio.youtube.com/channel/" + CID,
                      "https://studio.youtube.com:443/channel/" + CID, "https://studio.youtube.com/?channel=" + CID,
                      "https://studio.youtube.com/channel/../default"]:
            self.assertEqual(dashboard_channel(value), "")

    def test_manifest_rejects_path_traversal_or_stale_commands(self):
        data = dict(action="connect", request_id="pc-connect-" + "a" * 32, nonce="b" * 64,
                    channel_id=CID, deadline=2000)
        self.assertEqual(validate_manifest(data, 1000), data)
        for field, value in [("channel_id", "../../default"), ("request_id", "../code"), ("nonce", ""),
                             ("action", "upload"), ("deadline", 999), ("deadline", 99999), ("deadline", True)]:
            with self.subTest(field=field, value=value):
                changed = dict(data); changed[field] = value
                with self.assertRaises(PairingError): validate_manifest(changed, 1000)
