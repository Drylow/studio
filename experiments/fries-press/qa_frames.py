"""Decode every final frame, check persistent English titles and load markers."""
import json, math, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageStat
movie=Path(sys.argv[1] if len(sys.argv)>1 else 'fries-hydraulic-press-final.mp4')
out=Path('qa')/movie.stem;out.mkdir(exist_ok=True,parents=True)
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(movie)]))
video=next(s for s in meta['streams'] if s['codec_type']=='video')
assert (video['width'],video['height'])==(1080,1920) and video['r_frame_rate']=='60/1'
assert abs(float(meta['format']['duration'])-63.6)<.05
assert any(s['codec_type']=='audio' for s in meta['streams'])
proc=subprocess.Popen(['ffmpeg','-v','error','-i',str(movie),'-vf','scale=216:384:flags=neighbor','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
size=216*384*3;frames=[]
while True:
 chunk=proc.stdout.read(size)
 if not chunk:break
 assert len(chunk)==size;frames.append(Image.frombytes('RGB',(216,384),chunk))
assert proc.wait()==0 and len(frames)==3816
coverage=[];markers=[]
for start,end,index,outro in [(0,18,0,False),(18,38,1,False),(38,60.8,2,False),(60.8,63.6,2,True)]:
 a=round(start*60);b=round(end*60);base=frames[a].tobytes()
 mask=[(y*216+x)*3 for y in range(48,69) for x in range(18,198) if base[(y*216+x)*3]<110 and base[(y*216+x)*3+1]<135 and base[(y*216+x)*3+2]<120]
 assert len(mask)>80,'Missing title'
 for n in range(a,b):
  pixels=frames[n].tobytes();score=sum(pixels[p]<110 and pixels[p+1]<135 and pixels[p+2]<120 for p in mask)/len(mask)
  coverage.append(score);assert score>.965,f'Incomplete title at {n}'
  for i in range(3):
   expected=[71,113,74] if outro or i<index else [32,60,42] if i==index else [180,172,145]
   rgb=frames[n].getpixel((28+i*60,360));error=max(abs(rgb[j]-expected[j]) for j in range(3));markers.append(error)
   assert error<35,f'Wrong load marker at {n}'
  assert sum(ImageStat.Stat(frames[n]).mean)>80,'Black frame'
for start in range(0,len(frames),60):
 sheet=Image.new('RGB',(1296,2060),'#203c2a');draw=ImageDraw.Draw(sheet)
 for j,frame in enumerate(frames[start:start+60]):
  x,y=j%6*216,j//6*206
  sheet.paste(frame.resize((108,192),Image.Resampling.NEAREST),(x,y+14))
  # The action crop next to each full thumbnail makes compression/oil readable.
  sheet.paste(frame.crop((0,93,216,328)).resize((108,118),Image.Resampling.NEAREST),(x+108,y+41))
  draw.text((x+3,y+1),f'{start+j:04d} | {(start+j)/60:.3f}s',fill='#f1e7d6')
 sheet.save(out/f'all-frames-{start//60+1:02d}.jpg',quality=94)
report={'file':movie.name,'duration':float(meta['format']['duration']),'frames':len(frames),'resolution':[1080,1920],'fps':'60/1','audio':True,'sheets':math.ceil(len(frames)/60),'minimum_title_coverage':min(coverage),'maximum_load_marker_color_error':max(markers),'load_markers_checked_every_frame':True}
(out/'media-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
