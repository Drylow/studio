"""Stream the checked long film to GoFile; send one kit to the dedicated Discord."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from dotenv import load_dotenv
import requests

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'output/nature-sleep/garden-production'
DELIVERY = OUT / 'delivery'
VIDEO = DELIVERY / 'Silent-Little-Worlds-The-Lantern-Garden-2-Hours.mp4'


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value, private=False):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    if private:
        os.chmod(path, 0o600)


def fingerprint(path):
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            sha.update(chunk)
            md5.update(chunk)
    return {'name': path.name, 'bytes': path.stat().st_size, 'sha256': sha.hexdigest(), 'md5': md5.hexdigest()}


def kit():
    timeline = json.loads((OUT / 'timeline.json').read_text())
    titles = ['Rainy Night in the Little Lantern Garden | 2 Hours of Cozy Sleep Stories',
              'A Quiet Evening in the Lantern Garden | Gentle Bedtime Stories for Adults',
              'Fall Asleep in a Cozy Rainy Garden | 2 Hours of Peaceful Stories']
    chapter_lines = []
    for i, c in enumerate(timeline['chapters']):
        sec = int(c['start']) if i else 0
        stamp = f'{sec // 3600}:{sec // 60 % 60:02}:{sec % 60:02}' if sec >= 3600 else f'{sec // 60:02}:{sec % 60:02}'
        chapter_lines.append(stamp + ' ' + c['title'])
    description = (
        'Settle beneath the pergola in a little lantern garden, with a warm cup, a soft blanket and gentle rain around you. '
        'Pip the ginger cat is asleep beside you, the greenhouse glows through the leaves, and the pond catches the lamplight.\n\n'
        'These eight connected, original bedtime stories share one peaceful garden: tending the lanterns with Elias, '
        'visiting June in the conservatory, watching Ada mend a blanket, browsing with Niall in the reading room, '
        'sharing tea by the pond with Ruth, resting in Tomas’s garden kitchen, exploring Iona’s seed library, '
        'and returning to the pergola as Mara settles the garden for the night. Gentle English narration accompanies '
        'the two-hour evening, with soft rain, quiet water and very subtle background music.\n\n'
        'Listen with the screen on or let the garden unfold in your imagination. English captions are optional; '
        'turn them on with YouTube’s CC button if you would like to follow along.\n\n'
        'CHAPTERS\n' + '\n'.join(chapter_lines) + '\n\n'
        'Silent Little Worlds creates original, fictional bedtime stories for adults. '
        'Original writing, ambient music and sound design, with AI-assisted artwork and narration. '
        'This is an imagined garden, created for a quiet evening.\n\n'
        '#SleepStory #BedtimeStories #CozyGarden')
    tags = 'sleep story, bedtime stories for adults, cozy sleep stories, lantern garden, rain ambience, peaceful garden, gentle storytelling, Silent Little Worlds, relaxing stories, sleep narration'
    pinned = 'Which quiet corner of the garden would you choose for a peaceful evening? Wishing you a restful night. 🌙'
    text = ('SILENT LITTLE WORLDS — EPISODE 01: THE LANTERN GARDEN\n\nTITLE OPTIONS\n' + '\n'.join(f'{i+1}. {t}' for i,t in enumerate(titles)) +
            '\n\nDESCRIPTION\n' + description + '\n\nTAGS\n' + tags + '\n\nPINNED COMMENT\n' + pinned +
            '\n\nUPLOAD NOTES (not part of the public description)\n'
            'Duration: 2:00:00. English original fiction. 1920x1080 / 30 fps.\n'
            'Upload the JPG as the thumbnail. The thumbnail is an actual frame from this film.\n'
            'YouTube Studio > Subtitles > English > Upload file > With timing: choose the supplied SRT.\n'
            'The video has no burned-in subtitles. The SRT must be added separately for CC to work.\n'
            'Set the title you prefer from the three options above. No mid-roll interruption is recommended for this sleep format.\n'
            'Original materials reduce reliance on third-party footage; monetization approval is not guaranteed.\n')
    (DELIVERY / 'Publication-Kit-English.txt').write_text(text, encoding='utf-8')
    script = '\n\n'.join(p.read_text(encoding='utf-8').strip() for p in sorted((HERE / 'script').glob('*.txt')))
    (DELIVERY / 'Full-Story-English.txt').write_text(script + '\n', encoding='utf-8')
    save(OUT / 'publication.json', {'titles': titles, 'description': description, 'tags': tags, 'pinned_comment': pinned})
    print(json.dumps({'kit_ready': True, 'title_options': len(titles), 'chapters': len(chapter_lines), 'description_chars': len(description)}))


def upload():
    if (HERE / 'HOLD.json').exists():
        raise RuntimeError('User changed the first-video direction; this garden episode is on hold')
    file = fingerprint(VIDEO)
    technical = json.loads((OUT / 'technical-review.json').read_text())
    editorial = json.loads((OUT / 'editorial-review.json').read_text())
    if not technical.get('technical_pass') or technical.get('sha256') != file['sha256'] or not editorial.get('approved_for_delivery') or editorial.get('sha256') != file['sha256']:
        raise RuntimeError('Matching final technical and editorial review required')
    receipt, pending = OUT / 'gofile-receipt.json', OUT / 'gofile-pending.json'
    if receipt.exists():
        old = json.loads(receipt.read_text())
        if old['file'] != file:
            raise RuntimeError('Existing delivery belongs to another file')
        print(json.dumps({'status': 'already-uploaded', 'url': old['url']}))
        return
    if pending.exists():
        raise RuntimeError('Uncertain upload retained; inspect before resubmission')
    response = requests.get('https://api.gofile.io/servers', timeout=(15, 30))
    response.raise_for_status()
    servers = response.json()['data']['servers']
    servers = [s for s in servers if re.fullmatch(r'store[a-z0-9-]+', str(s.get('name', '')))]
    server = next((s for s in servers if s.get('zone') == 'eu'), servers[0])
    save(pending, {'file': file, 'started': now()})
    private = OUT / 'gofile-response-private.json'
    # curl streams multipart directly from disk without loading the full movie into RAM.
    result = subprocess.run(['curl', '--silent', '--show-error', '--connect-timeout', '20', '--max-time', '1800',
        '--request', 'POST', '--form', f'file=@{VIDEO};type=video/mp4', '--output', str(private), '--write-out', '%{http_code}',
        'https://' + server['name'] + '.gofile.io/uploadFile'], capture_output=True, text=True)
    if private.exists():
        os.chmod(private, 0o600)
    if result.returncode != 0 or result.stdout.strip() != '200':
        raise RuntimeError('Upload outcome uncertain; private response and pending retained')
    data = json.loads(private.read_text())
    if data.get('status') != 'ok':
        raise RuntimeError('GoFile did not confirm upload')
    data = data['data']
    if data.get('md5') != file['md5'] or int(data.get('size', -1)) != file['bytes'] or fingerprint(VIDEO) != file:
        raise RuntimeError('Remote checksum/size mismatch')
    page = data.get('downloadPage', '')
    if not re.fullmatch(r'https://gofile\.io/d/[A-Za-z0-9]+', page):
        raise RuntimeError('Invalid download page')
    save(receipt, {'url': page, 'file': file, 'md5_and_size_verified': True, 'uploaded_at': now()})
    pending.unlink()
    print(json.dumps({'status': 'upload-confirmed', 'url': page, 'bytes_verified': file['bytes']}))


def discord(send):
    if send and (HERE / 'HOLD.json').exists():
        raise RuntimeError('User changed the first-video direction; this garden episode must not be sent')
    load_dotenv(ROOT / '.env', override=False)
    gofile = json.loads((OUT / 'gofile-receipt.json').read_text())
    files = [DELIVERY / name for name in ['Silent-Little-Worlds-Thumbnail.jpg', 'Silent-Little-Worlds-English.srt',
                                         'Publication-Kit-English.txt', 'Full-Story-English.txt']]
    publication = json.loads((OUT / 'publication.json').read_text())
    payload = {'username': 'Silent Little Worlds', 'allowed_mentions': {'parse': []},
        'content': 'Silent Little Worlds — Le jardin des lanternes, 2 h, 1080p. Le MP4 est sur GoFile ; miniature, sous-titres anglais activables, titres, description et histoire sont joints.',
        'embeds': [{'title': publication['titles'][0], 'url': gofile['url'],
            'description': '**Télécharger la vidéo :** ' + gofile['url'] + '\n\nHuit histoires originales en anglais dans un jardin cosy, voix douce, pluie, petit bassin et musique discrète. '
            'Le texte ne reste pas incrusté à l’écran : ajoute le SRT dans YouTube Studio pour activer CC. '
            'Trois titres au choix et les chapitres sont dans le kit.',
            'color': 10261310, 'image': {'url': 'attachment://' + files[0].name}}],
        'attachments': [{'id': i, 'filename': p.name} for i, p in enumerate(files)]}
    hashes = [fingerprint(p) for p in files]
    digest = hashlib.sha256((json.dumps(payload, sort_keys=True) + json.dumps(hashes, sort_keys=True)).encode()).hexdigest()
    save(OUT / 'discord-payload-review.json', payload)
    if not send:
        print(json.dumps({'dry_run': True, 'url': gofile['url'], 'attachments': [p.name for p in files], 'total_attachment_bytes': sum(p.stat().st_size for p in files)}))
        return
    webhook = os.getenv('DISCORD_WEBHOOK_QUIET_LITTLE_WORLDS', '')
    if not re.fullmatch(r'https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+', webhook):
        raise RuntimeError('Dedicated webhook missing; no fallback')
    pending, receipt = OUT / 'discord-pending.json', OUT / 'discord-receipt.json'
    with (OUT / 'discord.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if receipt.exists():
            if json.loads(receipt.read_text())['fingerprint'] != digest:
                raise RuntimeError('Existing Discord delivery differs')
            print('Discord already confirmed; no duplicate.')
            return
        if pending.exists():
            raise RuntimeError('Uncertain Discord send retained')
        check = requests.get(webhook, timeout=(15, 30))
        check.raise_for_status()
        if str(check.json().get('id')) != webhook.split('/')[-2]:
            raise RuntimeError('Discord destination mismatch')
        save(pending, {'fingerprint': digest, 'started': now()})
        with ExitStack() as stack:
            attached = [(f'files[{i}]', (p.name, stack.enter_context(p.open('rb')), 'image/jpeg' if i == 0 else 'text/plain; charset=utf-8')) for i, p in enumerate(files)]
            response = requests.post(webhook, params={'wait': 'true'}, data={'payload_json': json.dumps(payload)}, files=attached, timeout=(20, 120))
        save(OUT / 'discord-response-private.json', {'status_code': response.status_code, 'body': response.json()}, private=True)
        response.raise_for_status()
        message = response.json()
        if sorted(x['filename'] for x in message.get('attachments', [])) != sorted(p.name for p in files) or not str(message.get('id', '')).isdigit():
            raise RuntimeError('Discord attachment confirmation incomplete')
        # Read back the exact message to confirm all four small attachments.
        readback = requests.get(webhook + '/messages/' + str(message['id']), timeout=(15, 30))
        readback.raise_for_status()
        if sorted(x['filename'] for x in readback.json().get('attachments', [])) != sorted(p.name for p in files):
            raise RuntimeError('Discord readback incomplete')
        save(receipt, {'message_id': str(message['id']), 'fingerprint': digest, 'attachments': hashes,
                       'gofile_url': gofile['url'], 'confirmed_at': now(), 'readback_confirmed': True})
        pending.unlink()
        print('Discord: final video link and four attachments confirmed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=['kit', 'upload', 'discord'])
    parser.add_argument('--send', action='store_true')
    args = parser.parse_args()
    try:
        if args.step == 'discord':
            discord(args.send)
        else:
            globals()[args.step]()
    except Exception as exc:
        print('Delivery stopped safely: ' + type(exc).__name__)
        raise SystemExit(1)
