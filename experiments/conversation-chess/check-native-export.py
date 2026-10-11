#!/usr/bin/env python3
"""Check a completed native Conversation Chess export and extract review frames.

Compares the actual delivered audio with actual prepared tracks, not transcripts.
It never sets the visual-review or human-listening approvals.
"""
import argparse
import hashlib
import json
import math
import re
import subprocess
import time
import wave
import concurrent.futures
from PIL import Image, ImageDraw, ImageFont
from fractions import Fraction
from pathlib import Path

import numpy as np

RATE = 48000
CHANNELS = 2
FPS = 30
SAMPLES_PER_FRAME = RATE // FPS


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for data in iter(lambda: source.read(8 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
        '-show_streams', '-show_format', '-of', 'json', str(path)],
        capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def read_wav(path):
    with wave.open(str(path), 'rb') as source:
        if source.getframerate() != RATE or source.getnchannels() != CHANNELS or source.getsampwidth() != 2:
            raise ValueError(f'Prepared audio must be stereo PCM16 at 48 kHz: {path.name}')
        frames = source.getnframes()
        pcm = np.frombuffer(source.readframes(frames), dtype='<i2').reshape(-1, CHANNELS)
        return pcm.astype(np.float32) / 32768.0


def db(value):
    return float(20 * math.log10(value)) if value > 0 else -300.0


def rms(array):
    if not len(array):
        return 0.0
    data = np.asarray(array, dtype=np.float64)
    return float(np.sqrt(np.mean(data * data)))


def peak(array):
    return float(np.max(np.abs(array))) if len(array) else 0.0


def correlation_with_lag(expected, observed, padding):
    """FFT valid correlation with exact local variance, searching +/-padding."""
    x = np.asarray(expected, dtype=np.float64)
    y = np.asarray(observed, dtype=np.float64)
    if len(y) != len(x) + 2 * padding:
        raise ValueError('Correlation window length mismatch')
    x -= np.mean(x)
    var_x = float(np.sum(x * x))
    if var_x < 1e-10:
        return {'silent_reference': True}
    size = 1 << (len(x) + len(y) - 2).bit_length()
    convolution = np.fft.irfft(np.fft.rfft(y, size) * np.fft.rfft(x[::-1], size), size)
    numerator = convolution[len(x) - 1:len(y)]
    sums = np.concatenate(([0.0], np.cumsum(y)))
    squares = np.concatenate(([0.0], np.cumsum(y * y)))
    window_sum = sums[len(x):] - sums[:-len(x)]
    variance = squares[len(x):] - squares[:-len(x)] - window_sum * window_sum / len(x)
    denominator = np.sqrt(var_x * np.maximum(variance, 1e-20))
    scores = numerator / denominator
    index = int(np.argmax(scores))
    return {'correlation': float(scores[index]), 'lag_samples': index - padding,
        'lag_ms': (index - padding) * 1000 / RATE,
        'zero_lag_correlation': float(scores[padding])}


def compare_window(expected, actual, start, end, label, padding_seconds=.05):
    padding = round(padding_seconds * RATE)
    first, last = round(start * RATE), round(end * RATE)
    first = max(first, padding)
    last = min(last, len(expected), len(actual) - padding)
    if last <= first:
        return {'label': label, 'not_compared': 'No positive safe window'}
    x = np.asarray(expected[first:last]).mean(axis=1)
    y = np.asarray(actual[first-padding:last+padding]).mean(axis=1)
    if rms(x)<1e-4:
        return {'label':label,'silent_reference':True,'expected_rms_dbfs':db(rms(x)),
            'actual_peak_dbfs':db(peak(actual[first:last])),
            'start_seconds':first/RATE,'end_seconds':last/RATE}
    result = correlation_with_lag(x, y, padding)
    result.update(label=label, start_seconds=first / RATE, end_seconds=last / RATE,
        expected_rms_dbfs=db(rms(x)))
    if result.get('silent_reference'):
        result['actual_peak_dbfs'] = db(peak(actual[first:last]))
        return result
    lag = result['lag_samples']
    aligned = np.asarray(actual[first+lag:last+lag], dtype=np.float64)
    target = np.asarray(expected[first:last], dtype=np.float64)
    denominator = float(np.sum(target * target))
    gain = float(np.sum(target * aligned) / denominator) if denominator > 1e-20 else 1.0
    residual = aligned - target * gain
    result.update(gain=gain, gain_db=db(abs(gain)), residual_rms_dbfs=db(rms(residual)),
        residual_peak_dbfs=db(peak(residual)))
    return result


def run_logged(command, log):
    started = time.monotonic()
    with log.open('w') as output:
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT)
    return {'returncode': result.returncode, 'wall_seconds': time.monotonic()-started,
        'log': str(log)}


