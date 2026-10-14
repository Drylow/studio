"""Verify the finished native movie and prepare actual encoded QA sheets.

No uploads, paid services, or visual PASS claims. The root must view the sheets.
"""

if not __debug__:
    raise RuntimeError('Evidence tools require normal Python; optimization disables critical checks')
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

import av
import imageio_ffmpeg
import numpy as np
from PIL import Image,ImageDraw


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)

def samples_in_window(path,start,end):
    with av.open(str(path)) as container:
        stream=container.streams.audio[0]
        rate=stream.codec_context.sample_rate
        begin=round(start*rate);stop=round(end*rate)
        out=np.zeros(stop-begin,dtype=np.float64)
        filled=np.zeros(stop-begin,dtype=bool)
        container.seek(max(0,int((start-.2)*av.time_base)))
        for frame in container.decode(audio=0):
            frame_begin=round(float(frame.pts*frame.time_base)*rate)
            frame_end=frame_begin+frame.samples
            if frame_begin>=stop:
                break
            a=max(begin,frame_begin);b=min(stop,frame_end)
            if b<=a:
                continue
            data=frame.to_ndarray().reshape(-1)
            if np.issubdtype(data.dtype,np.integer):
                data=data.astype(np.float64)/(2**(np.iinfo(data.dtype).bits-1))
            out[a-begin:b-begin]=data[a-frame_begin:b-frame_begin]
            filled[a-begin:b-begin]=True
        assert filled.all(),('Incomplete audio sample window',str(path),start)
    return out,rate

