"""Independent timing/decode checks and review sheets for a renderer-only import."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageStat

from common import REPO
from services import media


def selection(indices):
    # A long left-associative sum exceeds the media filter parser's recursion limit.
    if len(indices) == 1:
        return f'eq(n,{indices[0]})'
    mid = len(indices) // 2
    return f'({selection(indices[:mid])}+{selection(indices[mid:])})'


def verify(pid):
    if not re.fullmatch(r'[a-z0-9-]+', pid):
        raise ValueError('Invalid project ID')
    root = Path(REPO) / 'work/TubeForge/data/projects' / pid
    p = json.loads((root / 'project.json').read_text(encoding='utf-8'))
    video = (root / p['render']['file']).resolve()
    if not video.is_relative_to(root.resolve()):
        raise ValueError('Video escapes project directory')
    for shot in p['scenes']:
        path = root / shot['image']
        if hashlib.sha256(path.read_bytes()).hexdigest() != shot['codex_receipt']['sha256']:
            raise ValueError('Reviewed source changed')
    probe = shutil.which('ffprobe')
    if not probe:
        raise ValueError('Independent verification requires ffprobe')
    result = subprocess.run([probe, '-v', 'error', '-count_frames', '-show_streams', '-of', 'json', str(video)],
                             capture_output=True, text=True, check=True)
    if result.stderr.strip():
        raise ValueError(result.stderr)
    streams = json.loads(result.stdout)['streams']
    picture = next(s for s in streams if s['codec_type'] == 'video')
    audio = next(s for s in streams if s['codec_type'] == 'audio')
    duration = media.duration(str(root / p['voiceover']['file']))
    frames = round(duration * 24)
    if (picture['width'], picture['height'], picture['r_frame_rate'], int(picture['nb_read_frames'])) != (1920, 1080, '24/1', frames):
        raise ValueError('Picture geometry or frame clock changed')
    if abs(float(picture['duration']) - frames / 24) > .5 / 24 or abs(float(audio['duration']) - duration) > .15:
        raise ValueError('Picture/audio timing mismatch')
    decoded = subprocess.run([media.ffmpeg_bin(), '-v', 'error', '-i', str(video), '-f', 'null', '-'],
                              capture_output=True, text=True, check=True)
    if decoded.stderr.strip():
        raise ValueError(decoded.stderr)
    check = root / 'render/check'
    check.mkdir(exist_ok=True)
    captures = [(s['id'], round((s['start'] + (s['end'] - s['start']) * fraction) * 24))
                for s in p['scenes'] for fraction in (.2, .5, .8)]
    indices = [frame for _, frame in captures]
    if indices != sorted(set(indices)):
        raise ValueError('Review capture clock overlaps')
    selector = selection(indices)
    subprocess.run([media.ffmpeg_bin(), '-v', 'error', '-y', '-i', str(video),
                    '-vf', f"select='{selector}',scale=640:360", '-fps_mode', 'vfr',
                    '-q:v', '2', str(check / '%03d.jpg')], check=True)
    for offset in range(0, len(captures), 18):
        sheet = Image.new('RGB', (1920, 2280), '#181818')
        draw = ImageDraw.Draw(sheet)
        for index, (sid, frame) in enumerate(captures[offset:offset + 18]):
            with Image.open(check / f'{offset + index + 1:03}.jpg') as image:
                if max(ImageStat.Stat(image).stddev) < 5:
                    raise ValueError('Blank review frame')
                x, y = index % 3 * 640, index // 3 * 380
                sheet.paste(image, (x, y))
                draw.text((x + 8, y + 361), f'Shot {sid:02} - {frame / 24:.2f}s', fill='white')
        sheet.save(check / f'sheet_{offset // 18 + 1:02}.jpg', quality=95)
    receipt = {'decoded_without_errors': True, 'picture_frames': frames, 'capture_count': len(captures),
               'streams': streams, 'manual_review_pending': True,
               'video_sha256': hashlib.sha256(video.read_bytes()).hexdigest(),
               'note': 'Technical verification only; no audio listening or perfect creative continuity claimed.'}
    (check / 'technical.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(f'{frames} frames checked; {len(captures)} captures ready for visual review')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('project_id')
    verify(parser.parse_args().project_id)
