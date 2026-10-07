"""Security/lease tests for the new private viewer; no real Google account used."""
import base64
import json
import os
from pathlib import Path
import secrets
import tempfile
import time
import unittest
from unittest.mock import patch
from studio.browser_connection import BRIDGE_PATH, signature, service_digest
from studio.web import create_app


class BrowserConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"YOUTUBE_BROWSER_ENABLED": "1", "NEWS_WORKER_TOKEN": "fixture-private-worker-credential-12345"})
        self.env.start()
        self.app = create_app({"TESTING": True, "PREVIEW": True, "WORKER_ENABLED": False, "SECRET_KEY": "fixture-session-key", "DB_PATH": Path(self.tmp.name)/"studio.db", "IMPORT_PRODUCTIONS": False})
        self.store = self.app.extensions["studio_store"]
        self.client = self.app.test_client()
        self.csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        self.app.config["PREVIEW"] = False
        self.cid = next(ch["id"] for ch in self.store.channels() if ch["key"] == "mma_en")
        self.expected = "UC"+"a"*22
        with self.store.db() as c:
            c.execute("UPDATE delamain_projects SET yt_channel_id=? WHERE id=?", (self.expected, self.cid))
        self.instance = secrets.token_hex(16)
        self.key = base64.b64encode(b"test-public-key-not-a-secret"*20).decode()
        self.bridge_client = self.app.test_client()
        self.bridge()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def bridge(self, result=None, **kwargs):
        value = {"instance": self.instance, "public_key": self.key, "source_digest": service_digest()}
        if result: value["result"] = result
        value.update(kwargs)
        body = json.dumps(value).encode()
        stamp, nonce = str(int(time.time())), secrets.token_hex(16)
        headers = {"Content-Type": "application/json", "X-Browser-Time": stamp, "X-Browser-Nonce": nonce,
                   "X-Browser-Proof": signature(os.environ["NEWS_WORKER_TOKEN"], stamp, nonce, body)}
        self.last_request = (body, headers)
        return self.bridge_client.post(BRIDGE_PATH, data=body, headers=headers)

    def post(self, path, value):
        return self.client.post("/api/studio/youtube-browser"+path, json=value, headers={"X-CSRF-Token": self.csrf})

    def viewer(self):
        response = self.post(f"/{self.cid}/sessions", {"revision": self.store.channel(self.cid)["revision"]})
        self.assertEqual(response.status_code, 200)
        return response.json["session_id"]

    def test_signed_bridge_requires_signature_and_rejects_replay(self):
        self.assertEqual(self.bridge_client.post(BRIDGE_PATH, json={}).status_code, 403)
        body, headers = self.last_request
        self.assertEqual(self.bridge_client.post(BRIDGE_PATH, data=body, headers=headers).status_code, 409)
        changed = dict(headers, **{"X-Browser-Proof": "é"*64})
        self.assertEqual(self.bridge_client.post(BRIDGE_PATH, data=body, headers=changed).status_code, 403)
        self.assertEqual(self.bridge_client.post(BRIDGE_PATH, data=body+b" ", headers=headers).status_code, 403)
        with patch.dict(os.environ, {"YOUTUBE_BROWSER_ENABLED": "0"}):
            self.assertEqual(self.bridge().status_code, 403)

    def test_plaintext_input_rejected_owner_session_bound_and_logout_revokes(self):
        sid = self.viewer()
        path = f"/{self.cid}/sessions/{sid}"
        bad = self.post(path+"/commands", {"kind": "input", "text": "not-a-real-password"})
        self.assertEqual(bad.status_code, 400)
        self.assertNotIn("not-a-real-password", json.dumps(self.store.rows("SELECT * FROM studio_browser_commands")))
        response = self.post(path+"/commands", {"kind": "frame"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.post(path+"/commands", {"kind": "frame"}).status_code, 409)
        identity = response.json["command_id"]
        work = self.bridge().json
        self.assertEqual(work["command"]["id"], identity)
        self.assertEqual(work["command"]["expected_id"], self.expected)
        self.assertIsNone(self.bridge().json["command"])
        self.bridge(result={"id": identity, "value": {"image": "fixture-frame"}})
        self.assertEqual(self.client.get("/api/studio/youtube-browser"+path+"/commands/"+identity).json["result"]["image"], "fixture-frame")
        self.client.post("/api/studio/logout", json={}, headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(self.client.get("/api/studio/youtube-browser"+path+"/commands/"+identity).status_code, 401)
        self.assertEqual(self.bridge().json["sessions"], [])
        self.assertEqual(self.store.rows("SELECT * FROM studio_browser_commands"), [])

    def test_editor_preview_and_unsigned_workers_cannot_access_viewer(self):
        sid = self.viewer()
        with self.client.session_transaction() as session:
            from studio import security
            security.issue(self.store, "collegue", container=session)
            csrf = session["csrf"]
        self.csrf = csrf
        self.assertEqual(self.client.get("/api/studio/youtube-browser/status").status_code, 403)
        self.assertEqual(self.post(f"/{self.cid}/sessions/{sid}/commands", {"kind": "frame"}).status_code, 403)
        self.app.config["PREVIEW"] = True
        self.assertEqual(self.bridge().status_code, 403)

    def test_channel_changes_worker_restart_expiry_revoke_without_enabling_publication(self):
        sid = self.viewer()
        with self.store.db() as c:
            c.execute("UPDATE studio_channels SET revision=revision+1 WHERE project_id=?", (self.cid,))
        self.assertEqual(self.bridge().json["sessions"], [])
        self.assertEqual(self.post(f"/{self.cid}/sessions/{sid}/commands", {"kind": "frame"}).status_code, 400)
        sid = self.viewer()
        self.instance = secrets.token_hex(16)
        self.assertEqual(self.bridge().json["sessions"], [])
        sid = self.viewer()
        with self.store.db() as c:
            c.execute("UPDATE studio_browser_sessions SET expires_at=? WHERE id=?", (time.time()-1, sid))
        self.assertEqual(self.bridge().json["sessions"], [])
        self.assertFalse(self.store.channel(self.cid)["enabled"])
        self.assertFalse(self.store.channel(self.cid)["connected"])

    def test_missing_csrf_and_wrong_session_do_not_reach_worker(self):
        sid = self.viewer()
        self.assertEqual(self.client.post(f"/api/studio/youtube-browser/{self.cid}/sessions/{sid}/commands", json={"kind": "frame"}).status_code, 403)
        self.assertEqual(self.post(f"/{self.cid+1}/sessions/{sid}/commands", {"kind": "frame"}).status_code, 400)
        self.assertEqual(self.store.rows("SELECT * FROM studio_browser_commands"), [])

    def test_machine_endpoint_still_requires_the_hosted_site_and_https(self):
        self.app.config.update(HOSTED=True, PUBLIC_URL="https://studio.example.invalid")
        body = json.dumps({"instance": self.instance, "public_key": self.key, "source_digest": service_digest()}).encode()
        stamp, nonce = str(int(time.time())), secrets.token_hex(16)
        headers = {"Content-Type": "application/json", "X-Browser-Time": stamp,
                   "X-Browser-Nonce": nonce, "X-Browser-Proof": signature(os.environ["NEWS_WORKER_TOKEN"], stamp, nonce, body)}
        self.assertEqual(self.bridge_client.post(BRIDGE_PATH, data=body, headers=headers,
                         base_url="http://studio.example.invalid").status_code, 426)
        self.assertEqual(self.bridge_client.post(BRIDGE_PATH, data=body, headers=headers,
                         base_url="https://other.example.invalid").status_code, 400)
        self.assertEqual(self.bridge_client.post(BRIDGE_PATH, data=body, headers=headers,
                         base_url="https://studio.example.invalid").status_code, 200)


if __name__ == "__main__":
    unittest.main()
