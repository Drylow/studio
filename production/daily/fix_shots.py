"""Corrige le prompt de quelques plans (sans toucher aux autres) puis les refait.

    python production/daily/fix_shots.py <video_id> fixes.json

fixes.json : {"41": {"replace": [["ancien texte", "nouveau texte"], ...], "append": "phrase ajoutée", "characters": [...],
                     "drop": ["Nom"]}, ...}   # drop : retire ce personnage et sa référence (corriger aussi le prompt)
Les autres plans sont renvoyés tels quels (image et revue conservées). Les plans corrigés sont refaits ensemble
par l'étape « images » (parallèle) ; `--one-by-one` les refait un par un.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import forge_flow as ff  # noqa: E402

KEEP = ("id", "text", "prompt", "location_id", "characters", "character_variants", "references", "start", "end",
        "image", "motion", "location_view", "shot_type", "visual_beat", "location_contract")


def main():
    video_id, fixes = sys.argv[1], json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    p = ff.api("GET", ff.vid(video_id))
    rows = []
    for s in p["scenes"]:
        row = {k: s[k] for k in KEEP if k in s}
        row["references"] = [{k: v for k, v in r.items() if k != "url"} for r in s.get("references") or []]
        fix = fixes.get(str(s["id"]))
        if fix:
            for old, new in fix.get("replace", []):
                if old not in row["prompt"]:
                    raise SystemExit(f"#{s['id']} : texte à remplacer introuvable : {old[:60]}")
                row["prompt"] = row["prompt"].replace(old, new)
            if fix.get("append"):
                row["prompt"] = row["prompt"].rstrip() + "\n" + fix["append"]
            if "characters" in fix:
                row["characters"] = fix["characters"]
            for name in fix.get("drop", []):   # personnage à retirer du plan, avec son image de référence
                row["characters"] = [c for c in row.get("characters") or [] if c != name]
                row.get("character_variants", {}).pop(name, None)
                row["references"] = [r for r in row["references"] if r.get("character") != name]
            row.pop("image", None)
        rows.append(row)
    ff.api("PUT", ff.NATIVE + f"/api/workspace/projects/{video_id}/scenes", {"scenes": rows})
    if "--one-by-one" in sys.argv:
        ff.regen(video_id, [int(k) for k in fixes])
        return
    # Les plans corrigés n'ont plus d'image : l'étape « images » les refait toutes en parallèle (quelques minutes
    # au lieu d'une minute par plan). Elle s'arrête parfois sur un échec isolé : on la relance pour les restes.
    for _ in range(6):
        s = ff.status(video_id)
        img = s.get("images") or {}
        if img.get("done") == img.get("total"):
            break
        try:
            ff.run(video_id, "images", {})
        except SystemExit as e:   # échec isolé : le tour suivant reprend les plans restants
            print(e, flush=True)
    print("plans refaits :", ff.summary(ff.status(video_id)))


if __name__ == "__main__":
    main()
