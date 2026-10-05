"""Dated public RSS signals, separate from verified facts and licensed media."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import html
import ipaddress
import json
import re
import socket
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from flask import jsonify, request, g
from studio.store import now, uid, Conflict
from studio.domain import date, fresh

DEFAULTS = {
    "mma_en": [("MMA News", "https://www.mmanews.com/feed/")],
    "football_en": [
        ("BBC Sport · Football", "https://feeds.bbci.co.uk/sport/football/rss.xml"),
        ("The Guardian · Football", "https://www.theguardian.com/football/rss"),
    ],
}


def initialize(store):
    with store.db() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS studio_news_config(channel_id INTEGER PRIMARY KEY,
              enabled INTEGER DEFAULT 0, interval_minutes INTEGER DEFAULT 60,
              last_run TEXT DEFAULT '', next_run TEXT DEFAULT '', revision INTEGER DEFAULT 1,
              FOREIGN KEY(channel_id) REFERENCES studio_channels(project_id));
            CREATE TABLE IF NOT EXISTS studio_news_feeds(id TEXT PRIMARY KEY,channel_id INTEGER NOT NULL,
              name TEXT NOT NULL,url TEXT NOT NULL,enabled INTEGER DEFAULT 1,revision INTEGER DEFAULT 1,
              last_checked TEXT DEFAULT '',last_success TEXT DEFAULT '',error TEXT DEFAULT '',
              UNIQUE(channel_id,url),FOREIGN KEY(channel_id) REFERENCES studio_channels(project_id));
            CREATE TABLE IF NOT EXISTS studio_news_items(id TEXT PRIMARY KEY,channel_id INTEGER NOT NULL,
              title TEXT NOT NULL,url TEXT NOT NULL,published TEXT NOT NULL,summary TEXT DEFAULT '',
              sources TEXT NOT NULL,story_key TEXT NOT NULL,status TEXT DEFAULT 'new',
              video_id TEXT DEFAULT '',revision INTEGER DEFAULT 1,seen_at TEXT NOT NULL,
              UNIQUE(channel_id,url),UNIQUE(channel_id,story_key),
              FOREIGN KEY(channel_id) REFERENCES studio_channels(project_id));
            CREATE TABLE IF NOT EXISTS studio_news_locks(channel_id INTEGER PRIMARY KEY,owner TEXT,expires TEXT);
            CREATE INDEX IF NOT EXISTS studio_news_date ON studio_news_items(channel_id,published);
        """)
        c.execute("BEGIN IMMEDIATE")
        for ch in store.channels():
            if ch["format"] != "news":
                continue
            added = c.execute(
                "INSERT OR IGNORE INTO studio_news_config(channel_id) VALUES(?)",
                (ch["id"],),
            ).rowcount
            if added:
                for name, url in DEFAULTS.get(ch["template_key"] or ch["key"], []):
                    c.execute(
                        "INSERT INTO studio_news_feeds(id,channel_id,name,url) VALUES(?,?,?,?)",
                        (uid(), ch["id"], name, url),
                    )
        c.execute("INSERT OR IGNORE INTO studio_schema VALUES(3,?)", (now(),))


def public_url(url, *, resolve=False):
    url = str(url).strip()
    parts = urllib.parse.urlsplit(url)
    try:
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.port not in (None, 443)
            or len(url) > 2000
        ):
            raise ValueError()
    except ValueError:
        raise ValueError(
            "Utilise l’adresse HTTPS publique d’un flux RSS, sans identifiant."
        )
    host = parts.hostname.lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Les adresses internes ne sont pas des sources d’actualité.")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        addresses = []
        if resolve:
            addresses = [
                ipaddress.ip_address(r[4][0])
                for r in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            ]
    if any(not a.is_global for a in addresses):
        raise ValueError("Les sources doivent être accessibles sur Internet public.")
    return urllib.parse.urlunsplit(
        ("https", parts.netloc.lower(), parts.path or "/", parts.query, "")
    )


def canonical(url):
    parts = urllib.parse.urlsplit(public_url(url))
    query = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parts.query)
        if not k.lower().startswith("utm_")
        and k.lower() not in {"fbclid", "gclid", "ref"}
    ]
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path.rstrip("/") or "/",
            urllib.parse.urlencode(sorted(query)),
            "",
        )
    )


