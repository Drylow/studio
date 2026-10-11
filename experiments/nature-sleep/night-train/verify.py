"""Check the encoded night-train preview and extract its actual frames for review."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageStat

ROOT = Path(__file__).resolve().parents[3]
folder = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "output/nature-sleep/night-train-preview"
qa = folder / "qa"
qa.mkdir(exist_ok=True, parents=True)
receipt = json.loads((folder / "render-receipt.json").read_text())
movie = folder / Path(receipt["movie"]).name
sha = hashlib.sha256(movie.read_bytes()).hexdigest()
assert sha == receipt["sha256"]
assert hashlib.sha256(Path(receipt["source"]).read_bytes()).hexdigest() == receipt["source_sha256"]
if "foliage" in receipt:
    assert hashlib.sha256(Path(receipt["foliage"]).read_bytes()).hexdigest() == receipt["foliage_sha256"]
assert hashlib.sha256(Path(receipt["forest"]).read_bytes()).hexdigest() == receipt["forest_sha256"]
probe = json.loads(subprocess.check_output([
    "ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(movie)
], text=True))
streams = probe["streams"]
assert len(streams) == 1 and streams[0]["codec_type"] == "video"
stream = streams[0]
assert (stream["width"], stream["height"], stream["avg_frame_rate"], int(stream["nb_read_frames"])) == (1920, 1080, "30/1", 720)
assert abs(float(probe["format"]["duration"]) - 24) < .001
decode = subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(movie), "-f", "null", "-"], capture_output=True, text=True)
(qa / "full-decode.log").write_text(decode.stderr)
assert decode.returncode == 0 and not decode.stderr.strip()

indices = sorted(set(range(0,720,12)) | {1,2,6,18,30,90,180,270,360,450,540,630,716,717,718,719})
expression = "+".join(f"eq(n,{i})" for i in indices)
subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(movie), "-vf", f"select='{expression}'", "-vsync", "0", "-y", str(qa / "frame-%03d.png")], check=True)
records=[]
for ordinal,index in enumerate(indices,1):
    records.append({"frame":index,"seconds":index/30,"file":str(qa / f"frame-{ordinal:03d}.png")})
for page in range((len(records)+15)//16):
    sheet=Image.new("RGB",(1920,1176),"#292c41")
    draw=ImageDraw.Draw(sheet)
    for cell,record in enumerate(records[page*16:(page+1)*16]):
        image=Image.open(record["file"]).convert("RGB").resize((480,270),Image.Resampling.LANCZOS)
        x=cell%4*480;y=cell//4*294
        sheet.paste(image,(x,y))
        draw.text((x+6,y+275),f'{record["seconds"]:.3f}s — frame {record["frame"]}',fill="#efdfd8")
    sheet.save(qa / f"contact-{page+1:02d}.jpg",quality=96)

by_index={r["frame"]:Image.open(r["file"]).convert("RGB") for r in records}
def mad(a,b): return sum(ImageStat.Stat(ImageChops.difference(a,b)).mean)/3
seam=mad(by_index[719],by_index[0])
adjacent=[mad(by_index[a],by_index[b]) for a,b in [(0,1),(1,2),(716,717),(717,718),(718,719)]]
zones={"forest":[865,90,1690,570],"steam":[1170,490,1260,657],"cat":[55,690,300,810],"stable_cabin":[50,40,660,410]}
motion={name:mad(by_index[0].crop(tuple(box)),by_index[180].crop(tuple(box))) for name,box in zones.items()}
assert motion["forest"] > 3, "Forest movement is missing"
assert motion["stable_cabin"] < .4, "The stable cabin unexpectedly moves"
# Whole-frame MAD is biased by the IDR/P compression difference in the static
# cabin. Compare actual moving-window continuity separately, and bound static
# reconstruction noise to under one 8-bit RGB level on average.
window_box=(860,40,1700,560)
window_seam=mad(by_index[719].crop(window_box),by_index[0].crop(window_box))
window_neighbors=[mad(by_index[a].crop(window_box),by_index[b].crop(window_box)) for a,b in [(0,1),(1,2),(716,717),(717,718),(718,719)]]
static_seam=mad(by_index[719].crop((0,0,600,400)),by_index[0].crop((0,0,600,400)))
assert window_seam < max(window_neighbors)*1.5, "Animated window jumps at the loop boundary"
assert static_seam < 1, "Visible static cabin change at the loop boundary"
report={"technical_pass":True,"movie":str(movie),"sha256":sha,"bytes":movie.stat().st_size,"duration_seconds":24,"frames":720,"dimensions":[1920,1080],"fps":30,"audio_streams":0,"full_decode_ok":True,"native_cycle_exact_match":receipt["native_cycle_exact_match"],"seam_mean_rgb_difference_0_to_255":seam,"window_seam_mean_rgb_difference":window_seam,"window_neighbor_differences":window_neighbors,"static_cabin_seam_mean_rgb_difference":static_seam,"neighbor_frame_differences_0_to_255":adjacent,"six_second_motion_mean_rgb_difference_by_region":motion,"source_dimensions":[receipt["source_geometry"]["sourceWidth"],receipt["source_geometry"]["sourceHeight"]],"native_animation_grid":receipt.get("native_grid"),"integer_enlargement":receipt.get("integer_scale"),"continuous_subpixel_motion":receipt.get("continuous_subpixel_motion",False),"actual_decoded_captures":records,"contact_sheets":len(list(qa.glob('contact-*.jpg'))),"human_continuous_playback":False,"visual_review":"pending; metrics do not replace inspecting captures"}
(qa / "technical-review.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"technical_pass":True,"captures":len(records),"contact_sheets":report["contact_sheets"],"seam":seam,"motion":motion}))
