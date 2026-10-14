"""Two-pass level correction of the recovered original voice, with no TTS."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

import av
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent
SOURCE = Path('/workspace/recovery/voice-history/samurai-native-derived-voice.mp3')
DESTINATION = ROOT / 'voice-derived' / 'samurai-original-level-normalized.flac'
EXPECTED = '976f1493619e9266301dc772af362f5a7fe5602433f2a8b66cc728fd1e3a2671'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED
DESTINATION.parent.mkdir(exist_ok=True)
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
measure = subprocess.run([ffmpeg, '-hide_banner', '-nostdin', '-i', str(SOURCE),
                         '-af', 'loudnorm=I=-17:TP=-1.5:LRA=11:print_format=json',
                         '-f', 'null', '-'], capture_output=True, text=True, check=True)
measurements = json.loads(re.findall(r'\{\s*"input_i".*?\}', measure.stderr, re.S)[-1])
filter_text = ('loudnorm=I=-17:TP=-1.5:LRA=11:linear=true:print_format=json:'
               f"measured_I={measurements['input_i']}:"
               f"measured_TP={measurements['input_tp']}:"
               f"measured_LRA={measurements['input_lra']}:"
               f"measured_thresh={measurements['input_thresh']}:"
               f"offset={measurements['target_offset']}")
converted = subprocess.run([ffmpeg, '-hide_banner', '-nostdin', '-y', '-i', str(SOURCE),
                           '-af', filter_text, '-ac', '1', '-ar', '44100',
                           '-c:a', 'flac', str(DESTINATION)], capture_output=True, text=True, check=True)
verified = subprocess.run([ffmpeg, '-hide_banner', '-nostdin', '-i', str(DESTINATION),
                          '-af', 'loudnorm=I=-17:TP=-1.5:LRA=11:print_format=json',
                          '-f', 'null', '-'], capture_output=True, text=True, check=True)
final_levels = json.loads(re.findall(r'\{\s*"input_i".*?\}', verified.stderr, re.S)[-1])
def audio_count(path):
    with av.open(str(path)) as container:
        rate = container.streams.audio[0].codec_context.sample_rate
        samples = sum(frame.samples for frame in container.decode(audio=0))
    return samples, rate
original_count = audio_count(SOURCE)
derived_count = audio_count(DESTINATION)
assert original_count == derived_count, (original_count, derived_count)
proof = {'schema':'samurai-level-only-derived-voice-v1', 'source':str(SOURCE),
         'source_sha256':EXPECTED, 'derived_file':str(DESTINATION),
         'derived_sha256':hashlib.sha256(DESTINATION.read_bytes()).hexdigest(),
         'measured_original':measurements, 'measured_final':final_levels,
         'decoded_samples':derived_count[0], 'sample_rate':derived_count[1],
         'duration_seconds':derived_count[0]/derived_count[1], 'drift_ms':0,
         'paid_tts_calls':0, 'operation':'two-pass loudness correction only'}
(DESTINATION.parent/'normalization-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
print(json.dumps(proof))
