"""Récupère la transcription d'une vidéo YouTube (« Video context » de TubeGen)."""
import asyncio
import re


def video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})", url or "")
    if m:
        return m.group(1)
    return url if re.fullmatch(r"[A-Za-z0-9_-]{11}", url or "") else None


def _fetch(vid: str) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    langs = ["en", "fr", "es", "de", "it", "pt"]
    try:
        tr = api.fetch(vid, languages=langs)
    except Exception:  # noqa: BLE001 — on prend n'importe quelle langue disponible
        listing = api.list(vid)
        tr = next(iter(listing)).fetch()
    text = " ".join(s.text.replace("\n", " ") for s in tr)
    return re.sub(r"\s+", " ", text).strip()


async def transcript(url: str) -> str:
    vid = video_id(url)
    if not vid:
        raise ValueError("URL YouTube invalide")
    return await asyncio.to_thread(_fetch, vid)


async def info(url: str) -> dict:
    """Titre et chaîne d'une vidéo (oEmbed, sans clé API)."""
    import httpx

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
        r = await c.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"})
        r.raise_for_status()
        d = r.json()
    return {"title": d.get("title", ""), "author": d.get("author_name", "")}


async def thumbnail(url: str, dst) -> bool:
    """Télécharge la miniature de la vidéo (meilleure qualité disponible)."""
    import httpx

    vid = video_id(url)
    if not vid:
        return False
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        for name in ("maxresdefault.jpg", "sddefault.jpg", "hqdefault.jpg"):
            r = await c.get(f"https://i.ytimg.com/vi/{vid}/{name}")
            if r.status_code == 200 and len(r.content) > 5000:
                from io import BytesIO

                from PIL import Image
                Image.open(BytesIO(r.content)).convert("RGB").save(dst)
                return True
    return False
