"""Local companion authorization; no fixture logs into or uploads to YouTube."""
import base64
import hashlib
import io
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.parse
import zipfile

from production.pc_youtube import PairingError, authenticated_dashboard, dashboard_channel, validate_manifest
from studio.pc_youtube import latest, TABLE
from studio.pc_installer import SOURCE, installer_zip
from studio.worker import worker_application

CID = "UC" + "a" * 22


class PCPairingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = worker_application(dict(TESTING=True, HOSTED=False, PREVIEW=True,
            SECRET_KEY="fixture-session-key-never-exported", DB_PATH=Path(self.tmp.name) / "studio.db", IMPORT_PRODUCTIONS=False))
        self.store = self.app.extensions["studio_store"]
        self.client = self.app.test_client()
        self.machine = self.app.test_client()
        self.csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        self.app.config["PREVIEW"] = False
        self.cid = next(c["id"] for c in self.store.channels() if c["key"] == "mma_en")
        self.lookup = patch("studio.public_statistics.lookup", return_value=dict(youtube_id=CID, name="Cage Dispatch"))
        self.lookup.start()

    def tearDown(self):
        self.lookup.stop(); self.tmp.cleanup()

    def post(self, action="connect", revision=None):
        return self.client.post(f"/api/studio/youtube/{self.cid}/pc/{action}", json={"revision": self.store.channel(self.cid)["revision"] if revision is None else revision}, headers={"X-CSRF-Token": self.csrf})

    def connect(self):
        result = self.post(); self.assertEqual(result.status_code, 202)
        self.state = result.json
        parsed = urllib.parse.urlsplit(self.state["launch_uri"])
        self.rid = parsed.path.lstrip("/")
        self.auth = {"Authorization": "Bearer " + urllib.parse.parse_qs(parsed.query)["token"][0]}
        self.path = "/api/studio/pc-local/" + self.rid
        return result

    def progress(self, status="waiting", code="preparing_browser", **changes):
        data=dict(status=status, code=code, device_id="d" * 32, expected_channel_id=CID,
                  channel_id="", browser_visible=False, navigation_verified=False)
        data.update(changes)
        return self.machine.post(self.path + "/progress", json=data, headers=self.auth)

    def preparing(self):
        self.assertEqual(self.progress().status_code, 200)

    def signing_in(self):
        self.preparing()
        self.assertEqual(self.progress(code="sign_in", browser_visible=True).status_code, 200)

    def test_connection_never_uses_shared_relay_or_claims_browser_opened(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("No relay access")):
            self.connect()
            self.assertEqual(self.post("check").json["status"], "awaiting_app")
        self.assertIn("n’a pas encore répondu", self.state["message"])
        self.assertEqual(latest(self.store, self.cid)["device_id"], "")

    def test_pairing_does_not_activate_or_publish(self):
        before = self.store.channel(self.cid)
        self.connect(); self.signing_in()
        self.assertEqual(self.progress("ready", "dashboard_confirmed", browser_visible=True, navigation_verified=True, channel_id=CID).status_code, 200)
        state = self.post("check").json
        self.assertEqual(state["status"], "ready")
        self.assertFalse(state["publication_validated"])
        self.assertNotIn("launch_uri", state)
        self.assertNotIn("device_id", state)
        self.assertEqual(self.store.channel(self.cid), before)
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])

    def test_duplicate_request_returns_same_link_without_new_command(self):
        self.connect()
        self.assertEqual(self.post().json["launch_uri"], self.state["launch_uri"])
        self.assertEqual(len(self.store.rows(f"SELECT * FROM {TABLE}")), 1)

    def test_preview_revision_and_csrf_guards(self):
        self.app.config["PREVIEW"] = True
        self.assertEqual(self.post().status_code, 400)
        self.app.config["PREVIEW"] = False
        self.assertEqual(self.post(revision=-1).status_code, 409)
        self.assertEqual(self.client.post(f"/api/studio/youtube/{self.cid}/pc/connect", json={"revision": 1}).status_code, 403)
        self.assertIsNone(latest(self.store,self.cid))

    def test_editor_cannot_launch_or_download_and_sees_no_capability(self):
        self.connect()
        with self.store.db() as c: c.execute("UPDATE studio_users SET role='editor'")
        state=self.client.get(f"/api/studio/youtube/{self.cid}/pc").json
        self.assertNotIn("launch_uri", state); self.assertNotIn("installer_href", state)
        self.assertEqual(self.post().status_code,403)
        self.assertEqual(self.post("check").status_code,403)
        self.assertEqual(self.client.get(self.state["installer_href"]).status_code,403)
        self.assertEqual(self.machine.get(self.path+"/manifest",headers=self.auth).status_code,410)

    def test_anonymous_cannot_read_connect_or_download(self):
        self.connect()
        self.assertEqual(self.machine.get(f"/api/studio/youtube/{self.cid}/pc").status_code,401)
        self.assertEqual(self.machine.get(self.state["installer_href"]).status_code,401)
        self.assertEqual(self.machine.post(f"/api/studio/youtube/{self.cid}/pc/connect",json={"revision":1}).status_code,401)

    def test_caps_do_not_grant_other_site_actions_or_other_requests(self):
        self.connect()
        self.assertEqual(self.machine.get("/api/studio/workspace",headers=self.auth).status_code,401)
        self.assertEqual(self.machine.post(f"/api/studio/youtube/{self.cid}/disconnect",json={},headers=self.auth).status_code,401)
        other=self.path.replace(self.rid,"pc-local-"+"e"*32)
        self.assertEqual(self.machine.get(other+"/manifest",headers=self.auth).status_code,403)
        self.assertEqual(self.machine.get(self.path+"/manifest").status_code,401)
        self.assertEqual(self.machine.get(self.path+"/manifest",headers={"Authorization":"Bearer "+"e"*64}).status_code,403)

    def test_machine_manifest_only_has_scoped_channel_and_deadline(self):
        self.connect()
        response=self.machine.get(self.path+"/manifest",headers=self.auth)
        self.assertEqual(response.status_code,200)
        self.assertEqual(set(response.json),{"channel_id","channel_title","deadline"})
        self.assertEqual(response.json["channel_id"],CID)
        self.assertEqual(response.headers["Cache-Control"],"no-store")

    def test_invalid_expected_and_device_fields_cannot_report_progress(self):
        self.connect()
        for changes in [{"device_id":"../default"},{"device_id":False},{"expected_channel_id":"UC"+"b"*22},{"status":[]},{"code":[]}]:
            with self.subTest(changes=changes):self.assertEqual(self.progress(**changes).status_code,400)
        self.assertEqual(latest(self.store,self.cid)["status"],"awaiting_app")

    def test_ready_requires_visible_browser_and_first_party_channel_confirmation(self):
        self.connect()
        self.assertEqual(self.progress("ready","dashboard_confirmed",browser_visible=True,navigation_verified=True,channel_id=CID).status_code,400)
        self.preparing()
        self.assertEqual(self.progress(code="sign_in",browser_visible=False).status_code,400)
        self.assertEqual(self.progress(code="sign_in",browser_visible=True).status_code,200)
        for changes in [{"browser_visible":False},{"navigation_verified":False},{"channel_id":"UC"+"b"*22}]:
            data=dict(browser_visible=True,navigation_verified=True,channel_id=CID);data.update(changes)
            self.assertEqual(self.progress("ready","dashboard_confirmed",**data).status_code,400)
        self.assertEqual(latest(self.store,self.cid)["status"],"waiting")

    def test_other_device_cannot_take_over_a_started_connection(self):
        self.connect();self.preparing()
        self.assertEqual(self.progress(code="sign_in",browser_visible=True,device_id="e"*32).status_code,409)
        self.assertEqual(latest(self.store,self.cid)["device_id"],"d"*32)

    def test_expiry_retirement_and_revision_invalidate_the_capability(self):
        self.connect()
        with patch("studio.pc_youtube.now",return_value="2999-01-01T00:00:00+00:00"):
            self.assertEqual(self.machine.get(self.path+"/manifest",headers=self.auth).status_code,410)
        self.store.update_channel(self.cid,{"paused":1},self.store.channel(self.cid)["revision"])
        self.assertEqual(self.progress().status_code,410)
        self.assertEqual(self.post("check").json["status"],"failed")
        self.connect()
        self.store.retire_channel(self.cid,self.store.channel(self.cid)["revision"])
        self.assertEqual(self.machine.get(self.path+"/manifest",headers=self.auth).status_code,410)

    def test_concurrent_channel_edit_prevents_request_creation(self):
        def changed(*args):
            self.store.update_channel(self.cid,{"paused":1},self.store.channel(self.cid)["revision"])
            return dict(youtube_id=CID,name="Cage Dispatch")
        with patch("studio.public_statistics.lookup",side_effect=changed):self.assertEqual(self.post().status_code,409)
        self.assertIsNone(latest(self.store,self.cid))

    def test_actor_checked_again_inside_progress_transaction(self):
        self.connect()
        from studio.pc_youtube import valid_actor
        calls=[0]
        def raced(c,row):
            calls[0]+=1
            return valid_actor(c,row) if calls[0]==1 else False
        with patch("studio.pc_youtube.valid_actor",side_effect=raced):self.assertEqual(self.progress().status_code,410)
        self.assertEqual(latest(self.store,self.cid)["status"],"awaiting_app")

    def test_wrong_existing_identity_is_rejected(self):
        with self.store.db() as c:c.execute("UPDATE delamain_projects SET yt_channel_id=? WHERE id=?",("UC"+"b"*22,self.cid))
        self.assertEqual(self.post().status_code,400)
        self.assertIsNone(latest(self.store,self.cid))

    def test_failure_is_final_and_new_request_can_be_created(self):
        self.connect();self.preparing()
        self.assertEqual(self.progress("failed","cancelled").status_code,200)
        self.assertEqual(self.progress().status_code,410)
        self.assertEqual(self.post("check").json["status"],"failed")
        old=self.rid;self.connect();self.assertNotEqual(self.rid,old)

    def test_cross_origin_and_oversized_machine_responses_rejected(self):
        self.connect()
        bad=dict(self.auth,Origin="https://other.example")
        self.assertEqual(self.machine.post(self.path+"/progress",json={},headers=bad).status_code,403)
        self.assertEqual(self.machine.post(self.path+"/progress",data=b"a"*2049,headers=self.auth).status_code,413)

    def test_private_installer_bundles_only_owned_code_and_scoped_link(self):
        self.connect()
        response=self.client.get(self.state["installer_href"])
        self.assertEqual(response.status_code,200)
        self.assertIn("Edgerunners-PC.zip",response.headers["Content-Disposition"])
        self.assertEqual(response.headers["Cache-Control"],"no-store")
        with zipfile.ZipFile(io.BytesIO(response.data)) as z:
            self.assertEqual(set(z.namelist()),{"Installer.cmd","EdgerunnersPC.cs","LISEZ-MOI.txt"})
            cmd=z.read("Installer.cmd").decode("ascii")
            encoded=cmd.split("::EDGERUNNERS_SOURCE_BEGIN\r\n",1)[1].strip()
            self.assertEqual(base64.b64decode(encoded),SOURCE.read_bytes())
            self.assertIn(hashlib.sha256(SOURCE.read_bytes()).hexdigest(),cmd)
            self.assertIn(self.state["launch_uri"],cmd)
            self.assertIn("'%%1'",cmd)
            self.assertLess(len(cmd.splitlines()[3]),8000)
            self.assertTrue(cmd.splitlines()[3].endswith('"'))
            self.assertIn(r"\r?\n",cmd.splitlines()[3])
            self.assertNotIn("ExecutionPolicy",cmd)
            self.assertNotIn(self.app.config["SECRET_KEY"],cmd)
            for text in ["NEWS_WORKER_TOKEN","GOOGLE_CLIENT_SECRET","ALGROW_API_KEY"]:self.assertNotIn(text,cmd)
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"),[])

    def test_installer_rejects_command_injection(self):
        with self.assertRaises(ValueError):installer_zip("edgerunners-studio://connect/../?token=x&cmd=evil")

    def test_expired_installer_download_does_not_install(self):
        self.connect()
        with patch("studio.pc_youtube.now",return_value="2999-01-01T00:00:00+00:00"):
            self.assertEqual(self.client.get(self.state["installer_href"]).status_code,400)

    def test_channel_connection_does_not_depend_on_worker_credentials(self):
        with patch.dict(os.environ,{"NEWS_WORKER_URL":"","NEWS_WORKER_TOKEN":""}):self.connect()
        self.assertTrue(self.state["configured"])

    def test_machine_capability_never_bypasses_host_or_https(self):
        self.connect()
        self.app.config.update(HOSTED=True,PUBLIC_URL="https://edgerunners.fr")
        self.assertEqual(self.machine.get(self.path+"/manifest",headers=self.auth,base_url="https://other.example").status_code,400)
        self.assertEqual(self.machine.post(self.path+"/progress",json={},headers=self.auth,base_url="http://edgerunners.fr").status_code,426)
        self.assertEqual(self.machine.get(self.path+"/manifest",headers=self.auth,base_url="https://edgerunners.fr").status_code,200)

    def test_machine_posts_respect_deployment_maintenance(self):
        self.connect()
        marker=Path(self.tmp.name)/"maintenance.json"
        marker.write_text("{}")
        self.app.config["DEVELOPMENT_MAINTENANCE_PATH"]=str(marker)
        self.assertEqual(self.progress().status_code,503)
        self.assertEqual(latest(self.store,self.cid)["status"],"awaiting_app")


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
