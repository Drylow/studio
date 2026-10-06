"""Owner-initiated pairing with a visible local YouTube Studio browser.

Pairing is deliberately separate from OAuth and publication readiness. It never
enables a channel, changes its Google token, or queues an upload.
"""

from datetime import datetime, timedelta, timezone
import io
import json
import os
import re
import secrets
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request

from flask import jsonify, request, session
from studio.store import ROOT, Conflict, now
from studio import public_statistics

ACTIVE = {"queued", "waiting"}
MESSAGES = {
    "idle": "Connecte YouTube dans Chrome sur ton PC.",
    "queued": "Demande envoyée. L’agent PC va ouvrir Chrome.",
    "preparing_browser": "Ton PC prépare Chrome. Une notification Windows annonce la connexion.",
    "sign_in": "Dans Chrome sur ton PC, connecte-toi à YouTube puis choisis cette chaîne.",
    "dashboard_confirmed": "La bonne chaîne est ouverte dans Chrome. L’envoi automatique reste à valider.",
    "expired_request": "Cette demande a expiré. Allume ton PC puis clique de nouveau sur Connecter avec mon PC.",
    "invalid_request": "La demande PC n’a pas pu être vérifiée. Relance la connexion.",
    "chrome_missing": "Installe Google Chrome sur ton PC, puis relance la connexion.",
    "notification_failed": "Windows n’a pas pu afficher la notification. Vérifie les notifications de ton PC avant de réessayer.",
    "dependency_failed": "La préparation du navigateur a échoué. Vérifie la connexion Internet du PC, puis réessaie.",
    "agent_missing": "L’agent PC ne retrouve pas son dossier. La connexion n’a pas été ouverte.",
    "windows_required": "Cette connexion nécessite l’agent Windows déjà installé sur ton PC.",
    "unsafe_profile": "Le profil Chrome dédié ne peut pas être utilisé. Aucune session personnelle n’a été ouverte.",
    "browser_busy": "Ferme la fenêtre Chrome ouverte par Edgerunners pour cette chaîne, puis réessaie.",
    "browser_failed": "Chrome n’a pas pu être contrôlé. Aucune vidéo n’a été envoyée.",
    "sign_in_timeout": "Connexion non terminée. Clique de nouveau sur Connecter avec mon PC, puis connecte-toi dans Chrome.",
    "wrong_channel": "La chaîne ouverte ne correspond pas. Relance, puis dans YouTube Studio clique sur ta photo → Changer de compte et choisis la chaîne affichée ici.",
    "channel_changed": "Cette chaîne a changé pendant la connexion. Actualise et relance.",
    "worker_unavailable": "Le relais PC est indisponible. Aucune vidéo n’a été envoyée.",
}


