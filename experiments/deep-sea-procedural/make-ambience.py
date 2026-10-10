#!/usr/bin/env python3
"""Create quiet original underwater ambience; no samples, music, or speech."""
import argparse
import math
import random
import wave
from pathlib import Path
from array import array

def create(seconds, output):
    rate=48000
    total=round(seconds*rate)
    rng=random.Random(1442)
    pcm=array('h')
    low_left=low_right=0.0
    for i in range(total):
        t=i/rate
        envelope=min(1,t/1.5,(seconds-t)/2)
        envelope=max(0,envelope)
        low_left=.986*low_left+.014*rng.uniform(-1,1)
        low_right=.986*low_right+.014*rng.uniform(-1,1)
        rumble=math.sin(2*math.pi*48*t)*.038 + math.sin(2*math.pi*71*t+.11*math.sin(t*.7))*.025
        pulse=math.sin(2*math.pi*188*t)*(.0015+.0015*math.sin(t*.17))
        left=(rumble+low_left*.34+pulse)*envelope
        right=(rumble*.94+low_right*.34+pulse)*envelope
        pcm.extend((round(max(-1,min(1,left))*32767),round(max(-1,min(1,right))*32767)))
    output.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(output),'wb') as stream:
        stream.setparams((2,2,rate,total,'NONE','not compressed'))
        stream.writeframes(pcm.tobytes())

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=float,default=30)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if not math.isfinite(args.seconds) or args.seconds<=0 or args.seconds>120:
        parser.error('Use a duration between 0 and 120 seconds.')
    create(args.seconds,args.out)
    print(f'Original stereo ambience: {args.seconds:g}s / 48 kHz')
