"""Cage/Pitch autopilot with fake providers: story choice, facts, script, rights and gates."""

import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio.store import now, uid
from studio.worker import worker_application

ARTICLE = (
    "Ilia Topuria will defend his title against Justin Gaethje at UFC 330 in Madrid on December 12, "
    "the promotion announced on Tuesday. Gaethje said he has waited two years for this chance and "
    "promised a war from the opening bell. Topuria told reporters he expects to finish the fight "
    "inside three rounds. The bout was first rumored in August before talks stalled over the date. "
    "Tickets for the Madrid card sold out within an hour according to the promoter. "
) * 3
QUOTES = [
    "Ilia Topuria will defend his title against Justin Gaethje at UFC 330 in Madrid",
    "Gaethje said he has waited two years for this chance",
    "Topuria told reporters he expects to finish the fight inside three rounds",
    "The bout was first rumored in August before talks stalled over the date",
    "Tickets for the Madrid card sold out within an hour according to the promoter",
]


def plan(words=90, segments=8):
    body = " ".join(["Topuria and Gaethje meet in Madrid, and fans already argue about the result."] * 7)
    narration = " ".join(body.split()[:words])
    return {
        "title": "Topuria vs Gaethje Is Official — Madrid Sold Out",
        "title_options": ["A", "B", "C"],
        "segments": [
            {
                "headline": f"Part {i + 1}",
                "lines": ["Official", "Madrid"],
                "narration": narration,
                "source_ids": ["s1"],
                "fact_ids": ["f1"],
                "people": ["Ilia Topuria"] if i % 2 == 0 else ["Justin Gaethje"],
            }
            for i in range(segments)
        ],
        "description": "The fight is official.",
        "tags": ["UFC", "Topuria", "Gaethje"],
        "pinned_comment": "Who wins?",
        "thumbnail": {
            "line1": "IT'S OFFICIAL",
            "line2": "MADRID WAR",
            "people": ["Ilia Topuria", "Justin Gaethje"],
            "scene": "arena lights",
        },
    }


class Fake:
    def __init__(self, root, *, quotes=QUOTES, problems=None, thumb_ok=True):
        self.root, self.quotes, self.thumb_ok = root, quotes, thumb_ok
        self.problems = list(problems or [])
        self.calls = []

    def chat(self, messages, **kw):
        system = messages[0]["content"] if isinstance(messages[0]["content"], str) else ""
        self.calls.append(system[:40])
        if "Score each headline" in system:
            heads = json.loads(messages[1]["content"])["headlines"]
            return {"items": [{"id": h["id"], "score": 9 if "Topuria" in h["title"] else 3, "why": "x"} for h in heads]}
        if "Extract the verifiable facts" in system:
            return {
                "facts": [{"claim": q, "quote": q, "source_id": "s1", "status": "confirmed"} for q in self.quotes],
                "people": ["Ilia Topuria", "Justin Gaethje"],
                "rumor": False,
            }
        if "YouTube news analysis" in system:
            return plan()
        if "strict fact-checker" in system:
            return {"problems": self.problems.pop(0) if self.problems else []}
        text = messages[0]["content"][0]["text"] if isinstance(messages[0]["content"], list) else ""
        if "Is exactly ONE person" in text:
            return {"ok": True}
        return {"ok": self.thumb_ok, "problem": "texte faux"}

    def fetch(self, url):
        return {"title": "Fight announced", "text": ARTICLE, "words": len(ARTICLE.split())}

    def portraits(self, name):
        return [
            {
                "name": name,
                "title": f"File:{name}.jpg",
                "url": "https://upload.wikimedia.org/x/" + name.replace(" ", "_") + ".jpg",
                "credit": f"Photo: Author / Wikimedia Commons (CC BY 2.0)",
                "rights": {
                    "license": "CC BY 2.0",
                    "license_url": "https://creativecommons.org/licenses/by/2.0",
                    "author": "Author",
                    "evidence_url": "https://commons.wikimedia.org/wiki/File:" + name.replace(" ", "_") + ".jpg",
                    "reviewed_at": now(),
                },
            }
        ]

    def download(self, url, dest):
        from PIL import Image

        Image.new("RGB", (600, 800), (80, 80, 80)).save(dest, "JPEG")

    def image(self, prompt, refs):
        from PIL import Image

        self.prompt = prompt
        out = io.BytesIO()
        Image.new("RGB", (1536, 864), (10, 20, 40)).save(out, "PNG")
        return out.getvalue()

    def build(self, folder, log):
        video = self.root / "work" / "news_brief" / folder.name / "video.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"fake mp4 " + folder.name.encode())
        (folder / "check").mkdir(exist_ok=True)
        (folder / "result.json").write_text(json.dumps({"file": str(video)}))

    def tools(self):
        from studio.autonews import Tools

        return Tools(
            chat=self.chat,
            fetch=self.fetch,
            portraits=self.portraits,
            image=self.image,
            build=self.build,
            download=self.download,
            sheets=lambda tools, folder: [],
            decode=lambda path: None,
        )


class AutonewsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.app = worker_application(
            dict(
                TESTING=True,
                PREVIEW=False,
                SECRET_KEY="fixture",
                DB_PATH=self.root / "studio.db",
                IMPORT_PRODUCTIONS=False,
                DEVELOPMENT_MAINTENANCE_PATH=str(self.root / "maintenance.json"),
            )
        )
        self.store = self.app.extensions["studio_store"]
        self.ch = next(c for c in self.store.channels() if c["key"] == "mma_en")
        with self.store.db() as c:
            c.execute(
                "UPDATE delamain_projects SET autonomy='auto',yt_refresh_token='fixture',yt_channel_id='UCfixture' WHERE id=?",
                (self.ch["id"],),
            )
            c.execute(
                "UPDATE studio_channels SET enabled=1,paused=0,publication_mode='news' WHERE project_id=?",
                (self.ch["id"],),
            )
            c.execute("UPDATE studio_settings SET paused=0 WHERE id=1")
        self.paths = [
            patch("studio.autonews.ROOT", self.root),
            patch("studio.imports.ROOT", self.root),
        ]
        for p in self.paths:
            p.start()
        self.at = datetime.now(timezone.utc)

    def tearDown(self):
        for p in self.paths:
            p.stop()
        self.tmp.cleanup()

    def item(self, title, hours=2):
        iid = uid()
        published = (self.at - timedelta(hours=hours)).isoformat()
        source = [{"id": uid(), "name": "Sherdog", "url": f"https://www.sherdog.com/{iid}", "published": published}]
        with self.store.db() as c:
            c.execute(
                "INSERT INTO studio_news_items(id,channel_id,title,url,published,summary,sources,story_key,seen_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (iid, self.ch["id"], title, source[0]["url"], published, "", json.dumps(source), iid, now()),
            )
        return iid

    def job(self):
        class Job:
            def update(self, progress=None, message=None):
                pass

        return Job()

    def test_hot_story_is_queued_once_and_the_daily_cap_holds(self):
        from studio.autonews import tick

        fake = Fake(self.root)
        hot = self.item("Topuria vs Gaethje official for Madrid")
        self.item("Regional card preview")
        queued = tick(self.store, self.at, tools=fake.tools())
        self.assertEqual(len(queued), 1)
        payload = json.loads(self.store.one("SELECT payload FROM studio_jobs WHERE id=?", (queued[0],))["payload"])
        self.assertEqual(payload["item_id"], hot)
        self.assertEqual(tick(self.store, self.at, tools=fake.tools()), [])
        with self.store.db() as c:
            c.execute("UPDATE studio_jobs SET status='done'")
            for _ in range(2):
                c.execute(
                    "INSERT INTO studio_videos(id,channel_id,title,status,engine_ref,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (uid(), self.ch["id"], "Done", "published", json.dumps({"auto": True}), now(), now()),
                )
        self.assertEqual(tick(self.store, self.at, tools=fake.tools()), [])

    def test_paused_studio_or_manual_channel_queues_nothing(self):
        from studio.autonews import tick

        self.item("Topuria vs Gaethje official for Madrid")
        with self.store.db() as c:
            c.execute("UPDATE studio_settings SET paused=1 WHERE id=1")
        self.assertEqual(tick(self.store, self.at, tools=Fake(self.root).tools()), [])
        with self.store.db() as c:
            c.execute("UPDATE studio_settings SET paused=0 WHERE id=1")
            c.execute("UPDATE delamain_projects SET autonomy='manual' WHERE id=?", (self.ch["id"],))
        self.assertEqual(tick(self.store, self.at, tools=Fake(self.root).tools()), [])

    def test_produced_video_is_ready_with_sources_rights_and_passes_the_gates(self):
        from studio.autonews import produce
        from studio.domain import blockers

        fake = Fake(self.root)
        iid = self.item("Topuria vs Gaethje official for Madrid")
        result = produce(self.store, {"channel_id": self.ch["id"], "item_id": iid}, self.job(), fake.tools())
        v = self.store.video(result["video_id"])
        self.assertEqual(v["status"], "ready", v["error"])
        self.assertEqual((v["quality_status"], v["rights_status"]), ("verified", "verified"))
        self.assertIn("Sources:", v["description"])
        self.assertIn("Wikimedia Commons", v["description"])
        self.assertIn("VERIFIED FACTS", v["notes"])
        self.assertTrue(v["engine_ref"]["auto"])
        self.assertIn("IT'S OFFICIAL", fake.prompt)
        manifest = v["rights_manifest"]
        self.assertEqual(manifest["voice"]["automated_access"], "owner_accepted_risk")
        self.assertTrue(manifest["visuals"])
        self.assertTrue(self.store.one("SELECT 1 AS x FROM studio_reviews WHERE video_id=?", (v["id"],)))
        brief = json.loads((self.root / v["engine_ref"]["job"] / "brief.json").read_text())
        self.assertTrue(all(s["visual"]["rights"]["license"] == "CC BY 2.0" for s in brief["segments"]))
        self.assertEqual(blockers(v, self.store.channel(self.ch["id"]), self.store.settings(), automatic=True), [])
        self.assertEqual(
            self.store.one("SELECT status FROM studio_news_items WHERE id=?", (iid,))["status"], "used"
        )

    def test_facts_not_found_in_the_sources_block_the_video(self):
        from studio.autonews import produce

        fake = Fake(self.root, quotes=["The champion was secretly injured last week in camp"] * 6)
        iid = self.item("Topuria vs Gaethje official for Madrid")
        with self.assertRaisesRegex(ValueError, "mot pour mot"):
            produce(self.store, {"channel_id": self.ch["id"], "item_id": iid}, self.job(), fake.tools())
        v = self.store.one("SELECT status,error FROM studio_videos WHERE channel_id=?", (self.ch["id"],))
        self.assertEqual(v["status"], "blocked")

    def test_fact_check_problems_are_rewritten_or_stop_the_video(self):
        from studio.autonews import produce

        issue = [{"segment": 0, "sentence": "x", "issue": "invented number"}]
        fixed = Fake(self.root, problems=[issue])
        iid = self.item("Topuria vs Gaethje official for Madrid")
        produce(self.store, {"channel_id": self.ch["id"], "item_id": iid}, self.job(), fixed.tools())
        stuck = Fake(self.root, problems=[issue, issue, issue])
        other = self.item("Topuria vs Gaethje: Madrid tickets gone", hours=1)
        with self.assertRaisesRegex(ValueError, "vérification des faits"):
            produce(self.store, {"channel_id": self.ch["id"], "item_id": other}, self.job(), stuck.tools())

    def test_trial_mode_stops_before_publication(self):
        from studio.autonews import produce

        iid = self.item("Topuria vs Gaethje official for Madrid")
        with patch.dict(os.environ, {"NEWS_AUTO_DRY": "1"}):
            result = produce(self.store, {"channel_id": self.ch["id"], "item_id": iid}, self.job(), Fake(self.root).tools())
        self.assertEqual(self.store.video(result["video_id"])["status"], "review")

    def test_a_stopped_video_resumes_from_its_saved_script(self):
        from studio.autonews import produce

        broken = Fake(self.root)
        broken.build = lambda folder, log: (_ for _ in ()).throw(ValueError("ffmpeg a échoué"))
        iid = self.item("Topuria vs Gaethje official for Madrid")
        payload = {"channel_id": self.ch["id"], "item_id": iid}
        with self.assertRaisesRegex(ValueError, "ffmpeg"):
            produce(self.store, payload, self.job(), broken.tools())
        fixed = Fake(self.root)
        result = produce(self.store, dict(payload, resume=True), self.job(), fixed.tools())
        self.assertEqual(self.store.video(result["video_id"])["status"], "ready")
        self.assertFalse(any("YouTube news analysis" in c or "Extract" in c for c in fixed.calls))
        self.assertEqual(produce(self.store, dict(payload, resume=True), self.job(), fixed.tools()), {"skipped": "nothing to resume"})

    def test_group_photos_are_refused_and_photos_alternate(self):
        from studio.autonews import _photos, illustrate

        fake = Fake(self.root)
        options = lambda name: [dict(o, url=o["url"] + str(i)) for i in range(3) for o in Fake.portraits(fake, name)]
        seen = []

        def chat(messages, **kw):
            seen.append(1)
            return {"ok": len(seen) != 1}  # the first photo shows a group

        tools = fake.tools()
        tools.portraits, tools.chat = options, chat
        found = _photos(tools, self.root, ["Ilia Topuria"])
        self.assertEqual([p["url"][-1] for p in found["Ilia Topuria"]], ["1", "2"])
        brief = plan()
        illustrate(brief, found)
        urls = [s["visual"]["url"][-1] for s in brief["segments"] if s.get("visual")]
        self.assertEqual(urls[:2], ["1", "2"])

    def test_a_card_never_shows_someone_else_and_extra_faces_are_refused(self):
        from studio.autonews import illustrate, produce

        brief = plan()
        found = {"Justin Gaethje": Fake.portraits(Fake(self.root), "Justin Gaethje")}
        illustrate(brief, found)
        for seg in brief["segments"]:
            self.assertEqual(bool(seg.get("visual")), seg["people"] == ["Justin Gaethje"])
        crowd = Fake(self.root)
        original = crowd.chat
        crowd.chat = lambda messages, **kw: (
            {"ok": True, "people_visible": 3}
            if isinstance(messages[0]["content"], list) and "Check this YouTube thumbnail" in messages[0]["content"][0]["text"]
            else original(messages, **kw)
        )
        iid = self.item("Topuria vs Gaethje official for Madrid")
        with self.assertRaisesRegex(ValueError, "Miniature refusée"):
            produce(self.store, {"channel_id": self.ch["id"], "item_id": iid}, self.job(), crowd.tools())

    def test_a_refused_thumbnail_blocks_the_video(self):
        from studio.autonews import produce

        iid = self.item("Topuria vs Gaethje official for Madrid")
        with self.assertRaisesRegex(ValueError, "Miniature refusée"):
            produce(self.store, {"channel_id": self.ch["id"], "item_id": iid}, self.job(), Fake(self.root, thumb_ok=False).tools())