def story_key(title):
    text = unicodedata.normalize("NFKD", title).casefold()
    text = " ".join(re.findall(r"[a-z0-9]+", text))
    return hashlib.sha256(text.encode()).hexdigest()


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl, resolve=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_feed(url):
    url = public_url(url, resolve=True)
    opener = urllib.request.build_opener(PublicRedirect())
    with opener.open(
        urllib.request.Request(
            url,
            headers={
                "User-Agent": "EdgerunnersStudio/1.0 (+RSS reader)",
                "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml",
            },
        ),
        timeout=12,
    ) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Ce flux dépasse la taille autorisée.")
    return parse_feed(raw)


def clean(text):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", text or "")).split())


def parse_feed(raw):
    # No entity expansion or external DTD processing, even in owner-provided feeds.
    if (
        b"<!DOCTYPE" in raw.replace(b"\x00", b"").upper()
        or b"<!ENTITY" in raw.replace(b"\x00", b"").upper()
    ):
        raise ValueError("Ce flux contient une déclaration XML non prise en charge.")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise ValueError("Cette adresse ne renvoie pas un flux RSS ou Atom valide.")
    atom = "{http://www.w3.org/2005/Atom}"
    entries = root.findall("./channel/item") or root.findall(atom + "entry")
    if root.tag.split("}")[-1] not in {"rss", "feed", "RDF"}:
        raise ValueError("Cette adresse ne renvoie pas un flux RSS ou Atom.")
    rows = []
    for e in entries[:60]:
        title = clean(e.findtext("title") or e.findtext(atom + "title"))[:300]
        url = e.findtext("link")
        if not url:
            link = next(
                (
                    x
                    for x in e.findall(atom + "link")
                    if x.get("rel", "alternate") == "alternate"
                ),
                None,
            )
            url = link.get("href", "") if link is not None else ""
        published = (
            e.findtext("pubDate")
            or e.findtext(atom + "published")
            or e.findtext(atom + "updated")
        )
        when = date(published)
        if not when:
            try:
                when = parsedate_to_datetime(published)
            except (ValueError, TypeError, IndexError):
                continue
        if not when.tzinfo or not title or not url:
            continue
        try:
            url = canonical(url)
        except ValueError:
            continue
        rows.append(
            {
                "title": title,
                "url": url,
                "published": when.astimezone(timezone.utc).isoformat(),
                "summary": clean(
                    e.findtext("description")
                    or e.findtext(atom + "summary")
                    or e.findtext(atom + "content")
                )[:1200],
            }
        )
    return rows


