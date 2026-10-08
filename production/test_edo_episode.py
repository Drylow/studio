import copy
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
spec = importlib.util.spec_from_file_location("edo_episode", Path(__file__).with_name("edo_episode.py"))
episode_tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(episode_tools)


class ProductionContractTests(unittest.TestCase):
    def test_narration_only_reads_the_authored_source_without_inventing_shots(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "script.txt"
            script.write_text("An authored first section.\n\nA second section.\n", encoding="utf-8")
            manifest = {"phase": "narration-only", "narration_script": "script.txt"}
            with patch.object(episode_tools, "REPO", folder):
                self.assertEqual(episode_tools.authored_text(manifest),
                                 "An authored first section.\n\nA second section.")
                manifest["shots"] = []
                with self.assertRaisesRegex(SystemExit, "masquerade"):
                    episode_tools.authored_text(manifest)

    def test_empty_narration_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "script.txt"
            script.write_text("\n", encoding="utf-8")
            with patch.object(episode_tools, "REPO", folder):
                with self.assertRaisesRegex(SystemExit, "empty"):
                    episode_tools.authored_text({"phase": "narration-only", "narration_script": "script.txt"})

    def test_requested_duration_is_a_measured_gate(self):
        manifest = {"target_duration_seconds": [1200, 1500]}
        for duration in (1200, 1350, 1500):
            episode_tools.validate_narration_duration(manifest, duration)
        for duration in (1199.9, 1500.1):
            with self.assertRaisesRegex(SystemExit, "manual revision"):
                episode_tools.validate_narration_duration(manifest, duration)
        episode_tools.validate_narration_duration({}, 10)

    def test_exports_can_be_named_for_each_channel_without_path_escape(self):
        work = Path("work")
        self.assertEqual(episode_tools.export_path({}, work), work / "Edo-Daily-01.mp4")
        self.assertEqual(episode_tools.export_path({"export_filename": "Aztec-Daily-01.mp4"}, work),
                         work / "Aztec-Daily-01.mp4")
        for name in ("../escape.mp4", "sub/video.mp4", "sub\\video.mp4", "video.txt", None):
            with self.assertRaises(SystemExit):
                episode_tools.export_path({"export_filename": name}, work)


class NarrationMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        (self.work / "script.txt").write_text("A measured voice stays unchanged.", encoding="utf-8")
        (self.work / "narration.mp3").write_bytes(b"audio fixture")
        self.episode = {"phase": "narration-only", "narration_script": "script.txt",
                        "voice": {"id": "fixture", "speed": 1}, "language": "en"}
        identity = {"text": "A measured voice stays unchanged.", "voice": self.episode["voice"]}
        self.sha = episode_tools.digest(self.work / "narration.mp3")
        episode_tools.save(self.work / "voice.json", {
            "signature": hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
            "audio_sha256": self.sha, "duration": 3.0})
        self.words = [{"w": word, "s": i * 0.5, "e": i * 0.5 + 0.4}
                      for i, word in enumerate("A measured voice stays unchanged".split())]
        self.repo_patch = patch.object(episode_tools, "REPO", self.work)
        self.repo_patch.start()

    def tearDown(self):
        self.repo_patch.stop()
        self.tmp.cleanup()

    def test_measurement_is_cached_without_inventing_a_shot_plan(self):
        with patch.object(episode_tools, "measure_words", return_value=self.words) as measure, \
             patch.object(episode_tools.media, "duration", return_value=3.0):
            episode_tools.measure_narration(self.episode, self.work)
            episode_tools.measure_narration(self.episode, self.work)
        measure.assert_called_once()
        receipt = episode_tools.read(self.work / "narration_measurement.json")
        self.assertEqual(receipt["coverage"], 1.0)
        self.assertTrue(receipt["shot_authoring_pending"])
        self.assertFalse((self.work / "timeline.json").exists())

    def test_measurement_refuses_changed_source_or_audio(self):
        for target, contents in (("script.txt", b"Different narration."),
                                 ("narration.mp3", b"changed audio")):
            with self.subTest(target=target):
                original = (self.work / target).read_bytes()
                (self.work / target).write_bytes(contents)
                with self.assertRaisesRegex(SystemExit, "source or audio changed"):
                    episode_tools.measure_narration(self.episode, self.work)
                (self.work / target).write_bytes(original)

    def test_measurement_records_actual_audio_duration_not_provider_metadata(self):
        voice = episode_tools.read(self.work / "voice.json")
        voice["duration"] = 99.0
        episode_tools.save(self.work / "voice.json", voice)
        with patch.object(episode_tools, "measure_words", return_value=self.words), \
             patch.object(episode_tools.media, "duration", return_value=3.0):
            episode_tools.measure_narration(self.episode, self.work)
        receipt = episode_tools.read(self.work / "narration_measurement.json")
        self.assertEqual(receipt["duration"], 3.0)

    def test_measurement_refuses_estimates_or_mismatched_cache(self):
        with patch.object(episode_tools.media, "duration", return_value=3.0), \
             patch.object(episode_tools, "measure_words", return_value=None):
            with self.assertRaisesRegex(SystemExit, "estimated"):
                episode_tools.measure_narration(self.episode, self.work)
        episode_tools.save(self.work / "measured_words.json", {"audio_sha256": "wrong", "words": self.words})
        with patch.object(episode_tools.media, "duration", return_value=3.0):
            with self.assertRaisesRegex(SystemExit, "different narration"):
                episode_tools.measure_narration(self.episode, self.work)

    def test_measurement_refuses_low_transcript_coverage(self):
        with patch.object(episode_tools.media, "duration", return_value=3.0), \
             patch.object(episode_tools, "measure_words", return_value=[{"w": "Unrelated", "s": 0, "e": 1}]):
            with self.assertRaisesRegex(SystemExit, "discrepancy"):
                episode_tools.measure_narration(self.episode, self.work)
        self.assertFalse((self.work / "narration_measurement.json").exists())


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

    def test_small_script_change_refuses_a_cached_voice(self):
        self.episode["voice"] = {"id": "fixture", "speed": 1}
        identity = {"text": "\n\n".join(s["narration"] for s in self.episode["shots"]),
                    "voice": self.episode["voice"]}
        signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        episode_tools.save(self.work / "voice.json", {"audio_sha256": self.sha,
                                                     "signature": signature})
        self.episode["shots"][1]["narration"] = "The table was ready."
        with self.assertRaisesRegex(SystemExit, "Authored narration changed"):
            episode_tools.timeline(self.episode, self.work)

    def test_render_refuses_a_stale_image_selection(self):
        shots = [{"id": "001", "image": "old.png", "narration": "Hello.", "motion": "none"}]
        episode_tools.save(self.work / "timeline.json", {"audio_sha256": self.sha, "shots": shots})
        changed = {"shots": [{**shots[0], "image": "corrected.png"}]}
        with patch.object(episode_tools, "validate_images", return_value=True), \
             patch.object(episode_tools.render, "render_video") as encode:
            with self.assertRaisesRegex(SystemExit, "Shot selection changed"):
                episode_tools.export_video(changed, self.work, 1920, 1080)
        encode.assert_not_called()


    def test_resegmented_shots_preserve_cached_voice_identity(self):
        original = "You carry water home.\n\nThe table is ready."
        changed = copy.deepcopy(self.episode)
        changed["voice_text"] = original
        changed["shots"] = [
            {"id": "001-01", "narration": "You carry"},
            {"id": "001-02", "narration": "water home."},
            {"id": "002-01", "narration": "The table is ready."},
        ]
        self.assertEqual(episode_tools.authored_text(changed), original)

    def test_voice_text_cannot_hide_a_changed_word(self):
        self.episode["voice_text"] = "You carry water home. The table was ready."
        with self.assertRaisesRegex(SystemExit, "approved voice text"):
            episode_tools.authored_text(self.episode)

    def test_image_cadence_includes_final_tail(self):
        episode = {"max_shot_seconds": 6}
        episode_tools.validate_cadence(episode, [{"id": "001", "start": 0, "end": 5.6}], tail=0.4)
        with self.assertRaisesRegex(SystemExit, "image cadence"):
            episode_tools.validate_cadence(episode, [{"id": "001", "start": 0, "end": 5.7}], tail=0.4)

    def test_timeline_refuses_long_unsegmented_image(self):
        self.episode["max_shot_seconds"] = 1.9
        with patch.object(episode_tools, "measure_words", return_value=self.words), \
             patch.object(episode_tools.media, "duration", return_value=4.2):
            with self.assertRaisesRegex(SystemExit, "image cadence"):
                episode_tools.timeline(self.episode, self.work)


class RenderTimingTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"duration": 9.6, "shots": [{"start": 0}, {"start": 5}]}
        self.streams = [{"codec_type": "video", "nb_read_frames": "300", "duration": "10",
                         "r_frame_rate": "30/1"}, {"codec_type": "audio", "duration": "10"}]

    def test_exact_picture_and_audio_pass(self):
        self.assertEqual(episode_tools.validate_render_timing(self.plan, self.streams), 300)

    def test_short_picture_is_not_hidden_by_long_audio(self):
        self.streams[0].update(nb_read_frames="299", duration=str(299 / 30))
        with self.assertRaisesRegex(SystemExit, "Video frame count"):
            episode_tools.validate_render_timing(self.plan, self.streams)

    def test_wrong_picture_duration_blocks_review(self):
        self.streams[0]["duration"] = "9.9"
        with self.assertRaisesRegex(SystemExit, "Picture duration"):
            episode_tools.validate_render_timing(self.plan, self.streams)

    def test_wrong_picture_cadence_blocks_review(self):
        self.streams[0]["r_frame_rate"] = "25/1"
        with self.assertRaisesRegex(SystemExit, "cadence"):
            episode_tools.validate_render_timing(self.plan, self.streams)

    def test_missing_audio_blocks_review(self):
        with self.assertRaisesRegex(SystemExit, "both picture and narration"):
            episode_tools.validate_render_timing(self.plan, self.streams[:1])

    def test_wrong_audio_duration_blocks_review(self):
        self.streams[1]["duration"] = "11"
        with self.assertRaisesRegex(SystemExit, "Narration duration"):
            episode_tools.validate_render_timing(self.plan, self.streams)


class ImageGateTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        self.reference = self.work / "master.png"
        self.frame = self.work / "frame.png"
        Image.new("RGB", (960, 540), "white").save(self.reference)
        Image.new("RGB", (960, 540), "gray").save(self.frame)
        self.episode = {"shots": [{"id": "001", "image": str(self.frame),
                                    "references": [str(self.reference)]}]}
        self.review = {"001": {"accepted": True, "image": str(self.frame),
                                "sha256": episode_tools.digest(self.frame)}}
        episode_tools.save(self.work / "image_review.json", self.review)
        episode_tools.save(self.work / "frozen_references.json", {
            str(self.reference): {"sha256": episode_tools.digest(self.reference)}})

    def tearDown(self):
        self.tmp.cleanup()

    def test_reviewed_selection_passes(self):
        self.assertTrue(episode_tools.validate_images(self.episode, self.work))

    def test_revoked_continuity_review_blocks_render(self):
        self.review["001"]["accepted"] = False
        episode_tools.save(self.work / "image_review.json", self.review)
        with self.assertRaisesRegex(SystemExit, "Shot must be reviewed"):
            episode_tools.validate_images(self.episode, self.work)

    def test_different_selected_path_requires_review_even_if_bytes_match(self):
        duplicate = self.work / "duplicate.png"
        duplicate.write_bytes(self.frame.read_bytes())
        self.episode["shots"][0]["image"] = str(duplicate)
        with self.assertRaisesRegex(SystemExit, "Shot must be reviewed"):
            episode_tools.validate_images(self.episode, self.work)

    def test_changed_master_blocks_render(self):
        self.reference.write_bytes(b"changed reference fixture")
        with self.assertRaisesRegex(SystemExit, "Canonical reference changed"):
            episode_tools.validate_images(self.episode, self.work)

    def test_new_reference_requires_refreezing(self):
        self.episode["shots"][0]["references"].append("unreviewed.png")
        with self.assertRaisesRegex(SystemExit, "Reference selection changed"):
            episode_tools.validate_images(self.episode, self.work)


if __name__ == "__main__":
    unittest.main()