def make_single_cue_reference(cue, asset, directory):
    """Independent single-cue mix for the first 450 ms, before typing/comedy."""
    source = Path(asset['resolved_file'])
    with wave.open(str(source), 'rb') as audio:
        duration = audio.getnframes() / audio.getframerate()
    accent = cue != 'move'
    length = min(.8 if accent else .35, duration)
    samples = round(length * RATE)
    fade_in, fade_out = min(.004, length/3), min(.008, length/3)
    output = directory / (cue + '.wav')
    filters = (
        'anullsrc=r=48000:cl=stereo,atrim=end_sample=48000[bed];'
        f'[0:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,'
        f'atrim=end_sample={samples},asetpts=PTS-STARTPTS,volume={asset["gain"]},'
        f'afade=t=in:st=0:d={fade_in},afade=t=out:st={length-fade_out}:d={fade_out}[cue];'
        '[bed][cue]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,'
        'alimiter=limit=0.7943282347242815:level=false:attack=1:release=50:latency=true,'
        'apad=whole_len=21600,atrim=end_sample=21600,asetpts=PTS-STARTPTS[out]'
    )
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-protocol_whitelist',
        'file,pipe', '-i', str(source), '-filter_complex', filters, '-map', '[out]',
        '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2', str(output)], check=True)
    return read_wav(output)


