"""Private access: revocable sessions, password throttling and mandatory TOTP.

Only password-proven pending sessions may enrol or answer a second factor.
No pending session can reach the workspace, media or operational APIs.
"""

import base64
from contextlib import contextmanager
import hashlib
import hmac
import io
import json
import re
import secrets
import time

from cryptography.fernet import Fernet
from flask import current_app, g, jsonify, request, session
import pyotp
import qrcode
from werkzeug.security import check_password_hash, generate_password_hash

from studio.store import Conflict, now, uid

PUBLIC_APIS = {
    "/api/studio/bootstrap",
    "/api/studio/setup",
    "/api/studio/login",
    "/api/studio/logout",
    "/api/studio/auth/enrol",
    "/api/studio/auth/verify",
    "/api/studio/auth/finish",
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
        CREATE TABLE IF NOT EXISTS studio_mfa(
          user_id TEXT PRIMARY KEY REFERENCES studio_users(id), secret TEXT NOT NULL,
          last_step INTEGER NOT NULL DEFAULT -1);
        CREATE TABLE IF NOT EXISTS studio_recovery_codes(
          user_id TEXT NOT NULL REFERENCES studio_users(id), code_hash TEXT NOT NULL,
          PRIMARY KEY(user_id,code_hash));
        """)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def equal(left, right):
    return hmac.compare_digest(str(left).encode(), str(right).encode())


def cipher():
    key = current_app.config["SECRET_KEY"].encode()
    return Fernet(
        base64.urlsafe_b64encode(hmac.digest(key, b"studio-mfa-v1", "sha256"))
    )


def seal(value):
    return cipher().encrypt(json.dumps(value).encode()).decode()


def unseal(value):
    return json.loads(cipher().decrypt(value.encode()))


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
    if token:
        with store.db() as c:
            c.execute(
                "DELETE FROM studio_sessions WHERE token_hash=?", (digest(token),)
            )
    container.clear()


def issue(store, user_id, *, scope="full", private=None, container=session, ttl=None):
    revoke(store, container)
    token = secrets.token_urlsafe(32)
    at = time.time()
    lifespan = ttl or (43200 if scope == "full" else 600)
    with store.db() as c:
        c.execute("DELETE FROM studio_sessions WHERE expires_at<?", (at,))
        c.execute(
            "INSERT INTO studio_sessions VALUES(?,?,?,?,?,?)",
            (
                digest(token),
                user_id,
                scope,
                at + lifespan,
                at,
                seal(private) if private else "",
            ),
        )
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
        return None
    if (
        record["scope"] == "full"
        and current_app.config["MFA_REQUIRED"]
        and not current_app.config["PREVIEW"]
        and not current_app.config.get("LOCAL_OWNER")
        and not store.one(
            "SELECT user_id FROM studio_mfa WHERE user_id=?", (user["id"],)
        )
    ):
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


def login_stage(store, user_id):
    if not current_app.config["MFA_REQUIRED"]:
        issue(store, user_id)
    elif store.one("SELECT user_id FROM studio_mfa WHERE user_id=?", (user_id,)):
        issue(store, user_id, scope="challenge")
    else:
        issue(store, user_id, scope="enrol", private={"secret": pyotp.random_base32()})


def pending(scope):
    record = getattr(g, "auth_session", None)
    if not record or record["scope"] not in scope:
        raise PermissionError("Reconnecte-toi avant de confirmer ton accès.")
    return record


def auth_status():
    record = getattr(g, "auth_session", None)
    if not record or record["scope"] in {"full", "internal"}:
        return None
    result = {"stage": record["scope"]}
    if record["scope"] == "recovery":
        result["codes"] = unseal(record["private_data"])["codes"]
    return result


def accept_totp(c, user_id, code, *, secret=None):
    """Consume a step once. Called inside an immediate SQLite transaction."""
    if not re.fullmatch(r"[0-9]{6}", code):
        return False
    record = c.execute(
        "SELECT * FROM studio_mfa WHERE user_id=?", (user_id,)
    ).fetchone()
    last = record["last_step"] if record and secret is None else -1
    secret = secret or (unseal(record["secret"]) if record else None)
    if not secret:
        return False
    current = int(time.time()) // 30
    totp = pyotp.TOTP(secret)
    for step in (current, current - 1, current + 1):
        if step > last and hmac.compare_digest(totp.at(step * 30), code):
            c.execute(
                "INSERT INTO studio_mfa VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET secret=excluded.secret,last_step=excluded.last_step",
                (user_id, seal(secret), step),
            )
            return True
    return False


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
        login_stage(store, user_id)
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
        bounded = isinstance(password, str) and 1 <= len(password) <= 128
        correct = check_password_hash(
            u["password_hash"] if u else DUMMY_HASH, password if bounded else "invalid"
        )
        if not bounded or not u or not correct:
            return jsonify(error="Identifiant ou mot de passe incorrect."), 401
        clear_attempt(store, attempt)
        login_stage(store, u["id"])
        return jsonify(ok=True)

    @app.post("/api/studio/logout")
    def auth_logout():
        revoke(store)
        return jsonify(ok=True)

    @app.post("/api/studio/auth/enrol")
    def auth_enrol():
        record = pending({"enrol"})
        secret = unseal(record["private_data"])["secret"]
        user = store.one(
            "SELECT username FROM studio_users WHERE id=?", (record["user_id"],)
        )
        uri = pyotp.TOTP(secret).provisioning_uri(
            user["username"], issuer_name="Edgerunners Studio"
        )
        image = qrcode.make(uri)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return jsonify(
            secret=secret,
            uri=uri,
            qr="data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(),
        )

    @app.post("/api/studio/auth/verify")
    def auth_verify():
        record = pending({"enrol", "challenge"})
        b = json_body()
        code = str(b.get("code", ""))[:128].strip()
        user_id = record["user_id"]
        attempt = reserve_attempt(store, "mfa:" + user_id)
        if attempt is None:
            return throttled()
        recovered = False
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            # A concurrent successful verification must invalidate this pending cookie.
            if not c.execute(
                "SELECT 1 FROM studio_sessions WHERE token_hash=?",
                (record["token_hash"],),
            ).fetchone():
                raise PermissionError("Ce code a déjà été confirmé. Reconnecte-toi.")
            if b.get("recovery") is True and record["scope"] == "challenge":
                normalized = code.replace("-", "").replace(" ", "").upper()
                recovered = bool(
                    c.execute(
                        "DELETE FROM studio_recovery_codes WHERE user_id=? AND code_hash=?",
                        (user_id, digest(normalized)),
                    ).rowcount
                )
                accepted = recovered
            else:
                secret = (
                    unseal(record["private_data"])["secret"]
                    if record["scope"] == "enrol"
                    else None
                )
                accepted = accept_totp(c, user_id, code, secret=secret)
            if not accepted:
                return (
                    jsonify(
                        error="Code incorrect ou déjà utilisé. Utilise le nouveau code de ton application."
                    ),
                    401,
                )
            c.execute(
                "DELETE FROM studio_sessions WHERE token_hash=?",
                (record["token_hash"],),
            )
            if recovered or record["scope"] == "enrol":
                c.execute("DELETE FROM studio_sessions WHERE user_id=?", (user_id,))
            if record["scope"] == "enrol":
                codes = [secrets.token_hex(10).upper() for _ in range(8)]
                c.execute(
                    "DELETE FROM studio_recovery_codes WHERE user_id=?", (user_id,)
                )
                c.executemany(
                    "INSERT INTO studio_recovery_codes VALUES(?,?)",
                    [(user_id, digest(code)) for code in codes],
                )
        clear_attempt(store, attempt)
        if recovered:
            issue(
                store, user_id, scope="enrol", private={"secret": pyotp.random_base32()}
            )
        elif record["scope"] == "enrol":
            issue(store, user_id, scope="recovery", private={"codes": codes})
        else:
            issue(store, user_id)
            store.log("Studio", "login", "Connexion avec double authentification")
        return jsonify(ok=True)

    @app.post("/api/studio/auth/finish")
    def auth_finish():
        record = pending({"recovery"})
        if json_body().get("saved") is not True:
            raise ValueError("Enregistre tes codes de secours avant de continuer.")
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            if not c.execute(
                "DELETE FROM studio_sessions WHERE token_hash=?",
                (record["token_hash"],),
            ).rowcount:
                raise PermissionError("Cette connexion a expiré. Reconnecte-toi.")
        issue(store, record["user_id"])
        return jsonify(ok=True)

    @app.get("/api/studio/security")
    def security_status():
        return jsonify(
            mfa=bool(
                store.one(
                    "SELECT user_id FROM studio_mfa WHERE user_id=?", (g.user["id"],)
                )
            ),
            sessions=store.one(
                "SELECT COUNT(*) AS n FROM studio_sessions WHERE user_id=? AND scope='full' AND expires_at>? AND seen_at>?",
                (g.user["id"], time.time(), time.time() - 3600),
            )["n"],
            recovery_remaining=store.one(
                "SELECT COUNT(*) AS n FROM studio_recovery_codes WHERE user_id=?",
                (g.user["id"],),
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
            if app.config["MFA_REQUIRED"] and not accept_totp(
                c, user["id"], str(b.get("code", ""))[:128]
            ):
                return jsonify(error="Code de sécurité incorrect ou déjà utilisé."), 401
            if not c.execute(
                "UPDATE studio_users SET password_hash=? WHERE id=? AND password_hash=?",
                (hashed, user["id"], user["password_hash"]),
            ).rowcount:
                raise Conflict("Le mot de passe a changé. Reconnecte-toi.")
            c.execute("DELETE FROM studio_sessions WHERE user_id=?", (user["id"],))
        clear_attempt(store, attempt)
        issue(store, user["id"])
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
