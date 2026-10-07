import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
spec = importlib.util.spec_from_file_location("edo_episode", Path(__file__).with_name("edo_episode.py"))
episode_tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(episode_tools)


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        (self.work / "narration.mp3").write_bytes(b"test audio fixture")
        self.sha = episode_tools.digest(self.work / "narration.mp3")
        episode_tools.save(self.work / "voice.json", {"audio_sha256": self.sha})
        self.episode = {"language": "en", "shots": [
            {"id": "001", "narration": "You carry water home."},
            {"id": "002", "narration": "The table is ready."},
        ]}
        self.words = [{"w": word, "s": i * 0.5, "e": i * 0.5 + 0.4}
                      for i, word in enumerate("You carry water home The table is ready".split())]

    def tearDown(self):
        self.tmp.cleanup()

    def test_shots_use_measured_words_and_retain_exact_narration(self):
        with patch.object(episode_tools, "measure_words", return_value=self.words), \
             patch.object(episode_tools.media, "duration", return_value=4.2):
            episode_tools.timeline(self.episode, self.work)
        result = episode_tools.read(self.work / "timeline.json")
        self.assertEqual(result["shots"][0]["start"], 0)
        self.assertEqual(result["shots"][1]["start"], 2.0)
        self.assertEqual(result["shots"][1]["end"], 4.2)
        self.assertEqual(result["coverage"], 1.0)
        self.assertIn("The table is ready.", (self.work / "subtitles.srt").read_text())

    def test_missing_measurement_refuses_estimated_timings(self):
        with patch.object(episode_tools, "measure_words", return_value=None):
            with self.assertRaises(SystemExit):
                episode_tools.timeline(self.episode, self.work)
        self.assertFalse((self.work / "timeline.json").exists())

    def test_cached_measurements_cannot_follow_a_changed_audio_file(self):
        episode_tools.save(self.work / "measured_words.json", {"audio_sha256": "wrong", "words": self.words})
        with self.assertRaises(SystemExit):
            episode_tools.timeline(self.episode, self.work)

    def test_script_change_with_large_mismatch_stops_alignment(self):
        changed = copy.deepcopy(self.episode)
        changed["shots"][1]["narration"] = "A completely different unspoken paragraph exists now."
        with patch.object(episode_tools, "measure_words", return_value=self.words):
            with self.assertRaises(SystemExit):
                episode_tools.timeline(changed, self.work)

    def test_timestamps_round_across_minute_boundary(self):
        self.assertEqual(episode_tools.timestamp(59.9996), "00:01:00,000")

    def test_render_refuses_a_stale_image_selection(self):
        shots = [{"id": "001", "image": "old.png", "narration": "Hello.", "motion": "none"}]
        episode_tools.save(self.work / "timeline.json", {"audio_sha256": self.sha, "shots": shots})
        changed = {"shots": [{**shots[0], "image": "corrected.png"}]}
        with patch.object(episode_tools, "validate_images", return_value=True), \
             patch.object(episode_tools.render, "render_video") as encode:
            with self.assertRaisesRegex(SystemExit, "Shot selection changed"):
                episode_tools.export_video(changed, self.work, 1920, 1080)
        encode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
