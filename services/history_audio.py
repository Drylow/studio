"""Format Histoire : nappe musicale sombre et bruitages, générés par ffmpeg (aucun sample,
donc aucun risque Content ID). Nappe : bourdon grave + accords mineurs lents + vent ;
bruitages : whoosh (entrée des cartes), impact grave (phrases chocs), tic (unités qui bougent).
"""
import os

from services import media

# ré mineur : Dm – Bb – F – A (i – VI – III – V), 8 s par accord
_CHORDS = [(73.42, 146.83, 174.61, 220.00), (58.27, 116.54, 146.83, 174.61),
           (87.31, 130.81, 174.61, 220.00), (55.00, 110.00, 138.59, 164.81)]
_BAR = 8.0


def _pad(freqs, dur):
    # cordes « synthétiques » : fondamentale + harmoniques, léger désaccord, attaque et relâche lentes
    parts = []
    for f in freqs:
        parts.append(f"sin(2*PI*{f:.2f}*t)+0.5*sin(2*PI*{f * 2.003:.2f}*t)+0.22*sin(2*PI*{f * 3.01:.2f}*t)"
                     f"+0.6*sin(2*PI*{f * 1.004:.2f}*t)")
    env = f"(1-exp(-0.9*t))*(1-exp(-1.2*({dur:.2f}-t)))"
    drone = "0.9*sin(2*PI*36.71*t)+0.5*sin(2*PI*73.42*t)"
    return f"0.03*({'+'.join(parts)})*{env}+0.05*({drone})*(0.75+0.25*sin(2*PI*0.07*t))"


def music_bed(dest, seconds):
    """Nappe sombre bouclée à la durée voulue (MP3, ~-22 LUFS)."""
    tmp = dest + ".parts"
    os.makedirs(tmp, exist_ok=True)
    try:
        files = []
        for i, ch in enumerate(_CHORDS):
            p = os.path.join(tmp, f"c{i}.wav")
            media.run(["-f", "lavfi", "-i", f"aevalsrc='{_pad(ch, _BAR)}':s=44100:d={_BAR}", "-ac", "1", p])
            files.append(os.path.basename(p))
        loops = max(1, int(seconds // (_BAR * len(files))) + 1)
        with open(os.path.join(tmp, "list.txt"), "w", encoding="utf-8") as f:
            for _ in range(loops):
                for name in files:
                    f.write(f"file '{name}'\n")
        total = loops * _BAR * len(files)
        graph = ("[0:a]lowpass=f=1600,aecho=0.8:0.6:220|470:0.35|0.22,aformat=channel_layouts=stereo[m];"
                 "[1:a]bandpass=f=420:width_type=o:w=1.4,volume=0.05,"
                 "tremolo=f=0.12:d=0.6[w];[m][w]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-22:TP=-3[a]")
        media.run(["-f", "concat", "-safe", "0", "-i", "list.txt", "-f", "lavfi", "-i",
                   f"anoisesrc=color=brown:d={total:.2f}:a=0.6", "-filter_complex", graph, "-map", "[a]",
                   "-t", f"{seconds:.2f}", "-c:a", "libmp3lame", "-b:a", "160k", os.path.abspath(dest)], cwd=tmp)
    finally:
        for f in os.listdir(tmp):
            try:
                os.remove(os.path.join(tmp, f))
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass
    return dest


SFX = {
    # souffle filtré qui enfle puis retombe
    "whoosh": ["-f", "lavfi", "-i", "anoisesrc=color=pink:d=1.1:a=0.9", "-af",
               "highpass=f=280,lowpass=f=3200,volume='0.9*pow(sin(PI*t/1.1),3)':eval=frame,"
               "aecho=0.6:0.4:60:0.3,afade=t=out:st=0.9:d=0.2"],
    # impact grave (chute de fréquence + souffle court)
    "boom": ["-f", "lavfi", "-i",
             "aevalsrc='0.9*sin(2*PI*(62*t-14*t*t))*exp(-2.6*t)+0.25*sin(2*PI*31*t)*exp(-1.5*t)':s=44100:d=2.4",
             "-af", "lowpass=f=900,aecho=0.7:0.5:90|180:0.25|0.15,afade=t=out:st=2.0:d=0.4"],
    # tic sourd (déplacement d'unités sur la carte)
    "tick": ["-f", "lavfi", "-i", "aevalsrc='0.8*sin(2*PI*140*t)*exp(-28*t)+0.3*sin(2*PI*70*t)*exp(-18*t)':s=44100:d=0.35",
             "-af", "lowpass=f=1200"],
}


def ensure_sfx(folder):
    """Crée les bruitages manquants dans `folder` ; renvoie {nom: chemin relatif}."""
    os.makedirs(folder, exist_ok=True)
    out = {}
    for name, args in SFX.items():
        dest = os.path.join(folder, f"{name}.mp3")
        if not os.path.isfile(dest):
            media.run(args + ["-ac", "2", "-c:a", "libmp3lame", "-b:a", "128k", dest])
        out[name] = dest
    return out
