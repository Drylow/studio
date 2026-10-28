"""Offline recovery checks: no network requests, no real ledgers or paid jobs."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import recap_voiceovers_oct28_recovery as recovery

base = recovery.base
engine = recovery.engine


def sample_data(states):
    return {"voice_id": recovery.VOICE, "speed": recovery.SPEED,
            "episodes": [{"id": "example", "state": "ready", "characters": 1000,
                          "parts": [{"id": "part" + str(n), "state": s, "characters": 250}
                                    for n, s in enumerate(states)]}]}


class RecoveryTests(unittest.TestCase):
    def test_partition_is_exact_and_paragraph_aligned(self):
        text = "Début.\n\n" + "Un paragraphe français de contrôle.\n\n" * 2400 + "Dernière phrase."
        old = {"id": "episode-part1", "job_id": "private-test-id", "start": 0,
               "end": len(text), "sha256": hashlib.sha256(text.encode()).hexdigest()}
        parts = recovery.subdivide({}, old, text)
        self.assertEqual(len(parts), 4)
        self.assertEqual("".join(text[p["start"]:p["end"]] for p in parts), text)
        self.assertTrue(all(p["characters"] < 30000 for p in parts))
        self.assertTrue(all(a["end"] == b["start"] for a, b in zip(parts, parts[1:])))
        changed = dict(old, sha256="bad")
        with self.assertRaises(RuntimeError):
            recovery.subdivide({}, changed, text)

    def test_run_has_two_active_jobs_and_no_resubmission(self):
        data = sample_data(["ready"] * 6)
        submitted = []
        peak = []

        def submit(d, limit):
            self.assertEqual(limit, 2)
            self.assertFalse(any(p["state"] == "submitted" for p in d["episodes"][0]["parts"]))
            waiting = [p for p in d["episodes"][0]["parts"] if p["state"] == "ready"][:limit]
            for p in waiting:
                p["state"] = "submitted"
                submitted.append(p["id"])
            peak.append(len(waiting))
            return True

        def monitor(d):
            for p in d["episodes"][0]["parts"]:
                if p["state"] == "submitted":
                    p["state"] = "verified"
            if all(p["state"] == "verified" for p in d["episodes"][0]["parts"]):
                d["episodes"][0]["state"] = "verified"

        with patch.object(recovery, "prepare"), patch.object(recovery, "reconcile_original_failures"), \
                patch.object(engine.tts, "algrow_credits", return_value={"tts_characters": {"remaining": 100000}}), \
                patch.object(base, "submit", side_effect=submit), patch.object(base, "monitor", side_effect=monitor):
            self.assertTrue(recovery.run(data))
            self.assertTrue(recovery.run(data))
        self.assertEqual(len(submitted), 6)
        self.assertEqual(len(set(submitted)), 6)
        self.assertEqual(max(peak), 2)

    def test_new_terminal_failure_stops_the_queue(self):
        data = sample_data(["submitted", "submitted", "ready", "ready"])

        def monitor(d):
            d["episodes"][0]["parts"][0]["state"] = "failed"
            d["episodes"][0]["parts"][1]["state"] = "verified"

        with patch.object(recovery, "prepare"), patch.object(recovery, "status_files"), \
                patch.object(base, "monitor", side_effect=monitor), patch.object(base, "submit") as submit, \
                patch.object(engine, "emit"):
            self.assertFalse(recovery.run(data))
            submit.assert_not_called()

    def test_ambiguous_post_is_saved_and_never_repeated(self):
        data = sample_data(["ready", "ready"])
        rows = [(data["episodes"][0], p, "x" * 250) for p in data["episodes"][0]["parts"]]
        saved = []
        with patch.object(base, "prepare", return_value=rows), patch.object(base, "status_files"), \
                patch.object(engine, "save", side_effect=lambda d: saved.append(copy.deepcopy(d))), \
                patch.object(engine, "emit"), \
                patch.object(engine.tts, "algrow_credits", return_value={"tts_characters": {"remaining": 10000}}), \
                patch.object(engine.tts, "_algrow_call", side_effect=[{"job_id": "accepted"}, TimeoutError()]) as api:
            self.assertFalse(base.submit(data, 2))
            self.assertEqual(data["episodes"][0]["parts"][0]["state"], "submitted")
            self.assertEqual(data["episodes"][0]["parts"][1]["state"], "submission_unknown")
            with self.assertRaises(RuntimeError):
                base.submit(data, 2)
            self.assertEqual(api.call_count, 2)
            self.assertTrue(any(d["episodes"][0]["parts"][1]["state"] == "submitting" for d in saved))
            self.assertEqual(saved[-1]["episodes"][0]["parts"][1]["state"], "submission_unknown")

    def test_monitor_never_submits(self):
        data = sample_data(["submitted", "ready"])
        part = data["episodes"][0]["parts"][0]
        part["job_id"] = "already-existing"
        rows = [(data["episodes"][0], p, "x" * 250) for p in data["episodes"][0]["parts"]]
        with patch.object(engine, "parts", return_value=rows), patch.object(engine, "save"), \
                patch.object(engine, "emit"), patch.object(base, "status_files"), \
                patch.object(engine.tts, "algrow_credits", return_value={}), \
                patch.object(engine.tts, "_algrow_call", return_value={"status": "failed", "error": "test"}) as api:
            base.monitor(data)
            self.assertEqual(api.call_count, 1)
            self.assertEqual(api.call_args.args[0], "GET")
        self.assertEqual(part["state"], "failed")
        self.assertEqual(data["episodes"][0]["parts"][1]["state"], "ready")

    def test_short_assembly_never_delivers(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            audio = directory / "part.mp3"
            audio.write_bytes(b"test audio placeholder")
            episode = {"id": "test", "state": "ready", "parts": [
                {"audio_path": str(audio), "audio_bytes": audio.stat().st_size,
                 "audio_sha256": base.digest(audio), "duration_seconds": 6000,
                 "transcript_integrity_passed": True}]}

            def create_output(args, timeout):
                Path(args[-1]).write_bytes(audio.read_bytes())

            def verify(row, minimum=0):
                self.assertEqual(minimum, 7200)
                row.update(state="duration_below_minimum", duration_seconds=6000, full_decode_passed=True)

            with patch.object(engine, "STATE", directory), patch.object(engine.media, "run", side_effect=create_output), \
                    patch.object(engine, "verify", side_effect=verify), patch.object(base, "deliver") as deliver:
                recovery.assemble(episode)
                deliver.assert_not_called()
                self.assertEqual(episode["state"], "duration_below_minimum")


if __name__ == "__main__":
    unittest.main()
