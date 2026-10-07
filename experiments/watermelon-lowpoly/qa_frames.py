"""Decode every delivered frame and make readable, numbered review sheets."""
import json,math,subprocess,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageStat
movie=Path(sys.argv[1] if len(sys.argv)>1 else 'watermelon-chef-three-levels.mp4')
out=Path('qa')/movie.stem;out.mkdir(exist_ok=True,parents=True)
composition=json.loads(Path('assets/simulation.json').read_text(encoding='utf-8'))
expected_duration=composition['duration']
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(movie)]))
video=next(s for s in meta['streams'] if s['codec_type']=='video')
assert (video['width'],video['height'])==(1080,1920)
assert video['r_frame_rate']=='60/1'
assert abs(float(meta['format']['duration'])-expected_duration)<.05
assert any(s['codec_type']=='audio' for s in meta['streams'])
proc=subprocess.Popen(['ffmpeg','-v','error','-i',str(movie),'-vf','scale=180:320','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
size=180*320*3
frames=[]
while True:
    chunk=proc.stdout.read(size)
    if not chunk:break
    assert len(chunk)==size
    frames.append(Image.frombytes('RGB',(180,320),chunk))
assert proc.wait()==0
assert len(frames)==round(expected_duration*60),len(frames)
# Regression check for the observed partial-canvas capture: static title
# pixels must remain present throughout each chapter, including after cuts.
title_coverage=[]
review_chapters=composition['shots']+[{'start':composition['outroStart'],'length':expected_duration-composition['outroStart']}]
for shot in review_chapters:
    start=round(shot['start']*60)
    end=round((shot['start']+shot['length'])*60)
    baseline=frames[start].tobytes()
    indices=[(y*180+x)*3 for y in range(38,61) for x in range(15,165)
             if baseline[(y*180+x)*3]<110 and baseline[(y*180+x)*3+1]<135 and baseline[(y*180+x)*3+2]<120]
    assert len(indices)>50,'Title missing at chapter start'
    for n in range(start,end):
        data=frames[n].tobytes()
        coverage=sum(data[p]<110 and data[p+1]<135 and data[p+2]<120 for p in indices)/len(indices)
        title_coverage.append(coverage)
        assert coverage>.95,f'Title capture incomplete in frame {n}: {coverage:.1%}'
for start in range(0,len(frames),60):
    sheet=Image.new('RGB',(1800,2052),'#202d23')
    draw=ImageDraw.Draw(sheet)
    for j,frame in enumerate(frames[start:start+60]):
        col,row=j%10,j//10
        sheet.paste(frame,(col*180,row*342+22))
        draw.text((col*180+5,row*342+4),f'{start+j:03d} | {(start+j)/60:05.2f}s',fill='#f1e7d6')
        assert sum(ImageStat.Stat(frame).mean)>60,'Unexpected black image'
    sheet.save(out/f'all-frames-{start//60+1:02d}.jpg',quality=91)
report={'file':movie.name,'duration':float(meta['format']['duration']),'frames':len(frames),'resolution':[video['width'],video['height']],'fps':video['r_frame_rate'],'has_audio':True,'all_frames_decoded':True,'sheets':math.ceil(len(frames)/60),'minimum_title_coverage':min(title_coverage),'chapters':[{'tool':s['tool'],'start':s['start'],'count':s['count'],'length':s['length']} for s in composition['shots']]}
(out/'media-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
