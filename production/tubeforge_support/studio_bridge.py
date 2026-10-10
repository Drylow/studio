"""Execute the studio renderer/provider in an isolated, cancellable process."""
import asyncio
import json
import os
from pathlib import Path
import re
import uuid

from . import config, events, store
from .util import now


async def execute(payload, directory, progress=None):
    studio = Path(config.get('STUDIO_ROOT')).resolve()
    python = studio / 'venv/Scripts/python.exe'
    if not python.is_file():
        raise RuntimeError('Studio Python missing; rerun the TubeForge setup')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    identity = uuid.uuid4().hex
    request, result, cancel = [directory / f'{identity}.{suffix}' for suffix in ('job.json', 'result.json', 'cancel')]
    request.write_text(json.dumps({**payload, 'cancel': str(cancel)}), encoding='utf-8')
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env['PYTHONIOENCODING'] = 'utf-8'
    proc = await asyncio.create_subprocess_exec(str(python), str(studio / 'production/tubeforge_bridge.py'),
        str(request), str(result), cwd=studio, env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        creationflags=0x08000000 if os.name == 'nt' else 0)
    errors = asyncio.create_task(proc.stderr.read())
    try:
        while line := await proc.stdout.readline():
            if progress:
                try:
                    event = json.loads(line)
                    progress(round(event['fraction'] * 1000), 1000, event['message'])
                except (ValueError, KeyError):
                    pass
        code = await proc.wait()
        error = await errors
        if code:
            raise RuntimeError('Studio bridge failed: ' + error.decode(errors='replace')[-1200:])
        return json.loads(result.read_text(encoding='utf-8'))
    finally:
        if proc.returncode is None:
            cancel.touch()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
            except asyncio.TimeoutError:
                if os.name == 'nt':
                    killer = await asyncio.create_subprocess_exec('taskkill', '/PID', str(proc.pid), '/T', '/F',
                        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                        creationflags=0x08000000)
                    await killer.wait()
                else:
                    proc.kill()
                await proc.wait()
        await errors


async def render(p, jobs_scenes, total_frames, width, height, fps, out_dir, progress=None):
    audio = (store.project_dir(p['id']) / p['voiceover']['file']).resolve()
    scenes = [{'image': s['image'], 'start': s['f0'] / fps, 'motion': s['motion']} for s in jobs_scenes]
    result = await execute({'action': 'render', 'voice': str(audio), 'duration': p['voiceover']['duration'],
        'scenes': scenes, 'width': width, 'height': height, 'fps': fps,
        'motion_strength': 0.12 * float(p['settings']['visuals'].get('motion_strength', 1)),
        'workdir': str((out_dir / 'studio').resolve()), 'output': str((out_dir / 'final.mp4').resolve())},
        out_dir / 'bridge', progress)
    if result['video_frames'] != total_frames:
        raise RuntimeError('OVNI frame count disagrees with the TubeForge narration clock')
    title = re.sub(r'[\\/:*?"<>|]+', '', p.get('title') or 'video').strip()[:80] or 'video'
    p['render'] = {'file': 'render/final.mp4', 'srt': 'render/subtitles.srt', 'duration': total_frames / fps,
        'ts': now(), 'width': width, 'height': height, 'download_name': title + '.mp4',
        'backend': 'ovni', 'render_seconds': result['render_seconds'], 'qa_pending': True,
        'publication_ready': False}
    store.save_project(p)
    events.log(f"OVNI : {total_frames} images video, rendu en {result['render_seconds']:.1f} s", 'ok')
    return p['render']


async def voice(text, settings, out_dir, progress=None):
    languages = {'english': 'en', 'french': 'fr'}
    settings = {'voice_id': settings['voice_id'], 'speed': settings.get('speed', 1),
                'language': languages.get(str(settings.get('language', 'English')).lower(), 'en')}
    if progress:
        progress(0, 1)
    result = await execute({'action': 'voice', 'text': text, 'settings': settings,
        'workdir': str((out_dir / 'tts_cache').resolve()), 'output': str((out_dir / 'voice.mp3').resolve())},
        out_dir / 'bridge')
    if progress:
        progress(1, 1)
    return result
