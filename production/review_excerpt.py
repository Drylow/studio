"""Render an explicitly selected review excerpt, never a completed episode."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image

import edo_episode as ep
import historical_renderer


def prepare(manifest):
    assert manifest['phase'] == 'review-excerpt-NOT-complete-episode'
    assert manifest['selection'] and len(set(manifest['selection'])) == len(manifest['selection'])
    work = Path(manifest['workdir'])
    work.mkdir(parents=True, exist_ok=True)
    audio = Path(manifest['source_audio'])
    clock = ep.read(manifest['word_clock'])
    assert clock['audio_sha256'] == ep.digest(audio)
    tokens = Path(manifest['script']).read_text(encoding='utf-8').split()
    reviews = {r['file']: r for r in ep.read(manifest['shot_reviews'])['reviews']}
    for r in ep.read(manifest['opening_reviews'])['reviews']:
        if r['file'].startswith(manifest['channel'] + '/'):
            reviews[Path(r['file']).name] = {**r, 'accepted': r['creative_accepted']}
    frames = work / 'frames'
    frames.mkdir(exist_ok=True)
    source_work = Path(manifest['source_audio']).parent
    openings = ep.read(source_work / 'opening_requests.json')
    authored = ep.read(Path(manifest['script']).parent / 'shot-authoring.json')['shots']
    source_plans = {s['id']: s for s in openings + authored}
    cursor, shots, source_hashes = 0, [], set()
    for index, selected in enumerate(manifest['selection']):
        source = Path('output/imagegen/historical-01-2026-10-08') / manifest['channel'] / 'shots' / (selected + '.png')
        source_hash = ep.digest(source)
        assert source_hash not in source_hashes, 'Repeated image bytes cannot fill an excerpt'
        source_hashes.add(source_hash)
        review = reviews.get(source.name)
        # One original shot has a later explicit sequence-review entry.
        if not review or not review['accepted']:
            matching = [r for r in ep.read(manifest['shot_reviews'])['reviews']
                        if r['file'] == source.name and r['accepted']]
            assert matching, selected
            review = matching[-1]
        base_id = '-'.join(selected.split('-')[:3])
        source_plan = source_plans[base_id]
        receipt_path = source_work / 'image-jobs' / (selected + '.request.json')
        if receipt_path.exists():
            receipt = ep.read(receipt_path)
        else:
            assert selected == base_id and base_id in {s['id'] for s in openings}
            receipt = {'ordered_references': [
                {'path': path, 'sha256': sha}
                for path, sha in zip(source_plan['references'], source_plan['input_sha256'])]}
        first, last = source_plan['word_start'], source_plan['word_end']
        assert first == cursor, (selected, first, cursor)
        start = clock['words'][first]['s'] if first else 0.0
        end = clock['words'][last + 1]['s']
        assert 0 < end - start <= manifest['max_shot_seconds']
        narration = ' '.join(tokens[first:last + 1])
        if 'narration' in receipt:
            assert receipt['narration'].split() == narration.split()
        for ref in receipt['ordered_references']:
            assert ep.digest(ref['path']) == ref['sha256'], ref['path']
        with Image.open(source) as im:
            alpha_range = None
            if 'A' in im.getbands():
                alpha_range = im.getchannel('A').getextrema()
                # Fully transparent pixels need creative repair, not a black matte.
                assert alpha_range[0] > 0, selected
        target = frames / f'{index + 1:03}.png'
        subprocess.run([ep.media.ffmpeg_bin(), '-v', 'error', '-y', '-i', str(source),
                        '-vf', 'format=rgb24,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080',
                        '-frames:v', '1', str(target)], check=True)
        shots.append({'id': selected, 'source': str(source), 'source_sha256': source_hash,
                      'image': str(target), 'sha256': ep.digest(target),
                      'source_alpha_range': alpha_range,
                      'format_transform': 'Preserve RGB colours, discard nonzero provider alpha; centre crop to 16:9. Manual final-frame review required.',
                      'start': start, 'end': end, 'narration': narration,
                      'motion': 'zoom_in', 'references': receipt['ordered_references'],
                      'creative_review': review['notes']})
        cursor = last + 1
    ep.validate_cadence(manifest, shots, tail=manifest['tail'])
    ep.save(work / 'timeline.json', {'phase': manifest['phase'], 'shots': shots,
                                    'source_audio_sha256': ep.digest(audio), 'end': shots[-1]['end']})
    print(f"Prepared {len(shots)} distinct frames through {shots[-1]['end']:.2f}s; visual format approval required.")


def render(manifest):
    work = Path(manifest['workdir'])
    plan = ep.read(work / 'timeline.json')
    assert plan['phase'] == manifest['phase'] == 'review-excerpt-NOT-complete-episode'
    assert plan['source_audio_sha256'] == ep.digest(manifest['source_audio'])
    assert [s['id'] for s in plan['shots']] == manifest['selection']
    approval = ep.read(work / 'format-review.json')
    for shot in plan['shots']:
        assert approval[shot['id']]['accepted']
        assert approval[shot['id']]['notes'].strip()
        assert approval[shot['id']]['sha256'] == ep.digest(shot['image']) == shot['sha256']
        assert ep.digest(shot['source']) == shot['source_sha256']
        for ref in shot['references']:
            assert ep.digest(ref['path']) == ref['sha256']
    audio = work / 'excerpt.mp3'
    subprocess.run([ep.media.ffmpeg_bin(), '-v', 'error', '-y', '-i', manifest['source_audio'],
                    '-t', str(plan['end']), '-c:a', 'libmp3lame', '-q:a', '2', str(audio)], check=True)
    actual = ep.media.duration(str(audio))
    assert abs(actual - plan['end']) < 0.1
    plan['shots'][-1]['end'] = actual
    ep.validate_cadence(manifest, plan['shots'], tail=manifest['tail'])
    build = work / 'render'
    build.mkdir(exist_ok=True)
    output = Path(manifest['export'])
    output.parent.mkdir(parents=True, exist_ok=True)
    result = historical_renderer.render_video(manifest, str(build), plan['shots'], str(audio), str(output),
                                    width=1920, height=1080, fps=30, motion_strength=0.025,
                                    transition='fade', transition_dur=0.15, quality='high',
                                    captions={'mode': 'none'}, tail=manifest['tail'],
                                    progress=lambda p, msg: print(f'{p:.0%} {msg}', flush=True))
    ep.save(work / 'render-result.json', {**result, 'phase': manifest['phase'],
                                        'audio_sha256': ep.digest(audio), 'qa_pending': True})


def qa(manifest):
    from PIL import ImageDraw

    assert manifest['phase'] == 'review-excerpt-NOT-complete-episode'
    work, final = Path(manifest['workdir']), Path(manifest['export'])
    plan = ep.read(work / 'timeline.json')
    result = ep.read(work / 'render-result.json')
    assert plan['phase'] == result['phase'] == manifest['phase']
    assert plan['source_audio_sha256'] == ep.digest(manifest['source_audio'])
    assert result['audio_sha256'] == ep.digest(work / 'excerpt.mp3')
    probe = shutil.which('ffprobe')
    assert probe, 'Independent stream verification requires ffprobe'
    measured = subprocess.run([probe, '-v', 'error', '-count_frames', '-show_streams',
                               '-of', 'json', str(final)], capture_output=True, text=True, check=True)
    assert not measured.stderr.strip(), measured.stderr[:500]
    streams = json.loads(measured.stdout)['streams']
    timing_plan = {**plan, 'duration': ep.media.duration(str(work / 'excerpt.mp3'))}
    timing_plan['shots'][-1]['end'] = timing_plan['duration']
    frame_count = ep.validate_render_timing(timing_plan, streams)
    video = next(s for s in streams if s['codec_type'] == 'video')
    assert (video['width'], video['height']) == (1920, 1080)
    decoded = subprocess.run([ep.media.ffmpeg_bin(), '-v', 'error', '-i', str(final),
                              '-f', 'null', '-'], capture_output=True, text=True)
    assert decoded.returncode == 0 and not decoded.stderr.strip(), decoded.stderr[:500]
    check = work / 'check'
    check.mkdir(exist_ok=True)
    captures = []
    for shot in plan['shots']:
        for part, fraction in enumerate((0.2, 0.5, 0.8), 1):
            at = shot['start'] + (shot['end'] - shot['start']) * fraction
            path = check / f"{shot['id']}_{part}.jpg"
            subprocess.run([ep.media.ffmpeg_bin(), '-v', 'error', '-y', '-ss', str(at),
                            '-i', str(final), '-frames:v', '1', '-q:v', '2', str(path)], check=True)
            captures.append((shot['id'], at, path))
    for batch in range(0, len(captures), 18):
        sheet = Image.new('RGB', (1920, 2280), '#181818')
        draw = ImageDraw.Draw(sheet)
        for j, (sid, at, path) in enumerate(captures[batch:batch + 18]):
            x, y = (j % 3) * 640, (j // 3) * 380
            with Image.open(path) as im:
                im.thumbnail((640, 360))
                sheet.paste(im, (x, y))
            draw.text((x + 8, y + 361), f'{sid} - {at:.2f}s', fill='white')
        sheet.save(check / f'sheet_{batch // 18 + 1:02}.jpg', quality=95)
    ep.save(work / 'qa-technical.json', {'phase': manifest['phase'], 'decoded_without_errors': True,
            'video_sha256': ep.digest(final), 'video_frames': frame_count, 'streams': streams,
            'capture_count': len(captures), 'manual_montage_review_pending': True,
            'note': 'Audio streams and full decode checked technically; this does not claim a listening review.'})
    print(f'Technical checks passed: {frame_count} video frames and {len(captures)} captures. Manual montage review required.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest')
    parser.add_argument('--stage', choices=('prepare', 'render', 'qa'), required=True)
    args = parser.parse_args()
    globals()[args.stage](ep.read(args.manifest))
