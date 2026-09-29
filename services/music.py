"""Musiques de fond libres de droits, générées localement (aucune source externe).

Ambiances « lofi » très douces : nappes d'accords + arpège feutré + léger souffle vinyle,
synthétisés par ffmpeg (aevalsrc). Comme rien n'est échantillonné, il n'y a aucun
risque de réclamation Content ID sur YouTube. Pensées pour rester très bas sous la voix.
"""
import os

from services import media

# Notes (Hz)
N = {"C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61, "G3": 196.00, "A3": 220.00, "B3": 246.94,
     "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23, "G4": 392.00, "A4": 440.00, "B4": 493.88,
     "C5": 523.25, "D5": 587.33, "E5": 659.25, "Bb3": 233.08, "Eb4": 311.13, "Ab3": 207.65}

TRACKS = {
    "lofi_warm": {"name": "Lofi chaleureux (généré)", "bpm": 72, "chords": [
        ["F3", "A3", "C4", "E4"], ["E3", "G3", "B3", "D4"], ["D3", "F3", "A3", "C4"], ["C3", "E3", "G3", "B3"]]},
    "lofi_night": {"name": "Lofi nuit (généré)", "bpm": 68, "chords": [
        ["A3", "C4", "E4", "G4"], ["F3", "A3", "C4", "E4"], ["C3", "E3", "G3", "B3"], ["G3", "B3", "D4", "F4"]]},
    "soft_piano": {"name": "Piano doux (généré)", "bpm": 64, "chords": [
        ["C3", "E3", "G3", "B3"], ["A3", "C4", "E4", "G4"], ["D3", "F3", "A3", "C4"], ["G3", "B3", "D4", "F4"]]},
}


def _segment_expr(chord, beat):
    """Expression aevalsrc d'une mesure (4 temps) : nappe + arpège en croches."""
    dur = 4 * beat
    fs = [N[n] for n in chord]
    pad = "+".join(f"sin(2*PI*{f:.2f}*t)+0.25*sin(4*PI*{f:.2f}*t)" for f in fs)
    pad = f"0.045*({pad})*(1-exp(-2.5*t))*(1-exp(-6*({dur:.3f}-t)))"
    arp_notes = [fs[0] * 2, fs[1] * 2, fs[2] * 2, fs[3] * 2, fs[2] * 2, fs[1] * 2, fs[3] * 2, fs[2] * 2]
    step = beat / 2
    arp = "+".join(f"between(t,{j * step:.3f},{(j + 1) * step:.3f})*exp(-5*(t-{j * step:.3f}))"
                   f"*(sin(2*PI*{f:.2f}*t)+0.3*sin(4*PI*{f:.2f}*t))" for j, f in enumerate(arp_notes))
    return f"{pad}+0.05*({arp})", dur


def generate(key, dest, minutes=2.5):
    """Génère la piste `key` (MP3) dans dest ; renvoie le chemin."""
    t = TRACKS[key]
    beat = 60.0 / t["bpm"]
    tmpdir = dest + ".parts"
    os.makedirs(tmpdir, exist_ok=True)
    try:
        segs = []
        for i, chord in enumerate(t["chords"]):
            expr, dur = _segment_expr(chord, beat)
            p = os.path.join(tmpdir, f"s{i}.wav")
            media.run(["-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d={dur:.3f}", "-ac", "1", p])
            segs.append((p, dur))
        cycle = sum(d for _, d in segs)
        loops = max(1, int(minutes * 60 / cycle))
        lst = os.path.join(tmpdir, "list.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for _ in range(loops):
                for p, _ in segs:
                    f.write(f"file '{os.path.basename(p)}'\n")
        total = loops * cycle
        # chaleur : passe-bas, écho doux (pseudo-réverb), souffle vinyle très discret, fondu
        graph = (f"[0:a]lowpass=f=2400,aecho=0.8:0.55:140|290:0.28|0.16,aformat=channel_layouts=stereo[m];"
                 f"[1:a]lowpass=f=1800,volume=0.012[n];[m][n]amix=inputs=2:duration=first:normalize=0,"
                 f"afade=t=in:d=2,afade=t=out:st={max(0.0, total - 3):.2f}:d=3,loudnorm=I=-20:TP=-2[a]")
        media.run(["-f", "concat", "-safe", "0", "-i", "list.txt", "-f", "lavfi", "-i",
                   f"anoisesrc=color=brown:d={total:.2f}:a=0.5", "-filter_complex", graph, "-map", "[a]",
                   "-c:a", "libmp3lame", "-b:a", "160k", os.path.abspath(dest)], cwd=tmpdir)
    finally:
        for f in os.listdir(tmpdir):
            try:
                os.remove(os.path.join(tmpdir, f))
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass
    return dest


def ensure_defaults(music_dir):
    """Crée les musiques générées si la bibliothèque n'en contient aucune."""
    os.makedirs(music_dir, exist_ok=True)
    made = []
    for key in TRACKS:
        dest = os.path.join(music_dir, f"{key}_libre.mp3")
        if not os.path.isfile(dest):
            generate(key, dest)
            made.append(dest)
    return made
