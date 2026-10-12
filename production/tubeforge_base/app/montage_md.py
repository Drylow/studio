"""MONTAGE.md : tout le texte et toutes les décisions de montage d'une vidéo, au même endroit."""
from . import store
from .util import fmt_srt_time


def _tc(t: float) -> str:
    return fmt_srt_time(t)[3:11].replace(",", ".")  # mm:ss.cc


def write(p: dict) -> str:
    pdir = store.project_dir(p["id"])
    out = pdir / "render" / "MONTAGE.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    s = p.get("short") or {}
    vo = p.get("voiceover") or {}
    lines = [f"# {p.get('title', 'Sans titre')}", ""]
    lines += [f"- **Format** : {'Short vertical (TikTok / Reels / Shorts)' if p.get('format') == 'short' else 'Vidéo longue'}"
              f" — {p['settings']['visuals'].get('aspect', '16:9')}",
              f"- **Durée** : {_tc(vo.get('duration', 0))} — {len(p.get('scenes', []))} scènes",
              f"- **Langue** : {p['settings'].get('language', 'English')}",
              f"- **Voix** : {vo.get('provider', '?')} — {vo.get('voice', '')}"]
    if p.get("resolve"):
        lines.append(f"- **DaVinci Resolve** : projet « {p['resolve']['project']} », timeline « {p['resolve']['timeline']} »")
    lines.append("")
    if s.get("kind"):
        lines += [f"**Type** : {'Short PUB pour la vidéo YouTube « ' + s.get('parent_title', '') + ' »' if s['kind'] == 'promo' else 'TikTok autonome'}", ""]
    if s.get("kind") == "promo" and s.get("cta"):
        c = s["cta"]
        lines += ["## Appel à l'action (fin)", "",
                  f"- Voix : « {c.get('spoken', '')} »",
                  f"- Écran de fin à partir de {_tc(s.get('endcard_start') or 0)} : **{c.get('line1', '')}** / "
                  f"**{c.get('line2', '')}** / {c.get('line3', '')} + miniature de la vidéo YouTube", ""]
    if s.get("hook_text"):
        lines += ["## Accroche (à l'écran)", "", f"**{s['hook_text']}** — mot surligné : *{s.get('hook_highlight', '')}* "
                  f"— de 00:00 à {_tc(s.get('hook_duration', 2.5))} (claque + secousse + flash, whoosh + impact)", ""]
    if s.get("caption") or s.get("hashtags"):
        lines += ["## Publication TikTok", "", s.get("caption", ""), "",
                  " ".join(f"#{h}" for h in s.get("hashtags", [])), ""]
    lines += ["## Script (voix off)", "", p.get("script", ""), ""]
    lines += ["## Scènes", "", "| # | Début | Fin | Texte | Image | Prompt |", "|---|---|---|---|---|---|"]
    for sc in p.get("scenes", []):
        prompt = (sc.get("prompt") or "").replace("|", "/").replace("\n", " ")
        text = sc["text"].replace("|", "/")
        lines.append(f"| {sc['id']} | {_tc(sc['start'])} | {_tc(sc['end'])} | {text} | `{sc.get('image') or '—'}` | "
                     f"{prompt[:220]} |")
    lines.append("")
    if s.get("sfx"):
        lines += ["## Bruitages", "", "| Temps | Son | Volume |", "|---|---|---|"]
        for e in s["sfx"]:
            lines.append(f"| {_tc(e['t'])} | {e['kind']} | {round(e['gain'] * 100)} % |")
        lines.append("")
    words = store.load_words(p["id"])
    if words:
        from .steps.render import caption_groups
        lines += ["## Sous-titres minutés", "", "| Début | Fin | Texte |", "|---|---|---|"]
        for g in caption_groups(words):
            lines.append(f"| {_tc(g['start'])} | {_tc(g['end'])} | {g['text'].replace('|', '/')} |")
        lines.append("")
    chars = [c for c in p.get("characters", []) if c.get("enabled", True)]
    if chars:
        lines += ["## Personnages", ""] + [f"- **{c['name']}** — {c.get('description', '')}" for c in chars] + [""]
    lines += ["## Fichiers", "", "- Vidéo : `render/final.mp4`" + (" (et `render/resolve_final.mp4` rendue par Resolve)"
                                                                    if p.get("resolve") else ""),
              "- Sous-titres : `render/subtitles.srt`", "- Voix : `voice.mp3`",
              "- Éléments de montage Resolve : `render/resolve/` (scènes, sous-titres, accroche, bruitages)", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out)
