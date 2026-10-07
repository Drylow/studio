"""Private, short-lived access to the owner's first-party browser on the VPS.

The worker initiates HTTPS connections; there is no public browser/VNC port.
Keyboard text is encrypted by Web Crypto for the worker before it reaches this
server. A browser session is not an OAuth grant or a validated publisher.
"""

import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import tarfile
import time
import urllib.request
from flask import g, jsonify, request
from studio.store import ROOT, Conflict

BRIDGE_PATH = "/api/studio/youtube-browser/bridge"
SESSION_SECONDS = 1200
COMMAND_SECONDS = 45
CID = re.compile(r"UC[A-Za-z0-9_-]{22}")
ID = re.compile(r"[0-9a-f]{32}")


def enabled(app):
    return not app.config["PREVIEW"] and os.getenv("YOUTUBE_BROWSER_ENABLED") == "1"


def signing_key(token):
    return hmac.new(token.encode(), b"edgerunners-private-browser-v1", hashlib.sha256).digest()


def signature(token, stamp, nonce, body):
    message = (stamp + "\n" + nonce + "\n" + BRIDGE_PATH + "\n").encode() + body
    return hmac.new(signing_key(token), message, hashlib.sha256).hexdigest()


def initialize(store):
    with store.db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS studio_browser_worker(id INTEGER PRIMARY KEY CHECK(id=1),
            instance TEXT NOT NULL, public_key TEXT NOT NULL, seen_at REAL NOT NULL,
            source_digest TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS studio_browser_nonces(nonce TEXT PRIMARY KEY, expires_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS studio_browser_sessions(id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES studio_users(id), auth_hash TEXT NOT NULL,
            channel_id INTEGER NOT NULL REFERENCES studio_channels(project_id), revision INTEGER NOT NULL,
            instance TEXT NOT NULL, expected_id TEXT NOT NULL, expires_at REAL NOT NULL,
            closed INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS studio_browser_commands(id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES studio_browser_sessions(id) ON DELETE CASCADE,
            kind TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued',
            expires_at REAL NOT NULL, result TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS studio_browser_pending ON studio_browser_commands(state,expires_at);
        """)
        if "source_digest" not in {row["name"] for row in c.execute("PRAGMA table_info(studio_browser_worker)")}:
            c.execute("ALTER TABLE studio_browser_worker ADD COLUMN source_digest TEXT NOT NULL DEFAULT ''")


def service_digest():
    return hashlib.sha256((ROOT / "production/private_browser_service.py").read_bytes()).hexdigest()


def prune(c, at):
    # Logging out, changing role/channel or removing a channel revokes the viewer.
    c.execute("""UPDATE studio_browser_sessions SET closed=1 WHERE expires_at<? OR NOT EXISTS
        (SELECT 1 FROM studio_sessions a JOIN studio_users u ON u.id=a.user_id
         JOIN studio_channels ch ON ch.project_id=studio_browser_sessions.channel_id
         WHERE a.token_hash=studio_browser_sessions.auth_hash AND a.user_id=studio_browser_sessions.user_id
         AND a.expires_at>? AND a.seen_at>? AND u.role='owner' AND ch.retired=0
         AND ch.revision=studio_browser_sessions.revision)""", (at, at, at-3600))
    c.execute("DELETE FROM studio_browser_commands WHERE expires_at<? OR session_id IN (SELECT id FROM studio_browser_sessions WHERE closed=1)", (at,))
    c.execute("DELETE FROM studio_browser_sessions WHERE expires_at<? AND closed=1", (at-60,))
    c.execute("DELETE FROM studio_browser_nonces WHERE expires_at<?", (at,))


def authenticate_bridge(app, store):
    """The only machine endpoint; called after the existing HTTPS/host guards."""
    token = os.getenv("NEWS_WORKER_TOKEN", "")
    if not enabled(app) or len(token) < 24 or request.method != "POST":
        return jsonify(error="Accès refusé."), 403
    if request.headers.get("Origin") or request.headers.get("Cookie") or request.query_string:
        return jsonify(error="Accès refusé."), 403
    if (request.content_length or 0) > 1_500_000:
        return jsonify(error="Requête trop volumineuse."), 413
    stamp = request.headers.get("X-Browser-Time", "")
    nonce = request.headers.get("X-Browser-Nonce", "")
    proof = request.headers.get("X-Browser-Proof", "")
    if not re.fullmatch(r"[0-9]{10}", stamp) or not ID.fullmatch(nonce) or not re.fullmatch(r"[0-9a-f]{64}", proof):
        return jsonify(error="Accès refusé."), 403
    at = time.time()
    if abs(at-int(stamp)) > 120 or not hmac.compare_digest(signature(token, stamp, nonce, request.get_data()), proof):
        return jsonify(error="Accès refusé."), 403
    with store.db() as c:
        c.execute("BEGIN IMMEDIATE")
        prune(c, at)
        if c.execute("SELECT 1 FROM studio_browser_nonces WHERE nonce=?", (nonce,)).fetchone():
            return jsonify(error="Requête déjà utilisée."), 409
        c.execute("INSERT INTO studio_browser_nonces VALUES(?,?)", (nonce, at+240))
    return None


def bootstrap(app):
    """Start our reviewed service through the existing authenticated render API."""
    from urllib.parse import urlsplit
    base = os.getenv("NEWS_WORKER_URL", "").rstrip("/")
    token = os.getenv("NEWS_WORKER_TOKEN", "")
    site = app.config["PUBLIC_URL"]
    for address in (base, site):
        parsed = urlsplit(address)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("L’adresse HTTPS du navigateur doit être configurée sur le serveur.")
    headers = {"X-Worker-Token": token}
    try:
        with urllib.request.urlopen(urllib.request.Request(base+"/status", headers=headers), timeout=15) as response:
            if json.load(response).get("busy"):
                raise Conflict("Le VPS termine un montage. Réessaie à la fin du montage.")
        stream = io.BytesIO()
        code = (ROOT / "production/private_browser_service.py").read_bytes()
        launch = b"import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).resolve().parents[1]))\nfrom production.private_browser_service import bootstrap\nbootstrap(sys.argv[2])\n"
        config = json.dumps({"site": site}).encode()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            for path in ("code", "code/production", "job"):
                item = tarfile.TarInfo(path); item.type=tarfile.DIRTYPE; item.mode=0o700
                archive.addfile(item)
            for path, data in (("code/production/news.py", launch), ("code/production/private_browser_service.py", code), ("job/start.json", config)):
                item = tarfile.TarInfo(path); item.size=len(data); item.mode=0o600
                archive.addfile(item, io.BytesIO(data))
        name = "edgerunners-private-browser-"+secrets.token_hex(8)
        req = urllib.request.Request(base+"/job?name="+name+"&upload=0", data=stream.getvalue(), headers=headers, method="PUT")
        with urllib.request.urlopen(req, timeout=25):
            pass
    except (OSError, json.JSONDecodeError):
        raise ValueError("Le navigateur du VPS est indisponible. Aucun compte n’a été connecté.") from None


def worker(store):
    row = store.one("SELECT * FROM studio_browser_worker WHERE id=1")
    return row if row and row["seen_at"] > time.time()-35 and row["source_digest"] == service_digest() else None


def register(app, store, owner):
    initialize(store)

    @app.post(BRIDGE_PATH)
    def remote_browser_bridge():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not ID.fullmatch(str(data.get("instance", ""))):
            raise ValueError("Requête du navigateur invalide.")
        instance = data["instance"]
        public_key = data.get("public_key", "")
        if not isinstance(public_key, str) or not 500 <= len(public_key) <= 800 or not re.fullmatch(r"[A-Za-z0-9+/=]+", public_key):
            raise ValueError("Clé du navigateur invalide.")
        digest = data.get("source_digest", "")
        if digest != service_digest():
            return jsonify(error="Version du navigateur à mettre à jour."), 409
        at = time.time()
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            prior = c.execute("SELECT * FROM studio_browser_worker WHERE id=1").fetchone()
            if prior and (prior["instance"] != instance or prior["public_key"] != public_key):
                c.execute("UPDATE studio_browser_sessions SET closed=1")
            c.execute("INSERT INTO studio_browser_worker VALUES(1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET instance=excluded.instance,public_key=excluded.public_key,seen_at=excluded.seen_at,source_digest=excluded.source_digest", (instance, public_key, at, digest))
            prune(c, at)
            result = data.get("result")
            if isinstance(result, dict) and ID.fullmatch(str(result.get("id", ""))):
                command = c.execute("SELECT j.*,s.instance,s.expected_id FROM studio_browser_commands j JOIN studio_browser_sessions s ON s.id=j.session_id WHERE j.id=? AND j.state='claimed' AND s.closed=0 AND j.expires_at>?", (result["id"], at)).fetchone()
                if command and command["instance"] == instance:
                    value = result.get("value")
                    if not isinstance(value, dict) or len(json.dumps(value)) > 1_000_000:
                        raise ValueError("Résultat du navigateur invalide.")
                    # Keep connection/publication false; this is an interactive login, not an uploader.
                    c.execute("UPDATE studio_browser_commands SET state='done',payload='{}',result=? WHERE id=?", (json.dumps(value), command["id"]))
            sessions = [dict(s) for s in c.execute("SELECT id,channel_id,expected_id,expires_at FROM studio_browser_sessions WHERE closed=0 AND instance=?", (instance,))]
            queued = c.execute("SELECT j.*,s.channel_id,s.expected_id FROM studio_browser_commands j JOIN studio_browser_sessions s ON s.id=j.session_id WHERE j.state='queued' AND j.expires_at>? AND s.closed=0 AND s.instance=? ORDER BY j.rowid LIMIT 1", (at, instance)).fetchone()
            command = None
            if queued:
                command = {key: queued[key] for key in ("id", "session_id", "kind", "channel_id", "expected_id", "expires_at")}
                command["payload"] = json.loads(queued["payload"])
                c.execute("UPDATE studio_browser_commands SET state='claimed' WHERE id=?", (queued["id"],))
        return jsonify(command=command, sessions=sessions)

    def checked(cid):
        owner()
        if not enabled(app):
            raise PermissionError("Le navigateur privé n’est pas activé.")
        channel = store.channel(cid)
        if not channel:
            raise ValueError("Cette chaîne a été retirée.")
        return channel

    def viewer(cid, sid):
        checked(cid)
        if not ID.fullmatch(sid):
            raise PermissionError("Accès au navigateur refusé.")
        with store.db() as c:
            prune(c, time.time())
        row = store.one("SELECT * FROM studio_browser_sessions WHERE id=? AND channel_id=? AND user_id=? AND auth_hash=? AND closed=0", (sid, cid, g.user["id"], g.auth_session["token_hash"]))
        active = worker(store)
        if not row or not active or row["instance"] != active["instance"]:
            raise ValueError("Le navigateur a expiré. Rouvre la connexion depuis la chaîne.")
        return row, active

    @app.get("/api/studio/youtube-browser/status")
    def browser_status():
        owner()
        return jsonify(enabled=enabled(app), available=bool(enabled(app) and worker(store)), publication_validated=False)

    @app.post("/api/studio/youtube-browser/start-service")
    def browser_start_service():
        owner()
        if not enabled(app):
            raise PermissionError("Le navigateur privé n’est pas activé.")
        if not worker(store):
            bootstrap(app)
        return jsonify(starting=not bool(worker(store)))

    @app.post("/api/studio/youtube-browser/<int:cid>/sessions")
    def browser_session_start(cid):
        channel = checked(cid)
        data = request.get_json(silent=True) or {}
        if data.get("revision") != channel["revision"]:
            raise Conflict("Cette chaîne a changé. Actualise la page.")
        active = worker(store)
        if not active:
            raise ValueError("Démarre d’abord le navigateur du serveur.")
        expected = channel["yt_channel_id"]
        if not CID.fullmatch(expected):
            from studio.public_statistics import api_key, lookup
            expected = lookup(api_key(store), channel["handle"])["youtube_id"]
        sid = secrets.token_hex(16)
        at = time.time()
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            current = c.execute("SELECT revision,retired FROM studio_channels WHERE project_id=?", (cid,)).fetchone()
            if current["revision"] != channel["revision"] or current["retired"]:
                raise Conflict("Cette chaîne a changé. Actualise la page.")
            c.execute("UPDATE studio_browser_sessions SET closed=1")
            prune(c, at)
            c.execute("INSERT INTO studio_browser_sessions VALUES(?,?,?,?,?,?,?,?,0)", (sid, g.user["id"], g.auth_session["token_hash"], cid, channel["revision"], active["instance"], expected, at+SESSION_SECONDS))
        return jsonify(session_id=sid, public_key=active["public_key"], expires_at=at+SESSION_SECONDS)

    @app.post("/api/studio/youtube-browser/<int:cid>/sessions/<sid>/commands")
    def browser_command(cid, sid):
        row, active = viewer(cid, sid)
        data = request.get_json(silent=True) or {}
        kind = data.get("kind")
        if kind not in {"open", "frame", "input", "inspect"}:
            raise ValueError("Commande du navigateur invalide.")
        payload = {}
        if kind == "input":
            for field, limit in (("key", 1024), ("iv", 32), ("ciphertext", 16000)):
                value = data.get(field)
                if not isinstance(value, str) or not 1 <= len(value) <= limit or not re.fullmatch(r"[A-Za-z0-9+/=]+", value):
                    raise ValueError("La saisie doit être chiffrée pour le navigateur.")
                payload[field] = value
            if set(data) != {"kind", "key", "iv", "ciphertext"}:
                raise ValueError("Requête de saisie invalide.")
        identity = secrets.token_hex(16)
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            prune(c, time.time())
            if c.execute("SELECT 1 FROM studio_browser_commands WHERE session_id=? AND state IN ('queued','claimed')", (sid,)).fetchone():
                raise Conflict("Le navigateur traite encore la dernière action.")
            c.execute("INSERT INTO studio_browser_commands VALUES(?,?,?,?, 'queued',?, '')", (identity, sid, kind, json.dumps(payload), time.time()+COMMAND_SECONDS))
        return jsonify(command_id=identity)

    @app.get("/api/studio/youtube-browser/<int:cid>/sessions/<sid>/commands/<identity>")
    def browser_command_result(cid, sid, identity):
        viewer(cid, sid)
        row = store.one("SELECT state,result FROM studio_browser_commands WHERE id=? AND session_id=?", (identity, sid))
        if not row:
            raise ValueError("Action expirée. Elle ne sera pas renvoyée automatiquement.")
        return jsonify(state=row["state"], result=json.loads(row["result"]) if row["result"] else None)

    @app.post("/api/studio/youtube-browser/<int:cid>/sessions/<sid>/close")
    def browser_session_close(cid, sid):
        # Closing works even when the VPS is unavailable; screenshots/input are erased.
        checked(cid)
        with store.db() as c:
            c.execute("UPDATE studio_browser_sessions SET closed=1 WHERE id=? AND channel_id=? AND user_id=? AND auth_hash=?", (sid, cid, g.user["id"], g.auth_session["token_hash"]))
            prune(c, time.time())
        return jsonify(closed=True)
