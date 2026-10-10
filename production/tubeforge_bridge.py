"""Technical render/voice bridge; never authors scripts, prompts or references."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from common import REPO
from services import media, render_ovni, tts


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp.json')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def render(job):
    actual = media.duration(job['voice'])
    if abs(actual - job['duration']) > 0.1:
        raise ValueError('TubeForge voice duration changed; remeasure the scene clock')
    return render_ovni.render_video(job['workdir'], job['scenes'], job['voice'], job['output'],
        width=job['width'], height=job['height'], fps=job['fps'], tail=0,
        motion_strength=job['motion_strength'], transition='none', quality='high',
        captions={'mode': 'none'}, normalize=False,
        cancelled=lambda: Path(job['cancel']).exists(),
        progress=lambda p, message: print(json.dumps({'fraction': p, 'message': message}), flush=True))


def voice(job):
    text, settings = job['text'], job['settings']
    if len(text.strip()) < 200:
        raise ValueError('Algrow requires at least 200 characters; provide a longer authored excerpt')
    key = hashlib.sha256(json.dumps({'text': text, 'settings': settings}, sort_keys=True).encode()).hexdigest()
    root = Path(job['workdir'])
    root.mkdir(parents=True, exist_ok=True)
    cached, receipt = root / f'algrow-{key}.mp3', root / f'algrow-{key}.json'
    if receipt.exists() and cached.exists():
        result = json.loads(receipt.read_text(encoding='utf-8'))
        if hashlib.sha256(cached.read_bytes()).hexdigest() != result['audio_sha256']:
            raise ValueError('Cached narration changed')
    else:
        raw = tts.synthesize(text, str(cached), provider='algrow', voice=settings['voice_id'],
                             speed=float(settings.get('speed', 1)), lang=settings.get('language', 'en'))
        tokens = list(re.finditer(r'\S+', text))
        aligned = tts.align_to_text(raw['words'], text)
        if len(tokens) != len(aligned):
            raise ValueError('Voice alignment lost authored words')
        words = [{**word, 'c0': token.start(), 'c1': token.end()}
                 for token, word in zip(tokens, aligned)]
        result = {'file': 'voice.mp3', 'duration': media.duration(str(cached)), 'words': words,
                  'audio_sha256': hashlib.sha256(cached.read_bytes()).hexdigest(), 'provider': 'algrow'}
        save(receipt, result)
    shutil.copy2(cached, job['output'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('job')
    parser.add_argument('result')
    args = parser.parse_args()
    job = json.loads(Path(args.job).read_text(encoding='utf-8'))
    if job['action'] not in ('render', 'voice'):
        raise ValueError('Unknown technical bridge action')
    save(args.result, globals()[job['action']](job))
