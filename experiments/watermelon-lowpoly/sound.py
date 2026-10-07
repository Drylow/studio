"""Deterministic, band-limited cut accents and restrained fragment landings."""
import json, math, random, wave, struct
from pathlib import Path

rate = 48000
simulation = json.loads(Path('assets/simulation.json').read_text(encoding='utf-8'))
out = [0.0] * int(simulation['duration'] * rate)
rng = random.Random(10726)
events = json.loads(Path('assets/events.json').read_text(encoding='utf-8'))
cuts = [e for e in events if e['type'] == 'cut']
impacts = [e for e in events if e['type'] != 'cut']

# Nearby landings share a quiet wooden accent instead of hundreds of overlapping
# resonances. Cuts remain individually aligned with their geometric events.
groups = {}
for e in impacts:
    key = (e['chapter'], int(e['t'] / .05))
    group = groups.setdefault(key, {'t': e['t'], 'energy': 0})
    group['energy'] += min(.09, e['speed'] * .012) ** 2
accents = [(e, True) for e in cuts]
accents += [({'t': g['t'], 'gain': min(.045, math.sqrt(g['energy']) * .30)}, False)
            for g in groups.values()]
accents.sort(key=lambda item: item[0]['t'])
for e, cut in accents:
    length = .055 if cut else .065
    center = .018
    start = round((e['t'] - center if cut else e['t']) * rate)
    occupancy = sum(abs(c['t'] - e['t']) < .04 for c in cuts) if cut else 1
    gain = .90 / math.sqrt(occupancy) if cut else e['gain']
    low = mid = air = 0.0
    for i in range(round(length * rate)):
        t = i / rate
        noise = rng.uniform(-1, 1)
        low = low * .92 + noise * .08
        mid = mid * .72 + noise * .28
        air = air * .88 + noise * .12
        fade = min(1, t / .003, (length - t) / .004)
        if cut:
            snap = (mid - low) * 1.35 * math.exp(-abs(t - center) * 220)
            sweep = air * .13 * math.sin(math.pi * t / length)
            age = max(0, t - center)
            tail = math.sin(2 * math.pi * (430 - 900 * age) * age) * .14 * math.exp(-age * 100) if t >= center else 0
            value = snap + sweep + tail
        else:
            value = (math.sin(2 * math.pi * (130 - 160 * t) * t) * .60 + low * .20) * math.exp(-t * 55)
        k = start + i
        if 0 <= k < len(out):
            out[k] += value * gain * fade

raw_peak = max(abs(x) for x in out)
# Linear headroom avoids the previous saturator's distortion during salves.
master_gain = min(1.8, .78 / max(raw_peak, 1e-9))
out = [x * master_gain for x in out]
with wave.open('assets/sound.wav', 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes(b''.join(struct.pack('<h', round(x * 32767)) for x in out))
report = {'cut_accents': len(cuts), 'original_impact_events': len(impacts),
          'mixed_impact_groups': len(groups), 'master_gain': master_gain,
          'peak': max(abs(x) for x in out), 'clipped_samples': sum(abs(x) >= 1 for x in out)}
assert len(cuts) == sum(s['count'] for s in simulation['shots'])
assert report['clipped_samples'] == 0
Path('qa').mkdir(exist_ok=True)
Path('qa/sound-polish-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
