"""Workspace boundaries, restart recovery and publication tests without external calls."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

from studio.web import create_app
from studio.store import ROOT, Store, now, uid
from studio.domain import blockers, channel_summary, fresh, stock_eligible, TZ
from studio.imports import digest


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ, {"STUDIO_BOOTSTRAP_TOKEN": "test-bootstrap-code"}
        )
        self.env.start()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-session-key",
                "DB_PATH": Path(self.tmp.name) / "studio.db",
                "PREVIEW": False,
                "WORKER_ENABLED": False,
                "IMPORT_PRODUCTIONS": False,
            }
        )
        self.store = self.app.extensions["studio_store"]
        self.client = self.app.test_client()
        self.csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        r = self.client.post(
            "/api/studio/setup",
            json={
                "token": "test-bootstrap-code",
                "name": "Owner",
                "username": "owner",
                "password": "a sufficiently long test password",
            },
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(r.status_code, 200)
        self.csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        self.channel = self.store.channels()[0]

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def post(self, path, data):
        return self.client.post(
            "/api/studio" + path, json=data, headers={"X-CSRF-Token": self.csrf}
        )

    def patch(self, path, data):
        return self.client.patch(
            "/api/studio" + path, json=data, headers={"X-CSRF-Token": self.csrf}
        )

    def video(self):
        r = self.post(
            "/videos",
            {"channel_id": self.channel["id"], "title": "A grounded sports analysis"},
        )
        self.assertEqual(r.status_code, 201)
        return self.store.video(r.json["id"])

    def colleague(self):
        r = self.post(
            "/users",
            {
                "name": "Colleague",
                "username": "colleague",
                "password": "another long test password",
            },
        )
        self.assertEqual(r.status_code, 201)
        c = self.app.test_client()
        csrf = c.get("/api/studio/bootstrap").json["csrf"]
        r = c.post(
            "/api/studio/login",
            json={"username": "colleague", "password": "another long test password"},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(r.status_code, 200)
        return c, c.get("/api/studio/bootstrap").json["csrf"]

    def test_session_and_csrf_protect_changes_and_media(self):
        unauth = self.app.test_client()
        self.assertEqual(unauth.get("/api/studio/workspace").status_code, 401)
        self.assertEqual(unauth.get("/media/anything/video").status_code, 401)
        r = self.client.post("/api/studio/tasks", json={"title": "Not authorized"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.store.rows("SELECT * FROM studio_tasks"), [])

    def test_setup_is_one_use_and_login_is_rate_limited(self):
        self.assertEqual(
            self.post("/setup", {"token": "test-bootstrap-code"}).status_code, 400
        )
        c = self.app.test_client()
        csrf = c.get("/api/studio/bootstrap").json["csrf"]
        for _ in range(8):
            self.assertEqual(
                c.post(
                    "/api/studio/login",
                    json={"username": "owner", "password": "wrong"},
                    headers={"X-CSRF-Token": csrf},
                ).status_code,
                401,
            )
        self.assertEqual(
            c.post(
                "/api/studio/login",
                json={"username": "owner", "password": "wrong"},
                headers={"X-CSRF-Token": csrf},
            ).status_code,
            429,
        )

    def test_two_accounts_share_tasks_and_stale_update_is_rejected(self):
        task_id = self.post("/tasks", {"title": "Relire la vidéo"}).json["id"]
        c, csrf = self.colleague()
        tasks = c.get("/api/studio/workspace").json["tasks"]
        t = next(t for t in tasks if t["id"] == task_id)
        r = c.patch(
            "/api/studio/tasks/" + task_id,
            json={"done": True, "revision": t["revision"]},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            self.patch(
                "/tasks/" + task_id, {"done": False, "revision": t["revision"]}
            ).status_code,
            409,
        )
        self.assertEqual(
            self.store.one("SELECT done FROM studio_tasks WHERE id=?", (task_id,))[
                "done"
            ],
            1,
        )

    def test_colleague_cannot_change_budget_or_create_users(self):
        c, csrf = self.colleague()
        self.assertEqual(
            c.patch(
                "/api/studio/settings",
                json={"revision": 1, "daily_budget": 100},
                headers={"X-CSRF-Token": csrf},
            ).status_code,
            403,
        )
        self.assertEqual(
            c.post(
                "/api/studio/users", json={}, headers={"X-CSRF-Token": csrf}
            ).status_code,
            403,
        )

    def test_private_connection_fields_are_never_serialized(self):
        with self.store.db() as c:
            c.execute(
                "UPDATE delamain_projects SET yt_refresh_token=?,proxy=? WHERE id=?",
                ("private-refresh-value", "private-proxy-value", self.channel["id"]),
            )
        text = self.client.get("/api/studio/workspace").get_data(as_text=True)
        self.assertNotIn("private-refresh-value", text)
        self.assertNotIn("private-proxy-value", text)
        self.assertNotIn("yt_refresh_token", text)

    def test_oauth_rejects_forged_state_before_network(self):
        with patch("urllib.request.urlopen") as remote:
            r = self.client.get(
                "/api/studio/youtube/callback?state=forged&code=anything"
            )
            self.assertEqual(r.status_code, 400)
            remote.assert_not_called()

    def test_publication_and_verified_flags_cannot_be_faked_by_patch(self):
        v = self.video()
        r = self.patch(
            "/videos/" + v["id"],
            {
                "revision": v["revision"],
                "status": "published",
                "rights_status": "verified",
            },
        )
        self.assertEqual(r.status_code, 400)
        with patch("urllib.request.urlopen") as remote:
            self.assertEqual(
                self.post(
                    "/videos/" + v["id"] + "/action", {"action": "publish"}
                ).status_code,
                400,
            )
            remote.assert_not_called()
        self.assertEqual(self.store.video(v["id"])["rights_status"], "unknown")

    def test_manual_receipt_is_distinct_from_confirmed_publication(self):
        v = self.video()
        r = self.post(
            "/videos/" + v["id"] + "/action",
            {
                "action": "report",
                "url": "https://youtu.be/abcdefghijk",
                "revision": v["revision"],
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.store.video(v["id"])["status"], "reported")
        self.assertEqual(
            self.client.get("/api/studio/workspace").json["channels"][0]["published"], 0
        )

    def test_calendar_conflicts_and_timezone_requirement(self):
        v = self.video()
        r = self.patch(
            "/videos/" + v["id"],
            {"revision": v["revision"], "post_at": "2099-10-05T18:00"},
        )
        self.assertEqual(r.status_code, 400)
        r = self.patch(
            "/videos/" + v["id"],
            {"revision": v["revision"], "post_at": "2099-10-05T18:00:00+02:00"},
        )
        self.assertEqual(r.status_code, 200)
        v2 = self.video()
        r = self.patch(
            "/videos/" + v2["id"],
            {"revision": v2["revision"], "post_at": "2099-10-05T16:00:00Z"},
        )
        self.assertEqual(r.status_code, 409)

    def test_script_edit_invalidates_previous_review(self):
        v = self.video()
        self.store.update(
            "studio_videos",
            v["id"],
            {
                "quality_status": "verified",
                "rights_status": "verified",
                "render_digest": "hash",
                "approved_digest": "hash",
            },
        )
        v = self.store.video(v["id"])
        self.assertEqual(
            self.patch(
                "/videos/" + v["id"],
                {"revision": v["revision"], "script": "Changed narration"},
            ).status_code,
            200,
        )
        v = self.store.video(v["id"])
        self.assertEqual(v["approved_digest"], "")
        self.assertEqual(v["rights_status"], "unknown")

    def test_duplicate_requests_and_concurrent_workers_are_serialized(self):
        v = self.video()
        with ThreadPoolExecutor(2) as ex:
            ids = list(
                ex.map(lambda _: self.store.enqueue("render", v["id"]), range(2))
            )
        self.assertEqual(ids[0], ids[1])
        with ThreadPoolExecutor(2) as ex:
            claims = list(
                ex.map(lambda owner: self.store.claim(owner), ["worker-a", "worker-b"])
            )
        self.assertEqual(sum(c is not None for c in claims), 1)
        with self.store.db() as c:
            c.execute(
                "UPDATE studio_jobs SET lease_until='2000-01-01T00:00:00+00:00' WHERE id=?",
                (ids[0],),
            )
        self.assertEqual(self.store.claim("restarted")["id"], ids[0])

    def test_agent_retry_does_not_duplicate_workspace_actions(self):
        from studio.agent import respond

        response = {
            "message": "Voici les prochaines priorités.",
            "actions": [
                {
                    "type": "task",
                    "title": "Vérifier la voix",
                    "channel_id": self.channel["id"],
                }
            ],
        }
        with patch("services.ai.chat_json", return_value=response) as provider:
            a = respond(self.store, "Prépare les tâches.", "Owner", "stable-job-id")
            b = respond(self.store, "Prépare les tâches.", "Owner", "stable-job-id")
        self.assertEqual(a, b)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(len(self.store.rows("SELECT * FROM studio_tasks")), 1)

    def test_cancelled_queue_is_not_claimed(self):
        v = self.video()
        jid = self.store.enqueue("render", v["id"])
        self.assertEqual(self.post("/jobs/" + jid + "/cancel", {}).status_code, 200)
        self.assertIsNone(self.store.claim("worker"))

    def test_cancel_after_worker_crash_releases_the_video_reservation(self):
        v = self.video()
        jid = self.store.enqueue("render", v["id"])
        self.store.claim("old-worker")
        self.post("/jobs/" + jid + "/cancel", {})
        with self.store.db() as c:
            c.execute(
                "UPDATE studio_jobs SET lease_until='2000-01-01T00:00:00+00:00' WHERE id=?",
                (jid,),
            )
        self.assertIsNone(self.store.claim("restarted"))
        self.assertNotEqual(self.store.enqueue("render", v["id"]), jid)

    def test_concurrent_calendar_writes_cannot_reserve_the_same_slot(self):
        a = self.video()
        b = self.video()

        def reserve(v):
            try:
                self.store.update(
                    "studio_videos",
                    v["id"],
                    {"post_at": "2099-10-05T16:00:00+00:00"},
                    v["revision"],
                )
                return True
            except sqlite3.IntegrityError:
                return False

        with ThreadPoolExecutor(2) as ex:
            result = list(ex.map(reserve, [a, b]))
        self.assertEqual(sum(result), 1)

    def test_worker_failure_is_visible_and_provider_secret_is_redacted(self):
        from studio.worker import run

        v = self.video()
        self.store.enqueue("render", v["id"])
        with patch.dict(os.environ, {"AI_API_KEY": "provider-secret-fixture"}), patch(
            "studio.jobs.execute",
            side_effect=RuntimeError("error: provider-secret-fixture"),
        ):
            run(self.store, once=True)
        self.assertEqual(self.store.video(v["id"])["status"], "blocked")
        self.assertNotIn("provider-secret-fixture", self.store.video(v["id"])["error"])

    def test_legacy_ui_redirects_and_secret_tool_files_are_unavailable(self):
        self.assertEqual(self.client.get("/tools/osl-studio").status_code, 302)
        self.assertEqual(self.client.get("/tools/delamain").location, "/agent")
        self.assertEqual(self.client.get("/toolfiles/config.js").status_code, 404)


class MigrationAndStockTests(unittest.TestCase):
    def test_old_messages_survive_additive_migration(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "old.db"
            c = sqlite3.connect(path)
            c.execute(
                "CREATE TABLE delamain_messages(id INTEGER,project_id INTEGER,content TEXT)"
            )
            c.execute(
                "INSERT INTO delamain_messages VALUES(1,5,'keep this conversation')"
            )
            c.commit()
            c.close()
            s = Store(path)
            s.migrate()
            s.migrate()
            self.assertEqual(
                s.one("SELECT content FROM delamain_messages")["content"],
                "keep this conversation",
            )

    def fixtures(self):
        at = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)
        c = {
            "id": 1,
            "format": "news",
            "freshness_hours": 48,
            "autonomy": "auto",
            "enabled": 1,
            "paused": 0,
            "connected": 1,
            "cadence_days": "1",
            "post_time": "18:00",
            "target_stock": 3,
        }
        v = {
            "id": "a",
            "channel_id": 1,
            "status": "ready",
            "event_at": at.isoformat(),
            "quality_status": "verified",
            "rights_status": "verified",
            "video_path": "file",
            "thumb_path": "thumb",
            "render_digest": "hash",
            "approved_digest": "hash",
            "post_at": "",
            "youtube_id": "",
        }
        return at, c, v

    def test_news_staleness_and_future_stale_schedule_do_not_count_as_stock(self):
        at, c, v = self.fixtures()
        self.assertTrue(stock_eligible(v, c, at))
        self.assertFalse(fresh(v, c, at + timedelta(hours=49)))
        v["post_at"] = (at + timedelta(days=7)).isoformat()
        self.assertFalse(stock_eligible(v, c, at))

    def test_calendar_coverage_stops_at_gap(self):
        at, c, v = self.fixtures()
        c["format"] = "history"
        v["status"] = "scheduled"
        v["post_at"] = "2026-10-05T18:00:00+02:00"
        later = dict(v, id="b", post_at="2026-10-08T18:00:00+02:00")
        result = channel_summary(c, [v, later], at)
        self.assertEqual(result["ready"], 2)
        self.assertLess(result["days_ahead"], 1)

    def test_scheduled_wall_clock_survives_autumn_timezone_change(self):
        before = datetime(2026, 10, 24, 18, tzinfo=TZ)
        after = before + timedelta(days=1)
        self.assertEqual(before.hour, after.hour)
        self.assertEqual(
            (
                after.astimezone(timezone.utc) - before.astimezone(timezone.utc)
            ).total_seconds(),
            25 * 3600,
        )

    def test_private_youtube_id_can_resume_but_published_video_cannot(self):
        at, c, v = self.fixtures()
        v["youtube_id"] = "abcdefghijk"
        self.assertEqual(blockers(v, c, {"paused": 0}, at=at), [])
        v["status"] = "published"
        self.assertTrue(blockers(v, c, {"paused": 0}, at=at))

    def test_preview_refuses_non_local_clients(self):
        with tempfile.TemporaryDirectory() as d:
            app = create_app(
                {
                    "TESTING": True,
                    "SECRET_KEY": "test-key",
                    "DB_PATH": Path(d) / "p.db",
                    "PREVIEW": True,
                    "WORKER_ENABLED": False,
                    "IMPORT_PRODUCTIONS": False,
                }
            )
            self.assertEqual(
                app.test_client()
                .get(
                    "/api/studio/bootstrap",
                    environ_overrides={"REMOTE_ADDR": "203.0.113.8"},
                )
                .status_code,
                403,
            )


class PublishingRecoveryTests(unittest.TestCase):
    def test_upload_session_survives_lost_response_and_does_not_duplicate_video(self):
        from studio.publishing import publish

        with tempfile.TemporaryDirectory(dir=ROOT / "work/studio") as d:
            s = Store(Path(d) / "s.db")
            s.migrate()
            from studio.imports import seed

            seed(s)
            ch = s.channels()[0]
            with s.db() as c:
                c.execute(
                    "UPDATE delamain_projects SET yt_refresh_token=?,yt_channel_id='UCfixturePublication' WHERE id=?",
                    ("fixture", ch["id"]),
                )
            ch = s.channel(ch["id"])
            path = Path(d) / "video.mp4"
            path.write_bytes(b"preverified fixture bytes")
            thumb = Path(d) / "thumb.png"
            thumb.write_bytes(b"preverified fixture thumbnail")
            vid = s.add_video(
                {
                    "channel_id": ch["id"],
                    "title": "Verified fixture",
                    "status": "ready",
                    "quality_status": "verified",
                    "rights_status": "verified",
                    "render_digest": digest(path),
                    "video_path": str(path.relative_to(ROOT)),
                    "thumb_path": str(thumb.relative_to(ROOT)),
                    "event_at": now(),
                }
            )
            with s.db() as c:
                c.execute(
                    "CREATE TABLE studio_reviews(video_id TEXT PRIMARY KEY,manifest TEXT,video_sha256 TEXT,thumbnail_sha256 TEXT,created_at TEXT)"
                )
                c.execute(
                    "INSERT INTO studio_reviews VALUES(?,?,?,?,?)",
                    (vid, "{}", digest(path), digest(thumb), now()),
                )
            calls = []

            class Response(io.BytesIO):
                def __init__(self, payload=None, headers=None):
                    super().__init__(json.dumps(payload or {}).encode())
                    self.headers = headers or {}

            class Opener:
                lost = True

                def open(self, req, timeout=None):
                    calls.append((req.get_method(), req.full_url))
                    if "uploadType=resumable" in req.full_url:
                        return Response(
                            headers={
                                "Location": "https://www.googleapis.com/upload/session-fixture"
                            }
                        )
                    if req.full_url.endswith("session-fixture"):
                        if self.lost:
                            self.lost = False
                            raise urllib.error.URLError("lost completion response")
                        return Response({"id": "abcdefghijk"})
                    if "thumbnails/set" in req.full_url:
                        return Response()
                    return Response({"status": {"privacyStatus": "public"}})

            class Job:
                def update(self, *args):
                    pass

            op = Opener()
            with patch(
                "routes.youtube._access_token", return_value="fixture-access"
            ), patch("routes.youtube._opener", return_value=op), patch(
                "routes.youtube._fetch_channel", return_value=(ch["name"], "UCfixturePublication")
            ):
                with self.assertRaises(urllib.error.URLError):
                    publish(s, s.video(vid), ch, Job())
                self.assertTrue(
                    s.one(
                        "SELECT session_url FROM studio_uploads WHERE video_id=?",
                        (vid,),
                    )
                )
                result = publish(s, s.video(vid), ch, Job())
            self.assertTrue(result["published"])
            self.assertEqual(s.video(vid)["status"], "published")
            self.assertEqual(sum("uploadType=resumable" in url for _, url in calls), 1)


class EngineResumeTests(unittest.TestCase):
    def test_news_edited_narration_is_rendered_without_overwriting_archive(self):
        from studio.jobs import news_production

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            store = Store(root / "studio.db")
            store.migrate()
            from studio.imports import seed

            seed(store)
            ch = next(c for c in store.channels() if c["key"] == "mma_en")
            sources = [
                {
                    "id": "official",
                    "name": "Official source",
                    "url": "https://example.org/source",
                }
            ]
            old = " ".join(["original"] * 600)
            edited = " ".join(["corrected"] * 600)
            archive = root / "archive"
            archive.mkdir()
            original = {
                "title": "Archive",
                "channel": "mma_en",
                "reviewed_at": now(),
                "sources": sources,
                "segments": [
                    {
                        "headline": "Archive",
                        "lines": ["Original"],
                        "narration": old,
                        "source_ids": ["official"],
                    }
                ],
            }
            raw = json.dumps(original)
            (archive / "brief.json").write_text(raw)
            vid = store.add_video(
                {
                    "channel_id": ch["id"],
                    "title": "Corrected analysis",
                    "script": edited,
                    "sources": sources,
                    "notes": "Verified correction",
                    "engine_ref": {"kind": "news", "brief": True, "job": "archive"},
                }
            )
            with patch("studio.jobs.ROOT", root), patch(
                "services.news_brief.build", return_value={}
            ) as build, patch("services.ai.chat_json") as ai:
                news_production(store, store.video(vid), ch, Mock(), "render")
                build.assert_called_once()
                ai.assert_not_called()
                plan = json.loads(
                    (root / "work/studio/productions" / vid / "brief.json").read_text()
                )
                self.assertEqual(plan["segments"][0]["narration"], edited)
                self.assertEqual((archive / "brief.json").read_text(), raw)
                changed = store.video(vid)
                changed["notes"] = "A new verified fact"
                with self.assertRaisesRegex(ValueError, "faits ou sources"):
                    news_production(store, changed, ch, Mock(), "render")
                build.assert_called_once()

    def test_history_edited_script_invalidates_dependent_stages(self):
        from studio.jobs import sync_history_script

        engine = Mock()
        engine.script_from_fos.return_value = {"hook": "Corrected", "sections": []}
        project = {
            "title": "History",
            "script": {"hook": "Old", "sections": []},
            "voice": {"file": "old.mp3"},
            "plan": {"scenes": []},
            "render": {"file": "old.mp4"},
        }
        sync_history_script(engine, project, "Corrected narration")
        self.assertIsNone(project["voice"])
        self.assertIsNone(project["plan"])
        self.assertIsNone(project["render"])
        self.assertEqual(project["fos"]["text"], "Corrected narration")
        engine.save_project.assert_called_once_with(project)
        sync_history_script(engine, project, "Corrected narration")
        engine.save_project.assert_called_once()


if __name__ == "__main__":
    unittest.main()
