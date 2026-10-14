"""Bind explicitly root-reviewed final history evidence or its seven delivery files."""

if not __debug__:
    raise RuntimeError('Evidence tools require normal Python; optimization disables critical checks')
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def artifact(path):
    return {'path': str(path.resolve()), 'sha256': digest(path)}


def save(path, data):
    data = json.dumps(data, indent=2) + '\n'
    if path.exists():
        assert path.read_text() == data, 'Different existing release; inspect rather than overwrite'
    else:
        path.write_text(data)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--profile', type=Path, required=True)
parser.add_argument('--movie', type=Path, required=True)
parser.add_argument('--movie-sha256', required=True)
parser.add_argument('--stage', choices=['evidence', 'manifest'], required=True)
parser.add_argument('--root-release', action='store_true', required=True)
args = parser.parse_args()
profile=json.loads(args.profile.read_text())
ep=Path(profile['base']).resolve()
delivery=ep/'delivery'
movie=args.movie.resolve()
assert digest(movie) == args.movie_sha256
qa_path = ep / 'final-vps-encoded-qa' / args.movie_sha256 / 'technical-proof.json'
qa = json.loads(qa_path.read_text())
visual_path = delivery / 'final-visual-qa.json'
visual = json.loads(visual_path.read_text())
count, frames, words = profile['scenes'], profile['frames'], profile['words']
assert qa['movie_sha256'] == visual['movie_sha256'] == args.movie_sha256
assert qa['full_av_fatal_decode_exit'] == 0 and qa['actual_decoded_video_frames'] == frames
assert visual['state'] == 'pass' and visual['finished_render_visual_reviewed'] is True
assert visual['reviewed_encoded_scene_count'] == count and visual['reviewed_cut_count'] == count - 1
assert {row['path'] for row in visual['capture_sheets']} == set(qa['capture_sheets'])
assert all(row['state'] == 'pass' and row['reviewer'] and row['notes']
           and digest(row['path']) == row['sha256'] for row in visual['capture_sheets'])
if args.stage == 'evidence':
    shutil.copyfile(qa_path, delivery / 'final-technical-qa.json')
    save(delivery / 'final-audio-analysis.json', {
        'movie_sha256': args.movie_sha256, 'measurements': qa['audio_measured_levels'],
        'actual_full_movie_measurement_evidence': artifact(qa_path)})
    final_evidence = {'technical': artifact(qa_path), 'visual': artifact(visual_path),
                      'audio_mastering': artifact(delivery / 'audio-only-mastering.json')}
    if (delivery / 'root-encoded-spot-check.json').exists():
        final_evidence['additional_root_encoded_spot_check'] = artifact(delivery / 'root-encoded-spot-check.json')
    save(delivery / 'final-quality-review.json', {
        'movie_sha256': args.movie_sha256, 'state': 'verified',
        'source': 'delegated_ai_inspection', 'reviewer': 'root',
        'notes': 'Complete fatal decode of final audio/video, actual final AAC levels and seven narration alignment checks passed. Every encoded scene midpoint, cut pair, first and last frame genuinely reviewed in the bound visual ledger. Exact native video packets and timing retained during audio-only mastering.',
        'evidence': final_evidence})
    release_path = delivery / 'root-film-release.json'
    if not release_path.exists():
        save(release_path, {'movie_sha256': args.movie_sha256, 'state': 'released',
                            'author': 'root', 'released_at': datetime.now(timezone.utc).isoformat()})
    else:
        previous = json.loads(release_path.read_text())
        assert previous['movie_sha256'] == args.movie_sha256 and previous['state'] == 'released'
else:
    files = [('video', movie)] + [(f'thumbnail_{k.lower()}', ep / 'thumbnails' / f'Thumbnail-{k}.jpg') for k in 'ABCD']
    files += [('upload_text', delivery / 'UPLOAD.txt'), ('captions', delivery / 'English-Captions.srt')]
    evidence = [('source_review', ep / 'combined-actual-source-review.json'),
                ('native_plan', ep / 'vps-adoption/exact-authored-scenes-new-vps-clock.json'),
                ('thumbnail_review', ep / 'thumbnails/export-and-actual-review.json'),
                ('caption_proof', delivery / 'caption-proof.json'),
                ('native_export', delivery / 'native-export-binding.json'),
                ('technical_qa', delivery / 'final-technical-qa.json'),
                ('visual_qa', visual_path)]
    rows = [{'role': role, **artifact(path)} for role, path in files]
    result = {'schema': 'history-gofile-delivery-v2', 'episode': profile['episode'],
              'expected': {'scene_count': count, 'canonical_words': words, 'frames': frames, 'fps': profile['fps']},
              'files': rows, 'evidence': {role: artifact(path) for role, path in evidence},
              'root_final_release': {'author': 'root', 'approved': True,
                                     'movie_sha256': args.movie_sha256,
                                     'delivery_file_sha256s': {row['role']: row['sha256'] for row in rows}}}
    save(delivery / 'gofile-final-manifest.json', result)
print(json.dumps({'episode': profile['episode'], 'stage': args.stage, 'movie_sha256': args.movie_sha256,
                  'network_calls': 0, 'uploads': 0}))
