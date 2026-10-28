"""Offline checks for paid-request safety and the authorized narration scope."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "production"))
import forgotten_voiceovers_oct28 as batch


class ForgottenBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.old = (batch.engine.STATE, batch.engine.SOURCE, batch.engine.OUT, batch.FRENCH_LEDGER)
        batch.engine.STATE = root / "state"
        batch.engine.SOURCE = root / "state/sources"
        batch.engine.OUT = root / "delivery"
        batch.FRENCH_LEDGER = root / "french.json"
        self.set_reserve([
            {"state": "ready", "characters": 10000},
            {"state": "submitting", "characters": 20000},
            {"state": "submission_unknown", "characters": 30000},
            {"state": "submitted", "characters": 40000},
            {"state": "verified", "characters": 50000},
        ])
        self.data = batch.load()
        batch.prepare(self.data)
        self.balance = {"tts_characters": {"remaining": 1000000}}

    def tearDown(self):
        batch.engine.STATE, batch.engine.SOURCE, batch.engine.OUT, batch.FRENCH_LEDGER = self.old
        self.temp.cleanup()

    def set_reserve(self, parts):
        batch.FRENCH_LEDGER.write_text(json.dumps({"generate_srt": True, "episodes": [{"parts": parts}]}))

    def test_only_three_authorized_episodes_and_exact_slices(self):
        self.assertEqual(tuple(e["id"] for e in self.data["episodes"]), batch.IDS)
        self.assertEqual(len(batch.IDS), 3)
        self.assertFalse(any(e["id"].startswith(("FR-07", "FR-08")) for e in self.data["episodes"]))
        planned = list(batch.parts(self.data))
        self.assertEqual(len(planned), 24)
        self.assertEqual(sum(len(text) for _, _, text in planned), 524530)
        for episode in self.data["episodes"]:
            whole = (batch.engine.SOURCE / episode["script"]).read_text("utf-8-sig")
            self.assertEqual("".join(text for e, _, text in planned if e is episode), whole)
            self.assertTrue(all(15000 <= p["characters"] <= 30000 for p in episode["parts"]))
        self.assertEqual(batch.load(), self.data)

    def test_excluded_episode_injected_into_resume_is_rejected(self):
        altered = copy.deepcopy(self.data)
        altered["episodes"].append({"id": "FR-07-oblivion-crisis"})
        with self.assertRaises(RuntimeError):
            batch.validate_settings(altered)

    def test_reserve_covers_ready_and_ambiguous_not_already_accepted(self):
        self.assertEqual(batch.french_reserve(), 72000)
        batch.FRENCH_LEDGER.unlink()
        with self.assertRaises(FileNotFoundError):
            batch.french_reserve()

    def test_budget_never_spends_french_reserve(self):
        balance = {"tts_characters": {"remaining": 524530 + 72000 - 1}}
        with patch.object(batch.engine.tts, "algrow_credits", return_value=balance), \
                patch.object(batch.engine.tts, "_algrow_call") as post:
            self.assertFalse(batch.submit_pair(self.data))
            post.assert_not_called()
        self.assertTrue(self.data["budget_blocked"])
        self.assertTrue(all(p["state"] == "ready" for _, p, _ in batch.parts(self.data)))

    def test_budget_snapshot_is_conservative_during_french_submission(self):
        with patch.object(batch, "french_reserve", side_effect=[90000, 60000]), \
                patch.object(batch.engine.tts, "algrow_credits", return_value=self.balance):
            self.assertTrue(batch.budget_snapshot(self.data))
        self.assertEqual(self.data["french_reserve"], 90000)

    def test_accepts_two_once_with_exact_voice_settings(self):
        with patch.object(batch.engine.tts, "algrow_credits", return_value=self.balance), \
                patch.object(batch.engine.tts, "_algrow_call", side_effect=[{"job_id": "test-a"}, {"job_id": "test-b"}]) as post:
            self.assertTrue(batch.submit_pair(self.data))
            self.assertEqual(post.call_count, 2)
            for call in post.call_args_list:
                self.assertEqual(call.args[:2], ("POST", "/api/generate-simple"))
                settings = call.args[2]
                self.assertEqual(settings["voice_id"], batch.VOICE)
                self.assertEqual(settings["speed"], "0.90")
                self.assertEqual(settings["generate_srt"], "false")
            with self.assertRaises(RuntimeError):
                batch.submit_pair(self.data)
            self.assertEqual(post.call_count, 2)
        self.assertEqual(sum(p["state"] == "submitted" for _, p, _ in batch.parts(self.data)), 2)

    def test_unknown_submission_is_persisted_and_never_retried(self):
        with patch.object(batch.engine.tts, "algrow_credits", return_value=self.balance), \
                patch.object(batch.engine.tts, "_algrow_call", side_effect=TimeoutError("simulated")) as post:
            self.assertFalse(batch.submit_pair(self.data))
            reloaded = batch.load()
            self.assertEqual(reloaded["episodes"][0]["parts"][0]["state"], "submission_unknown")
            with self.assertRaises(RuntimeError):
                batch.submit_pair(reloaded)
            self.assertEqual(post.call_count, 1)

    def test_monitor_with_only_ready_parts_never_submits(self):
        with patch.object(batch.engine.tts, "_algrow_call") as network:
            batch.monitor(self.data)
            network.assert_not_called()

    def test_pause_file_blocks_run_and_every_submission(self):
        (batch.engine.STATE / "pause-submissions.json").write_text('{"reason":"user_duration_review"}')
        with patch.object(batch.engine.tts, "_algrow_call") as network, \
                patch.object(batch.engine.tts, "algrow_credits") as credits:
            self.assertFalse(batch.run(self.data))
            self.assertFalse(batch.submit_pair(self.data))
            network.assert_not_called()
            credits.assert_not_called()
            batch.monitor(self.data)
            network.assert_not_called()

    def test_pause_appearing_after_persistence_prevents_post(self):
        # submit_pair entry, first loop entry, then final check before POST.
        with patch.object(batch, "submissions_paused", side_effect=[False, False, True]), \
                patch.object(batch.engine.tts, "algrow_credits", return_value=self.balance), \
                patch.object(batch.engine.tts, "_algrow_call") as post:
            self.assertFalse(batch.submit_pair(self.data))
            post.assert_not_called()
        self.assertEqual(batch.load()["episodes"][0]["parts"][0]["state"], "ready")

    def test_missing_local_qa_cannot_mark_audio_verified(self):
        part = self.data["episodes"][0]["parts"][0]
        def fake_decode(row):
            row["state"] = "verified"
        with patch.object(batch.engine, "verify", side_effect=fake_decode):
            batch.verify_part(part, "source")
        self.assertEqual(part["state"], "audio_review_required")


if __name__ == "__main__":
    unittest.main()
