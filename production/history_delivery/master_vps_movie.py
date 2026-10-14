"""Audio-only master of a completed native VPS render. Never encode video."""

if not __debug__:
    raise RuntimeError('Evidence tools require normal Python; optimization disables critical checks')
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, record):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(record, indent=2) + '\n')
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode-dir', type=Path, required=True)
    parser.add_argument('--project-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--normalization-proof', type=Path)
    parser.add_argument('--proof', type=Path)
    parser.add_argument('--author', default='root')
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--download-receipt', type=Path, required=True)
    args = parser.parse_args()
    root = args.episode_dir.resolve()
    project_id = args.project_id
    adoption = root / 'vps-adoption'
    normalization_path = args.normalization_proof or adoption / 'level-only-normalization-proof.json'
    normalization = json.loads(normalization_path.read_text())
    source = Path(normalization['derived'])
    assert digest(normalization['source']) == normalization['source_sha256']
    assert normalization['drift_samples'] == 0
    assert normalization['derived_sha256'] == digest(source)
    receipt = json.loads(args.download_receipt.read_text())
    base_sha = digest(args.base)
    assert receipt['project_id'] == project_id and receipt['sha256'] == base_sha
    assert Path(receipt['path']).resolve() == args.base.resolve() and receipt['method'] == 'GET'
    voice_proof = json.loads((adoption / 'voice-adoption.json').read_text())
    assert digest(source) == voice_proof['derived_voice_sha256']
    target = args.output.resolve()
    proof_path = args.proof or target.parent / 'audio-only-mastering.json'
    if target.exists() or proof_path.exists():
        assert target.exists() and proof_path.exists(), 'Incomplete previous mastering; inspect before retry'
        proof = json.loads(proof_path.read_text())
        assert proof['native_base_sha256'] == base_sha and proof['final_sha256'] == digest(target)
        assert proof['normalized_voice_sha256'] == digest(source)
        print(json.dumps({'episode': args.project_id, 'status': 'existing_hash_bound_master',
                          'file': str(target), 'sha256': proof['final_sha256']}))
        return
    version = subprocess.run([os.environ.get('HISTORY_FFMPEG', 'ffmpeg'), '-version'], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    command = [os.environ.get('HISTORY_FFMPEG', 'ffmpeg'), '-hide_banner', '-nostdin', '-n', '-xerror', '-i', str(args.base),
               '-i', str(source), '-map', '0:v:0', '-map', '1:a:0', '-map_metadata', '0',
               '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-ac', '1',
               '-movflags', '+faststart', str(target)]
    target.parent.mkdir(parents=True, exist_ok=True)
    with (target.parent / 'audio-only-mastering.log').open('w') as log:
        subprocess.run(command, check=True, stdout=log, stderr=log)
    spec = importlib.util.spec_from_file_location('native_binding', Path(__file__).with_name('media_identity.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base_packets, final_packets = module.video_packet_identity(args.base), module.video_packet_identity(target)
    assert base_packets == final_packets, 'Encoded video packets or timing changed'
    properties = ('codec_name', 'codec_tag_string', 'width', 'height', 'pix_fmt', 'r_frame_rate',
                  'avg_frame_rate', 'time_base', 'duration_ts', 'nb_frames', 'extradata_hash',
                  'extradata_size', 'start_pts')
    base_stream = module.probe_movie(args.base)['video_streams'][0]
    final_stream = module.probe_movie(target)['video_streams'][0]
    assert all(base_stream.get(k) == final_stream.get(k) for k in properties)
    final_sha = digest(target)
    proof = {'schema': 'native-vps-visual-audio-only-master-v1', 'author': args.author,
             'native_project_id': project_id, 'native_base_path': str(args.base.resolve()),
             'native_base_sha256': base_sha, 'final_path': str(target.resolve()),
             'final_sha256': final_sha, 'normalized_voice_path': str(source),
             'normalized_voice_sha256': digest(source),
             'normalization_proof': {'path': str(normalization_path), 'sha256': digest(normalization_path)},
             'video_codec_mode': 'copy', 'visual_encoding_performed': False,
             'audio_filter': 'Previously measured two-pass level-only normalization, no timing or content edit',
             'command': command, 'ffmpeg_version': version,
             'native_base_video_packets': base_packets, 'final_video_packets': final_packets,
             'encoded_video_packets_and_timing_identical': True,
             'video_stream_properties_identical': True,
             'compared_video_properties': list(properties),
             'completed_at': datetime.now(timezone.utc).isoformat()}
    save(proof_path, proof)
    print(json.dumps({'episode': args.project_id, 'status': 'video_copy_master_complete',
                      'file': str(target), 'sha256': final_sha, 'bytes': target.stat().st_size}))


if __name__ == '__main__':
    main()
