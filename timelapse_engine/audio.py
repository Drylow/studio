"""Bande son d'un timelapse : musique (Kevin MacLeod, CC BY 4.0) + petits « tocs » de bois quand
des bâtiments apparaissent (pops.json écrit par render.mjs), puis mixage avec la vidéo.

    python timelapse_engine/audio.py video_raw.mp4 out.mp4 --music "work/timelapse/music/Pamgaea.mp3"
"""
import argparse
import json
import subprocess
import wave

import imageio_ffmpeg
import numpy as np

SR = 44100


def knock(rng, pitch):
    n = int(SR * 0.09)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * pitch * t) * np.exp(-t * 55) + 0.5 * np.sin(2 * np.pi * pitch * 2.6 * t) * np.exp(-t * 90)
    click = rng.standard_normal(n) * np.exp(-t * 600) * 0.35
    return (body + click) * 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--music", required=True)
    ap.add_argument("--music-gain", type=float, default=0.55)
    a = ap.parse_args()
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    hh, mm, ss = subprocess.run([ff, "-i", a.video], capture_output=True, text=True).stderr.split("Duration: ")[1].split(",")[0].split(":")
    dur = int(hh) * 3600 + int(mm) * 60 + float(ss)
    pops = json.load(open(a.video.replace(".mp4", ".pops.json")))
    rng = np.random.default_rng(3)
    sfx = np.zeros(int(SR * (dur + 1)))
    last = -1.0
    for t, n in pops:
        if n <= 0 or t - last < 0.07:  # pas plus d'un toc toutes les 70 ms
            continue
        last = t
        k = knock(rng, rng.uniform(520, 900)) * min(1.0, 0.25 + 0.18 * np.log1p(n))
        i = int(t * SR)
        sfx[i:i + len(k)] += k[:len(sfx) - i]
    sfx = np.clip(sfx * 0.32, -1, 1)
    wav = a.out + ".sfx.wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((sfx * 32767).astype("<i2").tobytes())
    fade = max(0, dur - 2.5)
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", a.video, "-i", a.music, "-i", wav, "-filter_complex",
                    f"[1:a]volume={a.music_gain},afade=t=in:d=0.8,afade=t=out:st={fade}:d=2.5[m];[2:a]aformat=channel_layouts=stereo[s];"
                    f"[m][s]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(dur), a.out], check=True)
    print("OK", a.out)


if __name__ == "__main__":
    main()