def scan(store, cid):
    ch = store.channel(cid)
    if not ch or ch["format"] != "news":
        raise ValueError("Le radar concerne les chaînes d’actualité.")
    if store.settings()["paused"] or ch["paused"]:
        raise ValueError("Le radar attend la reprise du studio ou de cette chaîne.")
    feeds = store.rows(
        "SELECT * FROM studio_news_feeds WHERE channel_id=? AND enabled=1", (cid,)
    )
    if not feeds:
        raise ValueError("Ajoute ou active au moins un flux dans les sources du radar.")
    owner = uid()
    with store.db() as c:
        c.execute("BEGIN IMMEDIATE")
        lock = c.execute(
            "SELECT * FROM studio_news_locks WHERE channel_id=?", (cid,)
        ).fetchone()
        if lock and lock["expires"] > now():
            raise Conflict(
                "Une recherche est déjà en cours sur cette chaîne. Son résultat apparaîtra ici."
            )
        c.execute(
            "INSERT OR REPLACE INTO studio_news_locks VALUES(?,?,?)",
            (
                cid,
                owner,
                (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
            ),
        )

    def one(feed):
        try:
            return feed, fetch_feed(feed["url"]), ""
        except Exception as e:
            # Do not display URLs, authentication headers or arbitrary remote response bodies.
            text = (
                str(e)
                if isinstance(e, ValueError)
                else "Source indisponible. Le prochain passage réessaiera."
            )
            return feed, [], text[:240]

    added = 0
    succeeded = 0
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(one, feeds))
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            known_urls = {}
            known_titles = {}
            for video in c.execute(
                "SELECT id,title,sources FROM studio_videos WHERE channel_id=?", (cid,)
            ):
                known_titles[story_key(video["title"])] = video["id"]
                for source in json.loads(video["sources"]):
                    try:
                        known_urls[canonical(source.get("url", ""))] = video["id"]
                    except ValueError:
                        pass
            # Configuration could change while the network request was in progress.
            for feed, rows, error in results:
                current = c.execute(
                    "SELECT enabled,revision FROM studio_news_feeds WHERE id=?",
                    (feed["id"],),
                ).fetchone()
                if (
                    not current
                    or not current["enabled"]
                    or current["revision"] != feed["revision"]
                ):
                    continue
                c.execute(
                    "UPDATE studio_news_feeds SET last_checked=?,last_success=CASE WHEN ?='' THEN ? ELSE last_success END,error=? WHERE id=?",
                    (now(), error, now(), error, feed["id"]),
                )
                succeeded += not bool(error)
                for item in rows:
                    if not fresh({"event_at": item["published"]}, ch):
                        continue
                    source = {
                        "id": uid(),
                        "name": feed["name"],
                        "url": item["url"],
                        "published": item["published"],
                    }
                    existing = c.execute(
                        "SELECT * FROM studio_news_items WHERE channel_id=? AND (url=? OR story_key=?)",
                        (cid, item["url"], story_key(item["title"])),
                    ).fetchone()
                    if existing:
                        sources = json.loads(existing["sources"])
                        if not any(s["url"] == item["url"] for s in sources):
                            sources.append(source)
                            c.execute(
                                "UPDATE studio_news_items SET sources=?,revision=revision+1 WHERE id=?",
                                (
                                    json.dumps(sources, ensure_ascii=False),
                                    existing["id"],
                                ),
                            )
                        continue
                    c.execute(
                        "INSERT INTO studio_news_items(id,channel_id,title,url,published,summary,sources,story_key,seen_at,status,video_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            uid(),
                            cid,
                            item["title"],
                            item["url"],
                            item["published"],
                            item["summary"],
                            json.dumps([source], ensure_ascii=False),
                            story_key(item["title"]),
                            now(),
                            (
                                "used"
                                if item["url"] in known_urls
                                or story_key(item["title"]) in known_titles
                                else "new"
                            ),
                            known_urls.get(item["url"])
                            or known_titles.get(story_key(item["title"]))
                            or "",
                        ),
                    )
                    added += 1
            cfg = c.execute(
                "SELECT interval_minutes FROM studio_news_config WHERE channel_id=?",
                (cid,),
            ).fetchone()
            c.execute(
                "UPDATE studio_news_config SET last_run=?,next_run=? WHERE channel_id=?",
                (
                    now(),
                    (
                        datetime.now(timezone.utc)
                        + timedelta(minutes=cfg["interval_minutes"])
                    ).isoformat(),
                    cid,
                ),
            )
        store.log(
            "Radar",
            "news",
            f"{ch['name']} : {added} nouvelles infos · {succeeded}/{len(feeds)} sources accessibles",
        )
        return {
            "added": added,
            "successful_feeds": succeeded,
            "failed_feeds": len(feeds) - succeeded,
        }
    finally:
        with store.db() as c:
            c.execute(
                "DELETE FROM studio_news_locks WHERE channel_id=? AND owner=?",
                (cid, owner),
            )


def tick(store):
    if store.settings()["paused"]:
        return
    for cfg in store.rows(
        "SELECT * FROM studio_news_config WHERE enabled=1 AND next_run<=?", (now(),)
    ):
        try:
            scan(store, cfg["channel_id"])
        except (ValueError, Conflict):
            # Pause and unavailable settings remain visible; don't retry every three seconds.
            with store.db() as c:
                c.execute(
                    "UPDATE studio_news_config SET next_run=? WHERE channel_id=?",
                    (
                        (
                            datetime.now(timezone.utc)
                            + timedelta(minutes=cfg["interval_minutes"])
                        ).isoformat(),
                        cfg["channel_id"],
                    ),
                )


def prepare(store, item_id, revision, actor):
    with store.db() as c:
        c.execute("BEGIN IMMEDIATE")
        item = c.execute(
            "SELECT * FROM studio_news_items WHERE id=?", (item_id,)
        ).fetchone()
        if not item:
            raise ValueError("Cette information n’existe plus.")
        if item["video_id"]:
            return item["video_id"]
        if item["revision"] != revision:
            raise Conflict("Cette information a changé. Actualise le radar.")
        ch = store.channel(item["channel_id"])
        if not fresh({"event_at": item["published"]}, ch):
            raise ValueError(
                "Cette information a dépassé la fraîcheur autorisée sur la chaîne."
            )
        vid = uid()
        # RSS titles/summaries are research signals; never place them into the verified-facts field.
        c.execute(
            "INSERT INTO studio_videos(id,channel_id,title,status,minutes,sources,event_at,cost_cap,created_at,updated_at) VALUES(?,?,?,'research',5,?,?,?,?,?)",
            (
                vid,
                ch["id"],
                item["title"][:200],
                item["sources"],
                item["published"],
                ch["budget"],
                now(),
                now(),
            ),
        )
        c.execute(
            "UPDATE studio_news_items SET status='used',video_id=?,revision=revision+1 WHERE id=?",
            (vid, item_id),
        )
        c.execute(
            "INSERT INTO studio_activity(actor,action,message,created_at) VALUES(?,'research',?,?)",
            (actor, "Recherche préparée : " + item["title"], now()),
        )
        return vid


