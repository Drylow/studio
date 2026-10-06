"""Pair on the PC that opens the link, using a narrowly scoped local companion.

This replaces the shared PC relay queue. A connection never activates publishing,
exports cookies, installs on a remote PC, or supplies arbitrary commands.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import io
import re
import secrets

from flask import g, jsonify, request, send_file
from studio import public_statistics
from studio.store import Conflict, now

ACTIVE = {"awaiting_app", "waiting"}
TABLE = "studio_pc_local_connections"
MESSAGES = {
    "idle": "Installe l’assistant une fois sur le PC qui servira à publier.",
    "awaiting_app": "L’assistant n’a pas encore répondu. Ouvre-le sur ce PC, ou télécharge l’installation ci-dessous.",
    "preparing_browser": "L’assistant a répondu depuis le PC où il a été lancé. Il prépare Chrome.",
    "sign_in": "Une fenêtre Chrome visible a été confirmée. Dans cette fenêtre, connecte-toi et choisis la chaîne indiquée.",
    "dashboard_confirmed": "La bonne chaîne a été vérifiée dans Chrome. La publication automatique reste à valider.",
    "expired_request": "Ce lien a expiré. Clique sur Connecter avec mon PC pour en créer un nouveau.",
    "invalid_request": "Cette demande n’est pas valide. Relance la connexion depuis le studio.",
    "chrome_missing": "Installe Google Chrome sur ce PC, puis relance depuis le studio.",
    "unsafe_profile": "Le profil dédié ne peut pas être utilisé. Aucune session personnelle n’a été ouverte.",
    "browser_busy": "Ferme la fenêtre Chrome dédiée déjà ouverte pour cette chaîne, puis relance.",
    "browser_failed": "Chrome n’a pas pu être ouvert ou vérifié. Aucune vidéo n’a été envoyée.",
    "browser_closed": "La fenêtre Chrome dédiée a été fermée. Relance la connexion depuis le studio.",
    "desktop_not_interactive": "Ouvre ta session Windows, puis lance l’assistant depuis le studio sur ce PC.",
    "browser_not_visible": "Aucune fenêtre Chrome visible n’a été confirmée. Ouvre ta session Windows puis relance.",
    "sign_in_timeout": "Connexion non terminée. Relance et connecte-toi dans la nouvelle fenêtre Chrome.",
    "wrong_channel": "La chaîne ouverte est différente. Relance puis clique sur ta photo → Changer de compte dans YouTube Studio.",
    "channel_changed": "Cette chaîne a changé. Actualise le site puis relance la connexion.",
    "cancelled": "Connexion annulée sur le PC. Tu peux la relancer depuis le studio.",
}
FAILURES = set(MESSAGES) - {"idle", "awaiting_app", "preparing_browser", "sign_in", "dashboard_confirmed"}


def initialize(store):
    with store.db() as c:
        c.executescript(f"""
        CREATE TABLE IF NOT EXISTS {TABLE}(
            request_id TEXT PRIMARY KEY,channel_id INTEGER NOT NULL REFERENCES studio_channels(project_id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES studio_users(id),revision INTEGER NOT NULL,
            expected_channel_id TEXT NOT NULL,channel_title TEXT NOT NULL,
            status TEXT NOT NULL,code TEXT NOT NULL,device_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,expires_at TEXT NOT NULL,checked_at TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS studio_pc_local_channel ON {TABLE}(channel_id,created_at);
        """)


def latest(store, cid):
    return store.one(f"SELECT * FROM {TABLE} WHERE channel_id=? ORDER BY created_at DESC LIMIT 1", (cid,))


def capability(app, row):
    payload = ":".join(str(row[k]) for k in ("request_id", "user_id", "channel_id", "revision", "expires_at"))
    return hmac.new(app.config["SECRET_KEY"].encode(), ("pc-local-v1:" + payload).encode(), hashlib.sha256).hexdigest()


def valid_actor(c, row):
    user = c.execute("SELECT role FROM studio_users WHERE id=?", (row["user_id"],)).fetchone()
    ch = c.execute("SELECT revision,retired FROM studio_channels WHERE project_id=?", (row["channel_id"],)).fetchone()
    return bool(user and user["role"] == "owner" and ch and not ch["retired"] and ch["revision"] == row["revision"])


def expire(store, cid):
    with store.db() as c:
        c.execute("BEGIN IMMEDIATE")
        for row in c.execute(f"SELECT * FROM {TABLE} WHERE channel_id=? AND status IN ('awaiting_app','waiting')", (cid,)).fetchall():
            code = "expired_request" if now() >= row["expires_at"] else "channel_changed" if not valid_actor(c, row) else ""
            if code:
                c.execute(f"UPDATE {TABLE} SET status='failed',code=? WHERE request_id=?", (code, row["request_id"]))


def public_state(app, row):
    state = dict(configured=True, preview=app.config["PREVIEW"], status=row["status"] if row else "idle",
                 message=MESSAGES.get(row["code"] if row else "idle", MESSAGES["invalid_request"]),
                 channel_title=row["channel_title"] if row else "", channel_id=row["expected_channel_id"] if row else "",
                 created_at=row["created_at"] if row else "", publication_validated=False)
    # Narrow capabilities are visible only to the owner who initiated this request.
    if row and row["status"] in ACTIVE and g.user and g.user["role"] == "owner" and g.user["id"] == row["user_id"] and not app.config["PREVIEW"]:
        state["launch_uri"] = "edgerunners-studio://connect/" + row["request_id"] + "?token=" + capability(app, row)
        state["installer_href"] = f'/api/studio/youtube/{row["channel_id"]}/pc/installer/{row["request_id"]}'
    return state


def authorize_machine(app, store):
    """Only two fixed endpoints use this capability instead of the private gate."""
    rid = (request.view_args or {}).get("request_id", "")
    if not re.fullmatch(r"pc-local-[a-f0-9]{32}", rid):
        return jsonify(error="Demande invalide."), 404
    if app.config["PREVIEW"]:
        return jsonify(error="Connexion PC désactivée dans l’aperçu."), 403
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return jsonify(error="Autorisation de l’assistant requise."), 401
    token = header[7:]
    row = store.one(f"SELECT * FROM {TABLE} WHERE request_id=?", (rid,))
    if not row or not re.fullmatch(r"[a-f0-9]{64}", token) or not hmac.compare_digest(token, capability(app, row)):
        return jsonify(error="Autorisation refusée."), 403
    origin = request.headers.get("Origin")
    if origin and origin != request.host_url.rstrip("/"):
        return jsonify(error="Origine refusée."), 403
    with store.db() as c:
        if now() >= row["expires_at"] or not valid_actor(c, row) or row["status"] not in ACTIVE:
            return jsonify(error="Cette demande n’est plus active."), 410
    g.pc_connection = row
    return None


def register(app, store, owner):
    initialize(store)

    def channel(cid):
        ch = store.channel(cid)
        if not ch:
            raise ValueError("Cette chaîne a été retirée ou n’existe pas.")
        return ch

    def state_for(cid):
        expire(store, cid)
        return public_state(app, latest(store, cid))

    @app.get("/api/studio/youtube/<int:cid>/pc")
    def pc_local_state(cid):
        channel(cid)
        return jsonify(state_for(cid))

    @app.post("/api/studio/youtube/<int:cid>/pc/connect")
    def pc_local_start(cid):
        owner()
        ch = channel(cid)
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or type(data.get("revision")) is not int or data["revision"] != ch["revision"]:
            raise Conflict("Cette chaîne a changé. Actualise avant de connecter ton PC.")
        if app.config["PREVIEW"]:
            raise ValueError("La connexion PC est désactivée dans l’aperçu.")
        expire(store, cid)
        row = latest(store, cid)
        if row and row["status"] in ACTIVE and row["user_id"] == g.user["id"]:
            return jsonify(public_state(app, row)), 202
        public = public_statistics.lookup(public_statistics.api_key(store), ch["handle"])
        if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", public["youtube_id"]):
            raise ValueError("Identifiant de chaîne invalide.")
        if ch["yt_channel_id"] and ch["yt_channel_id"] != public["youtube_id"]:
            raise ValueError("Le @pseudo correspond à une autre chaîne. Corrige-le avant de connecter YouTube.")
        row = dict(request_id="pc-local-" + secrets.token_hex(16), channel_id=cid, user_id=g.user["id"],
                   revision=ch["revision"], expected_channel_id=public["youtube_id"], channel_title=public["name"][:200],
                   status="awaiting_app", code="awaiting_app", created_at=now(),
                   expires_at=(datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat())
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            if not valid_actor(c, row):
                raise Conflict("Cette chaîne a changé. Actualise avant de connecter ton PC.")
            existing = c.execute(f"SELECT * FROM {TABLE} WHERE channel_id=? AND user_id=? AND status IN ('awaiting_app','waiting') AND expires_at>? ORDER BY created_at DESC LIMIT 1", (cid, row["user_id"], now())).fetchone()
            if existing:
                return jsonify(public_state(app, dict(existing))), 202
            c.execute(f"UPDATE {TABLE} SET status='failed',code='channel_changed' WHERE channel_id=? AND status IN ('awaiting_app','waiting')", (cid,))
            c.execute(f'INSERT INTO {TABLE}(' + ','.join(row) + ') VALUES(' + ','.join('?' for _ in row) + ')', list(row.values()))
        store.log("user", "pc-youtube", "Lien local préparé pour " + ch["name"] + ". Assistant pas encore lancé.")
        return jsonify(public_state(app, row)), 202

    @app.post("/api/studio/youtube/<int:cid>/pc/check")
    def pc_local_check(cid):
        owner()
        channel(cid)
        return jsonify(state_for(cid))

    @app.get("/api/studio/youtube/<int:cid>/pc/installer/<request_id>")
    def pc_local_installer(cid, request_id):
        owner()
        channel(cid)
        expire(store, cid)
        row = store.one(f"SELECT * FROM {TABLE} WHERE request_id=? AND channel_id=? AND user_id=?", (request_id, cid, g.user["id"]))
        if app.config["PREVIEW"] or not row or row["status"] not in ACTIVE:
            raise ValueError("Ce lien d’installation a expiré. Relance la connexion.")
        from studio.pc_installer import installer_zip
        uri = "edgerunners-studio://connect/" + request_id + "?token=" + capability(app, row)
        return send_file(io.BytesIO(installer_zip(uri)), as_attachment=True, download_name="Edgerunners-PC.zip", mimetype="application/zip", max_age=0)

    @app.get("/api/studio/pc-local/<request_id>/manifest")
    def pc_local_manifest(request_id):
        row = g.pc_connection
        return jsonify(channel_id=row["expected_channel_id"], channel_title=row["channel_title"],
                       deadline=datetime.fromisoformat(row["expires_at"]).timestamp())

    @app.post("/api/studio/pc-local/<request_id>/progress")
    def pc_local_progress(request_id):
        if (request.content_length or 0) > 2048:
            return jsonify(error="Réponse trop longue."), 413
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("Réponse de l’assistant invalide.")
        status, code, device = data.get("status"), data.get("code"), data.get("device_id")
        if not isinstance(status, str) or not isinstance(code, str) or not isinstance(device, str) or not re.fullmatch(r"[a-f0-9]{32}", device):
            raise ValueError("Réponse de l’assistant invalide.")
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            row = dict(c.execute(f"SELECT * FROM {TABLE} WHERE request_id=?", (request_id,)).fetchone())
            if now() >= row["expires_at"] or not valid_actor(c, row) or row["status"] not in ACTIVE:
                return jsonify(error="Cette demande n’est plus active."), 410
            if row["device_id"] and row["device_id"] != device:
                return jsonify(error="Cette connexion est déjà utilisée sur un autre PC."), 409
            if data.get("expected_channel_id") != row["expected_channel_id"]:
                raise ValueError("La chaîne de la demande ne correspond pas.")
            if status == "waiting" and code == "preparing_browser" and row["code"] in {"awaiting_app", "preparing_browser"}:
                pass
            elif status == "waiting" and code == "sign_in" and row["code"] in {"preparing_browser", "sign_in"} and data.get("browser_visible") is True:
                pass
            elif status == "ready" and code == "dashboard_confirmed" and row["code"] == "sign_in" and data.get("browser_visible") is True and data.get("navigation_verified") is True and data.get("channel_id") == row["expected_channel_id"]:
                pass
            elif status == "failed" and code in FAILURES:
                pass
            else:
                raise ValueError("L’assistant n’a pas confirmé les étapes de connexion.")
            c.execute(f"UPDATE {TABLE} SET status=?,code=?,device_id=?,checked_at=? WHERE request_id=?", (status, code, device, now(), request_id))
        return jsonify(ok=True)
