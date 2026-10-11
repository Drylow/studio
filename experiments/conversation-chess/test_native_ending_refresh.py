"""Exercise native ending guards without invoking any media process."""

import copy
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock


_spec = importlib.util.spec_from_file_location(
    "native_ending_refresh", Path(__file__).with_name("refresh-native-ending.py"))
ending = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ending)


class EndingFilterTests(unittest.TestCase):
    def test_authored_eighteen_frame_tail(self):
        video, graphics, audio = ending.ending_filters(.6, .5)
        self.assertTrue(video.startswith(ending.SOURCE_VIDEO_FILTER + ",fade=t=out:"))
        for value in (video, graphics, audio):
            match = re.search(r"fade=t=out:st=([^:]+):d=([^,:]+)", value)
            self.assertIsNotNone(match)
            self.assertAlmostEqual(float(match[1]), .1)
            self.assertEqual(float(match[2]), .5)
        self.assertIn("format=argb", graphics)
        self.assertIn(":alpha=1", graphics)
        self.assertIn("atrim=end_sample=28800", audio)

    def test_rejects_invalid_duration_fade_and_gain(self):
        cases = [
            (-.6, .5, 1), (.4, .5, 1), (.61, .5, 1),
            (True, .5, 1), (float("nan"), .5, 1),
            (.6, -.1, 1), (.6, 0, 1), (.6, .7, 1), (2, 1.3, 1),
            (.6, .51, 1), (.6, True, 1), (.6, float("inf"), 1),
            (.6, .5, 0), (.6, .5, -.1), (.6, .5, 1.01),
            (.6, .5, True), (.6, .5, float("nan")),
        ]
        for duration, fade, gain in cases:
            with self.subTest(duration=duration, fade=fade, gain=gain):
                with self.assertRaises(ValueError):
                    ending.ending_filters(duration, fade, gain)


class BeforeOutputValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="native-ending-guards-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.source = self.folder / "source.bin"
        self.source.write_bytes(b"Local provenance fixture; not an encoded media file.")
        self.timeline = self.folder / "timeline.json"
        self.timeline.write_text(json.dumps({"source_in": 0, "source_out": .6}), encoding="utf-8")
        self.manifest = self.folder / "manifest.json"
        self.out = self.folder / "new-output"
        self.base = {
            "fps": 30,
            "original_source": str(self.source),
            "source_sha256": ending.digest(self.source),
            "timeline_file": str(self.timeline),
            "timeline_sha256": ending.digest(self.timeline),
            "segments": [{
                "kind": "source", "start_frame": 480, "end_frame": 498,
                "duration_frames": 18, "duration": .6,
                "source_in": 0, "source_out": .6,
                "graphics_type": "alpha_png", "dialogue_gain": 1,
            }, {"kind": "outro"}],
        }

    def assert_rejected_before_output(self, fields, message, fade="0.5"):
        manifest = copy.deepcopy(self.base)
        manifest["segments"][0].update(fields)
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        argv = ["refresh-native-ending.py", "--manifest", str(self.manifest),
                "--seconds", fade, "--out", str(self.out)]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(ending.subprocess, "run", side_effect=AssertionError("No encoding allowed")) as run, \
                mock.patch.object(ending.subprocess, "check_output", side_effect=AssertionError("No probing allowed")) as probe:
            with self.assertRaisesRegex(ValueError, message):
                ending.main()
            run.assert_not_called()
            probe.assert_not_called()
        self.assertFalse(self.out.exists(), "Invalid input created an output directory")
        self.assertEqual(ending.digest(self.source), self.base["source_sha256"])
        self.assertEqual(ending.digest(self.timeline), self.base["timeline_sha256"])

    def test_rejects_boolean_noninteger_and_nonpositive_frame_coordinates(self):
        cases = [
            {"duration_frames": True}, {"duration_frames": 18.0},
            {"duration_frames": 17.5}, {"duration_frames": 0},
            {"duration_frames": -18}, {"start_frame": True},
            {"start_frame": 480.0}, {"end_frame": True}, {"end_frame": 498.0},
        ]
        for fields in cases:
            with self.subTest(fields=fields):
                self.assert_rejected_before_output(fields, "integer frame coordinates")

    def test_rejects_frame_span_and_declared_duration_mismatch(self):
        for fields, message in [
            ({"end_frame": 499}, "Final frame bounds changed"),
            ({"duration": .61}, "Source duration is not frame aligned"),
            ({"duration": -.6}, "Source duration is not frame aligned"),
            ({"duration": True}, "Source duration is not frame aligned"),
        ]:
            with self.subTest(fields=fields):
                self.assert_rejected_before_output(fields, message)

    def test_rejects_invalid_source_intervals(self):
        cases = [
            {"source_in": .01}, {"source_out": .61},
            {"source_in": -1 / 30}, {"source_out": -1 / 30},
            {"source_in": True}, {"source_out": True},
            {"source_in": float("nan")}, {"source_out": float("inf")},
            {"source_out": 19 / 30}, {"source_in": .6, "source_out": 0},
        ]
        for fields in cases:
            with self.subTest(fields=fields):
                self.assert_rejected_before_output(fields, "Final source bounds must match")

    def test_rejects_invalid_gain_before_output(self):
        for gain in (0, -.1, 1.01, True, float("nan"), float("inf")):
            with self.subTest(gain=gain):
                self.assert_rejected_before_output({"dialogue_gain": gain}, "Native preparation gain")

    def test_rejects_invalid_requested_fade_before_output(self):
        for fade, message in [
            ("-0.1", "Fade must be positive"), ("0", "Fade must be positive"),
            ("0.51", "Fade must be positive"), ("nan", "Fade must be positive"),
            ("1.3", "Fade must be positive"), ("0.7", "Fade exceeds"),
        ]:
            with self.subTest(fade=fade):
                self.assert_rejected_before_output({}, message, fade)


if __name__ == "__main__":
    unittest.main()
