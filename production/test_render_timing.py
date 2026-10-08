"""Small real-encoder regressions for image-scene timing."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from PIL import Image

from services import render


@unittest.skipUnless(shutil.which("ffprobe"), "ffprobe required for encoder checks")
class ClipTimingTests(unittest.TestCase):
    def test_crossfades_keep_every_requested_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before, after = root / "before.png", root / "after.png"
            Image.new("RGB", (320, 180), "navy").save(before)
            Image.new("RGB", (320, 180), "green").save(after)
            for frames in (50, 63, 128):
                with self.subTest(frames=frames):
                    clip = root / f"{frames}.mp4"
                    render.render_clip(str(after), str(clip), frames, 320, 180, 30,
                                       "zoom_in", 0.045, motion_frames=frames + 6,
                                       prev={"image": str(before), "motion": "zoom_in",
                                             "n": 76, "offset": 70, "tf": 6})
                    result = subprocess.run(
                        [shutil.which("ffprobe"), "-v", "error", "-count_frames",
                         "-show_entries", "stream=nb_read_frames,duration",
                         "-of", "json", str(clip)], capture_output=True, text=True, check=True)
                    stream = json.loads(result.stdout)["streams"][0]
                    self.assertEqual(int(stream["nb_read_frames"]), frames)
                    self.assertAlmostEqual(float(stream["duration"]), frames / 30, places=5)


if __name__ == "__main__":
    unittest.main()
