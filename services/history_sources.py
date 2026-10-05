"""Format Histoire : vraies images d'archive (objets, manuscrits, œuvres) avant de recourir à l'IA.

Sources, sans clé :
  - The Metropolitan Museum of Art (Open Access, domaine public) ;
  - Wikimedia Commons (licences libres : le crédit auteur + licence est affiché sous l'image).
Les résultats bruts des moteurs sont peu fiables (« casque normand » → un vase étrusque) : l'IA texte
choisit le bon candidat, ou aucun. Toute erreur réseau → None, et le pipeline génère l'image.
"""
import html
import json
import re
import urllib.parse
import urllib.request

UA = "EdgerunnersStudio/1.0 (history documentary tool; local use)"


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _json(url, timeout=20):
    return json.loads(_get(url, timeout).decode("utf-8"))


def _strip(s):
    return re.sub(r"<[^>]+>", "", html.unescape(s or "")).strip()


def met_candidates(query, limit=8):
    out = []
    q = urllib.parse.urlencode({"q": query, "hasImages": "true"})
    ids = (_json(f"https://collectionapi.metmuseum.org/public/collection/v1.1/search?{q}").get("objectIDs") or [])[:limit * 2]
    for oid in ids:
        try:
            o = _json(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}")
        except Exception:  # noqa: BLE001
            continue
        img = o.get("primaryImage") or o.get("primaryImageSmall")
        if not (o.get("isPublicDomain") and img):
            continue
        out.append({"title": o.get("title", ""), "date": o.get("objectDate", ""), "culture": o.get("culture") or o.get("period", ""),
                    "source": "The Met", "url": o.get("primaryImageSmall") or img,
                    "credit": "The Metropolitan Museum of Art · Public domain"})
        if len(out) >= limit:
            break
    return out


def commons_candidates(query, limit=8):
    q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrsearch": query,
                                "gsrnamespace": 6, "gsrlimit": limit, "prop": "imageinfo",
                                "iiprop": "url|extmetadata", "iiurlwidth": 1600})
    data = _json(f"https://commons.wikimedia.org/w/api.php?{q}")
    out = []
    for p in (data.get("query") or {}).get("pages", {}).values():
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        url = info.get("thumburl") or info.get("url") or ""
        if not re.search(r"\.(jpe?g|png)$", url.split("?")[0], re.I):
            continue
        lic = _strip((meta.get("LicenseShortName") or {}).get("value"))
        artist = _strip((meta.get("Artist") or {}).get("value"))[:60]
        out.append({"title": _strip((meta.get("ObjectName") or {}).get("value")) or p.get("title", "").replace("File:", ""),
                    "date": _strip((meta.get("DateTimeOriginal") or {}).get("value"))[:40], "culture": "",
                    "source": "Wikimedia Commons", "url": url,
                    "credit": " · ".join(x for x in ("Wikimedia Commons", artist, lic) if x)})
    return out


def find_real_image(beat, pick):
    """(octets, crédit) d'une vraie image pour une carte d'archive, ou None.

    pick(candidates, beat) → index retenu (voir history_ai.pick_archive)."""
    query = (beat.get("search") or beat.get("title") or "").strip()
    if not query:
        return None
    cands = []
    for fn in (met_candidates, commons_candidates):
        try:
            cands += fn(query)
        except Exception:  # noqa: BLE001 — source injoignable / limitée : on continue avec l'autre
            continue
    if not cands:
        return None
    i = pick(cands, beat)
    if i < 0:
        return None
    try:
        return _get(cands[i]["url"], timeout=60), cands[i]["credit"]
    except Exception:  # noqa: BLE001
        return None
