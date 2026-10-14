"""Horodate les chapitres d'une description sur la vraie voix TubeForge (jamais estimés sur le texte).

    python production/daily/chapters.py <video_id> anchors.json

anchors.json : [["Titre du chapitre", "premiers mots exacts de sa première phrase"], ...] dans l'ordre.
Affiche les lignes « 00:00 Titre » ; le premier chapitre est toujours à 00:00 (règle YouTube).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import forge_flow as ff  # noqa: E402


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'"))


def main():
    video_id, anchors = sys.argv[1], json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    words = ff.api("GET", ff.vid(video_id) + "/transcript")["words"]
    spoken = [norm(w["w"]) for w in words]
    pos, lines = 0, []
    for i, (title, start) in enumerate(anchors):
        key = [norm(w) for w in start.split() if norm(w)][:6]
        hit = next((j for j in range(pos, len(spoken) - len(key) + 1) if spoken[j:j + len(key)] == key), None)
        if hit is None:
            raise SystemExit(f"début introuvable dans la voix : {title} / {start}")
        t = 0 if i == 0 else words[hit]["s"]
        pos = hit + 1
        lines.append(f"{int(t // 60):02d}:{int(t % 60):02d} {title}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
