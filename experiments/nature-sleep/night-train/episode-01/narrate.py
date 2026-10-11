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

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'output/nature-sleep/night-train-production'
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from services.tts import _ai33_call, _download, _open, align_to_text, _norm

VOICE = 'elevenlabs_VsVIOTkd9zjLUVaQO9TA'
SPEED = '0.75'


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


def render(chapter, number, paragraphs):
    name = f'{chapter}-{number:02}'
    folder = OUT / 'narration' / name
    folder.mkdir(parents=True, exist_ok=True)
    fields = dict(text=' '.join(' '.join(x.split()) for x in paragraphs),
                  voice_id=VOICE, speed=SPEED, with_transcript='true')
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
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
    args = parser.parse_args()
    load_dotenv(ROOT / '.env', override=False)
    jobs = []
    for chapter in args.chapters:
        paras = [p.strip() for p in (HERE / 'script' / f'{chapter}.txt').read_text().split('\n\n') if p.strip()]
        for k in range(0, len(paras), 6):
            jobs.append((chapter, k // 6, paras[k:k + 6]))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda x: render(*x), jobs))
    print(json.dumps({'parts': len(results), 'duration': round(sum(x['duration'] for x in results), 2),
                      'words': sum(len(x['words']) for x in results)}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Provider responses and signed download links must not enter the task transcript.
        print(f'Stopped safely: {type(exc).__name__}', file=sys.stderr)
        raise SystemExit(1)
