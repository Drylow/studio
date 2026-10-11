"""Resume-safe narration using the configured voice service; private jobs stay in output/."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import difflib
import re
import shutil

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'output/nature-sleep/garden-production'
REUSE_ROOT = ROOT / 'output/nature-sleep/night-train-production/narration'
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from services.tts import _ai33_call, _download, _open, align_to_text, _norm

VOICE = 'elevenlabs_VsVIOTkd9zjLUVaQO9TA'
SPEED = '0.75'
CHAPTER_TITLES = {
    '00-welcome': 'Welcome to the lantern garden',
    '01-lanterns': 'The lantern keeper',
    '02-conservatory': 'The conservatory in the rain',
    '03-mender': 'The mender’s blanket',
    '04-reading-room': 'The garden reading room',
    '05-pond-room': 'Tea beside the pond',
    '06-garden-kitchen': 'The orchard kitchen',
    '07-seed-library': 'The seed library',
    '08-last-lantern': 'The last garden lantern',
}


def request_fields(paragraphs):
    return dict(text=' '.join(' '.join(x.split()) for x in paragraphs),
                voice_id=VOICE, speed=SPEED, with_transcript='true')


def request_digest(fields):
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def check_script(chapter, text):
    review = json.loads((HERE / 'script-review.json').read_text())
    item = review.get('scripts', {}).get(chapter, {})
    if (not review.get('approved_for_narration') or not item.get('approved_for_narration')
            or hashlib.sha256(text.encode()).hexdigest() != item.get('sha256')):
        raise ValueError(f'{chapter}: matching editorial review is required')
    if chapter not in CHAPTER_TITLES or not text.strip():
        raise ValueError('Unknown or empty garden chapter')
    stale = re.compile(r'\b(?:quiet little worlds|the little railway|night train|railway carriage|'
                       r'train compartment|train window|welcome aboard)\b', re.I)
    if stale.search(text):
        raise ValueError(f'{chapter}: old channel name or railway framing remains in garden text')
    if chapter == '00-welcome' and 'Silent Little Worlds' not in text:
        raise ValueError('Garden introduction must use the current channel name')


def reuse_index():
    """Index finished local requests only. A similar transcript never qualifies."""
    index = {}
    for path in sorted(REUSE_ROOT.glob('*/result.json')):
        data = json.loads(path.read_text())
        digest = data.get('request_sha256', '')
        if re.fullmatch(r'[0-9a-f]{64}', digest):
            index.setdefault(digest, []).append((path, data))
    return index


def exact_source(index, digest, fields):
    for result_path, data in index.get(digest, []):
        audio = (ROOT / data['audio']).resolve()
        transcript = result_path.parent / 'transcript-private.json'
        if not audio.is_relative_to(REUSE_ROOT.resolve()):
            raise RuntimeError('Reusable narration audio is outside the expected source folder')
        if data.get('voice') != VOICE or float(data.get('speed', -1)) != float(SPEED):
            raise RuntimeError('Reusable narration has different voice parameters')
        if ' '.join(w['w'] for w in data['words']) != fields['text']:
            raise RuntimeError('Request digest matches but reusable text differs')
        if data.get('text_match_ratio', 0) < .94:
            raise RuntimeError('Reusable narration did not pass the original transcript check')
        if not audio.is_file() or hashlib.sha256(audio.read_bytes()).hexdigest() != data['audio_sha256']:
            raise RuntimeError('Reusable narration audio checksum mismatch')
        if not transcript.is_file():
            raise RuntimeError('Reusable narration has no private timing transcript')
        json.loads(transcript.read_text())
        return result_path, data, audio, transcript
    return None


def copy_private(source, target):
    temporary = target.with_suffix(target.suffix + '.tmp')
    shutil.copyfile(source, temporary)
    os.chmod(temporary, 0o600)
    if hashlib.sha256(temporary.read_bytes()).digest() != hashlib.sha256(source.read_bytes()).digest():
        raise RuntimeError('Narration reuse copy failed checksum validation')
    temporary.replace(target)


def reuse_finished(source, folder, chapter, number, paragraphs):
    result_path, original, audio, transcript = source
    copy_private(audio, folder / 'voice.mp3')
    copy_private(transcript, folder / 'transcript-private.json')
    data = dict(original)
    data.update(id=f'{chapter}-{number:02}', chapter=chapter, part=number,
                audio=str((folder / 'voice.mp3').relative_to(ROOT)),
                paragraph_word_counts=[len(p.split()) for p in paragraphs],
                reused_from={'result': str(result_path.relative_to(ROOT)),
                             'id': original['id'], 'audio_sha256': original['audio_sha256']})
    save(folder / 'result.json', data)
    print(f'{data["id"]}: reused an exact completed request, no submission', flush=True)
    return data


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False))
    os.chmod(temp, 0o600)
    temp.replace(path)


def get_task(task):
    # Read failures never cause another billable submission.
    for attempt in range(5):
        try:
            return _ai33_call('GET', '/v1/task/' + task)
        except Exception:
            if attempt == 4:
                raise RuntimeError('Task status unreadable; existing task retained') from None
            time.sleep(3 * (attempt + 1))


def render(chapter, number, paragraphs, index):
    name = f'{chapter}-{number:02}'
    folder = OUT / 'narration' / name
    folder.mkdir(parents=True, exist_ok=True)
    fields = request_fields(paragraphs)
    digest = request_digest(fields)
    result_path, job_path = folder / 'result.json', folder / 'job-private.json'
    audio = folder / 'voice.mp3'
    if result_path.exists():
        data = json.loads(result_path.read_text())
        if data['request_sha256'] != digest:
            raise RuntimeError(f'{name}: text changed after production; use a new revision')
        if hashlib.sha256(audio.read_bytes()).hexdigest() != data['audio_sha256']:
            raise RuntimeError(f'{name}: cached audio hash mismatch')
        return data
    pending = folder / 'submission-pending.json'
    if job_path.exists():
        job = json.loads(job_path.read_text())
        if job['request_sha256'] != digest:
            raise RuntimeError(f'{name}: existing task belongs to different text')
    else:
        if pending.exists():
            raise RuntimeError(f'{name}: unresolved submission; check provider before retry')
        source = exact_source(index, digest, fields)
        if source is not None:
            return reuse_finished(source, folder, chapter, number, paragraphs)
        save(pending, {'request_sha256': digest, 'created': time.time()})
        # If this POST has an uncertain outcome, pending prevents a blind retry.
        job = _ai33_call('POST', '/v3/text-to-speech', fields)
        if not job.get('task_id'):
            save(folder / 'submission-response-private.json', job)
            raise RuntimeError(f'{name}: submission has no task identifier')
        job['request_sha256'] = digest
        save(job_path, job)
        pending.unlink()
        print(f'{name}: submitted', flush=True)
    started = time.monotonic()
    while True:
        status = get_task(job['task_id'])
        if status.get('status') == 'done':
            break
        if status.get('status') == 'error':
            save(folder / 'failure-private.json', status)
            raise RuntimeError(f'{name}: provider failed; task retained for diagnosis')
        if time.monotonic() - started > 1800:
            raise RuntimeError(f'{name}: still processing; resume the existing task later')
        time.sleep(6)
    meta = status.get('metadata') or {}
    save(folder / 'task-private.json', status)
    _download(meta['audio_url'], str(audio))
    with _open(meta['json_url'], 90) as response:
        raw = json.loads(response.read().decode())
    save(folder / 'transcript-private.json', raw)
    raw = raw[0] if isinstance(raw, list) else raw
    native = [{'w': x['text'], 's': round(x['start'], 3), 'e': round(x['end'], 3)}
              for x in raw.get('words', []) if x.get('type') == 'word']
    if not native:
        raise RuntimeError(f'{name}: missing native word timing')
    tokens = fields['text'].split()
    match = difflib.SequenceMatcher(None, [_norm(x) for x in tokens],
                                   [_norm(x['w']) for x in native], autojunk=False).ratio()
    if match < .94:
        raise RuntimeError(f'{name}: narration/text mismatch {match:.3f}; review required')
    duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                    'format=duration', '-of', 'default=nw=1:nk=1', str(audio)]))
    data = {'id': name, 'chapter': chapter, 'part': number,
            'request_sha256': digest, 'audio_sha256': hashlib.sha256(audio.read_bytes()).hexdigest(),
            'audio': str(audio.relative_to(ROOT)), 'duration': duration,
            'voice': VOICE, 'speed': float(SPEED), 'paragraph_word_counts': [len(p.split()) for p in paragraphs],
            'text_match_ratio': round(match, 5), 'words': align_to_text(native, fields['text'])}
    save(result_path, data)
    print(f'{name}: ready {duration:.1f}s, {len(tokens)} words, match {match:.3f}', flush=True)
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('chapters', nargs='+', help='Script filename stems, already reviewed')
    parser.add_argument('--plan', action='store_true', help='Read-only exact-cache plan; no copies or paid submissions')
    args = parser.parse_args()
    jobs = []
    for chapter in args.chapters:
        text = (HERE / 'script' / f'{chapter}.txt').read_text()
        check_script(chapter, text)
        paras = [p.strip() for p in text.split('\n\n') if p.strip()]
        for k in range(0, len(paras), 6):
            jobs.append((chapter, k // 6, paras[k:k + 6]))
    index = reuse_index()
    if args.plan:
        plan = []
        for chapter, number, paragraphs in jobs:
            fields = request_fields(paragraphs)
            digest = request_digest(fields)
            name = f'{chapter}-{number:02}'
            folder = OUT / 'narration' / name
            if (folder / 'result.json').exists():
                existing = json.loads((folder / 'result.json').read_text())
                if existing['request_sha256'] != digest:
                    raise RuntimeError('An existing garden result belongs to different text')
                if hashlib.sha256((folder / 'voice.mp3').read_bytes()).hexdigest() != existing['audio_sha256']:
                    raise RuntimeError('An existing garden result has an invalid audio checksum')
                state = 'garden_cached'
            elif (folder / 'job-private.json').exists():
                state = 'resume_existing_job'
            elif (folder / 'submission-pending.json').exists():
                state = 'unresolved_submission'
            else:
                state = 'reuse_exact_request' if exact_source(index, digest, fields) else 'new_request_needed'
            plan.append({'id': name, 'state': state, 'characters': len(fields['text']), 'request_sha256': digest})
        print(json.dumps({'parts': plan, 'counts': {s: sum(p['state'] == s for p in plan) for s in sorted({p['state'] for p in plan})}}, indent=2))
        return
    load_dotenv(ROOT / '.env', override=False)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda x: render(*x, index), jobs))
    print(json.dumps({'parts': len(results), 'duration': round(sum(x['duration'] for x in results), 2),
                      'words': sum(len(x['words']) for x in results)}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Provider responses and signed download links must not enter the task transcript.
        print(f'Stopped safely: {type(exc).__name__}', file=sys.stderr)
        raise SystemExit(1)
