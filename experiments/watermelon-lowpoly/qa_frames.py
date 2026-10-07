"""Decode every delivered frame and make readable, numbered review sheets."""
import json,subprocess,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageStat
movie=Path(sys.argv[1] if len(sys.argv)>1 else 'watermelon-lowpoly.mp4')
out=Path('qa');out.mkdir(exist_ok=True)
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(movie)]))
video=next(s for s in meta['streams'] if s['codec_type']=='video')
assert (video['width'],video['height'])==(1080,1920)
assert video['r_frame_rate']=='30/1'
assert abs(float(meta['format']['duration'])-18)<.05
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
assert len(frames)==540,len(frames)
for start in range(0,len(frames),60):
    sheet=Image.new('RGB',(1800,2052),'#202d23')
    draw=ImageDraw.Draw(sheet)
    for j,frame in enumerate(frames[start:start+60]):
        col,row=j%10,j//10
        sheet.paste(frame,(col*180,row*342+22))
        draw.text((col*180+5,row*342+4),f'{start+j:03d} | {(start+j)/30:05.2f}s',fill='#f1e7d6')
        assert sum(ImageStat.Stat(frame).mean)>60,'Unexpected black image'
    sheet.save(out/f'all-frames-{start//60+1:02d}.jpg',quality=91)
report={'file':movie.name,'duration':float(meta['format']['duration']),'frames':len(frames),'resolution':[video['width'],video['height']],'fps':video['r_frame_rate'],'has_audio':True,'all_frames_decoded':True,'sheets':9}
(out/'media-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
