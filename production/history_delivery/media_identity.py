"""Actual ffprobe packet/timing identity; no visual approval."""
import hashlib
import json
import os
import subprocess

def probe_movie(path):
    result = subprocess.run(
        [os.environ.get('HISTORY_FFPROBE', 'ffprobe'), '-v', 'error', '-show_streams', '-show_format', '-show_data_hash', 'sha256',
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

def video_packet_identity(path):
    """Hash ordered encoded video packets and timing; never decode/encode frames."""
    result = subprocess.run([os.environ.get('HISTORY_FFPROBE', 'ffprobe'), '-v', 'error', '-select_streams', 'v:0',
        '-show_packets', '-show_data_hash', 'sha256', '-show_entries',
        'packet=pts,dts,duration,size,flags,data_hash', '-of', 'json', str(path)],
        check=True, capture_output=True, text=True)
    packets = json.loads(result.stdout).get('packets', [])
    if not packets or any(not p.get('data_hash') for p in packets):
        raise ValueError('No complete encoded video packet hash evidence')
    canonical = json.dumps(packets, sort_keys=True, separators=(',', ':')).encode()
    return {'method': 'ffprobe ordered encoded video packet data_sha256 plus pts,dts,duration,size,flags',
            'packet_count': len(packets), 'ordered_packets_sha256': hashlib.sha256(canonical).hexdigest()}
