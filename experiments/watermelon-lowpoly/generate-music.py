"""Generate the explicitly requested music once; keep credentials outside Git."""
import argparse, json, os, sys, urllib.request, urllib.error
from pathlib import Path
from dotenv import dotenv_values

parser = argparse.ArgumentParser()
parser.add_argument('--env-file', type=Path, default=Path('../../.env'))
args = parser.parse_args()
destination = Path('assets/chill-game-music.mp3')
if destination.exists():
    print('Existing music retained; no paid regeneration.')
    sys.exit(0)
settings = dotenv_values(args.env_file) if args.env_file.exists() else {}
key = (os.environ.get('ELEVENLABS_API_KEY') or settings.get('ELEVENLABS_API_KEY') or '').strip()
if not key:
    sys.exit('ELEVENLABS_API_KEY is not configured in the selected environment file.')
request_data = json.loads(Path('music-request.json').read_text(encoding='utf-8'))
request = urllib.request.Request(
    'https://api.elevenlabs.io/v1/music?output_format=mp3_44100_128',
    data=json.dumps(request_data).encode(),
    headers={'xi-api-key': key, 'Content-Type': 'application/json'}, method='POST')
print(f"Requesting {request_data['music_length_ms'] / 1000:g} seconds of instrumental game music from ElevenLabs...", flush=True)
try:
    with urllib.request.urlopen(request, timeout=240) as response:
        content_type = response.headers.get('Content-Type', '')
        if 'audio' not in content_type and 'octet-stream' not in content_type:
            sys.exit('Unexpected response type; no music file saved.')
        audio = response.read()
except urllib.error.HTTPError as error:
    detail = error.read().decode('utf-8', errors='replace').replace(key, '[redacted]')
    sys.exit(f'ElevenLabs HTTP {error.code}: {detail[:1200]}')
except urllib.error.URLError:
    sys.exit('ElevenLabs network request failed; no automatic paid retry.')
if len(audio) < 1000:
    sys.exit('Empty audio response; no music file saved.')
destination.parent.mkdir(exist_ok=True)
destination.write_bytes(audio)
Path('music-source.json').write_text(json.dumps({
    'provider': 'ElevenLabs', 'file': str(destination.as_posix()),
    'requested_duration_s': request_data['music_length_ms'] / 1000, 'instrumental': True,
    'request_file': 'music-request.json', 'bytes': len(audio),
    'api_documentation': 'https://elevenlabs.io/docs/api-reference/music/compose'
}, indent=2), encoding='utf-8')
print(f'Music saved: {destination} ({len(audio)} bytes).')
