"""Decode every exported frame; validate titles and write numbered review sheets."""
import json, math, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageStat
movie=Path(sys.argv[1] if len(sys.argv)>1 else 'chocolate-crazy-tools-final.mp4')
out=Path('qa')/movie.stem;out.mkdir(exist_ok=True,parents=True)
d=json.loads(Path('assets/simulation.json').read_text())
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(movie)]))
video=next(s for s in meta['streams'] if s['codec_type']=='video')
assert (video['width'],video['height'])==(1080,1920)
assert video['r_frame_rate']=='60/1'
assert abs(float(meta['format']['duration'])-d['duration'])<.05
assert any(s['codec_type']=='audio' for s in meta['streams'])
proc=subprocess.Popen(['ffmpeg','-v','error','-i',str(movie),'-vf','scale=180:320','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
size=180*320*3;frames=[]
while True:
    chunk=proc.stdout.read(size)
    if not chunk:break
    assert len(chunk)==size
    frames.append(Image.frombytes('RGB',(180,320),chunk))
assert proc.wait()==0
assert len(frames)==round(d['duration']*60)
coverage=[]
tool_coverage=[]
scale=5/6
# All three tool silhouettes must stay visible, including future tools at frame zero.
reference=frames[0]
icon_masks=[]
for i in range(3):
    mask=[]
    for y in range(round(344*scale),round(364*scale)):
        for x in range(round((37+i*60)*scale),round((59+i*60)*scale)):
            rgb=reference.getpixel((x,y))
            if max(abs(rgb[j]-[241,231,214][j]) for j in range(3))>45:mask.append((x,y,rgb))
    assert len(mask)>25,'Missing future tool icon'
    icon_masks.append(mask)
chapters=d['trials']+[{'start':d['outroStart'],'length':d['duration']-d['outroStart']}]
for chapter in chapters:
    start=round(chapter['start']*60);end=round((chapter['start']+chapter['length'])*60)
    base=frames[start].tobytes()
    indices=[(y*180+x)*3 for y in range(38,75) for x in range(15,165)
             if base[(y*180+x)*3]<110 and base[(y*180+x)*3+1]<135 and base[(y*180+x)*3+2]<120]
    assert len(indices)>50,'Missing title'
    for n in range(start,end):
        pixels=frames[n].tobytes()
        score=sum(pixels[p]<110 and pixels[p+1]<135 and pixels[p+2]<120 for p in indices)/len(indices)
        coverage.append(score);assert score>.95,f'Incomplete title at frame {n}'
        for mask in icon_masks:
            score=sum(max(abs(frames[n].getpixel((x,y))[j]-rgb[j]) for j in range(3))<40 for x,y,rgb in mask)/len(mask)
            tool_coverage.append(score);assert score>.90,f'Missing tool silhouette at frame {n}'
        active=['fork','glove','jackhammer'].index(chapter.get('tool','jackhammer'))
        for i in range(3):
            expected=[71,113,74] if chapter['start']==d['outroStart'] or i<active else [32,60,42] if i==active else [180,172,145]
            rgb=frames[n].getpixel((round((27.5+i*60)*scale),round(356*scale)))
            assert max(abs(rgb[j]-expected[j]) for j in range(3))<40,f'Wrong active tool at frame {n}'
for start in range(0,len(frames),60):
    sheet=Image.new('RGB',(1800,2052),'#203c2a');draw=ImageDraw.Draw(sheet)
    for j,frame in enumerate(frames[start:start+60]):
        x,y=j%10*180,j//10*342
        sheet.paste(frame,(x,y+22));draw.text((x+5,y+4),f'{start+j:04d} | {(start+j)/60:05.2f}s',fill='#f1e7d6')
        assert sum(ImageStat.Stat(frame).mean)>60,'Black frame'
    sheet.save(out/f'all-frames-{start//60+1:02d}.jpg',quality=91)
report={'file':movie.name,'duration':float(meta['format']['duration']),'frames':len(frames),'resolution':[1080,1920],'fps':'60/1','audio':True,'sheets':math.ceil(len(frames)/60),'minimum_title_coverage':min(coverage),'minimum_tool_icon_coverage':min(tool_coverage),'active_tool_checked_every_frame':True}
(out/'media-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
