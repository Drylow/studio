"""Inspect the encoded garden loop, its seam and actual motion regions."""
from pathlib import Path
import hashlib
import json
import subprocess

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'output/nature-sleep/garden-production'
QA = OUT / 'qa'
movie = OUT / 'loop.mp4'
receipt = json.loads((OUT / 'render-receipt.json').read_text())
transform = json.loads((OUT / 'loop-transform.json').read_text())
assert hashlib.file_digest(movie.open('rb'), 'sha256').hexdigest() == transform['sha256']
assert hashlib.file_digest((OUT / 'loop-master.mp4').open('rb'), 'sha256').hexdigest() == receipt['sha256'] == transform['master_sha256']
count = transform['frames']
duration = transform['duration']
assert receipt['native_cycle_exact_match']
assert not receipt['browser_errors']
probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames',
        '-show_streams', '-show_format', '-of', 'json', str(movie)]))
v = probe['streams'][0]
assert len(probe['streams']) == 1
assert (v['width'], v['height'], v['avg_frame_rate'], int(v['nb_read_frames'])) == (1920, 1080, '30/1', count)
assert abs(float(probe['format']['duration']) - duration) < .01
# Decode every source frame and keep lightweight signatures to identify freezes,
# corrupt frames and abrupt luminance changes across the complete source cycle.
decoded = subprocess.check_output(['ffmpeg', '-v', 'error', '-xerror', '-threads', '2',
        '-i', str(movie), '-vf', 'scale=160:90', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'])
all_frames = np.frombuffer(decoded, np.uint8).reshape(count, 90, 160, 3)
motion = np.mean(np.abs(np.diff(all_frames.astype(np.int16), axis=0)), axis=(1, 2, 3))
assert np.isfinite(motion).all() and float(motion.max()) < 3
assert int(np.sum(motion == 0)) == 0, 'A duplicate adjacent source frame was found'
indices = sorted(set(range(0, count, 15)) | {1, 2, 3, count-4, count-3, count-2, count-1})
expression = f'not(mod(n,15))+lt(n,4)+gte(n,{count-4})'
subprocess.run(['ffmpeg', '-v', 'error', '-i', str(movie), '-vf', f"select='{expression}'",
    '-vsync', '0', '-q:v', '2', '-y', str(QA / 'frame-%03d.jpg')], check=True)
frames = {}
for k, index in enumerate(indices, 1):
    frames[index] = np.asarray(Image.open(QA / f'frame-{k:03}.jpg').convert('RGB'))
for page in range((len(indices) + 15) // 16):
    sheet = Image.new('RGB', (1920, 1176), '#222822')
    draw = ImageDraw.Draw(sheet)
    for cell, index in enumerate(indices[page*16:(page+1)*16]):
        im = Image.fromarray(frames[index]).resize((480, 270), Image.Resampling.LANCZOS)
        x, y = cell % 4 * 480, cell // 4 * 294
        sheet.paste(im, (x, y)); draw.text((x+8, y+275), f'{index/30:.3f}s / frame {index}', fill='white')
    sheet.save(QA / f'contact-{page+1:02}.jpg', quality=95)
def mad(a, b, box=None):
    aa, bb = frames[a], frames[b]
    if box:
        x0, y0, x1, y1 = box; aa = aa[y0:y1, x0:x1]; bb = bb[y0:y1, x0:x1]
    return float(np.mean(np.abs(aa.astype(float)-bb.astype(float))))
regions = {'pond': [1460, 762, 1740, 826], 'tea_steam': [530, 528, 611, 635],
           'cat_body': [115, 692, 272, 773], 'rain': [1350, 193, 1560, 272],
           'greenhouse_structure': [620, 302, 1000, 469], 'dry_bench': [20, 515, 260, 605]}
motion_regions = {key: mad(0, 90, box) for key, box in regions.items()}
assert motion_regions['pond'] > .5
assert motion_regions['greenhouse_structure'] < 1
assert motion_regions['dry_bench'] < 1
neighbors = [mad(a,b) for a,b in [(0,1),(1,2),(2,3),(count-4,count-3),(count-3,count-2),(count-2,count-1)]]
seam = mad(count-1,0)
assert seam < max(neighbors)*1.8 + .05, 'Loop seam needs review'
result = {'technical_pass': True, 'sha256': transform['sha256'], 'duration': duration,
          'frames': count, 'resolution': [1920,1080], 'fps':30,
          'all_source_frames_decoded': True, 'duplicate_adjacent_frames':int(np.sum(motion == 0)),
          'native_master_endpoints_identical': True, 'encoded_seam_mad':seam,
          'encoded_loop_correction': 'One-second cyclic crossfade, lossless intermediate',
          'neighbor_mad':neighbors, 'motion_mad_regions':motion_regions,
          'all_frame_small_signature_motion_max':float(motion.max()),
          'all_frame_small_signature_motion_min':float(motion.min()),
          'captures':len(indices), 'contact_sheets':(len(indices)+15)//16,
          'human_continuous_playback':False, 'visual_review':'pending separate inspection'}
(QA/'technical-review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
