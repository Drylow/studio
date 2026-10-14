#!/usr/bin/env python3
"""Upload one newly root-released seven-file history kit once, then verify normal-site readback.

Offline validation is the default. Private GoFile state lives outside the public
delivery kit. No POST is repeated after an uncertain result.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
import requests
from PIL import Image

ROLES = {'video', 'thumbnail_a', 'thumbnail_b', 'thumbnail_c', 'thumbnail_d', 'upload_text', 'captions'}

SHA = re.compile(r'[a-f0-9]{64}')
PAGE = re.compile(r'https://gofile\.io/d/[A-Za-z0-9]+')

def save(path, value, private=False):
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600 if private else 0o644)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(value, stream, indent=2); stream.write('\n')
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)

def hashes(path):
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(part); md5.update(part)
    return {'filename': path.name, 'bytes': path.stat().st_size,
            'sha256': sha.hexdigest(), 'md5': md5.hexdigest()}

def require(value, message):
    if not value: raise ValueError(message)


_master_spec = importlib.util.spec_from_file_location('audio_mastering_contract', Path(__file__).with_name('audio_mastering_contract.py'))
MASTERING = importlib.util.module_from_spec(_master_spec)
_master_spec.loader.exec_module(MASTERING)

def prepare(manifest, profile_path):
    frozen = {}
    def pin(path, expected=None):
        path = Path(path).resolve(); require(path.is_file(), 'Required local file missing: ' + str(path))
        actual = hashes(path)['sha256']
        if expected is not None: require(actual == expected, 'Pinned local SHA changed: ' + str(path))
        frozen[str(path)] = actual
        return path
    def json_file(spec):
        require(isinstance(spec, dict) and SHA.fullmatch(str(spec.get('sha256',''))), 'Evidence needs actual SHA')
        value=json.loads(pin(spec['path'],spec['sha256']).read_text())
        require(isinstance(value,dict), 'Evidence must be a JSON object')
        return value
    manifest=pin(manifest); data=json.loads(manifest.read_text())
    require(data.get('schema')=='history-gofile-delivery-v2', 'Wrong/current history delivery schema required')
    profile_path=pin(profile_path); profile=json.loads(profile_path.read_text())
    require(profile.get('schema')=='history-episode-profile-v1' and profile.get('episode')==data.get('episode'), 'Explicit current episode profile required')
    require(profile.get('reviewer') and profile.get('project_id') and profile.get('brand') and profile.get('title'), 'Missing episode profile identifiers')
    count,words,frames,fps=profile['scenes'],profile['words'],profile['frames'],profile['fps']
    require(data.get('expected')=={'scene_count':count,'canonical_words':words,'frames':frames,'fps':fps}, 'Current episode contract differs')
    files=data.get('files',[])
    require(len(files)==7 and {r.get('role') for r in files}==ROLES, 'Exactly seven current delivery roles required')
    rows=[]
    for entry in files:
        require(SHA.fullmatch(str(entry.get('sha256',''))), 'Each upload needs actual SHA')
        path=pin(entry['path'],entry['sha256']); info=hashes(path); require(info['bytes']>0,'Empty upload file')
        rows.append({'role':entry['role'],'path':str(path),**info})
    order=['video','thumbnail_a','thumbnail_b','thumbnail_c','thumbnail_d','upload_text','captions']
    rows.sort(key=lambda r:order.index(r['role']))
    require(len({r['filename'] for r in rows})==7, 'Seven upload filenames must be unique')
    by_role={r['role']:r for r in rows}; movie_sha=by_role['video']['sha256']
    require(Path(by_role['video']['path']).suffix.lower()=='.mp4','Final MP4 required')
    for key in 'abcd':
        row=by_role['thumbnail_'+key]
        require(row['bytes']<2_000_000, 'Reviewed thumbnail must be under 2 MB')
        with Image.open(row['path']) as im:
            require(im.format=='JPEG' and im.size==(3840,2160),'Actual reviewed 3840x2160 JPEG export required'); im.verify()
    require(len({by_role['thumbnail_'+key]['sha256'] for key in 'abcd'})==4,'Four distinct thumbnail exports required')
    require(Path(by_role['captions']['path']).name=='English-Captions.srt','Exact English caption SRT filename required')
    require(Path(by_role['upload_text']['path']).name=='UPLOAD.txt','Exact UPLOAD.txt filename required')
    text=Path(by_role['upload_text']['path']).read_text()
    require(profile['title'] in text and profile['brand'] in text,'Current episode title/channel text required')
    evidence=data.get('evidence',{})
    thumbnails=json_file(evidence['thumbnail_review']); thumb_records=thumbnails.get('records',[])
    require(len(thumb_records)==4 and {r.get('id') for r in thumb_records}==set('ABCD'),'Actual root reviews of all four exports required')
    require(len({r.get('original_sha256') for r in thumb_records})==4,'Four distinct actual originals required')
    for row in thumb_records:
        chosen=by_role['thumbnail_'+row['id'].lower()]
        require(row.get('review_state')=='pass' and row.get('actual_reviewer')==profile['reviewer'] and row.get('findings')
                and row.get('export_sha256')==chosen['sha256'] and str(Path(row['export']).resolve())==chosen['path']
                and row.get('export_dimensions')==[3840,2160] and row.get('bytes')==chosen['bytes'], 'Actual thumbnail root/export binding differs')
        pin(row['original'],row['original_sha256'])
    captions=json_file(evidence['caption_proof'])
    require(captions.get('sha256')==by_role['captions']['sha256'] and str(Path(captions['file']).resolve())==by_role['captions']['path']
            and captions.get('literal_word_identity') is True and captions.get('canonical_words')==words,'Exact current caption proof required')
    clock_path=pin(captions['source_clock'],captions['source_clock_sha256']); clock=json.loads(clock_path.read_text())
    require(len(clock)==words,'Actual current word clock count differs')
    blocks=re.split(r'\n\s*\n',Path(by_role['captions']['path']).read_text().strip()); spoken=[]; previous=0.0
    def seconds(t):
        h,m,s,ms=map(int,re.split('[:,]',t)); return h*3600+m*60+s+ms/1000
    for number,block in enumerate(blocks,1):
        lines=block.splitlines(); require(len(lines)>=3 and lines[0]==str(number),'Malformed SRT cue sequence')
        match=re.fullmatch(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})',lines[1]); require(match,'Malformed SRT timing')
        start,end=map(seconds,match.groups()); require(start>=previous-.002 and end>start and end<=profile['duration']+.05,'SRT timing outside current final voice'); previous=end
        spoken.extend(' '.join(lines[2:]).split())
    require(len(blocks)==captions.get('cues') and spoken==[w['w'] for w in clock],'SRT words differ from actual canonical narration')
    source=json_file(evidence['source_review']); records=source.get('records',[])
    require(len(records)==count and sorted(r['id'] for r in records)==list(range(1,count+1))
            and all(r.get('state')=='pass' and r.get('reviewer') and r.get('notes') for r in records),'All current source images need genuine visual PASS')
    selected={r['id']:r for r in records}
    for row in records: pin(row['image'],row['image_sha256'])
    plan=json_file(evidence['native_plan'])
    require(plan.get('total_frames')==frames and plan.get('fps')==fps and plan.get('script_words')==words
            and len(plan.get('scenes',[]))==count and abs(plan.get('duration_seconds',0)-profile['duration'])<.001,'New VPS native clock/plan required')
    require(str(Path(evidence['native_plan']['path']).resolve())==str(Path(profile.get('native_plan_path') or (Path(profile['base'])/'vps-adoption/exact-authored-scenes-new-vps-clock.json')).resolve()),'Old clock/plan cannot be reused')
    native=json_file(evidence['native_export'])
    require(native.get('sha256')==movie_sha and native.get('state')=='complete'
            and native.get('engine')=='tubeforge-native-api+audio-mastering' and native.get('project_id')==profile['project_id']
            and native.get('source_plan_sha256')==evidence['native_plan']['sha256']
            and native.get('source_review_sha256')==evidence['source_review']['sha256']
            and native.get('scene_image_sha256s')==[selected[i]['image_sha256'] for i in range(1,count+1)]
            and native.get('scene_count')==count,'Actual new native API export/source binding required')
    pin(native['absolute_file'],movie_sha)
    require(str(Path(native['absolute_file']).resolve())==by_role['video']['path'],'Native final path differs')
    require(native.get('info',{}).get('frames')==frames,'Wrong final native frame count')
    # Pin actual importer and API engine completion proof; this helper never creates them.
    import_manifest=json_file(native['native_import']); provider=json_file(native['provider_render_proof'])
    mastering_inputs=None
    if native['engine']=='tubeforge-native-api+audio-mastering':
        mastering_inputs=MASTERING.validate(native,profile,count,frames,pin,json_file,require,import_manifest,provider,clock)
    else:
        require(not native.get('audio_mastering') and not native.get('native_base'),'Raw API engine cannot conceal an audio-mastered derivative')
    qa=json_file(evidence['technical_qa']); visual=json_file(evidence['visual_qa'])
    if mastering_inputs is not None:
        require(qa.get('source_voice_sha256')==mastering_inputs['source_sha256'] and qa.get('derived_voice_sha256')==mastering_inputs['derived_sha256'],'Final mastered-film correlation proof must identify exact official and normalized voices')
    require(qa.get('movie_sha256')==movie_sha and qa.get('state') in ('pass','technical_pass_visual_review_pending')
            and qa.get('actual_decoded_video_frames')==frames and qa.get('full_av_fatal_decode_exit')==0,'Complete final A/V decode proof required')
    metadata=qa.get('metadata',{})
    require(metadata.get('width')==1920 and metadata.get('height')==1080 and metadata.get('fps')==fps,'Final export must be1920x1080 at24fps')
    levels=qa.get('audio_measured_levels',{})
    require(-19<float(levels.get('input_i','-100'))<-15 and float(levels.get('input_tp','100'))<-.3,'Actual final narration levels must pass')
    correlations=qa.get('voice_correlation_windows',[])
    require(len(correlations)==7 and all(r['zero_lag_correlation']>.97 and abs(r['best_lag_samples'])<=3 for r in correlations),'Actual final voice timing/correlation must pass')
    require(visual.get('movie_sha256')==movie_sha and visual.get('state')=='pass'
            and visual.get('finished_render_visual_reviewed') is True and visual.get('reviewed_encoded_scene_count')==count
            and visual.get('reviewed_cut_count')==count-1,'Genuine finished scene and cut review required')
    reviewed=visual.get('capture_sheets',[]); require(len(reviewed)>0 and len(reviewed)==len(qa.get('capture_sheets',[])),'Finished capture review incomplete')
    paths=[]
    for row in reviewed:
        require(row.get('state')=='pass' and row.get('reviewer') and row.get('notes'),'Actual finished sheet review missing')
        paths.append(str(pin(row['path'],row['sha256'])))
    require(len(set(paths))==len(paths) and set(paths)=={str(Path(p).resolve()) for p in qa['capture_sheets']},'Actual encoded capture/review binding differs')
    release=data.get('root_final_release',{})
    require(release.get('author')=='root' and release.get('approved') is True and release.get('movie_sha256')==movie_sha
            and release.get('delivery_file_sha256s')=={r['role']:r['sha256'] for r in rows},'Exact final root release of all seven files required')
    fingerprint=hashlib.sha256(json.dumps({'files':rows,'frozen':frozen},sort_keys=True).encode()).hexdigest()
    return {'manifest':str(manifest),'manifest_sha256':hashes(manifest)['sha256'],'files':rows,'frozen':frozen,'fingerprint':fingerprint,'movie_sha256':movie_sha,'episode':data['episode']}

def unchanged(kit):
    require(all(hashes(Path(p))['sha256'] == sha for p, sha in kit['frozen'].items()), 'Reviewed input changed before/during upload')

def result_data(response, label):
    require(response.status_code == 200, label + ': non-200; no automatic retry')
    try: body = response.json()
    except ValueError: raise ValueError(label + ': unreadable result; no automatic retry') from None
    require(body.get('status') == 'ok' and isinstance(body.get('data'), dict), label + ': success unconfirmed; no automatic retry')
    return body['data']

def matched_listing(listing, folder, rows):
    require(listing.get('folder_id') == folder and listing.get('folder_type') == 'folder'
            and listing.get('folder_public') is True
            and listing.get('http_status') == 200 and listing.get('api_status') == 'ok', 'Wrong/private remote readback folder')
    files = listing.get('files', [])
    require(len(files) == len(rows), 'Remote readback file count differs')
    pagination = listing.get('metadata', {})
    require(pagination.get('totalCount') == len(rows) and pagination.get('totalPages') == 1
            and pagination.get('page') == 1 and pagination.get('pageSize', 0) >= len(rows)
            and pagination.get('hasNextPage') is False, 'Remote listing incomplete or paginated')
    for row in rows:
        matches = [r for r in files if r.get('name') == row['filename']]
        require(len(matches) == 1, 'Remote readback filename differs')
        remote = matches[0]
        require(remote.get('type') == 'file' and int(remote.get('size', -1)) == row['bytes']
                and str(remote.get('md5', '')).lower() == row['md5'], 'Remote MD5/size readback differs')

def upload(kit, state, session):
    owner_path, pending_path, receipt_path = [state / n for n in ('owner-private.json', 'pending-private.json', 'receipt.json')]
    require(not pending_path.exists() and not receipt_path.exists(), 'Previous upload state exists; inspect, do not repeat POST')
    preflight_path = state / 'normal-site-preflight.json'
    preflight = json.loads(preflight_path.read_text())
    require(preflight.get('listing_observed') is True and preflight.get('owner_private_file_present') is True
            and preflight.get('normal_guest_creation_posts') == 0 and preflight.get('file_uploads') == 0
            and not preflight.get('blocked_mutations'),
            'Normal official-site readback preflight must succeed before upload')
    require(owner_path.stat().st_mode & 0o777 == 0o600, 'Owner token file must be private mode 600')
    owner = json.loads(owner_path.read_text()); token = owner['owner_token']
    response = session.get('https://api.gofile.io/servers', timeout=(15,30), allow_redirects=False)
    servers = result_data(response, 'GoFile server selection').get('servers', [])
    servers = [s for s in servers if re.fullmatch(r'store[a-z0-9-]+', str(s.get('name', '')))]
    require(servers, 'No official upload server returned')
    server = next((s for s in servers if s.get('zone') == 'eu'), servers[0])
    endpoint = 'https://' + server['name'] + '.gofile.io/uploadfile'
    folder = page = None
    pending = {'manifest_sha256': kit['manifest_sha256'], 'episode': kit['episode'], 'new_folder_only': True, 'fingerprint': kit['fingerprint'], 'intended_files': kit['files'], 'confirmed_files': [], 'url': None}
    save(pending_path, pending, private=True)
    for row in kit['files']:
        unchanged(kit)
        pending['in_flight_filename'] = row['filename']; pending['pre_post_checkpoint_utc'] = datetime.now(timezone.utc).isoformat(); save(pending_path, pending, private=True)
        try:
            with open(row['path'], 'rb') as stream:
                response = session.post(endpoint, headers={'Authorization': 'Bearer ' + token},
                    data={'folderId': folder} if folder else {},
                    files={'file': (row['filename'], stream, mimetypes.guess_type(row['filename'])[0] or 'application/octet-stream')},
                    timeout=(30,1800), allow_redirects=False)
        except requests.RequestException:
            raise RuntimeError('Upload outcome uncertain; pending retained, no automatic retry') from None
        received = result_data(response, 'GoFile upload')
        require(int(received.get('size', -1)) == row['bytes'] and str(received.get('md5', '')).lower() == row['md5'],
                'Upload response MD5/size mismatch; preserve pending')
        if folder is None:
            folder = received.get('parentFolder') or received.get('folderId'); page = received.get('downloadPage')
            require(isinstance(folder, str) and re.fullmatch(r'[A-Za-z0-9-]+', folder)
                    and isinstance(page, str) and PAGE.fullmatch(page), 'Upload did not confirm a share folder')
            owner.update(folder_id=folder, url=page); save(owner_path, owner, private=True)
        else:
            require(received.get('parentFolder', folder) == folder and received.get('downloadPage', page) == page,
                    'Upload folder changed')
        pending['url'] = page; pending['confirmed_files'].append(row); pending.pop('in_flight_filename', None)
        save(pending_path, pending, private=True)
        print(json.dumps({'uploaded': row['filename'], 'bytes_md5_confirmed': True}), flush=True)
    unchanged(kit)
    # The direct listing API is Premium-only. Use the already tested unmodified
    # public website, retaining its real successful GET response and screenshot.
    helper = Path(__file__).with_name('gofile_site_readback.py')
    proof = state / 'final-normal-site-readback.json'
    expected = state / 'expected-listing-files.json'
    save(expected, [r['filename'] for r in kit['files']])
    result = subprocess.run([os.environ.get('HISTORY_BROWSER_PYTHON', sys.executable), str(helper),
        '--url', page, '--state-dir', str(state), '--output', str(proof), '--expected-folder', folder, '--expected-files-json', str(expected)],
        capture_output=True, text=True)
    require(result.returncode == 0, 'Normal official-site final readback failed; preserve pending, no POST retry')
    readback = json.loads(proof.read_text())
    require(readback.get('listing_observed') is True and readback.get('screenshot_created_this_run') is True
            and readback.get('all_expected_filenames_painted') is True and readback.get('complete_listing_observed') is True and readback.get('proof_verified') is True and not readback.get('blocked_authorization_requests') and not readback.get('blocked_mutations')
            and readback.get('normal_guest_creation_posts') == 0, 'Normal site DOM/screenshot/mutation proof incomplete')
    matched_listing(readback['listing'], folder, kit['files'])
    screenshot = Path(readback['screenshot'])
    require(screenshot.is_file() and hashes(screenshot)['sha256'] == readback.get('screenshot_sha256'),
            'Normal-site screenshot proof changed')
    unchanged(kit)
    receipt = {'schema': 'history-gofile-confirmed-delivery-v2', 'url': page, 'fingerprint': kit['fingerprint'],
               'files': kit['files'], 'movie_sha256': kit['movie_sha256'],
               'upload_response_md5_size_verified': True, 'official_normal_site_readback_matched': True,
               'direct_premium_api_readback_complete': False, 'remote_sha256_available': False,
               'readback_proof': {'path': str(proof), 'sha256': hashes(proof)['sha256']},
               'readback_screenshot': {'path': str(screenshot), 'sha256': readback['screenshot_sha256']},
               'verified_at': datetime.now(timezone.utc).isoformat()}
    save(receipt_path, receipt)
    pending_path.replace(state / 'pending-confirmed-private.json')
    print(json.dumps({'status': 'upload-and-normal-site-readback-confirmed', 'url': page, 'files': 7}), flush=True)

def existing_confirmed(kit, state):
    receipt_path = state / 'receipt.json'
    if not receipt_path.exists(): return False
    receipt = json.loads(receipt_path.read_text())
    require(receipt.get('fingerprint') == kit['fingerprint'] and receipt.get('files') == kit['files']
            and receipt.get('official_normal_site_readback_matched') is True
            and PAGE.fullmatch(str(receipt.get('url', ''))), 'Existing confirmed receipt identifies another kit')
    proof = receipt['readback_proof']; proof_path = Path(proof['path'])
    require(hashes(proof_path)['sha256'] == proof['sha256'], 'Existing normal-site proof changed')
    listing = json.loads(proof_path.read_text())
    require(listing.get('public_url') == receipt['url'], 'Existing normal-site URL changed')
    owner_path = state / 'owner-private.json'
    require(owner_path.stat().st_mode & 0o777 == 0o600, 'Owner file permissions changed')
    owner = json.loads(owner_path.read_text())
    matched_listing(listing['listing'], owner['folder_id'], kit['files'])
    screenshot = receipt['readback_screenshot']
    require(hashes(Path(screenshot['path']))['sha256'] == screenshot['sha256'], 'Existing screenshot proof changed')
    unchanged(kit)
    print(json.dumps({'status': 'already-uploaded-and-confirmed-no-new-POST', 'url': receipt['url'], 'files': 7}), flush=True)
    return True

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--manifest-sha256', help='Exact ROOT-released manifest SHA; required for upload')
    args = parser.parse_args()
    state = args.state_dir.resolve(); state.mkdir(parents=True, exist_ok=True); state.chmod(0o700)
    with (state / 'delivery.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        kit = prepare(args.manifest, args.profile)
        if args.upload:
            require(SHA.fullmatch(str(args.manifest_sha256 or '')) and args.manifest_sha256 == kit['manifest_sha256'], 'Exact ROOT manifest SHA gate required before any POST')
            if not existing_confirmed(kit, state):
                with requests.Session() as session: upload(kit, state, session)
        else:
            print(json.dumps({'status': 'local-final-kit-validated-no-upload', 'files': kit['files'],
                              'movie_sha256': kit['movie_sha256'], 'fingerprint': kit['fingerprint']}))

if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, RuntimeError, requests.RequestException) as exc:
        # Transport exceptions can contain private URLs/headers; do not print them.
        if isinstance(exc, requests.RequestException): message = type(exc).__name__ + '; no automatic retry'
        else: message = str(exc)
        raise SystemExit('Delivery stopped: ' + message) from None
