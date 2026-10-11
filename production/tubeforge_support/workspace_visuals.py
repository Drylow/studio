"""Explicit one-time replacement of the style catalog, retaining existing media."""
import copy
import hashlib
from pathlib import Path
import shutil

from app import channels, config, google_flow, store
from app.util import now, read_json, write_json


STYLE_ID = "fictional-god-of-war"
THEMES = (("pokemon", "Pokemon - tetes blanches"),
          ("naruto", "Naruto - tetes blanches"),
          ("god-of-war", "God of War - tetes blanches"))
ART_STYLE = (
    "2D hand-drawn comic illustration matching the user-approved visual references. Every humanoid, "
    "including protagonists, recognizable fictional heroes, companions and background extras, has an "
    "oversized perfectly round white head, simple small black eyes and a small expressive line mouth. "
    "Simple eyebrows may convey emotion. No realistic human faces, noses or ears. Exposed skin and "
    "rounded simplified hands are white; bodies have readable adult proportions, fully clothed in the "
    "outfits, armor, headbands, hats and equipment appropriate to the current fictional universe. "
    "Identity comes from outfit, silhouette, equipment and distinctive markings, while the round white "
    "head remains intact. Non-humanoid creatures retain their recognizable species design and colors, "
    "as in the approved creature-companion reference. Clean dark ink contours, matte colored shapes, "
    "restrained cel shading, readable detailed comic environments and clear expressive action. "
    "Treat attached approved images as drawing-style references only: do not copy their setting, "
    "characters or props into a different universe. No photorealism, 3D render or mixed human-face styles. "
    "No captions, lettering or watermark unless explicitly requested in the scene prompt."
)
BACKGROUND = (
    "Detailed readable comic environments appropriate to each fictional universe, clean lines, matte "
    "colors and restrained shading. Composition follows the narrated action: interactions, gestures, "
    "objects, reactions, close-ups and occupied spaces. Avoid repeating one tableau with only zooms. "
    "Use verified location and character references for continuity within each scene."
)
THUMBNAIL = (
    "Readable 16:9 comic thumbnail using the same round white-headed humanoids and universe-specific "
    "outfits as the video. One clear dramatic action tied to the title and actual story, expressive "
    "simple faces, detailed but readable setting, strong subject contrast. Non-humanoid creatures keep "
    "their species identity. No realistic human faces. Text only when explicitly supplied."
)


def activate(studio=None):
    """Run only on explicit user request; later deployments do not reset edits."""
    marker = config.DATA / "workspace-visual-policy.json"
    if marker.exists():
        return read_json(marker)
    studio = Path(studio or config.get("STUDIO_ROOT")).resolve()
    source = studio / "output/imagegen/fictional-theme-references-2026-10-11"
    if not google_flow.configured():
        raise ValueError("Google Flow must be configured before replacing the styles")
    record = read_json(source / "registre.json", {})
    grouped = {}
    for theme, _ in THEMES:
        scenes = [s for s in record.get("scenes", []) if s.get("theme") == theme]
        if len(scenes) != 3:
            raise ValueError("Each theme needs exactly three reviewed references")
        for scene in scenes:
            path = (source / scene.get("image", "")).resolve()
            if (not path.is_relative_to(source.resolve()) or not path.is_file()
                    or scene.get("review_state") != "reviewed_by_codex"
                    or hashlib.sha256(path.read_bytes()).hexdigest() != scene.get("image_sha256")):
                raise ValueError("A reference is missing, changed or not visually reviewed")
        grouped[theme] = scenes
    styles = list(config.STYLES_DIR.glob("*/style.json"))
    saved_channels = read_json(channels.FILE, []) or []
    backup = config.DATA / "archives" / ("styles-before-fictional-" + str(now()).replace(".", "-"))
    backup.mkdir(parents=True, exist_ok=False)
    write_json(backup / "channels.json", saved_channels)
    for path in styles:
        target = backup / path.parent.name
        target.mkdir()
        shutil.copy2(path, target / "style.json")
    base = copy.deepcopy(store.get_style("pov-history") or store.default_style())
    model = google_flow.setting("USEAPI_IMAGE_MODEL")
    for theme, name in THEMES:
        sid = "fictional-" + theme
        style = copy.deepcopy(base)
        style.update(id=sid, name=name, archived=False, workspace_managed=True,
                     created=now(), updated=now(), characters=[])
        style["script"].update(instructions="Scripts, decoupages et prompts ecrits par Codex. Aucune reecriture automatique.", references=[])
        style["visuals"].update(art_style=ART_STYLE + " Current universe: " + name.split(" - ")[0] + ".",
            background_direction=BACKGROUND, image_provider="google_flow", image_model=model,
            auto_characters=False, avg_scene_seconds=6, use_style_refs=True, reference_update_pending=False)
        style["thumbnail"].update(style=THUMBNAIL, model=model, image_provider="google_flow", preview=None)
        style["shorts"]["promo_count"] = 0
        directory = store.style_dir(sid) / "refs"
        directory.mkdir(parents=True, exist_ok=True)
        refs = []
        for scene in grouped[theme]:
            filename = Path(scene["image"]).name
            destination = directory / filename
            shutil.copy2(source / scene["image"], destination)
            refs.append({"path": "refs/" + filename, "label": scene["stem"], "role": "style-only",
                         "sha256": scene["image_sha256"], "review_state": "verified"})
        style["workspace_references"] = refs
        style["visuals"].update(style_refs=[r["path"] for r in refs], reference_sources=copy.deepcopy(refs),
                                preview=refs[0]["path"])
        store.save_style(style)
    for channel in saved_channels:
        channel.setdefault("preview_history", []).append({"style_id": channel.get("style_id"),
            "video_preview": channel.pop("video_preview", None),
            "thumbnail_preview": channel.pop("thumbnail_preview", None), "changed_at": now()})
        channel.update(style_id=STYLE_ID, reference_status="derived_from_user_approved_style", updated=now())
    if not any(c.get("name") == "Oddly Fictional Lives" for c in saved_channels):
        saved_channels.append({"id": "oddly-fictional-lives", "name": "Oddly Fictional Lives",
            "language": "English", "style_id": STYLE_ID, "workspace_managed": True,
            "kind": "long", "target_minutes": 20, "auto_resolve": False, "created": now(),
            "reference_status": "derived_from_user_approved_style", "voice": copy.deepcopy(base["voice"])})
    write_json(channels.FILE, saved_channels)
    # Remove definitions from both active and archived catalogs. Keep media paths in
    # place because older projects can still refer to these exact source images.
    for path in styles:
        if path.parent.name not in {"fictional-" + theme for theme, _ in THEMES}:
            path.unlink()
    config.update({"IMAGE_PROVIDER": "google_flow"})
    policy = {"version": 1, "default_style_id": STYLE_ID, "image_provider": "google_flow",
              "activated_at": now(), "retired_style_ids": [p.parent.name for p in styles if p.parent.name not in {"fictional-" + theme for theme, _ in THEMES}],
              "backup": str(backup.relative_to(config.DATA)), "projects_untouched": True}
    write_json(marker, policy)
    return policy


if __name__ == "__main__":
    print(activate())