def correlation_windows(source,movie,duration):
    rows=[]
    for start in [2., duration*.1, duration*.25, duration*.5, duration*.75, duration*.9, duration-6.]:
        a,rate=samples_in_window(source,start,start+3.)
        b,other=samples_in_window(movie,start,start+3.)
        assert rate==other==44100
        a-=a.mean();b-=b.mean()
        correlation=float(np.dot(a,b)/np.sqrt(np.dot(a,a)*np.dot(b,b)))
        size=1<<(2*len(a)-1).bit_length()
        cross=np.fft.irfft(np.fft.rfft(a,n=size)*np.conj(np.fft.rfft(b,n=size)),n=size)
        limit=round(.02*rate)
        lags=np.arange(-limit,limit+1)
        peak=int(lags[np.argmax(cross[lags%size])])
        rows.append({'start_seconds':start,'duration_seconds':3.,'zero_lag_correlation':correlation,
                     'best_lag_samples':peak,'best_lag_ms':peak*1000/rate})
        assert correlation>.97,('Narration correlation failed',rows[-1])
        assert abs(peak)<=3,('Narration alignment changed',rows[-1])
    return rows

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--movie',type=Path,required=True)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--episode',type=Path,required=True)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--voice-proof',type=Path,required=True)
    parser.add_argument('--scene-count',type=int,required=True)
    parser.add_argument('--min-seconds',type=float,default=900)
    parser.add_argument('--max-seconds',type=float,default=1200)
    args=parser.parse_args()
    episode=args.episode.resolve()
    movie=args.movie.resolve();assert sha(movie)==args.sha256
    plan=json.loads(args.plan.read_text())
    scenes=plan['scenes']
    voice=json.loads(args.voice_proof.read_text())
    duration=voice['duration_seconds'];total_frames=voice['total_frames']
    assert len(scenes)==args.scene_count and args.min_seconds<=duration<=args.max_seconds
    assert [s['id'] for s in scenes]==list(range(1,args.scene_count+1))
    assert scenes[0]['start']==0 and abs(scenes[-1]['end']-duration)<1/24
    assert all(abs(a['end']-b['start'])<1/24 for a,b in zip(scenes,scenes[1:]))
    folder=episode/'final-vps-encoded-qa'/args.sha256
    images=folder/'frames';images.mkdir(parents=True,exist_ok=True)
    captured={};wanted={0,total_frames-1}
    mids={s['id']:(round(s['start']*24)+round(s['end']*24)-1)//2 for s in scenes}
    wanted.update(mids.values())
    boundaries=[]
    for scene in scenes[1:]:
        cut=round(scene['start']*24);wanted.update([cut-1,cut])
        boundaries.append({'previous_scene_id':scene['id']-1,'next_scene_id':scene['id'],
                           'before_frame':cut-1,'after_frame':cut,'cut_seconds':cut/24})
    start=time.time();count=0;audio_frames=0;audio_samples=0
    with av.open(str(movie)) as container:
        video=container.streams.video[0];audio=container.streams.audio[0]
        assert video.width==1920 and video.height==1080 and float(video.average_rate)==24
        assert video.codec_context.name=='h264'
        assert audio.codec_context.name=='aac' and audio.codec_context.sample_rate==44100
        assert audio.codec_context.layout.name=='mono'
        video.codec_context.options={'err_detect':'explode'}
        audio.codec_context.options={'err_detect':'explode'}
        video_duration=float(video.duration*video.time_base)
        audio_duration=float(audio.duration*audio.time_base)
        metadata={'video_frames':video.frames,'width':video.width,'height':video.height,
                  'fps':float(video.average_rate),'video_codec':video.codec_context.name,
                  'audio_codec':audio.codec_context.name,'audio_rate':44100,
                  'video_duration':video_duration,'audio_duration':audio_duration}
        assert abs(video_duration-duration)<1/24
        assert abs(audio_duration-duration)<1/24
        for frame in container.decode():
            if isinstance(frame,av.AudioFrame):
                audio_frames+=1;audio_samples+=frame.samples
                assert frame.sample_rate==44100
                continue
            assert isinstance(frame,av.VideoFrame)
            index=count
            if index in wanted:
                path=images/f'frame-{index:05d}.jpg'
                frame.to_image().save(path,quality=95)
                captured[index]=str(path)
            count+=1
            if count%1200==0:
                write(folder/'progress.json',{'stage':'full_video_decode_and_actual_capture',
                                             'decoded_frames':count,'total_frames':total_frames,
                                             'elapsed_seconds':time.time()-start})
    assert count==total_frames and set(captured)==wanted
    assert audio_frames>0 and abs(audio_samples-voice['decoded_samples'])<=2048
    full_decode_seconds=time.time()-start
    panels=[]
    for sid,index in mids.items():
        panels.append((f'Scene {sid:03d} — encoded midpoint frame {index}',[index]))
    for row in boundaries:
        panels.append((f"Cut {row['previous_scene_id']:03d} → {row['next_scene_id']:03d}",
                       [row['before_frame'],row['after_frame']]))
    panels.extend([('Actual first movie frame',[0]),('Actual last movie frame',[total_frames-1])])
    sheets=[];sheet_index=[]
    for offset in range(0,len(panels),9):
        sheet=Image.new('RGB',(1680,1035),(30,30,30));draw=ImageDraw.Draw(sheet)
        for local,(label,indexes) in enumerate(panels[offset:offset+9]):
            x=(local%3)*560;y=(local//3)*345
            draw.text((x+7,y+7),label,fill='white')
            if len(indexes)==1:
                with Image.open(captured[indexes[0]]) as image:
                    sheet.paste(image.resize((560,315),Image.Resampling.LANCZOS),(x,y+30))
            else:
                for part,index in enumerate(indexes):
                    with Image.open(captured[index]) as image:
                        sheet.paste(image.resize((280,158),Image.Resampling.LANCZOS),(x+part*280,y+90))
            sheet_index.append({'sheet':len(sheets)+1,'panel':local+1,'label':label,'frames':indexes})
        path=folder/f'sheet-{len(sheets)+1:02d}.jpg';sheet.save(path,quality=95);sheets.append(str(path))
    write(folder/'capture-index.json',{'movie_sha256':args.sha256,'actual_captured_frames':captured,
                                     'panels':sheet_index,'sheets':sheets,'visual_review_state':'pending_actual_view'})
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    write(folder/'progress.json',{'stage':'final_audio_levels_and_correlation','decoded_frames':count})
    levels=subprocess.run([ffmpeg,'-hide_banner','-nostdin','-xerror','-i',str(movie),'-vn','-af',
                           'loudnorm=I=-17:TP=-1.5:LRA=11:print_format=json','-f','null','-'],
                          capture_output=True,text=True,check=True)
    (folder/'audio-fatal-decode-and-levels.log').write_text(levels.stderr)
    measured=json.loads(re.findall(r'\{\s*"input_i".*?\}',levels.stderr,re.S)[-1])
    assert -19<float(measured['input_i'])<-15
    assert float(measured['input_tp'])<-.3
    narration=Path(voice.get('comparison_voice_path', voice['official_voice_path']))
    assert sha(narration)==voice['derived_voice_sha256']
    correlations=correlation_windows(narration,movie,duration)
    assert sha(movie)==args.sha256,'Movie changed during final QA'
    proof={'schema':'history-final-av-technical-review-v1','movie':str(movie),
           'movie_sha256':args.sha256,'state':'technical_pass_visual_review_pending',
           'metadata':metadata,'actual_decoded_video_frames':count,'full_av_fatal_decode_exit':0,
           'full_av_fatal_decode_method':'One complete PyAV decode of both streams, err_detect=explode; additional audio-only FFmpeg xerror pass measures final levels. No second full video decode.',
           'actual_decoded_audio_frames':audio_frames,'actual_decoded_audio_samples':audio_samples,
           'full_av_decode_elapsed_seconds':full_decode_seconds,
           'audio_measured_levels':measured,'voice_correlation_windows':correlations,
           'source_voice_sha256':voice['original_voice_sha256'],
           'derived_voice_sha256':voice['derived_voice_sha256'],
           'captured_frame_count':len(captured),'capture_sheets':sheets,
           'visual_review_state':'pending_actual_view','elapsed_seconds':time.time()-start,
           'paid_calls':0,'uploaded':False}
    write(folder/'technical-proof.json',proof)
    write(folder/'progress.json',{'stage':'technical_pass_visual_review_pending','decoded_frames':count,
                                'elapsed_seconds':proof['elapsed_seconds']})
    print(json.dumps({'technical_state':proof['state'],'proof':str(folder/'technical-proof.json'),
                      'actual_sheets':len(sheets),'frames':count,'elapsed_seconds':proof['elapsed_seconds']}))

if __name__=='__main__':
    main()
