"""Read-only hash/semantic gate for the authorized audio-only finishing branch."""
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit


def validate(native, profile, count, frames, pin, json_file, require, import_manifest, provider, caption_clock):
    base = native.get('native_base', {})
    require(isinstance(base, dict), 'Separate native base artifact required')
    base_path = pin(base['path'], base['sha256'])
    require(base['sha256'] != native['sha256'] and str(base_path) != str(Path(native['absolute_file']).resolve()),
            'Raw native base and audio-mastered final must remain distinct')
    receipt = json_file(base['download_receipt'])
    require(receipt.get('method') == 'GET' and receipt.get('project_id') == profile['project_id']
            and receipt.get('sha256') == base['sha256']
            and str(Path(receipt['path']).resolve()) == str(base_path), 'Native base must bind the actual authenticated API GET receipt')
    mastering = json_file(native['audio_mastering'])
    require(mastering.get('schema') == 'native-vps-visual-audio-only-master-v1'
            and mastering.get('author') == 'root' and mastering.get('native_project_id') == profile['project_id']
            and mastering.get('native_base_sha256') == base['sha256']
            and str(Path(mastering['native_base_path']).resolve()) == str(base_path)
            and mastering.get('final_sha256') == native['sha256']
            and str(Path(mastering['final_path']).resolve()) == str(Path(native['absolute_file']).resolve()),
            'Actual root audio-mastering proof must identify both distinct movie artifacts')
    require(mastering.get('video_codec_mode') == 'copy' and mastering.get('visual_encoding_performed') is False
            and mastering.get('encoded_video_packets_and_timing_identical') is True
            and mastering.get('video_stream_properties_identical') is True, 'No video re-encoding or packet/timing/stream change is allowed')
    base_packets, final_packets = mastering.get('native_base_video_packets'), mastering.get('final_video_packets')
    require(isinstance(base_packets, dict) and base_packets == final_packets
            and base_packets.get('packet_count') == frames
            and re.fullmatch(r'[a-f0-9]{64}', str(base_packets.get('ordered_packets_sha256', ''))),
            'Actual ordered encoded video packets and timing SHA must match for the complete movie')
    command = mastering.get('command', [])
    require(isinstance(command, list) and command.count('-c:v') == 1
            and command[command.index('-c:v')+1] == 'copy'
            and not any(x in command for x in ['-vf','-filter:v','-filter_complex'])
            and mastering.get('ffmpeg_version'), 'Actual mastering command must copy video without a visual filter')
    normalization = json_file(mastering['normalization_proof'])
    source_path = pin(normalization['source'], normalization['source_sha256'])
    derived_path = pin(normalization['derived'], normalization['derived_sha256'])
    require(mastering.get('normalized_voice_sha256') == normalization['derived_sha256']
            and str(Path(mastering['normalized_voice_path']).resolve()) == str(derived_path), 'Mastering must use the actual normalized FLAC')
    require(normalization.get('source_decode') == normalization.get('derived_decode')
            and normalization.get('source_decode',{}).get('samples',0) > 0
            and normalization['source_decode'].get('rate') == 44100
            and normalization['source_decode'].get('layout') == 'mono'
            and normalization.get('drift_samples') == 0 and normalization.get('drift_ms') == 0,
            'Normalization must retain all decoded samples, sample rate/layout and zero clock drift')
    levels = normalization.get('final_levels', {})
    require(-19 < float(levels.get('input_i', '-100')) < -15
            and float(levels.get('input_tp', '100')) < -.3, 'Measured normalized voice levels must pass')
    adoption = json_file({'path': str(Path(profile.get('voice_adoption_path') or (Path(profile['base'])/'vps-adoption/voice-adoption.json'))),
                          'sha256': native['voice_adoption_sha256']})
    require(adoption.get('project_id') == profile['project_id'] and adoption.get('total_frames') == frames
            and adoption.get('sample_rate') == 44100 and adoption.get('decoded_samples') == normalization['source_decode']['samples']
            and abs(adoption.get('duration_seconds',0)-profile['duration']) < .001
            and adoption.get('original_voice_sha256') == normalization['source_sha256']
            and adoption.get('derived_voice_sha256') == normalization['derived_sha256']
            and str(Path(adoption['official_voice_path']).resolve()) == str(source_path)
            and str(Path(adoption['comparison_voice_path']).resolve()) == str(derived_path),
            'Both voice artifacts must bind the actual current native project/adoption clock')
    require(provider.get('schema') == 'native-existing-media-delivery-proof-v1'
            and provider.get('proof_state') == 'complete' and provider.get('expected_ordered_scene_count') == count
            and provider.get('verification_checks') and all(x.get('state') == 'passed' for x in provider['verification_checks'])
            and provider.get('official_native_project', {}).get('id') == profile['project_id'], 'Complete actual native API import/render/derivation proof required')
    expected_hashes = native['scene_image_sha256s']
    require([x.get('id') for x in provider.get('ordered_scenes', [])] == list(range(1,count+1))
            and [x.get('selected_source',{}).get('sha256') for x in provider['ordered_scenes']] == expected_hashes,
            'Current native proof must contain every selected source image in exact order')
    artifacts = provider['source_artifacts']
    require(artifacts['combined_selected_source_review']['sha256'] == native['source_review_sha256']
            and artifacts['native_import_manifest']['sha256'] == native['native_import']['sha256'], 'Current source/import proof SHA binding differs')
    official_voice = provider['official_voice']
    require(official_voice['downloaded_official_voice']['sha256'] == normalization['source_sha256']
            and str(Path(official_voice['downloaded_official_voice']['path']).resolve()) == str(source_path)
            and official_voice['actual_word_clock']['sha256'] == import_manifest['official_clock_sha256']
            and str(Path(official_voice['actual_word_clock']['path']).resolve()) == str(Path(import_manifest['official_clock_path']).resolve()), 'Official project voice/word-clock import association differs')
    actual_clock = json_file(official_voice['actual_word_clock'])
    require(actual_clock.get('words') == caption_clock and len(caption_clock) == profile['words'], 'Caption clock must equal the exact current official native word list')
    render = provider['official_native_render']; raw = render['raw_native_api_base']; final = render['final_derived_movie']
    origin = profile.get('portal_origin', 'https://tools.kanye.studio')
    received_url = urlsplit(urljoin(origin, receipt.get('endpoint','')))
    official_url = urlsplit(urljoin(origin, render.get('official_video_download_endpoint') or ''))
    require(received_url == official_url and received_url.scheme == 'https' and received_url.hostname == urlsplit(origin).hostname
            and received_url.port in (None,443) and received_url.username is None and received_url.password is None,
            'Native GET receipt must match the full current HTTPS portal endpoint, including origin and query')
    require(raw.get('origin',{}).get('state') == 'verified' and raw['file']['sha256'] == base['sha256']
            and str(Path(raw['file']['path']).resolve()) == str(base_path)
            and raw['origin']['receipt']['sha256'] == base['download_receipt']['sha256'], 'Current provider proof must identify the downloaded raw API base')
    derivation = final.get('derivation',{})
    require(final['file']['sha256'] == native['sha256']
            and str(Path(final['file']['path']).resolve()) == str(Path(native['absolute_file']).resolve())
            and derivation.get('state') == 'verified'
            and derivation['provenance']['sha256'] == native['audio_mastering']['sha256']
            and derivation.get('native_base_video_packets') == base_packets
            and derivation.get('final_video_packets') == final_packets
            and derivation.get('encoded_video_packets_and_timing_identical') is True
            and derivation.get('video_stream_properties_identical') is True
            and render.get('final_movie_audio',{}).get('state') == 'verified', 'Provider proof must independently bind final audio-only derivation and measured audio')
    audio = render['final_movie_audio']
    require(-18 <= float(audio.get('observed_integrated_lufs', '-100')) <= -16
            and float(audio.get('observed_true_peak_dbtp','100')) < -.3, 'Actual final AAC mastering measurements must remain within the stricter native proof range')
    final_review = final.get('final_quality_review',{})
    require(final_review.get('state') == 'verified' and final_review.get('record',{}).get('movie_sha256') == native['sha256']
            and final_review['record'].get('state') == 'verified' and final_review['record'].get('reviewer')
            and final_review['record'].get('notes') and final_review['record'].get('source') in ('delegated_ai_inspection','explicit_human_review'),
            'Actual provider delivery proof must retain genuine final derivative quality review')
    json_file(final_review['evidence']); json_file(provider['release']['evidence'])
    json_file(audio['evidence'])
    require(provider.get('release',{}).get('state') == 'released_by_root'
            and provider['release']['record'].get('state') == 'released'
            and provider['release']['record'].get('author') == 'root'
            and provider['release']['record'].get('movie_sha256') == native['sha256'], 'Actual root final-movie release must bind the mastered derivative')
    return normalization
