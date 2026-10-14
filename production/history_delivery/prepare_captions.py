"""Write exact English SRT from an existing reviewed canonical narration clock."""

if not __debug__:
    raise RuntimeError('Evidence tools require normal Python; optimization disables critical checks')
import argparse
import hashlib
import json
from pathlib import Path
import re
import textwrap

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def srt_stamp(value):
    milliseconds = round(value * 1000)
    h, milliseconds = divmod(milliseconds, 3600000)
    m, milliseconds = divmod(milliseconds, 60000)
    s, milliseconds = divmod(milliseconds, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{milliseconds:03d}'

def captions(script, clock, folder, duration):
    words = json.loads(clock.read_text())
    canonical = script.read_text().split()
    assert [w['w'] for w in words] == canonical
    groups = []
    group = []
    for word in words:
        candidate = group + [word]
        text = ' '.join(w['w'] for w in candidate)
        if group and (len(text) > 70 or len(candidate) > 12 or word['e'] - group[0]['s'] > 4.5):
            groups.append(group); group = []
        group.append(word)
        if len(group) >= 5 and re.search(r'[.!?]$', word['w']):
            groups.append(group); group = []
    if group:
        groups.append(group)
    cues = []
    for i, group in enumerate(groups, 1):
        start, end = group[0]['s'], group[-1]['e']
        assert 0 <= start < end <= duration + .01
        text = '\n'.join(textwrap.wrap(' '.join(w['w'] for w in group), width=42,
                                      break_long_words=False, break_on_hyphens=False))
        cues.append(f'{i}\n{srt_stamp(start)} --> {srt_stamp(end)}\n{text}')
    file = folder / 'English-Captions.srt'
    file.write_text('\n\n'.join(cues) + '\n', encoding='utf-8')
    spoken = []
    for cue in cues:
        spoken.extend(' '.join(cue.splitlines()[2:]).split())
    assert spoken == canonical
    proof = {'file': str(file), 'sha256': sha(file), 'source_clock': str(clock),
             'source_clock_sha256': sha(clock), 'literal_word_identity': True,
             'canonical_words': len(canonical), 'cues': len(cues),
             'timing_source': 'Actual provider audio clock adopted into exact canonical words; provider cue intervals subdivided by the native clock helper, not phoneme-perfect alignment.'}
    (folder / 'caption-proof.json').write_text(json.dumps(proof, indent=2) + '\n')

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script',type=Path,required=True)
    parser.add_argument('--clock',type=Path,required=True)
    parser.add_argument('--out-dir',type=Path,required=True)
    parser.add_argument('--duration',type=float,required=True)
    args=parser.parse_args()
    args.out_dir.mkdir(parents=True,exist_ok=True)
    if (args.out_dir/'English-Captions.srt').exists() or (args.out_dir/'caption-proof.json').exists():
        raise SystemExit('Existing caption output preserved; use a new output directory or inspect explicitly')
    captions(args.script.resolve(),args.clock.resolve(),args.out_dir.resolve(),args.duration)
    print('Exact canonical caption words checked; not phoneme-perfect timing or a movie review')
