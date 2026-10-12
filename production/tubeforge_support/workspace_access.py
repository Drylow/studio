"""Optional hosted-workspace authentication. Desktop stays unchanged when disabled.

One shared workspace with named admin/worker access, not isolated tenants.
Only password hashes are stored; API connections remain owner-managed.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

from fastapi.responses import JSONResponse

log = logging.getLogger("tubeforge.access")


class Access:
    def __init__(self, path):
        self.path = Path(path)
        self.stamp = None
        self.users = {}
        self.cache = {}
        self.reload()

    def reload(self):
        stat = self.path.stat()
        stamp = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
        if stamp != self.stamp:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not data or any(u.get("role") not in ("admin", "worker") or not u.get("password_hash") for u in data.values()):
                raise ValueError("Invalid workspace access registry")
            self.users, self.stamp = data, stamp
            self.cache.clear()

    def authenticate(self, header):
        try:
            self.reload()
            if not header or len(header) > 2048 or not header.startswith("Basic "):
                return None
            raw = base64.b64decode(header[6:], validate=True).decode("utf-8")
            username, password = raw.split(":", 1)
            user = self.users.get(username)
            if not user or len(password) > 512:
                return None
            key = hashlib.sha256(header.encode()).digest()
            if self.cache.get(key, 0) > time.monotonic():
                return {"username": username, "role": user["role"]}
            algorithm, rounds, salt, expected = user["password_hash"].split("$")
            if algorithm != "pbkdf2_sha256" or not 100000 <= int(rounds) <= 1000000:
                return None
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
            if not hmac.compare_digest(actual, expected):
                return None
            if len(self.cache) > 128:
                self.cache.clear()
            self.cache[key] = time.monotonic() + 30
            return {"username": username, "role": user["role"]}
        except (OSError, ValueError, UnicodeError, TypeError, KeyError):
            return None


def install(app):
    if getattr(app.state, "workspace_access_installed", False):
        return
    path = os.environ.get("TUBEFORGE_USERS_FILE", "")
    required = os.environ.get("TUBEFORGE_REQUIRE_AUTH") == "1"
    if not path:
        if required:
            raise RuntimeError("Hosted TubeForge requires a workspace access registry")
        return
    access = Access(path)

    @app.middleware("http")
    async def authenticate(request, call_next):
        if request.url.path == "/healthz" and request.method == "GET":
            return JSONResponse({"status": "ok"})
        user = access.authenticate(request.headers.get("authorization"))
        if not user:
            return JSONResponse({"detail": "Connexion TubeForge requise"}, 401,
                                headers={"WWW-Authenticate": 'Basic realm="TubeForge", charset="UTF-8"',
                                         "Cache-Control": "no-store"})
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if request.headers.get("sec-fetch-site") == "cross-site" or (origin and urlsplit(origin).netloc != request.url.netloc):
                return JSONResponse({"detail": "Origine de la requête refusée"}, 403)
            if user["role"] != "admin" and request.url.path == "/api/settings":
                return JSONResponse({"detail": "Les connexions API sont gérées par le propriétaire"}, 403)
            log.info("workspace_write user=%s method=%s path=%s", user["username"], request.method, request.url.path)
        request.state.workspace_user = user
        if request.url.path == "/api/workspace/session" and request.method == "GET":
            return JSONResponse(user)
        return await call_next(request)

    app.state.workspace_access_installed = True
