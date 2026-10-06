"""Public YouTube monitoring by handle, independent of publication OAuth.

Only Data API reads with one server-side API key. Period views are observed
counter differences, never fabricated Analytics reports or scraped private data.
"""
from datetime import datetime, timedelta, timezone
import csv
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from flask import jsonify, request, Response
from studio.store import now, uid

MAX_CHANNELS = 20
MAX_VIDEOS = 200
RETENTION_DAYS = 29
POLL_MINUTES = 60
COOLDOWN_MINUTES = 15
_threads = {}
_cleaned = {}


def initialize(store):
    with store.db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS studio_public_settings(id INTEGER PRIMARY KEY CHECK(id=1),
            api_key TEXT NOT NULL DEFAULT '',verified_at TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL DEFAULT 1);
        INSERT OR IGNORE INTO studio_public_settings(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS studio_public_channels(id TEXT PRIMARY KEY,youtube_id TEXT NOT NULL UNIQUE,
            handle TEXT NOT NULL,name TEXT NOT NULL,uploads TEXT NOT NULL DEFAULT '',
            studio_id INTEGER REFERENCES studio_channels(project_id),created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS studio_public_samples(track_id TEXT REFERENCES studio_public_channels(id) ON DELETE CASCADE,
            captured_at TEXT NOT NULL,views INTEGER,subscribers INTEGER,videos INTEGER,PRIMARY KEY(track_id,captured_at));
        CREATE TABLE IF NOT EXISTS studio_public_sync(track_id TEXT PRIMARY KEY REFERENCES studio_public_channels(id) ON DELETE CASCADE,
            last_attempt TEXT NOT NULL DEFAULT '',lease_until TEXT NOT NULL DEFAULT '',lease_id TEXT NOT NULL DEFAULT '',
            next_check TEXT NOT NULL DEFAULT '',error TEXT NOT NULL DEFAULT '',videos_at TEXT NOT NULL DEFAULT '',has_more INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS studio_public_videos(track_id TEXT REFERENCES studio_public_channels(id) ON DELETE CASCADE,
            video_id TEXT NOT NULL,title TEXT NOT NULL,published_at TEXT NOT NULL,duration INTEGER,
            views INTEGER,likes INTEGER,comments INTEGER,PRIMARY KEY(track_id,video_id));
        CREATE TABLE IF NOT EXISTS studio_public_video_samples(track_id TEXT REFERENCES studio_public_channels(id) ON DELETE CASCADE,
            video_id TEXT NOT NULL,captured_at TEXT NOT NULL,views INTEGER,PRIMARY KEY(track_id,video_id,captured_at));
        CREATE INDEX IF NOT EXISTS studio_public_video_retention ON studio_public_video_samples(captured_at);
        """)
        c.execute("INSERT OR IGNORE INTO studio_schema VALUES(9,?)", (now(),))


def moment(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def normalize_handle(value):
    if not isinstance(value, str) or len(value) > 300:
        raise ValueError("Renseigne le @pseudo ou le lien YouTube de la chaîne.")
    value = value.strip()
    if value.startswith(("youtube.com/", "www.youtube.com/", "m.youtube.com/")):
        value = "https://" + value
    if "://" in value:
        try:
            parsed = urllib.parse.urlsplit(value)
            valid = parsed.scheme == "https" and parsed.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"} and not parsed.port and not parsed.username and parsed.path.startswith("/@")
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Utilise un lien comme https://www.youtube.com/@NomDeChaine.")
        value = urllib.parse.unquote(parsed.path[1:].rstrip("/"))
    name = value.removeprefix("@")
    if not 1 <= len(name) <= 100 or any(not (unicodedata.category(char)[0] in "LNM" or char in "-_.·") for char in name):
        raise ValueError("Le @pseudo contient des caractères invalides.")
    return "@" + name


def api_key(store):
    setting = store.one("SELECT api_key FROM studio_public_settings WHERE id=1")
    return setting["api_key"] or next((os.getenv(k, "").strip() for k in ("YOUTUBE_API_KEY", "YOUTUBE_DATA_API_KEY", "GOOGLE_API_KEY") if os.getenv(k, "").strip()), "")


def api_read(key, resource, **parameters):
    if resource not in {"channels", "playlistItems", "videos"}:
        raise ValueError("Lecture YouTube non prise en charge.")
    if not key:
        raise ValueError("Configure la clé de lecture publique dans Statistiques → Configurer la clé.")
    url = "https://www.googleapis.com/youtube/v3/" + resource + "?" + urllib.parse.urlencode(parameters)
    req = urllib.request.Request(url, headers={"X-Goog-Api-Key": key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.load(response)
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ValueError("Réponse YouTube incomplète. Réessaie plus tard.")
        return data
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read(65536))
            details = body.get("error", {})
            reasons = {item.get("reason") for item in details.get("errors", []) + details.get("details", []) if isinstance(item, dict)}
        except (ValueError, AttributeError, TypeError):
            reasons = set()
        if reasons & {"API_KEY_INVALID", "keyInvalid", "API_KEY_SERVICE_BLOCKED", "API_KEY_HTTP_REFERRER_BLOCKED", "API_KEY_IP_ADDRESS_BLOCKED"}:
            message = "La clé API est invalide ou ses restrictions refusent ce serveur. Vérifie la clé de lecture publique."
        elif reasons & {"accessNotConfigured", "SERVICE_DISABLED"}:
            message = "Active YouTube Data API v3 dans le même projet Google que cette clé."
        elif reasons & {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "RATE_LIMIT_EXCEEDED"}:
            message = "Le quota de lecture YouTube est atteint. Les relevés conservés restent disponibles ; réessaie plus tard."
        else:
            message = "YouTube refuse cette lecture publique. Vérifie la clé API ou réessaie plus tard."
        raise ValueError(message) from None
    except (OSError, json.JSONDecodeError):
        raise ValueError("YouTube est temporairement injoignable. Les relevés conservés restent disponibles.") from None


def count(data, name):
    value = data.get(name)
    if isinstance(value, (str, int)) and not isinstance(value, bool) and re.fullmatch(r"\d{1,18}", str(value)):
        return int(value)
    return None


def channel_data(item):
    identity = item.get("id", "")
    if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", identity):
        raise ValueError("YouTube n’a pas confirmé l’identité de cette chaîne.")
    snippet = item.get("snippet", {})
    counters = item.get("statistics", {})
    return dict(youtube_id=identity, name=str(snippet.get("title", ""))[:200],
                handle=snippet.get("customUrl", "") if str(snippet.get("customUrl", "")).startswith("@") else "",
                uploads=item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", ""),
                views=count(counters, "viewCount"), videos=count(counters, "videoCount"),
                subscribers=None if counters.get("hiddenSubscriberCount") else count(counters, "subscriberCount"))


def lookup(key, handle):
    items = api_read(key, "channels", part="snippet,statistics,contentDetails", forHandle=normalize_handle(handle))["items"]
    if len(items) != 1:
        raise ValueError("Aucune chaîne trouvée avec ce @pseudo. Copie le @ affiché sur sa page YouTube.")
    try:
        return channel_data(items[0])
    except (AttributeError, TypeError, KeyError):
        raise ValueError("Réponse YouTube incomplète. Réessaie plus tard.") from None


def duration(value):
    m = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    return sum(int(v or 0) * factor for v, factor in zip(m.groups(), (86400, 3600, 60, 1))) if m else None


def video_data(key, channel):
    ids, page, more = [], "", False
    if not channel["uploads"]:
        return [], False
    for _ in range(MAX_VIDEOS // 50):
        params = dict(part="contentDetails", playlistId=channel["uploads"], maxResults=50)
        if page:
            params["pageToken"] = page
        data = api_read(key, "playlistItems", **params)
        for item in data["items"]:
            identity = item.get("contentDetails", {}).get("videoId", "")
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", identity) and identity not in ids:
                ids.append(identity)
        page = data.get("nextPageToken", "")
        more = bool(page)
        if not page:
            break
    videos = []
    for offset in range(0, len(ids), 50):
        for item in api_read(key, "videos", part="snippet,statistics,contentDetails,status", id=",".join(ids[offset:offset + 50]))["items"]:
            snippet, counters = item.get("snippet", {}), item.get("statistics", {})
            if item.get("id") not in ids or snippet.get("channelId") != channel["youtube_id"] or item.get("status", {}).get("privacyStatus") != "public":
                continue
            published = snippet.get("publishedAt", "")
            try:
                moment(published)
            except (ValueError, TypeError):
                continue
            videos.append(dict(video_id=item["id"], title=str(snippet.get("title", ""))[:300], published_at=published,
                               duration=duration(item.get("contentDetails", {}).get("duration")),
                               views=count(counters, "viewCount"), likes=count(counters, "likeCount"), comments=count(counters, "commentCount")))
    return videos, more


def tracked(store, identity):
    item = store.one("SELECT * FROM studio_public_channels WHERE id=?", (identity,))
    if not item:
        raise ValueError("Cette chaîne n’est plus suivie.")
    return item


def add(store, handle, studio_id=None):
    if studio_id is not None and (isinstance(studio_id, bool) or not isinstance(studio_id, int) or not store.channel(studio_id)):
        raise ValueError("Choisis une chaîne active du studio ou laisse l’association vide.")
    public = lookup(api_key(store), handle)
    if studio_id:
        expected = store.channel(studio_id)["yt_channel_id"]
        if expected and expected != public["youtube_id"]:
            raise ValueError("Ce @pseudo correspond à une autre chaîne YouTube que la chaîne du studio choisie.")
    identity, stamp = uid(), now()
    with store.db() as c:
        c.execute("BEGIN IMMEDIATE")
        existing = c.execute("SELECT id FROM studio_public_channels WHERE youtube_id=?", (public["youtube_id"],)).fetchone()
        if existing:
            return existing["id"], False
        if c.execute("SELECT count(*) FROM studio_public_channels").fetchone()[0] >= MAX_CHANNELS:
            raise ValueError("Le studio suit déjà 20 chaînes. Retire un suivi pour en ajouter un autre.")
        c.execute("INSERT INTO studio_public_channels VALUES(?,?,?,?,?,?,?,?)", (identity, public["youtube_id"], public["handle"] or normalize_handle(handle), public["name"], public["uploads"], studio_id, stamp, stamp))
        c.execute("INSERT INTO studio_public_samples VALUES(?,?,?,?,?)", (identity, stamp, public["views"], public["subscribers"], public["videos"]))
        c.execute("INSERT INTO studio_public_sync(track_id,next_check) VALUES(?,?)", (identity, stamp))
    return identity, True


def cleanup(store):
    clock = datetime.now(timezone.utc)
    key = str(store.path)
    if key in _cleaned and clock - _cleaned[key] < timedelta(hours=1):
        return
    cutoff = (clock - timedelta(days=RETENTION_DAYS)).isoformat()
    with store.db() as c:
        c.execute("DELETE FROM studio_public_samples WHERE captured_at<?", (cutoff,))
        c.execute("DELETE FROM studio_public_video_samples WHERE captured_at<?", (cutoff,))
        c.execute("DELETE FROM studio_public_videos WHERE track_id IN (SELECT track_id FROM studio_public_sync WHERE videos_at!='' AND videos_at<?)", (cutoff,))
        c.execute("UPDATE studio_public_channels SET name='' WHERE updated_at<?", (cutoff,))
    _cleaned[key] = clock


def sync(store, identity):
    key = api_key(store)
    if not key or store.web_app.config["PREVIEW"]:
        return
    stamp, lease = now(), uid()
    with store.db() as c:
        c.execute("BEGIN IMMEDIATE")
        record = c.execute("SELECT * FROM studio_public_channels WHERE id=?", (identity,)).fetchone()
        state = c.execute("SELECT * FROM studio_public_sync WHERE track_id=?", (identity,)).fetchone()
        if not record or not state or state["lease_until"] > stamp or state["next_check"] > stamp:
            return
        c.execute("UPDATE studio_public_sync SET last_attempt=?,lease_until=?,lease_id=? WHERE track_id=?", (stamp, (moment(stamp) + timedelta(minutes=3)).isoformat(), lease, identity))
        record = dict(record)
    error, public, videos, more = "", None, None, False
    try:
        data = api_read(key, "channels", part="snippet,statistics,contentDetails", id=record["youtube_id"])["items"]
        if len(data) != 1 or data[0].get("id") != record["youtube_id"]:
            raise ValueError("YouTube n’a pas retrouvé cette chaîne. Le suivi précédent reste disponible.")
        public = channel_data(data[0])
        try:
            videos, more = video_data(key, public)
        except ValueError:
            error = "Les compteurs de chaîne sont actualisés ; la liste des vidéos n’a pas pu être actualisée."
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        error = str(exc) if isinstance(exc, ValueError) else "Réponse YouTube incomplète. Réessaie plus tard."
    with store.db() as c:
        c.execute("BEGIN IMMEDIATE")
        active = c.execute("SELECT lease_id FROM studio_public_sync WHERE track_id=?", (identity,)).fetchone()
        if not active or active["lease_id"] != lease:
            return
        stamp = now()
        if public:
            c.execute("UPDATE studio_public_channels SET name=?,handle=?,uploads=?,updated_at=? WHERE id=?", (public["name"], public["handle"] or record["handle"], public["uploads"], stamp, identity))
            c.execute("INSERT INTO studio_public_samples VALUES(?,?,?,?,?)", (identity, stamp, public["views"], public["subscribers"], public["videos"]))
        if videos is not None:
            c.execute("DELETE FROM studio_public_videos WHERE track_id=?", (identity,))
            for video in videos:
                c.execute("INSERT INTO studio_public_videos VALUES(?,?,?,?,?,?,?,?)", (identity, video["video_id"], video["title"], video["published_at"], video["duration"], video["views"], video["likes"], video["comments"]))
                c.execute("INSERT INTO studio_public_video_samples VALUES(?,?,?,?)", (identity, video["video_id"], stamp, video["views"]))
            c.execute("UPDATE studio_public_sync SET videos_at=?,has_more=? WHERE track_id=?", (stamp, int(more), identity))
        c.execute("UPDATE studio_public_sync SET lease_until='',lease_id='',error=?,next_check=? WHERE track_id=?", (error, (moment(stamp) + timedelta(minutes=POLL_MINUTES)).isoformat(), identity))


def tick(store):
    if Path(store.web_app.config.get("DEVELOPMENT_MAINTENANCE_PATH", "/nonexistent")).exists():
        return
    cleanup(store)
    key = str(store.path)
    if store.web_app.config["PREVIEW"] or not api_key(store) or (_threads.get(key) and _threads[key].is_alive()):
        return
    due = store.one("SELECT track_id FROM studio_public_sync WHERE next_check<=? AND lease_until<=? ORDER BY next_check LIMIT 1", (now(), now()))
    if due:
        thread = threading.Thread(target=sync, args=(store, due["track_id"]), daemon=True, name="public-statistics")
        _threads[key] = thread
        thread.start()


def start_monitor(store):
    """Poll independently of long-running video jobs; restart with the deployed code."""
    if store.web_app.config["PREVIEW"]:
        return
    version = Path(__file__).resolve().parents[1] / "work/studio/runtime-revision"
    initial = version.read_text() if version.exists() else ""
    def monitor():
        stop = threading.Event()
        while not (version.exists() and version.read_text() != initial):
            try:
                tick(store)
            except (OSError, ValueError, sqlite3.Error):
                pass
            stop.wait(30)
    thread = threading.Thread(target=monitor, daemon=True, name="public-statistics-monitor")
    thread.start()


def range_hours():
    value = request.args.get("hours", "48")
    if value not in {"24", "48", "168", "336", "672"}:
        raise ValueError("Choisis 24 h, 48 h, 7, 14 ou 28 jours.")
    return int(value)


def report(store, record, hours):
    clock = datetime.now(timezone.utc)
    start = clock - timedelta(hours=hours)
    cutoff = (clock - timedelta(days=RETENTION_DAYS)).isoformat()
    samples = store.rows("SELECT captured_at,views,subscribers,videos FROM studio_public_samples WHERE track_id=? AND captured_at>=? ORDER BY captured_at", (record["id"], cutoff))
    state = store.one("SELECT * FROM studio_public_sync WHERE track_id=?", (record["id"],)) or {}
    last = samples[-1] if samples else None
    before = [row for row in samples if moment(row["captured_at"]) <= start]
    baseline = before[-1] if before else (samples[0] if samples else None)
    history = [row for row in samples if baseline and row["captured_at"] >= baseline["captured_at"]]
    def gain(metric):
        return last[metric] - baseline[metric] if len(history) > 1 and last[metric] is not None and baseline[metric] is not None else None
    studio = store.channel(record["studio_id"]) if record["studio_id"] else None
    return dict(id=record["id"],youtube_id=record["youtube_id"],handle=record["handle"],name=record["name"] or record["handle"],studio_id=record["studio_id"],
                responsible_id=studio["responsible_id"] if studio else None,accent=studio["accent"] if studio else "#43dbc8",
                totals={k:last[k] if last else None for k in ("views","subscribers","videos")},
                gain=gain("views"),subscriber_gain=gain("subscribers"),since=baseline["captured_at"] if baseline else None,
                updated_at=last["captured_at"] if last else None,partial=bool(baseline and moment(baseline["captured_at"])>start),
                stale=bool(last and clock-moment(last["captured_at"])>timedelta(minutes=POLL_MINUTES*2)),
                error=state.get("error", ""),refreshing=state.get("lease_until", "")>now(),queued=bool(state.get("next_check") and state["next_check"]<=now()),
                videos_at=state.get("videos_at", ""),has_more=bool(state.get("has_more")),history=chart_history(history))


def chart_history(history):
    step = max(1, (len(history) + 119) // 120)
    result = history[::step]
    if history and result[-1] != history[-1]:
        result.append(history[-1])
    return result


def videos_report(store, identity, hours):
    start = (datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat()
    videos = store.rows("""WITH baselines AS (SELECT v.*,
        COALESCE((SELECT s.captured_at FROM studio_public_video_samples s WHERE s.track_id=v.track_id AND s.video_id=v.video_id AND s.captured_at<=? ORDER BY s.captured_at DESC LIMIT 1),
            (SELECT s.captured_at FROM studio_public_video_samples s WHERE s.track_id=v.track_id AND s.video_id=v.video_id ORDER BY s.captured_at LIMIT 1)) AS since
        FROM studio_public_videos v WHERE v.track_id=?)
        SELECT b.*,(SELECT s.views FROM studio_public_video_samples s WHERE s.track_id=b.track_id AND s.video_id=b.video_id AND s.captured_at=b.since) AS baseline_views
        FROM baselines b ORDER BY b.published_at DESC""", (start,identity))
    state = store.one("SELECT videos_at FROM studio_public_sync WHERE track_id=?", (identity,)) or {}
    for video in videos:
        video["gain"] = video["views"]-video["baseline_views"] if video["views"] is not None and video["baseline_views"] is not None and video["since"]!=state.get("videos_at") else None
        video["partial"] = bool(video["since"] and video["since"]>start)
        video["published_in_period"] = moment(video["published_at"]) >= moment(start)
        video["engagement"] = round((video["likes"]+video["comments"])*100/video["views"],2) if video["views"] and video["likes"] is not None and video["comments"] is not None else None
        video.pop("baseline_views",None)
        video.pop("track_id",None)
    return videos


def register(app, store, owner):
    initialize(store)

    def body():
        data=request.get_json(silent=True)
        if not isinstance(data,dict):
            raise ValueError("Informations manquantes.")
        return data

    @app.get("/api/studio/statistics")
    def public_statistics():
        cleanup(store)
        hours=range_hours()
        records=[report(store,row,hours) for row in store.rows("SELECT * FROM studio_public_channels ORDER BY created_at")]
        setting=store.one("SELECT verified_at FROM studio_public_settings WHERE id=1")
        worker=store.one("SELECT heartbeat FROM studio_worker WHERE id=1")
        return jsonify(channels=records,hours=hours,configuration=dict(configured=bool(api_key(store)),verified_at=setting["verified_at"],poll_minutes=POLL_MINUTES,max_channels=MAX_CHANNELS,max_videos=MAX_VIDEOS,
            worker_online=bool(worker and worker["heartbeat"] and datetime.now(timezone.utc)-moment(worker["heartbeat"])<timedelta(minutes=2))))

    @app.post("/api/studio/statistics/key")
    def statistics_key():
        owner()
        if app.config["PREVIEW"]:
            raise ValueError("La configuration réelle est désactivée dans l’aperçu.")
        key=body().get("api_key","")
        if not isinstance(key,str) or not re.fullmatch(r"[A-Za-z0-9_-]{30,120}",key.strip()):
            raise ValueError("Colle la clé API créée dans Google Cloud.")
        lookup(key.strip(),"@GoogleDevelopers")
        with store.db() as c:
            c.execute("UPDATE studio_public_settings SET api_key=?,verified_at=?,revision=revision+1 WHERE id=1",(key.strip(),now()))
            c.execute("UPDATE studio_public_sync SET lease_id='',lease_until='',next_check=?,error=''",(now(),))
        return jsonify(ok=True,configured=True)

    @app.post("/api/studio/statistics/channels")
    def statistics_add():
        if app.config["PREVIEW"]:
            raise ValueError("Les lectures publiques réelles sont désactivées dans l’aperçu.")
        data=body()
        identity,created=add(store,data.get("handle"),data.get("studio_id"))
        return jsonify(id=identity,created=created),201 if created else 200

    @app.get("/api/studio/statistics/channels/<identity>")
    def statistics_detail(identity):
        cleanup(store)
        hours=range_hours()
        return jsonify(**report(store,tracked(store,identity),hours),videos=videos_report(store,identity,hours))

    @app.post("/api/studio/statistics/channels/<identity>/refresh")
    def statistics_refresh(identity):
        if app.config["PREVIEW"]:
            raise ValueError("Les lectures réelles sont désactivées dans l’aperçu.")
        tracked(store,identity)
        if not api_key(store):
            raise ValueError("Configure d’abord la clé de lecture publique.")
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            state=c.execute("SELECT * FROM studio_public_sync WHERE track_id=?",(identity,)).fetchone()
            if state["lease_until"]>now():
                status="running"
            elif state["last_attempt"] and datetime.now(timezone.utc)-moment(state["last_attempt"])<timedelta(minutes=COOLDOWN_MINUTES):
                status="cached"
            else:
                c.execute("UPDATE studio_public_sync SET next_check=? WHERE track_id=?",(now(),identity))
                status="queued"
        return jsonify(status=status),202 if status=="queued" else 200

    @app.delete("/api/studio/statistics/channels/<identity>")
    def statistics_remove(identity):
        tracked(store,identity)
        with store.db() as c:
            c.execute("DELETE FROM studio_public_channels WHERE id=?",(identity,))
        return jsonify(ok=True)

    @app.get("/api/studio/statistics/export")
    def statistics_export():
        hours=range_hours()
        out=io.StringIO(newline="")
        writer=csv.writer(out,delimiter=";")
        writer.writerow(["Chaîne","Pseudo","Vues cumulées","Abonnés arrondis","Vidéos publiques","Variation observée","Début du relevé","Dernier relevé","Période incomplète"])
        for row in store.rows("SELECT * FROM studio_public_channels ORDER BY created_at"):
            data=report(store,row,hours)
            values=[data["name"],data["handle"],data["totals"]["views"],data["totals"]["subscribers"],data["totals"]["videos"],data["gain"],data["since"],data["updated_at"],"oui" if data["partial"] else "non"]
            writer.writerow(["'"+str(v) if isinstance(v,str) and v.startswith(("=","+","-","@","\t","\r")) else v for v in values])
        return Response("\ufeff"+out.getvalue(),mimetype="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=statistiques-youtube.csv"})