class CommonsTests(unittest.TestCase):
    def test_only_reusable_licences_matching_the_name_are_kept(self):
        from services.commons import portraits

        def page(title, short, artist="Jane Doe", w=1200, h=1500, url="https://creativecommons.org/licenses/by-sa/4.0"):
            return {
                "title": title,
                "imageinfo": [
                    {
                        "mime": "image/jpeg",
                        "width": w,
                        "height": h,
                        "thumburl": "https://upload.wikimedia.org/t.jpg",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/" + title,
                        "extmetadata": {
                            "LicenseShortName": {"value": short},
                            "LicenseUrl": {"value": url},
                            "Artist": {"value": f"<a href='#'>{artist}</a>"},
                        },
                    }
                ],
            }

        data = {
            "query": {
                "pages": {
                    "1": page("File:Ilia Topuria 2024.jpg", "CC BY-SA 4.0"),
                    "2": page("File:Ilia Topuria poster.jpg", "CC BY-NC 2.0"),
                    "3": page("File:UFC crowd.jpg", "CC BY 2.0"),
                    "4": page("File:Ilia Topuria tiny.jpg", "CC BY 2.0", w=200, h=200),
                }
            }
        }
        found = portraits("Ilia Topuria", get=lambda params: data)
        self.assertEqual([p["title"] for p in found], ["File:Ilia Topuria 2024.jpg"])
        rights = found[0]["rights"]
        self.assertEqual((rights["license"], rights["author"], rights["adaptation_license"]), ("CC BY-SA 4.0", "Jane Doe", "CC BY-SA 4.0"))
        from services.news_rights import image_rights

        image_rights({"rights": rights})


if __name__ == "__main__":
    unittest.main()
