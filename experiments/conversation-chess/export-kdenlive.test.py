"""Verify editable portrait profiles without copyrighted test fixtures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

module = importlib.util.spec_from_file_location("native_export", Path(__file__).with_name("export-kdenlive.py"))
exporter = importlib.util.module_from_spec(module)
module.loader.exec_module(exporter)


class ExportProfiles(unittest.TestCase):
    def make(self, root, width, height):
        source = root / "fixture.mp4"
        source.write_bytes(b"synthetic fixture; probe is mocked")
        graphic = root / "fixture.png"
        graphic.write_bytes(b"synthetic image fixture")
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({
            "schema": "conversation-chess-kdenlive-interchange-v1",
            "width": width, "height": height, "fps": 30, "duration_frames": 30,
            "voiceover": False, "rating_schema_version": 4,
            "original_source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "source_quality": {"minimum_height": 1080, "accepted_for_final": True, "visually_reviewed": True},
            "opening": {"speaker": "white", "label": "First", "reviewed": True},
            "side_colors": {"white": "First", "black": "Second"},
            "segments": [{"kind": "source", "start_frame": 0, "end_frame": 30,
                          "duration_frames": 30, "background_file": str(source),
                          "graphics_file": str(graphic), "dialogue_audio_file": str(source)}],
        }), encoding="utf8")
        return manifest

    def test_native_profiles_and_dialogue_tracks(self):
        info = {"streams": [{"codec_type": "video", "width": 1920, "height": 1080, "index": 0},
                            {"codec_type": "audio", "index": 1}], "format": {"duration": "1"}}
        for width, height, num, den, preset in [(1920, 1080, "16", "9", "atsc_1080p_30"),
                                              (1080, 1920, "9", "16", "vertical_hd_30")]:
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp, patch.object(exporter, "probe", return_value=info):
                root = Path(tmp)
                project, report = exporter.generate(self.make(root, width, height), root / "bundle")
                xml = ET.parse(project)
                profile = xml.getroot().find("profile")
                self.assertEqual((profile.get("width"), profile.get("height")), (str(width), str(height)))
                self.assertEqual((profile.get("display_aspect_num"), profile.get("display_aspect_den")), (num, den))
                self.assertEqual(profile.get("sample_aspect_num"), profile.get("sample_aspect_den"))
                prop = xml.find(".//property[@name='kdenlive:docproperties.profile']")
                self.assertEqual(prop.text or "", preset)
                self.assertEqual(report["output_dimensions"], [width, height])
                self.assertEqual(len(report["track_clips"]["dialogue"]), 1)
                self.assertEqual(report["duration_frames"], 30)

    def test_unreviewed_geometry_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "reviewed"):
                exporter.generate(self.make(root, 720, 1280), root / "bundle")


if __name__ == "__main__":
    unittest.main()
