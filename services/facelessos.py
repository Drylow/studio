"""FacelessOS v5 : les skills de scriptwriting appliquées à chaque script.

Les fichiers du pack (skills/facelessos/*.md + trailer-voice-scan.py) sont lus tels quels :
les prompts d'écriture et d'audit citent le texte des skills (« run from the open file,
never from memory »), et le scanner d'origine tourne en Python sur chaque brouillon.
Pour mettre le pack à jour, il suffit de remplacer le contenu du dossier.
"""
import importlib.util
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(ROOT, "skills", "facelessos")
REFS_DIR = os.path.join(ROOT, "skills", "references")

_cache = {}


def skill(name):
    """Texte d'un fichier du pack (frontmatter retiré), '' s'il manque."""
    path = os.path.join(SKILLS_DIR, name)
    try:
        st = os.stat(path)
    except OSError:
        return ""
    key = (path, st.st_mtime)
    if key not in _cache:
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = f.read()
        _cache[key] = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S).strip()
    return _cache[key]


def section(name, heading, level=None):
    """Une section Markdown (du titre qui contient `heading` jusqu'au titre suivant de même niveau)."""
    text = skill(name)
    lines = text.splitlines()
    start, lvl = None, 0
    for i, ln in enumerate(lines):
        m = re.match(r"^(#+)\s+(.*)", ln)
        if not m:
            continue
        if start is None and heading.lower() in m.group(2).lower() and (level is None or len(m.group(1)) == level):
            start, lvl = i, len(m.group(1))
        elif start is not None and len(m.group(1)) <= lvl:
            return "\n".join(lines[start:i]).strip()
    return "\n".join(lines[start:]).strip() if start is not None else ""


def available():
    return bool(skill("greenlight-audit-skill.md") and skill("faceless-scripts-os-master.md"))


def files_used():
    return sorted(f for f in os.listdir(SKILLS_DIR) if f.endswith((".md", ".py"))) if os.path.isdir(SKILLS_DIR) else []


# ── Scanner d'origine (trailer-voice-scan.py) ──────────────────────────────

