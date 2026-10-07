"""Frozen food foley; main accents from fork contacts, restrained wooden debris."""
import json, math, subprocess, wave, hashlib
from pathlib import Path
import numpy as np

RATE=48000
data=json.loads(Path('assets/simulation.json').read_text())
events=json.loads(Path('assets/events.json').read_text())
out=np.zeros(round(data['duration']*RATE),dtype=np.float64)
QA=Path('qa');QA.mkdir(exist_ok=True)
metadata={}

def write(path,a):
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(RATE)
        w.writeframes(np.round(np.clip(a,-.999,.999)*32767).astype('<i2').tobytes())

def sources(name,length):
    source=Path(f'assets/sfx-{name}-source.mp3')
    if not source.exists():
        # A build is reproducible from frozen trimmed assets even without source.
        result=[]
        for i in range(3):
            with wave.open(f'assets/sfx-{name}-{i}.wav','rb') as w:
                assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(1,2,RATE)
                result.append(np.frombuffer(w.readframes(w.getnframes()),'<i2').astype(float)/32768)
        return result
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(source),'-ac','1','-ar',str(RATE),'-af','highpass=f=75,lowpass=f=6500','-f','f32le','-'])
    a=np.frombuffer(raw,'<f4').astype(float)
    block=480
    env=np.sqrt(np.mean(a[:len(a)//block*block].reshape(-1,block)**2,axis=1))
    candidates=[]
    for j in np.argsort(env)[::-1]:
        if all(abs(j-old)>55 for old in candidates):candidates.append(int(j))
        if len(candidates)==3:break
    clips=[];starts=[]
    for i,j in enumerate(candidates):
        # Find the quiet-to-loud edge near the selected attack, not its long tail.
        first=j
        while first>max(0,j-16) and env[first-1]>.22*env[j]:first-=1
        start=max(0,round(first*.01*RATE))
        sample=a[start:start+round(length*RATE)].copy()
        if len(sample)<round(length*RATE):sample=np.pad(sample,(0,round(length*RATE)-len(sample)))
        fade=min(round(.002*RATE),len(sample)//2)
        sample[:fade]*=np.linspace(0,1,fade)
        end=round(.012*RATE);sample[-end:]*=np.linspace(1,0,end)
        peak=max(float(np.max(np.abs(sample))),1e-6);sample*=.70/peak
        write(f'assets/sfx-{name}-{i}.wav',sample);clips.append(sample);starts.append(start/RATE)
    metadata[name]={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'trim_starts':starts,'clip_seconds':length,'variants':3}
    return clips

snaps=sources('snap',.17)
woods=sources('wood',.095)
crumbs=sources('crumbs',.38)

def add(sample,t,gain,speed=1):
    n=round(len(sample)/speed)
    changed=np.interp(np.arange(n)*speed,np.arange(len(sample)),sample)
    start=round(t*RATE);lo=max(0,start);hi=min(len(out),start+n)
    if hi>lo:out[lo:hi]+=changed[lo-start:hi-start]*gain

crunch=[e for e in events if e['type']=='crunch']
for e in crunch:
    # Dense stack: overlapping attacks share a bounded energy budget.
    occupancy=sum(abs(c['t']-e['t'])<.075 for c in crunch)
    gain=.72/math.sqrt(occupancy)
    add(snaps[(e['bar']+e['chapter'])%3],e['t'],gain,1+(e['bar']%5-2)*.024)
    add(woods[e['bar']%3],e['t'],gain*.18,.92)

groups={}
for e in events:
    if e['type']!='landing':continue
    key=(e['chapter'],math.floor(e['t']/.04))
    g=groups.setdefault(key,{'t':e['t'],'energy':0,'hits':0})
    g['t']=min(g['t'],e['t']);g['energy']+=min(.08,e['mass']*e['speed']**2);g['hits']+=1
for i,g in enumerate(sorted(groups.values(),key=lambda g:g['t'])):
    gain=min(.075,math.sqrt(g['energy'])*.11)
    add(woods[i%3],g['t'],gain,1+(i%3-1)*.05)

# One gentle granular tail per trial avoids playing a noise cloud per tiny shard.
for chapter,trial in enumerate(data['trials']):
    last=max(b['hit'] for b in trial['bars'])
    add(crumbs[chapter%3],trial['start']+last+.30,.055+chapter*.009)

# Tiny original two-note finish. No background music bed.
for i,hz in enumerate([659.25,987.77]):
    t=np.arange(round(.15*RATE))/RATE
    tone=(np.sin(2*np.pi*hz*t)+.15*np.sin(2*np.pi*2*hz*t))*np.exp(-t*29)*np.minimum(1,t/.003)
    add(tone,data['outroStart']+.12+i*.09,.038)

raw=float(np.max(np.abs(out)));gain=min(2,.73/max(raw,1e-8));out*=gain
write('assets/sound.wav',out)
report={'duration':len(out)/RATE,'crunch_contacts':len(crunch),'raw_landing_events':sum(e['type']=='landing' for e in events),'landing_groups':len(groups),'peak_dbfs':20*math.log10(float(np.max(np.abs(out)))),'clipped_samples':int(np.sum(np.abs(out)>=1)),'linear_master_gain':gain,'sources':metadata}
assert report['clipped_samples']==0 and len(crunch)==31
(QA/'audio-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
