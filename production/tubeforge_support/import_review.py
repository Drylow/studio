"""Import an already reviewed excerpt, without authoring or generating anything."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from . import config, store


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def import_review(directory):
    studio = Path(config.get('STUDIO_ROOT')).resolve()
    directory = Path(directory).resolve()
    plan, reviews = load(directory / 'timeline.json'), load(directory / 'format-review.json')
    if plan['phase'] != 'review-excerpt-NOT-complete-episode':
        raise ValueError('Only explicitly reviewed excerpts may be imported')
    shots = plan['shots']
    for shot in shots:
        path = studio / shot['image']
        review = reviews[shot['id']]
        if not review['accepted'] or digest(path) != shot['sha256'] or review['sha256'] != shot['sha256']:
            raise ValueError('Reviewed image changed: ' + shot['id'])
        for ref in shot['references']:
            if digest(studio / ref['path']) != ref['sha256']:
                raise ValueError('Reference changed: ' + ref['path'])
    text = ' '.join(s['narration'] for s in shots)
    clock = load(directory.parent / 'authoring_words.json')['words'][:len(text.split())]
    if [w['w'] for w in clock] != text.split():
        raise ValueError('Excerpt does not match the authored word clock')
    p = store.create_project('Edo Daily - extrait 3 minutes - test TubeForge', store.list_styles()[0]['id'],
                             mode='review', custom_script=text, characters=[])
    p.update(codex_directed=True, technical_test=True, prompts_approved=True,
             source_review_directory=str(directory), source_timeline=plan)
    p['settings']['visuals'].update(captions=False, auto_characters=False, aspect='16:9')
    p['settings']['thumbnail']['count'] = 0
    p['auto_promo_shorts'] = 0
    pdir = store.project_dir(p['id'])
    (pdir / 'images').mkdir(exist_ok=True)
    shutil.copy2(directory / 'excerpt.mp3', pdir / 'voice.mp3')
    p['voiceover'] = {'file': 'voice.mp3', 'duration': plan['end'], 'provider': 'algrow',
                      'voice': p['settings']['voice']['voice_id'], 'audio_sha256': digest(pdir / 'voice.mp3')}
    p['scenes'] = []
    for index, shot in enumerate(shots, 1):
        target = f'images/{index:03}.png'
        shutil.copy2(studio / shot['image'], pdir / target)
        p['scenes'].append({'id': index, 'start': shot['start'], 'end': shot['end'], 'text': shot['narration'],
            'prompt': 'Renderer-only import. Original Codex authoring and ordered references retained in source_timeline.',
            'image': target, 'status': 'done', 'motion': shot['motion'], 'codex_receipt': shot})
    pos = 0
    words = []
    for word in clock:
        start = text.index(word['w'], pos)
        pos = start + len(word['w'])
        words.append({**word, 'c0': start, 'c1': pos})
    store.save_words(p['id'], words)
    for key in ('script', 'voiceover', 'visuals'):
        p['steps'][key]['state'] = 'done'
    store.save_project(p)
    return p


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    print(import_review(parser.parse_args().directory)['id'])
