"""Check only this public handoff; no network, generation or publication."""
import hashlib
import json
from pathlib import Path

base = Path(__file__).resolve().parent
manifest = json.loads((base / 'asset-manifest.json').read_text(encoding='utf-8'))
for record in manifest['records']:
    path = (base / record['path']).resolve()
    assert path.is_relative_to(base), record['path']
    assert path.is_file(), record['path']
    assert path.stat().st_size == record['bytes'], record['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'], record['path']
    assert path.stat().st_size < 100_000_000, record['path']
plan = json.loads((base / 'plan/bound-plan.json').read_text(encoding='utf-8'))['document']
reviews = json.loads((base / 'reviews/source-review.json').read_text(encoding='utf-8'))['document']
assert [scene['id'] for scene in plan['scenes']] == list(range(1, 109))
assert len(reviews['records']) == 108
assert all(row['state'] == 'pass' for row in reviews['records'])
frames = 0
for scene in plan['scenes']:
    assert round(scene['start'] * 24) == frames
    frames = round(scene['end'] * 24)
    for reference in scene['references']:
        p = base / reference['path']
        assert hashlib.sha256(p.read_bytes()).hexdigest() == reference['sha256'], p
assert frames == 28297
for row in reviews['records']:
    assert hashlib.sha256((base / row['image']).read_bytes()).hexdigest() == row['image_sha256']
assert hashlib.sha256((base / 'narration/spoken.txt').read_bytes()).hexdigest() == plan['script_sha256']
print(f"PASS: {len(manifest['records'])} manifest entries, 108 selected sources, exact references and {frames} native frames. No new human/media review claimed.")
