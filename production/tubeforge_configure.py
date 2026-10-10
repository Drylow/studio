"""Configure a supplied TubeForge installation using private studio settings."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

from dotenv import dotenv_values
from common import REPO
from services import media


def configure(root):
    root = Path(root).resolve()
    private = dotenv_values(Path(REPO) / '.env')
    spec = importlib.util.spec_from_file_location('tubeforge_config', root / 'app/config.py')
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    if not private.get('AI_API_KEY') or not private.get('ALGROW_API_KEY'):
        raise ValueError('Studio proxy and Algrow credentials are required')
    backup = root / '.env.from-archive'
    if not backup.exists():
        shutil.copy2(root / '.env', backup)
    config.update({'PROXY_BASE_URL': private['AI_BASE_URL'], 'PROXY_API_KEY': private['AI_API_KEY'],
        'ELEVENLABS_API_KEY': '', 'SCRIPT_MODEL': private['AI_TEXT_MODEL'],
        'FAST_MODEL': private.get('AI_FAST_MODEL') or private['AI_TEXT_MODEL'],
        'STUDIO_ROOT': str(Path(REPO)), 'HOST': '127.0.0.1', 'PORT': '8766',
        'FFMPEG': media.ffmpeg_bin(), 'FFPROBE': shutil.which('ffprobe') or '',
        'RENDER_BACKEND': 'auto', 'RENDER_CONCURRENCY': '1', 'RENDER_WORKERS': '4',
        'PROJECT_PARALLEL': '6', 'LOCAL_TTS_VRAM_GB': '4', 'LOCAL_TTS_WORKERS': '1'})
    voice = json.loads((Path(REPO) / 'chaines/edo-daily/01-production-2026-10-08/narration.json').read_text())['voice']
    for file in (root / 'data/styles').glob('*/style.json'):
        style = json.loads(file.read_text(encoding='utf-8'))
        style.setdefault('voice', {}).update(provider='algrow', voice_id=voice['id'], voice_name='Voix historique du studio', speed=voice['speed'])
        if private.get('AI_IMAGE_MODEL'):
            style.setdefault('visuals', {})['image_model'] = private['AI_IMAGE_MODEL']
            style.setdefault('thumbnail', {})['model'] = private['AI_IMAGE_MODEL']
        file.write_text(json.dumps(style, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    channels = root / 'data/channels.json'
    if channels.exists():
        data = json.loads(channels.read_text(encoding='utf-8'))
        for channel in data:
            channel['voice'] = {'provider': 'algrow', 'voice_id': voice['id'], 'speed': voice['speed']}
            channel['auto_resolve'] = False
        channels.write_text(json.dumps(data, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print('Private proxy configured; Algrow selected; local-only server; GPU renders serialized. No keys printed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    configure(parser.parse_args().directory)
