"""Dated news research must stay distinct from facts, production and publication."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from studio.web import create_app
from studio.store import now, uid, Conflict
from studio.newsroom import parse_feed, public_url, scan, prepare, tick, initialize


class FeedTests(unittest.TestCase):
    def test_rss_dates_tracking_links_and_html_are_normalized(self):
        rows = parse_feed(b"""<rss><channel><item><title>A &amp; B</title>
          <link>https://example.org/story/?utm_source=reader&amp;id=1</link>
          <pubDate>Mon, 05 Oct 2026 18:00:00 +0200</pubDate>
          <description>&lt;p&gt;A dated report&lt;/p&gt;</description></item>
          <item><title>Undated</title><link>https://example.org/old</link></item>
          </channel></rss>""")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["published"], "2026-10-05T16:00:00+00:00")
        self.assertEqual(rows[0]["summary"], "A dated report")
        self.assertEqual(rows[0]["url"], "https://example.org/story?id=1")

    def test_atom_and_xml_entity_rejection(self):
        rows = parse_feed(
            b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>A report</title>
        <link href="https://example.org/news"/><published>2026-10-05T10:00:00Z</published></entry></feed>"""
        )
        self.assertEqual(rows[0]["title"], "A report")
        for raw in [
            b'<!DOCTYPE rss [<!ENTITY a "secret">]><rss/>',
            "<!DOCTYPE rss><rss/>".encode("utf-16"),
        ]:
            with self.assertRaises(ValueError):
                parse_feed(raw)

    def test_sources_cannot_read_credentials_or_internal_destinations(self):
        for url in [
            "http://example.org/rss",
            "https://user:password@example.org/rss",
            "https://127.0.0.1/rss",
            "https://169.254.169.254/rss",
            "https://localhost/rss",
            "https://site.internal/rss",
            "https://example.org:444/rss",
        ]:
            with self.assertRaises(ValueError, msg=url):
                public_url(url)
        with patch(
            "studio.newsroom.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("10.0.0.1", 443))],
        ):
            with self.assertRaises(ValueError):
                public_url("https://example.org/rss", resolve=True)


class NewsroomTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "PREVIEW": True,
                "SECRET_KEY": "test",
                "DB_PATH": Path(self.tmp.name) / "studio.db",
                "WORKER_ENABLED": False,
                "IMPORT_PRODUCTIONS": False,
            }
        )
        self.client = self.app.test_client()
        self.csrf = self.client.get("/api/studio/bootstrap").json["csrf"]
        self.store = self.app.extensions["studio_store"]
        self.ch = next(c for c in self.store.channels() if c["key"] == "football_en")

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, path, data):
        return self.client.post(
            "/api/studio" + path, json=data, headers={"X-CSRF-Token": self.csrf}
        )

    def item(self, days=0):
        row = {
            "title": "A genuinely new report",
            "url": "https://example.org/story",
            "summary": "An unverified feed summary",
            "published": (
                datetime.now(timezone.utc) - timedelta(days=days)
            ).isoformat(),
        }
        with patch("studio.newsroom.fetch_feed", return_value=[row]):
            scan(self.store, self.ch["id"])
        return self.store.one("SELECT * FROM studio_news_items")

    def test_repeat_and_cross_source_scan_do_not_duplicate_exact_story(self):
        def fetch(url):
            return [
                {
                    "title": "Same story!",
                    "url": "https://example.org/" + ("a" if "bbc" in url else "b"),
                    "published": now(),
                    "summary": "Signal only",
                }
            ]

        with patch("studio.newsroom.fetch_feed", side_effect=fetch):
            first = scan(self.store, self.ch["id"])
            second = scan(self.store, self.ch["id"])
        self.assertEqual(first["added"], 1)
        self.assertEqual(second["added"], 0)
        self.assertEqual(
            len(
                json.loads(self.store.one("SELECT * FROM studio_news_items")["sources"])
            ),
            2,
        )
        self.assertEqual(self.store.videos(), [])
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])

    def test_undated_old_and_future_reports_are_not_new_candidates(self):
        rows = [
            {
                "title": "Old",
                "url": "https://example.org/old",
                "published": (
                    datetime.now(timezone.utc) - timedelta(days=5)
                ).isoformat(),
                "summary": "",
            },
            {
                "title": "Future",
                "url": "https://example.org/future",
                "published": (
                    datetime.now(timezone.utc) + timedelta(hours=2)
                ).isoformat(),
                "summary": "",
            },
        ]
        with patch("studio.newsroom.fetch_feed", return_value=rows):
            result = scan(self.store, self.ch["id"])
        self.assertEqual(result["added"], 0)

    def test_two_people_prepare_one_draft_without_treating_rss_as_facts(self):
        item = self.item()
        with ThreadPoolExecutor(max_workers=2) as pool:
            videos = list(
                pool.map(
                    lambda _: prepare(self.store, item["id"], item["revision"], "Crew"),
                    range(2),
                )
            )
        self.assertEqual(videos[0], videos[1])
        self.assertEqual(len(self.store.videos()), 1)
        video = self.store.video(videos[0])
        self.assertEqual(video["status"], "research")
        self.assertEqual(video["notes"], "")
        self.assertEqual(video["script"], "")
        self.assertEqual(video["quality_status"], "unknown")
        self.assertEqual(video["rights_status"], "unknown")
        self.assertEqual(len(video["sources"]), 1)
        self.assertEqual(self.store.rows("SELECT * FROM studio_jobs"), [])

    def test_expiration_blocks_preparation_even_with_old_browser_state(self):
        item = self.item()
        with self.store.db() as c:
            c.execute(
                "UPDATE studio_news_items SET published=? WHERE id=?",
                (
                    (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
                    item["id"],
                ),
            )
        self.assertEqual(
            self.post(
                "/news/items/" + item["id"] + "/prepare", {"revision": item["revision"]}
            ).status_code,
            400,
        )
        self.assertEqual(self.store.videos(), [])

    def test_single_scan_lease_pause_and_partial_failure(self):
        with self.store.db() as c:
            c.execute(
                "INSERT INTO studio_news_locks VALUES(?,?,?)",
                (
                    self.ch["id"],
                    "other",
                    (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
                ),
            )
        with patch("studio.newsroom.fetch_feed") as external:
            with self.assertRaises(Conflict):
                scan(self.store, self.ch["id"])
            external.assert_not_called()
        with self.store.db() as c:
            c.execute("DELETE FROM studio_news_locks")

        def one(url):
            if "bbc" in url:
                raise OSError("remote secret response")
            return []

        with patch("studio.newsroom.fetch_feed", side_effect=one):
            result = scan(self.store, self.ch["id"])
        self.assertEqual(result["failed_feeds"], 1)
        self.assertNotIn("secret", json.dumps(self.client.get("/api/studio/news").json))
        self.assertEqual(self.store.rows("SELECT * FROM studio_news_locks"), [])

    def test_scheduled_collection_and_pause_respect_server_configuration(self):
        with self.store.db() as c:
            c.execute(
                "UPDATE studio_news_config SET enabled=1 WHERE channel_id=?",
                (self.ch["id"],),
            )
        with patch("studio.newsroom.fetch_feed", return_value=[]) as external:
            tick(self.store)
            tick(self.store)
            self.assertEqual(external.call_count, 2)  # two sources, one pass
            with self.store.db() as c:
                c.execute(
                    "UPDATE studio_news_config SET next_run='' WHERE channel_id=?",
                    (self.ch["id"],),
                )
                c.execute("UPDATE studio_settings SET paused=1")
            tick(self.store)
            self.assertEqual(external.call_count, 2)

    def test_disabling_source_during_download_discards_its_pending_result(self):
        def fetch(url):
            with self.store.db() as c:
                c.execute(
                    "UPDATE studio_news_feeds SET enabled=0,revision=revision+1 WHERE url=?",
                    (url,),
                )
            return [
                {
                    "title": "Stopped source",
                    "url": "https://example.org/stopped",
                    "published": now(),
                    "summary": "",
                }
            ]

        with patch("studio.newsroom.fetch_feed", side_effect=fetch):
            result = scan(self.store, self.ch["id"])
        self.assertEqual(result["added"], 0)
        initialize(self.store)
        self.assertTrue(
            all(
                not f["enabled"]
                for f in self.store.rows(
                    "SELECT * FROM studio_news_feeds WHERE channel_id=?",
                    (self.ch["id"],),
                )
            )
        )

    def test_agent_can_queue_news_work_without_production_or_publication(self):
        item = self.item()
        from studio.agent import respond

        response = {
            "message": "Je prépare la fiche de recherche.",
            "actions": [{"type": "news_prepare", "item_id": item["id"]}],
        }
        with patch("services.ai.chat_json", return_value=response):
            respond(self.store, "Prépare cette info", "Owner", "fixed-news-agent")
            respond(self.store, "Prépare cette info", "Owner", "fixed-news-agent")
        jobs = self.store.rows("SELECT * FROM studio_jobs")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["kind"], "news_prepare")
        from studio.worker import run

        run(self.store, once=True)
        self.assertEqual(len(self.store.videos()), 1)
        self.assertEqual(self.store.videos()[0]["notes"], "")

    def test_already_sourced_video_is_linked_to_newly_discovered_report(self):
        vid = self.store.add_video(
            {
                "channel_id": self.ch["id"],
                "title": "Original analysis",
                "sources": [
                    {
                        "id": "original",
                        "name": "Source",
                        "url": "https://example.org/story?utm_source=old",
                    }
                ],
            }
        )
        item = self.item()
        self.assertEqual(item["status"], "used")
        self.assertEqual(item["video_id"], vid)
        self.assertEqual(prepare(self.store, item["id"], item["revision"], "Crew"), vid)
        self.assertEqual(len(self.store.videos()), 1)

    def test_collaborator_can_prepare_but_cannot_change_sources(self):
        item = self.item()
        c = self.app.test_client()
        with c.session_transaction() as session:
            session["studio_user"] = "collegue"
        csrf = c.get("/api/studio/bootstrap").json["csrf"]
        headers = {"X-CSRF-Token": csrf}
        r = c.post(
            "/api/studio/news/feeds",
            json={
                "channel_id": self.ch["id"],
                "name": "Forbidden",
                "url": "https://example.org/rss",
            },
            headers=headers,
        )
        self.assertEqual(r.status_code, 403)
        r = c.post(
            "/api/studio/news/items/" + item["id"] + "/prepare",
            json={"revision": item["revision"]},
            headers=headers,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.store.video(r.json["video_id"])["status"], "research")

    def test_publication_readiness_explains_specific_steps(self):
        item = self.item()
        vid = prepare(self.store, item["id"], item["revision"], "Crew")
        r = self.client.get("/api/studio/videos/" + vid + "/readiness")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json["ready"])
        checks = {c["key"]: c for c in r.json["checks"]}
        self.assertFalse(checks["research"]["complete"])
        self.assertIn("Script & notes", checks["research"]["help"])
        self.assertFalse(checks["youtube"]["complete"])
        self.assertIn("Chaînes", checks["youtube"]["help"])


if __name__ == "__main__":
    unittest.main()
