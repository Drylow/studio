"""Deterministic procedural cuts and collision accents, with no external audio."""
import json,math,random,wave,struct
from pathlib import Path
rate=48000
out=[0.0]*(18*rate)
rng=random.Random(10726)
events=json.loads(Path('assets/events.json').read_text(encoding='utf-8'))
last={}
for e in events:
    cut=e['type']=='cut'
    if not cut:
        key=e['piece']
        if e['t']-last.get(key,-10)<.13:continue
        last[key]=e['t']
    length=.16 if cut else .105
    start=int((e['t']-.035 if cut else e['t'])*rate)
    gain=.19 if cut else min(.17,e['speed']*.016)
    low=0.
    for i in range(int(length*rate)):
        t=i/rate
        noise=rng.uniform(-1,1)
        low=low*.80+noise*.20
        if cut:
            value=(.45*noise+.55*low)*math.sin(math.pi*t/length)**1.6
        else:
            value=(math.sin(2*math.pi*(110-140*t)*t)*.8+low*.35)*math.exp(-t*45)
        k=start+i
        if 0<=k<len(out):out[k]+=value*gain
peak=max(abs(x) for x in out)
scale=min(1,.65/max(peak,.001))
with wave.open('assets/sound.wav','wb') as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate)
    w.writeframes(b''.join(struct.pack('<h',int(x*scale*32767)) for x in out))
print('Sound peak:',round(peak,3),'events:',len(events))
