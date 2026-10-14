"""Corrige le prompt de quelques plans (sans toucher aux autres) puis les refait.

    python production/daily/fix_shots.py <video_id> fixes.json

fixes.json : {"41": {"replace": [["ancien texte", "nouveau texte"], ...], "append": "phrase ajoutée", "characters": [...],
                     "drop": ["Nom"]}, ...}   # drop : retire ce personnage et sa référence (corriger aussi le prompt)
Les autres plans sont renvoyés tels quels (image et revue conservées).
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
    ff.regen(video_id, [int(k) for k in fixes])


if __name__ == "__main__":
    main()
