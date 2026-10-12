"""Chaînes de publication (un compte TikTok = une chaîne).

Chaque chaîne fixe la langue, la voix, le type de shorts (pub vers YouTube ou TikTok autonome), les
heures de publication, les hashtags de base et le projet DaVinci Resolve où ses shorts sont montés.
"""
import copy
import uuid

from . import config, store
from .util import read_json, slugify, write_json

FILE = config.DATA / "channels.json"

DEFAULT_CHANNEL = {
    "id": "",
    "name": "",
    "emoji": "📱",
    "language": "French",
    "style_id": "",
    "kind": "standalone",          # "standalone" (TikTok autonome) | "promo" (clipping → vidéo YouTube)
    "voice": {},                   # surcharge des réglages voix du style (ex. {"local_voice": "Narrateur FR - Remy.wav"})
    "posts_per_day": 2,
    "post_times": ["12:30", "19:00"],
    "start_date": "",              # premier jour du planning (AAAA-MM-JJ, vide = demain)
    "hashtags": [],                # ajoutés à chaque légende
    "handle": "",                  # @compte, rappelé dans la légende des shorts pub
    "cta": {"spoken": "", "line1": "", "line2": "", "line3": ""},
    "auto_resolve": True,          # monter chaque short fini dans DaVinci Resolve (projet de la chaîne)
}

SEED = []


def _normalize(ch: dict) -> dict:
    out = copy.deepcopy(DEFAULT_CHANNEL)
    for k, v in ch.items():
        if k == "cta" and isinstance(v, dict):
            out["cta"].update(v)
        else:
            out[k] = v
    out["posts_per_day"] = max(1, min(6, int(out.get("posts_per_day") or 1)))
    times = [t.strip() for t in out.get("post_times") or [] if str(t).strip()]
    out["post_times"] = sorted(times)[: out["posts_per_day"]] or ["18:00"]
    out["hashtags"] = [h.strip().lstrip("#") for h in out.get("hashtags") or [] if str(h).strip()]
    if not out.get("style_id") or not store.get_style(out["style_id"]):
        out["style_id"] = store.list_styles()[0]["id"]
    return out


def list_channels() -> list[dict]:
    data = read_json(FILE, None)
    if data is None:
        data = [_normalize(c) for c in SEED]
        write_json(FILE, data)
    return [_normalize(c) for c in data]


def get(cid: str | None) -> dict | None:
    if not cid:
        return None
    key = str(cid).strip().lower()
    for c in list_channels():
        if key in (c["id"].lower(), c["name"].lower()):
            return c
    return None


def save(ch: dict) -> dict:
    chans = list_channels()
    ch = _normalize(ch)
    if not ch.get("id"):
        ch["id"] = f"{slugify(ch.get('name') or "channel", 30)}-{uuid.uuid4().hex[:4]}"
    chans = [c for c in chans if c["id"] != ch["id"]] + [ch]
    write_json(FILE, chans)
    return ch


def delete(cid: str) -> None:
    write_json(FILE, [c for c in list_channels() if c["id"] != cid])


def apply(p: dict, ch: dict) -> None:
    """Rattache un projet à une chaîne : langue, voix et appel à l'action de la chaîne."""
    p["channel_id"] = ch["id"]
    s = p["settings"]
    s["language"] = ch["language"]
    s.setdefault("voice", {}).update({k: v for k, v in (ch.get("voice") or {}).items() if v not in (None, "")})
    shorts = s.setdefault("shorts", {})
    for k in ("spoken", "line1", "line2", "line3"):
        if (ch["cta"].get(k) or "").strip():
            shorts[f"cta_{k}"] = ch["cta"][k].strip()


def projects_of(cid: str) -> list[dict]:
    return [p for p in store.list_projects(False) if p.get("channel_id") == cid and p.get("format") == "short"]


def used_hooks(cid: str | None, limit: int = 40) -> list[str]:
    """Accroches et titres déjà utilisés sur la chaîne (pour ne pas se répéter d'un short à l'autre)."""
    if not cid:
        return []
    ps = sorted(projects_of(cid), key=lambda p: p.get("created", 0), reverse=True)
    out = []
    for p in ps:
        for t in ((p.get("short") or {}).get("hook_text"), p.get("title")):
            if t and t not in out:
                out.append(t)
    return out[:limit]
