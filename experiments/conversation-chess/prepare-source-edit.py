"""Prepare explicitly authored scene cuts and remap native chess annotations.

This prepares a source intermediate, not a final export. Final assembly remains
in the existing Kdenlive workflow. No cropping, mirroring, rate change or quality
reduction is applied. Content ID clearance is not inferred from a local edit.
"""
import argparse
import copy
import hashlib
import json
import math
import subprocess
from pathlib import Path


def digest(file):
    h = hashlib.sha256()
    with file.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def media_probe(file, count_frames=False):
    args = ['ffprobe', '-v', 'error']
    if count_frames:
        args.append('-count_frames')
    return json.loads(subprocess.check_output(args + [
        '-show_format', '-show_streams', '-of', 'json', str(file)]))


def plan_edit(edit, timeline, source_meta):
    """Validate authored decisions before creating media or an output directory."""
    if edit.get('schema') != 'conversation-chess-source-edit-v1' or edit.get('source_visually_reviewed') is not True:
        raise ValueError('Use an explicitly authored and visually reviewed edit.')
    if timeline.get('schema') != 'conversation-chess-clip-v1':
        raise ValueError('Use a native conversation-chess timeline.')
    video = next((s for s in source_meta['streams'] if s['codec_type'] == 'video'), None)
    if video is None or not any(s['codec_type'] == 'audio' for s in source_meta['streams']):
        raise ValueError('The reviewed source must contain video and its original audio.')
    dimensions = {'width': video['width'], 'height': video['height']}
    if edit.get('source_dimensions') != dimensions:
        raise ValueError('source_dimensions must match the reviewed source; no upscale or replacement is allowed.')
    if any(not isinstance(n, int) or n <= 0 or n % 2 for n in dimensions.values()):
        raise ValueError('The native dimensions must be positive even pixel counts for yuv420p.')
    if video.get('sample_aspect_ratio', '1:1') not in ('1:1', 'N/A', '0:1'):
        raise ValueError('Review a square-pixel source; silently changing its aspect ratio is not allowed.')
    rotation = video.get('tags', {}).get('rotate', 0)
    if float(rotation) % 360 or any(float(s.get('rotation', 0)) % 360 for s in video.get('side_data_list', [])):
        raise ValueError('Review a source with its display rotation resolved before making cuts.')
    source_duration = float(source_meta['format']['duration'])
    if not math.isfinite(source_duration) or source_duration <= 0:
        raise ValueError('The source must have a positive finite duration.')

    opening = edit.get('opening')
    if not isinstance(opening, dict) or opening.get('reviewed') is not True:
        raise ValueError('Each edit requires its own explicitly reviewed opening.')
    if opening.get('speaker') != 'white':
        raise ValueError('White must open the retained conversation.')
    for camp in ('white', 'black'):
        field = camp + '_label'
        if not isinstance(edit.get(field), str) or not edit[field].strip() or edit[field] != timeline.get(field):
            raise ValueError(f'Edit {field} must match the reviewed timeline camp.')
    if edit['white_label'] == edit['black_label'] or opening.get('label') != edit['white_label']:
        raise ValueError('The opening label must identify the White camp; the two camps must differ.')
    base_opening = timeline.get('opening', {})
    if base_opening.get('reviewed') is not True or base_opening.get('speaker') != 'white' or base_opening.get('label') != opening['label']:
        raise ValueError('The edited opening camps must agree with the reviewed source timeline.')
    if not isinstance(opening.get('evidence'), str) or not opening['evidence'].strip():
        raise ValueError('The edit opening needs evidence about the first retained dialogue.')

    cuts, cursor, previous = [], 0, -1
    if not isinstance(edit.get('cuts'), list) or not edit['cuts']:
        raise ValueError('Supply at least one authored cut.')
    for cut in edit['cuts']:
        times = [cut.get('in'), cut.get('out')]
        if any(not isinstance(t, (int, float)) or not math.isfinite(t) for t in times):
            raise ValueError('Cut boundaries must be finite source timestamps.')
        start, end = (round(t * 30) for t in times)
        if start < 0 or start < previous or end <= start or end / 30 > source_duration + .002 or not isinstance(cut.get('reason'), str) or not cut['reason'].strip():
            raise ValueError('Cuts must be ordered, inside the source, positive and editorially justified.')
        cuts.append({**cut, 'in': start / 30, 'out': end / 30,
                     'edited_in': cursor / 30, 'edited_out': (cursor + end - start) / 30,
                     'frames': end - start})
        cursor += end - start
        previous = end
    first_at = opening.get('source_at')
    if not isinstance(first_at, (int, float)) or not math.isfinite(first_at) or abs(first_at - cuts[0]['in']) > 1e-8:
        raise ValueError('opening.source_at must match the first retained cut, rather than the unedited opening.')

    annotations, previous = [], -1
    for item in edit.get('annotations', []):
        index, at = item.get('base_index'), item.get('original_at')
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(timeline['annotations']):
            raise ValueError('Each remapped annotation must identify an existing base annotation.')
        if not isinstance(at, (int, float)) or not math.isfinite(at):
            raise ValueError('Annotation source timestamps must be finite.')
        matches = [c for c in cuts if c['in'] <= at < c['out']]
        if len(matches) != 1:
            raise ValueError(f'Annotation {at} must lie in exactly one retained cut.')
        cut = matches[0]
        mapped = round(cut['edited_in'] + at - cut['in'], 9)
        if mapped <= previous or not 0 < mapped < cursor / 30:
            raise ValueError('Remapped annotations must remain ordered and inside the edited scene.')
        a = copy.deepcopy(timeline['annotations'][index])
        a.update(source_at=mapped, original_source_at=at)
        if item.get('comment'):
            a['comment'] = item['comment']
        a['boundary_evidence'] = 'Mapped from the explicit retained source edit. ' + cut['reason']
        annotations.append(a)
        previous = mapped
    base = copy.deepcopy(timeline)
    base.update(source_in=0, source_out=cursor / 30, annotations=annotations, opening=copy.deepcopy(opening))
    return base, cuts, cursor, dimensions


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
    if digest(source) != edit['source_sha256']:
        parser.error('Source differs from the reviewed original.')
    original_timeline = json.loads((editfile.parent / edit['timeline']).read_text(encoding='utf-8'))
    try:
        base, cuts, cursor, dimensions = plan_edit(edit, original_timeline, media_probe(source))
    except ValueError as error:
        parser.error(str(error))
    annotations = base['annotations']
    out.mkdir(parents=True)
    parts = out / 'parts'
    parts.mkdir()
    files = []
    for i, cut in enumerate(cuts):
        file = parts / f'cut-{i:02}.mkv'
        duration = cut['frames'] / 30
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-ss', str(cut['in']), '-i', str(source),
                        '-vf', f'fps=30,trim=end_frame={cut["frames"]},setpts=N/(30*TB),setsar=1',
                        '-af', f'aresample=48000,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.02,afade=t=out:st={duration-.02}:d=0.02,apad,atrim=end_sample={cut["frames"]*1600}',
                        '-c:v', 'libx264', '-crf', '16', '-preset', 'superfast', '-threads', '4', '-pix_fmt', 'yuv420p',
                        '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2', '-t', str(duration), str(file)], check=True)
        meta = media_probe(file, count_frames=True)
        video = next(s for s in meta['streams'] if s['codec_type'] == 'video')
        if {k: video[k] for k in ('width', 'height')} != dimensions or int(video['nb_read_frames']) != cut['frames']:
            raise RuntimeError('An intermediate changed the native dimensions or authored frame count.')
        if abs(float(meta['format']['duration']) - duration) > .002:
            raise RuntimeError('Intermediate duration drift would shift later dialogue cuts.')
        if any(abs(float(s.get('start_time', 0))) > .002 for s in meta['streams']):
            raise RuntimeError('Intermediate tracks must start together at zero.')
        files.append(file)
        print(f'Prepared cut {i+1}/{len(cuts)}', flush=True)
    concat = out / 'parts.txt'
    concat.write_text(''.join(f"file 'parts/{f.name}'\n" for f in files), encoding='utf-8')
    edited = out / f'scene-edit-{dimensions["width"]}x{dimensions["height"]}.mkv'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-f', 'concat', '-safe', '0', '-i', str(concat),
                    '-c', 'copy', str(edited)], check=True)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(edited), '-f', 'null', '-'], check=True)
    probe = media_probe(edited, count_frames=True)
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    if int(video['nb_read_frames']) != cursor or {k: video[k] for k in ('width', 'height')} != dimensions:
        raise RuntimeError('Edited picture must preserve dimensions and authored frame count.')
    base.update(source_sha256=digest(edited), source_in=0, source_out=cursor / 30, annotations=annotations)
    base['review_evidence'] = 'Explicit authored cuts; original source audio and key actions retained. Source cuts visually reviewed; full final-render review required. No clearance inferred.'
    base['source_edit'] = {'edit_file': str(editfile), 'original_source_sha256': edit['source_sha256'],
                           'native_dimensions': dimensions, 'cuts': cuts}
    base['youtube_clearance_verified'] = False
    timeline = out / 'timeline.json'
    timeline.write_text(json.dumps(base, indent=2) + '\n', encoding='utf-8')
    (out / 'cut-map.json').write_text(json.dumps({'original_source': str(source), 'edited_source': str(edited),
                                                 'native_dimensions': dimensions, 'frames': cursor, 'cuts': cuts}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'source': str(edited), 'timeline': str(timeline), 'source_duration': cursor / 30,
                      'final_expected_seconds': cursor / 30 + base['intro_seconds'] + base['outro_seconds'] + sum(a['hold_seconds'] for a in annotations)}))


if __name__ == '__main__':
    main()
