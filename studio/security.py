"""Private two-person access with password throttling and revocable sessions."""

from contextlib import contextmanager
import hashlib
import hmac
import re
import secrets
import time

from flask import current_app, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from studio.store import Conflict, now, uid

PUBLIC_APIS = {
    "/api/studio/bootstrap",
    "/api/studio/setup",
    "/api/studio/login",
    "/api/studio/logout",
}
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(32))


def initialize(store):
    with store.db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS studio_sessions(
          token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES studio_users(id),
          scope TEXT NOT NULL, expires_at REAL NOT NULL, seen_at REAL NOT NULL,
          private_data TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS studio_sessions_user ON studio_sessions(user_id);
        """)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def equal(left, right):
    return hmac.compare_digest(str(left).encode(), str(right).encode())


def valid_password(value):
    if not isinstance(value, str) or not 16 <= len(value) <= 128:
        raise ValueError("Choisis un mot de passe personnel de 16 à 128 caractères.")
    if len(set(value)) < 6:
        raise ValueError("Choisis plusieurs mots ou caractères différents.")
    return value


def reserve_attempt(store, subject):
    """Reserve before expensive verification, including concurrent requests."""
    cutoff = time.time() - 600
    with store.db() as c:
        c.execute("BEGIN IMMEDIATE")
        c.execute(
            "DELETE FROM studio_login_attempts WHERE created_at<?",
            (time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(cutoff)),),
        )
        attempts = c.execute(
            "SELECT COUNT(*) FROM studio_login_attempts WHERE ip=? OR username=?",
            (request.remote_addr or "unknown", subject),
        ).fetchone()[0]
        if attempts >= 8:
            return None
        cursor = c.execute(
            "INSERT INTO studio_login_attempts VALUES(?,?,?)",
            (request.remote_addr or "unknown", subject, now()),
        )
        return cursor.lastrowid


def clear_attempt(store, attempt):
    with store.db() as c:
        c.execute("DELETE FROM studio_login_attempts WHERE rowid=?", (attempt,))


def throttled():
    return (
        jsonify(error="Trop d’essais. Réessaie dans 10 minutes."),
        429,
        {"Retry-After": "600"},
    )


def revoke(store, container=session):
    token = container.get("studio_sid", "")
    if isinstance(token, str) and 0 < len(token) <= 128:
        with store.db() as c:
            c.execute(
                "DELETE FROM studio_sessions WHERE token_hash=?", (digest(token),)
            )
    container.clear()


def issue(
    store, user_id, *, scope="full", container=session, ttl=None, expected_hash=None
):
    """Serialize credential changes with issuance; an old password cannot regain access."""
    if scope not in {"full", "internal"}:
        raise ValueError("Type de session invalide.")
    token = secrets.token_urlsafe(32)
    previous = container.get("studio_sid", "")
    at = time.time()
    lifespan = ttl or (43200 if scope == "full" else 300)
    with store.db() as c:
        c.execute("BEGIN IMMEDIATE")
        user = c.execute(
            "SELECT password_hash FROM studio_users WHERE id=?", (user_id,)
        ).fetchone()
        if not user or (
            expected_hash is not None
            and not equal(user["password_hash"], expected_hash)
        ):
            raise Conflict("Les identifiants ont changé. Reconnecte-toi.")
        if isinstance(previous, str) and 0 < len(previous) <= 128:
            c.execute(
                "DELETE FROM studio_sessions WHERE token_hash=?", (digest(previous),)
            )
        c.execute("DELETE FROM studio_sessions WHERE expires_at<?", (at,))
        c.execute(
            "INSERT INTO studio_sessions VALUES(?,?,?,?,?,?)",
            (digest(token), user_id, scope, at + lifespan, at, ""),
        )
    container.clear()
    container.update(
        studio_sid=token, studio_user=user_id, csrf=secrets.token_urlsafe(32)
    )
    container["_permanent"] = True


def identity(store):
    g.auth_session = None
    token = session.get("studio_sid", "")
    if not isinstance(token, str) or len(token) > 128 or not token:
        return None
    record = store.one(
        "SELECT * FROM studio_sessions WHERE token_hash=?", (digest(token),)
    )
    if (
        not record
        or record["user_id"] != session.get("studio_user")
        or record["expires_at"] <= time.time()
        or record["seen_at"] < time.time() - 3600
    ):
        revoke(store)
        return None
    user = next((u for u in store.users() if u["id"] == record["user_id"]), None)
    if not user:
        revoke(store)
        return None
    g.auth_session = record
    if record["seen_at"] < time.time() - 60:
        with store.db() as c:
            c.execute(
                "UPDATE studio_sessions SET seen_at=? WHERE token_hash=?",
                (time.time(), digest(token)),
            )
    if record["scope"] not in {"full", "internal"}:
        revoke(store)
        g.auth_session = None
        return None
    return user


@contextmanager
def trusted_client(store, user_id):
    """An internal worker impersonates only its already-authorized job's user."""
    app = store.web_app
    base = app.config.get("PUBLIC_URL") if app.config["HOSTED"] else "http://localhost"
    client = app.test_client()
    with app.app_context(), client.session_transaction(base_url=base) as container:
        issue(store, user_id, scope="internal", container=container, ttl=300)
        csrf = container["csrf"]
        token_hash = digest(container["studio_sid"])
    try:
        yield client, csrf, base
    finally:
        with store.db() as c:
            c.execute("DELETE FROM studio_sessions WHERE token_hash=?", (token_hash,))


def json_body():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValueError("Requête JSON attendue.")
    return value


def register(app, store):
    @app.post("/api/studio/setup")
    def auth_setup():
        import os

        b = json_body()
        attempt = reserve_attempt(store, "setup")
        if attempt is None:
            return throttled()
        token = os.getenv("STUDIO_BOOTSTRAP_TOKEN", "")
        supplied = str(b.get("token", ""))[:256]
        if not token or not equal(supplied, token):
            raise PermissionError("Code d’activation invalide.")
        clear_attempt(store, attempt)
        name = str(b.get("name", "")).strip()
        username = str(b.get("username", "")).strip().lower()
        password = valid_password(b.get("password"))
        if not 1 <= len(name) <= 80 or not re.fullmatch(r"[a-z0-9_.-]{3,40}", username):
            raise ValueError(
                "Renseigne ton nom et un identifiant de 3 à 40 caractères."
            )
        if store.users():
            raise Conflict("Le studio a déjà été activé.")
        hashed = generate_password_hash(password)
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT 1 FROM studio_users").fetchone():
                raise Conflict("Le studio a déjà été activé.")
            user_id = uid()
            c.execute(
                "INSERT INTO studio_users VALUES(?,?,?,?,?,?)",
                (user_id, name, username, hashed, "owner", now()),
            )
        issue(store, user_id, expected_hash=hashed)
        store.log(name, "setup", "Compte propriétaire créé")
        return jsonify(ok=True)

    @app.post("/api/studio/login")
    def auth_login():
        b = json_body()
        username = str(b.get("username", "")).strip().lower()[:40]
        password = b.get("password")
        attempt = reserve_attempt(store, "password:" + username)
        if attempt is None:
            return throttled()
        u = store.one("SELECT * FROM studio_users WHERE username=?", (username,))
        bounded = (
            isinstance(password, str)
            and 16 <= len(password) <= 128
            and len(set(password)) >= 6
        )
        correct = check_password_hash(
            u["password_hash"] if u else DUMMY_HASH, password if bounded else "invalid"
        )
        if not bounded or not u or not correct:
            return jsonify(error="Identifiant ou mot de passe incorrect."), 401
        clear_attempt(store, attempt)
        issue(store, u["id"], expected_hash=u["password_hash"])
        store.log(u["name"], "login", "Connexion au studio")
        return jsonify(ok=True)

    @app.post("/api/studio/logout")
    def auth_logout():
        revoke(store)
        return jsonify(ok=True)

    @app.get("/api/studio/security")
    def security_status():
        return jsonify(
            sessions=store.one(
                "SELECT COUNT(*) AS n FROM studio_sessions WHERE user_id=? AND scope='full' AND expires_at>? AND seen_at>?",
                (g.user["id"], time.time(), time.time() - 3600),
            )["n"],
            preview=app.config["PREVIEW"],
        )

    @app.post("/api/studio/security/password")
    def change_password():
        if app.config["PREVIEW"]:
            raise PermissionError(
                "Le mot de passe de l’aperçu ne peut pas être modifié."
            )
        b = json_body()
        replacement = valid_password(b.get("password"))
        old = b.get("current_password")
        attempt = reserve_attempt(store, "security:" + g.user["id"])
        if attempt is None:
            return throttled()
        user = store.one("SELECT * FROM studio_users WHERE id=?", (g.user["id"],))
        if (
            not isinstance(old, str)
            or len(old) > 128
            or not check_password_hash(user["password_hash"], old)
        ):
            return jsonify(error="Mot de passe actuel incorrect."), 401
        hashed = generate_password_hash(replacement)
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            if not c.execute(
                "UPDATE studio_users SET password_hash=? WHERE id=? AND password_hash=?",
                (hashed, user["id"], user["password_hash"]),
            ).rowcount:
                raise Conflict("Le mot de passe a changé. Reconnecte-toi.")
            c.execute("DELETE FROM studio_sessions WHERE user_id=?", (user["id"],))
        clear_attempt(store, attempt)
        issue(store, user["id"], expected_hash=hashed)
        store.log(
            user["name"],
            "security",
            "Mot de passe renouvelé, anciennes sessions fermées",
        )
        return jsonify(ok=True)

    @app.post("/api/studio/security/sessions")
    def close_other_sessions():
        with store.db() as c:
            c.execute(
                "DELETE FROM studio_sessions WHERE user_id=? AND token_hash<>? AND scope<>'internal'",
                (g.user["id"], g.auth_session["token_hash"]),
            )
        return jsonify(ok=True)


def health_token(secret):
    return (
        hmac.new(
            secret.encode(), b"studio-private-health-v1", hashlib.sha256
        ).hexdigest()
        if secret
        else ""
    )
