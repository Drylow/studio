"""Prepare explicitly authored scene cuts and remap native chess annotations.

This prepares a source intermediate, not a final export. Final assembly remains
in the existing Kdenlive workflow. No cropping, mirroring, rate change or quality
reduction is applied. Content ID clearance is not inferred from a local edit.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def digest(file):
    h = hashlib.sha256()
    with file.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--edit', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    source, editfile, out = args.source.resolve(strict=True), args.edit.resolve(strict=True), args.out.resolve()
    if out.exists():
        parser.error('Choose a new directory; preserve prior preparations.')
    edit = json.loads(editfile.read_text(encoding='utf-8'))
    if edit.get('schema') != 'conversation-chess-source-edit-v1' or not edit.get('source_visually_reviewed'):
        parser.error('Use an explicitly authored and visually reviewed edit.')
    if digest(source) != edit['source_sha256']:
        parser.error('Source differs from the reviewed original.')
    base = json.loads((editfile.parent / edit['timeline']).read_text(encoding='utf-8'))
    cuts, cursor, previous = [], 0, -1
    for cut in edit['cuts']:
        start, end = round(cut['in'] * 30), round(cut['out'] * 30)
        if start < previous or end <= start or not cut.get('reason'):
            parser.error('Cuts must be ordered, positive and editorially justified.')
        cuts.append({**cut, 'in': start / 30, 'out': end / 30,
                     'edited_in': cursor / 30, 'edited_out': (cursor + end - start) / 30,
                     'frames': end - start})
        cursor += end - start
        previous = end
    def map_time(t):
        match = [c for c in cuts if c['in'] <= t < c['out']]
        if len(match) != 1:
            raise ValueError(f'Annotation {t} must lie in exactly one retained cut.')
        c = match[0]
        return c['edited_in'] + t - c['in']
    annotations = []
    for item in edit['annotations']:
        a = dict(base['annotations'][item['base_index']])
        a['source_at'] = round(map_time(item['original_at']), 9)
        a['original_source_at'] = item['original_at']
        if item.get('comment'):
            a['comment'] = item['comment']
        a['boundary_evidence'] = 'Mapped from the explicit retained source edit. ' + next(
            c['reason'] for c in cuts if c['in'] <= item['original_at'] < c['out'])
        annotations.append(a)
    out.mkdir(parents=True)
    parts = out / 'parts'
    parts.mkdir()
    files = []
    for i, cut in enumerate(cuts):
        file = parts / f'cut-{i:02}.mkv'
        duration = cut['frames'] / 30
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-ss', str(cut['in']), '-i', str(source),
                        '-vf', 'fps=30,setpts=N/(30*TB),setsar=1', '-frames:v', str(cut['frames']),
                        '-af', f'aresample=48000,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.02,afade=t=out:st={duration-.02}:d=0.02,apad,atrim=end_sample={cut["frames"]*1600}',
                        '-c:v', 'libx264', '-crf', '16', '-preset', 'superfast', '-threads', '4', '-pix_fmt', 'yuv420p',
                        '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2', '-t', str(duration), str(file)], check=True)
        meta = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(file)]))
        if abs(float(meta['format']['duration']) - duration) > .002:
            raise RuntimeError('Intermediate duration drift would shift later dialogue cuts.')
        if any(abs(float(s.get('start_time', 0))) > .002 for s in meta['streams']):
            raise RuntimeError('Intermediate tracks must start together at zero.')
        files.append(file)
        print(f'Prepared cut {i+1}/{len(cuts)}', flush=True)
    concat = out / 'parts.txt'
    concat.write_text(''.join(f"file 'parts/{f.name}'\n" for f in files), encoding='utf-8')
    edited = out / 'scene-edit-1080.mkv'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-f', 'concat', '-safe', '0', '-i', str(concat),
                    '-c', 'copy', str(edited)], check=True)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(edited), '-f', 'null', '-'], check=True)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-of', 'json', str(edited)]))
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    if int(video['nb_read_frames']) != cursor or (video['width'], video['height']) != (1920, 1080):
        raise RuntimeError('Edited picture must preserve dimensions and authored frame count.')
    base.update(source_sha256=digest(edited), source_in=0, source_out=cursor / 30, annotations=annotations)
    base['opening']['evidence'] = 'The first retained line is the televised representative introducing himself on behalf of L. L remains White and Light Black.'
    base['review_evidence'] = 'Explicit authored cuts; original English dub and key actions retained. Source cuts visually reviewed; full final-render review required. No clearance inferred.'
    base['source_edit'] = {'edit_file': str(editfile), 'original_source_sha256': edit['source_sha256'], 'cuts': cuts}
    base['youtube_clearance_verified'] = False
    timeline = out / 'timeline.json'
    timeline.write_text(json.dumps(base, indent=2) + '\n', encoding='utf-8')
    (out / 'cut-map.json').write_text(json.dumps({'original_source': str(source), 'edited_source': str(edited), 'frames': cursor, 'cuts': cuts}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'source': str(edited), 'timeline': str(timeline), 'source_duration': cursor / 30,
                      'final_expected_seconds': cursor / 30 + base['intro_seconds'] + base['outro_seconds'] + sum(a['hold_seconds'] for a in annotations)}))


if __name__ == '__main__':
    main()
