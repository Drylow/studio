"""Channel identity, OAuth returns and hosted-worker actions without remote calls."""

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch
import urllib.error

from studio.store import uid
from studio.worker import worker_application, run


class YouTubeConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "fixture-client",
                "GOOGLE_CLIENT_SECRET": "fixture-server-secret",
                "OAUTH_REDIRECT_BASE": "https://studio.example.org",
            },
        )
        self.env.start()
        self.app = worker_application(
            dict(
                TESTING=True,
                PREVIEW=True,
                SECRET_KEY="fixture-session",
                DB_PATH=Path(self.tmp.name) / "studio.db",
                IMPORT_PRODUCTIONS=False,
            )
        )
        self.store = self.app.extensions["studio_store"]
        self.client = self.app.test_client()
        self.csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        self.app.config["PREVIEW"] = False
        self.channel = next(c for c in self.store.channels() if c["key"] == "mma_en")
        self.cid = self.channel["id"]
        self.yt_id = "UCfixtureMMAChannel"

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def post(self, action, revision=None):
        return self.client.post(
            f"/api/studio/youtube/{self.cid}/{action}",
            json={
                "revision": (
                    revision
                    if revision is not None
                    else self.store.channel(self.cid)["revision"]
                )
            },
            headers={"X-CSRF-Token": self.csrf},
        )

    def state(self):
        r = self.client.get(f"/api/studio/youtube/{self.cid}/connect")
        self.assertEqual(r.status_code, 302)
        query = parse_qs(urlparse(r.location).query)
        self.assertEqual(
            query["redirect_uri"],
            ["https://studio.example.org/api/studio/youtube/callback"],
        )
        self.assertEqual(query["access_type"], ["offline"])
        return query["state"][0]

    def callback(self, state=None, title=None, yt_id=None, fetch=None):
        state = state or self.state()
        response = Mock()
        response.__enter__ = Mock(
            return_value=io.StringIO(
                json.dumps(
                    {
                        "refresh_token": "fixture-permanent-access",
                        "access_token": "fixture-short-access",
                    }
                )
            )
        )
        response.__exit__ = Mock(return_value=False)
        with patch("urllib.request.urlopen", return_value=response), patch(
            "routes.youtube._fetch_channel",
            side_effect=fetch,
            return_value=(title or self.channel["name"], yt_id or self.yt_id),
        ):
            return self.client.get(
                "/api/studio/youtube/callback",
                query_string={"state": state, "code": "fixture-code"},
            )

    def linked(self):
        with self.store.db() as c:
            c.execute(
                "UPDATE delamain_projects SET yt_channel_id=?,yt_channel_title=?,yt_refresh_token=? WHERE id=?",
                (
                    self.yt_id,
                    self.channel["name"],
                    "fixture-permanent-access",
                    self.cid,
                ),
            )

    def test_oauth_binds_one_channel_does_not_enable_and_state_is_one_use(self):
        state = self.state()
        old = self.store.channel(self.cid)
        r = self.callback(state)
        self.assertEqual(r.location, f"/channels?connected={self.cid}")
        ch = self.store.channel(self.cid)
        self.assertEqual(ch["yt_channel_id"], self.yt_id)
        self.assertEqual(ch["connected"], 1)
        self.assertEqual(ch["enabled"], 0)
        self.assertEqual(ch["revision"], old["revision"] + 1)
        self.assertEqual(ch["autonomy"], old["autonomy"])
        workspace = self.client.get("/api/studio/workspace").get_data(as_text=True)
        self.assertNotIn("fixture-permanent-access", workspace)
        self.assertNotIn("fixture-server-secret", workspace)
        with patch("urllib.request.urlopen") as remote:
            self.assertEqual(
                self.client.get(
                    "/api/studio/youtube/callback",
                    query_string={"state": state, "code": "again"},
                ).status_code,
                400,
            )
            remote.assert_not_called()

    def test_oauth_rejects_another_channel_without_overwriting_access(self):
        self.linked()
        r = self.callback(yt_id="UCotherChannel")
        self.assertIn("youtube_error", parse_qs(urlparse(r.location).query))
        self.assertEqual(self.store.channel(self.cid)["yt_channel_id"], self.yt_id)
        self.assertEqual(
            self.store.channel(self.cid)["revision"], self.channel["revision"]
        )

    def test_first_connection_rejects_mismatched_name_and_duplicate_identity(self):
        r = self.callback(title="Unrelated Channel")
        self.assertIn("youtube_error", r.location)
        self.assertFalse(self.store.channel(self.cid)["connected"])
        other = next(c for c in self.store.channels() if c["id"] != self.cid)
        with self.store.db() as c:
            c.execute(
                "UPDATE delamain_projects SET yt_channel_id=? WHERE id=?",
                (self.yt_id, other["id"]),
            )
        r = self.callback()
        self.assertIn("youtube_error", r.location)
        self.assertFalse(self.store.channel(self.cid)["connected"])

    def test_connection_cannot_overwrite_a_concurrent_edit_or_retirement(self):
        def edit(_):
            self.store.update_channel(
                self.cid,
                {"instructions": "Colleague edit"},
                self.channel["revision"],
            )
            return self.channel["name"], self.yt_id

        r = self.callback(fetch=edit)
        self.assertIn("youtube_error", r.location)
        self.assertFalse(self.store.channel(self.cid)["connected"])

        def retire(_):
            ch = self.store.channel(self.cid)
            self.store.retire_channel(self.cid, ch["revision"])
            return self.channel["name"], self.yt_id

        r = self.callback(fetch=retire)
        self.assertIn("youtube_error", r.location)
        raw = self.store.one(
            "SELECT yt_refresh_token FROM delamain_projects WHERE id=?", (self.cid,)
        )
        self.assertEqual(raw["yt_refresh_token"], "")

    def test_google_failure_returns_to_the_studio_without_raw_provider_error(self):
        state = self.state()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("fixture-server-secret"),
        ):
            r = self.client.get(
                "/api/studio/youtube/callback",
                query_string={"state": state, "code": "fixture"},
            )
        self.assertEqual(r.status_code, 302)
        self.assertIn("youtube_error", r.location)
        self.assertNotIn("fixture-server-secret", r.location)
        self.assertFalse(self.store.channel(self.cid)["connected"])

    def test_refused_consent_returns_to_channel_without_network_or_token(self):
        state = self.state()
        with patch("urllib.request.urlopen") as remote:
            r = self.client.get(
                "/api/studio/youtube/callback",
                query_string={"state": state, "error": "access_denied"},
            )
        self.assertEqual(r.status_code, 302)
        self.assertIn("youtube_error", r.location)
        remote.assert_not_called()
        self.assertFalse(self.store.channel(self.cid)["connected"])

    def test_delamain_checks_access_as_the_requesting_account(self):
        from studio.agent import respond

        self.linked()
        plan = {
            "message": "Tout est OK",
            "actions": [{"type": "youtube_verify", "channel_id": self.cid}],
        }
        with patch("services.ai.chat_json", return_value=plan), patch(
            "routes.youtube._access_token", return_value="fixture-access"
        ) as remote, patch(
            "routes.youtube._fetch_channel",
            return_value=(self.channel["name"], self.yt_id),
        ):
            result = respond(self.store, "Vérifie YouTube", "Drylow", uid(), "drylow")
            self.assertEqual(result["actions"], 1)
            self.assertIn("Connexion vérifiée", result["message"])
            remote.reset_mock()
            result = respond(self.store, "Vérifie YouTube", "Kanye", uid(), "collegue")
            self.assertEqual(result["actions"], 0)
            remote.assert_not_called()

    def test_connection_verification_checks_google_identity_and_keeps_rules(self):
        self.linked()
        old = self.store.channel(self.cid)
        with patch(
            "routes.youtube._access_token", return_value="fixture-short-access"
        ) as token, patch(
            "routes.youtube._fetch_channel",
            return_value=(self.channel["name"], self.yt_id),
        ):
            r = self.post("verify")
        self.assertEqual(r.status_code, 200)
        token.assert_called_once()
        self.assertEqual(r.json["channel_id"], self.yt_id)
        self.assertIn("checked_at", r.json)
        self.assertNotIn("fixture-short-access", r.get_data(as_text=True))
        self.assertEqual(self.store.channel(self.cid), old)
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])

    def test_verification_handles_missing_expired_wrong_or_changed_access(self):
        with patch("routes.youtube._access_token") as token:
            self.assertEqual(self.post("verify").status_code, 400)
            token.assert_not_called()
        self.linked()
        with patch(
            "routes.youtube._access_token",
            side_effect=urllib.error.URLError("fixture-permanent-access"),
        ):
            r = self.post("verify")
            self.assertEqual(r.status_code, 400)
            self.assertNotIn("fixture-permanent-access", r.get_data(as_text=True))
        with patch(
            "routes.youtube._access_token", return_value="fixture-short-access"
        ), patch("routes.youtube._fetch_channel", return_value=("Other", "UCwrong")):
            self.assertEqual(self.post("verify").status_code, 400)

        def disconnect(_):
            self.store.update_channel(
                self.cid,
                {"paused": 1},
                self.store.channel(self.cid)["revision"],
            )
            return self.channel["name"], self.yt_id

        with patch(
            "routes.youtube._access_token", return_value="fixture-short-access"
        ), patch("routes.youtube._fetch_channel", side_effect=disconnect):
            self.assertEqual(self.post("verify").status_code, 409)

    def test_disconnect_suspends_only_this_channel_and_retains_binding(self):
        self.linked()
        with self.store.db() as c:
            c.execute(
                "UPDATE studio_channels SET enabled=1,paused=0 WHERE project_id=?",
                (self.cid,),
            )
        other = next(c for c in self.store.channels() if c["id"] != self.cid)
        r = self.post("disconnect")
        self.assertEqual(r.status_code, 200)
        ch = self.store.channel(self.cid)
        self.assertEqual((ch["connected"], ch["enabled"], ch["paused"]), (0, 0, 1))
        self.assertEqual(ch["yt_channel_id"], self.yt_id)
        self.assertEqual(self.store.channel(other["id"]), other)
        self.assertEqual(
            self.post("disconnect", self.channel["revision"]).status_code, 409
        )

    def test_connection_operations_require_owner_csrf_and_non_preview(self):
        self.linked()
        with patch("routes.youtube._access_token") as remote:
            self.app.config["PREVIEW"] = True
            for action in ["verify", "disconnect"]:
                self.assertEqual(self.post(action).status_code, 400)
            self.assertEqual(
                self.client.get(f"/api/studio/youtube/{self.cid}/connect").status_code,
                400,
            )
            self.app.config["PREVIEW"] = False
            self.assertEqual(
                self.client.post(
                    f"/api/studio/youtube/{self.cid}/disconnect", json={"revision": 1}
                ).status_code,
                403,
            )
            with self.client.session_transaction() as session:
                session["studio_user"] = "collegue"
            for action in ["verify", "disconnect"]:
                self.assertEqual(self.post(action).status_code, 403)
            self.assertEqual(
                self.client.get(f"/api/studio/youtube/{self.cid}/connect").status_code,
                403,
            )
            remote.assert_not_called()

    def test_standalone_worker_dispatches_delamain_through_authenticated_routes(self):
        self.assertIs(self.store.web_app, self.app)
        self.assertFalse(self.app.config["WORKER_ENABLED"])
        jid = self.store.enqueue(
            "agent",
            payload={
                "message": "Crée une tâche",
                "actor": "Drylow",
                "user_id": "drylow",
            },
        )
        with patch(
            "services.ai.chat_json",
            return_value={
                "message": "Prepared",
                "actions": [
                    {
                        "type": "task",
                        "title": "Hosted worker task",
                        "assignee": "collegue",
                    }
                ],
            },
        ):
            run(self.store, once=True)
        self.assertEqual(
            self.store.one("SELECT status FROM studio_jobs WHERE id=?", (jid,))[
                "status"
            ],
            "done",
        )
        task = self.store.one(
            "SELECT * FROM studio_tasks WHERE title=?", ("Hosted worker task",)
        )
        self.assertEqual(task["assignee"], "collegue")
