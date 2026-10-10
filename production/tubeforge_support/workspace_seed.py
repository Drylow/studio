"""One-time, non-destructive setup of the user's historical workspace."""
import copy
import hashlib
from pathlib import Path
import shutil

from . import channels, config, store
from .util import read_json, write_json

POV_PROMPT = (
    "Minimalist cartoon illustration, ALL characters MUST have perfectly round oversized white heads "
    "with thick black outlines, simple small black dot eyes, tiny straight line mouth, NO nose, NO ears, "
    "NO hair, NO eyebrows, completely smooth white round heads like a perfect circle. ALL exposed skin "
    "MUST be #FFFFFF pure bright white — white hands, white arms, white neck, SAME pure white as their "
    "heads with NO variation. NO beige, NO cream, NO peach, NO tan, NO skin tone anywhere. Characters "
    "MUST wear long sleeves and long pants. Bodies are simplified but ADULT-SIZED and proportional "
    "compared to oversized heads — NOT tiny, NOT child-sized. Simple rounded white hands with NO "
    "detailed fingers. ALL characters MUST be the same cartoon style — absolutely NO realistic human "
    "faces, NO human hair, NO human features on ANY character. NO children unless specified. Clean "
    "flat digital illustration, anime-inspired detailed backgrounds, NO shading on faces or skin."
)

BACKGROUND_DIRECTION = (
    "Decors BD sobres : lignes nettes, aplats mats, textures reduites, ombres simples. Architecture "
    "detaillee et lisible. Horizons credibles, sans tours ou monuments fantaisie. Une reference "
    "maitre par lieu, des personnages references et des actions variees : pas le meme tableau partout."
)

THUMBNAIL_DIRECTION = (
    "Expressive human cartoon faces, clean comic illustration, 16:9 YouTube thumbnail. One readable "
    "scene showing several different daily activities appropriate to the video topic. Expression "
    "matches the situation. Historically grounded clothing and architecture. Short text relates "
    "to the final script and title; never claim NO JOBS without evidence. Do not always show a bread seller."
)

PROFILES = [
    ("edo-daily", "Edo Daily", "Japon d'Edo", "01-Edo-Daily.png"),
    ("aztec-daily", "Aztec Daily", "Tenochtitlan", "02-Aztec-Daily.png"),
    ("babylon-daily", "Babylon Daily", "Babylone", "03-Babylon-Daily.png"),
    ("imperial-china-daily", "Imperial China Daily", "Chine imperiale", "04-Imperial-China-Daily-v2.png"),
    ("ottoman-daily", "Ottoman Daily", "Empire ottoman", "05-Ottoman-Daily.png"),
]

PREVIEWS = {
    "edo-daily": "output/imagegen/style-bd-sobre-tetes-blanches-2026-10-07/01-edo.png",
    "aztec-daily": "output/imagegen/historical-01-2026-10-08/aztec-daily/shots/aztec-001-v2.png",
    "babylon-daily": "output/imagegen/historical-01-2026-10-08/babylon-daily/shots/babylon-001.png",
    "imperial-china-daily": "output/imagegen/historical-01-2026-10-08/imperial-china-daily/shots/tang-003.png",
    "ottoman-daily": "output/imagegen/historical-01-2026-10-08/ottoman-daily/shots/ottoman-001-v2.png",
}


def migrate_previews(studio):
    for channel in channels.list_channels():
        if channel["id"] not in PREVIEWS or channel.get("video_preview") != "refs/pov-video-preview.png":
            continue
        source = studio / PREVIEWS[channel["id"]]
        if source.is_file():
            target = "refs/preview-" + channel["id"] + ".png"
            shutil.copy2(source, store.style_dir(channel["style_id"]) / target)
            channel.update(video_preview=target, preview_label="Exemple de plan existant / miniature a valider")
            channels.save(channel)


def seed_workspace():
    marker = config.DATA / "workspace-seeded.json"
    studio = Path(config.get("STUDIO_ROOT")).resolve()
    if marker.exists():
        if read_json(marker).get("version") == 1:
            migrate_previews(studio)
            record = read_json(marker)
            record["version"] = 2
            write_json(marker, record)
        return read_json(marker)
    style = store.get_style("pov-history") or store.default_style("pov-history", "POV style")
    archive = config.DATA / "archives/workspace-before-simplification"
    archive.mkdir(parents=True, exist_ok=True)
    write_json(archive / "pov-history.json", copy.deepcopy(style))
    original_channels = channels.list_channels()
    write_json(archive / "channels.json", original_channels)
    style["name"] = "POV style"
    style["characters"] = []
    style["script"].update(instructions="Scripts, decoupages et prompts ecrits par Codex, sans reecriture automatique.", references=[])
    style["visuals"].update(art_style=POV_PROMPT, avg_scene_seconds=6, use_style_refs=True,
                            auto_characters=False, background_direction=BACKGROUND_DIRECTION)
    style["thumbnail"].update(style=THUMBNAIL_DIRECTION)
    style["shorts"]["promo_count"] = 0
    style["workspace_revision"] = "2026-10-10"
    refs_dir = store.style_dir(style["id"]) / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)

    def asset(source, name):
        source = studio / source
        if not source.is_file():
            return None
        shutil.copy2(source, refs_dir / name)
        return "refs/" + name

    sources = []
    for name in ("01-innocent-prison.jpg", "02-innocent-prison.jpg", "03-hitman.jpg", "04-hitman.jpg", "05-getaway-driver.jpg"):
        ref = asset("reference/strangely-ironic-guy/" + name, "strangely-" + name)
        if ref:
            sources.append({"file": ref, "observed": "2026-10-05", "label": "Capture video du 30 septembre au 2 octobre",
                            "role": "style-only", "sha256": hashlib.sha256((refs_dir.parent / ref).read_bytes()).hexdigest()})
    style["visuals"]["style_refs"] = [x["file"] for x in sources]
    style["visuals"]["reference_sources"] = sources
    style["visuals"]["reference_update_pending"] = True
    preview = asset("output/imagegen/style-bd-sobre-tetes-blanches-2026-10-07/01-edo.png", "pov-video-preview.png")
    style["visuals"]["preview"] = preview
    style["voice"]["provider"] = "algrow"
    store.save_style(style)
    for cid, name, setting, thumbnail in PROFILES:
        existing = next((c for c in original_channels if c["id"] == cid), None)
        if existing:
            continue
        thumb = asset("output/imagegen/miniatures-01-journee-v2-2026-10-07/A-REGARDER/" + thumbnail, "thumb-" + cid + ".png")
        channels.save({"id": cid, "name": name, "language": "English", "style_id": style["id"],
                       "kind": "long", "historical_profile": True, "setting": setting, "target_minutes": 22,
                       "auto_resolve": False, "voice": copy.deepcopy(style["voice"]),
                       "video_preview": preview, "thumbnail_preview": thumb,
                       "preview_label": "Style video commun / proposition de miniature a valider"})
    migrate_previews(studio)
    result = {"version": 2, "style_id": style["id"], "profiles": [x[0] for x in PROFILES],
              "reference_update_pending": True, "projects_untouched": True}
    write_json(marker, result)
    return result


if __name__ == "__main__":
    print(seed_workspace())
