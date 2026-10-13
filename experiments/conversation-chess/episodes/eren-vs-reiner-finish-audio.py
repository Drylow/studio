import argparse,array,hashlib,json,re,subprocess,wave
from pathlib import Path
parser=argparse.ArgumentParser(description='Finish the scene audio after a native Kdenlive render. Requires ffmpeg on PATH.')
parser.add_argument('--bundle',type=Path,required=True)
bundle=parser.parse_args().bundle.resolve();review=bundle.parent/'review';review.mkdir(exist_ok=True)
video=bundle/'video.mp4';dest=bundle/'EREN-VS-REINER-FINAL.mp4'
assert not dest.exists()
original=review/'audio-original.wav';processed=review/'audio-scenes-processed.wav';mixed=review/'audio-finished.wav'
subprocess.run(['ffmpeg','-v','error','-i',str(video),'-vn','-ac','2','-ar','48000','-c:a','pcm_s16le',str(original)],check=True)
filt='acompressor=threshold=0.125:ratio=2.5:attack=20:release=220:makeup=1.584893,alimiter=limit=0.794328:level=false:latency=true'
subprocess.run(['ffmpeg','-v','error','-i',str(original),'-af',filt,'-c:a','pcm_s16le',str(processed)],check=True)
with wave.open(str(original),'rb') as w:params=w.getparams();raw=w.readframes(w.getnframes())
with wave.open(str(processed),'rb') as w:praw=w.readframes(w.getnframes());assert w.getparams()[:4]==params[:4]
assert len(raw)==len(praw)
final=bytearray(raw);manifest=json.loads((bundle/'project-manifest.json').read_text());fps=manifest['fps'];stride=params.nchannels*params.sampwidth;rate=params.framerate;ranges=[]
for s in manifest['segments']:
 if s['kind']!='source':continue
 start=round(s['start_frame']/fps*rate)*stride;end=round(s['end_frame']/fps*rate)*stride
 final[start:end]=praw[start:end];ranges.append((start,end))
cursor=0
for start,end in ranges:assert bytes(final[cursor:start])==raw[cursor:start];cursor=end
assert bytes(final[cursor:])==raw[cursor:]
with wave.open(str(mixed),'wb') as w:w.setparams(params);w.writeframes(final)
subprocess.run(['ffmpeg','-v','warning','-i',str(video),'-i',str(mixed),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',str(dest)],check=True)
def picture_hash(p):return subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-map','0:v:0','-c','copy','-f','hash','-hash','sha256','-']).decode().strip()
h=picture_hash(video);assert picture_hash(dest)==h
subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(dest),'-map','0:v:0','-map','0:a:0','-f','null','NUL'],check=True)
measure=subprocess.run(['ffmpeg','-hide_banner','-i',str(dest),'-vn','-af','ebur128=peak=true','-f','null','NUL'],stderr=subprocess.PIPE,text=True,check=True).stderr
(review/'audio-final.txt').write_text(measure)
summary=measure.rsplit('Summary:',1)[-1];peak=float(re.search(r'Peak:\s*([-\d.]+) dBFS',summary).group(1));loudness=float(re.search(r'I:\s*([-\d.]+) LUFS',summary).group(1));assert peak<=-1
receipt={'filename':dest.name,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'picture_stream_unchanged':True,'picture_stream_sha256':h,'source_only_filter':filt,'guide_analysis_outro_pcm_unchanged':True,'true_peak_dbfs':peak,'integrated_loudness_lufs':loudness,'full_decode_passed':True,'source_ranges_seconds':[(a/stride/rate,b/stride/rate) for a,b in ranges]}
dest.with_suffix('.audio.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
