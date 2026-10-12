"""Découpe la voix off en scènes (une image par scène), calées sur les pauses naturelles.

Programmation dynamique : on cherche les coupures qui donnent des scènes proches de la durée
cible, en préférant couper en fin de phrase, puis sur ; : — puis sur les virgules.
"""
import hashlib
import re

CUT_PENALTY = {3: 0.0, 2: 0.3, 1: 0.8, 0: 3.0}


def cut_strength(script: str, w: dict, nxt: dict | None) -> int:
    seg = script[w["c0"]:nxt["c0"]] if nxt else script[w["c0"]:]
    seg_tail = seg.rstrip()
    if "\n" in seg.strip(" \t") or not nxt:
        return 3
    if re.search(r"[.!?…][\"'”’»)\]]*$", seg_tail):
        return 3
    if re.search(r"[;:—–]$|\s[-—–]$", seg_tail):
        return 2
    if re.search(r"[,)]$", seg_tail):
        return 1
    return 0


def split(words: list[dict], script: str, total: float, target: float = 6.0,
          min_d: float = 2.0, max_d: float = 12.0) -> list[dict]:
    n = len(words)
    if n == 0:
        return [{"start": 0.0, "end": total, "text": script.strip(), "w0": 0, "w1": 0}]
    strength = [cut_strength(script, words[i], words[i + 1] if i + 1 < n else None) for i in range(n)]

    def boundary(i: int) -> float:
        if i <= 0:
            return 0.0
        if i >= n:
            return total
        return (words[i - 1]["e"] + words[i]["s"]) / 2

    b = [boundary(i) for i in range(n + 1)]
    INF = float("inf")
    best = [INF] * (n + 1)
    prev = [0] * (n + 1)
    best[0] = 0.0
    for j in range(1, n + 1):
        pen = CUT_PENALTY[strength[j - 1]] if j < n else 0.0
        i = j - 1
        while i >= 0:
            d = b[j] - b[i]
            if d > max_d and j - i > 1:
                break
            if best[i] < INF:
                c = ((d - target) / target) ** 2
                if d < min_d:
                    c += 3 + (min_d - d) * 3
                cost = best[i] + c + pen
                if cost < best[j]:
                    best[j], prev[j] = cost, i
            i -= 1
    cuts, j = [], n
    while j > 0:
        cuts.append((prev[j], j))
        j = prev[j]
    cuts.reverse()
    scenes = []
    for i, j in cuts:
        text = script[words[i]["c0"]:words[j - 1]["c1"]].strip()
        if not text:
            text = " ".join(w["w"] for w in words[i:j])
        scenes.append({"start": round(b[i], 3), "end": round(b[j], 3), "text": re.sub(r"\s+", " ", text),
                       "w0": i, "w1": j, "c0": words[i]["c0"], "c1": words[j - 1]["c1"]})
    return scenes


def script_hash(script: str) -> str:
    return hashlib.sha1(script.encode("utf-8")).hexdigest()[:16]


def retime(scenes: list[dict], words: list[dict], total: float) -> bool:
    """Recalcule début/fin de scènes existantes avec de nouveaux timings (même script, autre voix).

    Retourne False si les scènes ne portent pas leurs positions dans le texte (anciens projets)."""
    if not words or any("c0" not in s for s in scenes):
        return False
    starts = []
    k = 0
    for s in scenes:
        while k < len(words) and words[k]["c0"] < s["c0"]:
            k += 1
        starts.append(k)
    n = len(words)
    for i, s in enumerate(scenes):
        a = starts[i]
        s["start"] = 0.0 if i == 0 else round((words[a - 1]["e"] + words[a]["s"]) / 2, 3) if 0 < a < n else \
            scenes[i - 1]["end"]
    for i, s in enumerate(scenes):
        s["end"] = round(total, 3) if i == len(scenes) - 1 else scenes[i + 1]["start"]
    return all(s["end"] > s["start"] for s in scenes)