def visual_capture_plan(data, rating_schema, check):
    fps=int(data['fps']);total=int(data['duration_frames']);segments=data['segments']
    if fps!=30 or not segments or segments[0]['start_frame']!=0 or segments[-1]['end_frame']!=total:
        raise ValueError('Invalid 30fps complete segment boundaries')
    if any(a['end_frame']!=b['start_frame'] for a,b in zip(segments,segments[1:])):
        raise ValueError('Non-contiguous manifest segments')
    shots=[]
    def add(group,name,frame,**metadata):
        if not isinstance(frame,int) or not 0<=frame<total:
            raise ValueError('Capture frame outside completed export')
        shots.append(dict(group=group,name=name,frame=frame,seconds=frame/fps,
            file=str(check/'frames'/group/(name+'.png')),**metadata))
    annotations=0
    for i,s in enumerate(segments):
        kind=s['kind'];start=int(s['start_frame']);end=int(s['end_frame']);length=end-start
        if kind=='analysis':
            complete=start+math.ceil((rating_schema['bubble_delay_seconds']+len(s['comment'])/rating_schema['typewriter_cps'])*fps)
            frame=end-round(.4*fps)
            if frame<complete:
                raise ValueError(f'Analysis {annotations} does not finish its text by capture')
            add('analyses',f'analysis-{annotations:02d}',frame,segment_index=i,
                rating=s['rating'],speaker=s.get('speaker'),score_text=s.get('score_text'),
                comment=s['comment'],text_complete_frame=complete,
                complete_text_margin_frames=frame-complete)
            annotations+=1
        elif kind in ('intro','outro'):
            sample_seconds=(1,4,8,12,15) if kind=='intro' else (2,6,10)
            for second in sample_seconds:
                relative=round(second*fps)
                if relative<length:
                    add(kind,f'{kind}-{i:02d}-{second:02d}s',start+relative,segment_index=i)
            if not any(s['group']==kind and s['segment_index']==i for s in shots):
                add(kind,f'{kind}-{i:02d}-mid',start+length//2,segment_index=i)
    for i,(left,right) in enumerate(zip(segments,segments[1:])):
        boundary=int(right['start_frame'])
        # Two frames on either side = 66.7 ms at30fps, clear of the exact cut frame.
        before=max(int(left['start_frame']),boundary-2)
        after=min(int(right['end_frame'])-1,boundary+2)
        for role,frame in [('before',before),('after',after)]:
            add('boundaries',f'boundary-{i:02d}-{left["kind"]}-to-{right["kind"]}-{role}',frame,
                boundary_frame=boundary,left_segment_index=i,right_segment_index=i+1)
    master_path=Path(data['original_source']).parent/'source-master-manifest.json'
    if master_path.is_file():
        master=json.loads(master_path.read_text())
        n=0
        for row in master.get('source_map',[]):
            if row.get('kind')!='chapter_card':continue
            mf=row['master_in_frames']+row['duration_frames']//2
            for i,s in enumerate(segments):
                if s['kind']!='source':continue
                lo=round(s['source_in']*fps);hi=round(s['source_out']*fps)
                if lo<=mf<hi:
                    add('chapters',f'chapter-{n:02d}',s['start_frame']+mf-lo,
                        segment_index=i,master_frame=mf,title=row['title'])
                    n+=1;break
            else:raise ValueError('Chapter card not retained in final forward source intervals')
    return {'schema':'conversation-chess-final-frame-inspection-v2','fps':fps,
        'duration_frames':total,'duration_seconds':total/fps,'annotation_count':annotations,
        'frame_convention':'0-based, end-exclusive; analysis .4s before end; boundaries +/-2frames',
        'group_counts':{g:sum(s['group']==g for s in shots) for g in sorted({s['group'] for s in shots})},
        'captures':shots,'finished_render_visual_reviewed':False,
        'visual_review_status':'Extracted frames still require actual inspection; no automatic visual approval'}


def contact_sheets(plan, check):
    try:font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
    except OSError:font=ImageFont.load_default()
    sheets=[]
    for group in sorted(plan['group_counts']):
        rows=[s for s in plan['captures'] if s['group']==group]
        columns,per_page,cell=(4,12,(480,270)) if group=='boundaries' else (2,4,(960,540))
        caption=34
        for page in range(math.ceil(len(rows)/per_page)):
            selected=rows[page*per_page:(page+1)*per_page]
            height=math.ceil(len(selected)/columns)*(cell[1]+caption)
            canvas=Image.new('RGB',(columns*cell[0],height),'#202020');draw=ImageDraw.Draw(canvas)
            for index,shot in enumerate(selected):
                with Image.open(shot['file']) as im:
                    im=im.convert('RGB');im.thumbnail(cell,Image.Resampling.LANCZOS)
                    x=index%columns*cell[0];y=index//columns*(cell[1]+caption)
                    canvas.paste(im,(x+(cell[0]-im.width)//2,y+(cell[1]-im.height)//2))
                draw.text((x+5,y+cell[1]+4),shot['name']+f' | {shot["seconds"]:.2f}s',font=font,fill='white')
            out=check/'contacts'/f'{group}-{page:02d}.jpg';out.parent.mkdir(exist_ok=True)
            canvas.save(out,quality=94,subsampling=0)
            sheets.append({'group':group,'page':page,'file':str(out),'shots':[s['name'] for s in selected]})
    return sheets


def run_visual_captures(args, check):
    data=json.loads(args.manifest.read_text())
    native=json.loads(args.bundle_manifest.read_text())
    if native.get('export_completed') is not True or Path(native.get('final_video','')).resolve()!=args.file:
        raise ValueError('Native completion receipt does not match finished MP4')
    info=probe(args.file);video=next(s for s in info['streams'] if s['codec_type']=='video')
    if ((int(video['width']),int(video['height']))!=(1920,1080)
        or Fraction(video['avg_frame_rate'])!=data['fps']
        or int(video.get('nb_frames',0))!=data['duration_frames']
        or abs(float(info['format']['duration'])-data['duration_frames']/data['fps'])>.1):
        raise ValueError('Completed MP4 profile/framecount mismatch')
    if sha256(args.file)!=native.get('output_sha256'):
        raise ValueError('MP4 SHA differs from native completion receipt')
    sfx_path=Path(data['sfx_manifest'])
    rating_schema=json.loads((sfx_path.parents[2]/'ratings.json').read_text())
    plan=visual_capture_plan(data,rating_schema,check)
    plan.update(video=str(args.file),manifest=str(args.manifest),
        manifest_sha256=sha256(args.manifest),source_quality=data.get('source_quality'),
        source_quality_accepted=data.get('source_quality',{}).get('accepted_for_final') is True,
        full_decode_checked_separately=not args.frames_only,
        finished_render_visual_reviewed=False,human_audio_listening=False)
    (check/'final-frame-plan.json').write_text(json.dumps(plan,indent=2))
    def capture(shot):
        out=Path(shot['file']);out.parent.mkdir(parents=True,exist_ok=True)
        seconds,remainder=divmod(shot['frame'],plan['fps'])
        command=['ffmpeg','-v','error','-nostdin','-threads','1','-ss',str(seconds),
            '-i',str(args.file),'-vf',rf'select=eq(n\,{remainder})','-frames:v','1',
            '-fps_mode','passthrough','-threads','1','-y',str(out)]
        subprocess.run(command,check=True)
        if not out.is_file() or out.stat().st_size==0:raise ValueError('Missing extracted frame')
        return shot['name']
    started=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(capture,s) for s in plan['captures']]
        for count,future in enumerate(concurrent.futures.as_completed(futures),1):
            future.result()
            if count%20==0 or count==len(futures):
                print(json.dumps({'stage':'visual_captures','done':count,'total':len(futures)}),flush=True)
    plan['contact_sheets']=contact_sheets(plan,check)
    plan['elapsed_seconds']=time.monotonic()-started
    plan['extraction_completed']=True
    (check/'final-frame-extraction.json').write_text(json.dumps(plan,indent=2))
    print(json.dumps({'report':str(check/'final-frame-extraction.json'),
        'captures':len(plan['captures']),'contacts':len(plan['contact_sheets']),
        'groups':plan['group_counts'],'visual_reviewed':False}),flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', '--video', dest='file', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--bundle-manifest', type=Path, required=True,
        help='Native Kdenlive completion receipt; prevents QA of a partial or wrong export')
    parser.add_argument('--timeline', type=Path,
        help='Defaults to timeline_file recorded in prepared manifest')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--frames-only', action='store_true',
        help='Extract visual review captures after validating completion receipt and output profile')
    parser.add_argument('--skip-frames', action='store_true')
    parser.add_argument('--workers', type=int, choices=(1,2), default=2)
    args = parser.parse_args()
    check = args.out.resolve()
    check.mkdir(parents=True,exist_ok=True)
    args.file=args.file.resolve(strict=True)
    args.manifest=args.manifest.resolve(strict=True)
    args.bundle_manifest=args.bundle_manifest.resolve(strict=True)
    data=json.loads(args.manifest.read_text())
    args.expected_frames=int(data['duration_frames'])
    args.timeline=(args.timeline or Path(data['timeline_file'])).resolve(strict=True)
    if args.frames_only:
        return run_visual_captures(args, check)
    export = json.loads(args.bundle_manifest.read_text())
    if export.get('export_completed') is not True:
        raise RuntimeError('Native export is not marked complete; do not run QA against a partial file')
    if Path(export.get('final_video', '')).resolve() != args.file.resolve():
        raise RuntimeError('Native completion receipt belongs to a different output file')
    data = json.loads(args.manifest.read_text())
    timeline = json.loads(args.timeline.read_text())
    info = probe(args.file)
    video = next(s for s in info['streams'] if s['codec_type']=='video')
    audio = next(s for s in info['streams'] if s['codec_type']=='audio')
    total = args.expected_frames * SAMPLES_PER_FRAME
    report = {'schema': 'conversation-chess-actual-native-audio-technical-qa-v1',
        'file': str(args.file), 'finished_render_visual_reviewed': False,
        'human_audio_listening': False, 'published': False, 'failures': [], 'warnings': [],
        'delivery_ready': False, 'source_quality': data.get('source_quality'),
        'source_dimensions': data.get('source_dimensions'), 'opening': data.get('opening'),
        'annotation_count': len(timeline['annotations']),
        'expected_frames': args.expected_frames, 'expected_seconds': args.expected_frames/FPS,
        'probe': info, 'comparison_method': 'Actual final decoded PCM versus actual prepared dialogue/SFX/music at manifest frame boundaries; single intended grade cue versus prepared onset; no human-listening claim.'}
    def require(condition, message):
        if not condition:
            report['failures'].append(message)
    def persist():
        (check/'audio-technical-qa.json').write_text(json.dumps(report, indent=2))
    require(data['duration_frames']==args.expected_frames, 'Prepared timeline frame count changed')
    require(int(video.get('nb_frames',0))==args.expected_frames, 'Final frame count differs from target')
    require((video['width'],video['height'])==(1920,1080), 'Final geometry is not 1920×1080')
    require(Fraction(video['avg_frame_rate'])==30, 'Final frame rate is not 30 fps')
    require(audio['codec_name']=='aac' and int(audio['sample_rate'])==RATE and int(audio['channels'])==2,
        'Final audio is not stereo AAC48k')
    require(abs(float(info['format']['duration'])-args.expected_frames/FPS)<.1,
        'Final A/V duration differs materially from exact timeline')
    require(data.get('voiceover') is False, 'Unexpected voiceover metadata')
    report['sha256'] = sha256(args.file)
    require(report['sha256']==export.get('output_sha256'), 'Final SHA differs from native export receipt')
    report['full_av_decode'] = run_logged(['ffmpeg', '-v', 'error', '-xerror', '-nostdin',
        '-threads', '2', '-protocol_whitelist', 'file,pipe', '-i', str(args.file),
        '-f', 'null', '-'], check/'full-av-decode.log')
    require(report['full_av_decode']['returncode']==0, 'Full final A/V decode failed')
    require((check/'full-av-decode.log').stat().st_size==0,
        'Full final A/V decode emitted an error log')
    persist()
    print(json.dumps({'stage':'full_av_decode','passed':report['full_av_decode']['returncode']==0}), flush=True)
    final_pcm = check/'final-decoded-f32le.pcm'
    result = run_logged(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-threads', '2',
        '-protocol_whitelist', 'file,pipe', '-i', str(args.file), '-vn', '-c:a',
        'pcm_f32le', '-ar', str(RATE), '-ac', str(CHANNELS), '-f', 'f32le', str(final_pcm)],
        check/'audio-decode.log')
    require(result['returncode']==0, 'Final audio PCM decode failed')
    actual = np.memmap(final_pcm, dtype='<f4', mode='r').reshape(-1, CHANNELS)
    require(abs(len(actual)-total)<=2048, 'Final decoded audio sample count differs by more than AAC padding')
    actual_peak, over = 0.0, 0
    for index in range(0,len(actual),RATE*10):
        block=np.asarray(actual[index:index+RATE*10])
        actual_peak=max(actual_peak,peak(block))
        over += int(np.count_nonzero(np.abs(block)>=1.0))
    report['audio_peak']={'sample_peak':actual_peak,'sample_peak_dbfs':db(actual_peak),
        'samples_at_or_above_full_scale':over,'decoded_samples_per_channel':len(actual),
        'expected_samples_per_channel':total}
    require(over==0, 'Final decoded PCM reaches or exceeds full scale')
    expected_path = check/'expected-prepared-f32le.pcm'
    expected = np.memmap(expected_path, dtype='<f4', mode='w+', shape=(total,CHANNELS))
    expected[:]=0
    cursor = 0
    prepared_audio = []
    audio_arrays = {}
    for index,segment in enumerate(data['segments']):
        first=segment['start_frame']*SAMPLES_PER_FRAME
        length=segment['duration_frames']*SAMPLES_PER_FRAME
        require(segment['start_frame']==cursor, f'Segment{index} frame boundaries are not contiguous')
        require(segment['end_frame']-segment['start_frame']==segment['duration_frames'],
            f'Segment{index} duration differs from frame boundaries')
        cursor=segment['end_frame']
        sources=[]
        for key in ('dialogue_audio_file','sfx_file','music_file'):
            if not segment.get(key):continue
            samples=read_wav(Path(segment[key]))
            difference=len(samples)-length
            require(abs(difference)<=SAMPLES_PER_FRAME, f'Segment{index} {key} duration exceeds one-frame tolerance')
            if difference:
                report['warnings'].append(f'Segment{index} {key}: {difference} sample difference from rounded frame duration')
            used=min(length,len(samples))
            expected[first:first+used] += samples[:used]
            sources.append({'role':key,'file':segment[key],'samples':len(samples),
                'frame_needed_samples':length,'difference_samples':difference,'peak_dbfs':db(peak(samples))})
            if key=='sfx_file':audio_arrays[index]=samples
        prepared_audio.append({'index':index,'kind':segment['kind'],'start_frame':segment['start_frame'],
            'duration_frames':segment['duration_frames'],'audio':sources})
        if segment['kind']=='source':
            background_info=probe(Path(segment['background_file']))
            background_video=next(s for s in background_info['streams'] if s['codec_type']=='video')
            background_duration=float(background_info['format']['duration'])
            needed_duration=segment['duration_frames']/FPS
            prepared_audio[-1]['prepared_video']={'file':segment['background_file'],
                'duration_seconds':background_duration,'needed_seconds':needed_duration,
                'width':background_video['width'],'height':background_video['height'],
                'fps':background_video['avg_frame_rate']}
            require((background_video['width'],background_video['height'])==(1920,1080),
                f'Segment{index} prepared video geometry changed')
            require(Fraction(background_video['avg_frame_rate'])==FPS,
                f'Segment{index} prepared video is not 30 fps')
            require(abs(background_duration-needed_duration)<=.08,
                f'Segment{index} prepared video duration exceeds two-frame tolerance')
    expected.flush()
    require(cursor==args.expected_frames,'Manifest segments do not reach final expected frame')
    report['prepared_audio']=prepared_audio
    report['audio_correlations']=[]
    report['reading_tails']=[]
    report['grade_onsets']=[]
    sfx_path=Path(data['sfx_manifest'])
    rating_schema=json.loads((sfx_path.parents[2]/'ratings.json').read_text())
    sfx=json.loads(sfx_path.read_text())
    references={}
    refs=check/'grade-reference';refs.mkdir(exist_ok=True)
    for cue in ('move','brilliant','error','blunder'):
        asset={**sfx[cue],'resolved_file':str(sfx_path.parent/sfx[cue]['file'])}
        references[cue]=make_single_cue_reference(cue,asset,refs)
    annotations=timeline['annotations']
    card=0
    for index,segment in enumerate(data['segments']):
        start=segment['start_frame']/FPS
        duration=segment['duration_frames']/FPS
        kind=segment['kind']
        if not any(segment.get(k) for k in ('dialogue_audio_file','sfx_file','music_file')):continue
        inset=.15 if kind=='source' else .03
        window_start=start+min(inset,duration/8)
        window_end=min(start+duration-.1,window_start+min(4,duration-.2))
        comp=compare_window(expected,actual,window_start,window_end,f'{index}:{kind}')
        comp.update(segment_index=index,kind=kind)
        report['audio_correlations'].append(comp)
        if comp.get('silent_reference'):
            require(comp.get('actual_peak_dbfs',-300)<-60, f'Segment{index}:{kind} unexpected audio during silent reference')
        if not comp.get('silent_reference') and not comp.get('not_compared'):
            threshold=.90 if kind=='analysis' else .96
            require(comp['correlation']>=threshold, f'Segment{index}:{kind} audio correlation is unexpectedly low')
            require(abs(comp['lag_ms'])<=33.4,f'Segment{index}:{kind} audio drift exceeds one frame')
        if kind!='analysis':continue
        annotation=annotations[card];card+=1
        require(segment['rating']==annotation['rating'],'Analysis rating order differs from timeline')
        reading_start=rating_schema['bubble_delay_seconds']+len(annotation['comment'])/rating_schema['typewriter_cps']+.1
        tail_first=round((start+reading_start)*RATE)
        tail_last=round((start+duration-.08)*RATE)
        target=expected[tail_first:tail_last]
        observed=actual[tail_first:tail_last]
        tail={'segment_index':index,'annotation_id':annotation.get('id'),'start_seconds':tail_first/RATE,
            'end_seconds':tail_last/RATE,'duration_seconds':max(0,tail_last-tail_first)/RATE,
            'prepared_peak_dbfs':db(peak(target)),'final_peak_dbfs':db(peak(observed)),
            'final_rms_dbfs':db(rms(observed))}
        report['reading_tails'].append(tail)
        require(tail_last>tail_first,'Analysis reading tail has no positive duration')
        require(peak(target)<1e-7,f'Analysis{card} prepared reading tail is not silent')
        require(peak(observed)<.001,f'Analysis{card} final reading tail contains unexpected audible-level audio')
        cue='brilliant' if annotation['rating']=='brilliant' else 'blunder' if annotation['rating']=='blunder' else 'error' if annotation['rating'] in ('mistake','inaccuracy') else 'move'
        samples=audio_arrays[index][:len(references[cue])]
        reference=references[cue][:len(samples)]
        difference=samples-reference
        onset={'segment_index':index,'annotation_id':annotation.get('id'),'rating':annotation['rating'],
            'single_intended_cue':cue,'comparison_seconds':len(samples)/RATE,
            'prepared_difference_peak':peak(difference),
            'prepared_difference_peak_dbfs':db(peak(difference)),
            'matches_single_intended_cue':peak(difference)<=2/32768}
        observed_comparison=compare_window(expected,actual,start+.03,start+.45,
            f'{index}:grade-onset',padding_seconds=.02)
        onset['final_vs_prepared']=observed_comparison
        report['grade_onsets'].append(onset)
        require(onset['matches_single_intended_cue'],f'Analysis{card} onset does not match its single intended cue')
        if not observed_comparison.get('silent_reference') and not observed_comparison.get('not_compared'):
            require(observed_comparison['correlation']>=.90,
                f'Analysis{card} final grade onset does not match prepared SFX')
    require(card==len(annotations),'Final native project does not contain every analysis annotation')
    report['true_peak_scan']=run_logged(['ffmpeg','-v','info','-nostdin','-threads','2',
        '-protocol_whitelist','file,pipe','-i',str(args.file),'-vn','-af','ebur128=peak=true',
        '-f','null','-'],check/'true-peak.log')
    peak_matches=re.findall(r'True peak:\s*Peak:\s*([-+\d.]+)\s*dBFS',
        (check/'true-peak.log').read_text(errors='replace'))
    if peak_matches:
        report['audio_peak']['true_peak_dbfs']=float(peak_matches[-1])
        require(float(peak_matches[-1])<0,'Final estimated true peak reaches full scale')
    else:
        report['warnings'].append('True-peak summary could not be parsed; decoded sample peak is reported')
    report['technical_audio_passed']=not report['failures']
    report['completed']=True
    report['full_video_audio_decode_ok']=report['full_av_decode']['returncode']==0
    report['frames_and_boundaries_derived_from_manifest']=True
    persist()
    text=(f"Actual final technical/audio QA: {'PASS' if report['technical_audio_passed'] else 'FAIL'}\n"
        f"File: {args.file.name}\nFrames: {video.get('nb_frames')} / {args.expected_frames}; 1080p30; AAC48k stereo.\n"
        f"SHA256: {report['sha256']}\nSample peak: {db(actual_peak):.3f} dBFS; full-scale decoded samples: {over}.\n"
        f"Correlated audio segments: {len(report['audio_correlations'])}; silent reading tails: {len(report['reading_tails'])}; single grade cues checked: {len(report['grade_onsets'])}.\n"
        "Human audio listening: false. Finished-render visual review: false, awaiting reviewer inspection.\n"
        f"Failures: {report['failures']}\nWarnings: {report['warnings']}\n")
    (check/'AUDIO_TECHNICAL_QA.txt').write_text(text)
    print(json.dumps({'report':str(check/'audio-technical-qa.json'),
        'passed':report['technical_audio_passed'],'failures':report['failures']}),flush=True)
    visual_exit=0 if args.skip_frames else run_visual_captures(args,check)
    return 0 if report['technical_audio_passed'] and visual_exit==0 else 1


if __name__=='__main__':
    raise SystemExit(main())
