"""Check delivered streams and extract review frames from the actual long export."""
import json
import subprocess

from PIL import Image, ImageDraw

from build import OUT, VIDEO, sha, verify


def audio_payload(path):
    return subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
        '-map', '0:a:0', '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-'], text=True).strip()


def main():
    verify()
    report = json.loads((OUT / 'technical-review.json').read_text())
    source_audio = audio_payload(OUT / 'final-audio.m4a')
    final_audio = audio_payload(VIDEO)
    assert source_audio == final_audio, 'Final audio payload differs from the approved mix'
    caption_review = json.loads((OUT / 'qa/captions-review.json').read_text())
    assert caption_review['technical_pass']
    srt = OUT / 'delivery/Silent-Little-Worlds-English.srt'
    assert sha(srt) == caption_review['inputs_sha256'][str(srt.relative_to(OUT.parents[2]))]
    target = OUT / 'qa/final'
    target.mkdir(parents=True, exist_ok=True)
    timeline = json.loads((OUT / 'timeline.json').read_text())
    # Chapter openings, regular samples, and encoded loop seams throughout the film.
    times = {0, 4, 9, 58.967, 59, 59.033, 3600, 7199, 7199.967}
    times.update(range(300, 7200, 300))
    times.update(round(c['start'] + 2, 3) for c in timeline['chapters'])
    for seam in (59 * 60, 59 * 120):
        times.update((round(seam - 1/30, 6), seam, round(seam + 1/30, 6)))
    times = sorted(times)
    for i, moment in enumerate(times):
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-threads', '1',
            '-ss', str(moment), '-i', str(VIDEO), '-frames:v', '1', '-q:v', '2',
            '-y', str(target / f'frame-{i:03}.jpg')], check=True)
    for page in range((len(times)+15)//16):
        sheet = Image.new('RGB', (1920,1176), '#222822')
        draw = ImageDraw.Draw(sheet)
        for cell, moment in enumerate(times[page*16:(page+1)*16]):
            i = page*16 + cell
            with Image.open(target / f'frame-{i:03}.jpg') as source:
                frame = source.resize((480,270), Image.Resampling.LANCZOS)
            x,y = cell%4*480, cell//4*294
            sheet.paste(frame,(x,y))
            draw.text((x+8,y+275), f'{moment//3600:.0f}:{int(moment//60)%60:02}:{moment%60:06.3f}', fill='white')
        sheet.save(target / f'contact-{page+1:02}.jpg', quality=95)
    result = {'sha256': report['sha256'], 'technical_pass': True,
        'audio_payload_identical_to_mix': True, 'audio_payload_sha256': source_audio,
        'captions_review_sha256': sha(OUT / 'qa/captions-review.json'),
        'srt_sha256': sha(OUT / 'delivery/Silent-Little-Worlds-English.srt'),
        'capture_times_seconds': times, 'contact_sheets': (len(times)+15)//16,
        'visual_review': 'pending inspection of the extracted images',
        'human_audio_listening': False}
    (target/'review-preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
