"""Fetch one manifest-pinned recording for local editing; do not redistribute it."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("id", help="Recording ID in assets/music/manifest.json")
args = parser.parse_args()
directory = Path(__file__).resolve().parent / "assets/music"
tracks = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))["tracks"]
track = next((item for item in tracks if item["id"] == args.id), None)
if track is None:
    parser.error("Unknown recording ID")
destination = directory / track["file"]
if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == track["sha256"]:
    print(f"Verified: {destination.name}")
else:
    with urlopen(track["source_url"], timeout=60) as response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != track["sha256"]:
        raise ValueError("Recording differs from the reviewed manifest; download was not saved")
    destination.write_bytes(content)
    print(f"Downloaded and verified: {destination.name}")
