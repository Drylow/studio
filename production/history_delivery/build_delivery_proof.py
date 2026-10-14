"""Build a sanitized, hash-bound native delivery proof; only GET remote APIs.

No rendering, reviews, generation or GoFile upload occurs here. Pending inputs stay
pending. The original source plans/ledgers and media import records are never edited.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = None
EPISODES = {}
EXPECTED = {}

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def artifact(path):
    path = Path(path)
    return {'path': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size}


def write_private(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    temporary.chmod(0o600)
    temporary.replace(path)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def refresh_api(slug, pid):
    # Use the supplied personal session and inspected HTTPS/2 transport normally.
    if not os.environ.get('FORGE_SESSION_FILE') and not os.environ.get('FORGE_SESSION_TOKEN'):
        raise ValueError('Set a personal FORGE_SESSION_FILE or FORGE_SESSION_TOKEN before API refresh')
    forge = module('forge', Path(__file__).resolve().parents[1] / 'tubeforge_support/forge_docs/forge.py')
    forge.request = module('curl_transport', Path(__file__).with_name('curl_transport.py')).bind(forge)
    snapshots = {}
    for kind, endpoint in (
            ('project', '/api/2d/api/workspace/projects/' + pid),
            ('outputs', '/api/forge/v1/videos/' + pid + '/outputs')):
        with forge.request('GET', forge.HOST + endpoint) as response:
            value = json.load(response)
        path = ROOT / 'private' / (slug + '-delivery-' + kind + '.json')
        write_private(path, value)
        snapshots[kind] = (path, endpoint)
    return snapshots


def review(record):
    # Deliberately omit model/provider settings and portal authentication.
    return {key: record.get(key) for key in
            ('state', 'source', 'reviewer', 'notes', 'reviewed_at', 'evidence') if key in record}


def probe_movie(path):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-show_data_hash', 'sha256',
         '-of', 'json', str(path)],
        check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    videos = [x for x in data.get('streams', []) if x.get('codec_type') == 'video']
    audios = [x for x in data.get('streams', []) if x.get('codec_type') == 'audio']
    fields = ('index', 'codec_type', 'codec_name', 'width', 'height', 'pix_fmt', 'r_frame_rate',
              'avg_frame_rate', 'time_base', 'duration', 'duration_ts', 'nb_frames',
              'sample_rate', 'channels', 'channel_layout', 'codec_tag_string', 'profile', 'level',
              'extradata_hash', 'extradata_size', 'start_pts', 'start_time')
    return {'tool': 'ffprobe', 'video_streams': [{k: v.get(k) for k in fields if k in v}
                                               for v in videos],
            'audio_streams': [{k: a.get(k) for k in fields if k in a} for a in audios],
            'format': {k: data.get('format', {}).get(k)
                       for k in ('format_name', 'duration', 'size', 'bit_rate')},
            'scope': 'Container/stream metadata only; no visual or audible final quality approval.'}


def path_query(url):
    parsed = urlparse(url)
    return parsed.path + ('?' + parsed.query if parsed.query else '')


def official_endpoint_matches(recorded, official):
    if not isinstance(recorded, str) or not recorded or not isinstance(official, str) or not official:
        return False
    expected_host = 'tools.kanye.studio'
    first, second = (urlparse(urljoin('https://' + expected_host, value))
                     for value in (recorded, official))
    return (first.scheme == second.scheme == 'https'
            and first.netloc == second.netloc == expected_host
            and not first.fragment and not second.fragment
            and path_query(first.geturl()) == path_query(second.geturl()))


def video_packet_identity(path):
    """Hash ordered encoded video packets and timing; never decode/encode frames."""
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_packets', '-show_data_hash', 'sha256', '-show_entries',
        'packet=pts,dts,duration,size,flags,data_hash', '-of', 'json', str(path)],
        check=True, capture_output=True, text=True)
    packets = json.loads(result.stdout).get('packets', [])
    if not packets or any(not p.get('data_hash') for p in packets):
        raise ValueError('No complete encoded video packet hash evidence')
    canonical = json.dumps(packets, sort_keys=True, separators=(',', ':')).encode()
    return {'method': 'ffprobe ordered encoded video packet data_sha256 plus pts,dts,duration,size,flags',
            'packet_count': len(packets), 'ordered_packets_sha256': hashlib.sha256(canonical).hexdigest()}


def build(args):
    slug = args.episode
    ep, count = EPISODES[slug], EXPECTED[slug]
    directory = ROOT / 'staging' / (slug + '-native-import')
    plan_path = ep / 'vps-adoption/selected-generation-provenance-plan.json'
    combined_path = ep / 'combined-actual-source-review.json'
    manifest_path = directory / 'import-manifest.json'
    scenes_path, locations_path = directory / 'scenes.json', directory / 'locations.json'
    media_path = directory / 'media-import-state.json'
    plan, combined, manifest = read(plan_path), read(combined_path), read(manifest_path)
    local_scenes, media = read(scenes_path)['scenes'], read(media_path)
    state = read(ROOT / 'private/history-migration-state.json')['episodes'][slug]
    pid = state['remote_project_id']
    checks = []

    def check(name, valid, pending=False, detail=None):
        item = {'check': name, 'state': 'passed' if valid else 'pending' if pending else 'failed'}
        if detail:
            item['detail'] = detail
        checks.append(item)

    if args.refresh_api:
        snapshot_paths = refresh_api(slug, pid)
    else:
        snapshot_paths = {
            'project': (Path(args.project_json) if args.project_json else
                        ROOT / 'private' / (slug + '-delivery-project.json'),
                        '/api/2d/api/workspace/projects/' + pid),
            'outputs': (Path(args.outputs_json) if args.outputs_json else
                        ROOT / 'private' / (slug + '-delivery-outputs.json'),
                        '/api/forge/v1/videos/' + pid + '/outputs')}
    project = read(snapshot_paths['project'][0]) if snapshot_paths['project'][0].exists() else None
    outputs = read(snapshot_paths['outputs'][0]) if snapshot_paths['outputs'][0].exists() else None
    check('current_official_project_snapshot', project is not None, pending=True)
    check('current_official_outputs_snapshot', outputs is not None, pending=True)
    if project is not None:
        check('official_project_id_matches_owned_creation', project.get('id') == pid)
        check('official_member_owner_recorded', bool(project.get('owner_id')))
    if outputs is not None:
        check('official_outputs_id_matches_project', outputs.get('id') == pid)
    check('media_import_project_id_matches', media.get('project_id') == pid)
    check('manifest_binds_selected_plan', manifest.get('source_plan_sha256') == digest(plan_path))
    check('selected_plan_binds_combined_review',
          plan.get('actual_selected_source_review_sha256') == digest(combined_path))
    ordered = list(range(1, count + 1))
    check('ordered_selected_scene_ids', [x['id'] for x in plan['scenes']] == ordered)
    check('ordered_native_authored_scene_ids', [x['id'] for x in local_scenes] == ordered)
    check('ordered_import_manifest_scene_ids', [x['scene_id'] for x in manifest['scenes']] == ordered)
    source_reviews = {x['id']: x for x in combined['records']}
    manifest_scenes = {x['scene_id']: x for x in manifest['scenes']}
    source_scenes = {x['id']: x for x in plan['scenes']}
    remote_scenes = {x['id']: x for x in (project or {}).get('scenes', [])}
    check('ordered_current_official_scene_ids',
          [x['id'] for x in (project or {}).get('scenes', [])] == ordered, pending=project is None)
    check('all_selected_source_reviews_present', sorted(source_reviews) == ordered)
    check('all_native_image_import_records_present',
          sorted(int(x) for x in media.get('images', {})) == ordered, pending=True)
    prepared = []
    for scene in local_scenes:
        sid, source = scene['id'], source_scenes[scene['id']]
        source_review = source_reviews[sid]
        imported = media.get('images', {}).get(str(sid))
        remote = remote_scenes.get(sid)
        selected_hash = source.get('selected_image_sha256')
        check(f'scene_{sid}_selected_image_hash', selected_hash == source_review['image_sha256']
              == digest(source['selected_image']))
        check(f'scene_{sid}_selected_source_pass', source.get('selected_source_state') == 'pass'
              and source_review.get('state') == 'pass')
        check(f'scene_{sid}_preserved_source_review',
              source.get('selected_generation_review_record') == source_review)
        if imported:
            check(f'scene_{sid}_import_source_hash', imported.get('source_sha256') == selected_hash)
            check(f'scene_{sid}_import_decoded_rgb_equality',
                  imported.get('decoded_rgb_pixels_equal') is True)
        else:
            check(f'scene_{sid}_import_completed', False, pending=True)
        current_review = review((remote or {}).get('human_review') or {})
        authoring_fields = ('text', 'prompt', 'characters', 'character_variants', 'start', 'end',
            'motion', 'location_id', 'location_view', 'shot_type', 'visual_beat', 'location_contract')
        check(f'scene_{sid}_current_api_authoring_matches_saved_native_copy',
              remote is not None and all(remote.get(k) == scene.get(k) for k in authoring_fields),
              pending=remote is None)
        official_refs = [{k: v for k, v in ref.items() if k != 'url'}
                         for ref in (remote or {}).get('references', [])]
        check(f'scene_{sid}_current_api_ordered_references_match_saved_native_copy',
              remote is not None and official_refs == scene['references'], pending=remote is None)
        if imported and remote:
            check(f'scene_{sid}_official_selected_remote_path', remote.get('image') == imported['remote_path'])
            check(f'scene_{sid}_official_image_hash',
                  (current_review.get('evidence') or {}).get('image_sha256') == imported['remote_sha256'],
                  pending=current_review.get('state') != 'verified')
        check(f'scene_{sid}_current_delegated_review', current_review.get('state') == 'verified'
              and current_review.get('source') == 'delegated_ai_inspection', pending=True)
        references = []
        original_refs = manifest_scenes[sid]['original_ordered_references']
        relocated_refs = manifest_scenes[sid]['relocated_ordered_references']
        evidence_refs = manifest_scenes[sid]['relocation_evidence']
        check(f'scene_{sid}_reference_order_lengths',
              len(original_refs) == len(relocated_refs) == len(evidence_refs) == len(scene['references']))
        check(f'scene_{sid}_native_and_manifest_ordered_references_equal',
              scene['references'] == relocated_refs)
        for index, (original, relocated, evidence) in enumerate(
                zip(original_refs, relocated_refs, evidence_refs), 1):
            check(f'scene_{sid}_reference_{index}_source_and_remote_hashes',
                  original['sha256'] == evidence.get('source_sha256')
                  and relocated['sha256'] == evidence.get('remote_sha256')
                  and original['path'] == evidence.get('source_path')
                  and relocated['path'] == evidence.get('remote_path')
                  and Path(original['path']).is_file()
                  and original['sha256'] == digest(original['path'])
                  and evidence.get('decoded_rgb_pixels_equal') is True)
            references.append({'attachment_index': index,
                'source': {'path': original['path'], 'sha256': original['sha256']},
                'imported': {k: relocated.get(k) for k in ('owner', 'path', 'sha256', 'role',
                    'character', 'variant', 'location_id', 'review_state') if k in relocated},
                'decoded_rgb_pixels_equal': evidence.get('decoded_rgb_pixels_equal')})
        prepared.append({'id': sid, 'narration_sha256': hashlib.sha256(scene['text'].encode()).hexdigest(),
            'actual_voice_start': scene['start'], 'actual_voice_end': scene['end'],
            'original_group_selection': source.get('group_selection'),
            'original_cast_order': source.get('cast_order'),
            'original_actor_count': source.get('actor_count'),
            'original_authored_action': source.get('action'),
            'group_reference_slots_present': sorted(set(source.get('characters', [])) &
                {'CREW_EXTRAS', 'ENGLISH_LOCALS', 'ENSLAVED_ASIDE', 'CAPTURED_SAILORS'}),
            'selected_source': {'path': source['selected_image'], 'sha256': selected_hash,
                                'state': source.get('selected_source_state')},
            'source_generation_argument_association': source.get('actual_generation_argument_association'),
            'selected_generation_arguments_present': source.get('selected_generation_arguments') is not None,
            'preserved_selected_source_quality_review': source_review,
            'imported_scene_image': imported,
            'official_selected_image_path': (remote or {}).get('image'),
            'current_official_scene_review': current_review, 'ordered_references': references})
    clock_path = Path(manifest['official_clock_path'])
    clock, voice = read(clock_path), (project or {}).get('voiceover') or {}
    voice_path = ROOT / 'staging' / (slug + '-remote-clock') / 'voice.mp3'
    check('downloaded_official_voice_file_present', voice_path.is_file())
    check('official_clock_hash_bound_by_import_manifest', digest(clock_path) == manifest['official_clock_sha256'])
    voice_duration = voice.get('duration')
    check('official_voice_and_clock_duration_match',
          isinstance(voice_duration, (int, float)) and math.isfinite(voice_duration)
          and abs(voice_duration - clock['duration_seconds']) <= 0.05, pending=project is None)
    scopes = {key: review(value) for key, value in (project or {}).get('human_reviews', {}).items()}
    check('current_official_voice_review', scopes.get('voiceover', {}).get('state') == 'verified', pending=True)
    if project and voice_path.is_file():
        observed_voice_evidence = hashlib.sha256(json.dumps(
            {'file_sha256': digest(voice_path), 'script': project.get('script'), 'media': voice},
            sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        check('downloaded_official_voice_hash_matches_current_native_review_evidence',
              observed_voice_evidence == scopes.get('voiceover', {}).get('evidence'),
              pending=scopes.get('voiceover', {}).get('state') != 'verified')
    render = (project or {}).get('render')
    check('official_native_render_exists', bool(render), pending=True)
    check('official_output_video_endpoint_available', bool((outputs or {}).get('video')), pending=True)
    check('current_official_native_project_technical_ready',
          (project or {}).get('technical_ready') is True, pending=project is None or not render)
    native_backend = (render or {}).get('backend')
    project_backend = (project or {}).get('settings', {}).get('visuals', {}).get('render_backend')
    native_backend_confirmed = native_backend == 'native' or (
        native_backend is None and project_backend == 'native')
    check('official_render_native_backend_confirmed', native_backend_confirmed,
          pending=not render or native_backend is None and project_backend is None)
    final_movie = {'state': 'pending', 'reason': 'Completed official native movie path not supplied.'}
    native_base = {'state': 'pending', 'reason': 'Completed raw native API base movie not supplied.'}
    final_audio = {'state': 'pending', 'target_integrated_lufs': -17.0,
                   'maximum_true_peak_dbtp': -0.3,
                   'reason': 'No measured final MP4 audio analysis supplied.'}
    if args.native_base and Path(args.native_base).is_file():
        base_path = Path(args.native_base)
        native_base = {'state': 'observed', 'file': artifact(base_path), 'ffprobe': probe_movie(base_path),
                       'origin': {'state': 'pending', 'reason': 'Official completed GET receipt missing.'},
                       'notice': 'Raw API native visual render. Quiet source audio is not final audio approval.'}
        if args.download_receipt:
            receipt_path, receipt = Path(args.download_receipt), read(args.download_receipt)
            valid = (receipt.get('project_id') == pid
                     and receipt.get('sha256') == native_base['file']['sha256']
                     and Path(receipt.get('path', '')).resolve() == base_path.resolve()
                     and receipt.get('method') == 'GET'
                     and official_endpoint_matches(receipt.get('endpoint'), (outputs or {}).get('video'))
                     and receipt.get('bytes') == base_path.stat().st_size
                     and bool(receipt.get('completed_at')))
            check('native_base_hash_and_official_download_origin_receipt', valid)
            native_base['origin'] = {'state': 'verified' if valid else 'failed',
                'receipt': artifact(receipt_path), 'record': {k: receipt.get(k) for k in
                    ('project_id', 'endpoint', 'path', 'sha256', 'method', 'completed_at', 'bytes') if k in receipt}}
        else:
            check('native_base_hash_and_official_download_origin_receipt', False, pending=True)
        try:
            base_stream = native_base['ffprobe']['video_streams'][0]
            numerator, denominator = (float(x) for x in base_stream['avg_frame_rate'].split('/'))
            observed_fps = numerator / denominator
            observed_frames = int(base_stream['nb_frames'])
            api_duration = float((render or {})['duration'])
            api_frames = (render or {}).get('total_frames', (render or {}).get('video_frames'))
            valid_render = (math.isfinite(observed_fps) and observed_fps > 0
                and base_stream['width'] == (render or {}).get('width') == 1920
                and base_stream['height'] == (render or {}).get('height') == 1080
                and abs(float(base_stream['duration']) - api_duration) <= 0.05
                and observed_frames == round(api_duration * observed_fps)
                and (api_frames is None or observed_frames == api_frames)
                and ((render or {}).get('fps') is None or observed_fps == render['fps']))
        except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
            observed_fps, observed_frames, valid_render = None, None, False
        check('raw_native_video_stream_agrees_with_actual_api_render_dimensions_duration_frames', valid_render)
        native_base['api_render_agreement'] = {'state': 'verified' if valid_render else 'failed',
            'observed_stream_fps': observed_fps, 'observed_stream_frame_count': observed_frames,
            'frame_count_basis': 'Observed ffprobe count checked against API duration times observed stream fps; '
                'API frame count/fps compared directly only when actually reported.'}
    else:
        check('completed_raw_official_native_base_present', False, pending=True)
    if args.movie:
        movie_path = Path(args.movie)
        if movie_path.is_file():
            final_movie = {'state': 'observed', 'file': artifact(movie_path), 'ffprobe': probe_movie(movie_path),
                           'derivation': {'state': 'pending', 'reason': 'Explicit root audio-mastering provenance missing.'},
                           'engine_claim': 'Native VPS visual render plus separately authorized audio-only mastering/remux.'}
            video_streams = final_movie['ffprobe']['video_streams']
            check('downloaded_movie_is_1920x1080', bool(video_streams)
                  and video_streams[0].get('width') == 1920 and video_streams[0].get('height') == 1080)
            check('downloaded_movie_contains_audio', bool(final_movie['ffprobe']['audio_streams']))
            if args.mastering_provenance and native_base.get('file'):
                mastering_path, mastering = Path(args.mastering_provenance), read(args.mastering_provenance)
                base_packets, final_packets = video_packet_identity(base_path), video_packet_identity(movie_path)
                identical = base_packets == final_packets
                properties = ('codec_name', 'codec_tag_string', 'width', 'height', 'pix_fmt',
                    'r_frame_rate', 'avg_frame_rate', 'time_base', 'duration_ts', 'nb_frames',
                    'extradata_hash', 'extradata_size', 'start_pts')
                base_stream = native_base['ffprobe']['video_streams'][0]
                final_stream = final_movie['ffprobe']['video_streams'][0]
                properties_identical = all(base_stream.get(k) == final_stream.get(k) for k in properties)
                valid = (mastering.get('native_project_id') == pid
                         and mastering.get('native_base_sha256') == native_base['file']['sha256']
                         and mastering.get('final_sha256') == final_movie['file']['sha256']
                         and mastering.get('video_codec_mode') == 'copy'
                         and mastering.get('visual_encoding_performed') is False and identical
                         and properties_identical and isinstance(mastering.get('command'), list)
                         and bool(mastering['command']) and all(isinstance(x, str) for x in mastering['command'])
                         and Path(mastering.get('native_base_path', '')).resolve() == base_path.resolve()
                         and Path(mastering.get('final_path', '')).resolve() == movie_path.resolve()
                         and bool(mastering.get('ffmpeg_version')) and bool(mastering.get('completed_at')))
                check('root_audio_only_mastering_hash_bound_provenance', valid)
                check('final_video_encoded_packets_and_timing_identical_to_native_base', identical)
                check('final_video_stream_properties_identical_to_native_base', properties_identical)
                final_movie['derivation'] = {'state': 'verified' if valid else 'failed',
                    'provenance': artifact(mastering_path), 'record': {k: mastering.get(k) for k in
                        ('schema', 'native_project_id', 'native_base_path', 'native_base_sha256',
                         'final_path', 'final_sha256', 'video_codec_mode', 'visual_encoding_performed',
                         'command', 'ffmpeg_version', 'completed_at', 'audio_filter', 'author') if k in mastering},
                    'native_base_video_packets': base_packets, 'final_video_packets': final_packets,
                    'encoded_video_packets_and_timing_identical': identical,
                    'video_stream_properties_identical': properties_identical,
                    'compared_video_properties': list(properties)}
            else:
                check('root_audio_only_mastering_hash_bound_provenance', False, pending=True)
            if args.audio_analysis:
                analysis = read(args.audio_analysis)
                measurements = analysis.get('measurements', analysis)
                try:
                    integrated = float(measurements['input_i'])
                    true_peak = float(measurements['input_tp'])
                    valid = (analysis.get('movie_sha256') == final_movie['file']['sha256']
                             and math.isfinite(integrated) and math.isfinite(true_peak)
                             and -18.0 <= integrated <= -16.0 and true_peak < -0.3)
                except (KeyError, TypeError, ValueError):
                    integrated, true_peak, valid = None, None, False
                final_audio = {'state': 'verified' if valid else 'failed',
                    'target_integrated_lufs': -17.0, 'maximum_true_peak_dbtp': -0.3,
                    'observed_integrated_lufs': integrated, 'observed_true_peak_dbtp': true_peak,
                    'evidence': artifact(args.audio_analysis), 'record': analysis}
                check('final_movie_measured_loudness_and_true_peak', valid)
            else:
                check('final_movie_measured_loudness_and_true_peak', False, pending=True)
            if args.final_qa:
                qa = read(args.final_qa)
                valid = (qa.get('movie_sha256') == final_movie['file']['sha256']
                         and qa.get('state') == 'verified'
                         and qa.get('source') in ('delegated_ai_inspection', 'explicit_human_review')
                         and bool(qa.get('reviewer')) and bool(qa.get('notes')))
                check('final_derived_movie_actual_hash_bound_quality_review', valid)
                final_movie['final_quality_review'] = {'state': 'verified' if valid else 'failed',
                                                       'evidence': artifact(args.final_qa), 'record': qa}
            else:
                check('final_derived_movie_actual_hash_bound_quality_review', False, pending=True)
            try:
                final_duration = float(final_movie['ffprobe']['format']['duration'])
                audio_duration = float(final_movie['ffprobe']['audio_streams'][0]['duration'])
                valid_sync = (isinstance(voice_duration, (int, float))
                              and abs(audio_duration - voice_duration) <= 0.1
                              and abs(final_duration - voice_duration) <= 0.1)
            except (KeyError, IndexError, TypeError, ValueError):
                valid_sync = False
            check('final_derived_movie_audio_and_container_cover_actual_voice_duration', valid_sync)
        else:
            check('completed_downloaded_movie_present', False, pending=True)
    else:
        check('completed_downloaded_movie_present', False, pending=True)
        check('final_movie_measured_loudness_and_true_peak', False, pending=True)
        check('final_derived_movie_actual_hash_bound_quality_review', False, pending=True)
    snapshots = {kind: {'endpoint': endpoint, **artifact(path)} for kind, (path, endpoint)
                 in snapshot_paths.items() if path.exists()}
    release = {'state': 'pending_explicit_root_release', 'gofile_upload_performed_by_this_helper': False,
        'notice': 'This proof does not authorize delivery or infer final film QA from source image reviews.'}
    if args.root_release:
        record = read(args.root_release)
        final_hash = final_movie.get('file', {}).get('sha256')
        valid = (final_movie.get('state') == 'observed' and isinstance(final_hash, str)
                 and len(final_hash) == 64 and record.get('state') == 'released'
                 and bool(record.get('author')) and record.get('movie_sha256') == final_hash)
        check('explicit_root_release_bound_to_exact_final_movie', valid)
        release.update(state='released_by_root' if valid else 'invalid_release_record',
                       evidence=artifact(args.root_release), record=record)
    else:
        check('explicit_root_release_bound_to_exact_final_movie', False, pending=True)
    proof = {'schema': 'native-existing-media-delivery-proof-v1', 'episode': slug,
        'generated_at': datetime.now(timezone.utc).isoformat(), 'expected_ordered_scene_count': count,
        'proof_state': 'failed' if any(x['state'] == 'failed' for x in checks) else
                       'pending' if any(x['state'] == 'pending' for x in checks) else 'complete',
        'source_artifacts': {'selected_generation_plan': artifact(plan_path),
            'combined_selected_source_review': artifact(combined_path),
            'native_import_manifest': artifact(manifest_path), 'native_authored_scenes': artifact(scenes_path),
            'native_location_registry': artifact(locations_path), 'image_import_state': artifact(media_path)},
        'official_native_project': {'id': pid, 'member_owner_id': (project or {}).get('owner_id'),
            'member_owner_name': (project or {}).get('owner_name'), 'snapshots': snapshots,
            'review_state': (project or {}).get('review_state'),
            'technical_ready': (project or {}).get('technical_ready'),
            'publication_ready_as_reported_for_raw_native_base': (project or {}).get('publication_ready'),
            'technical_issues': (project or {}).get('technical_issues'), 'scope_reviews': scopes},
        'ordered_scenes': prepared,
        'official_voice': {'native_file': voice.get('file'), 'actual_api_duration_seconds': voice_duration,
            'downloaded_official_voice': artifact(voice_path) if voice_path.exists() else None,
            'actual_word_clock': artifact(clock_path), 'actual_clock_duration_seconds': clock['duration_seconds'],
            'word_count': len(clock['words']), 'current_official_review': scopes.get('voiceover')},
        'official_native_render': {'state': 'reported' if render else 'pending',
            'api_reported_fields': {k: render.get(k) for k in ('file', 'duration', 'width', 'height',
                'fps', 'total_frames', 'video_frames', 'backend', 'render_seconds', 'ts',
                'qa_pending', 'publication_ready') if k in render} if render else None,
            'fps_reported_by_api': (render or {}).get('fps'),
            'native_backend_evidence': {'api_reported_backend': native_backend,
                'consumed_project_render_backend': project_backend, 'confirmed': native_backend_confirmed},
            'official_video_download_endpoint': (outputs or {}).get('video'),
            'current_official_review_of_raw_native_base': scopes.get('render'),
            'raw_native_api_base': native_base, 'final_derived_movie': final_movie,
            'final_movie_audio': final_audio},
        'verification_checks': checks,
        'release': release,
        'native_identity_binding_template_limitation':
            'Original group assets CREW_EXTRAS, ENGLISH_LOCALS, ENSLAVED_ASIDE and CAPTURED_SAILORS '
            'contain multiple distinct reviewed adults with explicit original selection/count. '
            'The generic native identity binding template says one person for a registered slot; '
            'this is not a claim about those original group pixels. Original group_selection, '
            'cast_order, authored action/count and source visual review are authoritative. '
            'The generic blocks were appended after generation as native import metadata, and '
            'no provider generation was run against them.',
        'scope_notice': 'Only current official API snapshots and this exact source/import chain apply. '
            'Old local clip/render manifests are not reused. Native contract blocks were added after generation; '
            'they are not historical provider receipts. Provider settings and authentication are omitted.'}
    target = Path(args.out) if args.out else directory / 'delivery-provenance.pending.json'
    write_private(target, proof)
    states = {name: sum(x['state'] == name for x in checks) for name in ('passed', 'pending', 'failed')}
    print(slug, 'proof', proof['proof_state'], 'scene imports', len(media.get('images', {})),
          '/', count, 'checks', states, 'saved', target)
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episode', help='Slug matching the migration state episode key')
    parser.add_argument('--episode-dir', type=Path, required=True)
    parser.add_argument('--staging-root', type=Path, required=True, help='Contains private/ snapshots and staging/<slug>-native-import records')
    parser.add_argument('--scene-count', type=int, required=True)
    parser.add_argument('--refresh-api', action='store_true', help='Only GET current official project and outputs.')
    parser.add_argument('--project-json')
    parser.add_argument('--outputs-json')
    parser.add_argument('--native-base', help='Exact raw completed authenticated native API MP4 download.')
    parser.add_argument('--movie', help='Final derived MP4 after separately authorized audio-only mastering/remux.')
    parser.add_argument('--download-receipt', help='Actual native-base GET receipt: project_id,endpoint,path,sha256,method,bytes,completed_at.')
    parser.add_argument('--mastering-provenance', help='Root mastering receipt binding native project/base/final hashes and video copy.')
    parser.add_argument('--audio-analysis', help='Actual final MP4 analysis JSON: movie_sha256,measurements.input_i/input_tp.')
    parser.add_argument('--final-qa', help='Actual final MP4 QA JSON: movie_sha256,state,source,reviewer,notes.')
    parser.add_argument('--root-release', help='Explicit root release JSON: movie_sha256,state=released,author.')
    parser.add_argument('--out')
    args = parser.parse_args()
    ROOT = args.staging_root.resolve()
    EPISODES = {args.episode: args.episode_dir.resolve()}
    EXPECTED = {args.episode: args.scene_count}
    build(args)
