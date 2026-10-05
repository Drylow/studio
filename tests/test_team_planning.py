"""Team transfers, optimistic concurrency, stable cadence and personal exports."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from studio.web import create_app
from studio.store import Store
from studio.domain import channel_summary
from studio.planning import planning
from studio.schedule import TZ, cadence_slots


class TeamPlanningTests(unittest.TestCase):
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
        self.client = self.app.test_client()
        self.csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        self.ch = self.store.channels()[0]
        self.store.update_channel(
            self.ch["id"],
            {"cadence_anchor": "2026-10-05", "post_time": "18:00", "cadence_days": "2"},
            self.ch["revision"],
        )
        self.at = datetime(2026, 10, 5, 12, tzinfo=TZ)

    def tearDown(self):
        self.tmp.cleanup()

    def assign(self, member, revision=None, client=None, csrf=None):
        return (client or self.client).patch(
            f"/api/studio/channels/{self.ch['id']}/responsibility",
            json={
                "responsible_id": member,
                "revision": (
                    revision
                    if revision is not None
                    else self.store.channel(self.ch["id"])["revision"]
                ),
            },
            headers={"X-CSRF-Token": csrf or self.csrf},
        )

    def reserve(self, day="2026-10-05T18:00:00+02:00", cid=None):
        vid = self.store.add_video(
            dict(
                channel_id=cid or self.ch["id"],
                title="Team planning analysis",
                minutes=5,
                cost_cap=1,
            )
        )
        self.store.update("studio_videos", vid, {"post_at": day})
        return vid

    def test_transfer_preserves_rules_videos_and_explicit_task_assignees(self):
        self.reserve()
        self.client.post(
            "/api/studio/tasks",
            json={"title": "Review", "channel_id": self.ch["id"], "assignee": "drylow"},
            headers={"X-CSRF-Token": self.csrf},
        )
        original = self.store.channel(self.ch["id"])
        videos, tasks = self.store.videos(), self.store.rows(
            "SELECT * FROM studio_tasks"
        )
        self.assertEqual(self.assign("drylow").status_code, 200)
        self.assertEqual(self.assign("collegue").status_code, 200)
        updated = self.store.channel(self.ch["id"])
        self.assertEqual(updated["responsible_id"], "collegue")
        for key in original:
            if key not in {"responsible_id", "revision", "updated_at"}:
                self.assertEqual(updated[key], original[key], key)
        self.assertEqual(self.store.videos(), videos)
        self.assertEqual(self.store.rows("SELECT * FROM studio_tasks"), tasks)
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])
        self.assertEqual(self.assign(None).status_code, 200)
        self.assertIsNone(self.store.channel(self.ch["id"])["responsible_id"])

    def test_stale_transfer_cannot_overwrite_other_person(self):
        revision = self.store.channel(self.ch["id"])["revision"]
        self.assertEqual(self.assign("drylow", revision).status_code, 200)
        self.assertEqual(self.assign("collegue", revision).status_code, 409)
        self.assertEqual(self.store.channel(self.ch["id"])["responsible_id"], "drylow")

    def test_unknown_or_malformed_member_is_rejected(self):
        for member in ["missing", "", 0, False, [], {}]:
            with self.subTest(member=member):
                self.assertEqual(self.assign(member).status_code, 400)
        self.assertIsNone(self.store.channel(self.ch["id"])["responsible_id"])

    def test_editor_can_transfer_and_csrf_is_required(self):
        other = self.app.test_client()
        other.get("/api/studio/bootstrap")
        with other.session_transaction() as session:
            from studio.security import issue

            with self.app.app_context():
                issue(self.store, "collegue", container=session)
        csrf = other.get("/api/studio/bootstrap").json["csrf"]
        self.assertEqual(
            self.assign("collegue", client=other, csrf=csrf).status_code, 200
        )
        response = other.patch(
            f"/api/studio/channels/{self.ch['id']}/responsibility",
            json={
                "responsible_id": None,
                "revision": self.store.channel(self.ch["id"])["revision"],
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_restart_and_migration_preserve_team_and_anchor(self):
        self.assign("collegue")
        original = self.store.channel(self.ch["id"])
        self.store.migrate()
        self.store.migrate()
        restarted = create_app(self.config).extensions["studio_store"]
        self.assertEqual(restarted.channel(self.ch["id"]), original)
        self.assertTrue(all(c["cadence_anchor"] for c in restarted.channels()))
        self.assertTrue(
            all(c["responsible_id"] is None for c in restarted.channels()[1:])
        )

    def test_legacy_schema_gets_nullable_assignment_without_data_loss(self):
        path = Path(self.tmp.name) / "legacy.db"
        legacy = Store(path)
        legacy.migrate()
        with legacy.db() as c:
            c.execute("ALTER TABLE studio_channels DROP COLUMN responsible_id")
            c.execute("ALTER TABLE studio_channels DROP COLUMN cadence_anchor")
        app = create_app({**self.config, "DB_PATH": path})
        channels = app.extensions["studio_store"].channels()
        self.assertEqual(len(channels), 7)
        self.assertTrue(
            all(c["responsible_id"] is None and c["cadence_anchor"] for c in channels)
        )

    def test_personal_agenda_follows_transfer_without_new_jobs(self):
        self.reserve()
        self.assign("drylow")
        mine = self.client.get("/api/studio/planning?start=2026-10-05&scope=mine").json
        self.assertEqual({s["channel_id"] for s in mine["slots"]}, {self.ch["id"]})
        self.assertEqual(len(mine["slots"]), 4)
        self.assign("collegue")
        self.assertEqual(
            self.client.get("/api/studio/planning?start=2026-10-05&scope=mine").json[
                "slots"
            ],
            [],
        )
        other = self.client.get(
            "/api/studio/planning?start=2026-10-05&scope=collegue"
        ).json
        self.assertEqual(len(other["slots"]), 4)
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])

    def test_reserved_video_replaces_suggestion_and_reports_real_blockers(self):
        vid = self.reserve()
        self.assign("drylow")
        result = planning(self.store, "2026-10-05", scope="drylow", at=self.at)
        actual = [s for s in result["slots"] if s["kind"] == "reserved"]
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]["video_id"], vid)
        self.assertEqual(actual[0]["state"], "Bloquée")
        self.assertIn("Chaîne YouTube à connecter", actual[0]["blockers"])
        self.assertIn("Contrôle du rendu à terminer", actual[0]["blockers"])
        self.assertEqual(len(result["slots"]), 4)
        self.assertEqual(
            {s["state"] for s in result["slots"] if s["kind"] == "suggestion"},
            {"À programmer"},
        )

    def test_pause_is_visible_without_generating_a_video(self):
        self.assign("drylow")
        self.store.update_channel(
            self.ch["id"], {"paused": 1}, self.store.channel(self.ch["id"])["revision"]
        )
        result = planning(self.store, "2026-10-05", scope="drylow")
        self.assertEqual({s["state"] for s in result["slots"]}, {"En pause"})
        self.assertEqual(self.store.videos(), [])

    def test_reserved_second_autumn_hour_fills_one_cadence_slot(self):
        self.assign("drylow")
        self.store.update_channel(
            self.ch["id"],
            {"cadence_anchor": "2026-10-25", "post_time": "02:30", "cadence_days": "1"},
            self.store.channel(self.ch["id"])["revision"],
        )
        self.reserve("2026-10-25T02:30:00+01:00")
        result = planning(self.store, "2026-10-25", 1, "drylow", at=self.at)
        self.assertEqual(len(result["slots"]), 1)
        self.assertEqual(result["slots"][0]["kind"], "reserved")

    def test_plan_query_limits_and_unknown_scope(self):
        for query in [
            "start=2026-02-31",
            "start=bad",
            "days=0",
            "days=32",
            "days=bad",
            "scope=missing",
        ]:
            self.assertEqual(
                self.client.get("/api/studio/planning?" + query).status_code, 400, query
            )
        self.assertEqual(
            self.client.get("/api/studio/planning?scope=unassigned").status_code, 200
        )
        unauth_app = create_app({**self.config, "PREVIEW": False})
        self.assertEqual(
            unauth_app.test_client().get("/api/studio/planning").status_code, 401
        )

    def test_ics_exports_only_selected_person_and_follows_transfer(self):
        self.reserve()
        other = self.store.channels()[1]
        self.reserve(cid=other["id"])
        self.assign("drylow")
        export = self.client.get(
            "/api/studio/calendar.ics?month=2026-10&scope=mine"
        ).text
        self.assertEqual(export.count("BEGIN:VEVENT"), 1)
        self.assertIn(self.ch["name"], export)
        self.assertNotIn(other["name"], export)
        self.assign("collegue")
        export = self.client.get(
            "/api/studio/calendar.ics?month=2026-10&scope=mine"
        ).text
        self.assertNotIn("BEGIN:VEVENT", export)
        self.assertEqual(
            self.client.get(
                "/api/studio/calendar.ics?month=2026-10&scope=missing"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.get(
                f"/api/studio/calendar.ics?month=2026-10&scope=collegue&channel_id={other['id']}"
            ).text.count("BEGIN:VEVENT"),
            0,
        )

    def test_anchor_validation_is_atomic(self):
        original = self.store.channel(self.ch["id"])
        response = self.client.patch(
            f"/api/studio/channels/{self.ch['id']}",
            json={
                "revision": original["revision"],
                "cadence_anchor": "2026-02-31",
                "post_time": "20:00",
            },
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.channel(self.ch["id"]), original)


class CadenceTests(unittest.TestCase):
    def slots(self, start, end, cadence="2", anchor="2026-10-05", hour="18:00"):
        return list(
            cadence_slots(
                dict(cadence_days=cadence, cadence_anchor=anchor, post_time=hour),
                datetime.fromisoformat(start).replace(tzinfo=TZ),
                datetime.fromisoformat(end).replace(tzinfo=TZ),
            )
        )

    def test_two_day_and_weekly_rhythm_stays_anchored(self):
        slots = self.slots("2026-10-06", "2026-10-12")
        self.assertEqual([s.day for s in slots], [7, 9, 11])
        self.assertEqual(
            [s.day for s in self.slots("2026-10-06", "2026-10-20", "7")], [12, 19]
        )

    def test_half_day_rhythm_and_future_anchor(self):
        slots = self.slots("2026-10-05", "2026-10-07", "0.5")
        self.assertEqual([(s.day, s.hour) for s in slots], [(5, 18), (6, 6), (6, 18)])
        self.assertEqual(self.slots("2026-10-01", "2026-10-04"), [])

    def test_dst_wall_time_and_missing_spring_hour(self):
        slots = self.slots("2026-10-24", "2026-10-27", "1", "2026-10-24")
        self.assertEqual([s.hour for s in slots], [18, 18, 18])
        self.assertEqual(
            (
                slots[1].astimezone(timezone.utc) - slots[0].astimezone(timezone.utc)
            ).total_seconds(),
            25 * 3600,
        )
        slots = self.slots("2026-03-28", "2026-03-31", "1", "2026-03-28", "02:30")
        self.assertEqual([s.day for s in slots], [28, 30])

    def test_autumn_ambiguous_hour_occurs_once(self):
        slots = self.slots("2026-10-25", "2026-10-26", "1", "2026-10-25", "02:30")
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0].astimezone(timezone.utc).hour, 0)

    def test_stock_coverage_uses_same_anchor(self):
        at = datetime(2026, 10, 6, 12, tzinfo=TZ)
        c = dict(
            id=1,
            format="history",
            autonomy="auto",
            cadence_days="2",
            cadence_anchor="2026-10-05",
            post_time="18:00",
        )
        v = dict(
            id="x",
            channel_id=1,
            status="scheduled",
            quality_status="verified",
            rights_status="verified",
            video_path="v",
            thumb_path="t",
            render_digest="hash",
            post_at="2026-10-07T18:00:00+02:00",
        )
        result = channel_summary(c, [v], at)
        self.assertEqual(result["days_ahead"], 1.2)
        # A reservation in the second autumn occurrence fills the same wall slot.
        c.update(cadence_days="1", cadence_anchor="2026-10-25", post_time="02:30")
        v["post_at"] = "2026-10-25T02:30:00+01:00"
        result = channel_summary(c, [v], datetime(2026, 10, 25, 0, tzinfo=TZ))
        self.assertGreater(result["days_ahead"], 0)


if __name__ == "__main__":
    unittest.main()
