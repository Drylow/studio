"""Deterministic procedural cuts and collision accents, with no external audio."""
import json,math,random,wave,struct
from pathlib import Path
rate=48000
duration=json.loads(Path('assets/simulation.json').read_text(encoding='utf-8'))['duration']
out=[0.0]*int(duration*rate)
rng=random.Random(10726)
events=json.loads(Path('assets/events.json').read_text(encoding='utf-8'))
last={}
for e in events:
    cut=e['type']=='cut'
    if not cut:
        key=(e['chapter'],e['piece'])
        if e['t']-last.get(key,-10)<.13:continue
        last[key]=e['t']
    length=.065 if cut else .080
    start=int((e['t']-.025 if cut else e['t'])*rate)
    gain=.78 if cut else min(.09,e['speed']*.012)
    low=0.;air=0.
    for i in range(int(length*rate)):
        t=i/rate
        noise=rng.uniform(-1,1)
        low=low*.80+noise*.20
        if cut:
            # Fast air sweep, a wet mid-band snap at the geometric cut,
            # and a short pitched wooden tail. Every slash has one accent.
            air=air*.4+noise*.6
            sweep=air*.38*math.sin(math.pi*t/length)**1.2
            snap=(noise*.62+low*.38)*math.exp(-abs(t-.025)*260)
            pitch=1050+(e['cut']%7)*73
            tail=math.sin(2*math.pi*(pitch-2800*t)*t)*.24*math.exp(-max(0,t-.025)*115) if t>=.025 else 0
            value=sweep+snap+tail
        else:
            value=(math.sin(2*math.pi*(110-140*t)*t)*.8+low*.35)*math.exp(-t*45)
        k=start+i
        if 0<=k<len(out):out[k]+=value*gain
peak=max(abs(x) for x in out)
# A fixed soft limiter keeps the single cut punchy when dense volleys overlap.
out=[.86*math.tanh(x*1.6) for x in out]
with wave.open('assets/sound.wav','wb') as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate)
    w.writeframes(b''.join(struct.pack('<h',int(x*32767)) for x in out))
print('Sound peak:',round(peak,3),'events:',len(events))
