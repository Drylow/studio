"""Crée un style TubeForge propre (découpage automatique permis) à partir d'une fiche JSON, puis branche la chaîne.

    python production/daily/make_style.py fiche.json

fiche.json : {"channel_id": "...", "name": "...", "prompt": "...", "background_direction": "...",
              "thumbnail_prompt": "...", "drawing_guide": "chemin.png",
              "cast": [{"name": "Eirik", "image": "chemin.png", "description": "...", "main": true}, ...]}
Chaque image de personnage est versée puis marquée vérifiée : ne la mettre dans la fiche qu'après l'avoir
regardée. Le style ne garde qu'une image de dessin, pas les anciens décors non relus.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "production" / "daily"))
import forge_flow as ff  # noqa: E402
sys.path.insert(0, str(ROOT))
from services import ai  # noqa: E402

CLI = str(ROOT / "production/tubeforge_support/forge_docs/forge.py")


def upload(url, image, fields):
    cmd = ["python3", CLI, "upload", url, str(image)] + sum((["--field", f"{k}={v}"] for k, v in fields.items()), [])
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)


def main():
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    base = ff.NATIVE + "/api/workspace/management"
    s = ff.api("POST", base + "/styles", {
        "name": spec["name"], "prompt": spec["prompt"], "background_direction": spec["background_direction"],
        "thumbnail_prompt": spec["thumbnail_prompt"], "image_provider": "cli_proxy", "image_model": ai.image_model(),
        "camera_policy": "varied"})
    sid = s["id"]
    ref = upload(f"/api/2d/api/workspace/management/styles/{sid}/references", ROOT / spec["drawing_guide"],
                 {"label": "drawing guide"})
    ff.api("PUT", f"{base}/styles/{sid}", {"drawing_reference_path": ref["path"]})
    for c in spec["cast"]:
        fields = {"name": c["name"], "variant": "default", "description": c["description"]}
        if c.get("main"):
            fields["is_main"] = "true"
        upload(f"/api/2d/api/workspace/management/styles/{sid}/characters", ROOT / c["image"], fields)
        ff.api("PUT", f"{base}/styles/{sid}/characters", {"name": c["name"], "variant": "default",
                                                          "description": c["description"], "verify": True,
                                                          "is_main": bool(c.get("main"))})
        print(c["name"], "ok")
    if spec.get("channel_id"):
        ff.api("PUT", f"{base}/channels/{spec['channel_id']}", {"style_id": sid})
    print("STYLE", sid)


if __name__ == "__main__":
    main()
