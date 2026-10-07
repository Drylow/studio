"""Wikimedia Commons portraits with the licence facts needed to reuse them.

Only files whose licence allows commercial reuse and modification are returned,
with author, licence link and file page recorded as proof (services.news_rights).
"""

import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://commons.wikimedia.org/w/api.php"
AGENT = "EdgerunnersStudio/1.0 (https://edgerunners.fr/about)"

# Commons short names → the licence names checked by services.news_rights.
LICENSES = {
    "cc0": "CC0",
    "cc-zero": "CC0",
    "public domain": "Public domain",
    "pd": "Public domain",
    "cc by 2.0": "CC BY 2.0",
    "cc by 2.5": "CC BY 2.5",
    "cc by 3.0": "CC BY 3.0",
    "cc by 4.0": "CC BY 4.0",
    "cc by-sa 2.0": "CC BY-SA 2.0",
    "cc by-sa 2.5": "CC BY-SA 2.5",
    "cc by-sa 3.0": "CC BY-SA 3.0",
    "cc by-sa 4.0": "CC BY-SA 4.0",
}


def _get(params, timeout=20):
    url = API + "?" + urllib.parse.urlencode(dict(params, format="json"))
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(4_000_000))


def text(value):
    """Commons metadata is HTML; keep readable text only."""
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def licence(meta):
    short = text((meta.get("LicenseShortName") or {}).get("value")).lower()
    name = LICENSES.get(short)
    if not name:
        return None
    url = text((meta.get("LicenseUrl") or {}).get("value"))
    if url.startswith("//"):
        url = "https:" + url
    url = url.replace("http://", "https://").rstrip("/")
    if name == "Public domain":
        url = ""
    elif name == "CC0":
        url = "https://creativecommons.org/publicdomain/zero/1.0"
    return name, url


def portraits(name, *, limit=12, get=_get):
    """Photos whose title names this person, best first; each with its rights."""
    words = [w.lower() for w in re.findall(r"[\w'-]+", name) if len(w) > 1]
    data = get(
        {
            "action": "query",
            "generator": "search",
            "gsrsearch": f'"{name}" filetype:bitmap',
            "gsrnamespace": 6,
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime",
            "iiurlwidth": 1600,
        }
    )
    found = []
    for page in (data.get("query") or {}).get("pages", {}).values():
        title = page.get("title", "")
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = licence(meta)
        if (
            not lic
            or info.get("mime") not in {"image/jpeg", "image/png", "image/webp"}
            or min(info.get("width", 0), info.get("height", 0)) < 500
            or not all(w in title.lower() for w in words)
        ):
            continue
        author = text((meta.get("Artist") or {}).get("value")) or text(
            (meta.get("Credit") or {}).get("value")
        )
        if not author:
            continue
        page_url = info.get("descriptionurl") or (
            "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
        )
        rights = {
            "license": lic[0],
            "license_url": lic[1],
            "author": author[:300],
            "evidence_url": page_url,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "source": "Wikimedia Commons",
        }
        if "BY-SA" in lic[0]:
            rights["adaptation_license"] = lic[0]
        found.append(
            {
                "name": name,
                "title": title,
                "url": info.get("thumburl") or info.get("url"),
                "width": info.get("width", 0),
                "height": info.get("height", 0),
                "credit": f"Photo: {author[:120]} / Wikimedia Commons ({lic[0]})",
                "rights": rights,
            }
        )
    # Larger, portrait-like photos first; crowded event photos tend to be wide.
    found.sort(key=lambda p: (p["height"] >= p["width"] * 0.8, p["height"]), reverse=True)
    return found


def download(url, dest, *, limit=15_000_000):
    host = urllib.parse.urlsplit(url).hostname or ""
    if not host.endswith("wikimedia.org"):
        raise ValueError("Image hors de Wikimedia Commons refusée.")
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read(limit + 1)
    if len(body) > limit:
        raise ValueError("Image trop lourde.")
    with open(dest, "wb") as f:
        f.write(body)
    return dest
