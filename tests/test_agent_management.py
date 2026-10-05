"""Agent permissions, canonical release gates, replay and retired channel isolation."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from studio.agent import respond, initialize
from studio.domain import overview
from studio.imports import seed
from studio.store import now, uid
from studio.web import create_app


class AgentManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = dict(
            TESTING=True,
            PREVIEW=True,
            SECRET_KEY="test",
            DB_PATH=Path(self.tmp.name) / "studio.db",
            WORKER_ENABLED=False,
            IMPORT_PRODUCTIONS=False,
        )
        self.app = create_app(self.config)
        self.store = self.app.extensions["studio_store"]
        self.cid = self.store.channels()[0]["id"]

    def tearDown(self):
        self.tmp.cleanup()

    def act(self, actions, user="drylow", before=None, job=None):
        def provider(*args, **kwargs):
            if before:
                before()
            return {"message": "Opération déjà terminée !", "actions": actions}

        with patch("services.ai.chat_json", side_effect=provider):
            return respond(
                self.store,
                "Applique ma demande explicite.",
                "Drylow",
                job or uid(),
                user,
            )

    def video(self):
        return self.store.add_video(
            dict(channel_id=self.cid, title="A sourced analysis", minutes=5, cost_cap=1)
        )

    def test_channel_create_assign_edit_and_retire_use_the_site_rules(self):
        result = self.act(
            [
                {
                    "type": "channel_create",
                    "name": "New Sport Channel",
                    "format": "news",
                    "autonomy": "auto",
                    "enabled": 1,
                }
            ]
        )
        channel = next(
            c for c in self.store.channels() if c["name"] == "New Sport Channel"
        )
        self.assertEqual(channel["autonomy"], "manual")
        self.assertEqual(channel["enabled"], 0)
        self.assertEqual(result["attachments"][0]["id"], channel["id"])
        result = self.act(
            [
                {
                    "type": "channel_assign",
                    "channel_id": channel["id"],
                    "responsible_id": "collegue",
                },
                {
                    "type": "channel_update",
                    "channel_id": channel["id"],
                    "changes": {"post_time": "20:15", "cadence_days": 2},
                },
            ]
        )
        self.assertEqual(result["actions"], 2)
        self.assertEqual(
            self.store.channel(channel["id"])["responsible_id"], "collegue"
        )
        self.assertEqual(self.store.channel(channel["id"])["post_time"], "20:15")
        self.act([{"type": "channel_retire", "channel_id": channel["id"]}])
        self.assertIsNone(self.store.channel(channel["id"]))
        seed(self.store)
        self.assertIsNone(self.store.channel(channel["id"]))

    def test_editor_cannot_change_mode_budget_or_activation(self):
        old = self.store.channel(self.cid)
        result = self.act(
            [
                {
                    "type": "channel_update",
                    "channel_id": self.cid,
                    "changes": {"autonomy": "manual", "budget": 50},
                }
            ],
            user="collegue",
        )
        self.assertEqual(result["actions"], 0)
        self.assertEqual(self.store.channel(self.cid), old)
        result = self.act(
            [
                {
                    "type": "channel_update",
                    "channel_id": self.cid,
                    "changes": {"post_time": "19:00"},
                }
            ],
            user="collegue",
        )
        self.assertEqual(result["actions"], 1)

    def test_owner_cannot_activate_without_connecting_youtube(self):
        result = self.act(
            [
                {
                    "type": "channel_update",
                    "channel_id": self.cid,
                    "changes": {"enabled": 1},
                }
            ]
        )
        self.assertEqual(result["actions"], 0)
        self.assertIn("Connecte d’abord", result["message"])

    def test_schedule_retains_timezone_and_cannot_mark_rights_verified(self):
        vid = self.video()
        result = self.act(
            [
                {
                    "type": "video_update",
                    "video_id": vid,
                    "changes": {"post_at": "2026-10-25T18:00:00+01:00"},
                }
            ]
        )
        self.assertEqual(result["actions"], 1)
        self.assertEqual(self.store.video(vid)["post_at"], "2026-10-25T17:00:00+00:00")
        original = self.store.video(vid)
        result = self.act(
            [
                {
                    "type": "video_update",
                    "video_id": vid,
                    "changes": {
                        "rights_status": "verified",
                        "quality_status": "verified",
                        "title": "Untrusted override",
                    },
                }
            ]
        )
        self.assertEqual(result["actions"], 0)
        self.assertEqual(self.store.video(vid), original)

    def test_publish_is_blocked_and_failed_actions_do_not_claim_success(self):
        vid = self.video()
        self.app.config["PREVIEW"] = False
        result = self.act([{"type": "production", "video_id": vid, "stage": "publish"}])
        self.assertEqual(result["actions"], 0)
        self.assertIn("Action bloquée", result["message"])
        self.assertIn("Droits de réutilisation", result["message"])
        self.assertNotIn("Opération déjà terminée", result["message"])
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])
        self.assertEqual(result["attachments"][0]["id"], vid)

    def test_publish_queue_is_not_reported_as_uploaded_and_requires_existing_approval(
        self,
    ):
        vid = self.video()
        self.app.config["PREVIEW"] = False
        with self.store.db() as c:
            c.execute(
                "UPDATE delamain_projects SET yt_refresh_token='fixture',autonomy='manual' WHERE id=?",
                (self.cid,),
            )
        self.store.update(
            "studio_videos",
            vid,
            dict(
                status="ready",
                video_path="fixture.mp4",
                thumb_path="fixture.jpg",
                render_digest="digest",
                rights_status="verified",
                quality_status="verified",
                event_at=now(),
            ),
        )
        result = self.act([{"type": "production", "video_id": vid, "stage": "publish"}])
        self.assertEqual(result["actions"], 0)
        self.assertIn("Validation humaine", result["message"])
        self.store.update("studio_videos", vid, {"approved_digest": "digest"})
        result = self.act([{"type": "production", "video_id": vid, "stage": "publish"}])
        self.assertEqual(result["actions"], 1)
        self.assertIn("mise en file", result["message"])
        self.assertEqual(self.store.video(vid)["status"], "ready")
        self.assertEqual(
            self.store.rows("SELECT kind FROM studio_jobs"), [{"kind": "publish"}]
        )
        result = self.act([{"type": "production", "video_id": vid, "stage": "approve"}])
        self.assertEqual(result["actions"], 0)

    def test_preview_blocks_generation_and_zero_budget_is_enforced_by_the_route(self):
        vid = self.video()
        result = self.act([{"type": "production", "video_id": vid, "stage": "render"}])
        self.assertEqual(result["actions"], 0)
        self.app.config["PREVIEW"] = False
        ch = self.store.channel(self.cid)
        self.store.update_channel(self.cid, {"budget": 0}, ch["revision"])
        result = self.act([{"type": "production", "video_id": vid, "stage": "script"}])
        self.assertEqual(result["actions"], 0)
        self.assertIn("budget", result["message"])
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])

    def test_task_edit_done_and_delete_work_for_collaborator(self):
        result = self.act(
            [
                {
                    "type": "task",
                    "title": "Check the sources",
                    "channel_id": self.cid,
                    "assignee": "collegue",
                    "due_at": "2026-10-06T18:00:00+02:00",
                }
            ],
            user="collegue",
        )
        self.assertEqual(result["actions"], 1)
        task = self.store.rows("SELECT * FROM studio_tasks")[0]
        self.assertEqual(task["assignee"], "collegue")
        result = self.act(
            [{"type": "task_update", "task_id": task["id"], "changes": {"done": True}}],
            user="collegue",
        )
        self.assertEqual(result["actions"], 1)
        self.assertEqual(
            self.store.one("SELECT done FROM studio_tasks WHERE id=?", (task["id"],))[
                "done"
            ],
            1,
        )
        result = self.act(
            [{"type": "task_delete", "task_id": task["id"]}], user="collegue"
        )
        self.assertEqual(result["actions"], 1)
        self.assertEqual(self.store.rows("SELECT * FROM studio_tasks"), [])

    def test_stale_model_context_does_not_overwrite_a_teammate(self):
        def change_channel():
            ch = self.store.channel(self.cid)
            self.store.update_channel(self.cid, {"post_time": "21:00"}, ch["revision"])

        result = self.act(
            [
                {
                    "type": "channel_update",
                    "channel_id": self.cid,
                    "changes": {"post_time": "19:00"},
                }
            ],
            before=change_channel,
        )
        self.assertEqual(result["actions"], 0)
        self.assertEqual(self.store.channel(self.cid)["post_time"], "21:00")

    def test_show_thumbnail_is_a_real_attachment_without_modification(self):
        vid = self.video()
        before = self.store.video(vid)
        result = self.act([{"type": "show_video", "video_id": vid}])
        self.assertEqual(
            result["attachments"],
            [{"kind": "video", "id": vid, "title": before["title"]}],
        )
        self.assertEqual(self.store.video(vid), before)
        client = self.app.test_client()
        messages = client.get("/api/studio/chat").json["messages"]
        self.assertEqual(messages[-1]["attachments"], result["attachments"])
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])

    def test_replay_uses_saved_results_and_does_not_duplicate_creations(self):
        actions = [
            {"type": "channel_create", "name": "Replay channel", "format": "pov"},
            {"type": "task", "title": "Replay task"},
        ]
        job = uid()
        first = self.act(actions, job=job)
        with patch(
            "services.ai.chat_json",
            side_effect=AssertionError("Provider must not be called again"),
        ):
            second = respond(self.store, "Same mission", "Drylow", job, "drylow")
        self.assertEqual(first, second)
        self.assertEqual(
            len([c for c in self.store.channels() if c["name"] == "Replay channel"]), 1
        )
        self.assertEqual(len(self.store.rows("SELECT * FROM studio_tasks")), 1)
        self.assertEqual(len(self.store.rows("SELECT * FROM studio_chat")), 1)
        with self.assertRaises(PermissionError):
            respond(self.store, "Other person", "Kanye", job, "collegue")

    def test_interrupted_action_is_not_blindly_repeated(self):
        job = uid()
        initialize(self.store)
        with self.store.db() as c:
            c.execute(
                "INSERT INTO studio_agent_steps(job_id,step,state) VALUES(?,0,'running')",
                (job,),
            )
        result = self.act([{"type": "task", "title": "Never duplicate this"}], job=job)
        self.assertEqual(result["actions"], 0)
        self.assertIn("vérifie l’état", result["message"])
        self.assertEqual(self.store.rows("SELECT * FROM studio_tasks"), [])

    def test_chat_identity_comes_from_session_not_json(self):
        client = self.app.test_client()
        boot = client.get("/api/studio/bootstrap").json
        self.app.config["PREVIEW"] = False
        r = client.post(
            "/api/studio/chat",
            json={
                "message": "Show the thumbnails",
                "user_id": "collegue",
                "actor": "Kanye",
            },
            headers={"X-CSRF-Token": boot["csrf"]},
        )
        self.assertEqual(r.status_code, 202)
        payload = json.loads(
            self.store.one(
                "SELECT payload FROM studio_jobs WHERE id=?", (r.json["job_id"],)
            )["payload"]
        )
        self.assertEqual(payload["user_id"], "drylow")

    def test_retired_channel_history_is_preserved_but_not_exposed_or_runnable(self):
        vid = self.video()
        client = self.app.test_client()
        csrf = client.get("/api/studio/bootstrap").json["csrf"]
        r = client.post(
            "/api/studio/tasks",
            json={"title": "Related task", "video_id": vid},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(r.status_code, 201)
        jid = self.store.enqueue("render", vid)
        c = self.store.channel(self.cid)
        self.store.retire_channel(self.cid, c["revision"])
        self.assertIsNone(self.store.channel(self.cid))
        self.assertIsNone(self.store.video(vid))
        self.assertTrue(
            self.store.one(
                "SELECT 1 AS exists_flag FROM studio_videos WHERE id=?", (vid,)
            )
        )
        self.assertEqual(
            self.store.one("SELECT status FROM studio_jobs WHERE id=?", (jid,))[
                "status"
            ],
            "cancelled",
        )
        self.assertEqual(overview(self.store)["tasks"], [])
        self.assertEqual(overview(self.store)["jobs"], [])
        self.assertEqual(client.get(f"/media/{vid}/thumbnail").status_code, 400)
        result = self.act([{"type": "production", "video_id": vid, "stage": "render"}])
        self.assertEqual(result["actions"], 0)

    def test_ring_dispatch_stays_retired_across_seed_and_restart(self):
        self.assertEqual(len(self.store.channels()), 7)
        self.assertFalse(
            any(c["name"] == "Ring Dispatch" for c in self.store.channels())
        )
        seed(self.store)
        restarted = create_app(self.config).extensions["studio_store"]
        self.assertEqual(len(restarted.channels()), 7)
        raw = restarted.one(
            "SELECT retired,paused,enabled FROM studio_channels WHERE key='boxing_en'"
        )
        self.assertEqual(raw, {"retired": 1, "paused": 1, "enabled": 0})

    def test_shared_settings_and_job_cancellation_keep_account_permissions(self):
        result = self.act(
            [{"type": "studio_settings", "changes": {"paused": True}}], user="collegue"
        )
        self.assertEqual(result["actions"], 0)
        self.assertEqual(self.store.settings()["paused"], 0)
        result = self.act([{"type": "studio_settings", "changes": {"paused": True}}])
        self.assertEqual(result["actions"], 1)
        vid = self.video()
        jid = self.store.enqueue("render", vid)
        result = self.act([{"type": "job_cancel", "job_id": jid}])
        self.assertEqual(result["actions"], 1)
        self.assertEqual(
            self.store.one("SELECT status FROM studio_jobs WHERE id=?", (jid,))[
                "status"
            ],
            "cancelled",
        )

    def test_radar_sources_use_owner_and_public_url_validation(self):
        create = {
            "type": "news_feed_create",
            "channel_id": self.cid,
            "name": "New trusted source",
            "url": "https://example.org/feed",
        }
        result = self.act([create], user="collegue")
        self.assertEqual(result["actions"], 0)
        result = self.act([{**create, "url": "https://127.0.0.1/feed"}])
        self.assertEqual(result["actions"], 0)
        result = self.act([create])
        self.assertEqual(result["actions"], 1)
        feed = self.store.one(
            "SELECT * FROM studio_news_feeds WHERE name='New trusted source'"
        )
        result = self.act(
            [{"type": "news_feed_update", "feed_id": feed["id"], "enabled": False}]
        )
        self.assertEqual(result["actions"], 1)
        self.assertEqual(
            self.store.one(
                "SELECT enabled FROM studio_news_feeds WHERE id=?", (feed["id"],)
            )["enabled"],
            0,
        )
        result = self.act([{"type": "news_feed_delete", "feed_id": feed["id"]}])
        self.assertEqual(result["actions"], 1)
        result = self.act(
            [
                {
                    "type": "news_config",
                    "channel_id": self.cid,
                    "enabled": True,
                    "interval_minutes": 60,
                }
            ]
        )
        self.assertEqual(result["actions"], 0)


if __name__ == "__main__":
    unittest.main()