def initialize(store):
    with store.db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS studio_pc_connections(
            request_id TEXT PRIMARY KEY,channel_id INTEGER NOT NULL REFERENCES studio_channels(project_id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES studio_users(id),revision INTEGER NOT NULL,
            expected_channel_id TEXT NOT NULL,channel_title TEXT NOT NULL,nonce TEXT NOT NULL,
            status TEXT NOT NULL,code TEXT NOT NULL,device_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,expires_at TEXT NOT NULL,checked_at TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS studio_pc_connection_channel ON studio_pc_connections(channel_id,created_at);
        """)


def worker_configuration():
    base = os.getenv("NEWS_WORKER_URL", "").strip().rstrip("/")
    token = os.getenv("NEWS_WORKER_TOKEN", "").strip()
    try:
        url = urllib.parse.urlsplit(base)
        valid = url.scheme == "https" and bool(url.hostname) and not url.username and not url.query and not url.fragment
    except ValueError:
        valid = False
    return (base, token) if valid and token else ("", "")


def relay(path, method="GET", body=None):
    base, token = worker_configuration()
    if not base:
        raise ValueError("Le relais PC n’est pas configuré sur le serveur.")
    req = urllib.request.Request(base + path, data=body, method=method,
                                 headers={"X-Worker-Token": token, "Content-Type": "application/gzip" if body else "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("Le relais PC a renvoyé une réponse trop longue.")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("Réponse du relais PC invalide.")
        return value
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise ValueError(MESSAGES["worker_unavailable"]) from None
    except (OSError, json.JSONDecodeError):
        raise ValueError(MESSAGES["worker_unavailable"]) from None


def bundle(row):
    manifest = dict(action="connect", request_id=row["request_id"], nonce=row["nonce"],
                    channel_id=row["expected_channel_id"], deadline=datetime.fromisoformat(row["expires_at"]).timestamp())
    files = {
        "code/production/news.py": b"from pc_youtube import main\nmain()\n",
        "code/production/pc_youtube.py": (ROOT / "production/pc_youtube.py").read_bytes(),
        "job/pc_request.json": json.dumps(manifest).encode(),
    }
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for dirname in ("code", "code/production", "job"):
            info = tarfile.TarInfo(dirname)
            info.type, info.mode = tarfile.DIRTYPE, 0o700
            archive.addfile(info)
        for name, raw in files.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(raw), 0o600
            archive.addfile(info, io.BytesIO(raw))
    return output.getvalue()


def latest(store, cid):
    return store.one("SELECT * FROM studio_pc_connections WHERE channel_id=? ORDER BY created_at DESC LIMIT 1", (cid,))


def public_state(row, preview=False):
    return dict(configured=bool(worker_configuration()[0]), preview=preview, status=row["status"] if row else "idle",
                message=MESSAGES.get(row["code"] if row else "idle", MESSAGES["invalid_request"]),
                channel_title=row["channel_title"] if row else "", channel_id=row["expected_channel_id"] if row else "",
                created_at=row["created_at"] if row else "", publication_validated=False)


def apply_result(store, row, result):
    status, code, device = "failed", "invalid_request", ""
    if now() >= row["expires_at"]:
        code = "expired_request"
    elif isinstance(result, dict) and type(result.get("version")) is int and all(result.get(k) == v for k, v in {
        "version": 1, "action": "connect", "request_id": row["request_id"],
        "nonce": row["nonce"], "expected_channel_id": row["expected_channel_id"],
    }.items()):
        returned_status, returned_code = result.get("status"), result.get("code")
        if not isinstance(returned_status, str) or not isinstance(returned_code, str):
            pass
        elif returned_status == "ready" and returned_code == "dashboard_confirmed" and result.get("dashboard_seen") is True and result.get("channel_id") == row["expected_channel_id"] and re.fullmatch(r"[a-f0-9]{32}", str(result.get("device_id", ""))):
            status, code, device = "ready", "dashboard_confirmed", result["device_id"]
        elif returned_status == "waiting" and returned_code in {"preparing_browser", "sign_in"}:
            status, code = "waiting", returned_code
        elif returned_status == "failed" and returned_code in MESSAGES and returned_code not in {"idle", "queued", "preparing_browser", "sign_in", "dashboard_confirmed"}:
            code = returned_code
    with store.db() as c:
        c.execute("BEGIN IMMEDIATE")
        ch = c.execute("SELECT revision,retired FROM studio_channels WHERE project_id=?", (row["channel_id"],)).fetchone()
        if not ch or ch["retired"] or ch["revision"] != row["revision"]:
            status, code, device = "failed", "channel_changed", ""
        c.execute("UPDATE studio_pc_connections SET status=?,code=?,device_id=?,checked_at=? WHERE request_id=? AND status IN ('queued','waiting')",
                  (status, code, device, now(), row["request_id"]))


def register(app, store, owner):
    initialize(store)

    def channel(cid):
        ch = store.channel(cid)
        if not ch:
            raise ValueError("Cette chaîne a été retirée ou n’existe pas.")
        return ch

    @app.get("/api/studio/youtube/<int:cid>/pc")
    def state(cid):
        channel(cid)
        return jsonify(public_state(latest(store, cid), app.config["PREVIEW"]))

    @app.post("/api/studio/youtube/<int:cid>/pc/connect")
    def start(cid):
        owner()
        ch = channel(cid)
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or type(data.get("revision")) is not int or data["revision"] != ch["revision"]:
            raise Conflict("Cette chaîne a changé. Actualise avant de connecter ton PC.")
        if app.config["PREVIEW"]:
            raise ValueError("La connexion PC est désactivée dans l’aperçu.")
        stamp = now()
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("UPDATE studio_pc_connections SET status='failed',code='expired_request' WHERE status IN ('queued','waiting') AND expires_at<=?", (stamp,))
            if c.execute("SELECT request_id FROM studio_pc_connections WHERE status IN ('queued','waiting')").fetchone():
                raise Conflict("Une connexion PC est déjà en cours. Termine-la dans Chrome avant de connecter une autre chaîne.")
        status = relay("/status") or {}
        seen = status.get("pc_seen")
        if isinstance(seen, bool) or not isinstance(seen, (int, float)) or not 0 <= time.time() - seen <= 300:
            raise ValueError("Allume ton PC, puis réessaie Connecter avec mon PC. L’agent installé peut mettre jusqu’à 15 minutes à redémarrer.")
        public = public_statistics.lookup(public_statistics.api_key(store), ch["handle"])
        if ch["yt_channel_id"] and ch["yt_channel_id"] != public["youtube_id"]:
            raise ValueError("Le @pseudo correspond à une autre chaîne. Corrige-le avant de connecter YouTube.")
        row = dict(request_id="pc-connect-" + secrets.token_hex(16), nonce=secrets.token_hex(32),
                   channel_id=cid, user_id=session["studio_user"], revision=ch["revision"],
                   expected_channel_id=public["youtube_id"], channel_title=public["name"],
                   status="queued", code="queued", created_at=stamp,
                   expires_at=(datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat())
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            current = channel(cid)
            if current["revision"] != ch["revision"]:
                raise Conflict("Cette chaîne a changé. Actualise avant de connecter ton PC.")
            if c.execute("SELECT request_id FROM studio_pc_connections WHERE status IN ('queued','waiting')").fetchone():
                raise Conflict("Une connexion PC est déjà en cours. Termine-la dans Chrome.")
            c.execute("INSERT INTO studio_pc_connections(" + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")", list(row.values()))
        # An ambiguous relay response must never cause a second browser command.
        try:
            accepted = relay("/pcjob?" + urllib.parse.urlencode({"name": row["request_id"]}), "PUT", bundle(row))
            if not accepted or accepted.get("ok") is not True:
                raise ValueError(MESSAGES["worker_unavailable"])
        except ValueError:
            return jsonify(public_state(row)), 202
        store.log("user", "pc-youtube", "Connexion locale demandée pour " + ch["name"] + ". Aucune publication.")
        return jsonify(public_state(row)), 202

    @app.post("/api/studio/youtube/<int:cid>/pc/check")
    def check(cid):
        owner()
        ch = channel(cid)
        row = latest(store, cid)
        if not row or row["status"] not in ACTIVE or app.config["PREVIEW"]:
            return jsonify(public_state(row, app.config["PREVIEW"]))
        if row["revision"] != ch["revision"] or now() >= row["expires_at"]:
            apply_result(store, row, None)
        elif not row["checked_at"] or (datetime.now(timezone.utc) - datetime.fromisoformat(row["checked_at"])).total_seconds() >= 12:
            with store.db() as c:
                c.execute("UPDATE studio_pc_connections SET checked_at=? WHERE request_id=?", (now(), row["request_id"]))
            suffix = urllib.parse.urlencode({"name": row["request_id"], "path": "result.json"})
            result = relay("/pc/file?" + suffix)
            if result is not None:
                apply_result(store, row, result)
            else:
                remote = relay("/pc/state?" + urllib.parse.urlencode({"name": row["request_id"]}))
                if (remote and remote.get("state") == "done") or (remote is None and (datetime.now(timezone.utc) - datetime.fromisoformat(row["created_at"])).total_seconds() > 30):
                    apply_result(store, row, {})
        return jsonify(public_state(latest(store, cid), app.config["PREVIEW"]))
