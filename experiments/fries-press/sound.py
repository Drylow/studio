"""Frozen hydraulic, food and liquid foley, mixed from the picture's schedule."""
import json, math, subprocess, wave, hashlib
from pathlib import Path
import numpy as np
RATE=48000
events=json.loads(Path('assets/events.json').read_text())
out=np.zeros(round(63.6*RATE),dtype=float)
metadata={}
def decode(name,filters):
 p=Path(f'assets/sfx-{name}-source.mp3')
 a=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-ac','1','-ar',str(RATE),'-af',filters,'-f','f32le','-']),'<f4').astype(float)
 a-=np.mean(a);a*=.65/max(np.max(np.abs(a)),1e-8)
 metadata[name]={'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'seconds':len(a)/RATE,'filters':filters}
 return a
motor=decode('hydraulic','highpass=f=65,lowpass=f=1700')
squeeze=decode('squeeze','highpass=f=100,lowpass=f=5500')
oil=decode('oil','highpass=f=130,lowpass=f=4800')
crunch=decode('crunch','highpass=f=110,lowpass=f=6200')
tray=decode('tray','highpass=f=75,lowpass=f=4500')
def accents(a,duration):
 block=480;env=np.sqrt(np.mean(a[:len(a)//block*block].reshape(-1,block)**2,axis=1));chosen=[]
 for j in np.argsort(env)[::-1]:
  if all(abs(int(j)-old)>.5/.01 for old in chosen):chosen.append(int(j))
  if len(chosen)==3:break
 clips=[]
 for j in chosen:
  first=j
  while first>max(0,j-12) and env[first-1]>.22*env[j]:first-=1
  b=a[max(0,first*block):max(0,first*block)+round(duration*RATE)].copy()
  b=np.pad(b,(0,max(0,round(duration*RATE)-len(b))));fade=round(.003*RATE);tail=round(.025*RATE)
  b[:fade]*=np.linspace(0,1,fade);b[-tail:]*=np.linspace(1,0,tail);b*=.65/max(np.max(np.abs(b)),1e-8);clips.append(b)
 return clips
crunches=accents(crunch,.14);trays=accents(tray,.14);drips=accents(oil,.16)
def add(a,t,gain,speed=1):
 n=round(len(a)/speed);b=np.interp(np.arange(n)*speed,np.arange(len(a)),a)*gain;start=round(t*RATE);lo=max(0,start);hi=min(len(out),start+n)
 if hi>lo:out[lo:hi]+=b[lo-start:hi-start]
def bed(a,start,end,gain):
 # Equal-amplitude overlap and short fades avoid loop clicks and doubled gains.
 cross=round(.35*RATE);length=round((end-start)*RATE);b=np.zeros(length+len(a));weight=np.zeros_like(b)
 hop=len(a)-cross
 for pos in range(0,length,hop):
  n=min(len(a),len(b)-pos);window=np.ones(n);window[:cross]=np.linspace(0,1,cross);window[-cross:]=np.linspace(1,0,cross)
  b[pos:pos+n]+=a[:n]*window;weight[pos:pos+n]+=window
 b=b[:length]/np.maximum(weight[:length],1);fade=min(round(.18*RATE),length//2)
 b[:fade]*=np.linspace(0,1,fade);b[-fade:]*=np.linspace(1,0,fade)
 time=np.arange(length)/RATE;b*=.86+.14*np.sin(time*.8)**2
 add(b,start,gain)
for e in events:
 kind=e['kind'];gain=e['gain']
 if kind in ('motor','lift'):bed(motor,e['t'],e['end'],gain)
 elif kind=='squeeze':bed(squeeze,e['t'],e['end'],gain)
 elif kind=='oil':bed(oil,e['t'],e['end'],gain)
 elif kind=='crunch':
  nearby=sum(f['kind']=='crunch' and abs(f['t']-e['t'])<.09 for f in events)
  add(crunches[e['variant']],e['t'],gain/math.sqrt(nearby),1+(e['variant']-1)*.035)
 elif kind=='tray':add(trays[e['load']],e['t'],gain)
 elif kind=='drop':add(drips[e['variant']],e['t'],gain,1+(e['variant']-1)*.06)
 elif kind=='celebrate':
  for i,hz in enumerate([659.25,987.77]):
   t=np.arange(round(.16*RATE))/RATE;a=(np.sin(2*np.pi*hz*t)+.12*np.sin(4*np.pi*hz*t))*np.exp(-t*28)*np.minimum(1,t/.004);add(a,e['t']+i*.09,gain)
peak=float(np.max(np.abs(out)));master=.74/max(peak,1e-8);out*=master
out[-round(.18*RATE):]*=np.linspace(1,0,round(.18*RATE))
with wave.open('assets/sound.wav','wb') as w:
 w.setnchannels(1);w.setsampwidth(2);w.setframerate(RATE);w.writeframes(np.round(np.clip(out,-.999,.999)*32767).astype('<i2').tobytes())
report={'seconds':len(out)/RATE,'peak_dbfs':20*math.log10(np.max(np.abs(out))),'rms_dbfs':20*math.log10(np.sqrt(np.mean(out**2))),'clipped_samples':int(np.sum(np.abs(out)>=1)),'master_gain':master,'events':len(events),'sources':metadata}
Path('qa').mkdir(exist_ok=True);Path('qa/audio-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='sources'}))
