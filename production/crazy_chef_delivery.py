"""Deliver verified Crazy Chef exports and a mobile kit to the channel webhook."""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

import requests

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / 'chaines/crazy-chef-3d/videos.json'
WORK = ROOT / 'work/crazy-chef-delivery'
STATE = WORK / 'state.json'

def local(name):
    result = (ROOT / name).resolve()
    if not result.is_relative_to(ROOT) or not result.is_file():
        raise RuntimeError('Missing or unsafe delivery asset: ' + name)
    return result

def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def save(state):
    WORK.mkdir(parents=True, exist_ok=True)
    pending = STATE.with_suffix('.tmp')
    pending.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    pending.replace(STATE)

def upload(path, state, label):
    sha = digest(path)
    cached = state.setdefault('uploads', {}).get(sha)
    if cached:
        print('Already uploaded: ' + label, flush=True)
        return cached
    print('Uploading: ' + label, flush=True)
    result = subprocess.run([
        'curl.exe', '--silent', '--show-error', '--fail', '--noproxy', '*',
        '--connect-timeout', '30', '--max-time', '1800',
        '-F', 'file=@' + str(path), 'https://upload.gofile.io/uploadfile'
    ], capture_output=True)
    if result.returncode:
        raise RuntimeError('GoFile upload failed for ' + label + '; curl exit ' + str(result.returncode))
    try:
        response = json.loads(result.stdout)
    except ValueError:
        raise RuntimeError('GoFile returned an unreadable response for ' + label) from None
    data = response.get('data') or {}
    if response.get('status') != 'ok' or not str(data.get('downloadPage', '')).startswith('https://gofile.io/d/'):
        raise RuntimeError('GoFile did not confirm the upload for ' + label)
    md5 = digest(path, 'md5')
    if data.get('md5') != md5 or int(data.get('size', -1)) != path.stat().st_size:
        raise RuntimeError('GoFile integrity mismatch for ' + label)
    receipt = {'url': data['downloadPage'], 'sha256': sha, 'md5': md5,
               'bytes': path.stat().st_size, 'filename': path.name}
    state['uploads'][sha] = receipt
    save(state)
    print('Upload verified: ' + label + ' — ' + receipt['url'], flush=True)
    return receipt

