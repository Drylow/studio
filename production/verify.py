"""Vérification d'une vidéo AVANT envoi : contrôles automatiques (ticket de caisse juste du début à la fin,
chiffres affichés = chiffres dits, intro sans « total ») + planches d'images à chaque animation (intro,
tickets, compteurs, cartes HAND, trajets, listes...) à REGARDER. Écrit <folder>/check/report.txt et
<folder>/check/fx_*.jpg.  python production/verify.py <folder>"""
import os
import re
import subprocess
import sys

from common import folder
from services import pov_engine as E, pov_store as store, motion
from PIL import Image, ImageDraw
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
D = folder(sys.argv[1])
pid = open(os.path.join(D, "pid.txt")).read().strip()
pr = store.get_project(pid)
video = os.path.join(store.project_dir(pid), pr["render"]["file"])
out = os.path.join(D, "check")
os.makedirs(out, exist_ok=True)
x = E.render_inputs(pid, os.path.join(out, "work"))
problems = []
allowed = E.allowed_numbers(pr)
rows, total = [], None
for f in x["fx"] or []:
    sp = f["spec"]
    t = sp.get("type")
    if t in ("intro", "outro", "title"):
        if any(re.search(r"(?i)total", it) for it in sp.get("items") or []):
            problems.append(f"intro : ligne qui ressemble à un total : {sp.get('items')}")
        continue
    nums = set(E._fx_numbers(sp)) if t != "chapter" else set()  # « HAND #3 » vient du titre de partie
    if not nums <= allowed:
        problems.append(f"{f['t']:.1f}s {t} : chiffres jamais dits {sorted(nums - allowed)}")
    if t == "receipt":
        asked = [(str(i.get("item")), str(i.get("amount"))) for i in sp.get("items") or []]
        new = motion.recap_filter(rows, asked, total, str(sp.get("total") or ""))
        if any(E._TOTAL_ITEM.match(n) for n, _ in asked):
            problems.append(f"{f['t']:.1f}s ticket : ligne « total » {asked}")
        exp = (motion._amount(total) or 0) + sum(E._signed_amount(a) or 0 for _, a in new)
        tv = motion._amount(sp.get("total"))
        if new and tv is not None and abs(exp - tv) > 0.5:
            problems.append(f"{f['t']:.1f}s ticket : total {sp.get('total')} au lieu de {exp:,.0f}")
        if not new and total and tv is not None and abs((motion._amount(total) or 0) - tv) > 0.5:
            problems.append(f"{f['t']:.1f}s récap : total {sp.get('total')} au lieu de {total}")
        rows += new
        total = sp.get("total") or total
# planches : une image 1,8 s après le début de chaque animation (+ fin de l'intro)
shots = []
fxs = x["fx"] or []
for n, f in enumerate(fxs):
    t = f["spec"].get("type")
    obj = motion.make(f["spec"], {"panel": (0, 0, 1920, 1080), "k": 1.0, "W": 1920, "H": 1080})
    at = f["t"] + min(max(1.8, (obj.length if obj else 1.5) + 0.3), 6.0)
    if n + 1 < len(fxs):  # avant que l'animation suivante ne la remplace
        at = max(f["t"] + 0.8, min(at, fxs[n + 1]["t"] - 0.3))
    shots.append((at, f"{int(at // 60)}:{int(at % 60):02d} {t}"))
frames = []
for k, (at, lab) in enumerate(shots):
    p = os.path.join(out, f"s{k:03d}.jpg")
    subprocess.run([FF, "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", video, "-frames:v", "1", "-vf", "scale=480:-1", p])
    if os.path.isfile(p):
        im = Image.open(p).convert("RGB")
        ImageDraw.Draw(im).rectangle((0, 0, 200, 22), fill=(0, 0, 0))
        ImageDraw.Draw(im).text((4, 4), lab, fill=(255, 255, 0))
        frames.append(im)
for i in range(0, len(frames), 12):
    sheet = Image.new("RGB", (480 * 3, 270 * 4), "white")
    for j, im in enumerate(frames[i:i + 12]):
        sheet.paste(im.resize((480, 270)), ((j % 3) * 480, (j // 3) * 270))
    sheet.save(os.path.join(out, f"fx_{i // 12 + 1:02d}.jpg"), quality=82)
rep = "\n".join(problems) or "OK : aucun problème automatique"
open(os.path.join(out, "report.txt"), "w").write(rep + f"\n{len(frames)} images, {(len(frames) + 11) // 12} planches\n")
print(rep, len(frames), "frames")
