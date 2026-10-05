"""Personal diagnostics, concurrent shared routines and real calendar exports."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio.control import calendar_export, create_routine, diagnostics
from studio.store import Conflict, now, uid
from studio.web import create_app


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = dict(
            TESTING=True,
            PREVIEW=True,
            MFA_REQUIRED=False,
            SECRET_KEY="test",
            DB_PATH=Path(self.tmp.name) / "studio.db",
            WORKER_ENABLED=False,
            IMPORT_PRODUCTIONS=False,
        )
        self.app = create_app(self.config)
        self.store = self.app.extensions["studio_store"]
        self.client = self.app.test_client()
        self.csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        self.ch = self.store.channels()[0]

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, path, body):
        return self.client.post(
            "/api/studio" + path, json=body, headers={"X-CSRF-Token": self.csrf}
        )

    def task(self):
        return self.post(
            "/tasks",
            dict(
                title="Review the facts",
                channel_id=self.ch["id"],
                due_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            ),
        ).json["id"]

    def video(self, cid=None, title="A sourced analysis"):
        return self.store.add_video(
            dict(channel_id=cid or self.ch["id"], title=title, minutes=5, cost_cap=1)
        )

    def test_alert_reads_are_personal_and_changed_or_resolved_causes_reappear(self):
        tid = self.task()
        alert = next(
            a
            for a in self.client.get("/api/studio/control").json["alerts"]
            if a["key"] == f"task:{tid}:due"
        )
        self.assertEqual(
            self.post(
                f"/control/alerts/{alert['key']}/read",
                {"fingerprint": alert["fingerprint"]},
            ).status_code,
            200,
        )
        current = diagnostics(self.store, "drylow", preview=True)
        self.assertTrue(
            next(a for a in current["alerts"] if a["key"] == alert["key"])["read"]
        )
        colleague = diagnostics(self.store, "collegue", preview=True)
        self.assertFalse(
            next(a for a in colleague["alerts"] if a["key"] == alert["key"])["read"]
        )
        self.store.update("studio_tasks", tid, {"title": "Review the updated facts"})
        current = diagnostics(self.store, "drylow", preview=True)
        self.assertFalse(
            next(a for a in current["alerts"] if a["key"] == alert["key"])["read"]
        )
        self.store.update("studio_tasks", tid, {"done": 1})
        self.assertFalse(
            any(
                a["key"] == alert["key"]
                for a in diagnostics(self.store, "drylow")["alerts"]
            )
        )

    def test_changed_alert_or_missing_csrf_cannot_be_marked_read(self):
        alert = self.client.get("/api/studio/control").json["alerts"][0]
        path = f"/api/studio/control/alerts/{alert['key']}/read"
        self.assertEqual(
            self.client.post(
                path, json={"fingerprint": alert["fingerprint"]}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                path.removeprefix("/api/studio"), {"fingerprint": "obsolete"}
            ).status_code,
            409,
        )
        self.assertEqual(self.store.rows("SELECT * FROM studio_alert_reads"), [])

    def test_missing_worker_is_an_incident_only_when_expected_and_not_in_preview(self):
        self.assertFalse(
            any(
                a["key"] == "system:worker"
                for a in diagnostics(self.store, "drylow")["alerts"]
            )
        )
        with self.store.db() as c:
            c.execute(
                "UPDATE studio_news_config SET enabled=1 WHERE channel_id=?",
                (self.ch["id"],),
            )
            c.execute(
                "UPDATE studio_channels SET paused=1 WHERE project_id=?",
                (self.ch["id"],),
            )
        self.assertFalse(
            any(
                a["key"] == "system:worker"
                for a in diagnostics(self.store, "drylow")["alerts"]
            )
        )
        self.store.enqueue("news_scan", payload={"channel_id": self.ch["id"]})
        self.assertTrue(
            any(
                a["key"] == "system:worker"
                for a in diagnostics(self.store, "drylow")["alerts"]
            )
        )
        self.assertFalse(
            any(
                a["key"] == "system:worker"
                for a in diagnostics(self.store, "drylow", preview=True)["alerts"]
            )
        )
        with self.store.db() as c:
            c.execute("UPDATE studio_worker SET heartbeat=? WHERE id=1", (now(),))
        self.assertFalse(
            any(
                a["key"] == "system:worker"
                for a in diagnostics(self.store, "drylow")["alerts"]
            )
        )

    def test_schedule_task_and_source_incidents_provide_precise_actions(self):
        vid = self.video()
        self.store.update(
            "studio_videos",
            vid,
            {
                "status": "scheduled",
                "post_at": (
                    datetime.now(timezone.utc) - timedelta(minutes=5)
                ).isoformat(),
            },
        )
        tid = self.task()
        with self.store.db() as c:
            c.execute(
                "UPDATE studio_news_feeds SET error='Flux inaccessible' WHERE id=(SELECT id FROM studio_news_feeds LIMIT 1)"
            )
        alerts = diagnostics(self.store, "drylow", preview=True)["alerts"]
        a = next(a for a in alerts if a["key"] == f"video:{vid}:schedule")
        self.assertEqual(a["level"], "critical")
        self.assertIn("Créneau dépassé", a["message"])
        self.assertEqual(a["action"]["video_id"], vid)
        self.assertTrue(any(a["action"].get("task_id") == tid for a in alerts))
        self.assertTrue(
            any(
                a["category"] == "news" and "Configurer le radar" in a["help"]
                for a in alerts
            )
        )

    def test_failed_job_is_superseded_and_diagnostics_do_not_expose_credentials(self):
        marker = "test-private-provider-value"
        jid = self.store.enqueue("news_scan", payload={"channel_id": self.ch["id"]})
        with self.store.db() as c:
            c.execute(
                "UPDATE studio_jobs SET status='failed',error=? WHERE id=?",
                (marker, jid),
            )
        with patch.dict(
            os.environ, {"AI_API_KEY": marker, "NEWS_WORKER_TOKEN": marker}
        ):
            output = diagnostics(self.store, "drylow", preview=True)
            self.assertNotIn(marker, json.dumps(output))
            self.assertTrue(any(a["key"] == f"job:{jid}" for a in output["alerts"]))
        self.store.enqueue("news_scan", payload={"channel_id": self.ch["id"]})
        self.assertFalse(
            any(
                a["key"] == f"job:{jid}"
                for a in diagnostics(self.store, "drylow")["alerts"]
            )
        )

    def routine(self, **extra):
        return dict(
            template="research",
            channel_id=self.ch["id"],
            assignee="collegue",
            due_at="",
            request_key=uid(),
            **extra,
        )

    def test_two_users_and_request_retries_create_one_open_routine(self):
        first, second = self.routine(), self.routine()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda b: create_routine(self.store, b, "Team"), [first, second]
                )
            )
        self.assertEqual(results[0]["task_ids"], results[1]["task_ids"])
        self.assertEqual(sum(r["created"] for r in results), 1)
        self.assertEqual(len(self.store.rows("SELECT * FROM studio_tasks")), 4)
        self.assertFalse(create_routine(self.store, first, "Team")["created"])
        with self.store.db() as c:
            c.execute("UPDATE studio_tasks SET done=1")
        self.assertTrue(create_routine(self.store, self.routine(), "Team")["created"])
        self.assertEqual(len(self.store.rows("SELECT * FROM studio_tasks")), 8)
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])

    def test_routine_rejects_changed_request_wrong_channel_and_unknown_assignee(self):
        b = self.routine()
        create_routine(self.store, b, "Owner")
        with self.assertRaises(Conflict):
            create_routine(self.store, dict(b, template="weekly"), "Owner")
        other = self.store.channels()[1]
        foreign_vid = self.video(other["id"])
        for changes in [
            {"video_id": foreign_vid},
            {"assignee": "unknown"},
            {"assignee": ["drylow"]},
            {"due_at": "2026-10-25T02:30:00"},
            {"channel_id": "bad"},
        ]:
            r = self.post("/routines", dict(self.routine(), **changes))
            self.assertEqual(r.status_code, 400, changes)
        self.assertEqual(len(self.store.rows("SELECT * FROM studio_tasks")), 4)

    def test_collaborator_can_add_routine_without_changing_review_or_rights(self):
        vid = self.video()
        c = self.app.test_client()
        with c.session_transaction() as session:
            from studio.security import issue

            with self.app.app_context():
                issue(self.store, "collegue", container=session)
        csrf = c.get("/api/studio/bootstrap").json["csrf"]
        response = c.post(
            "/api/studio/routines",
            json=self.routine(video_id=vid),
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            all(
                t["video_id"] == vid
                for t in self.store.rows("SELECT * FROM studio_tasks")
            )
        )
        self.assertEqual(self.store.video(vid)["rights_status"], "unknown")
        self.assertEqual(self.store.video(vid)["quality_status"], "unknown")
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])

    def test_calendar_preserves_dst_month_scope_uids_and_escapes_event_text(self):
        vid = self.video(title="A; B, é" * 20 + "\r\nBEGIN:VEVENT")
        self.store.update(
            "studio_videos",
            vid,
            {"status": "scheduled", "post_at": "2026-10-25T02:30:00+01:00"},
        )
        boundary = self.video(title="Paris November")
        self.store.update(
            "studio_videos", boundary, {"post_at": "2026-10-31T23:30:00+00:00"}
        )
        other = self.video(self.store.channels()[1]["id"], title="Another channel")
        self.store.update(
            "studio_videos", other, {"post_at": "2026-10-12T11:00:00+00:00"}
        )
        content = calendar_export(self.store, "2026-10", self.ch["id"])
        self.assertIn("DTSTART:20261025T013000Z", content)
        self.assertEqual(content.split("\r\n").count("BEGIN:VEVENT"), 1)
        self.assertNotIn("Paris November", content)
        self.assertNotIn("Another channel", content)
        self.assertIn("\\;", content)
        self.assertIn("\\,", content)
        self.assertIn("\\nBEGIN:VEVENT", content)
        self.assertTrue(all(len(line.encode()) <= 75 for line in content.split("\r\n")))
        self.assertIn(f"UID:video-{vid}@edgerunners.studio", content)
        self.store.update("studio_videos", vid, {"title": "Updated title"})
        self.assertIn(
            f"UID:video-{vid}@edgerunners.studio",
            calendar_export(self.store, "2026-10", self.ch["id"]),
        )
        self.store.update("studio_videos", vid, {"status": "reported"})
        self.assertNotIn(
            f"UID:video-{vid}", calendar_export(self.store, "2026-10", self.ch["id"])
        )

    def test_export_requires_authentication_and_valid_filters(self):
        r = self.client.get("/api/studio/calendar.ics?month=2026-10")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "text/calendar")
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        for suffix in [
            "month=2026-13",
            "month=invalid",
            "month=2026-10&channel_id=0",
            "month=2026-10&channel_id=bad",
        ]:
            self.assertEqual(
                self.client.get("/api/studio/calendar.ics?" + suffix).status_code, 400
            )
        app = create_app(dict(self.config, PREVIEW=False))
        c = app.test_client()
        for path in [
            "/api/studio/control",
            "/api/studio/routines",
            "/api/studio/calendar.ics?month=2026-10",
        ]:
            self.assertEqual(c.get(path).status_code, 401)


if __name__ == "__main__":
    unittest.main()
