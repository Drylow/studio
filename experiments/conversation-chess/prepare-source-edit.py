"""Prepare explicitly authored scene cuts and remap native chess annotations.

This prepares a source intermediate, not a final export. Final assembly remains
in the existing Kdenlive workflow. No cropping, mirroring, playback-speed change or quality
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
    args = ['ffprobe', '-v', 'error', '-threads', '4']
    if count_frames:
        args.append('-count_frames')
    return json.loads(subprocess.check_output(args + [
        '-show_format', '-show_streams', '-of', 'json', str(file)]))


def verify_clock(file, frames):
    """Check decoded pictures AND samples; mux duration alone can hide truncation."""
    decoded = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-threads', '4', '-show_frames', '-show_entries',
        'frame=media_type,best_effort_timestamp_time,nb_samples', '-of', 'json', str(file)]))
    pictures, samples, worst = 0, 0, 0.0
    for frame in decoded['frames']:
        if frame['media_type'] == 'video':
            expected = pictures / 30
            pictures += 1
        elif frame['media_type'] == 'audio':
            expected = samples / 48000
            samples += int(frame['nb_samples'])
        else:
            raise RuntimeError('Unexpected decoded media stream.')
        drift = abs(float(frame['best_effort_timestamp_time']) - expected)
        worst = max(worst, drift)
        if drift > .0011:
            raise RuntimeError('Decoded frame/sample timestamps break the authored cadence.')
    if pictures != frames or samples != frames * 1600:
        raise RuntimeError('Decoded picture/audio totals disagree with the authored duration.')
    return {'video_frames': pictures, 'audio_samples_per_channel': samples,
            'maximum_timestamp_error_seconds': worst, 'timestamp_budget_seconds': .0011}


def prepare_cut(source, cut, file):
    duration = cut['frames'] / 30
    # Both filters have finite output. A global -t can stop the mux before the
    # final PCM packet drains, even when every authored picture was encoded.
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-ss', str(cut['in']), '-i', str(source),
                    '-vf', f'fps=30,trim=end_frame={cut["frames"]},setpts=N/(30*TB),setsar=1',
                    '-af', f'aresample=48000,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.02,afade=t=out:st={duration-.02}:d=0.02,apad,atrim=end_sample={cut["frames"]*1600},asetpts=N/SR/TB',
                    '-c:v', 'libx264', '-crf', '16', '-preset', 'superfast', '-threads', '4', '-pix_fmt', 'yuv420p',
                    '-enc_time_base:v', '1:30', '-fps_mode:v', 'passthrough', '-enc_time_base:a', '1:48000',
                    '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2', str(file)], check=True)


def finite_timestamp(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def conversation_at(conversations, source_at, source_out):
    """Use half-open chapter scopes; a boundary belongs to the new chapter."""
    if not finite_timestamp(source_at) or not conversations[0]['source_at'] <= source_at < source_out:
        return None
    return next(i for i in range(len(conversations) - 1, -1, -1)
                if conversations[i]['source_at'] <= source_at)


def remap_conversations(timeline, cuts, edit_opening):
    """Keep explicit chapter openings, refusing a cut which loses their evidence.

    The first chapter may lose its original opening only when the edit's own
    reviewed White opening replaces it. Later openings must remain in a cut.
    Absence of this optional list preserves the single-conversation workflow.
    """
    if 'conversations' not in timeline:
        return None, None
    original = timeline['conversations']
    if not isinstance(original, list) or not original:
        raise ValueError('conversations must be a nonempty ordered list of reviewed chapter openings.')
    source_in, source_out = timeline.get('source_in'), timeline.get('source_out')
    if not all(finite_timestamp(t) for t in (source_in, source_out)) or not 0 <= source_in < source_out:
        raise ValueError('Chapter scopes require the original source_in/source_out interval.')
    previous = None
    for chapter in original:
        if not isinstance(chapter, dict):
            raise ValueError('Each conversation must contain reviewed chapter metadata.')
        at = chapter.get('source_at')
        if not finite_timestamp(at) or not source_in <= at < source_out or (previous is not None and at <= previous):
            raise ValueError('Conversation source_at values must be strictly ordered inside the original source interval.')
        for camp in ('white', 'black'):
            label = chapter.get(camp + '_label')
            if not isinstance(label, str) or not label.strip():
                raise ValueError('Each conversation needs its reviewed White and Black labels.')
        if chapter['white_label'] == chapter['black_label']:
            raise ValueError('The two conversation camps must differ.')
        opening = chapter.get('opening')
        if (not isinstance(opening, dict) or opening.get('reviewed') is not True
                or opening.get('speaker') != 'white' or opening.get('label') != chapter['white_label']
                or not isinstance(opening.get('evidence'), str) or not opening['evidence'].strip()):
            raise ValueError('Each conversation opening requires reviewed White-first evidence matching its White label.')
        if 'source_at' in opening and (not finite_timestamp(opening['source_at']) or opening['source_at'] != at):
            raise ValueError('A conversation opening.source_at must match its chapter source_at.')
        if (chapter.get('initial_score_text') != '0.0' or not finite_timestamp(chapter.get('initial_control'))
                or chapter['initial_control'] != .5):
            raise ValueError('Each conversation must restart at initial_score_text=0.0 and initial_control=0.5.')
        previous = at
    first = original[0]
    if first['source_at'] != source_in:
        raise ValueError('The first conversation must start at the original source_in.')
    if (any(first[camp + '_label'] != timeline.get(camp + '_label') for camp in ('white', 'black'))
            or timeline.get('initial_score_text') != '0.0'
            or not finite_timestamp(timeline.get('initial_control')) or timeline['initial_control'] != .5):
        raise ValueError('The first conversation must agree with the global camps and initial 0.0/0.5 state.')
    global_opening = timeline['opening']
    if 'source_at' in global_opening and (not finite_timestamp(global_opening['source_at'])
                                         or global_opening['source_at'] != source_in):
        raise ValueError('The global opening.source_at must match the first conversation at source_in.')
    if any(c['in'] < source_in or c['out'] > source_out for c in cuts):
        raise ValueError('Retained chapter cuts must stay inside the original source_in/source_out interval.')
    if conversation_at(original, cuts[0]['in'], source_out) != 0:
        raise ValueError('The first retained cut must stay in the first conversation; later chapters cannot replace it.')

    remapped = []
    for index, chapter in enumerate(original):
        retained_at = cuts[0]['in'] if index == 0 else chapter['source_at']
        matches = [c for c in cuts if c['in'] <= retained_at < c['out']]
        if len(matches) != 1:
            raise ValueError(f'Conversation {index + 1} opening must remain in exactly one retained cut; do not silently omit a chapter.')
        cut = matches[0]
        mapped = round(cut['edited_in'] + retained_at - cut['in'], 9)
        if remapped and mapped <= remapped[-1]['source_at']:
            raise ValueError('Remapped conversation openings must remain strictly ordered.')
        result = copy.deepcopy(chapter)
        result.update(source_at=mapped, original_source_at=chapter['source_at'])
        result['opening'] = copy.deepcopy(edit_opening if index == 0 else chapter['opening'])
        result['opening'].update(source_at=mapped, original_source_at=retained_at)
        remapped.append(result)
    return original, remapped


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
    original_conversations, conversations = remap_conversations(timeline, cuts, opening)

    annotations, previous = [], -1
    for item in edit.get('annotations', []):
        index, at = item.get('base_index'), item.get('original_at')
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(timeline['annotations']):
            raise ValueError('Each remapped annotation must identify an existing base annotation.')
        if not isinstance(at, (int, float)) or not math.isfinite(at):
            raise ValueError('Annotation source timestamps must be finite.')
        if conversations is not None:
            base_at = timeline['annotations'][index].get('source_at')
            original_scope = conversation_at(original_conversations, base_at, timeline['source_out'])
            retained_scope = conversation_at(original_conversations, at, timeline['source_out'])
            if original_scope is None or retained_scope != original_scope:
                raise ValueError('An annotation cannot migrate to another conversation through original_at.')
            if at == original_conversations[retained_scope]['source_at'] or base_at == original_conversations[original_scope]['source_at']:
                raise ValueError('An annotation cannot coincide with a conversation opening.')
        matches = [c for c in cuts if c['in'] <= at < c['out']]
        if len(matches) != 1:
            raise ValueError(f'Annotation {at} must lie in exactly one retained cut.')
        cut = matches[0]
        mapped = round(cut['edited_in'] + at - cut['in'], 9)
        if mapped <= previous or not 0 < mapped < cursor / 30:
            raise ValueError('Remapped annotations must remain ordered and inside the edited scene.')
        if conversations is not None:
            if conversation_at(conversations, mapped, cursor / 30) != original_scope:
                raise ValueError('A remapped annotation must remain in its original conversation scope.')
            if mapped == conversations[original_scope]['source_at']:
                raise ValueError('An annotation cannot coincide with a remapped conversation opening.')
        a = copy.deepcopy(timeline['annotations'][index])
        a.update(source_at=mapped, original_source_at=at)
        if item.get('comment'):
            a['comment'] = item['comment']
        a['boundary_evidence'] = 'Mapped from the explicit retained source edit. ' + cut['reason']
        annotations.append(a)
        previous = mapped
    base = copy.deepcopy(timeline)
    base.update(source_in=0, source_out=cursor / 30, annotations=annotations, opening=copy.deepcopy(opening))
    if conversations is not None:
        base['conversations'] = conversations
        base['opening'] = copy.deepcopy(conversations[0]['opening'])
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
    clock_receipts = []
    for i, cut in enumerate(cuts):
        file = parts / f'cut-{i:02}.mkv'
        duration = cut['frames'] / 30
        prepare_cut(source, cut, file)
        meta = media_probe(file, count_frames=True)
        video = next(s for s in meta['streams'] if s['codec_type'] == 'video')
        if {k: video[k] for k in ('width', 'height')} != dimensions or int(video['nb_read_frames']) != cut['frames']:
            raise RuntimeError('An intermediate changed the native dimensions or authored frame count.')
        if abs(float(meta['format']['duration']) - duration) > .002:
            raise RuntimeError('Intermediate duration drift would shift later dialogue cuts.')
        if any(abs(float(s.get('start_time', 0))) > .002 for s in meta['streams']):
            raise RuntimeError('Intermediate tracks must start together at zero.')
        clock_receipts.append({'cut': i, **verify_clock(file, cut['frames'])})
        files.append(file)
        print(f'Prepared cut {i+1}/{len(cuts)}', flush=True)
    concat = out / 'parts.txt'
    concat.write_text(''.join(f"file 'parts/{f.name}'\nduration {cut['frames']/30:.12f}\n"
                              for f, cut in zip(files, cuts)), encoding='utf-8')
    edited = out / f'scene-edit-{dimensions["width"]}x{dimensions["height"]}.mkv'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-f', 'concat', '-safe', '0', '-i', str(concat),
                    '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'copy', '-r:v', '30',
                    '-af', f'asetpts=N/SR/TB,apad,atrim=end_sample={cursor*1600}',
                    '-enc_time_base:a', '1:48000', '-c:a', 'pcm_s16le', str(edited)], check=True)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(edited), '-f', 'null', '-'], check=True)
    probe = media_probe(edited, count_frames=True)
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    if int(video['nb_read_frames']) != cursor or {k: video[k] for k in ('width', 'height')} != dimensions:
        raise RuntimeError('Edited picture must preserve dimensions and authored frame count.')
    combined_clock = verify_clock(edited, cursor)
    base.update(source_sha256=digest(edited), source_in=0, source_out=cursor / 30, annotations=annotations)
    base['review_evidence'] = 'Explicit authored cuts; original source audio and key actions retained. Source cuts visually reviewed; full final-render review required. No clearance inferred.'
    base['source_edit'] = {'edit_file': str(editfile), 'original_source_sha256': edit['source_sha256'],
                           'native_dimensions': dimensions, 'cuts': cuts}
    base['youtube_clearance_verified'] = False
    timeline = out / 'timeline.json'
    timeline.write_text(json.dumps(base, indent=2) + '\n', encoding='utf-8')
    (out / 'cut-map.json').write_text(json.dumps({'original_source': str(source), 'edited_source': str(edited),
                                                 'native_dimensions': dimensions, 'frames': cursor, 'cuts': cuts,
                                                 'clock_verification': {'parts': clock_receipts, 'combined': combined_clock}}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'source': str(edited), 'timeline': str(timeline), 'source_duration': cursor / 30,
                      'final_expected_seconds': cursor / 30 + base['intro_seconds'] + base['outro_seconds'] + sum(a['hold_seconds'] for a in annotations)}))


if __name__ == '__main__':
    main()