def webhook():
    for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('DISCORD_WEBHOOK_CRAZY_CHEF_3D='):
            value = line.split('=', 1)[1].strip().strip('\"\'')
            if value.startswith('https://discord.com/api/webhooks/'):
                return value.replace('/api/webhooks/', '/api/v10/webhooks/', 1)
    raise RuntimeError('The channel webhook is missing from .env')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--videos-only', action='store_true')
    args = parser.parse_args()
    config = json.loads(REGISTRY.read_text(encoding='utf-8'))
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    items = config['videos']
    for item in items:
        assert item['reviewed'] is True, 'Unreviewed video: ' + item['id']
        movie = local(item['file'])
        assert digest(movie) == item['sha256'].lower(), 'Changed export: ' + item['id']
        qa = local(item['qa']).read_text(encoding='utf-8').lower()
        assert item['sha256'].lower() in qa, 'QA does not identify this export: ' + item['id']
    print('All final video fingerprints and QA records verified.', flush=True)
    if args.videos_only:
        if not args.dry_run:
            for item in items:
                upload(local(item['file']), state, item['id'])
        return
    assets = [local(config['logo'])] + [local(item['cover']) for item in items]
    from PIL import Image
    for item, path in zip(items, assets[1:]):
        with Image.open(path) as im:
            # Permit the one-pixel rounding of native portrait image exports.
            assert abs(im.width - im.height * 9 / 16) <= 1, 'Cover must be 9:16: ' + item['id']
        assert path.stat().st_size < 9 * 1024 * 1024, 'Cover too large for Discord'
    url = webhook()
    if args.dry_run:
        print('Dry run: ' + str(len(items)) + ' verified videos, ' + str(len(assets)) + ' image attachments; no network writes.')
        return
    receipts = [upload(local(item['file']), state, item['id']) for item in items]
    channel_text = 'Channel name: ' + config['channel'] + '\nHandle: ' + config['handle'] + '\n\nDescription:\n' + config['bio'] + '\n'
    video_text = '\n\n'.join(item['title'] + '\n' + item['description'] + '\nVideo: ' + receipt['url'] for item, receipt in zip(items, receipts))
    kit = WORK / 'crazy-chef-3d-phone-kit.zip'
    with zipfile.ZipFile(kit, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        contents = [(path.name, path.read_bytes()) for path in assets]
        contents += [('channel.txt', channel_text.encode('utf-8')),
                     ('video-titles-and-captions.txt', video_text.encode('utf-8'))]
        for name, content in contents:
            entry = zipfile.ZipInfo(name, date_time=(2026, 10, 8, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(entry, content)
    kit_receipt = upload(kit, state, 'mobile kit')
    names = [p.name for p in assets]
    embeds = [{'title': config['channel'], 'description': config['bio'], 'color': 0x1C422E,
               'thumbnail': {'url': 'attachment://' + names[0]},
               'fields': [{'name': 'Channel name', 'value': config['channel']},
                          {'name': 'Handle', 'value': config['handle']},
                          {'name': 'Logo, covers & copy-ready text', 'value': kit_receipt['url']}]}]
    for item, receipt, name in zip(items, receipts, names[1:]):
        embeds.append({'title': item['title'], 'url': receipt['url'], 'description': item['description'],
                       'color': 0x1C422E, 'image': {'url': 'attachment://' + name},
                       'fields': [{'name': 'Final MP4 — verified', 'value': receipt['url']},
                                  {'name': 'Format', 'value': f"{item['seconds']} s · 1080 × 1920 · 60 FPS"}]})
    payload = {'username': config['channel'], 'content': '**Crazy Chef 3D — pack prêt à publier depuis ton téléphone**\n\n' +
               '**Description de la chaîne :**\n' + config['bio'] + '\n\nLes trois vidéos finales et les images sont ci-dessous. ' +
               'Kit complet : ' + kit_receipt['url'], 'embeds': embeds, 'allowed_mentions': {'parse': []}}
    signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    previous = state.get('discord', {}).get(signature)
    if previous:
        if previous.get('status') == 'sent':
            print('Discord delivery already confirmed; no duplicate sent.')
            return
        raise RuntimeError('A previous Discord send has an uncertain outcome; inspect it before retrying.')
    state.setdefault('discord', {})[signature] = {'status': 'pending', 'started': time.time()}
    save(state)
    for attempt in range(4):
        try:
            with ExitStack() as stack:
                files = [(f'files[{i}]', (path.name, stack.enter_context(path.open('rb')), 'image/png')) for i, path in enumerate(assets)]
                response = requests.post(url, params={'wait': 'true'}, data={'payload_json': json.dumps(payload)}, files=files, timeout=(20, 120))
        except requests.RequestException:
            raise RuntimeError('Discord network failure; delivery state retained for inspection.') from None
        if response.status_code == 429:
            delay = float(response.json().get('retry_after', 1)) + 0.2
            if delay > 60:
                raise RuntimeError('Discord rate limit exceeds one minute; send left pending.')
            time.sleep(delay)
            continue
        if response.status_code != 200:
            raise RuntimeError('Discord did not confirm delivery; HTTP ' + str(response.status_code))
        message = response.json()
        assert message.get('id'), 'Discord message confirmation incomplete'
        returned_names = [attachment['filename'] for attachment in message.get('attachments', [])]
        state['discord'][signature] = {'status': 'sent' if sorted(returned_names) == sorted(names) else 'needs_attachment_review',
                                      'message_id': message['id'], 'channel_id': message['channel_id'],
                                      'attachments': returned_names, 'confirmed': time.time()}
        save(state)
        assert sorted(returned_names) == sorted(names), 'Discord attachment confirmation incomplete; message receipt saved'
        print('Discord confirmed: ' + str(len(items)) + ' video links, logo, covers, channel details and mobile kit.', flush=True)
        return
    raise RuntimeError('Discord did not accept the message after rate-limit retries.')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Never include a webhook URL or raw provider response in exception output.
        print('Delivery stopped: ' + str(exc) if not isinstance(exc, requests.RequestException) else 'Delivery stopped: network failure', file=sys.stderr)
        sys.exit(1)
