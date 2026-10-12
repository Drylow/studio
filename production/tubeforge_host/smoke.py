"""Linux native-render smoke: local fixtures, no API calls or production edits."""
import asyncio
import json
from pathlib import Path
import subprocess
import tempfile
import sys
from unittest.mock import patch

import av
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "work/TubeForge"))
from app import config, store
from app.steps import render


with tempfile.TemporaryDirectory(prefix="tubeforge-smoke-") as tmp:
    root = Path(tmp)
    audio = root / "fixture.mp3"
    subprocess.run([config.get("FFMPEG"), "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:a", "libmp3lame", "-y", str(audio)], check=True)
    Image.new("RGB", (1280, 720), "#808080").save(root / "one.png")
    Image.new("RGB", (1280, 720), "#A8BE87").save(root / "two.png")
    p = {"id": "fixture", "title": "Local test", "voiceover": {"file": "fixture.mp3", "duration": 2},
         "settings": {"visuals": {"aspect": "16:9", "captions": False, "render_backend": "native", "motion_strength": .25}},
         "scenes": [{"id": 1, "image": "one.png", "start": 0, "end": 1, "motion": "none"},
                    {"id": 2, "image": "two.png", "start": 1, "end": 2, "motion": "none"}]}
    with patch.object(store, "project_dir", return_value=root), patch.object(store, "load_words", return_value=[]), \
         patch.object(store, "save_project", side_effect=lambda obj: obj):
        asyncio.run(render.render(p))
    with av.open(str(root / p["render"]["file"])) as movie:
        video = movie.streams.video[0]
        frames = sum(1 for _ in movie.decode(video=0))
        assert frames == 48 and (video.width, video.height) == (1920, 1080)
        assert len(movie.streams.audio) == 1
    print(json.dumps({"native_render": "ok", "frames": 48, "fps": 24, "audio": True, "paid_api_calls": 0}))
