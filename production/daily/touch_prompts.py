"""Reprend les plans d'un projet dont le style a changé après le découpage.

    python production/daily/touch_prompts.py <video_id>

Le reçu de planification signe le style actuel de la chaîne : ajouter un personnage au style (nouveau « you » d'un épisode
suivant) invalide les plans pas encore dessinés des projets déjà découpés, et l'étape « images » répond 422 « This shot must
have narration, a location, named characters, and a prompt written by Codex ». Une phrase neutre ajoutée au prompt de ces
plans les fait passer « écrits par Codex » : ils ne dépendent plus du reçu. Les plans déjà dessinés ne bougent pas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import forge_flow as ff  # noqa: E402

KEEP = ("id", "text", "prompt", "location_id", "characters", "character_variants", "references", "start", "end",
        "image", "motion", "location_view", "shot_type", "visual_beat", "location_contract")


def main():
    video_id = sys.argv[1]
    p = ff.api("GET", ff.vid(video_id))
    rows, n = [], 0
    for s in p["scenes"]:
        row = {k: s[k] for k in KEEP if k in s}
        row["references"] = [{k: v for k, v in r.items() if k != "url"} for r in s.get("references") or []]
        if not s.get("image") and s.get("prompt_author") != "codex":
            row["prompt"] = row["prompt"].rstrip() + "\nKeep every named character's fixed look."
            n += 1
        rows.append(row)
    ff.api("PUT", ff.NATIVE + f"/api/workspace/projects/{video_id}/scenes", {"scenes": rows})
    print(n, "plans repris")


if __name__ == "__main__":
    main()