def register(app, store, owner):
    initialize(store)

    @app.get("/api/studio/news")
    def news_workspace():
        items = store.rows(
            "SELECT * FROM studio_news_items ORDER BY published DESC LIMIT 400"
        )
        for item in items:
            item["sources"] = json.loads(item["sources"])
            item["fresh"] = fresh(
                {"event_at": item["published"]}, store.channel(item["channel_id"])
            )
        return jsonify(
            items=items,
            feeds=store.rows("SELECT * FROM studio_news_feeds ORDER BY name"),
            configs=store.rows("SELECT * FROM studio_news_config"),
        )

    @app.post("/api/studio/news/scan")
    def news_refresh():
        b = request.get_json() or {}
        return jsonify(scan(store, int(b.get("channel_id", 0))))

    @app.post("/api/studio/news/feeds")
    def news_add_feed():
        owner()
        b = request.get_json() or {}
        cid = int(b.get("channel_id", 0))
        ch = store.channel(cid)
        name = str(b.get("name", "")).strip()
        if not ch or ch["format"] != "news" or not 2 <= len(name) <= 100:
            raise ValueError("Choisis une chaîne d’actualité et un nom de source.")
        url = public_url(b.get("url", ""))
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            if (
                c.execute(
                    "SELECT count(*) FROM studio_news_feeds WHERE channel_id=?", (cid,)
                ).fetchone()[0]
                >= 6
            ):
                raise ValueError(
                    "Six flux maximum par chaîne. Supprime une source inutilisée."
                )
            fid = uid()
            c.execute(
                "INSERT INTO studio_news_feeds(id,channel_id,name,url) VALUES(?,?,?,?)",
                (fid, cid, name, url),
            )
        return jsonify(id=fid), 201

    @app.patch("/api/studio/news/feeds/<fid>")
    def news_edit_feed(fid):
        owner()
        b = request.get_json() or {}
        with store.db() as c:
            cur = c.execute(
                "UPDATE studio_news_feeds SET enabled=?,revision=revision+1 WHERE id=? AND revision=?",
                (int(bool(b.get("enabled"))), fid, b.get("revision")),
            )
            if not cur.rowcount:
                raise Conflict("La source a changé. Actualise le radar.")
        return jsonify(ok=True)

    @app.delete("/api/studio/news/feeds/<fid>")
    def news_delete_feed(fid):
        owner()
        b = request.get_json() or {}
        with store.db() as c:
            if not c.execute(
                "DELETE FROM studio_news_feeds WHERE id=? AND revision=?",
                (fid, b.get("revision")),
            ).rowcount:
                raise Conflict("La source a changé. Actualise le radar.")
        return jsonify(ok=True)

    @app.patch("/api/studio/news/config/<int:cid>")
    def news_config(cid):
        owner()
        b = request.get_json() or {}
        minutes = int(b.get("interval_minutes", 60))
        if not 30 <= minutes <= 1440:
            raise ValueError("Choisis un passage entre 30 minutes et 24 heures.")
        if app.config["PREVIEW"] and b.get("enabled"):
            raise ValueError(
                "La collecte régulière sera disponible lorsque le moteur permanent sera actif. Le bouton Actualiser fonctionne dans l’aperçu."
            )
        with store.db() as c:
            if not c.execute(
                "UPDATE studio_news_config SET enabled=?,interval_minutes=?,next_run='',revision=revision+1 WHERE channel_id=? AND revision=?",
                (int(bool(b.get("enabled"))), minutes, cid, b.get("revision")),
            ).rowcount:
                raise Conflict("Les réglages du radar ont changé.")
        return jsonify(ok=True)

    @app.post("/api/studio/news/items/<iid>/prepare")
    def news_create_video(iid):
        b = request.get_json() or {}
        return jsonify(video_id=prepare(store, iid, b.get("revision"), g.user["name"]))

    @app.patch("/api/studio/news/items/<iid>")
    def news_dismiss(iid):
        b = request.get_json() or {}
        if b.get("status") not in {"new", "dismissed"}:
            raise ValueError("Statut du radar invalide.")
        with store.db() as c:
            if not c.execute(
                "UPDATE studio_news_items SET status=?,revision=revision+1 WHERE id=? AND revision=? AND video_id=''",
                (b["status"], iid, b.get("revision")),
            ).rowcount:
                raise Conflict("Cette info est déjà utilisée ou vient de changer.")
        return jsonify(ok=True)