def _scanner():
    path = os.path.join(SKILLS_DIR, "trailer-voice-scan.py")
    if not os.path.isfile(path):
        return None
    key = ("scanner", os.stat(path).st_mtime)
    if key not in _cache:
        spec = importlib.util.spec_from_file_location("fos_trailer_voice_scan", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _cache[key] = mod
    return _cache[key]


_MECH = [
    (re.compile("—"), "em dash"),
    (re.compile("–"), "en dash"),
    (re.compile(r"(?<=\w)--(?=\s|\w)|\s--\s"), "double hyphen standing in for a dash"),
    (re.compile("[‘’“”]"), "curly quote"),
    (re.compile("…"), "ellipsis character"),
    (re.compile(r"(?i)\b(i hope this helps|would you like me to|as of my last update|while details are limited)\b"),
     "chatbot artifact"),
]


def scan(parts):
    """Scanner FacelessOS sur [(heading, text)] → {"hard", "flags", "floor", "echo", "mech"} (listes de str)."""
    mod = _scanner()
    body = "\n\n".join(t.strip() for _, t in parts if t.strip())
    out = {"hard": [], "flags": [], "floor": [], "echo": [], "mech": []}
    if mod:
        for para in mod.spoken_paras(body):
            for rx, name in mod.TELLS:
                for m in re.finditer(rx, para):
                    ctx = para[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")
                    (out["hard"] if name.startswith("HARD-BAN") else out["flags"]).append(f"[{name}] ...{ctx}...")
            shorts, total = mod.short_sents(para)
            if len(shorts) >= 2:
                out["flags"].append(f"[staccato x{len(shorts)}/{total}] " + " | ".join(f'"{s}"' for s in shorts[:4])
                                    + f"  << {para[:70]}...")
        out["floor"] = [h.strip() for h in mod.antithesis_floor(body)]
        out["echo"] = [h.strip() for h in mod.echo_check(body)]
    for rx, name in _MECH:
        for m in rx.finditer(body):
            ctx = body[max(0, m.start() - 30):m.end() + 30].replace("\n", " ")
            out["mech"].append(f"[{name}] ...{ctx}...")
    return out


def scan_report(sc):
    """Rapport texte du scanner, au format du script d'origine."""
    lines = []
    for key, title in (("hard", "HARD-BAN (fix on sight, no adjudication)"), ("mech", "MECHANICAL SWEEP (delete on sight)"),
                       ("flags", "SHAPE FLAGS (judge each by the D1 shape test against the anchor)"),
                       ("floor", "ANTITHESIS/REFRAME FLOOR (the D7 ledger must list at least this many)"),
                       ("echo", "ECHO CHECK (H18)")):
        items = sc.get(key) or []
        lines.append(f"-- {title}: {len(items)}")
        lines += ["  " + x for x in items[:14]]
    return "\n".join(lines)


def mech_fix(text):
    """Balayage mécanique sans jugement (humanizer : « find one, delete it »)."""
    t = text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    t = t.replace("…", "...").replace(" ", " ")
    t = re.sub(r"\s*[—–]\s*", ", ", t)          # tiret → virgule (les cas délicats passent par l'audit)
    t = re.sub(r"(?<=\w)\s*--\s*(?=\w)", ", ", t)
    t = re.sub(r",\s*([.!?])", r"\1", t)
    t = re.sub(r",\s*,", ",", t)
    return t


def hard_ban_hits(text):
    mod = _scanner()
    if not mod:
        return []
    return [name for rx, name in mod.HARD_BAN if rx.search(text)]


# ── Références (vidéo modèle de la niche) ──────────────────────────────────

def bundled_reference(video_id):
    """Transcription fournie avec l'app pour une vidéo de référence (YouTube bloque parfois)."""
    path = os.path.join(REFS_DIR, f"{video_id}.txt")
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def anchor(reference_text, words=230, extra=170):
    """Échantillon parlé VERBATIM (voice anchoring) : l'ouverture (~60-90 s) + un passage avec dialogue."""
    blocks = [b for b in re.split(r"\n\s*---[^\n]*---\s*\n|\A---[^\n]*---\s*\n", "\n" + (reference_text or ""))
              if b.strip()]
    if not blocks:
        return ""
    ref = blocks[0].strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", ref) if p.strip()]
    if len(paras) < 3:  # transcription d'un seul bloc : découpe en phrases
        sents = re.split(r"(?<=[.!?])\s+", ref)
        paras = [" ".join(sents[i:i + 4]) for i in range(0, len(sents), 4)]

    def take(ps, limit):
        out, n = [], 0
        for p in ps:
            out.append(p)
            n += len(p.split())
            if n >= limit:
                break
        return "\n\n".join(out)
    opening = take(paras, words)
    used = opening.count("\n\n") + 1
    rest = paras[used:]
    mid = [i for i, p in enumerate(rest) if '"' in p and i >= len(rest) // 4]
    second = take(rest[mid[0]:], extra) if mid else take(rest[len(rest) // 2:], extra)
    return opening + ("\n\n[...]\n\n" + second if second else "")


def text_stats(text):
    """Rythme mesuré d'un texte parlé (pour l'analyse de référence)."""
    body = re.sub(r"^---.*?---\s*$", "", text or "", flags=re.M)
    sents = [s for s in re.split(r"(?<=[.!?])\s+", body.replace('"', "")) if s.strip()]
    lens = [len(s.split()) for s in sents] or [0]
    n = len(lens)
    return {"words": len(body.split()), "sentences": n, "avg": round(sum(lens) / max(1, n), 1),
            "short_pct": round(100 * sum(1 for x in lens if x <= 4) / max(1, n)),
            "long_pct": round(100 * sum(1 for x in lens if x >= 25) / max(1, n)),
            "dialogue_lines": len(re.findall(r'"[^"\n]{2,}"', body))}
